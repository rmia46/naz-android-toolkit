import os
import sys
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFileDialog, QTextEdit, QComboBox, 
                             QGroupBox, QLineEdit, QProgressBar, QTableWidget,
                             QTableWidgetItem, QHeaderView, QMessageBox, QTabWidget,
                             QFormLayout, QFrame, QGridLayout, QSplitter)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QColor, QPixmap, QTextCursor

from core.command_thread import CommandThread
from core.adb_fastboot import (get_devices, fetch_partitions_from_device, check_tools, 
                               get_adb_info, get_fastboot_info, get_adb_metrics)
from utils.logger import save_session_log, start_boot_monitor
from utils.settings import SettingsManager

# Global Professional Stylesheet
STYLESHEET = """
QMainWindow { background-color: #121212; color: #E0E0E0; }
QTabWidget::pane { border: 1px solid #333333; top: -1px; background: #1E1E1E; border-radius: 4px; }
QTabBar::tab { background: #252525; padding: 10px 20px; border: 1px solid #333333; margin-right: 2px; border-top-left-radius: 4px; border-top-right-radius: 4px; color: #AAAAAA; }
QTabBar::tab:selected { background: #1E1E1E; border-bottom-color: #1E1E1E; color: #00E676; font-weight: bold; }
QGroupBox { font-weight: bold; border: 2px solid #333333; border-radius: 6px; margin-top: 15px; padding-top: 15px; color: #00E676; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 5px; left: 10px; bottom: 5px; }
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
"""

