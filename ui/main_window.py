import os
import sys
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFileDialog, QTextEdit, QComboBox, 
                             QGroupBox, QLineEdit, QProgressBar, QTableWidget,
                             QTableWidgetItem, QHeaderView, QMessageBox, QTabWidget,
                             QFormLayout)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QColor, QPixmap

from core.command_thread import CommandThread
from core.adb_fastboot import (get_devices, fetch_partitions_from_device, check_tools, 
                               get_adb_info, get_fastboot_info)
from utils.logger import save_session_log, start_boot_monitor

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Naz Android Toolkit")
        self.setMinimumSize(1000, 850)
        self.is_flashing = False
        self.session_log = []
        
        self.init_ui()
        self.check_env()
        self.refresh_devices()

    def check_env(self):
        missing = check_tools()
        if missing:
            QMessageBox.critical(self, "Environment Error", 
                                f"Missing tools: {', '.join(missing)}\nPlease install Android Platform Tools.")

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Header
        header_layout = QHBoxLayout()
        
        # Logo
        logo_label = QLabel()
        if os.path.exists("logo.png"):
            pixmap = QPixmap("logo.png").scaled(50, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(pixmap)
        header_layout.addWidget(logo_label)

        title = QLabel("Naz Android Toolkit")
        title.setFont(QFont("Arial", 22, QFont.Bold))
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(250)
        self.device_combo.currentIndexChanged.connect(self.on_device_selected)
        btn_refresh = QPushButton("Refresh Devices")
        btn_refresh.clicked.connect(self.refresh_devices)
        header_layout.addWidget(QLabel("Target:"))
        header_layout.addWidget(self.device_combo)
        header_layout.addWidget(btn_refresh)
        
        main_layout.addLayout(header_layout)

        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.setup_dashboard_tab()
        self.setup_adb_tab()
        self.setup_fastboot_tab()
        self.setup_logs_tab()

        # Bottom Status/Progress
        self.progress = QProgressBar()
        main_layout.addWidget(self.progress)
        
        self.status_label = QLabel("Ready")
        main_layout.addWidget(self.status_label)

    def setup_dashboard_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Info Group
        info_group = QGroupBox("Device Information")
        info_layout = QFormLayout()
        self.info_labels = {
            "Model": QLabel("N/A"),
            "Build/Product": QLabel("N/A"),
            "State": QLabel("N/A"),
            "Bootloader": QLabel("N/A"),
            "Root": QLabel("N/A")
        }
        for k, v in self.info_labels.items():
            v.setStyleSheet("font-weight: bold; color: #1565c0;")
            info_layout.addRow(f"{k}:", v)
        
        btn_integrity = QPushButton("Check Device Integrity")
        btn_integrity.clicked.connect(self.check_integrity)
        info_layout.addRow("", btn_integrity)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Connectivity Group
        conn_group = QGroupBox("Wireless Connectivity (ADB)")
        conn_layout = QHBoxLayout()
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("192.168.1.X:5555")
        btn_connect = QPushButton("Connect Wireless")
        btn_connect.clicked.connect(lambda: self.run_command(f"adb connect {self.ip_input.text()}"))
        conn_layout.addWidget(QLabel("IP:Port"))
        conn_layout.addWidget(self.ip_input)
        conn_layout.addWidget(btn_connect)
        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)
        
        layout.addStretch()
        self.tabs.addTab(tab, "Dashboard")

    def setup_adb_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # App Management
        app_group = QGroupBox("App Management")
        app_layout = QHBoxLayout()
        btn_install = QPushButton("Install APK")
        btn_install.clicked.connect(self.install_apk)
        self.pkg_input = QLineEdit()
        self.pkg_input.setPlaceholderText("com.package.name")
        btn_uninstall = QPushButton("Uninstall")
        btn_uninstall.clicked.connect(lambda: self.run_command(f"adb uninstall {self.pkg_input.text()}", safety=True))
        app_layout.addWidget(btn_install)
        app_layout.addWidget(QLabel("Pkg:"))
        app_layout.addWidget(self.pkg_input)
        app_layout.addWidget(btn_uninstall)
        app_group.setLayout(app_layout)
        layout.addWidget(app_group)

        # Custom Command
        cmd_group = QGroupBox("Custom ADB Command")
        cmd_layout = QHBoxLayout()
        self.adb_cmd_input = QLineEdit()
        self.adb_cmd_input.setPlaceholderText("shell pm list packages")
        btn_exec = QPushButton("Execute")
        btn_exec.clicked.connect(lambda: self.run_command(f"adb {self.adb_cmd_input.text()}"))
        cmd_layout.addWidget(self.adb_cmd_input)
        cmd_layout.addWidget(btn_exec)
        cmd_group.setLayout(cmd_layout)
        layout.addWidget(cmd_group)

        layout.addStretch()
        self.tabs.addTab(tab, "ADB Tools")

    def setup_fastboot_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Reboot Options
        reboot_group = QGroupBox("Reboot Modes")
        reboot_layout = QHBoxLayout()
        for mode in ["Bootloader", "Fastboot", "Recovery", "System"]:
            btn = QPushButton(mode)
            btn.clicked.connect(lambda checked, m=mode: self.reboot_device(m))
            reboot_layout.addWidget(btn)
        reboot_group.setLayout(reboot_layout)
        layout.addWidget(reboot_group)

        # Flash Queue
        queue_group = QGroupBox("Flash Queue (Batch)")
        queue_layout = QVBoxLayout()
        
        input_layout = QHBoxLayout()
        self.partition_combo = QComboBox()
        self.partition_combo.setEditable(True)
        btn_fetch = QPushButton("Fetch Partitions")
        btn_fetch.clicked.connect(self.fetch_partitions)
        btn_browse = QPushButton("Add Images...")
        btn_browse.clicked.connect(self.browse_file)
        
        input_layout.addWidget(QLabel("Partition:"))
        input_layout.addWidget(self.partition_combo, 1)
        input_layout.addWidget(btn_fetch)
        input_layout.addWidget(btn_browse)
        queue_layout.addLayout(input_layout)

        self.queue_table = QTableWidget(0, 3)
        self.queue_table.setHorizontalHeaderLabels(["Partition", "File Path", "Status"])
        self.queue_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        queue_layout.addWidget(self.queue_table)

        btn_flash = QPushButton("START BATCH FLASH")
        btn_flash.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold; height: 40px;")
        btn_flash.clicked.connect(self.process_queue)
        
        btn_clear_queue = QPushButton("Clear Queue")
        btn_clear_queue.clicked.connect(lambda: self.queue_table.setRowCount(0))
        
        queue_layout.addWidget(btn_flash)
        queue_layout.addWidget(btn_clear_queue)
        queue_group.setLayout(queue_layout)
        layout.addWidget(queue_group)

        # Fastboot Console
        self.fb_console = QTextEdit()
        self.fb_console.setReadOnly(True)
        self.fb_console.setStyleSheet("background-color: #1e1e1e; color: #00e676; font-family: 'Courier New'; font-size: 11px;")
        layout.addWidget(self.fb_console)

        # Format Options
        fmt_group = QGroupBox("Generic Format/Erase")
        fmt_layout = QHBoxLayout()
        
        self.fmt_partition_combo = QComboBox()
        self.fmt_partition_combo.setEditable(True)
        self.fmt_partition_combo.setMinimumWidth(150)
        
        self.fs_combo = QComboBox()
        self.fs_combo.addItems(["f2fs", "ext4", "fat"])
        
        btn_generic_format = QPushButton("Format Partition")
        btn_generic_format.clicked.connect(self.format_partition)
        
        btn_erase_generic = QPushButton("Erase Partition")
        btn_erase_generic.clicked.connect(lambda: self.run_command(f"fastboot erase {self.fmt_partition_combo.currentText()}", safety=True))
        
        fmt_layout.addWidget(QLabel("Part:"))
        fmt_layout.addWidget(self.fmt_partition_combo, 1)
        fmt_layout.addWidget(QLabel("FS:"))
        fmt_layout.addWidget(self.fs_combo)
        fmt_layout.addWidget(btn_generic_format)
        fmt_layout.addWidget(btn_erase_generic)
        
        fmt_group.setLayout(fmt_layout)
        layout.addWidget(fmt_group)

        self.tabs.addTab(tab, "Fastboot Tools")

    def setup_logs_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
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

    def log(self, text):
        self.console.append(text)
        if hasattr(self, 'fb_console'):
            self.fb_console.append(text)
        self.session_log.append(text)

    def refresh_devices(self):
        self.device_combo.clear()
        devices = get_devices()
        for dev in devices:
            self.device_combo.addItem(f"{dev['type']}: {dev['serial']}", dev['serial'])
        if not devices:
            self.status_label.setText("No devices connected.")
        else:
            self.status_label.setText(f"Connected: {len(devices)} device(s)")

    def on_device_selected(self):
        serial = self.device_combo.currentData()
        if not serial: return
        
        text = self.device_combo.currentText()
        is_fastboot = "FASTBOOT" in text
        
        # Reset labels
        for lbl in self.info_labels.values(): lbl.setText("Fetching...")

        if is_fastboot:
            info = get_fastboot_info(serial)
            self.info_labels["Model"].setText("N/A")
            self.info_labels["Build/Product"].setText(info["Product"])
            self.info_labels["State"].setText("FASTBOOT")
            self.info_labels["Bootloader"].setText("Unlocked" if info["Unlocked"] == "yes" else "Locked" if info["Unlocked"] == "no" else "Unknown")
            self.info_labels["Root"].setText("N/A")
            self.fetch_partitions()
        else:
            info = get_adb_info(serial)
            self.info_labels["Model"].setText(info["Model"])
            self.info_labels["Build/Product"].setText(info["Build"])
            self.info_labels["State"].setText("ADB")
            self.info_labels["Bootloader"].setText("N/A (check in Fastboot)")
            self.info_labels["Root"].setText(info["Root"])

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
            parts = fetch_partitions_from_device(serial)
            if parts:
                self.partition_combo.clear()
                self.partition_combo.addItems(parts)
                self.fmt_partition_combo.clear()
                self.fmt_partition_combo.addItems(parts)

    def browse_file(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Images", "", "Images (*.img *.bin)")
        if files:
            selected_part = self.partition_combo.currentText().strip()
            for f in files:
                partition = selected_part if selected_part else os.path.basename(f).lower().replace(".img", "").replace(".bin", "")
                row = self.queue_table.rowCount()
                self.queue_table.insertRow(row)
                
                part_item = QTableWidgetItem(partition)
                self.queue_table.setItem(row, 0, part_item)
                
                file_item = QTableWidgetItem(f)
                file_item.setFlags(file_item.flags() & ~Qt.ItemIsEditable)
                self.queue_table.setItem(row, 1, file_item)
                
                status_item = QTableWidgetItem("Pending")
                status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
                self.queue_table.setItem(row, 2, status_item)

    def install_apk(self):
        apk, _ = QFileDialog.getOpenFileName(self, "Select APK", "", "APK Files (*.apk)")
        if apk:
            self.run_command(f'adb install "{apk}"')

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

        self.log(f"> {cmd}")
        self.thread = CommandThread(cmd)
        self.thread.output_signal.connect(self.log)
        if callback: self.thread.finished_signal.connect(callback)
        self.thread.start()

    def process_queue(self):
        if self.queue_table.rowCount() == 0: return
        
        cmds = []
        serial = self.device_combo.currentData()
        for i in range(self.queue_table.rowCount()):
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
            self.run_command(f'fastboot flash {p} "{f}"', self.on_finished)
        else:
            self.is_flashing = False
            self.log("Batch complete.")

    def on_finished(self, code):
        status = "Success" if code == 0 else "Failed"
        self.queue_table.setItem(self.current_row, 2, QTableWidgetItem(status))
        self.current_row += 1
        self.flash_next()

    def check_integrity(self):
        serial = self.device_combo.currentData()
        if not serial: return
        is_adb = "ADB" in self.device_combo.currentText()
        
        if not is_adb:
            QMessageBox.information(self, "Integrity Check", "Integrity check is only available in ADB mode.")
            return

        self.log("Starting Device Integrity Check...")
        # Check for Magisk
        self.run_command("adb shell 'ls /data/adb/magisk'", callback=self.on_integrity_part)
        # Check for DM-Verity (generic check)
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
