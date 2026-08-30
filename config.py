
# -*- coding: utf-8 -*-
"""
設定の集中管理 + 設定ファイルの読み書きヘルパ
 - executor は「文字列」を標準とする（過去の辞書形式に対しては互換処理で文字列化）
 - sheets は「文字列のリスト」
"""

from pathlib import Path
import json
import sys
from typing import Any, List

# === アプリ基本情報 ===
APP_NAME: str = "検査成績書作成ツール"
APP_VERSION: str = "0.1.0"

# === 自動アップデート設定 ===
GITHUB_OWNER: str = "ryuma-matsubara55"      # GitHubのオーナー名
GITHUB_REPO: str = "InspectionReportTool"    # GitHubのリポジトリ名
UPDATE_CHECK_ENABLED: bool = True            # 起動時の自動更新チェック
UPDATE_CHECK_TIMEOUT: int = 10               # 通信タイムアウト(秒)

# === UI/Qt 設定 ===
QT_STYLE: str = "Fusion"

# === ウィンドウの見た目 ===
WINDOW_TITLE: str = APP_NAME
WINDOW_WIDTH: int = 1400
WINDOW_HEIGHT: int = 900

# === ロギング関連（必要に応じて）===
ENABLE_LOGGING: bool = True
LOG_LEVEL: str = "INFO"
LOG_DIR: Path = Path("logs")
LOG_FILE: Path = LOG_DIR / "app.log"

# === パス類 ===
if getattr(sys, 'frozen', False):
    # PyInstallerなどでパッケージ化されている場合：実行ファイルと同じ階層をベースにする
    BASE_DIR = Path(sys.executable).resolve().parent
    # リソース類は内部（sys._MEIPASS）にある可能性があるが、
    # 実行環境に合わせて適宜調整
    RESOURCES_DIR = Path(getattr(sys, '_MEIPASS', BASE_DIR)) / "resources"
else:
    # 通常のスクリプト実行時：ソースコードと同じ階層をベースにする
    BASE_DIR = Path(__file__).resolve().parent
    RESOURCES_DIR = BASE_DIR / "resources"

CONFIG_DIR: Path = BASE_DIR  # 設定ファイルはアプリの実行場所に保存

# === 国際化 ===
LANG: str = "ja-JP"

if ENABLE_LOGGING:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

# === 設定ファイル ===
EXECUTOR_JSON: Path = CONFIG_DIR / "executor.json"
SHEETS_JSON: Path = CONFIG_DIR / "sheets.json"
THEME_JSON: Path = CONFIG_DIR / "theme.json"

DEFAULT_EXECUTOR: str = ""  # 実行者名（未設定なら空文字）
DEFAULT_SHEETS: List[str] = ["シート1"]
DEFAULT_THEME: str = "dark"  # デフォルトはダークモード

# === JSON ヘルパ ===
def _read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _write_json(path: Path, data: Any) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

# === レガシー互換：executor の型を常に str に正規化 ===
def _normalize_executor(obj: Any) -> str:
    """
    過去に dict で保存されていた executor を文字列へ正規化する。
    例:
      - "山田太郎"        -> "山田太郎"
      - {"name": "山田"}  -> "山田"
      - {"executor":"A"}  -> "A"
      - {"user":"B"}      -> "B"
      - {"first":"A", "last":"B"} -> "A B"
      - その他辞書        -> 最初の値を文字列化
      - list/tuple        -> 先頭要素を文字列化
      - None/未知         -> DEFAULT_EXECUTOR
    """
    if obj is None:
        return DEFAULT_EXECUTOR
    if isinstance(obj, str):
        return obj
    if isinstance(obj, (list, tuple)) and obj:
        return str(obj[0]) or DEFAULT_EXECUTOR
    if isinstance(obj, dict):
        # よくありそうなキーを優先
        for key in ("name", "executor", "user", "displayName", "value"):
            if key in obj and obj[key]:
                return str(obj[key])
        # first/last をまとめる
        first = obj.get("first") or obj.get("given") or ""
        last = obj.get("last") or obj.get("family") or ""
        if first or last:
            return f"{str(first).strip()} {str(last).strip()}".strip()
        # それ以外は最初の値を使う
        try:
            first_val = next(iter(obj.values()))
            if first_val:
                return str(first_val)
        except Exception:
            pass
        return DEFAULT_EXECUTOR
    # その他は文字列化して返す
    try:
        s = str(obj)
        return s if s.lower() not in ("none", "{}", "[]") else DEFAULT_EXECUTOR
    except Exception:
        return DEFAULT_EXECUTOR

# === main_window から期待される API ===
def load_executor() -> str:
    """executor.json を読み込み、常に文字列（実行者名）を返す。無ければ DEFAULT_EXECUTOR。"""
    raw = _read_json(EXECUTOR_JSON, DEFAULT_EXECUTOR)
    return _normalize_executor(raw)

def save_executor(name: str) -> bool:
    """executor.json に文字列（実行者名）を書き込む。"""
    # 互換確保：誤って dict を渡しても文字列化して保存
    norm = _normalize_executor(name)
    return _write_json(EXECUTOR_JSON, norm)

def load_sheets() -> List[str]:
    """sheets.json を読み込み、文字列リストを返す。無ければ DEFAULT_SHEETS。"""
    data = _read_json(SHEETS_JSON, DEFAULT_SHEETS)
    return data if isinstance(data, list) else DEFAULT_SHEETS

def save_sheets(sheets: List[str]) -> bool:
    """sheets.json に文字列リストを書き込む。"""
    if not isinstance(sheets, list):
        return False
    # 空白除去と重複排除
    cleaned = []
    for s in sheets:
        s = str(s).strip()
        if s and s not in cleaned:
            cleaned.append(s)
    return _write_json(SHEETS_JSON, cleaned if cleaned else DEFAULT_SHEETS)

def load_theme() -> str:
    """theme.json を読み込み、'dark' または 'light' を返す。"""
    theme = _read_json(THEME_JSON, DEFAULT_THEME)
    return theme if theme in ('dark', 'light') else DEFAULT_THEME

def save_theme(theme: str) -> bool:
    """theme.json にテーマを書き込む。"""
    if theme not in ('dark', 'light'):
        return False
    return _write_json(THEME_JSON, theme)

# === 実行時ヘルパ ===
def apply_qt_style(app):
    try:
        app.setStyle(QT_STYLE)
    except Exception:
        pass
