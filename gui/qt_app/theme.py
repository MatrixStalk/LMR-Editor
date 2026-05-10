NEON = "#4e98ff"
NEON_2 = "#23d9ff"
BLUE_SOFT = "#8fb8ff"
MUTED = "#78a4e8"
STYLE_PATH = __file__.replace("theme.py", "live_style.qss")

FALLBACK_QSS = f"""
* {{
    font-family: "Cascadia Mono", "JetBrains Mono", "Consolas";
    color: #d9e8ff;
}}

QWidget#Root {{
    background: transparent;
}}

QFrame#Backdrop {{
    background: #000000;
    border-radius: 24px;
}}

QFrame#Shell {{
    background: rgba(2, 7, 23, 0.58);
    border: 1px solid rgba(78, 152, 255, 0.85);
    border-radius: 28px;
}}

QFrame#Chrome {{
    background: transparent;
}}

QFrame#Panel, QFrame#PreviewPanel, QFrame#CardPanel {{
    background: rgba(4, 13, 35, 0.84);
    border: 1px solid rgba(78, 152, 255, 0.72);
    border-radius: 10px;
}}

QFrame#MenuBody {{
    background: transparent;
}}

QFrame#HeroPanel {{
    background: qradialgradient(cx:0.15, cy:0.15, radius:1.0,
        stop:0 rgba(28, 80, 176, 0.34), stop:0.48 rgba(5, 18, 49, 0.78), stop:1 rgba(2, 7, 23, 0.62));
    border: 1px solid rgba(78, 152, 255, 0.42);
    border-radius: 18px;
}}

QFrame#MenuActions {{
    background: rgba(4, 13, 35, 0.76);
    border: 1px solid rgba(78, 152, 255, 0.68);
    border-radius: 16px;
}}

QFrame#CardPanel {{
    border-color: rgba(78, 152, 255, 0.58);
}}

QLabel#AppTitle {{
    color: {BLUE_SOFT};
    font-size: 21px;
    font-weight: 700;
    letter-spacing: 1px;
}}

QLabel#AppSubtitle, QLabel#SectionHint {{
    color: {MUTED};
    font-size: 10px;
}}

QLabel#SectionTitle {{
    color: {BLUE_SOFT};
    font-size: 14px;
    font-weight: 700;
}}

QLabel#HeroTitle {{
    color: white;
    font-size: 34px;
    font-weight: 800;
    line-height: 1.1;
}}

QLabel#HeroText {{
    color: #a9c7ff;
    font-size: 13px;
    line-height: 1.4;
}}

QLabel#SmallTitle {{
    color: {BLUE_SOFT};
    font-size: 12px;
    font-weight: 700;
}}

QLabel#Muted {{
    color: {MUTED};
}}

QPushButton {{
    background: rgba(10, 31, 74, 0.78);
    border: 1px solid rgba(78, 152, 255, 0.78);
    border-radius: 7px;
    padding: 7px 12px;
    color: {BLUE_SOFT};
}}

QPushButton:hover {{
    background: rgba(22, 67, 152, 0.82);
    border-color: {NEON_2};
    color: white;
}}

QPushButton:pressed {{
    background: rgba(4, 15, 40, 0.95);
    color: {NEON_2};
}}

QPushButton#GamePill {{
    min-width: 210px;
    min-height: 34px;
    font-size: 12px;
}}

QPushButton#Primary {{
    min-width: 150px;
    min-height: 34px;
    color: white;
    font-weight: 700;
    background: rgba(30, 90, 202, 0.72);
}}

QPushButton#MenuButton {{
    text-align: left;
    padding-left: 18px;
    font-size: 13px;
    font-weight: 700;
}}

QPushButton#WindowButton {{
    border: none;
    background: transparent;
    font-size: 20px;
    padding: 2px 8px;
}}

QPushButton#WindowButton:hover {{
    background: rgba(78, 152, 255, 0.18);
}}

QPushButton#Danger:hover {{
    background: rgba(255, 68, 104, 0.22);
    color: #ff86a0;
}}

QTreeView {{
    background: transparent;
    border: none;
    outline: none;
    padding: 4px;
    color: {BLUE_SOFT};
}}

QTreeView::item {{
    min-height: 24px;
    border-radius: 5px;
    padding: 2px;
}}

QTreeView::item:selected {{
    background: rgba(78, 152, 255, 0.28);
    color: white;
}}

QPlainTextEdit {{
    background: rgba(2, 8, 24, 0.86);
    border: 1px solid rgba(78, 152, 255, 0.62);
    border-radius: 9px;
    selection-background-color: rgba(35, 217, 255, 0.28);
    selection-color: white;
    padding: 12px;
    font-size: 14px;
    line-height: 1.25;
}}

QTabWidget::pane {{
    border: none;
    background: transparent;
}}

QTabBar::tab {{
    background: rgba(8, 25, 64, 0.88);
    border: 1px solid rgba(78, 152, 255, 0.68);
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 9px 18px;
    margin-right: 4px;
    color: {BLUE_SOFT};
}}

QTabBar::tab:selected {{
    background: rgba(13, 38, 93, 0.98);
    color: white;
    border-color: {NEON_2};
}}

QSplitter::handle {{
    background: transparent;
}}

QStatusBar {{
    background: transparent;
    color: {BLUE_SOFT};
}}

QComboBox {{
    background: rgba(10, 31, 74, 0.78);
    border: 1px solid rgba(78, 152, 255, 0.78);
    border-radius: 6px;
    padding: 6px 10px;
    color: {BLUE_SOFT};
}}
"""


def load_app_qss() -> str:
    try:
        with open(STYLE_PATH, "r", encoding="utf-8") as style_file:
            return style_file.read()
    except OSError:
        return FALLBACK_QSS


APP_QSS = load_app_qss()
