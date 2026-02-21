import os
import sys
import shutil
import subprocess
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFileDialog, QTextEdit, QComboBox, 
                             QGroupBox, QLineEdit, QProgressBar, QTableWidget,
                             QTableWidgetItem, QHeaderView, QMessageBox, QTabWidget,
                             QFormLayout, QFrame, QGridLayout, QSplitter, QInputDialog,
                             QDialog, QDialogButtonBox, QCheckBox, QStackedWidget, QTabBar)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QColor, QPixmap, QTextCursor

from ui.theme import Theme
from ui.components import InfoCard, ActionButton, CompactGroupBox, create_h_layout, create_v_layout
from core.command_thread import CommandThread
from core.adb_fastboot import (get_devices, fetch_partitions_from_device, check_tools, 
                               get_adb_info, get_fastboot_info, get_adb_metrics, is_scrcpy_available)
from utils.logger import save_session_log, start_boot_monitor
from utils.settings import SettingsManager
from utils.paths import get_resource_path

APP_VERSION = "v1.4.0"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Naz Android Toolkit {APP_VERSION}")
        self.setMinimumSize(1000, 750) 
        self.setAcceptDrops(True)
        self.is_flashing = False
        self.session_log = []
        self.settings = SettingsManager()
        self.info_labels = {}
        self.modified_props = {}
        self.active_threads = []
        
        self.setStyleSheet(Theme.get_stylesheet())
        self.init_ui()
        self.check_env()
        self.refresh_devices()
        
        # Live Metrics Timer
        self.metrics_timer = QTimer()
        self.metrics_timer.timeout.connect(self.update_live_metrics)
        self.metrics_timer.start(5000)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext == ".apk":
                self.handle_apk_drop(f)
            elif ext in [".img", ".bin"]:
                self.handle_image_drop(f)
            else:
                self.log(f"Unsupported file dropped: {os.path.basename(f)}")

    def handle_apk_drop(self, file_path):
        serial = self.device_combo.currentData()
        if not serial or "ADB" not in self.device_combo.currentText():
            QMessageBox.warning(self, "ADB Error", "Please connect a device in ADB mode to install APKs.")
            return
        
        reply = QMessageBox.question(self, "Install APK", 
                                   f"Do you want to install {os.path.basename(file_path)}?",
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.tabs.setCurrentIndex(1)
            self.run_command(f'adb install "{file_path}"')

    def handle_image_drop(self, file_path):
        self.tabs.setCurrentIndex(2)
        selected_part = self.partition_combo.currentText().strip()
        partition = selected_part if selected_part else os.path.basename(file_path).lower().replace(".img", "").replace(".bin", "")
        
        row = self.queue_table.rowCount()
        self.queue_table.insertRow(row)
        
        part_item = QTableWidgetItem(partition)
        self.queue_table.setItem(row, 0, part_item)
        
        file_item = QTableWidgetItem(file_path)
        file_item.setFlags(file_item.flags() & ~Qt.ItemIsEditable)
        file_item.setToolTip(file_path)
        self.queue_table.setItem(row, 1, file_item)
        
        status_item = QTableWidgetItem("Pending")
        status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
        self.queue_table.setItem(row, 2, status_item)
        self.log(f"Added to queue via drag-drop: {os.path.basename(file_path)}")

    def check_env(self):
        missing = check_tools()
        if missing:
            QMessageBox.critical(self, "Environment Error", 
                                f"Missing tools: {', '.join(missing)}\nPlease install Android Platform Tools.")

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = create_v_layout(margins=(10, 10, 10, 10), spacing=8)

        # Header (Unified Navigation)
        header_container = QFrame()
        header_container.setObjectName("header_frame")
        header_layout = create_h_layout(margins=(15, 10, 15, 10), spacing=20)
        
        logo_label = QLabel()
        logo_path = get_resource_path(os.path.join("assets", "logo.svg"))
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path).scaled(42, 42, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(pixmap)
        header_layout.addWidget(logo_label)

        title_layout = create_v_layout(spacing=0)
        title = QLabel("Naz Android Toolkit")
        title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 18px; font-weight: 800; border: none; background: transparent;")
        sub_title = QLabel(f"Professional Android Fastboot Recovery Suite | {APP_VERSION}")
        sub_title.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 9px; font-weight: 600; border: none; background: transparent;")
        title_layout.addWidget(title)
        title_layout.addWidget(sub_title)
        header_layout.addLayout(title_layout)
        
        header_layout.addStretch()
        
        # Device Selection
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(200)
        self.device_combo.currentIndexChanged.connect(self.on_device_selected)
        btn_refresh = ActionButton("Refresh")
        btn_refresh.clicked.connect(self.refresh_devices)
        
        header_layout.addWidget(self.device_combo)
        header_layout.addWidget(btn_refresh)
        
        header_container.setLayout(header_layout)
        main_layout.addWidget(header_container)

        # Navigation Bar (Second Frame)
        nav_container = QFrame()
        nav_container.setObjectName("nav_frame")
        nav_layout = create_h_layout(margins=(10, 0, 10, 0))
        
        self.nav_bar = QTabBar()
        self.nav_bar.setExpanding(False)
        self.nav_bar.setDrawBase(False)
        nav_layout.addWidget(self.nav_bar)
        nav_container.setLayout(nav_layout)
        main_layout.addWidget(nav_container)

        # Content Panels
        self.content_stack = QStackedWidget()
        main_layout.addWidget(self.content_stack)

        self.setup_dashboard_tab()
        self.setup_adb_tab()
        self.setup_fastboot_tab()
        self.setup_tweaks_tab()
        self.setup_logs_tab()

        self.nav_bar.currentChanged.connect(self.content_stack.setCurrentIndex)

        # Bottom UI
        bottom_layout = create_h_layout()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(f"color: {Theme.ACCENT}; font-weight: bold;")
        bottom_layout.addWidget(self.status_label)
        bottom_layout.addStretch()
        self.progress = QProgressBar()
        self.progress.setFixedWidth(300)
        bottom_layout.addWidget(self.progress)
        
        main_layout.addLayout(bottom_layout)
        central_widget.setLayout(main_layout)

    def log(self, text):
        clean_text = text.replace("<b>", "").replace("</b>", "").replace("<font color=", "").replace("</font>", "").replace(">", "")
        self.session_log.append(clean_text)

        color = "#E0E0E0"
        if text.startswith(">"): color = "#FFEB3B"
        elif "OKAY" in text or "Success" in text or "finished" in text: color = Theme.ACCENT
        elif "FAILED" in text or "error" in text or "Error" in text: color = Theme.DANGER
        
        html_text = f'<font color="{color}">{text}</font>'
        
        self.console.append(html_text)
        if hasattr(self, 'fb_console'): self.fb_console.append(html_text)
        if hasattr(self, 'adb_console'): self.adb_console.append(html_text)
        
        self.console.moveCursor(QTextCursor.End)
        if hasattr(self, 'fb_console'): self.fb_console.moveCursor(QTextCursor.End)
        if hasattr(self, 'adb_console'): self.adb_console.moveCursor(QTextCursor.End)

    def setup_dashboard_tab(self):
        tab = QWidget()
        layout = create_v_layout(margins=(15, 5, 15, 15), spacing=12)
        
        grid = QGridLayout()
        grid.setSpacing(8)
        
        self.cards = {}
        # Keys are simplified to avoid slashes and match update logic
        card_configs = [
            ("Model", "Device Model", Theme.ACCENT),
            ("Product", "Build / Product", Theme.ACCENT),
            ("State", "Connection Mode", "#1565C0"),
            ("Root", "Root Status", "#FFC107"),
            ("Bootloader", "Bootloader State", "#F44336"),
            ("Battery", "Battery Level", "#4CAF50"),
            ("Temp", "CPU Temp", "#FF9800"),
            ("Storage", "Storage (Internal)", "#2196F3")
        ]

        for i, (key, title, color) in enumerate(card_configs):
            card = InfoCard(title, color)
            self.cards[f"{key}_card"] = card
            grid.addWidget(card, i // 4, i % 4)

        layout.addLayout(grid)

        mid_layout = QHBoxLayout()
        mid_layout.setSpacing(10)

        mirror_group = CompactGroupBox("Screen Mirroring")
        mirror_inner = create_v_layout(margins=(8, 8, 8, 8))
        btn_mirror = ActionButton("Standard Mirror")
        btn_mirror.clicked.connect(lambda: self.launch_scrcpy("standard"))
        btn_dex = ActionButton("DeX Mode (Off)", style="accent")
        btn_dex.clicked.connect(lambda: self.launch_scrcpy("dex"))
        self.chk_audio = QCheckBox("Forward Audio")
        self.chk_audio.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 11px;")
        
        mirror_inner.addLayout(create_h_layout([btn_mirror, btn_dex]))
        mirror_inner.addWidget(self.chk_audio)
        mirror_group.setLayout(mirror_inner)

        conn_group = CompactGroupBox("Wireless ADB (Android 11+)")
        conn_inner = create_v_layout(margins=(8, 8, 8, 8))
        btn_pair = ActionButton("Pair New Device")
        btn_pair.clicked.connect(self.wireless_pairing_workflow)
        btn_qconnect = ActionButton("Quick Connect")
        btn_qconnect.clicked.connect(self.wireless_quick_connect)
        
        conn_inner.addLayout(create_h_layout([btn_pair, btn_qconnect]))
        conn_group.setLayout(conn_inner)

        mid_layout.addWidget(mirror_group, 1)
        mid_layout.addWidget(conn_group, 1)
        layout.addLayout(mid_layout)

        terminal_group = CompactGroupBox("Manual Command Terminal")
        terminal_layout = create_h_layout(margins=(8, 8, 8, 8))
        self.terminal_tool_combo = QComboBox()
        self.terminal_tool_combo.addItems(["adb", "fastboot"])
        self.terminal_tool_combo.setFixedWidth(90)
        self.terminal_input = QLineEdit()
        self.terminal_input.setPlaceholderText("Enter command...")
        self.terminal_input.returnPressed.connect(self.run_manual_command)
        btn_exec = ActionButton("Execute")
        btn_exec.clicked.connect(self.run_manual_command)
        
        terminal_layout.addWidget(self.terminal_tool_combo)
        terminal_layout.addWidget(self.terminal_input, 1)
        terminal_layout.addWidget(btn_exec)
        terminal_group.setLayout(terminal_layout)
        layout.addWidget(terminal_group)
        
        layout.addStretch()
        tab.setLayout(layout)
        self.nav_bar.addTab("Dashboard")
        self.content_stack.addWidget(tab)

    def setup_adb_tab(self):
        tab = QWidget()
        layout = create_h_layout(margins=(10, 5, 10, 10), spacing=10)
        splitter = QSplitter(Qt.Horizontal)
        
        left_panel = QWidget()
        left_layout = create_v_layout()
        
        app_group = CompactGroupBox("Application Manager")
        app_layout = create_v_layout(margins=(8, 8, 8, 8))
        btn_install = ActionButton("Install APK Package")
        btn_install.clicked.connect(self.install_apk)
        
        uninstall_layout = create_h_layout()
        self.pkg_input = QLineEdit()
        self.pkg_input.setPlaceholderText("com.package.name")
        btn_uninstall = ActionButton("Uninstall")
        btn_uninstall.clicked.connect(lambda: self.run_command(f"adb uninstall {self.pkg_input.text()}", safety=True))
        uninstall_layout.addWidget(self.pkg_input)
        uninstall_layout.addWidget(btn_uninstall)
        
        app_layout.addWidget(btn_install)
        app_layout.addLayout(uninstall_layout)
        app_group.setLayout(app_layout)
        left_layout.addWidget(app_group)

        cmd_group = CompactGroupBox("Custom ADB Shell")
        cmd_layout = create_v_layout(margins=(8, 8, 8, 8))
        self.adb_cmd_input = QLineEdit()
        self.adb_cmd_input.setPlaceholderText("shell pm list packages")
        btn_exec = ActionButton("Run Command")
        btn_exec.clicked.connect(self.run_custom_adb)
        
        btn_shell = ActionButton("Open Interactive Shell", style="accent")
        btn_shell.clicked.connect(self.open_interactive_shell)
        
        cmd_layout.addWidget(self.adb_cmd_input)
        cmd_layout.addWidget(btn_exec)
        cmd_layout.addWidget(btn_shell)
        cmd_group.setLayout(cmd_layout)
        left_layout.addWidget(cmd_group)

        sideload_group = CompactGroupBox("ADB Sideload (Recovery)")
        sideload_layout = create_v_layout(margins=(8, 8, 8, 8))
        btn_reboot_sideload = ActionButton("Reboot to Sideload")
        btn_reboot_sideload.clicked.connect(lambda: self.run_command("adb reboot sideload"))
        
        sideload_input_layout = create_h_layout()
        self.sideload_path_edit = QLineEdit()
        self.sideload_path_edit.setPlaceholderText("Select .zip or .apk")
        btn_browse_sideload = ActionButton("...")
        btn_browse_sideload.setFixedWidth(40)
        btn_browse_sideload.clicked.connect(self.browse_sideload_file)
        sideload_input_layout.addWidget(self.sideload_path_edit)
        sideload_input_layout.addWidget(btn_browse_sideload)
        
        btn_sideload_exec = ActionButton("START SIDELOAD", style="danger")
        btn_sideload_exec.clicked.connect(self.run_sideload)
        
        sideload_layout.addWidget(btn_reboot_sideload)
        sideload_layout.addLayout(sideload_input_layout)
        sideload_layout.addWidget(btn_sideload_exec)
        sideload_group.setLayout(sideload_layout)
        left_layout.addWidget(sideload_group)
        
        left_layout.addStretch()
        left_panel.setLayout(left_layout)
        
        right_panel = CompactGroupBox("Console Output")
        right_layout = create_v_layout(margins=(5, 5, 5, 5))
        self.adb_console = QTextEdit()
        self.adb_console.setReadOnly(True)
        self.adb_console.setStyleSheet(f"background-color: #0A0A0A; color: {Theme.ACCENT}; font-family: 'Consolas', 'Courier New'; font-size: 11px;")
        right_layout.addWidget(self.adb_console)
        right_panel.setLayout(right_layout)
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)
        tab.setLayout(layout)
        self.nav_bar.addTab("ADB Tools")
        self.content_stack.addWidget(tab)

    def setup_fastboot_tab(self):
        tab = QWidget()
        layout = create_h_layout(margins=(10, 5, 10, 10), spacing=10)
        splitter = QSplitter(Qt.Horizontal)
        
        left_panel = QWidget()
        left_layout = create_v_layout()
        
        reboot_group = CompactGroupBox("Reboot Control")
        reboot_layout = QGridLayout()
        reboot_layout.setSpacing(5)
        modes = ["Bootloader", "Fastboot", "Recovery", "System"]
        for i, mode in enumerate(modes):
            btn = ActionButton(mode)
            btn.clicked.connect(lambda checked, m=mode: self.reboot_device(m))
            reboot_layout.addWidget(btn, i//2, i%2)
        reboot_group.setLayout(reboot_layout)
        left_layout.addWidget(reboot_group)

        queue_group = CompactGroupBox("Flash Queue")
        queue_layout = create_v_layout(margins=(8, 8, 8, 8))
        
        input_layout = create_h_layout()
        self.partition_combo = QComboBox()
        self.partition_combo.setEditable(True)
        btn_fetch = ActionButton("Fetch")
        btn_fetch.setFixedWidth(80)
        btn_fetch.clicked.connect(self.fetch_partitions)
        btn_browse = ActionButton("Add")
        btn_browse.setFixedWidth(80)
        btn_browse.clicked.connect(lambda: self.browse_file())
        
        input_layout.addWidget(self.partition_combo, 1)
        input_layout.addWidget(btn_fetch)
        input_layout.addWidget(btn_browse)
        queue_layout.addLayout(input_layout)

        self.queue_table = QTableWidget(0, 3)
        self.queue_table.setHorizontalHeaderLabels(["Part", "Image", "Status"])
        self.queue_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.queue_table.model().rowsInserted.connect(self.update_queue_validation)
        self.queue_table.model().rowsRemoved.connect(self.update_queue_validation)
        queue_layout.addWidget(self.queue_table)

        btn_row = create_h_layout()
        self.btn_flash = ActionButton("START BATCH FLASH", style="danger")
        self.btn_flash.setEnabled(False)
        self.btn_flash.clicked.connect(self.process_queue)
        btn_clear = ActionButton("Clear")
        btn_clear.clicked.connect(lambda: self.queue_table.setRowCount(0))
        btn_row.addWidget(self.btn_flash, 2)
        btn_row.addWidget(btn_clear, 1)
        queue_layout.addLayout(btn_row)
        queue_group.setLayout(queue_layout)
        left_layout.addWidget(queue_group, 1)

        fmt_group = CompactGroupBox("Erase / Format")
        fmt_layout = QGridLayout()
        fmt_layout.setSpacing(5)
        self.fmt_partition_combo = QComboBox()
        self.fmt_partition_combo.setEditable(True)
        self.fs_combo = QComboBox()
        self.fs_combo.addItems(["f2fs", "ext4", "fat"])
        
        btn_format = ActionButton("Format")
        btn_format.clicked.connect(self.format_partition)
        btn_erase = ActionButton("Erase")
        btn_erase.clicked.connect(lambda: self.run_command(f"fastboot erase {self.fmt_partition_combo.currentText()}", safety=True))
        
        fmt_layout.addWidget(QLabel("Partition:"), 0, 0)
        fmt_layout.addWidget(self.fmt_partition_combo, 0, 1)
        fmt_layout.addWidget(QLabel("FS:"), 1, 0)
        fmt_layout.addWidget(self.fs_combo, 1, 1)
        fmt_layout.addWidget(btn_format, 2, 0)
        fmt_layout.addWidget(btn_erase, 2, 1)
        fmt_group.setLayout(fmt_layout)
        left_layout.addWidget(fmt_group)
        
        left_layout.addStretch()
        left_panel.setLayout(left_layout)
        
        right_panel = CompactGroupBox("Fastboot Log")
        right_layout = create_v_layout(margins=(5, 5, 5, 5))
        self.fb_console = QTextEdit()
        self.fb_console.setReadOnly(True)
        self.fb_console.setStyleSheet(f"background-color: #0A0A0A; color: {Theme.ACCENT}; font-family: 'Consolas', 'Courier New'; font-size: 11px;")
        right_layout.addWidget(self.fb_console)
        right_panel.setLayout(right_layout)
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)
        tab.setLayout(layout)
        self.nav_bar.addTab("Fastboot")
        self.content_stack.addWidget(tab)

    def setup_tweaks_tab(self):
        tab = QWidget()
        layout = create_h_layout(margins=(10, 5, 10, 10), spacing=10)
        splitter = QSplitter(Qt.Horizontal)
        
        left_panel = QWidget()
        left_layout = create_v_layout()
        
        spoof_group = CompactGroupBox("Device Identity Spoofing (Beta / Experimental)")
        spoof_layout = create_v_layout(margins=(8, 8, 8, 8))
        preset_layout = create_h_layout()
        self.preset_combo = QComboBox()
        self.load_presets()
        btn_apply_preset = ActionButton("Apply Live")
        btn_apply_preset.clicked.connect(self.apply_identity_preset)
        btn_gen_script = ActionButton("Install Fix", style="accent")
        btn_gen_script.clicked.connect(self.install_magisk_fix)
        preset_layout.addWidget(self.preset_combo, 1)
        preset_layout.addWidget(btn_apply_preset)
        preset_layout.addWidget(btn_gen_script)
        spoof_layout.addLayout(preset_layout)
        spoof_layout.addWidget(QLabel(f"<font color='{Theme.DANGER}'><b>Experimental:</b> Some features may not work as expected.</font>"))
        spoof_group.setLayout(spoof_layout)
        left_layout.addWidget(spoof_group)

        prop_group = CompactGroupBox("Build Property Editor (Experimental)")
        prop_layout = create_v_layout(margins=(8, 8, 8, 8))
        search_layout = create_h_layout()
        self.prop_search = QLineEdit()
        self.prop_search.setPlaceholderText("Search property...")
        btn_read_all = ActionButton("Read All")
        btn_read_all.clicked.connect(self.read_all_props)
        btn_export_props = ActionButton("Export")
        btn_export_props.clicked.connect(self.export_props_to_file)
        search_layout.addWidget(self.prop_search)
        search_layout.addWidget(btn_read_all)
        search_layout.addWidget(btn_export_props)
        
        self.prop_table = QTableWidget(0, 2)
        self.prop_table.setHorizontalHeaderLabels(["Key", "Value"])
        self.prop_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.prop_table.itemChanged.connect(self.track_prop_change)
        
        batch_btn_layout = create_h_layout()
        btn_apply_all = ActionButton("APPLY ALL CHANGES", style="accent")
        btn_apply_all.clicked.connect(self.apply_all_props)
        btn_clear_pending = ActionButton("Clear")
        btn_clear_pending.clicked.connect(self.clear_pending_props)
        batch_btn_layout.addWidget(btn_apply_all, 2)
        batch_btn_layout.addWidget(btn_clear_pending, 1)
        
        prop_layout.addLayout(search_layout)
        prop_layout.addWidget(self.prop_table)
        prop_layout.addLayout(batch_btn_layout)
        prop_group.setLayout(prop_layout)
        left_layout.addWidget(prop_group, 1)
        
        left_panel.setLayout(left_layout)
        
        right_panel = CompactGroupBox("Tweak Log")
        right_layout = create_v_layout(margins=(5, 5, 5, 5))
        self.tweak_console = QTextEdit()
        self.tweak_console.setReadOnly(True)
        self.tweak_console.setStyleSheet(f"background-color: #0A0A0A; color: {Theme.ACCENT}; font-family: 'Consolas'; font-size: 11px;")
        right_layout.addWidget(self.tweak_console)
        right_panel.setLayout(right_layout)
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)
        tab.setLayout(layout)
        self.nav_bar.addTab("Tweaks")
        self.content_stack.addWidget(tab)

    def setup_logs_tab(self):
        tab = QWidget()
        layout = create_v_layout(margins=(10, 10, 10, 10))
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet(f"background-color: black; color: {Theme.ACCENT}; font-family: 'Consolas', monospace; font-size: 11px;")
        layout.addWidget(self.console)
        
        btn_layout = create_h_layout()
        btn_clear = ActionButton("Clear Console")
        btn_clear.clicked.connect(self.console.clear)
        btn_save = ActionButton("Save Logs")
        btn_save.clicked.connect(self.save_logs)
        btn_boot = ActionButton("Start Boot Monitor", style="accent")
        btn_boot.clicked.connect(self.boot_monitor)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_clear)
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_boot)
        layout.addLayout(btn_layout)
        tab.setLayout(layout)
        self.nav_bar.addTab("Logs")
        self.content_stack.addWidget(tab)

    def refresh_devices(self):
        self.device_combo.clear()
        devices = get_devices()
        for dev in devices:
            self.device_combo.addItem(f"{dev['type']}: {dev['serial']}", dev['serial'])
        if not devices:
            self.status_label.setText("No devices connected.")
            self.status_label.setStyleSheet(f"color: {Theme.DANGER}; font-weight: bold;")
        else:
            self.status_label.setText(f"Connected: {len(devices)} device(s)")
            self.status_label.setStyleSheet(f"color: {Theme.ACCENT}; font-weight: bold;")

    def on_device_selected(self):
        serial = self.device_combo.currentData()
        if not serial: return
        text = self.device_combo.currentText()
        is_fastboot = "FASTBOOT" in text
        is_sideload = "SIDELOAD" in text
        
        for card in self.cards.values(): 
            card.set_value("...")
        
        if is_fastboot:
            info = get_fastboot_info(serial)
            self.cards["Model_card"].set_value("N/A")
            self.cards["Product_card"].set_value(info["Product"])
            self.cards["State_card"].set_value("FASTBOOT", color="#FFEB3B") # Yellow
            
            bl_state = info["Unlocked"]
            bl_color = Theme.ACCENT if bl_state == "yes" else Theme.DANGER if bl_state == "no" else Theme.TEXT_SECONDARY
            self.cards["Bootloader_card"].set_value("Unlocked" if bl_state == "yes" else "Locked" if bl_state == "no" else "Unknown", color=bl_color)
            
            self.cards["Root_card"].set_value("N/A")
            for m_card in ["Battery_card", "Temp_card", "Storage_card"]:
                self.cards[m_card].set_value("N/A")
            self.fetch_partitions()
        elif is_sideload:
            for key in ["Model", "Product", "Bootloader", "Root", "Battery", "Temp", "Storage"]:
                self.cards[f"{key}_card"].set_value("N/A")
            self.cards["State_card"].set_value("SIDELOAD", color="#FFEB3B") # Yellow
        else:
            info = get_adb_info(serial)
            self.cards["Model_card"].set_value(info["Model"])
            self.cards["Product_card"].set_value(info["Build"])
            self.cards["State_card"].set_value("ADB", color="#FFEB3B") # Yellow
            self.cards["Bootloader_card"].set_value("Check in Fastboot")
            
            root_color = Theme.ACCENT if "Yes" in info["Root"] else Theme.DANGER
            self.cards["Root_card"].set_value(info["Root"], color=root_color)
            self.update_live_metrics()

    def update_live_metrics(self):
        serial = self.device_combo.currentData()
        if not serial or "ADB" not in self.device_combo.currentText(): return
        metrics = get_adb_metrics(serial)
        self.cards["Battery_card"].set_value(metrics["Battery"])
        self.cards["Temp_card"].set_value(metrics["Temp"])
        self.cards["Storage_card"].set_value(metrics["Storage"])

    def reboot_device(self, mode):
        serial = self.device_combo.currentData()
        if not serial: return
        is_adb = "ADB" in self.device_combo.currentText()
        cmd = f"adb reboot {mode.lower()}" if is_adb else f"fastboot reboot {mode.lower()}"
        if mode == "System": cmd = "adb reboot" if is_adb else "fastboot reboot"
        self.run_command(cmd)

    def fetch_partitions(self):
        serial = self.device_combo.currentData()
        if serial:
            cats = fetch_partitions_from_device(serial)
            for combo in [self.partition_combo, self.fmt_partition_combo]:
                combo.clear()
                if cats["Standard"]:
                    combo.addItem("--- STANDARD PARTITIONS ---")
                    combo.model().item(combo.count()-1).setEnabled(False)
                    combo.addItems(cats["Standard"])
                if cats["Critical/Advanced"]:
                    if cats["Standard"]: combo.insertSeparator(combo.count())
                    combo.addItem("--- CRITICAL/ADVANCED ---")
                    combo.model().item(combo.count()-1).setEnabled(False)
                    combo.addItems(cats["Critical/Advanced"])
                if cats["Standard"]: combo.setCurrentIndex(1)

    def browse_file(self, key="last_image_dir"):
        last_dir = self.settings.get_last_dir(key)
        files, _ = QFileDialog.getOpenFileNames(self, "Select Images", last_dir, "Images (*.img *.bin)")
        if files:
            self.settings.set_last_dir(os.path.dirname(files[0]), key)
            selected_part = self.partition_combo.currentText().strip()
            for f in files:
                partition = selected_part if selected_part else os.path.basename(f).lower().replace(".img", "").replace(".bin", "")
                row = self.queue_table.rowCount()
                self.queue_table.insertRow(row)
                part_item = QTableWidgetItem(partition)
                self.queue_table.setItem(row, 0, part_item)
                file_item = QTableWidgetItem(f)
                file_item.setFlags(file_item.flags() & ~Qt.ItemIsEditable)
                file_item.setToolTip(f)
                self.queue_table.setItem(row, 1, file_item)
                status_item = QTableWidgetItem("Pending")
                status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
                self.queue_table.setItem(row, 2, status_item)

    def install_apk(self):
        last_dir = self.settings.get_last_dir("last_apk_dir")
        apk, _ = QFileDialog.getOpenFileName(self, "Select APK", last_dir, "APK Files (*.apk)")
        if apk:
            self.settings.set_last_dir(os.path.dirname(apk), "last_apk_dir")
            self.run_command(f'adb install "{apk}"')

    def set_ui_enabled(self, enabled):
        self.device_combo.setEnabled(enabled)
        self.tabs.setEnabled(enabled)
        self.status_label.setText("Operation in progress..." if not enabled else "Ready")

    def run_command(self, cmd, callback=None, safety=False):
        serial = self.device_combo.currentData()
        if serial:
            if "adb" in cmd: cmd = cmd.replace("adb", f"adb -s {serial}", 1)
            if "fastboot" in cmd: cmd = cmd.replace("fastboot", f"fastboot -s {serial}", 1)
        
        if safety:
            warning_msg = f"This operation will run the following command:\n\n{cmd}\n\n"
            if any(x in cmd for x in ["flash", "erase", "format", "uninstall"]):
                warning_msg += "WARNING: This is a high-risk operation that could result in data loss or a bricked device if used incorrectly.\n\n"
            warning_msg += "Do you want to proceed?"
            reply = QMessageBox.warning(self, "Safety Verification", warning_msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No: return

        self.set_ui_enabled(False)
        self.log(f"> {cmd}")
        thread = CommandThread(cmd)
        self.active_threads.append(thread)
        thread.output_signal.connect(self.log)
        def on_finished_internal(code):
            if thread in self.active_threads: self.active_threads.remove(thread)
            self.set_ui_enabled(True)
            if callback: callback(code)
        thread.finished_signal.connect(on_finished_internal)
        thread.start()

    def update_queue_validation(self):
        has_items = self.queue_table.rowCount() > 0
        if hasattr(self, 'btn_flash'): self.btn_flash.setEnabled(has_items)

    def process_queue(self):
        count = self.queue_table.rowCount()
        if count == 0: return
        cmds = []
        serial = self.device_combo.currentData()
        for i in range(count):
            p = self.queue_table.item(i, 0).text().strip()
            f = self.queue_table.item(i, 1).text().strip()
            base_cmd = f"fastboot flash {p} \"{f}\""
            if serial: base_cmd = base_cmd.replace("fastboot", f"fastboot -s {serial}", 1)
            cmds.append(base_cmd)
        msg = "This operation will run the following commands:\n\n" + "\n".join(cmds) + "\n\nCRITICAL WARNING: Improper flashing can permanently damage your device.\nPROCEED WITH CAUTION!"
        reply = QMessageBox.critical(self, "Batch Safety Verification", msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes and not self.is_flashing:
            self.is_flashing = True
            self.btn_flash.setEnabled(False)
            self.btn_flash.setText("Flashing...")
            self.current_row = 0
            self.progress.setMaximum(count)
            self.progress.setValue(0)
            self.flash_next()

    def flash_next(self):
        if self.current_row < self.queue_table.rowCount():
            p = self.queue_table.item(self.current_row, 0).text().strip()
            f = self.queue_table.item(self.current_row, 1).text().strip()
            if not p:
                self.log(f"Error: No partition specified for {f}")
                self.on_finished(-1)
                return
            self.queue_table.setItem(self.current_row, 2, QTableWidgetItem("Flashing..."))
            self.run_batch_command(f'fastboot flash {p} "{f}"', self.on_finished)
        else:
            self.is_flashing = False
            self.btn_flash.setText("START BATCH FLASH")
            self.btn_flash.setEnabled(True)
            self.progress.setValue(self.progress.maximum())
            self.set_ui_enabled(True)
            self.log("<b>Batch operation complete.</b>")

    def run_batch_command(self, cmd, callback):
        serial = self.device_combo.currentData()
        if serial and "fastboot" in cmd: cmd = cmd.replace("fastboot", f"fastboot -s {serial}", 1)
        if serial and "adb" in cmd: cmd = cmd.replace("adb", f"adb -s {serial}", 1)
        self.log(f"> {cmd}")
        thread = CommandThread(cmd)
        self.active_threads.append(thread)
        thread.output_signal.connect(self.log)
        def on_finished_batch(code):
            if thread in self.active_threads: self.active_threads.remove(thread)
            if callback: callback(code)
        thread.finished_signal.connect(on_finished_batch)
        thread.start()

    def on_finished(self, code):
        success = code == 0
        status = "Success" if success else "Failed"
        color = Theme.ACCENT if success else Theme.DANGER
        status_item = QTableWidgetItem(status)
        status_item.setForeground(QColor(color))
        font = status_item.font()
        font.setBold(True)
        status_item.setFont(font)
        self.queue_table.setItem(self.current_row, 2, status_item)
        self.current_row += 1
        self.progress.setValue(self.current_row)
        self.flash_next()

    def format_partition(self):
        p = self.fmt_partition_combo.currentText().strip()
        fs = self.fs_combo.currentText()
        if not p:
            QMessageBox.warning(self, "Input Error", "Please select or enter a partition name.")
            return
        self.run_command(f"fastboot format:{fs} {p}", safety=True)

    def save_logs(self):
        if not self.session_log: return
        filename = save_session_log(self.session_log)
        QMessageBox.information(self, "Logs Saved", f"Session logs saved to: {filename}")

    def boot_monitor(self):
        serial = self.device_combo.currentData()
        if not serial: return
        if "ADB" not in self.device_combo.currentText():
            QMessageBox.warning(self, "Monitor Error", "Boot monitor requires ADB mode.")
            return
        filename = start_boot_monitor(serial)
        self.run_command(f"adb -s {serial} logcat -v time > {filename} &")
        QMessageBox.information(self, "Boot Monitor", f"Boot monitoring started. Saving to: {filename}")

    def run_manual_command(self):
        tool = self.terminal_tool_combo.currentText()
        cmd_text = self.terminal_input.text().strip()
        if not cmd_text: return
        if cmd_text == "shell" or cmd_text.startswith("shell "):
            if len(cmd_text.split()) == 1:
                QMessageBox.warning(self, "Command Blocked", "Interactive shell is not supported. Please provide a specific command (e.g., 'shell getprop').")
                return
        full_cmd = f"{tool} {cmd_text}"
        is_dangerous = any(x in cmd_text.lower() for x in ["flash", "erase", "format", "repartition", "uninstall", "rm "])
        self.tabs.setCurrentIndex(4)
        self.run_command(full_cmd, safety=is_dangerous)
        self.terminal_input.clear()

    def run_custom_adb(self):
        cmd_text = self.adb_cmd_input.text().strip()
        if not cmd_text: return
        if cmd_text == "shell":
            QMessageBox.warning(self, "Command Blocked", "Interactive shell is not supported in this console. Click 'Open Interactive ADB Shell' instead.")
            return
        if cmd_text.startswith("adb "): cmd_text = cmd_text[4:].strip()
        self.run_command(f"adb {cmd_text}")
        self.adb_cmd_input.clear()

    def open_interactive_shell(self):
        serial = self.device_combo.currentData()
        if not serial or "ADB" not in self.device_combo.currentText():
            QMessageBox.warning(self, "Connection Error", "Please select a device in ADB mode first.")
            return
        import platform
        import subprocess
        cmd = f"adb -s {serial} shell"
        self.log(f"Launching external terminal for shell: {serial}")
        try:
            if platform.system() == "Windows":
                subprocess.Popen(["cmd.exe", "/c", f"start cmd.exe /k {cmd}"])
            else:
                terminals = [
                    ["gnome-terminal", "--", "bash", "-c", f"{cmd}; exec bash"],
                    ["konsole", "-e", "bash", "-c", f"{cmd}; exec bash"],
                    ["xfce4-terminal", "-e", f"bash -c '{cmd}; exec bash'"],
                    ["xterm", "-e", f"bash -c '{cmd}; exec bash'"]
                ]
                success = False
                for term in terminals:
                    try:
                        subprocess.Popen(term)
                        success = True
                        break
                    except FileNotFoundError: continue
                if not success:
                    QMessageBox.warning(self, "Terminal Error", "Could not find a supported terminal emulator (gnome-terminal, konsole, xterm, etc.).")
        except Exception as e:
            self.log(f"Error launching shell: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to launch interactive shell: {str(e)}")

    def wireless_pairing_workflow(self):
        diag = QDialog(self)
        diag.setWindowTitle("Step 1: ADB Wireless Pairing")
        diag.setMinimumWidth(400)
        d_layout = QFormLayout(diag)
        
        addr_input = QLineEdit()
        addr_input.setPlaceholderText("e.g. 192.168.1.5:34567")
        code_input = QLineEdit()
        code_input.setPlaceholderText("6-digit code")
        
        d_layout.addRow("Pairing Address (IP:Port):", addr_input)
        d_layout.addRow("Pairing Code:", code_input)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(diag.accept)
        buttons.rejected.connect(diag.reject)
        d_layout.addRow(buttons)
        
        if diag.exec() == QDialog.Accepted:
            pair_addr = addr_input.text().strip()
            pair_code = code_input.text().strip()
            
            if not pair_addr or not pair_code: return
            
            self.tweak_console.append(f"Attempting to pair with {pair_addr}...")
            
            def on_pair_done(code):
                if code == 0:
                    self.log(f"<b>Successfully paired with {pair_addr}!</b>")
                    # Step 2: Now prompt for connection address
                    conn_addr, ok = QInputDialog.getText(self, "Step 2: Connect", 
                                                       "Enter Connection IP:Port (e.g. 192.168.1.5:5555):")
                    if ok and conn_addr:
                        self.settings.set_last_dir(conn_addr, "last_adb_ip")
                        self.run_command(f"adb connect {conn_addr}")
                else:
                    QMessageBox.critical(self, "Pairing Failed", 
                                       "Pairing failed. Ensure the IP and Code are correct and the phone's pairing screen is still visible.")

            self.run_command(f"adb pair {pair_addr} {pair_code}", callback=on_pair_done)

    def wireless_quick_connect(self):
        last_ip = self.settings.get_last_dir("last_adb_ip")
        ip, ok = QInputDialog.getText(self, "Quick Connect", "Enter Device IP:Port:", text=last_ip)
        if ok and ip:
            self.settings.set_last_dir(ip, "last_adb_ip")
            self.run_command(f"adb connect {ip}")

    def launch_scrcpy(self, mode):
        scrcpy_path = shutil.which("scrcpy")
        if not scrcpy_path:
            QMessageBox.critical(self, "Missing Tool", "Scrcpy executable not found in system PATH.")
            return

        serial = self.device_combo.currentData()
        if not serial or "ADB" not in self.device_combo.currentText():
            QMessageBox.warning(self, "Connection Error", "Mirroring requires an active ADB connection.")
            return

        # Build command list
        cmd_args = [scrcpy_path, "-s", serial, "--always-on-top", "--no-audio"]
        
        if mode == "dex":
            # Session Start: Wake up the device
            wake_cmd = f"adb -s {serial} shell 'input keyevent KEYCODE_WAKE && wm dismiss-keyguard'"
            try: subprocess.run(wake_cmd, shell=True, capture_output=True)
            except: pass

            cmd_args += [
                "--turn-screen-off", 
                "--stay-awake", 
                "--disable-screensaver",
                "--power-off-on-close",
                "--max-fps", "60",
                "--video-bit-rate", "16M"
            ]
            self.log("Launching Ultimate DeX Mode...")
        elif mode == "gaming":
            cmd_args += ["--max-fps", "60", "--video-bit-rate", "16M"]
            self.log("Launching Gaming Mode...")
        else:
            self.log("Launching Standard Mirroring...")

        try:
            if sys.platform == "win32":
                subprocess.Popen(cmd_args, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(cmd_args, start_new_session=True)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to launch scrcpy: {str(e)}")

    def browse_sideload_file(self):
        last_dir = self.settings.get_last_dir("last_sideload_dir")
        f, _ = QFileDialog.getOpenFileName(self, "Select Sideload File", last_dir, "Sideload Files (*.zip *.apk)")
        if f:
            self.settings.set_last_dir(os.path.dirname(f), "last_sideload_dir")
            self.sideload_path_edit.setText(f)

    def run_sideload(self):
        path = self.sideload_path_edit.text().strip()
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "File Error", "Please select a valid .zip or .apk file to sideload.")
            return
        serial = self.device_combo.currentData()
        mode_text = self.device_combo.currentText()
        if "ADB" not in mode_text and "SIDELOAD" not in mode_text:
            QMessageBox.warning(self, "Mode Error", "Sideload requires the device to be in ADB/Sideload mode.")
            return
        self.run_command(f'adb sideload "{path}"')

    def load_presets(self):
        self.preset_combo.clear()
        self.preset_combo.addItem("Select Preset...")
        presets_dir = get_resource_path("presets")
        if os.path.exists(presets_dir):
            for f in os.listdir(presets_dir):
                if f.endswith(".prop"):
                    name = f.replace(".prop", "").replace("_", " ")
                    self.preset_combo.addItem(name, os.path.join(presets_dir, f))

    def apply_identity_preset(self):
        preset_name = self.preset_combo.currentText()
        preset_path = self.preset_combo.currentData()
        if not preset_path or "Select" in preset_name: return
        serial = self.device_combo.currentData()
        if not serial or "ADB" not in self.device_combo.currentText():
            QMessageBox.warning(self, "Error", "Root access via ADB is required.")
            return
        reply = QMessageBox.critical(self, "Safety Verification", f"This will spoof your device as {preset_name}. Proceed?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.No: return
        self.tweak_console.append(f"<b>Applying preset: {preset_name}</b>")
        try:
            commands = []
            with open(preset_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"): continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        commands.append(f"resetprop -n {key.strip()} \"{val.strip()}\"")
            if not commands:
                self.tweak_console.append("Error: Preset file is empty or invalid.")
                return
            full_script = " ; ".join(commands)
            def on_preset_done(code):
                if code == 0:
                    self.tweak_console.append(f"<b>Preset '{preset_name}' commands sent successfully.</b>")
                    self.log("Identity spoofed. Waiting for system sync...")
                    QTimer.singleShot(2000, self.on_device_selected)
                else:
                    self.tweak_console.append(f"<b>Failed with code {code}</b>")
                    if code == 13: QMessageBox.critical(self, "Root Denied", "Grant 'Shell' root in Magisk.")
            self.run_command(f"adb shell su -c '{full_script}'", callback=on_preset_done)
        except Exception as e: self.tweak_console.append(f"Error reading preset: {str(e)}")

    def install_magisk_fix(self):
        preset_name = self.preset_combo.currentText()
        preset_path = self.preset_combo.currentData()
        if not preset_path or "Select" in preset_name: return
        serial = self.device_combo.currentData()
        if not serial: return
        msg = (f"This will install a boot script to spoof your device as {preset_name}.\\n\\n"
               "SAFETY FEATURES INCLUDED:\\n"
               "- 30 second delay before applying\\n"
               "- Automatic abort if in Safe Mode\\n\\nProceed?")
        reply = QMessageBox.warning(self, "Install Permanent Fix", msg, QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.No: return
        self.tweak_console.append("<b>Generating Safe Magisk boot script...</b>")
        script_lines = [
            "#!/system/bin/sh", "# Naz Android Toolkit Fix", "exec > /data/local/tmp/nat_fix.log 2>&1",
            "sleep 30", "if [ \"$(getprop persist.sys.safemode)\" = \"1\" ]; then exit 0; fi",
            "until [ \"$(getprop sys.boot_completed)\" = \"1\" ]; do sleep 2; done"
        ]
        try:
            with open(preset_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"): continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        script_lines.append(f"resetprop -n {key.strip()} \"{val.strip()}\"")
            local_script = os.path.join(os.getcwd(), "nat_fix.sh")
            with open(local_script, "w") as f: f.write("\n".join(script_lines))
            target_path = "/data/adb/service.d/nat_fix.sh"
            push_cmd = f"adb -s {serial} push \"{local_script}\" /data/local/tmp/nat_fix.sh"
            full_su_cmd = f"mkdir -p /data/adb/service.d && cat /data/local/tmp/nat_fix.sh > {target_path} && chmod 755 {target_path} && rm /data/local/tmp/nat_fix.sh"
            move_cmd = f"adb -s {serial} shell su -c \"{full_su_cmd}\""
            def on_install_done(code):
                if code == 0:
                    self.tweak_console.append("<b>Permanent fix installed! REBOOT device.</b>")
                    QMessageBox.information(self, "Success", "Script installed to /data/adb/service.d/nat_fix.sh\\n\\nPlease REBOOT.")
                else: self.tweak_console.append(f"Failed (Exit Code {code}). Check root.")
            self.run_batch_command(push_cmd, lambda code: self.run_command(move_cmd, callback=on_install_done))
        except Exception as e: self.tweak_console.append(f"Error: {str(e)}")

    def read_all_props(self):
        serial = self.device_combo.currentData()
        if not serial: return
        self.tweak_console.append("Fetching system properties...")
        self.prop_table.setRowCount(0)
        self.set_ui_enabled(False)
        self.thread = CommandThread(f"adb -s {serial} shell getprop")
        self.thread.output_signal.connect(self.populate_props)
        self.thread.finished_signal.connect(lambda: self.set_ui_enabled(True))
        self.thread.start()

    def populate_props(self, line):
        if ":" in line:
            try:
                parts = line.split(":", 1)
                key = parts[0].strip("[] ")
                val = parts[1].strip("[] ")
                search_term = self.prop_search.text().lower()
                if search_term and search_term not in key.lower(): return
                row = self.prop_table.rowCount()
                self.prop_table.blockSignals(True)
                self.prop_table.insertRow(row)
                key_item = QTableWidgetItem(key)
                key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
                self.prop_table.setItem(row, 0, key_item)
                self.prop_table.setItem(row, 1, QTableWidgetItem(val))
                self.prop_table.blockSignals(False)
            except: pass

    def track_prop_change(self, item):
        if item.column() == 1:
            row = item.row()
            key = self.prop_table.item(row, 0).text()
            new_val = item.text()
            self.modified_props[key] = new_val
            for col in range(2):
                self.prop_table.item(row, col).setBackground(QColor("#455A64"))
                self.prop_table.item(row, col).setForeground(QColor("#FFEB3B"))
            self.tweak_console.append(f"Queued change: {key} -> {new_val}")

    def clear_pending_props(self):
        self.modified_props = {}
        self.read_all_props()
        self.tweak_console.append("Pending changes cleared.")

    def apply_all_props(self):
        if not self.modified_props:
            QMessageBox.information(self, "No Changes", "No properties have been modified.")
            return
        reply = QMessageBox.warning(self, "Confirm Batch Write", f"Write {len(self.modified_props)} properties? Requires root.", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.tweak_console.append(f"<b>Starting batch write...</b>")
            commands = [f"resetprop -n {key} \"{val}\"" for key, val in self.modified_props.items()]
            full_script = " ; ".join(commands)
            self.run_command(f"adb shell su -c '{full_script}'", callback=lambda code: self.tweak_console.append(f"Batch write status: {code}"))
            self.modified_props = {}
            QTimer.singleShot(2000, self.read_all_props)

    def export_props_to_file(self):
        if self.prop_table.rowCount() == 0:
            QMessageBox.warning(self, "Export Error", "No properties to export. Click 'Read All Props' first.")
            return
        last_dir = self.settings.get_last_dir("last_export_dir")
        f, _ = QFileDialog.getSaveFileName(self, "Save Properties", last_dir, "Prop Files (*.prop);;Text Files (*.txt)")
        if f:
            self.settings.set_last_dir(os.path.dirname(f), "last_export_dir")
            try:
                with open(f, "w") as file:
                    for row in range(self.prop_table.rowCount()):
                        key = self.prop_table.item(row, 0).text()
                        val = self.prop_table.item(row, 1).text()
                        file.write(f"{key}={val}\n")
                self.tweak_console.append(f"Exported to {f}")
                QMessageBox.information(self, "Export Success", f"Saved to {os.path.basename(f)}")
            except Exception as e: QMessageBox.critical(self, "Error", str(e))
