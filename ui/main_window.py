from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTabWidget, QDialog, QLabel, QLineEdit,
    QFileDialog, QMessageBox, QDialogButtonBox, QInputDialog,
    QScrollArea, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QStatusBar,
    QStyledItemDelegate, QTextEdit, QStyle, QProgressDialog, QApplication,
    QUndoStack, QShortcut
)
from PyQt5.QtCore import Qt, QEvent, QTimer, QSize
from PyQt5.QtGui import QFont, QColor, QBrush, QTextDocument, QPalette, QKeySequence
from PyQt5.QtWidgets import QTextEdit, QAbstractItemView, QStyledItemDelegate

from config import (
    load_executor, save_executor, load_sheets, save_sheets, load_theme, save_theme,
    APP_VERSION, UPDATE_CHECK_ENABLED
)
from ui.test_case_widget import TestCaseWidget
from ui.styles import DARK_THEME_QSS, LIGHT_THEME_QSS
from ui.undo_commands import (
    AddRemoveTestCaseCommand, MoveTestCaseCommand, TestCaseDataCommand, SheetCommand
)
from ui.auto_save_manager import AutoSaveManager
from ui.dashboard_widget import DashboardWidget
from ui.update_dialog import UpdateCheckThread, UpdateDialog
from excel.excel_generator import ExcelGenerator
import os
from datetime import datetime


