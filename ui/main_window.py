import os
import sys
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFileDialog, QTextEdit, QComboBox, 
                             QGroupBox, QLineEdit, QProgressBar, QTableWidget,
                             QTableWidgetItem, QHeaderView, QMessageBox, QTabWidget,
                             QFormLayout, QFrame, QGridLayout, QSplitter, QInputDialog,
                             QDialog, QDialogButtonBox, QCheckBox)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QColor, QPixmap, QTextCursor

from core.command_thread import CommandThread
from core.adb_fastboot import (get_devices, fetch_partitions_from_device, check_tools, 
                               get_adb_info, get_fastboot_info, get_adb_metrics, is_scrcpy_available)
from utils.logger import save_session_log, start_boot_monitor
from utils.settings import SettingsManager
from utils.paths import get_resource_path

# Global Professional Stylesheet
STYLESHEET = """
QMainWindow { background-color: #121212; color: #E0E0E0; }
QTabWidget::pane { border: 1px solid #333333; top: -1px; background: #1E1E1E; border-radius: 4px; }
QTabBar::tab { background: #252525; padding: 10px 20px; border: 1px solid #333333; margin-right: 2px; border-top-left-radius: 4px; border-top-right-radius: 4px; color: #AAAAAA; }
QTabBar::tab:selected { background: #1E1E1E; border-bottom-color: #1E1E1E; color: #00E676; font-weight: bold; }
QGroupBox { font-weight: bold; border: 2px solid #333333; border-radius: 6px; margin-top: 20px; padding-top: 15px; color: #00E676; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 5px 10px; left: 10px; }
QPushButton { background-color: #333333; border: 1px solid #444444; border-radius: 4px; padding: 6px 15px; min-height: 25px; color: white; }
QPushButton:hover { background-color: #444444; border: 1px solid #00E676; }
QPushButton#flash_btn { background-color: #B71C1C; font-size: 14px; font-weight: bold; border: 1px solid #E53935; }
QPushButton#flash_btn:hover { background-color: #D32F2F; border: 1px solid white; }
QLineEdit, QComboBox { background-color: #252525; border: 1px solid #444444; border-radius: 3px; padding: 4px; color: #E0E0E0; }
QTableWidget { background-color: #1E1E1E; border: 1px solid #333333; alternate-background-color: #252525; color: #E0E0E0; gridline-color: #333333; }
QHeaderView::section { background-color: #252525; padding: 4px; border: 1px solid #333333; color: #AAAAAA; }
QProgressBar { border: 1px solid #333333; border-radius: 4px; text-align: center; background-color: #252525; height: 15px; }
QProgressBar::chunk { background-color: #00E676; border-radius: 3px; }
QTextEdit { background-color: #000000; border: 1px solid #333333; border-radius: 4px; }
QLabel { padding: 1px 0px; }
"""

