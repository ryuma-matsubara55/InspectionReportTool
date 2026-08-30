
# カラーパレットの定義
DARK_BG = "#121212"
DARK_SURFACE = "#1e1e1e"
DARK_BORDER = "#888888" # シート用（しっかりと見えるように）
DARK_BORDER_SUBTLE = "rgba(255, 255, 255, 0.08)" # ダッシュボード用（薄く）
DARK_TEXT = "#e0e0e0"
DARK_ACCENT = "#3d5afe"
DARK_ACCENT_HOVER = "#536dfe"

LIGHT_BG = "#f5f7fa"
LIGHT_SURFACE = "#ffffff"
LIGHT_BORDER = "#b8bfc9" # 少し濃くして見やすく
LIGHT_TEXT = "#2c3e50"
LIGHT_ACCENT = "#409eff"
LIGHT_ACCENT_HOVER = "#66b1ff"

SUCCESS = "#4caf50"
ERROR = "#f44336"
WARNING = "#ff9800"
INFO = "#2196f3"

DARK_THEME_QSS = f"""
/* 全体設定 */
QWidget {{
    background-color: {DARK_BG};
    color: {DARK_TEXT};
    font-family: "Segoe UI", "Meiryo", sans-serif;
    font-size: 10pt;
}}

/* ウィンドウメイン */
QMainWindow {{
    background-color: {DARK_BG};
}}

/* 入力フィールド */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {DARK_SURFACE};
    color: {DARK_TEXT};
    border: 1px solid {DARK_BORDER};
    border-radius: 6px;
    padding: 6px;
    selection-background-color: {DARK_ACCENT};
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {DARK_ACCENT};
}}

/* ボタン */
QPushButton {{
    background-color: #2c2c2c;
    color: #ffffff;
    border: 1px solid {DARK_BORDER};
    border-radius: 6px;
    padding: 8px 16px;
    min-height: 24px;
}}

QPushButton:hover {{
    background-color: #383838;
    border: 1px solid #444444;
}}

QPushButton:pressed {{
    background-color: #222222;
}}

QPushButton:disabled {{
    background-color: {DARK_BG};
    color: #555555;
    border: 1px solid {DARK_BORDER};
}}

/* プライマリアクションボタン */
QPushButton#primaryBtn {{
    background-color: {DARK_ACCENT};
    border: none;
}}

QPushButton#primaryBtn:hover {{
    background-color: {DARK_ACCENT_HOVER};
}}

/* 危険アクションボタン */
QPushButton#dangerBtn {{
    background-color: {ERROR};
    border: none;
}}

QPushButton#dangerBtn:hover {{
    background-color: #ff5252;
}}

/* コンボボックス */
QComboBox {{
    background-color: {DARK_SURFACE};
    border: 1px solid {DARK_BORDER};
    border-radius: 6px;
    padding: 5px;
    min-width: 6em;
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left-width: 0px;
}}

/* タブウィジェット */
QTabWidget::pane {{
    border: 1px solid {DARK_BORDER};
    background-color: {DARK_BG};
    top: -1px;
}}

QTabBar::tab {{
    background-color: #1a1a1a;
    color: #888888;
    padding: 10px 20px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 4px;
    border: 1px solid {DARK_BORDER};
    border-bottom: none;
}}

QTabBar::tab:selected {{
    background-color: {DARK_BG};
    color: #ffffff;
    border-bottom: 2px solid {DARK_ACCENT};
}}

QTabBar::tab:hover {{
    background-color: #252525;
    color: #ffffff;
}}

/* テーブル */
QTableWidget {{
    background-color: {DARK_SURFACE};
    gridline-color: #777777;
    border: 1px solid {DARK_BORDER};
}}

QHeaderView::section {{
    background-color: #252526;
    color: {DARK_TEXT};
    padding: 4px;
    border: 1px solid {DARK_BORDER};
}}

/* スクロールバー */
QScrollBar:vertical {{
    border: none;
    background: {DARK_BG};
    width: 12px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background: #333333;
    min-height: 30px;
    border-radius: 6px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background: #444444;
}}

/* カードスタイル（ダッシュボード用） */
QFrame#DashboardCard {{
    background-color: {DARK_SURFACE};
    border: 1px solid {DARK_BORDER_SUBTLE};
    border-radius: 10px;
}}

QFrame#DashboardCard QLabel {{
    background: transparent;
}}

QLabel#DashboardSubtitle {{
    font-size: 9pt;
    color: #6b7280;
}}

QLabel#DashboardMeta {{
    font-size: 9pt;
    color: #6b7280;
}}

QLabel#SectionTitle {{
    font-size: 12pt;
    font-weight: 600;
    color: {DARK_TEXT};
    letter-spacing: 1px;
}}

QLabel#CardTitle {{
    font-size: 11pt;
    font-weight: 600;
    color: {DARK_TEXT};
}}

QLabel#LegendText {{
    font-size: 9pt;
    color: #9aa0a6;
}}

QLabel#RateValue {{
    font-size: 30pt;
    font-weight: 700;
    color: #ffffff;
}}

QProgressBar#DashboardProgress {{
    background-color: rgba(255, 255, 255, 0.08);
    border: none;
    border-radius: 3px;
}}

QProgressBar#DashboardProgress::chunk {{
    background-color: {SUCCESS};
    border-radius: 3px;
}}

/* 一般的な枠線 */
QFrame#imagePreviewFrame,QFrame#expectedResultRow {{
    border: 1px solid #5f6368;
    background-color: #1a1a1a;
    border-radius: 6px;
}}

/* テストケース内の画像エリア */
QFrame#imageContainerFrame {{
    border: 1px solid #5f6368;
    background-color: #181818;
    border-radius: 6px;
}}

/* 自然なセパレータ線 */
QFrame#separatorLine {{
    background-color: #3a3a3a;
    border: none;
    min-height: 1px;
    max-height: 1px;
}}

QLabel#DashboardTitle {{
    font-size: 16pt;
    font-weight: 600;
    color: #ffffff;
    letter-spacing: 1px;
}}

QLabel#StatLabel {{
    font-size: 9pt;
    font-weight: 600;
    color: #8a8f98;
    letter-spacing: 1px;
}}

QLabel#StatValue {{
    font-size: 24pt;
    font-weight: 700;
}}

/* テストケースウィジェット */
QFrame#testCaseFrame {{
    background-color: {DARK_SURFACE};
    border: 1px solid {DARK_BORDER};
    border-radius: 8px;
    margin-bottom: 12px;
}}

QFrame#testCaseFrame:hover {{
    border: 1px solid #4d4d4d;
}}

QFrame#testCaseFrame[highlighted="true"] {{
    background-color: #333300;
    border: 2px solid #ffd700;
}}
"""

