# -*- coding: utf-8 -*-
"""
自動アップデート用UI
- UpdateCheckThread:  バックグラウンドでGitHub Releasesを確認するQThread
- UpdateDialog:       更新通知・ダウンロード進捗・適用を行うダイアログ
"""

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QMessageBox, QApplication
)

import config
from updater import (
    check_for_updates, download_installer, apply_update, UpdateError
)


class UpdateCheckThread(QThread):
    """GitHub Releases の最新版確認をバックグラウンドで行う"""
    # (結果dict または None, エラーメッセージ)
    finished_check = pyqtSignal(object, str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        try:
            result = check_for_updates()
            self.finished_check.emit(result, "")
        except UpdateError as e:
            self.finished_check.emit(None, str(e))
        except Exception as e:  # 予期しないエラーも握りつぶさない
            self.finished_check.emit(None, "予期しないエラー: %s" % e)


class UpdateDownloadThread(QThread):
    """インストーラーのダウンロードをバックグラウンドで行う"""
    progress = pyqtSignal(int, int)                        # (受信済, 総量)
    finished_download = pyqtSignal(object, str)            # (保存先 or None, エラー)

    def __init__(self, info: dict, parent=None):
        super().__init__(parent)
        self._info = info

    def run(self):
        def on_progress(received, total):
            self.progress.emit(received, total)

        try:
            path = download_installer(self._info, progress_cb=on_progress)
            self.finished_download.emit(path, "")
        except UpdateError as e:
            self.finished_download.emit(None, str(e))
        except Exception as e:
            self.finished_download.emit(None, "予期しないエラー: %s" % e)


class UpdateDialog(QDialog):
    """更新内容の表示とダウンロード・適用を行うダイアログ"""

    def __init__(self, update_info: dict, parent=None):
        super().__init__(parent)
        self._info = update_info
        self._installer_path = None
        self._download_thread = None

        self.setWindowTitle("アップデート")
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)

        version_label = QLabel(
            "新しいバージョンがあります。\n"
            "現在: v%s　→　最新: v%s" % (
                update_info.get("current", "?"),
                update_info.get("version", "?"),
            )
        )
        layout.addWidget(version_label)

        self.notes_view = QTextEdit()
        self.notes_view.setReadOnly(True)
        self.notes_view.setPlainText(update_info.get("notes") or "(リリースノートはありません)")
        self.notes_view.setMinimumHeight(120)
        layout.addWidget(self.notes_view)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setRange(0, 100)
        layout.addWidget(self.progress)

        self.status_label = QLabel("")
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)

        btn_layout = QHBoxLayout()
        self.download_btn = QPushButton("今すぐ更新")
        self.download_btn.clicked.connect(self.start_download)
        self.close_btn = QPushButton("後で")
        self.close_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.download_btn)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

    # ---------------- ダウンロード ----------------
    def start_download(self):
        self.download_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.status_label.setVisible(True)
        self.status_label.setText("ダウンロード中...")

        self._download_thread = UpdateDownloadThread(self._info, parent=self)
        self._download_thread.progress.connect(self.on_progress)
        self._download_thread.finished_download.connect(self.on_download_finished)
        self._download_thread.start()

    def on_progress(self, received: int, total: int):
        if total > 0:
            self.progress.setRange(0, 100)
            self.progress.setValue(min(100, int(received * 100 / total)))
            self.status_label.setText(
                "ダウンロード中... %.1f / %.1f MB" % (received / 1048576, total / 1048576))
        else:
            self.progress.setRange(0, 0)  # 不定進捗
            self.status_label.setText("ダウンロード中... %.1f MB" % (received / 1048576))

    def on_download_finished(self, path, error):
        if error:
            self.progress.setVisible(False)
            self.status_label.setText("")
            self.download_btn.setEnabled(True)
            self.close_btn.setEnabled(True)
            QMessageBox.warning(self, "アップデート", error)
            return

        self._installer_path = path
        self.progress.setValue(100)
        self.status_label.setText("ダウンロード完了。")

        reply = QMessageBox.question(
            self, "アップデート",
            "インストーラーを起動し、アプリケーションを更新します。\n"
            "続行しますか?\n(実行中のアプリは自動的に終了します)",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            try:
                apply_update(self._installer_path)
            except UpdateError as e:
                QMessageBox.warning(self, "アップデート", str(e))
                self.download_btn.setEnabled(True)
                self.close_btn.setEnabled(True)
                return
            # インストーラーに閉じられるため、こちらからも終了する
            QApplication.quit()
