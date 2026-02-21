from PySide6.QtGui import QColor

class Theme:
    # "Deep Oceanic" Modern Palette
    BG_DARK = "#0f172a"    # Deep Slate
    BG_CARD = "#1e293b"    # Slate Blue
    BG_INPUT = "#334155"   # Muted Slate
    BORDER = "#334155"     
    ACCENT = "#38bdf8"     # Sky Blue
    ACCENT_HOVER = "#7dd3fc"
    SECONDARY = "#818cf8"  # Indigo
    DANGER = "#f43f5e"     # Rose Red
    DANGER_HOVER = "#fb7185"
    SUCCESS = "#10b981"    # Emerald
    TEXT_PRIMARY = "#f1f5f9" 
    TEXT_SECONDARY = "#94a3b8"
    
    # Fonts
    FONT_FAMILY = "Inter, Segoe UI, system-ui, sans-serif"
    FONT_SIZE_BASE = "12px"
    FONT_SIZE_SMALL = "10px"
    FONT_SIZE_TITLE = "20px"

    # Layout
    SPACING = 8
    MARGIN = 10
    RADIUS = "8px"

    @classmethod
    def get_stylesheet(cls):
        return f"""
        QMainWindow {{ 
            background-color: {cls.BG_DARK}; 
            color: {cls.TEXT_PRIMARY}; 
            font-family: {cls.FONT_FAMILY}; 
            font-size: {cls.FONT_SIZE_BASE}; 
        }}
        
        QTabWidget {{ 
            margin: 0px;
            padding: 0px;
            border: none;
        }}

        QTabWidget::pane {{ 
            border: 1px solid {cls.BORDER}; 
            border-top: none;
            background: {cls.BG_CARD}; 
            border-bottom-left-radius: {cls.RADIUS}; 
            border-bottom-right-radius: {cls.RADIUS}; 
        }}
        
        QTabBar {{
            background-color: {cls.BG_DARK};
            qproperty-drawBase: 0;
            margin: 0px;
        }}

        QTabBar::tab {{ 
            background: transparent; 
            padding: 12px 30px; 
            margin-right: 0px; 
            color: {cls.TEXT_SECONDARY}; 
            font-weight: 700;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 1.2px;
            border-bottom: 2px solid transparent;
        }}
        
        QTabBar::tab:selected {{ 
            color: {cls.ACCENT}; 
            border-bottom: 3px solid {cls.ACCENT};
            background: {cls.BG_CARD};
        }}
        
        QTabBar::tab:hover:!selected {{
            color: white;
            background: {cls.BG_INPUT};
        }}
        
        QGroupBox {{ 
            font-weight: bold; 
            border: 1px solid {cls.BORDER}; 
            border-radius: {cls.RADIUS}; 
            margin-top: 8px; 
            padding-top: 10px; 
            background-color: {cls.BG_CARD};
            color: {cls.TEXT_PRIMARY};
        }}
        
        QGroupBox::title {{ 
            subcontrol-origin: margin; 
            subcontrol-position: top left; 
            padding: 0 10px; 
            left: 12px; 
            color: {cls.ACCENT};
            text-transform: uppercase;
            font-size: 10px;
            letter-spacing: 1.2px;
            font-weight: 800;
        }}
        
        QPushButton {{ 
            background-color: {cls.BG_INPUT}; 
            border: 1px solid {cls.BORDER}; 
            border-radius: 6px; 
            padding: 6px 16px; 
            color: {cls.TEXT_PRIMARY}; 
            min-height: 26px; 
            font-weight: 600;
        }}
        
        QPushButton:hover {{ 
            background-color: {cls.BORDER}; 
            border: 1px solid {cls.ACCENT}; 
        }}
        
        QPushButton#accent_btn {{ 
            background-color: {cls.ACCENT}; 
            color: {cls.BG_DARK}; 
            border: none; 
        }}
        
        QPushButton#accent_btn:hover {{ 
            background-color: white; 
        }}
        
        QPushButton#danger_btn {{ 
            background-color: {cls.DANGER}; 
            color: white;
            border: none;
        }}
        
        QLineEdit, QComboBox, QSpinBox {{ 
            background-color: {cls.BG_DARK}; 
            border: 1px solid {cls.BORDER}; 
            border-radius: 6px; 
            padding: 5px 10px; 
            color: {cls.TEXT_PRIMARY}; 
        }}
        
        QLineEdit:focus {{ 
            border: 1px solid {cls.ACCENT}; 
        }}
        
        QTableWidget {{ 
            background-color: {cls.BG_CARD}; 
            border: 1px solid {cls.BORDER}; 
            gridline-color: {cls.BORDER}; 
            color: {cls.TEXT_PRIMARY};
            selection-background-color: {cls.BG_INPUT};
        }}
        
        QHeaderView::section {{ 
            background-color: {cls.BG_INPUT}; 
            padding: 8px; 
            border: none;
            border-right: 1px solid {cls.BORDER};
            border-bottom: 1px solid {cls.BORDER};
            color: {cls.TEXT_SECONDARY}; 
            font-weight: bold; 
            text-transform: uppercase;
            font-size: 9px;
        }}
        
        QProgressBar {{ 
            border: none; 
            border-radius: 10px; 
            text-align: center; 
            background-color: {cls.BG_DARK}; 
            height: 10px; 
        }}
        
        QProgressBar::chunk {{ 
            background-color: {cls.ACCENT}; 
            border-radius: 10px; 
        }}
        
        QTextEdit {{ 
            background-color: #080c14; 
            border: 1px solid {cls.BORDER}; 
            border-radius: {cls.RADIUS}; 
            color: #cbd5e1; 
            font-family: 'JetBrains Mono', 'Consolas', monospace;
            font-size: 11px;
            padding: 8px;
        }}
        
        QScrollBar:vertical {{ 
            background: transparent; 
            width: 8px; 
        }}
        
        QScrollBar::handle:vertical {{ 
            background: {cls.BG_INPUT}; 
            border-radius: 4px; 
        }}
        """
