# -*- coding: utf-8 -*-
"""
GitHub Releases を利用した自動アップデート機能(標準ライブラリのみで実装)

- check_for_updates():   最新リリース情報の取得とバージョン比較
- download_installer():  セットアップ exe を一時フォルダへダウンロード(進捗コールバック付き)
- apply_update():        ダウンロードしたインストーラーを起動し、アプリを更新

配布形態は Inno Setup で作成したインストーラー(Qualis-Setup-{version}.exe)を
GitHub Releases に添付する運用を前提とする。
"""

import json
import os
import re
import subprocess
import tempfile
import urllib.request

import config

API_BASE = "https://api.github.com"


class UpdateError(Exception):
    """アップデート確認・ダウンロード時のエラー"""


# ---------------------------------------------------------------
# バージョン比較
# ---------------------------------------------------------------
def _version_tuple(version: str):
    """'v0.2.1' / '0.2.1' などを比較可能なタプル (0, 2, 1) に変換する"""
    v = str(version or "").strip().lstrip("vV")
    parts = []
    for piece in v.split("."):
        m = re.match(r"(\d+)", piece)
        parts.append(int(m.group(1)) if m else 0)
    # 少なくとも3要素(x.y.z)に揃える
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def is_newer_version(latest: str, current: str) -> bool:
    """latest が current より新しい場合 True"""
    return _version_tuple(latest) > _version_tuple(current)


# ---------------------------------------------------------------
# リリース情報の取得・解析
# ---------------------------------------------------------------
def _github_token() -> str:
    """プライベートリポジトリ用のトークン(環境変数から取得、無ければ空)"""
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""


def _make_request(url: str, accept: str = "application/json"):
    """GitHub API / ダウンロード用の urllib リクエストを生成する"""
    req = urllib.request.Request(url, headers={
        "Accept": accept,
        "User-Agent": "InspectionReportTool-Updater",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    token = _github_token()
    if token:
        req.add_header("Authorization", "token %s" % token)
    return req


def _select_installer_asset(assets):
    """リリースのアセットからインストーラー(SetUp exe)を選ぶ"""
    candidates = [a for a in assets if str(a.get("name", "")).lower().endswith(".exe")]
    if not candidates:
        return None
    # '...-Setup-x.y.z.exe' を優先
    for asset in candidates:
        if re.search(r"setup", str(asset.get("name", "")), re.IGNORECASE):
            return asset
    return candidates[0]


def parse_release(payload: dict) -> dict:
    """GitHub Releases API のレスポンスをアップデート情報 dict へ変換する"""
    tag = str(payload.get("tag_name") or "")
    assets = payload.get("assets") or []
    asset = _select_installer_asset(assets)
    return {
        "tag": tag,
        "version": tag.lstrip("vV"),
        "notes": payload.get("body") or "",
        "html_url": payload.get("html_url") or "",
        "asset_name": (asset or {}).get("name", ""),
        "asset_url": (asset or {}).get("browser_download_url", ""),
        "api_asset_url": (asset or {}).get("url", ""),
        "asset_size": (asset or {}).get("size", 0),
    }


def check_for_updates() -> dict:
    """
    GitHub Releases(latest) を確認し、更新の有無を返す。

    戻り値: {
        available, current, latest, notes, html_url,
        asset_name, asset_url, api_asset_url, asset_size
    }
    通信エラー・解析エラー時は UpdateError を送出する。
    """
    url = "%s/repos/%s/%s/releases/latest" % (
        API_BASE, config.GITHUB_OWNER, config.GITHUB_REPO)
    try:
        with urllib.request.urlopen(
                _make_request(url), timeout=config.UPDATE_CHECK_TIMEOUT) as res:
            payload = json.loads(res.read().decode("utf-8"))
    except Exception as e:
        raise UpdateError("更新情報の取得に失敗しました: %s" % e)

    if "message" in payload and not payload.get("tag_name"):
        raise UpdateError("GitHub API エラー: %s" % payload["message"])

    info = parse_release(payload)
    if not info["asset_url"] and not info["api_asset_url"]:
        raise UpdateError("リリースにインストーラー(.exe)が添付されていません。")

    return {
        "available": is_newer_version(info["version"], config.APP_VERSION),
        "current": config.APP_VERSION,
        **info,
    }


# ---------------------------------------------------------------
# ダウンロード・適用
# ---------------------------------------------------------------
def download_installer(info: dict, progress_cb=None, dest: str = None) -> str:
    """
    インストーラーをダウンロードし、保存先パスを返す。

    info:        check_for_updates() の戻り値
    progress_cb: (received_bytes, total_bytes) を受けるコールバック(任意)
    dest:        保存先ディレクトリ(未指定なら %TEMP%)
    """
    # プライベートリポジトリの場合は API 経由(+octet-stream)でしか取得できない
    if _github_token() and info.get("api_asset_url"):
        url = info["api_asset_url"]
    else:
        url = info["asset_url"]

    file_name = info.get("asset_name") or "update_installer.exe"
    dest_path = os.path.join(dest or tempfile.gettempdir(), file_name)

    try:
        with urllib.request.urlopen(
                _make_request(url, accept="application/octet-stream")) as res:
            total = int(res.headers.get("Content-Length") or info.get("asset_size") or 0)
            received = 0
            with open(dest_path, "wb") as f:
                while True:
                    chunk = res.read(64 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)
                    if progress_cb:
                        progress_cb(received, total)
    except Exception as e:
        raise UpdateError("インストーラーのダウンロードに失敗しました: %s" % e)

    return dest_path


def apply_update(installer_path: str):
    """
    ダウンロード済みインストーラーを起動する。
    アプリ自身は自分の exe を差し替えられないため、Inno Setup に
    /FORCECLOSEAPPLICATIONS で実行中の本アプリを閉じさせて上書きインストールする。
    """
    if not os.path.exists(installer_path):
        raise UpdateError("インストーラーが見つかりません: %s" % installer_path)
    subprocess.Popen([
        installer_path,
        "/SILENT",                   # 画面を最小限にしてインストール
        "/FORCECLOSEAPPLICATIONS",   # 実行中の本アプリを自動的に閉じる
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
    ], close_fds=True)