APP_VERSION = "v1.0.0"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Naz Android Toolkit {APP_VERSION}")
        self.setMinimumSize(1200, 900)
        self.is_flashing = False
        self.session_log = []
        self.settings = SettingsManager()
        self.info_labels = {}
        
        self.setStyleSheet(STYLESHEET)
        self.init_ui()
        self.check_env()
        self.refresh_devices()
        
        # Live Metrics Timer
        self.metrics_timer = QTimer()
        self.metrics_timer.timeout.connect(self.update_live_metrics)
        self.metrics_timer.start(5000)

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
        if os.path.exists("logo.png"):
            pixmap = QPixmap("logo.png").scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(pixmap)
        header_layout.addWidget(logo_label)

        title_layout = QVBoxLayout()
        title = QLabel("Naz Android Toolkit")
        title.setFont(QFont("Arial", 26, QFont.Bold))
        title.setStyleSheet("color: white; margin-bottom: -5px;")
        sub_title = QLabel(f"Another Android Fastboot Recovery Suite | {APP_VERSION}")
        sub_title.setStyleSheet("color: #AAAAAA; font-size: 12px; margin-top: -5px;")
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
        # Clean text for session log (no HTML)
        clean_text = text.replace("<b>", "").replace("</b>", "").replace("<font color=", "").replace("</font>", "").replace(">", "")
        self.session_log.append(clean_text)

        # Apply coloring for UI consoles
        color = "#E0E0E0"
        if text.startswith(">"): color = "#FFEB3B"  # Yellow for commands
        elif "OKAY" in text or "Success" in text or "finished" in text: color = "#00E676"  # Green
        elif "FAILED" in text or "error" in text or "Error" in text: color = "#F44336"  # Red
        
        html_text = f'<font color="{color}">{text}</font>'
        
        self.console.append(html_text)
        if hasattr(self, 'fb_console'): self.fb_console.append(html_text)
        if hasattr(self, 'adb_console'): self.adb_console.append(html_text)
        
        # Auto-scroll
        self.console.moveCursor(QTextCursor.End)
        if hasattr(self, 'fb_console'): self.fb_console.moveCursor(QTextCursor.End)
        if hasattr(self, 'adb_console'): self.adb_console.moveCursor(QTextCursor.End)

    def setup_dashboard_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(20)
        
        # Grid for Info Cards
        grid = QGridLayout()
        grid.setSpacing(15)
        
        self.cards = {}
        # Core Identity
        self.cards["Model_card"], self.info_labels["Model"] = self.create_info_card("Device Model")
        self.cards["Product_card"], self.info_labels["Build/Product"] = self.create_info_card("Build/Product")
        self.cards["State_card"], self.info_labels["State"] = self.create_info_card("Connection Mode", "#1565c0")
        self.cards["Root_card"], self.info_labels["Root"] = self.create_info_card("Root Status", "#FFC107")
        
        # Status/Security
        self.cards["Bootloader_card"], self.info_labels["Bootloader"] = self.create_info_card("Bootloader State", "#F44336")
        self.cards["Integrity_card"], self.info_labels["Integrity"] = self.create_info_card("Device Integrity", "#9C27B0")
        
        # Live Metrics (ADB Only)
        self.cards["Battery_card"], self.lbl_battery = self.create_info_card("Battery Level", "#4CAF50")
        self.cards["Temp_card"], self.lbl_temp = self.create_info_card("CPU Temp", "#FF9800")
        self.cards["Storage_card"], self.lbl_storage = self.create_info_card("Storage (Internal)", "#2196F3")

        card_keys = [
            "Model_card", "Product_card", "State_card",
            "Root_card", "Bootloader_card", "Integrity_card",
            "Battery_card", "Temp_card", "Storage_card"
        ]
        for i, key in enumerate(card_keys):
            grid.addWidget(self.cards[key], i // 3, i % 3)

        layout.addLayout(grid)

        # Bottom Actions
        actions_layout = QHBoxLayout()
        btn_integrity = QPushButton("Run Full Integrity Check")
        btn_integrity.setFixedHeight(40)
        btn_integrity.clicked.connect(self.check_integrity)
        
        btn_refresh = QPushButton("Refresh All Info")
        btn_refresh.setFixedHeight(40)
        btn_refresh.clicked.connect(self.on_device_selected)
        
        actions_layout.addWidget(btn_integrity)
        actions_layout.addWidget(btn_refresh)
        layout.addLayout(actions_layout)

        # Wireless Connection remains at bottom
        conn_group = QGroupBox("Wireless ADB Connector")
        conn_layout = QHBoxLayout()
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("192.168.1.X:5555")
        btn_connect = QPushButton("Connect Wireless")
        btn_connect.clicked.connect(lambda: self.run_command(f"adb connect {self.ip_input.text()}"))
        conn_layout.addWidget(self.ip_input)
        conn_layout.addWidget(btn_connect)
        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)
        
        layout.addStretch()
        self.tabs.addTab(tab, "Dashboard")

    def setup_adb_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        splitter = QSplitter(Qt.Horizontal)
        
        # Left Panel: Controls
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
        self.adb_cmd_input.setPlaceholderText("shell getprop ro.serialno")
        btn_exec = QPushButton("Run Command")
        btn_exec.clicked.connect(lambda: self.run_command(f"adb {self.adb_cmd_input.text()}"))
        cmd_layout.addWidget(self.adb_cmd_input)
        cmd_layout.addWidget(btn_exec)
        cmd_group.setLayout(cmd_layout)
        left_layout.addWidget(cmd_group)
        
        left_layout.addStretch()
        
        # Right Panel: ADB Console
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
        
        # Left Panel: Flashing & Formatting
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
        
        # Right Panel: Flash Console
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
        
        # Reset labels
        for lbl in self.info_labels.values(): lbl.setText("Fetching...")
        self.lbl_battery.setText("N/A")
        self.lbl_temp.setText("N/A")
        self.lbl_storage.setText("N/A")

        # Highlight Connection Mode Card
        mode_bg = "#1A237E" if not is_fastboot else "#311B92" # Deep Blue for ADB, Deep Purple for Fastboot
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
        else:
            info = get_adb_info(serial)
            self.info_labels["Model"].setText(info["Model"])
            self.info_labels["Build/Product"].setText(info["Build"])
            self.info_labels["State"].setText("ADB")
            self.info_labels["Bootloader"].setText("N/A (check in Fastboot)")
            self.cards["Bootloader_card"].setStyleSheet("background-color: #252525; border: 1px solid #333333; border-radius: 8px; border-left: 4px solid #F44336;")
            
            self.info_labels["Root"].setText(info["Root"])
            color = "#00E676" if info["Root"] == "Yes" else "#E53935"
            self.cards["Root_card"].setStyleSheet(f"background-color: #252525; border: 1px solid #333333; border-radius: 8px; border-left: 4px solid {color};")
            
            self.update_live_metrics()

    def update_live_metrics(self):
        serial = self.device_combo.currentData()
        if not serial or "ADB" not in self.device_combo.currentText():
            return
            
        metrics = get_adb_metrics(serial)
        self.lbl_battery.setText(metrics["Battery"])
        self.lbl_temp.setText(metrics["Temp"])
        self.lbl_storage.setText(metrics["Storage"])

    def reboot_device(self, mode):
        serial = self.device_combo.currentData()
        if not serial: return
        is_adb = "ADB" in self.device_combo.currentText()
        cmd = f"adb reboot {mode.lower()}" if is_adb else f"fastboot reboot {mode.lower()}"
        if mode == "System":
             cmd = "adb reboot" if is_adb else "fastboot reboot"
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
            
            reply = QMessageBox.warning(self, "Safety Verification", warning_msg,
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No: return

        self.set_ui_enabled(False)
        self.log(f"> {cmd}")
        self.thread = CommandThread(cmd)
        self.thread.output_signal.connect(self.log)
        
        def on_finished_internal(code):
            self.set_ui_enabled(True)
            if callback: callback(code)
            
        self.thread.finished_signal.connect(on_finished_internal)
        self.thread.start()

    def update_queue_validation(self):
        has_items = self.queue_table.rowCount() > 0
        if hasattr(self, 'btn_flash'):
            self.btn_flash.setEnabled(has_items)

    def process_queue(self):
        count = self.queue_table.rowCount()
        if count == 0: return
        
        cmds = []
        serial = self.device_combo.currentData()
        for i in range(count):
            p = self.queue_table.item(i, 0).text().strip()
            f = self.queue_table.item(i, 1).text().strip()
            base_cmd = f"fastboot flash {p} \"{f}\""
            if serial:
                base_cmd = base_cmd.replace("fastboot", f"fastboot -s {serial}", 1)
            cmds.append(base_cmd)
        
        msg = "This operation will run the following commands:\n\n" + "\n".join(cmds) + \
              "\n\nCRITICAL WARNING: Improper flashing can permanently damage your device.\nPROCEED WITH CAUTION!"
        
        reply = QMessageBox.critical(self, "Batch Safety Verification", msg, 
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes and not self.is_flashing:
            self.is_flashing = True
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
            self.progress.setValue(self.progress.maximum())
            self.set_ui_enabled(True)
            self.log("<b>Batch operation complete.</b>")

    def run_batch_command(self, cmd, callback):
        serial = self.device_combo.currentData()
        if serial and "fastboot" in cmd: 
            cmd = cmd.replace("fastboot", f"fastboot -s {serial}", 1)
        
        self.log(f"> {cmd}")
        self.thread = CommandThread(cmd)
        self.thread.output_signal.connect(self.log)
        self.thread.finished_signal.connect(callback)
        self.thread.start()

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

    def check_integrity(self):
        serial = self.device_combo.currentData()
        if not serial: return
        is_adb = "ADB" in self.device_combo.currentText()
        
        if not is_adb:
            QMessageBox.information(self, "Integrity Check", "Integrity check is only available in ADB mode.")
            return

        self.log("Starting Device Integrity Check...")
        self.run_command("adb shell 'ls /data/adb/magisk'", callback=self.on_integrity_part)
        self.run_command("adb shell 'getprop ro.boot.vbmeta.device_state'", callback=self.on_integrity_part)

    def on_integrity_part(self, code):
        self.log("Integrity part complete.")

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