class ExecutorDialog(QDialog):
    def __init__(self, current_executor: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle('実行者設定')
        self.setGeometry(200, 200, 320, 150)

        layout = QVBoxLayout()
        layout.addWidget(QLabel('実行者名:'))
        self.executor_edit = QLineEdit()
        self.executor_edit.setText(current_executor or "")
        layout.addWidget(self.executor_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def get_executor(self) -> str:
        return self.executor_edit.text().strip()



class AutoResizingTextEdit(QTextEdit):
    """
    - Enter: 改行
    - Ctrl+Enter: 確定（commit）
    - IME変換中でも崩れにくい（リサイズは外部でデバウンス）
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._commit = None
        self.setAcceptRichText(False)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setLineWrapMode(QTextEdit.WidgetWidth)
        self.setTabChangesFocus(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_InputMethodEnabled, True)

    def setCommitCallback(self, fn):
        self._commit = fn

    def keyPressEvent(self, e):
        # Ctrl+Enter = 確定
        if (e.key() in (Qt.Key_Return, Qt.Key_Enter)) and (e.modifiers() & Qt.ControlModifier):
            e.accept()
            if self._commit:
                self._commit()
            return

        # Enter/Return は「必ず改行」（ビュー側の確定動作を防ぐ）
        if e.key() in (Qt.Key_Return, Qt.Key_Enter):
            e.accept()
            super().keyPressEvent(e)  # QTextEditに改行させる
            return

        super().keyPressEvent(e)       


class MultiLineTextDelegate(QStyledItemDelegate):
    """
    - 表示時: sizeHintで行高を内容に合わせる
    - 編集時: QTextEdit。行高のみ変更し、geometryは触らない（消える問題対策）
    - リサイズはデバウンスしてIME入力に強くする
    """
    def __init__(self, parent=None, min_lines=2, padding=10, debounce_ms=40):
        super().__init__(parent)
        self.min_lines = min_lines
        self.padding = padding
        self.debounce_ms = debounce_ms
        self._timers = {}  # editor -> QTimer

    def _find_table(self, parent):
        p = parent
        while p is not None and not isinstance(p, QAbstractItemView):
            p = p.parent()
        return p

    def _calc_doc_height(self, font, text, width):
        doc = QTextDocument()
        doc.setDefaultFont(font)
        doc.setTextWidth(max(1, width))
        doc.setPlainText(text or "")
        return doc.documentLayout().documentSize().height()

    # --- 非編集中の行高さ（読みやすさの要）---
    def sizeHint(self, option, index):
        text = index.model().data(index, Qt.DisplayRole) or ""
        w = max(1, option.rect.width())

        doc_h = self._calc_doc_height(option.font, text, w)
        min_h = option.fontMetrics.lineSpacing() * self.min_lines + self.padding
        h = int(max(min_h, doc_h + self.padding))
        return QSize(option.rect.width(), h)

    def createEditor(self, parent, option, index):
        editor = AutoResizingTextEdit(parent)
        table = self._find_table(parent)
        row = index.row()

        def commit():
            # ここで確実にコミットして閉じる
            self.commitData.emit(editor)
            self.closeEditor.emit(editor, QStyledItemDelegate.NoHint)
            # 表示状態でも最適化
            if table is not None:
                QTimer.singleShot(0, table.resizeRowsToContents)

        editor.setCommitCallback(commit)

        # 入力のたびに行高を更新（ただしデバウンス）
        def schedule_resize():
            if table is None:
                return

            # editor毎にタイマーを持つ（連打を間引く）
            t = self._timers.get(editor)
            if t is None:
                t = QTimer(editor)
                t.setSingleShot(True)
                self._timers[editor] = t

                def do_resize():
                    # editorのviewport幅で折り返し確定
                    width = max(1, editor.viewport().width())
                    text = editor.toPlainText()
                    doc_h = self._calc_doc_height(editor.font(), text, width)
                    min_h = editor.fontMetrics().lineSpacing() * self.min_lines + self.padding
                    desired_h = int(max(min_h, doc_h + self.padding))

                    # ✅ 重要：行高さだけ変更（geometryは触らない）
                    # 結合セルがある場合や他の列の要素で既に十分な高さがある場合は小さくしない
                    current_h = table.rowHeight(row)
                    if desired_h > current_h:
                        table.setRowHeight(row, desired_h)

                t.timeout.connect(do_resize)

            # タイマー再始動（デバウンス）
            t.start(self.debounce_ms)

        # textChangedでもいいが、IMEの確定タイミングで揺れにくいのはdocument側
        editor.document().contentsChanged.connect(schedule_resize)

        # 編集開始直後にも1回（最初の1文字待ち対策）
        QTimer.singleShot(0, schedule_resize)
        return editor

    def setEditorData(self, editor, index):
        value = index.model().data(index, Qt.EditRole) or ""
        editor.setPlainText(value)

        # カーソル末尾
        cursor = editor.textCursor()
        cursor.movePosition(cursor.End)
        editor.setTextCursor(cursor)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.toPlainText(), Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        # editorの配置はQtに任せる（rowHeightが変わればrectも変わる）
        editor.setGeometry(option.rect)
       

class ResultDelegate(QStyledItemDelegate):
    """合否カラム用のデリゲート（編集中のみコンボボックスを表示）"""
    def __init__(self, parent=None):
        super().__init__(parent)
        
    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        combo.addItems(['未実施', 'OK', 'NG'])
        return combo
        
    def setEditorData(self, editor, index):
        value = index.model().data(index, Qt.EditRole)
        editor.setCurrentText(value)
        
    def setModelData(self, editor, model, index):
        value = editor.currentText()
        model.setData(index, value, Qt.EditRole)


class MainWindow(QMainWindow):
    def __init__(self, file_path=None):
        super().__init__()
        self.executor: str = load_executor()
        self.current_theme: str = load_theme()
        self.sheets = []
        self.sheet_views = {}
        
        # 自動保存関連
        self.current_file_path = file_path
        self.auto_save_manager = None
        
        # Undo/Redo スタック
        self.undo_stack = QUndoStack(self)
        self.undo_stack.setUndoLimit(20) # 直近20件まで保持
        self.is_undo_redo = False

        # アップデート確認スレッド
        self._update_thread = None
        self._update_check_manual = False

        self.init_ui()
        self.setup_shortcuts()

        # 起動時の自動アップデートチェック(起動後3秒、非同期)
        if UPDATE_CHECK_ENABLED:
            QTimer.singleShot(3000, self._start_update_check)

    def init_ui(self):
        self.setWindowTitle('検査成績書作成ツール')
        self.setGeometry(100, 100, 1400, 900)
        self.apply_theme()
        self.showMaximized()

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # トップバー
        top_bar = QHBoxLayout()

        self.executor_btn = QPushButton(f'🧑 実行者: {self.executor or "未設定"}')
        self.executor_btn.clicked.connect(self.set_executor)
        top_bar.addWidget(self.executor_btn)

        sheet_btn = QPushButton('📋 シート管理')
        sheet_btn.clicked.connect(self.manage_sheets)
        top_bar.addWidget(sheet_btn)

        theme_btn = QPushButton('🌓 テーマ切替')
        theme_btn.clicked.connect(self.toggle_theme)
        top_bar.addWidget(theme_btn)

        top_bar.addStretch()

        # アップデート確認ボタン
        self.update_btn = QPushButton('🔄 更新確認')
        self.update_btn.setToolTip(
            f'現在のバージョン: v{APP_VERSION}\n最新版をGitHubから確認します')
        self.update_btn.clicked.connect(self.check_for_updates_manual)
        top_bar.addWidget(self.update_btn)

        layout.addLayout(top_bar)

        # シートタブ
        self.tabs = QTabWidget()
        
        # ダッシュボード (最優先)
        self.dashboard = DashboardWidget(self)
        self.tabs.addTab(self.dashboard, 'ダッシュボード')
        
        # 統合ビュー
        self.integrated_view = IntegratedViewWidget(self)
        self.tabs.addTab(self.integrated_view, '統合ビュー')
        
        for sheet in self.sheets:
            view = SheetTabWidget(sheet, self)
            self.sheet_views[sheet] = view
            self.tabs.addTab(view, sheet)

        self.tabs.currentChanged.connect(self.on_tab_changed)

        layout.addWidget(self.tabs)
        
        # ステータスバー
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel('準備完了')
        self.file_label = QLabel('')
        self.save_time_label = QLabel('')
        self.status_bar.addWidget(self.status_label)
        self.status_bar.addPermanentWidget(self.file_label)
        self.status_bar.addPermanentWidget(self.save_time_label)
        
        # ファイルが指定されている場合の処理
        if self.current_file_path:
            self.update_window_title()
            
            # ファイルが存在する場合は読み込み
            if os.path.exists(self.current_file_path):
                self.load_from_file(self.current_file_path)
            
            # データ読み込み後に自動保存を有効化
            self.initialize_auto_save()

    def setup_shortcuts(self):
        """ショートカットキーの設定"""
        # Undo/Redo
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self.undo)
        QShortcut(QKeySequence("Ctrl+Y"), self).activated.connect(self.redo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self).activated.connect(self.redo)

    # -------------------------------------------------------------
    # アップデート確認
    # -------------------------------------------------------------
    def check_for_updates_manual(self):
        """「更新確認」ボタンからの明示的なチェック"""
        self._start_update_check(manual=True)

    def _start_update_check(self, manual=False):
        """GitHub Releases の最新版確認をバックグラウンドで開始する"""
        if self._update_thread is not None and self._update_thread.isRunning():
            if manual:
                QMessageBox.information(self, '更新確認', '現在、更新情報を確認中です。')
            return
        self._update_check_manual = manual
        self._update_thread = UpdateCheckThread(parent=self)
        self._update_thread.finished_check.connect(self._on_update_check_finished)
        self._update_thread.start()
        if manual:
            self.status_label.setText('更新情報を確認中...')

    def _on_update_check_finished(self, result, error):
        """更新チェック完了時の処理(自動時は失敗を通知しない)"""
        manual = self._update_check_manual
        if manual:
            self.status_label.setText('準備完了')

        if error:
            if manual:
                QMessageBox.warning(self, '更新確認', error)
            return

        if not result.get('available'):
            if manual:
                QMessageBox.information(
                    self, '更新確認',
                    f'アプリは最新の状態です。(v{APP_VERSION})')
            return

        self.status_label.setText(
            f"新しいバージョン v{result.get('version', '?')} があります。")
        dialog = UpdateDialog(result, parent=self)
        dialog.exec_()
        
    def mark_as_modified(self, modified=True):
        """変更フラグを設定し、自動保存をスケジュール"""
        if modified:
            if not self.windowTitle().endswith('*'):
                self.setWindowTitle(self.windowTitle() + '*')
            if self.auto_save_manager:
                self.auto_save_manager.schedule_save()
        else:
            if self.windowTitle().endswith('*'):
                self.setWindowTitle(self.windowTitle().rstrip('*'))

    def undo(self):
        if self.undo_stack.canUndo():
            text = self.undo_stack.undoText()
            self.undo_stack.undo()
            self.status_label.setText(f"元に戻しました: {text}")

    def redo(self):
        if self.undo_stack.canRedo():
            text = self.undo_stack.redoText()
            self.undo_stack.redo()
            self.status_label.setText(f"やり直しました: {text}")

    def commit_test_case_change(self, sheet_view, index, old_data, new_data):
        """テストケースのデータ変更をコミット（Undoスタックに積む）"""
        if getattr(self, 'is_undo_redo', False):
            return

        if old_data == new_data:
            return

        command = TestCaseDataCommand(
            sheet_view,
            index,
            old_data,
            new_data,
            f"テストケース編集 #{index + 1}"
        )
        self.undo_stack.push(command)

    def on_tab_changed(self, index):
        """タブ切り替え時の処理"""
        current_widget = self.tabs.widget(index)
        if isinstance(current_widget, IntegratedViewWidget):
            current_widget.refresh()
        elif isinstance(current_widget, DashboardWidget):
            current_widget.refresh()

    # ==== ハンドラ ====
    def update_executor(self, name: str):
        """実施者設定を更新し、永続化する"""
        self.executor = name
        save_executor(name)
        # 必要に応じてUIの表示を更新
        if hasattr(self, 'executor_btn'):
            self.executor_btn.setText(f'🧑 実行者: {self.executor or "未設定"}')
        if hasattr(self, 'integrated_view'):
            self.integrated_view.refresh()

    def set_executor(self):
        dialog = ExecutorDialog(self.executor, self)
        if dialog.exec_():
            new_executor = dialog.get_executor()
            self.update_executor(new_executor)
            QMessageBox.information(self, '成功', f'実行者を "{self.executor or "未設定"}" に設定しました')

    def toggle_theme(self):
        """テーマを切り替える"""
        self.current_theme = 'light' if self.current_theme == 'dark' else 'dark'
        save_theme(self.current_theme)
        self.apply_theme()
        self.integrated_view.refresh()
        self.dashboard.refresh()
        theme_name = 'ライトモード' if self.current_theme == 'light' else 'ダークモード'
        QMessageBox.information(self, 'テーマ変更', f'{theme_name}に切り替えました')

    def apply_theme(self):
        """現在のテーマを適用する"""
        stylesheet = LIGHT_THEME_QSS if self.current_theme == 'light' else DARK_THEME_QSS
        self.setStyleSheet(stylesheet)

    def manage_sheets(self):
        text, ok = QInputDialog.getText(
            self, 'シート名（カンマ区切り）', '例: 機能テスト,UIテスト,パフォーマンス'
        )
        if not ok:
            return
        new_sheets = [s.strip() for s in text.split(',') if s.strip()]
        if not new_sheets:
            QMessageBox.warning(self, '警告', '少なくとも1つのシート名を入力してください')
            return

        # 重複排除 & 既存チェック & バリデーション
        unique_new_sheets = []
        invalid_chars = ['\\', '/', '?', '*', '[', ']', ':']
        
        for s in new_sheets:
            # バリデーション
            if any(char in s for char in invalid_chars):
                QMessageBox.warning(self, '警告', f'シート名 "{s}" には使用できない文字が含まれています。\n使用できない文字: \\ / ? * [ ] :')
                continue
            if len(s) > 31:
                QMessageBox.warning(self, '警告', f'シート名 "{s}" は長すぎます（31文字以内）。')
                continue
                
            if s not in self.sheets and s not in unique_new_sheets:
                unique_new_sheets.append(s)

        if not unique_new_sheets:
            # 追加するものがなければ何もしない（既存にあるものばかりだった場合など）
            return

        # 新しいシートを追加
        for sheet in unique_new_sheets:
            command = SheetCommand(self, 'add', sheet, description=f"シート追加: {sheet}")
            self.undo_stack.push(command)
            
            # 追加したシートに切り替え
            view = self.sheet_views.get(sheet)
            if view:
                self.tabs.setCurrentWidget(view)

    def delete_sheet(self, sheet_name: str):
        """指定されたシートを削除する"""
        if len(self.sheets) <= 1:
            QMessageBox.warning(self, '警告', '最低1つのシートが必要です。最後のシートは削除できません。')
            return

        reply = QMessageBox.question(
            self, '確認', 
            f'シート "{sheet_name}" を削除しますか？\n(含まれる全テストケースも削除されます)',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        view = self.sheet_views.get(sheet_name)
        if view:
            data = view.get_all_data(include_empty=True)
            command = SheetCommand(self, 'remove', sheet_name, data=data, description=f"シート削除: {sheet_name}")
            self.undo_stack.push(command)
            self.mark_as_modified()
        
        # 変更されたことを通知して自動保存を促す
        self.mark_as_modified()
        
        QMessageBox.information(self, '成功', f'シート "{sheet_name}" を削除しました。')

    def export_to_excel(self):
        # 現状の excel_generator.py は executor を引数に取りません（内部で「自動生成」を使用）
        # → ここでは UI の運用上、未設定なら警告だけ出しておきます。
        if not self.executor:
            QMessageBox.warning(self, '警告', '先に実行者を設定してください')
            # それでも出力を続けたいなら return を削ればOK
            return

        file_path, _ = QFileDialog.getSaveFileName(self, 'Excel保存', '', 'Excel Files (*.xlsx)')
        if not file_path:
            return

        try:
            # 現状の ExcelGenerator は「テストケースのリスト」を受け取る実装
            # → 全シートのデータをフラットに集めて渡す
            all_cases = []
            for sheet, view in self.sheet_views.items():
                all_cases.extend(view.get_all_data())

            generator = ExcelGenerator()
            generator.create_excel(all_cases, file_path)  # executor引数は渡さない仕様
            QMessageBox.information(self, '成功', 'Excelファイルを出力しました')
        except Exception as e:
            QMessageBox.critical(self, 'エラー', f'Excel出力中にエラーが発生しました:\n{str(e)}')

    def load_from_excel(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Excel読み込み', '', 'Excel Files (*.xlsx)')
        if not file_path:
            return

        progress = QProgressDialog("Excelファイルを読み込み中...", "キャンセル", 0, 100, self)
        progress.setWindowTitle("読み込み中")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        
        def update_progress(current, total, msg):
            if progress.wasCanceled():
                raise Exception("ユーザーによってキャンセルされました")
            progress.setLabelText(msg)
            progress.setValue(current)
            QApplication.processEvents()

        try:
            generator = ExcelGenerator()
            all_data = generator.load_excel(file_path, progress_callback=update_progress)

            by_sheet = {}
            for d in all_data:
                sheet = d.get('sheet') or 'シート1'
                by_sheet.setdefault(sheet, []).append(d)

            total_cases = len(all_data)
            processed_cases = 0

            for sheet, data_list in by_sheet.items():
                if progress.wasCanceled():
                    break
                update_progress(90 + int((processed_cases / max(1, total_cases)) * 10), 100, f"シート '{sheet}' のUIを構築中...")
                
                if sheet not in self.sheet_views:
                    view = SheetTabWidget(sheet, self)
                    self.sheet_views[sheet] = view
                    self.tabs.addTab(view, sheet)
                    self.sheets.append(sheet)
                
                self.sheet_views[sheet].load_data(data_list)
                processed_cases += len(data_list)
            
            update_progress(100, 100, "完了")
            self.integrated_view.update_sheet_filter()
            self.integrated_view.refresh()
            self.dashboard.refresh()
            QMessageBox.information(self, '成功', 'Excelファイルを読み込みました')
        except Exception as e:
            if str(e) != "ユーザーによってキャンセルされました":
                QMessageBox.critical(self, 'エラー', f'Excel読み込み中にエラーが発生しました:\n{str(e)}')
        finally:
            progress.close()
    
    def load_from_file(self, file_path):
        """ファイルからデータを読み込み（起動時用）"""
        
        progress = QProgressDialog("ファイルを読み込み中...", "キャンセル", 0, 100, self)
        progress.setWindowTitle("読み込み中")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        
        def update_progress(current, total, msg):
            if progress.wasCanceled():
                raise Exception("ユーザーによってキャンセルされました")
            progress.setLabelText(msg)
            progress.setValue(current)
            QApplication.processEvents()
            
        try:
            print(f"[DEBUG] load_from_file started: {file_path}")
            generator = ExcelGenerator()
            all_data = generator.load_excel(file_path, progress_callback=update_progress)
            print(f"[DEBUG] Loaded {len(all_data)} test cases from Excel")
            
            by_sheet = {}
            for d in all_data:
                sheet = d.get('sheet') or 'シート1'
                by_sheet.setdefault(sheet, []).append(d)
            
            print(f"[DEBUG] Data grouped into {len(by_sheet)} sheets: {list(by_sheet.keys())}")
            
            total_cases = len(all_data)
            processed_cases = 0
            
            for sheet, data_list in by_sheet.items():
                if progress.wasCanceled():
                    break
                update_progress(90 + int((processed_cases / max(1, total_cases)) * 10), 100, f"シート '{sheet}' のUIを構築中...")
                print(f"[DEBUG] Processing sheet '{sheet}' with {len(data_list)} test cases")
                
                if sheet not in self.sheet_views:
                    print(f"[DEBUG] Creating new sheet view for '{sheet}'")
                    view = SheetTabWidget(sheet, self)
                    self.sheet_views[sheet] = view
                    self.tabs.addTab(view, sheet)
                    self.sheets.append(sheet)
                else:
                    print(f"[DEBUG] Sheet view '{sheet}' already exists, loading data")
                
                self.sheet_views[sheet].load_data(data_list)
                processed_cases += len(data_list)
                print(f"[DEBUG] Loaded {len(data_list)} test cases into sheet '{sheet}'")
            
            update_progress(100, 100, "完了")
            self.integrated_view.update_sheet_filter()
            self.integrated_view.refresh()
            self.dashboard.refresh()
            self.status_label.setText(f'読み込み完了: {len(all_data)}件')
            print(f"[DEBUG] load_from_file completed successfully")
        except Exception as e:
            if str(e) != "ユーザーによってキャンセルされました":
                import traceback
                error_details = traceback.format_exc()
                print(f"[ERROR] load_from_file failed: {error_details}")
                self.status_label.setText(f'読み込みエラー: {str(e)}')
                QMessageBox.critical(self, 'エラー', f'ファイル読み込み中にエラーが発生しました:\n{str(e)}\n\n詳細:\n{error_details}')
        finally:
            progress.close()
            # 読み込み後はUndoスタックをクリア
            if hasattr(self, 'undo_stack'):
                self.undo_stack.clear()
            self.mark_as_modified(False)
    
    def initialize_auto_save(self):
        """自動保存マネージャを初期化"""
        if not self.current_file_path:
            return
        
        self.auto_save_manager = AutoSaveManager(self.current_file_path, self)
        self.auto_save_manager.save_started.connect(self.on_save_started)
        self.auto_save_manager.save_completed.connect(self.on_save_completed)
        self.auto_save_manager.save_failed.connect(self.on_save_failed)
        
        self.file_label.setText(f'ファイル: {os.path.basename(self.current_file_path)}')
    
    def mark_as_modified_internal(self):
        # このメソッドは重複していたため削除予定ですが、参照がないか確認して置き換えます
        self.mark_as_modified(True)
    
    def update_window_title(self):
        """ウィンドウタイトルを更新"""
        if self.current_file_path:
            file_name = os.path.basename(self.current_file_path)
            self.setWindowTitle(f'検査成績書作成ツール - {file_name}')
        else:
            self.setWindowTitle('検査成績書作成ツール')
    
    def on_save_started(self):
        """保存開始時の処理"""
        self.status_label.setText('保存中...')
    
    def on_save_completed(self, save_time):
        """保存完了時の処理"""
        self.status_label.setText('保存完了')
        self.save_time_label.setText(f'最終保存: {save_time}')
    
    def on_save_failed(self, error_msg):
        """保存失敗時の処理"""
        self.status_label.setText(f'保存エラー: {error_msg}')

    def focus_on_test_case(self, sheet_name, index, highlight=False):
        """Undo/Redo後に指定されたテストケースにフォーカスを当てる"""
        current_widget = self.tabs.currentWidget()
        
        # 統合ビューの場合
        if current_widget == self.integrated_view:
            self.integrated_view.focus_on_test_case(sheet_name, index, highlight=highlight)
            return

        # それ以外（各シートまたはダッシュボード）の場合、該当シートを開いてフォーカス
        if sheet_name in self.sheet_views:
            sheet_view = self.sheet_views[sheet_name]
            if current_widget != sheet_view:
                self.tabs.setCurrentWidget(sheet_view)
            
            if 0 <= index < len(sheet_view.test_cases):
                test_case = sheet_view.test_cases[index]
                from PyQt5.QtCore import QTimer
                # タブ切替直後などはレイアウトが未確定の場合があるため遅延実行
                def do_focus():
                    from PyQt5.QtWidgets import QApplication
                    QApplication.processEvents()
                    sheet_view.scroll_to_test_case(test_case)
                    if highlight and hasattr(test_case, 'highlight_temporarily'):
                        test_case.highlight_temporarily()
                QTimer.singleShot(100, do_focus)


class SheetTabWidget(QWidget):
    def __init__(self, sheet_name: str, main_window: MainWindow):
        super().__init__()
        self.sheet_name = sheet_name
        self.main_window = main_window
        self.test_cases = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 操作ボタン行
        btn_layout = QHBoxLayout()
        
        add_btn = QPushButton('テストケース追加')
        add_btn.clicked.connect(self.add_test_case)
        btn_layout.addWidget(add_btn)
        
        copy_selected_btn = QPushButton('選択したテストケースをコピー')
        copy_selected_btn.clicked.connect(self.copy_selected_test_cases)
        btn_layout.addWidget(copy_selected_btn)
        
        dup_sheet_btn = QPushButton('シートを複製')
        dup_sheet_btn.clicked.connect(self.duplicate_sheet)
        btn_layout.addWidget(dup_sheet_btn)
        
        rename_sheet_btn = QPushButton('シート名変更')
        rename_sheet_btn.clicked.connect(self.rename_sheet)
        btn_layout.addWidget(rename_sheet_btn)
        
        del_sheet_btn = QPushButton('シート削除')
        del_sheet_btn.clicked.connect(self.delete_sheet)
        btn_layout.addWidget(del_sheet_btn)
        
        # 一括折りたたみ/展開ボタン        
        collapse_all_btn = QPushButton('すべて閉じる')
        collapse_all_btn.setToolTip('表示中のすべてのテストケース詳細を閉じます')
        collapse_all_btn.clicked.connect(self.collapse_all)
        btn_layout.addWidget(collapse_all_btn)

        expand_all_btn = QPushButton('すべて開く')
        expand_all_btn.setToolTip('すべてのテストケース詳細を開きます')
        expand_all_btn.clicked.connect(self.expand_all)
        btn_layout.addWidget(expand_all_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.scroll_area = scroll  # スクロールエリアへの参照を保存
        self.test_cases_container = QWidget()
        self.test_cases_layout = QVBoxLayout(self.test_cases_container)
        self.test_cases_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self.test_cases_container)
        layout.addWidget(scroll)

        # 初期1件
        self.add_test_case(push_undo=False)

    def add_test_case(self, data=None, push_undo=True):
        # シグナルからの呼び出し（boolが入る）をガード
        if isinstance(data, bool):
            data = None
            
        if data is None:
            # デフォルトデータ
            data = self.create_empty_test_case_data()
            
        if push_undo:
            command = AddRemoveTestCaseCommand(self, len(self.test_cases), data, True, "テストケース追加")
            self.main_window.undo_stack.push(command)
        else:
            # Undoを介さず直接追加
            test_case = TestCaseWidget(len(self.test_cases) + 1, self.sheet_name, self.main_window, self)
            test_case.load_data(data)
            self.test_cases.append(test_case)
            self.test_cases_layout.addWidget(test_case)
            self.main_window.mark_as_modified()

    def create_empty_test_case_data(self):
        return {
            'number': len(self.test_cases) + 1,
            'item': '',
            'input_condition': '',
            'procedure': '',
            'expected_results': [
                {
                    'expected': '',
                    'result': '未実施',
                    'memo': '',
                    'executor': '',
                    'date': ''
                }
            ],
            'sheet': self.sheet_name,
            'input_images': [],
            'result_images': []
        }

    def remove_test_case(self, test_case: 'TestCaseWidget', push_undo=True):
        if len(self.test_cases) <= 1:
            QMessageBox.warning(self, '警告', '最低1つのテストケースが必要です')
            return
            
        if test_case not in self.test_cases:
            return

        index = self.test_cases.index(test_case)
        data = test_case.get_data(include_empty=True)
        
        if push_undo:
            command = AddRemoveTestCaseCommand(self, index, data, False, f"テストケース削除 #{index+1}")
            self.main_window.undo_stack.push(command)
        else:
            self.test_cases.remove(test_case)
            self.test_cases_layout.removeWidget(test_case)
            test_case.deleteLater()
            self.refresh_order()

    def move_test_case_up(self, test_case: 'TestCaseWidget'):
        index = self.test_cases.index(test_case)
        if index > 0:
            command = MoveTestCaseCommand(self, index, index - 1, f"テストケースを上へ移動 #{index+1}")
            self.main_window.undo_stack.push(command)

    def move_test_case_down(self, test_case: 'TestCaseWidget'):
        index = self.test_cases.index(test_case)
        if index < len(self.test_cases) - 1:
            command = MoveTestCaseCommand(self, index, index + 1, f"テストケースを下へ移動 #{index+1}")
            self.main_window.undo_stack.push(command)

    def move_test_case_to_number(self, test_case: 'TestCaseWidget', target_number: int):
        if not (1 <= target_number <= len(self.test_cases)):
            QMessageBox.warning(self, '警告', f'移動先の番号は 1 から {len(self.test_cases)} の間で指定してください。')
            return
            
        current_index = self.test_cases.index(test_case)
        target_index = target_number - 1
        
        if current_index == target_index:
            return
            
        command = MoveTestCaseCommand(self, current_index, target_index, f"テストケースを #{target_number} へ移動")
        self.main_window.undo_stack.push(command)

    def copy_test_case(self, test_case: 'TestCaseWidget'):
        data = test_case.get_data(include_empty=True)
        self.add_test_case(data)
        self.main_window.integrated_view.refresh()

    def refresh_order(self):
        for test_case in self.test_cases:
            self.test_cases_layout.removeWidget(test_case)
        for i, test_case in enumerate(self.test_cases):
            test_case.update_number(i + 1)
            self.test_cases_layout.addWidget(test_case)
        self.main_window.integrated_view.refresh()
        self.main_window.mark_as_modified()

    def get_all_data(self, include_empty=False):
        return [tc.get_data(include_empty=include_empty) for tc in self.test_cases]

    def duplicate_sheet(self):
        default_name = f"Copy of {self.sheet_name}"
        new_name, ok = QInputDialog.getText(self, 'シート複製', '新しいシート名:', text=default_name)
        if not ok or not new_name.strip():
            return
            
        new_name = new_name.strip()
        
        # バリデーション
        invalid_chars = ['\\', '/', '?', '*', '[', ']', ':']
        if any(char in new_name for char in invalid_chars):
            QMessageBox.warning(self, '警告', f'シート名 "{new_name}" には使用できない文字が含まれています。\n使用できない文字: \\ / ? * [ ] :')
            return
        if len(new_name) > 31:
            QMessageBox.warning(self, '警告', f'シート名 "{new_name}" は長すぎます（31文字以内）。')
            return
        if new_name in self.main_window.sheets:
            QMessageBox.warning(self, '警告', f'シート名 "{new_name}" は既に使用されています。')
            return

        # 新しいシートを作成してデータをコピー
        current_data = self.get_all_data(include_empty=True)
        command = SheetCommand(self.main_window, 'add', new_name, data=current_data, description=f"シート複製: {self.sheet_name} -> {new_name}")
        self.main_window.undo_stack.push(command)
        
        # 新しいシートに切り替え
        new_view = self.main_window.sheet_views.get(new_name)
        if new_view:
            self.main_window.tabs.setCurrentWidget(new_view)
            
        QMessageBox.information(self, '成功', f'シート "{self.sheet_name}" を "{new_name}" として複製しました')

    def rename_sheet(self):
        new_name, ok = QInputDialog.getText(self, 'シート名変更', '新しいシート名:', text=self.sheet_name)
        if not ok or not new_name.strip():
            return
            
        new_name = new_name.strip()
        if new_name == self.sheet_name:
            return

        # バリデーション
        invalid_chars = ['\\', '/', '?', '*', '[', ']', ':']
        if any(char in new_name for char in invalid_chars):
            QMessageBox.warning(self, '警告', f'シート名 "{new_name}" には使用できない文字が含まれています。\n使用できない文字: \\ / ? * [ ] :')
            return
        if len(new_name) > 31:
            QMessageBox.warning(self, '警告', f'シート名 "{new_name}" は長すぎます（31文字以内）。')
            return
        if new_name in self.main_window.sheets:
            QMessageBox.warning(self, '警告', f'シート名 "{new_name}" は既に使用されています。')
            return

        # 名前変更処理
        old_name = self.sheet_name
        command = SheetCommand(self.main_window, 'rename', new_name, old_name=old_name, description=f"シート名変更: {old_name} -> {new_name}")
        self.main_window.undo_stack.push(command)
        self.main_window.mark_as_modified()
        QMessageBox.information(self, '成功', f'シート名を "{old_name}" から "{new_name}" に変更しました')

    def delete_sheet(self):
        """このシートの削除をメインウィンドウに依頼する"""
        self.main_window.delete_sheet(self.sheet_name)

    def copy_selected_test_cases(self):
        selected_cases = [tc for tc in self.test_cases if tc.is_selected()]
        if not selected_cases:
            QMessageBox.warning(self, '警告', 'コピーするテストケースを選択してください')
            return
            
        for tc in selected_cases:
            data = tc.get_data(include_empty=True)
            # コピーなので番号は自動採番されるが、内容はそのまま
            self.add_test_case(data)
            
        self.main_window.integrated_view.refresh()
        QMessageBox.information(self, '成功', f'{len(selected_cases)}件のテストケースをコピーしました')

    def load_data(self, data_list):
        """テストケースデータをロード"""
        # 既存のテストケースをクリア
        for test_case in self.test_cases[:]:
            test_case.prepare_delete()
            self.test_cases_layout.removeWidget(test_case)
            test_case.deleteLater()
        self.test_cases.clear()

        # 新しいデータをロード
        for data in data_list:
            self.add_test_case(data, push_undo=False)
        
        self.main_window.integrated_view.refresh()

    def collapse_all(self):
        """すべてのテストケースを折りたたむ"""
        for test_case in self.test_cases:
            test_case.set_expanded(False)

    def expand_all(self):
        """すべてのテストケースを展開"""
        for test_case in self.test_cases:
            test_case.set_expanded(True)

    def scroll_to_test_case(self, test_case_widget):
        """指定されたテストケースまでスクロール"""
        self.scroll_area.ensureWidgetVisible(test_case_widget, 50, 50)


class IntegratedViewWidget(QWidget):
    def __init__(self, main_window: MainWindow):
        super().__init__()
        self.main_window = main_window
        self.row_to_testcase = {}  # {row_idx: (sheet_name, test_case_widget, expected_result_index)}
        self.editing_in_progress = False  # 編集中フラグ
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel('シート:'))
        self.sheet_filter = QComboBox()
        self.update_sheet_filter()
        self.sheet_filter.currentTextChanged.connect(self.refresh)
        filter_layout.addWidget(self.sheet_filter)

        filter_layout.addWidget(QLabel('合否:'))
        self.result_filter = QComboBox()
        self.result_filter.addItems(['全て', '未実施', 'OK', 'NG'])
        self.result_filter.currentTextChanged.connect(self.refresh)
        filter_layout.addWidget(self.result_filter)
        
        filter_layout.addSpacing(20)
        filter_layout.addWidget(QLabel('🔍 検索:'))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText('項目、手順、期待結果などを検索...')
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self.refresh)
        filter_layout.addWidget(self.search_edit, 1) # 検索バーを伸ばす
        
        jump_btn = QPushButton('選択行に移動')
        jump_btn.clicked.connect(self.jump_to_selected)
        filter_layout.addWidget(jump_btn)
        
        filter_layout.addStretch()

        layout.addLayout(filter_layout)

        # 操作ボタン行
        action_layout = QHBoxLayout()
        
        add_btn = QPushButton('＋ テストケース追加')
        add_btn.clicked.connect(self.add_test_case)
        action_layout.addWidget(add_btn)
        
        copy_btn = QPushButton('コピー')
        copy_btn.clicked.connect(self.copy_test_case)
        action_layout.addWidget(copy_btn)
        
        del_case_btn = QPushButton('テストケース削除')
        del_case_btn.clicked.connect(self.delete_test_case)
        action_layout.addWidget(del_case_btn)
        
        add_result_btn = QPushButton('＋ 期待結果追加')
        add_result_btn.clicked.connect(self.add_expected_result)
        action_layout.addWidget(add_result_btn)
        
        del_result_btn = QPushButton('期待結果削除')
        del_result_btn.clicked.connect(self.delete_expected_result)
        action_layout.addWidget(del_result_btn)
        
        action_layout.addStretch()
        layout.addLayout(action_layout)

        self.table = QTableWidget()
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        # カラム: No, シート, 画像, 項目, 操作手順, 入力条件, 期待結果, 合否, 実施者, 実施日
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(['Ｎｏ', 'シート', '画像', '項目', '操作手順', '入力条件', '期待結果', '合否', '実施者', '実施日'])
        header = self.table.horizontalHeader()
        # ユーザーが列幅を調整できるように Interactive に設定
        header.setSectionResizeMode(QHeaderView.Interactive)
        # 初期幅の設定（適宜調整）
        self.table.setColumnWidth(0, 40)  # No
        self.table.setColumnWidth(1, 100)  # シート
        self.table.setColumnWidth(2, 40)  # 画像
        self.table.setColumnWidth(3, 250) # 項目
        self.table.setColumnWidth(4, 420) # 操作手順
        self.table.setColumnWidth(5, 350) # 入力条件
        self.table.setColumnWidth(6, 400) # 期待結果
        self.table.setColumnWidth(7, 70)  # 合否
        self.table.setColumnWidth(8, 75)  # 実施者
        self.table.setColumnWidth(9, 75)  # 実施日
        # 編集デリゲートを複数列に設定
        multi_delegate = MultiLineTextDelegate(self)
        self.table.setItemDelegateForColumn(3, multi_delegate)  # 項目
        self.table.setItemDelegateForColumn(4, multi_delegate)  # 操作手順
        self.table.setItemDelegateForColumn(5, multi_delegate)  # 入力条件
        self.table.setItemDelegateForColumn(6, multi_delegate)  # 期待結果
        self.table.setItemDelegateForColumn(7, ResultDelegate(self))
        
        # 単一選択モードに設定
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        
        # セル変更時のシグナル接続
        self.table.itemChanged.connect(self.on_cell_changed)
        
        # 画像セル（インデックス2）のダブルクリック処理
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)
        
        # イベントフィルターをインストールして余白ダブルクリックを検知
        self.table.viewport().installEventFilter(self)
        self.table.installEventFilter(self)
        
        # ワードラップを有効化
        self.table.setWordWrap(True)
        
        # 編集トリガーをダブルクリックのみに制限
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        
        layout.addWidget(self.table)

    def eventFilter(self, source, event):
        if source == self.table.viewport() or source == self.table:
            if event.type() == QEvent.MouseButtonDblClick:
                item = self.table.itemAt(event.pos())
                if not item:
                    self.table.clearSelection()
                    return True
            elif event.type() == QEvent.Wheel and (event.modifiers() & Qt.ControlModifier):
                delta = event.angleDelta().y()
                if delta > 0:
                    self.zoom_in()
                elif delta < 0:
                    self.zoom_out()
                return True
        return super().eventFilter(source, event)

    def zoom_in(self):
        if not hasattr(self, 'current_font_size'):
            self.current_font_size = 10
        if self.current_font_size < 36:
            self.current_font_size += 1
            self._apply_zoom()

    def zoom_out(self):
        if not hasattr(self, 'current_font_size'):
            self.current_font_size = 10
        if self.current_font_size > 6:
            self.current_font_size -= 1
            self._apply_zoom()

    def _apply_zoom(self):
        style = f"QTableWidget, QHeaderView::section {{ font-size: {self.current_font_size}pt; }}"
        self.table.setStyleSheet(style)
        self.table.resizeRowsToContents()

    def mouseDoubleClickEvent(self, event):
        self.table.clearSelection()
        super().mouseDoubleClickEvent(event)

    def update_sheet_filter(self):
        current_selection = self.sheet_filter.currentText()
        self.sheet_filter.blockSignals(True)
        self.sheet_filter.clear()
        self.sheet_filter.addItem('全て')
        for sheet in self.main_window.sheets:
            self.sheet_filter.addItem(sheet)
        
        # 選択状態の復元
        index = self.sheet_filter.findText(current_selection)
        if index >= 0:
            self.sheet_filter.setCurrentIndex(index)
        else:
            self.sheet_filter.setCurrentIndex(0)
        self.sheet_filter.blockSignals(False)

    def refresh(self):
        sheet_filter = self.sheet_filter.currentText()
        result_filter = self.result_filter.currentText()
        search_text = self.search_edit.text().lower()
        
        # マッピングをクリア
        self.row_to_testcase.clear()
        
        self.table.clearSpans()
        self.table.clearContents()
        self.table.setRowCount(0)
        
        # 行データの準備
        rows_to_add = []
        spans = []  # (row, col, row_span, col_span)

        current_row = 0
        test_case_index = 0  # テストケースのインデックス（背景色用）
        
        for sheet, view in self.main_window.sheet_views.items():
            if sheet_filter != '全て' and sheet != sheet_filter:
                continue
                
            for test_case in view.test_cases:
                data = test_case.get_data(include_empty=True)
                
                # 期待結果リストを取得
                expected_results = data.get('expected_results', [])
                
                
                # フィルタリング用の総合結果判定
                if expected_results:
                    has_ng = any(r['result'] == 'NG' for r in expected_results)
                    all_ok = all(r['result'] == 'OK' for r in expected_results)
                    if has_ng:
                        overall_result = 'NG'
                    elif all_ok:
                        overall_result = 'OK'
                    else:
                        overall_result = '未実施'
                else:
                    overall_result = data.get('result', '未実施')

                if result_filter != '全て' and overall_result != result_filter:
                    continue

                # 検索キーワードによるフィルタリング
                if search_text:
                    # 検索対象文字列の構築
                    search_targets = [
                        data.get('item', '') or '',
                        data.get('procedure', '') or '',
                        data.get('input_condition', '') or '',
                    ]
                    # 期待結果の内容も追加
                    for r in expected_results:
                        search_targets.append(r.get('expected', '') or '')
                    
                    search_content = " ".join(search_targets).lower()
                    
                    if search_text not in search_content:
                        continue

                # 表示データの構築
                if 'item' in data:
                    item_value = data['item']
                else:
                    item_value = '' 
                
                # 画像の有無を判定
                has_input_img = len(data.get('input_images', [])) > 0
                has_result_img = len(data.get('result_images', [])) > 0
                has_image = '📷' if (has_input_img or has_result_img) else ''
                
                base_info = {
                    'number': str(data['number']),
                    'sheet': data['sheet'],
                    'has_image': has_image,
                    'item': (item_value or ''),
                    'procedure': (data.get('procedure', '') or ''),
                    'input': (data['input_condition'] or ''),
                    'test_case_index': test_case_index  # 背景色用のインデックスを追加
                }


                # このテストケースが占める行数
                row_span = len(expected_results)
                
                # 期待結果が空の場合も1行分は表示する
                if row_span == 0:
                    row_span = 1
                    expected_results = [{'expected': '', 'result': '未実施', 'executor': '', 'date': ''}]
                
                
                # 共通項目の結合設定 (No, シート, 画像, 項目, 操作手順, 入力条件)
                # 列インデックス: 0=No, 1=Sheet, 2=Image, 3=Item, 4=Procedure, 5=Input
                if row_span > 1:
                    spans.append((current_row, 0, row_span, 1))
                    spans.append((current_row, 1, row_span, 1))
                    spans.append((current_row, 2, row_span, 1))
                    spans.append((current_row, 3, row_span, 1))
                    spans.append((current_row, 4, row_span, 1))
                    spans.append((current_row, 5, row_span, 1))

                for i, res in enumerate(expected_results):
                    row_data = base_info.copy() if i == 0 else {} # 2行目以降は共通項目は空
                    
                    # 期待結果ごとのデータ
                    row_data['expected'] = (res.get('expected', '') or '')
                    row_data['result'] = res.get('result', '未実施')
                    row_data['executor'] = res.get('executor', '')
                    row_data['date'] = res.get('date', '')
                    
                    # 背景色用のインデックスを保持
                    if i > 0:
                        row_data['test_case_index'] = test_case_index
                    
                    # テストケースとのマッピングを記録
                    self.row_to_testcase[current_row] = (sheet, test_case, i)
                    
                    rows_to_add.append(row_data)
                    current_row += 1
                
                # テストケースごとにインデックスをインクリメント
                test_case_index += 1

        self.table.setRowCount(len(rows_to_add))
        
        # シグナルを一時的にブロック
        self.table.blockSignals(True)
        
        # テーブルにデータを追加
        for row_idx, row_data in enumerate(rows_to_add):
            # テストケースごとの背景色を決定
            test_case_idx = row_data.get('test_case_index', 0)
            
            is_dark = self.main_window.current_theme == 'dark'
            if test_case_idx % 2 == 0:
                # 偶数行
                if is_dark:
                    base_bg_color = QColor('#121212') # 背景と同じ
                else:
                    base_bg_color = QColor('#FFFFFF')
            else:
                # 奇数行
                if is_dark:
                    base_bg_color = QColor('#252525') # 少し明るく
                else:
                    base_bg_color = QColor('#F5F5F5')
            
            
            # 各セルの設定
            if 'number' in row_data:
                # 0: No
                item = QTableWidgetItem(row_data['number'])
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                item.setBackground(base_bg_color)
                self.table.setItem(row_idx, 0, item)
                
                # 1: Sheet
                item = QTableWidgetItem(row_data['sheet'])
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                item.setBackground(base_bg_color)
                self.table.setItem(row_idx, 1, item)
                
                # 2: Image
                item = QTableWidgetItem(row_data['has_image'])
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                item.setBackground(base_bg_color)
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_idx, 2, item)
                
                # 3: Item
                item = QTableWidgetItem(row_data['item'])
                item.setBackground(base_bg_color)
                self.table.setItem(row_idx, 3, item)
                
                # 4: Procedure
                item = QTableWidgetItem(row_data['procedure'])
                item.setBackground(base_bg_color)
                self.table.setItem(row_idx, 4, item)
                
                # 5: Input
                item = QTableWidgetItem(row_data['input'])
                item.setBackground(base_bg_color)
                self.table.setItem(row_idx, 5, item)
            else:
                # 結合されるセルにも空のアイテムをセット（背景色のため）
                for col in range(6):
                    item = QTableWidgetItem('')
                    item.setBackground(base_bg_color)
                    self.table.setItem(row_idx, col, item)
            
            # 6: Expected
            item = QTableWidgetItem(row_data['expected'])
            item.setBackground(base_bg_color)
            self.table.setItem(row_idx, 6, item)
            
            # 7: Result (Delegate handles editing)
            item = QTableWidgetItem(row_data['result'])
            item.setBackground(base_bg_color)
            if row_data['result'] == 'OK':
                item.setForeground(QBrush(QColor('#00aa00')))
            elif row_data['result'] == 'NG':
                item.setForeground(QBrush(QColor('#dd0000')))
            self.table.setItem(row_idx, 7, item)
            
            # 8: Executor
            item = QTableWidgetItem(row_data['executor'])
            item.setBackground(base_bg_color)
            self.table.setItem(row_idx, 8, item)
            
            # 9: Date
            item = QTableWidgetItem(row_data['date'])
            item.setBackground(base_bg_color)
            self.table.setItem(row_idx, 9, item)

        # セルの結合を適用
        for span in spans:
            self.table.setSpan(span[0], span[1], span[2], span[3])
        # 行の高さを内容に合わせて自動調整
        self.table.resizeRowsToContents()
        self.table.blockSignals(False)

    def on_cell_changed(self, item):
        if self.editing_in_progress:
            return
            
        row = item.row()
        col = item.column()
        
        if row not in self.row_to_testcase:
            return
            
        sheet_name, test_case, result_index = self.row_to_testcase[row]

        self.editing_in_progress = True

        old_testcase_flag = test_case.is_undo_redo
        test_case.is_undo_redo = True

        try:
            value = item.text()
                    
            # カラムに応じた更新処理
            if col == 3: # Item
                test_case.item_edit.setPlainText(value)
            elif col == 4: # Procedure
                test_case.procedure_edit.setPlainText(value)
            elif col == 5: # Input
                test_case.input_edit.setPlainText(value)
            elif col == 6: # Expected
                test_case.expected_results.update_result(result_index, 'expected', value)
            elif col == 7: # Result
                test_case.expected_results.update_result(result_index, 'result', value)
                # 色の更新
                if value == 'OK':
                    item.setForeground(QBrush(QColor('#00aa00')))
                elif value == 'NG':
                    item.setForeground(QBrush(QColor('#dd0000')))
                else:
                    item.setForeground(QBrush(self.table.palette().color(QPalette.Text)))
                
                # OK/NGの場合は実施者・実施日を自動設定
                if value in ['OK', 'NG']:
                    # 実施者の自動設定（まだ設定されていない場合）
                    executor_item = self.table.item(row, 8)
                    if executor_item and not executor_item.text().strip():
                        executor = self.main_window.executor or ''
                        if executor:
                            executor_item.setText(executor)
                            test_case.expected_results.update_result(result_index, 'executor', executor)
                    
                    # 実施日の自動設定（まだ設定されていない場合）
                    date_item = self.table.item(row, 9)
                    if date_item and not date_item.text().strip():
                        today = datetime.now().strftime('%Y/%m/%d')
                        date_item.setText(today)
                        test_case.expected_results.update_result(result_index, 'date', today)
                elif value == '未実施':
                    # 未実施の場合は実施者・実施日をクリア
                    executor_item = self.table.item(row, 8)
                    if executor_item:
                        executor_item.setText('')
                        test_case.expected_results.update_result(result_index, 'executor', '')
                    date_item = self.table.item(row, 9)
                    if date_item:
                        date_item.setText('')
                        test_case.expected_results.update_result(result_index, 'date', '')
            elif col == 8: # Executor
                test_case.expected_results.update_result(result_index, 'executor', value)
            elif col == 9: # Date
                test_case.expected_results.update_result(result_index, 'date', value)

            # 変更を確定してUndoスタックに積む
            # # ここで一度だけUndo登録する
            test_case.is_undo_redo = old_testcase_flag
            test_case.commit_change()

            # commit後は念のため再度抑制状態へ戻す
            test_case.is_undo_redo = True

            self.main_window.mark_as_modified()
            
            # 編集後、テーブル全体の高さを最適化（表示崩れ防止・スパン対応）
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(0, self.table.resizeRowsToContents)

            
        finally:
            test_case.is_undo_redo = old_testcase_flag
            self.editing_in_progress = False


    def on_cell_double_clicked(self, row, col):
        if col == 2:  # 画像列
            item = self.table.item(row, col)
            if item and '📷' in item.text():
                self.show_image_preview(row)

    def show_image_preview(self, row):
        if row not in self.row_to_testcase:
            return
            
        sheet_name, test_case, _ = self.row_to_testcase[row]
        data = test_case.get_data(include_empty=True)
        
        images = []
        titles = []
        
        from PyQt5.QtGui import QPixmap
        import os
        
        # 入力画像
        input_images = data.get('input_images', [])
        for i, img_data in enumerate(input_images):
            pixmap = QPixmap()
            if isinstance(img_data, bytes):
                pixmap.loadFromData(img_data)
            elif isinstance(img_data, str) and os.path.exists(img_data):
                pixmap.load(img_data)
            
            if not pixmap.isNull():
                images.append((pixmap, img_data))
                titles.append(f"入力画像 {i+1}/{len(input_images)}")

        # 結果画像
        result_images = data.get('result_images', [])
        for i, img_data in enumerate(result_images):
            pixmap = QPixmap()
            if isinstance(img_data, bytes):
                pixmap.loadFromData(img_data)
            elif isinstance(img_data, str) and os.path.exists(img_data):
                pixmap.load(img_data)
                
            if not pixmap.isNull():
                images.append((pixmap, img_data))
                titles.append(f"結果画像 {i+1}/{len(result_images)}")

        if images:
            from ui.image_preview_dialog import ImagePreviewDialog
            dialog = ImagePreviewDialog(images, 0, self, titles=titles, test_case=test_case)
            dialog.exec_()
    
    def jump_to_selected(self):
        row = self.table.currentRow()
        if row < 0:
            return

        if row in self.row_to_testcase:
            sheet_name, test_case, _ = self.row_to_testcase[row]

            # タブを切り替え
            if sheet_name in self.main_window.sheet_views:
                view = self.main_window.sheet_views[sheet_name]
                self.main_window.tabs.setCurrentWidget(view)

                # ★重要：タブ切替直後はレイアウト未確定のことがあるので遅延してスクロール
                from PyQt5.QtCore import QTimer
                def do_jump():
                    from PyQt5.QtWidgets import QApplication
                    QApplication.processEvents()
                    view.scroll_to_test_case(test_case)
                QTimer.singleShot(100, do_jump)


    def get_selected_test_case_info(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        return self.row_to_testcase.get(row)

    def focus_on_test_case(self, sheet_name, index, highlight=False):
        """指定されたテストケースにフォーカスを当てる（フィルタで隠れている場合はフィルタを解除）"""
        sheet_view = self.main_window.sheet_views.get(sheet_name)
        if not sheet_view or index >= len(sheet_view.test_cases):
            return
            
        target_test_case = sheet_view.test_cases[index]
        
        def find_target_row():
            for row, info in self.row_to_testcase.items():
                if info[0] == sheet_name and info[1] == target_test_case:
                    return row
            return -1

        target_row = find_target_row()
        
        # フィルタによって隠れている場合は、すべてのフィルタをクリアして再検索
        if target_row == -1:
            self.sheet_filter.blockSignals(True)
            self.result_filter.blockSignals(True)
            self.search_edit.blockSignals(True)
            
            self.sheet_filter.setCurrentText('全て')
            self.result_filter.setCurrentText('全て')
            self.search_edit.setText('')
            
            self.sheet_filter.blockSignals(False)
            self.result_filter.blockSignals(False)
            self.search_edit.blockSignals(False)
            
            self.refresh()
            target_row = find_target_row()
                
        if target_row >= 0:
            item = self.table.item(target_row, 0)
            if item:
                self.table.scrollToItem(item)
                self.table.setCurrentCell(target_row, 0)

    def add_test_case(self):
        sheet_name = self.sheet_filter.currentText()
        if sheet_name == '全て':
            if not self.main_window.sheets:
                QMessageBox.warning(self, '警告', 'シートが存在しません')
                return
            sheet_name, ok = QInputDialog.getItem(self, 'シート選択', '追加するシートを選択してください:', self.main_window.sheets, 0, False)
            if not ok or not sheet_name:
                return
        
        view = self.main_window.sheet_views[sheet_name]
        view.add_test_case()
        self.refresh()
        # 追加された行（最後）を選択状態にするなどのUX向上も考えられるが、
        # refreshで全再描画されるので、とりあえずは更新のみ

    def copy_test_case(self):
        info = self.get_selected_test_case_info()
        if not info:
            QMessageBox.warning(self, '警告', 'コピーする行を選択してください')
            return
        
        sheet_name, test_case, _ = info
        view = self.main_window.sheet_views[sheet_name]
        view.copy_test_case(test_case)
        self.refresh()

    def delete_test_case(self):
        info = self.get_selected_test_case_info()
        if not info:
            QMessageBox.warning(self, '警告', '削除する行を選択してください')
            return
            
        sheet_name, test_case, _ = info
        
        reply = QMessageBox.question(self, '確認', f'テストケース #{test_case.number} を削除してもよろしいですか？', 
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            view = self.main_window.sheet_views[sheet_name]
            view.remove_test_case(test_case)
            self.refresh()

    def delete_expected_result(self):
        info = self.get_selected_test_case_info()
        if not info:
            QMessageBox.warning(self, '警告', '削除する行を選択してください')
            return
            
        sheet_name, test_case, result_index = info
        
        # すべての期待結果行を取得
        all_rows = test_case.expected_results.rows
        
        # 期待結果が1つしかない場合はテストケースごと削除するか確認
        if len(all_rows) <= 1:
            reply = QMessageBox.question(
                self, '確認', 
                f'これは最後の期待結果です。テストケース #{test_case.number} ごと削除しますか？',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                view = self.main_window.sheet_views[sheet_name]
                view.remove_test_case(test_case)
                self.refresh()
            return

        # 選択した位置の期待結果を削除
        if 0 <= result_index < len(all_rows):
            row_widget = all_rows[result_index]
            test_case.expected_results.remove_row(row_widget)
            self.refresh()

    def add_expected_result(self):
        """選択したテストケースに期待結果を追加"""
        info = self.get_selected_test_case_info()
        if not info:
            QMessageBox.warning(self, '警告', '期待結果を追加するテストケースの行を選択してください')
            return
            
        sheet_name, test_case, _ = info
        
        # テストケースに新しい期待結果行を追加
        test_case.expected_results.add_row()
        self.main_window.mark_as_modified()
        self.refresh()