LIGHT_THEME_QSS = f"""
/* 全体設定 */
QWidget {{
    background-color: {LIGHT_BG};
    color: {LIGHT_TEXT};
    font-family: "Segoe UI", "Meiryo", sans-serif;
    font-size: 10pt;
}}

/* ウィンドウメイン */
QMainWindow {{
    background-color: {LIGHT_BG};
}}

/* 入力フィールド */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {LIGHT_SURFACE};
    color: {LIGHT_TEXT};
    border: 1px solid {LIGHT_BORDER};
    border-radius: 6px;
    padding: 6px;
    selection-background-color: {LIGHT_ACCENT};
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {LIGHT_ACCENT};
}}

/* ボタン */
QPushButton {{
    background-color: {LIGHT_SURFACE};
    color: {LIGHT_TEXT};
    border: 1px solid {LIGHT_BORDER};
    border-radius: 6px;
    padding: 8px 16px;
    min-height: 24px;
}}

QPushButton:hover {{
    background-color: #f0f2f5;
    border: 1px solid #c0c4cc;
}}

QPushButton:pressed {{
    background-color: #e4e7ed;
}}

/* プライマリアクションボタン */
QPushButton#primaryBtn {{
    background-color: {LIGHT_ACCENT};
    color: #ffffff;
    border: none;
}}

QPushButton#primaryBtn:hover {{
    background-color: {LIGHT_ACCENT_HOVER};
}}

/* カードスタイル（ダッシュボード用） */
QFrame#DashboardCard {{
    background-color: #ffffff;
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: 10px;
}}

QFrame#DashboardCard QLabel {{
    background: transparent;
}}

QLabel#DashboardSubtitle {{
    font-size: 9pt;
    color: #6b7280;
}}

QLabel#DashboardMeta {{
    font-size: 9pt;
    color: #6b7280;
}}

QLabel#SectionTitle {{
    font-size: 12pt;
    font-weight: 600;
    color: {LIGHT_TEXT};
    letter-spacing: 1px;
}}

QLabel#CardTitle {{
    font-size: 11pt;
    font-weight: 600;
    color: {LIGHT_TEXT};
}}

QLabel#LegendText {{
    font-size: 9pt;
    color: #5f6b7a;
}}

QLabel#RateValue {{
    font-size: 30pt;
    font-weight: 700;
    color: {LIGHT_TEXT};
}}

QProgressBar#DashboardProgress {{
    background-color: rgba(0, 0, 0, 0.06);
    border: none;
    border-radius: 3px;
}}

QProgressBar#DashboardProgress::chunk {{
    background-color: {SUCCESS};
    border-radius: 3px;
}}

/* 一般的な枠線 */
QFrame#imagePreviewFrame,QFrame#expectedResultRow {{
    border: 1px solid #d5d9df;
    background-color: #ffffff;
    border-radius: 6px;
}}

/* テストケース内の画像エリア */
QFrame#imageContainerFrame {{
    border: 1px solid #d5d9df;
    background-color: #ffffff;
    border-radius: 6px;
}}

/* 自然なセパレータ線 */
QFrame#separatorLine {{
    background-color: #e1e5eb;
    border: none;
    min-height: 1px;
    max-height: 1px;
}}

QLabel#DashboardTitle {{
    font-size: 16pt;
    font-weight: 600;
    color: {LIGHT_TEXT};
    letter-spacing: 1px;
}}

QLabel#StatLabel {{
    font-size: 9pt;
    font-weight: 600;
    color: #6b7280;
    letter-spacing: 1px;
}}

QLabel#StatValue {{
    font-size: 24pt;
    font-weight: 700;
}}

/* テストケースウィジェット */
QFrame#testCaseFrame {{
    background-color: {LIGHT_SURFACE};
    border: 1px solid {LIGHT_BORDER};
    border-radius: 8px;
    margin-bottom: 12px;
}}

QFrame#testCaseFrame:hover {{
    border: 1px solid #c0c4cc;
}}

QFrame#testCaseFrame[highlighted="true"] {{
    background-color: #fffae6;
    border: 2px solid #ffcc00;
}}
"""
