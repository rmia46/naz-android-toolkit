import os
import sys
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFileDialog, QTextEdit, QComboBox, 
                             QGroupBox, QLineEdit, QProgressBar, QTableWidget,
                             QTableWidgetItem, QHeaderView, QMessageBox)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

from core.command_thread import CommandThread
from core.adb_fastboot import get_devices, fetch_partitions_from_device, check_tools

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Naz Flash Tool - Modular")
        self.setMinimumSize(900, 800)
        self.is_flashing = False
        
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
        layout = QVBoxLayout(central_widget)

        # Title
        title = QLabel("Naz Flash Tool")
        title.setFont(QFont("Arial", 24, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Device Selection
        conn_group = QGroupBox("1. Device Connectivity")
        conn_layout = QHBoxLayout()
        self.device_combo = QComboBox()
        self.device_combo.currentIndexChanged.connect(self.on_device_selected)
        btn_refresh = QPushButton("Refresh List")
        btn_refresh.clicked.connect(self.refresh_devices)
        conn_layout.addWidget(QLabel("Target Device:"))
        conn_layout.addWidget(self.device_combo, 1)
        conn_layout.addWidget(btn_refresh)
        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)

        # Quick Actions
        device_group = QGroupBox("Quick Actions")
        device_layout = QHBoxLayout()
        for action in ["Bootloader", "Fastboot", "Recovery", "System"]:
            btn = QPushButton(f"Reboot {action}")
            # Simplified reboot logic
            cmd = f"fastboot reboot {action.lower()}" if action != "System" else "fastboot reboot"
            btn.clicked.connect(lambda checked, c=cmd: self.run_command(c))
            device_layout.addWidget(btn)
        device_group.setLayout(device_layout)
        layout.addWidget(device_group)

        # Flash Queue
        queue_group = QGroupBox("2. Flash Queue (Batch Processing)")
        queue_layout = QVBoxLayout()
        input_layout = QHBoxLayout()
        self.partition_combo = QComboBox()
        self.partition_combo.setEditable(True)
        btn_fetch = QPushButton("Fetch")
        btn_fetch.clicked.connect(self.fetch_partitions)
        self.file_path_edit = QLineEdit()
        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self.browse_file)
        btn_add = QPushButton("Add")
        btn_add.clicked.connect(self.add_to_queue)
        
        input_layout.addWidget(QLabel("Part:"))
        input_layout.addWidget(self.partition_combo, 1)
        input_layout.addWidget(btn_fetch)
        input_layout.addWidget(QLabel("File:"))
        input_layout.addWidget(self.file_path_edit, 2)
        input_layout.addWidget(btn_browse)
        input_layout.addWidget(btn_add)
        queue_layout.addLayout(input_layout)

        self.queue_table = QTableWidget(0, 3)
        self.queue_table.setHorizontalHeaderLabels(["Partition", "File Path", "Status"])
        self.queue_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        queue_layout.addWidget(self.queue_table)

        btn_flash = QPushButton("START BATCH FLASH")
        btn_flash.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold; height: 40px;")
        btn_flash.clicked.connect(self.process_queue)
        queue_layout.addWidget(btn_flash)
        queue_group.setLayout(queue_layout)
        layout.addWidget(queue_group)

        self.progress = QProgressBar()
        layout.addWidget(self.progress)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background-color: black; color: #00ff00; font-family: 'Courier New';")
        layout.addWidget(self.console)

    def log(self, text):
        self.console.append(text)

    def refresh_devices(self):
        self.device_combo.clear()
        for dev in get_devices():
            self.device_combo.addItem(f"{dev['type']}: {dev['serial']}", dev['serial'])

    def on_device_selected(self):
        if "FASTBOOT" in self.device_combo.currentText():
            self.fetch_partitions()

    def fetch_partitions(self):
        serial = self.device_combo.currentData()
        if serial:
            parts = fetch_partitions_from_device(serial)
            if parts:
                self.partition_combo.clear()
                self.partition_combo.addItems(parts)

    def browse_file(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Images", "", "Images (*.img *.bin)")
        if files:
            for f in files:
                self.add_file_to_queue(f)

    def add_file_to_queue(self, file_path):
        partition = os.path.basename(file_path).lower().replace(".img", "").replace(".bin", "")
        row = self.queue_table.rowCount()
        self.queue_table.insertRow(row)
        self.queue_table.setItem(row, 0, QTableWidgetItem(partition))
        self.queue_table.setItem(row, 1, QTableWidgetItem(file_path))
        self.queue_table.setItem(row, 2, QTableWidgetItem("Pending"))

    def add_to_queue(self):
        p = self.partition_combo.currentText()
        f = self.file_path_edit.text()
        if p and f:
            row = self.queue_table.rowCount()
            self.queue_table.insertRow(row)
            self.queue_table.setItem(row, 0, QTableWidgetItem(p))
            self.queue_table.setItem(row, 1, QTableWidgetItem(f))
            self.queue_table.setItem(row, 2, QTableWidgetItem("Pending"))

    def run_command(self, cmd, callback=None):
        serial = self.device_combo.currentData()
        if serial:
            if "adb" in cmd: cmd = cmd.replace("adb", f"adb -s {serial}", 1)
            if "fastboot" in cmd: cmd = cmd.replace("fastboot", f"fastboot -s {serial}", 1)
        self.log(f"> {cmd}")
        self.thread = CommandThread(cmd)
        self.thread.output_signal.connect(self.log)
        if callback: self.thread.finished_signal.connect(callback)
        self.thread.start()

    def process_queue(self):
        if not self.is_flashing and self.queue_table.rowCount() > 0:
            self.is_flashing = True
            self.current_row = 0
            self.flash_next()

    def flash_next(self):
        if self.current_row < self.queue_table.rowCount():
            p = self.queue_table.item(self.current_row, 0).text()
            f = self.queue_table.item(self.current_row, 1).text()
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