APP_VERSION = "v1.3.0"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Naz Android Toolkit {APP_VERSION}")
        self.setMinimumSize(1200, 900)
        self.setAcceptDrops(True)
        self.is_flashing = False
        self.session_log = []
        self.settings = SettingsManager()
        self.info_labels = {}
        self.modified_props = {}
        self.active_threads = []
        
        self.setStyleSheet(STYLESHEET)
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

    def create_info_card(self, title, accent_color="#00E676"):
        frame = QFrame()
        frame.setStyleSheet(f"background-color: #252525; border: 1px solid #333333; border-radius: 8px; border-left: 4px solid {accent_color};")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(15, 10, 15, 10)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("color: #AAAAAA; font-size: 11px; text-transform: uppercase; font-weight: bold; border: none;")
        val_lbl = QLabel("N/A")
        val_lbl.setStyleSheet("color: white; font-size: 16px; font-weight: bold; border: none;")
        
        layout.addWidget(title_lbl)
        layout.addWidget(val_lbl)
        return frame, val_lbl

    def check_env(self):
        missing = check_tools()
        if missing:
            QMessageBox.critical(self, "Environment Error", 
                                f"Missing tools: {', '.join(missing)}\nPlease install Android Platform Tools.")

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # Header
        header_container = QGroupBox("Target Selection")
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(10, 10, 10, 10)
        
        logo_label = QLabel()
        logo_path = get_resource_path(os.path.join("assets", "logo.png"))
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path).scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(pixmap)
        header_layout.addWidget(logo_label)

        title_layout = QVBoxLayout()
        title = QLabel("Naz Android Toolkit")
        title.setFont(QFont("Arial", 26, QFont.Bold))
        title.setStyleSheet("color: white;")
        sub_title = QLabel(f"Another Android Fastboot Recovery Suite | {APP_VERSION}")
        sub_title.setStyleSheet("color: #AAAAAA; font-size: 12px;")
        title_layout.addWidget(title)
        title_layout.addWidget(sub_title)
        header_layout.addLayout(title_layout)
        
        header_layout.addStretch()
        
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(300)
        self.device_combo.setFixedHeight(35)
        self.device_combo.currentIndexChanged.connect(self.on_device_selected)
        btn_refresh = QPushButton("Refresh List")
        btn_refresh.setMinimumHeight(35)
        btn_refresh.clicked.connect(self.refresh_devices)
        header_layout.addWidget(QLabel("Current Device:"))
        header_layout.addWidget(self.device_combo)
        header_layout.addWidget(btn_refresh)
        
        header_container.setLayout(header_layout)
        main_layout.addWidget(header_container)

        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.setup_dashboard_tab()
        self.setup_adb_tab()
        self.setup_fastboot_tab()
        self.setup_tweaks_tab()
        self.setup_logs_tab()

        # Bottom UI
        bottom_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #00E676; font-weight: bold;")
        bottom_layout.addWidget(self.status_label)
        bottom_layout.addStretch()
        self.progress = QProgressBar()
        self.progress.setFixedWidth(400)
        bottom_layout.addWidget(self.progress)
        
        main_layout.addLayout(bottom_layout)

    def log(self, text):
        clean_text = text.replace("<b>", "").replace("</b>", "").replace("<font color=", "").replace("</font>", "").replace(">", "")
        self.session_log.append(clean_text)

        color = "#E0E0E0"
        if text.startswith(">"): color = "#FFEB3B"
        elif "OKAY" in text or "Success" in text or "finished" in text: color = "#00E676"
        elif "FAILED" in text or "error" in text or "Error" in text: color = "#F44336"
        
        html_text = f'<font color="{color}">{text}</font>'
        
        self.console.append(html_text)
        if hasattr(self, 'fb_console'): self.fb_console.append(html_text)
        if hasattr(self, 'adb_console'): self.adb_console.append(html_text)
        
        self.console.moveCursor(QTextCursor.End)
        if hasattr(self, 'fb_console'): self.fb_console.moveCursor(QTextCursor.End)
        if hasattr(self, 'adb_console'): self.adb_console.moveCursor(QTextCursor.End)

    def setup_dashboard_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(20)
        
        grid = QGridLayout()
        grid.setSpacing(15)
        
        self.cards = {}
        self.cards["Model_card"], self.info_labels["Model"] = self.create_info_card("Device Model")
        self.cards["Product_card"], self.info_labels["Build/Product"] = self.create_info_card("Build/Product")
        self.cards["State_card"], self.info_labels["State"] = self.create_info_card("Connection Mode", "#1565c0")
        self.cards["Root_card"], self.info_labels["Root"] = self.create_info_card("Root Status", "#FFC107")
        self.cards["Bootloader_card"], self.info_labels["Bootloader"] = self.create_info_card("Bootloader State", "#F44336")
        self.cards["Battery_card"], self.lbl_battery = self.create_info_card("Battery Level", "#4CAF50")
        self.cards["Temp_card"], self.lbl_temp = self.create_info_card("CPU Temp", "#FF9800")
        self.cards["Storage_card"], self.lbl_storage = self.create_info_card("Storage (Internal)", "#2196F3")

        card_keys = [
            "Model_card", "Product_card", "State_card",
            "Root_card", "Bootloader_card", "Battery_card", 
            "Temp_card", "Storage_card"
        ]
        for i, key in enumerate(card_keys):
            grid.addWidget(self.cards[key], i // 3, i % 3)

        layout.addLayout(grid)

        actions_layout = QHBoxLayout()
        btn_refresh = QPushButton("Refresh All Info")
        btn_refresh.setFixedHeight(40)
        btn_refresh.clicked.connect(self.on_device_selected)
        actions_layout.addWidget(btn_refresh)
        layout.addLayout(actions_layout)

        # Mirroring & Desktop Group
        mirror_group = QGroupBox("Desktop & Screen Mirroring")
        mirror_layout = QHBoxLayout()
        btn_mirror = QPushButton("Standard Mirror")
        btn_mirror.clicked.connect(lambda: self.launch_scrcpy("standard"))
        
        btn_dex = QPushButton("DeX Mode (Screen Off)")
        btn_dex.setStyleSheet("background-color: #0D47A1; font-weight: bold;")
        btn_dex.clicked.connect(lambda: self.launch_scrcpy("dex"))
        
        btn_game = QPushButton("Gaming Mode (60 FPS)")
        btn_game.clicked.connect(lambda: self.launch_scrcpy("gaming"))

        btn_wake = QPushButton("Wake & Dismiss Lock")
        btn_wake.clicked.connect(lambda: self.run_command("adb shell input keyevent KEYCODE_WAKE && adb shell wm dismiss-keyguard"))
        
        self.chk_audio = QCheckBox("Forward Audio (Android 11+)")
        self.chk_audio.setStyleSheet("color: #AAAAAA; font-size: 11px;")
        
        mirror_layout.addWidget(btn_mirror)
        mirror_layout.addWidget(btn_dex)
        mirror_layout.addWidget(btn_game)
        mirror_layout.addWidget(btn_wake)
        mirror_layout.addWidget(self.chk_audio)
        mirror_group.setLayout(mirror_layout)
        layout.addWidget(mirror_group)

        conn_group = QGroupBox("Wireless ADB Connector (Android 11+ Pairing Support)")
        conn_layout = QHBoxLayout()
        btn_pair_connect = QPushButton("PAIR & CONNECT NEW DEVICE")
        btn_pair_connect.setStyleSheet("background-color: #2E7D32; font-weight: bold; height: 35px;")
        btn_pair_connect.clicked.connect(self.wireless_pairing_workflow)
        
        btn_quick_connect = QPushButton("Quick Connect (Last IP)")
        btn_quick_connect.clicked.connect(self.wireless_quick_connect)
        
        conn_layout.addWidget(btn_pair_connect, 2)
        conn_layout.addWidget(btn_quick_connect, 1)
        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)

        terminal_group = QGroupBox("Manual Command Terminal")
        terminal_layout = QHBoxLayout()
        self.terminal_tool_combo = QComboBox()
        self.terminal_tool_combo.addItems(["adb", "fastboot"])
        self.terminal_tool_combo.setFixedWidth(100)
        self.terminal_input = QLineEdit()
        self.terminal_input.setPlaceholderText("Enter command (e.g. shell uptime or devices)")
        self.terminal_input.returnPressed.connect(self.run_manual_command)
        btn_terminal_exec = QPushButton("Execute")
        btn_terminal_exec.clicked.connect(self.run_manual_command)
        terminal_layout.addWidget(self.terminal_tool_combo)
        terminal_layout.addWidget(self.terminal_input, 1)
        terminal_layout.addWidget(btn_terminal_exec)
        terminal_group.setLayout(terminal_layout)
        layout.addWidget(terminal_group)
        
        layout.addStretch()
        self.tabs.addTab(tab, "Dashboard")

    def setup_adb_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        splitter = QSplitter(Qt.Horizontal)
        
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        app_group = QGroupBox("App Management")
        app_layout = QVBoxLayout()
        btn_install = QPushButton("Install APK Package")
        btn_install.setFixedHeight(35)
        btn_install.clicked.connect(self.install_apk)
        uninstall_layout = QHBoxLayout()
        self.pkg_input = QLineEdit()
        self.pkg_input.setPlaceholderText("com.package.name")
        btn_uninstall = QPushButton("Uninstall")
        btn_uninstall.clicked.connect(lambda: self.run_command(f"adb uninstall {self.pkg_input.text()}", safety=True))
        uninstall_layout.addWidget(self.pkg_input)
        uninstall_layout.addWidget(btn_uninstall)
        app_layout.addWidget(btn_install)
        app_layout.addLayout(uninstall_layout)
        app_group.setLayout(app_layout)
        left_layout.addWidget(app_group)

        cmd_group = QGroupBox("Custom ADB Shell")
        cmd_layout = QVBoxLayout()
        self.adb_cmd_input = QLineEdit()
        self.adb_cmd_input.setPlaceholderText("shell pm list packages")
        btn_exec = QPushButton("Run Command")
        btn_exec.clicked.connect(self.run_custom_adb)
        cmd_layout.addWidget(self.adb_cmd_input)
        cmd_layout.addWidget(btn_exec)
        
        btn_shell = QPushButton("Open Interactive ADB Shell")
        btn_shell.setFixedHeight(35)
        btn_shell.setStyleSheet("background-color: #1B5E20; font-weight: bold;")
        btn_shell.clicked.connect(self.open_interactive_shell)
        cmd_layout.addWidget(btn_shell)
        cmd_group.setLayout(cmd_layout)
        left_layout.addWidget(cmd_group)

        # Sideload Group
        sideload_group = QGroupBox("ADB Sideload (Recovery)")
        sideload_layout = QVBoxLayout()
        btn_reboot_sideload = QPushButton("Reboot to Sideload Mode")
        btn_reboot_sideload.clicked.connect(lambda: self.run_command("adb reboot sideload"))
        sideload_input_layout = QHBoxLayout()
        self.sideload_path_edit = QLineEdit()
        self.sideload_path_edit.setPlaceholderText("Select .zip or .apk to sideload")
        btn_browse_sideload = QPushButton("Browse...")
        btn_browse_sideload.clicked.connect(self.browse_sideload_file)
        sideload_input_layout.addWidget(self.sideload_path_edit)
        sideload_input_layout.addWidget(btn_browse_sideload)
        btn_sideload_exec = QPushButton("START SIDELOAD")
        btn_sideload_exec.setStyleSheet("background-color: #6A1B9A; font-weight: bold; height: 35px;")
        btn_sideload_exec.clicked.connect(self.run_sideload)
        sideload_layout.addWidget(btn_reboot_sideload)
        sideload_layout.addLayout(sideload_input_layout)
        sideload_layout.addWidget(btn_sideload_exec)
        sideload_group.setLayout(sideload_layout)
        left_layout.addWidget(sideload_group)
        
        left_layout.addStretch()
        
        right_panel = QGroupBox("ADB Console Output")
        right_layout = QVBoxLayout()
        self.adb_console = QTextEdit()
        self.adb_console.setReadOnly(True)
        self.adb_console.setStyleSheet("background-color: #0A0A0A; color: #00E676; font-family: 'Courier New';")
        right_layout.addWidget(self.adb_console)
        right_panel.setLayout(right_layout)
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)
        self.tabs.addTab(tab, "ADB Tools")

    def setup_fastboot_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        splitter = QSplitter(Qt.Horizontal)
        
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        reboot_group = QGroupBox("Fastboot Reboot Control")
        reboot_layout = QGridLayout()
        modes = ["Bootloader", "Fastboot", "Recovery", "System"]
        for i, mode in enumerate(modes):
            btn = QPushButton(mode)
            btn.clicked.connect(lambda checked, m=mode: self.reboot_device(m))
            reboot_layout.addWidget(btn, i//2, i%2)
        reboot_group.setLayout(reboot_layout)
        left_layout.addWidget(reboot_group)

        queue_group = QGroupBox("Partition Flash Queue")
        queue_layout = QVBoxLayout()
        input_layout = QHBoxLayout()
        self.partition_combo = QComboBox()
        self.partition_combo.setEditable(True)
        btn_fetch = QPushButton("Fetch")
        btn_fetch.clicked.connect(self.fetch_partitions)
        btn_browse = QPushButton("Add Images")
        btn_browse.clicked.connect(lambda: self.browse_file())
        input_layout.addWidget(self.partition_combo, 1)
        input_layout.addWidget(btn_fetch)
        input_layout.addWidget(btn_browse)
        queue_layout.addLayout(input_layout)

        self.queue_table = QTableWidget(0, 3)
        self.queue_table.setHorizontalHeaderLabels(["Partition", "Image", "Status"])
        self.queue_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.queue_table.model().rowsInserted.connect(self.update_queue_validation)
        self.queue_table.model().rowsRemoved.connect(self.update_queue_validation)
        queue_layout.addWidget(self.queue_table)

        self.btn_flash = QPushButton("START BATCH FLASH")
        self.btn_flash.setObjectName("flash_btn")
        self.btn_flash.setFixedHeight(40)
        self.btn_flash.setEnabled(False)
        self.btn_flash.clicked.connect(self.process_queue)
        btn_clear = QPushButton("Clear All")
        btn_clear.clicked.connect(lambda: self.queue_table.setRowCount(0))
        queue_layout.addWidget(self.btn_flash)
        queue_layout.addWidget(btn_clear)
        queue_group.setLayout(queue_layout)
        left_layout.addWidget(queue_group, 1)

        fmt_group = QGroupBox("Generic Format/Erase")
        fmt_layout = QGridLayout()
        self.fmt_partition_combo = QComboBox()
        self.fmt_partition_combo.setEditable(True)
        self.fs_combo = QComboBox()
        self.fs_combo.addItems(["f2fs", "ext4", "fat"])
        btn_format = QPushButton("Format")
        btn_format.clicked.connect(self.format_partition)
        btn_erase = QPushButton("Erase")
        btn_erase.clicked.connect(lambda: self.run_command(f"fastboot erase {self.fmt_partition_combo.currentText()}", safety=True))
        fmt_layout.addWidget(QLabel("Partition:"), 0, 0)
        fmt_layout.addWidget(self.fmt_partition_combo, 0, 1)
        fmt_layout.addWidget(QLabel("FS:"), 1, 0)
        fmt_layout.addWidget(self.fs_combo, 1, 1)
        fmt_layout.addWidget(btn_format, 2, 0)
        fmt_layout.addWidget(btn_erase, 2, 1)
        fmt_group.setLayout(fmt_layout)
        left_layout.addWidget(fmt_group)
        
        right_panel = QGroupBox("Fastboot Transaction Log")
        right_layout = QVBoxLayout()
        self.fb_console = QTextEdit()
        self.fb_console.setReadOnly(True)
        self.fb_console.setStyleSheet("background-color: #0A0A0A; color: #00E676; font-family: 'Courier New'; font-size: 11px;")
        right_layout.addWidget(self.fb_console)
        right_panel.setLayout(right_layout)
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)
        self.tabs.addTab(tab, "Fastboot Tools")

    def setup_tweaks_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        splitter = QSplitter(Qt.Horizontal)
        
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        spoof_group = QGroupBox("Device Identity Spoofing (Play Integrity Fix)")
        spoof_layout = QVBoxLayout()
        preset_layout = QHBoxLayout()
        self.preset_combo = QComboBox()
        self.load_presets()
        btn_apply_preset = QPushButton("Apply Preset (Live)")
        btn_apply_preset.clicked.connect(self.apply_identity_preset)
        btn_gen_script = QPushButton("Install Permanent Fix (Magisk)")
        btn_gen_script.setStyleSheet("background-color: #4A148C; font-weight: bold;")
        btn_gen_script.clicked.connect(self.install_magisk_fix)
        preset_layout.addWidget(self.preset_combo, 1)
        preset_layout.addWidget(btn_apply_preset)
        preset_layout.addWidget(btn_gen_script)
        spoof_layout.addLayout(preset_layout)
        spoof_layout.addWidget(QLabel("<font color='#FFA000'>Note: Requires Magisk/Root. Changes use 'resetprop'.</font>"))
        spoof_group.setLayout(spoof_layout)
        left_layout.addWidget(spoof_group)

        prop_group = QGroupBox("Custom Build Property Editor")
        prop_layout = QVBoxLayout()
        search_layout = QHBoxLayout()
        self.prop_search = QLineEdit()
        self.prop_search.setPlaceholderText("Search for a prop (e.g. ro.build...)")
        btn_read_all = QPushButton("Read All Props")
        btn_read_all.clicked.connect(self.read_all_props)
        btn_export_props = QPushButton("Save to File")
        btn_export_props.clicked.connect(self.export_props_to_file)
        search_layout.addWidget(self.prop_search)
        search_layout.addWidget(btn_read_all)
        search_layout.addWidget(btn_export_props)
        
        self.prop_table = QTableWidget(0, 2)
        self.prop_table.setHorizontalHeaderLabels(["Property Key", "Value"])
        self.prop_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.prop_table.itemChanged.connect(self.track_prop_change)
        
        batch_btn_layout = QHBoxLayout()
        btn_apply_all = QPushButton("APPLY ALL CHANGES")
        btn_apply_all.setStyleSheet("background-color: #1B5E20; font-weight: bold; height: 35px;")
        btn_apply_all.clicked.connect(self.apply_all_props)
        btn_clear_pending = QPushButton("Clear Pending")
        btn_clear_pending.clicked.connect(self.clear_pending_props)
        batch_btn_layout.addWidget(btn_apply_all, 2)
        batch_btn_layout.addWidget(btn_clear_pending, 1)
        
        prop_layout.addLayout(search_layout)
        prop_layout.addWidget(self.prop_table)
        prop_layout.addLayout(batch_btn_layout)
        prop_group.setLayout(prop_layout)
        left_layout.addWidget(prop_group, 1)
        
        right_panel = QGroupBox("System Tweak Logs")
        right_layout = QVBoxLayout()
        self.tweak_console = QTextEdit()
        self.tweak_console.setReadOnly(True)
        self.tweak_console.setStyleSheet("background-color: #0A0A0A; color: #00E676; font-family: 'Courier New';")
        right_layout.addWidget(self.tweak_console)
        right_panel.setLayout(right_layout)
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)
        self.tabs.addTab(tab, "System Tweaks")

    def setup_logs_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background-color: black; color: #00ff00; font-family: 'Courier New'; font-size: 12px;")
        layout.addWidget(self.console)
        btn_layout = QHBoxLayout()
        btn_clear = QPushButton("Clear Console")
        btn_clear.clicked.connect(self.console.clear)
        btn_save = QPushButton("Save Session Logs")
        btn_save.clicked.connect(self.save_logs)
        btn_boot = QPushButton("Start Boot Monitor")
        btn_boot.clicked.connect(self.boot_monitor)
        btn_layout.addWidget(btn_clear)
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_boot)
        layout.addLayout(btn_layout)
        self.tabs.addTab(tab, "Console Logs")

    def refresh_devices(self):
        self.device_combo.clear()
        devices = get_devices()
        for dev in devices:
            self.device_combo.addItem(f"{dev['type']}: {dev['serial']}", dev['serial'])
        if not devices:
            self.status_label.setText("No devices connected.")
            self.status_label.setStyleSheet("color: #E53935; font-weight: bold;")
        else:
            self.status_label.setText(f"Connected: {len(devices)} device(s)")
            self.status_label.setStyleSheet("color: #00E676; font-weight: bold;")

    def on_device_selected(self):
        serial = self.device_combo.currentData()
        if not serial: return
        text = self.device_combo.currentText()
        is_fastboot = "FASTBOOT" in text
        is_sideload = "SIDELOAD" in text
        for lbl in self.info_labels.values(): lbl.setText("Fetching...")
        self.lbl_battery.setText("N/A")
        self.lbl_temp.setText("N/A")
        self.lbl_storage.setText("N/A")
        mode_bg = "#1A237E" 
        if is_fastboot: mode_bg = "#311B92"
        elif is_sideload: mode_bg = "#4A148C"
        self.cards["State_card"].setStyleSheet(f"background-color: {mode_bg}; border: 1px solid #00E676; border-radius: 8px; border-left: 4px solid #1565c0;")
        if is_fastboot:
            info = get_fastboot_info(serial)
            self.info_labels["Model"].setText("N/A")
            self.info_labels["Build/Product"].setText(info["Product"])
            self.info_labels["State"].setText("FASTBOOT")
            bl_state = info["Unlocked"]
            self.info_labels["Bootloader"].setText("Unlocked" if bl_state == "yes" else "Locked" if bl_state == "no" else "Unknown")
            color = "#00E676" if bl_state == "yes" else "#E53935" if bl_state == "no" else "#AAAAAA"
            self.cards["Bootloader_card"].setStyleSheet(f"background-color: #252525; border: 1px solid #333333; border-radius: 8px; border-left: 4px solid {color};")
            self.info_labels["Root"].setText("N/A")
            self.fetch_partitions()
        elif is_sideload:
            self.info_labels["Model"].setText("N/A")
            self.info_labels["Build/Product"].setText("N/A")
            self.info_labels["State"].setText("SIDELOAD")
            self.info_labels["Bootloader"].setText("N/A")
            self.info_labels["Root"].setText("N/A")
        else:
            info = get_adb_info(serial)
            self.info_labels["Model"].setText(info["Model"])
            self.info_labels["Build/Product"].setText(info["Build"])
            self.info_labels["State"].setText("ADB")
            self.info_labels["Bootloader"].setText("N/A (check in Fastboot)")
            self.cards["Bootloader_card"].setStyleSheet("background-color: #252525; border: 1px solid #333333; border-radius: 8px; border-left: 4px solid #F44336;")
            self.info_labels["Root"].setText(info["Root"])
            color = "#00E676" if info["Root"] == "Yes (Magisk)" or info["Root"] == "Yes (System)" else "#E53935"
            self.cards["Root_card"].setStyleSheet(f"background-color: #252525; border: 1px solid #333333; border-radius: 8px; border-left: 4px solid {color};")
            self.update_live_metrics()

    def update_live_metrics(self):
        serial = self.device_combo.currentData()
        if not serial or "ADB" not in self.device_combo.currentText(): return
        metrics = get_adb_metrics(serial)
        self.lbl_battery.setText(metrics["Battery"])
        self.lbl_temp.setText(metrics["Temp"])
        self.lbl_storage.setText(metrics["Storage"])

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
        color = "#00E676" if success else "#F44336"
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
        import shutil
        scrcpy_path = shutil.which("scrcpy")
        
        if not scrcpy_path:
            QMessageBox.critical(self, "Missing Tool", "Scrcpy executable not found in system PATH.")
            return

        serial = self.device_combo.currentData()
        if not serial or "ADB" not in self.device_combo.currentText():
            QMessageBox.warning(self, "Connection Error", "Mirroring requires an active ADB connection.")
            return

        # Build command list
        cmd_args = [scrcpy_path, "-s", serial, "--always-on-top"]
        
        if not self.chk_audio.isChecked():
            cmd_args += ["--no-audio"]
        
        if mode == "dex":
            # PRE-LAUNCH: Wake up the device and dismiss the keyguard if possible
            # This helps prevent immediate locking when screen turns off
            wake_cmd = f"adb -s {serial} shell 'input keyevent KEYCODE_WAKE && wm dismiss-keyguard'"
            import subprocess
            subprocess.run(wake_cmd, shell=True)

            cmd_args += ["--turn-screen-off", "--stay-awake", "--disable-screensaver"]
            self.log("Launching DeX Mode (Screen Off)...")
        elif mode == "gaming":
            # Removed --mouse-capture as it can be confusing for standard UI navigation
            cmd_args += ["--max-fps", "60", "--video-bit-rate", "16M"]
            self.log("Launching Gaming Mode (High Performance)...")
        else:
            self.log("Launching Standard Mirroring...")

        self.log("<font color='#FFA000'>Note: If mouse clicks don't work, enable 'USB Debugging (Security Settings)' in your phone's Developer Options.</font>")

        import subprocess
        try:
            # Launch scrcpy as a detached process
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
