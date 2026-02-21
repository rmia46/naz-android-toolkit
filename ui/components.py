from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QPushButton, QGroupBox, QHBoxLayout, QWidget
from PySide6.QtCore import Qt
from ui.theme import Theme

class InfoCard(QFrame):
    def __init__(self, title, accent_color=Theme.ACCENT, parent=None):
        super().__init__(parent)
        self.accent_color = accent_color
        self.setStyleSheet(f"""
            QFrame {{ 
                background-color: {Theme.BG_CARD}; 
                border: 1px solid {Theme.BORDER}; 
                border-radius: {Theme.RADIUS}; 
            }}
            QLabel {{ border: none; background: transparent; padding: 0; }}
        """)
        self.setMinimumHeight(75)
        self.setMinimumWidth(180)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)
        
        self.title_lbl = QLabel(title.upper())
        self.title_lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 9px; font-weight: 800; letter-spacing: 1.2px;")
        
        self.val_lbl = QLabel("---")
        self.val_lbl.setStyleSheet(f"color: {accent_color}; font-size: 15px; font-weight: bold;")
        self.val_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.val_lbl.setWordWrap(True)
        
        layout.addWidget(self.title_lbl)
        layout.addWidget(self.val_lbl)

    def set_value(self, value, color=None):
        self.val_lbl.setText(str(value))
        current_color = color if color else self.accent_color
        self.val_lbl.setStyleSheet(f"color: {current_color}; font-size: 15px; font-weight: bold;")

class ActionButton(QPushButton):
    def __init__(self, text, style="default", parent=None):
        super().__init__(text, parent)
        if style == "accent":
            self.setObjectName("accent_btn")
        elif style == "danger":
            self.setObjectName("danger_btn")
        else:
            self.setObjectName("default_btn")

class CompactGroupBox(QGroupBox):
    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        self.setStyleSheet(f"""
            QGroupBox {{ 
                font-weight: bold; 
                border: 1px solid {Theme.BORDER}; 
                border-radius: {Theme.RADIUS}; 
                margin-top: 8px; 
                padding-top: 8px; 
                color: {Theme.TEXT_PRIMARY}; 
                background-color: {Theme.BG_CARD};
            }}
            QGroupBox::title {{ 
                subcontrol-origin: margin; 
                subcontrol-position: top left; 
                padding: 0 10px; 
                left: 12px; 
                top: 0px;
                color: {Theme.ACCENT};
                text-transform: uppercase;
                font-size: 9px;
                letter-spacing: 1.2px;
                font-weight: 800;
                background-color: transparent;
            }}
        """)

def create_h_layout(widgets=None, spacing=Theme.SPACING, margins=(0,0,0,0)):
    layout = QHBoxLayout()
    layout.setSpacing(spacing)
    layout.setContentsMargins(*margins)
    if widgets:
        for w in widgets:
            if isinstance(w, QWidget):
                layout.addWidget(w)
            elif isinstance(w, int):
                layout.addStretch(w)
    return layout

def create_v_layout(widgets=None, spacing=Theme.SPACING, margins=(0,0,0,0)):
    layout = QVBoxLayout()
    layout.setSpacing(spacing)
    layout.setContentsMargins(*margins)
    if widgets:
        for w in widgets:
            if isinstance(w, QWidget):
                layout.addWidget(w)
            elif isinstance(w, int):
                layout.addStretch(w)
    return layout
