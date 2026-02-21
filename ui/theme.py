from PySide6.QtGui import QColor

class Theme:
    # Colors
    BG_DARK = "#121212"
    BG_CARD = "#1E1E1E"
    BG_INPUT = "#252525"
    BORDER = "#333333"
    ACCENT = "#00E676"
    ACCENT_HOVER = "#00C853"
    DANGER = "#B71C1C"
    DANGER_HOVER = "#D32F2F"
    TEXT_PRIMARY = "#E0E0E0"
    TEXT_SECONDARY = "#AAAAAA"
    
    # Fonts
    FONT_FAMILY = "Segoe UI, Arial, sans-serif"
    FONT_SIZE_BASE = "12px"
    FONT_SIZE_SMALL = "10px"
    FONT_SIZE_LARGE = "14px"
    FONT_SIZE_TITLE = "22px"

    # Layout
    SPACING = 8
    MARGIN = 10
    RADIUS = "4px"

    @classmethod
    def get_stylesheet(cls):
        return f"""
        QMainWindow {{ background-color: {cls.BG_DARK}; color: {cls.TEXT_PRIMARY}; font-family: {cls.FONT_FAMILY}; font-size: {cls.FONT_SIZE_BASE}; }}
        
        QTabWidget::pane {{ border: 1px solid {cls.BORDER}; top: -1px; background: {cls.BG_CARD}; border-radius: {cls.RADIUS}; }}
        QTabBar::tab {{ background: {cls.BG_INPUT}; padding: 6px 15px; border: 1px solid {cls.BORDER}; margin-right: 2px; border-top-left-radius: {cls.RADIUS}; border-top-right-radius: {cls.RADIUS}; color: {cls.TEXT_SECONDARY}; }}
        QTabBar::tab:selected {{ background: {cls.BG_CARD}; border-bottom-color: {cls.BG_CARD}; color: {cls.ACCENT}; font-weight: bold; }}
        
        QGroupBox {{ font-weight: bold; border: 1px solid {cls.BORDER}; border-radius: 6px; margin-top: 15px; padding-top: 10px; color: {cls.ACCENT}; }}
        QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; padding: 0 5px; left: 10px; }}
        
        QPushButton {{ background-color: {cls.BG_INPUT}; border: 1px solid #444444; border-radius: {cls.RADIUS}; padding: 4px 12px; color: white; min-height: 22px; }}
        QPushButton:hover {{ background-color: #383838; border: 1px solid {cls.ACCENT}; }}
        QPushButton:pressed {{ background-color: #444444; }}
        QPushButton:disabled {{ color: #666666; background-color: #1A1A1A; border: 1px solid #222222; }}
        
        QPushButton#accent_btn {{ background-color: {cls.ACCENT}; color: #000000; font-weight: bold; border: none; }}
        QPushButton#accent_btn:hover {{ background-color: {cls.ACCENT_HOVER}; }}
        
        QPushButton#danger_btn {{ background-color: {cls.DANGER}; font-weight: bold; border: 1px solid {cls.DANGER_HOVER}; }}
        QPushButton#danger_btn:hover {{ background-color: {cls.DANGER_HOVER}; border: 1px solid white; }}
        
        QLineEdit, QComboBox, QSpinBox {{ background-color: {cls.BG_INPUT}; border: 1px solid {cls.BORDER}; border-radius: 3px; padding: 3px; color: {cls.TEXT_PRIMARY}; selection-background-color: {cls.ACCENT}; }}
        QLineEdit:focus, QComboBox:focus {{ border: 1px solid {cls.ACCENT}; }}
        
        QTableWidget {{ background-color: {cls.BG_CARD}; border: 1px solid {cls.BORDER}; alternate-background-color: {cls.BG_INPUT}; color: {cls.TEXT_PRIMARY}; gridline-color: {cls.BORDER}; outline: none; }}
        QHeaderView::section {{ background-color: {cls.BG_INPUT}; padding: 4px; border: 1px solid {cls.BORDER}; color: {cls.TEXT_SECONDARY}; font-weight: bold; }}
        
        QProgressBar {{ border: 1px solid {cls.BORDER}; border-radius: {cls.RADIUS}; text-align: center; background-color: {cls.BG_INPUT}; height: 12px; font-size: {cls.FONT_SIZE_SMALL}; }}
        QProgressBar::chunk {{ background-color: {cls.ACCENT}; border-radius: 2px; }}
        
        QTextEdit {{ background-color: #000000; border: 1px solid {cls.BORDER}; border-radius: {cls.RADIUS}; color: {cls.TEXT_PRIMARY}; selection-background-color: {cls.ACCENT}; }}
        
        QScrollBar:vertical {{ border: none; background: transparent; width: 8px; margin: 0; }}
        QScrollBar::handle:vertical {{ background: {cls.BORDER}; min-height: 20px; border-radius: 4px; }}
        QScrollBar::handle:vertical:hover {{ background: {cls.ACCENT}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        
        QSplitter::handle {{ background-color: {cls.BORDER}; }}
        """
