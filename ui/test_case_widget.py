from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QTextEdit, QPushButton, QComboBox,
                             QFrame, QGridLayout, QMessageBox, QCheckBox, QInputDialog)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
import copy
from datetime import datetime
from ui.image_widget import ImageWidget
from ui.expected_results_widget import ExpectedResultsWidget

class TestCaseWidget(QFrame):
    def __init__(self, number, sheet_name, main_window, parent_sheet):
        super().__init__()
        self.number = number
        self.sheet_name = sheet_name
        self.main_window = main_window
        self.parent_sheet = parent_sheet
        self.execution_date = None
        # スタイル適用のためオブジェクト名を設定
        self.setObjectName("testCaseFrame")
        self.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.setLineWidth(1)
        
        self.commit_timer = QTimer(self)
        self.commit_timer.setSingleShot(True)
        self.commit_timer.setInterval(1000) # 1秒停止で確定
        self.commit_timer.timeout.connect(self.commit_change)
        
        self.init_ui()
        
        # Undo用データ保持
        self.is_undo_redo = False
        self.last_committed_data = self.get_data(include_empty=True)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # ヘッダー行
        header = QHBoxLayout()
        header.setSpacing(6)

        # 選択用チェックボックス
        self.select_checkbox = QCheckBox('選択')
        self.select_checkbox.setToolTip('一括コピーなどの対象として選択します')
        header.addWidget(self.select_checkbox)

        self.number_label = QLabel(f'#{self.number}')
        self.number_label.setMinimumWidth(50)
        self.number_label.setFont(QFont('Arial', 10, QFont.Bold))
        self.number_label.setToolTip('テストケース番号')
        header.addWidget(self.number_label)

        self.summary_display = QLineEdit()
        self.summary_display.setReadOnly(True)
        self.summary_display.setPlaceholderText('項目の概要がここに表示されます')
        self.summary_display.setToolTip('項目に入力した内容の先頭部分を表示します')
        header.addWidget(self.summary_display, 1)

        # 詳細 開閉ボタン
        self.expand_btn = QPushButton('詳細を閉じる')
        self.expand_btn.setObjectName("secondaryBtn")
        self.expand_btn.setToolTip('このテストケースの詳細入力欄を閉じます')
        self.expand_btn.clicked.connect(self.toggle_expand)
        header.addWidget(self.expand_btn)

        # 並び替えボタン
        up_btn = QPushButton('↑ 上へ')
        up_btn.setToolTip('このテストケースを1つ上に移動します')
        up_btn.clicked.connect(lambda: self.parent_sheet.move_test_case_up(self))
        header.addWidget(up_btn)

        down_btn = QPushButton('↓ 下へ')
        down_btn.setToolTip('このテストケースを1つ下に移動します')
        down_btn.clicked.connect(lambda: self.parent_sheet.move_test_case_down(self))
        header.addWidget(down_btn)

        move_to_btn = QPushButton('番号移動')
        move_to_btn.setToolTip('指定した番号の位置へ移動します')
        move_to_btn.clicked.connect(self.prompt_move_to_number)
        header.addWidget(move_to_btn)

        # コピー
        copy_btn = QPushButton('コピー')
        copy_btn.setObjectName("primaryBtn")
        copy_btn.setToolTip('このテストケースをコピーして末尾に追加します')
        copy_btn.clicked.connect(lambda: self.parent_sheet.copy_test_case(self))
        header.addWidget(copy_btn)

        # 削除
        del_btn = QPushButton('削除')
        del_btn.setObjectName("dangerBtn")
        del_btn.setToolTip('このテストケースを削除します')
        del_btn.clicked.connect(self.confirm_remove_self)
        header.addWidget(del_btn)

        layout.addLayout(header)

        # 詳細パネル
        self.detail_panel = QWidget(self)
        self.detail_layout = QVBoxLayout(self.detail_panel)
        self.detail_panel.setVisible(True)

        self.create_detail_panel()
        layout.addWidget(self.detail_panel)

        layout.addStretch()

    def is_selected(self):
        return self.select_checkbox.isChecked()
    
    def create_separator(self):
        """自然な項目区切り線"""
        line = QFrame()
        line.setObjectName("separatorLine")
        line.setFrameShape(QFrame.NoFrame)
        line.setFixedHeight(1)
        return line

    def create_image_container(self):
        """画像エリア用の枠付きコンテナ"""
        frame = QFrame()
        frame.setObjectName("imageContainerFrame")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        image_widget = ImageWidget()
        image_widget.test_case = self # Undo時に再取得するため
        layout.addWidget(image_widget)

        return frame, image_widget

    def create_detail_panel(self):
        layout = self.detail_layout
        grid = QGridLayout()
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        grid.addWidget(QLabel('項目:'), 0, 0)
        self.item_edit = QTextEdit()
        self.item_edit.setMinimumHeight(35)
        self.item_edit.setMaximumHeight(35)
        self.item_edit.setTabChangesFocus(True)
        self.item_edit.textChanged.connect(self.update_item_display)
        grid.addWidget(self.item_edit, 0, 1, 1, 3)
        
        # セパレータ
        grid.addWidget(self.create_separator(), 1, 0, 1, 4)

        grid.addWidget(QLabel('入力条件:'), 2, 0)
        self.input_edit = QTextEdit()
        self.input_edit.setMinimumHeight(150)
        self.input_edit.setMaximumHeight(150)
        self.input_edit.setTabChangesFocus(True)
        grid.addWidget(self.input_edit, 2, 1, 1, 3)

        # セパレータ
        grid.addWidget(self.create_separator(), 3, 0, 1, 4)

        grid.addWidget(QLabel('操作手順:'), 4, 0)
        self.procedure_edit = QTextEdit()
        self.procedure_edit.setMinimumHeight(150)
        self.procedure_edit.setMaximumHeight(150)
        self.procedure_edit.setTabChangesFocus(True)
        grid.addWidget(self.procedure_edit, 4, 1, 1, 3)

        # セパレータ
        grid.addWidget(self.create_separator(), 5, 0, 1, 4)

        grid.addWidget(QLabel('入力画像:'), 6, 0)
        input_image_frame, self.input_images = self.create_image_container()
        grid.addWidget(input_image_frame, 6, 1, 1, 3)

        # セパレータ
        grid.addWidget(self.create_separator(), 7, 0, 1, 4)

        grid.addWidget(QLabel('期待結果と合否:'), 8, 0)
        self.expected_results = ExpectedResultsWidget(self.main_window)
        grid.addWidget(self.expected_results, 8, 1, 1, 3)

        # セパレータ
        grid.addWidget(self.create_separator(), 9, 0, 1, 4)

        grid.addWidget(QLabel('結果画像:'), 10, 0)
        result_image_frame, self.result_images = self.create_image_container()
        grid.addWidget(result_image_frame, 10, 1, 1, 3)

        self.detail_layout.addLayout(grid)
        self.detail_layout.addStretch()
        
        # データ変更通知の接続
        self.item_edit.textChanged.connect(self.on_changed)
        self.input_edit.textChanged.connect(self.on_changed)
        self.procedure_edit.textChanged.connect(self.on_changed)
        self.expected_results.data_changed.connect(self.on_changed)
        self.input_images.images_changed.connect(self.on_changed)
        self.result_images.images_changed.connect(self.on_changed)
    
    def on_changed(self):
        """データが変更されたことを通知"""
        if self.is_undo_redo or getattr(self.main_window, 'is_undo_redo', False):
            return
            
        sender = self.sender()
        # 画像や期待結果の変更は即時確定（1操作 = 1 Undo）
        if sender in [self.expected_results, self.input_images, self.result_images]:
            self.commit_change()
        else:
            # テキスト入力はタイマーでまとめて確定
            self.commit_timer.start()
            
        self.main_window.mark_as_modified()

    def commit_change(self, immediate_data=None):
        """変更を確定してUndoスタックに積む"""
        if self.is_undo_redo or getattr(self.main_window, 'is_undo_redo', False):
            return
        
        new_data = immediate_data if immediate_data else self.get_data(include_empty=True)
        
        # 変更がある場合のみスタックに積む
        if new_data != self.last_committed_data:
            try:
                index = self.parent_sheet.test_cases.index(self)
                self.main_window.commit_test_case_change(
                    self.parent_sheet, index, self.last_committed_data, new_data
                )
                # コマンド側でもセットしているが念のため
                self.last_committed_data = copy.deepcopy(new_data)
            except ValueError:
                pass # 削除済みの場合は無視
        
        self.commit_timer.stop()

    def set_expanded(self, expanded: bool):
        """詳細パネルの開閉状態を一元管理する"""
        self.detail_panel.setVisible(expanded)

        if hasattr(self, 'expand_btn'):
            self.expand_btn.setText('詳細を閉じる' if expanded else '詳細を開く')
            self.expand_btn.setToolTip(
                'このテストケースの詳細入力欄を閉じます'
                if expanded
                else 'このテストケースの詳細入力欄を開きます'
            )

    def toggle_expand(self):
        self.set_expanded(not self.detail_panel.isVisible())

    def highlight_temporarily(self):
        """追加やコピー時に少しの間だけハイライトする"""
        self.setProperty("highlighted", True)
        self.style().unpolish(self)
        self.style().polish(self)
        
        def remove_highlight():
            import sip
            if sip.isdeleted(self):
                return
            self.setProperty("highlighted", False)
            self.style().unpolish(self)
            self.style().polish(self)
            
        QTimer.singleShot(1500, remove_highlight)

    def prompt_move_to_number(self):
        target, ok = QInputDialog.getInt(
            self, '項目移動', '移動先の項目番号を入力してください:', 
            value=self.number, min=1
        )
        if ok and target != self.number:
            self.parent_sheet.move_test_case_to_number(self, target)
    
    def confirm_remove_self(self):
        """テストケース削除前の確認"""
        reply = QMessageBox.question(
            self,
            '確認',
            f'テストケース #{self.number} を削除しますか？',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.parent_sheet.remove_test_case(self)

    # 合否表示は削除したのでこのメソッドは不要
    # def update_result_display_from_expected_results(self):
    #     """期待結果リストから総合的な結果を表示"""
    #     results_data = self.expected_results.get_all_data()
    #     if not results_data:
    #         self.result_display.setText('未実施')
    #         self.result_display.setStyleSheet('color: #999; font-weight: bold;')
    #         return
    #     
    #     # 全てOKならOK、1つでもNGがあればNG、それ以外は未実施
    #     has_ng = any(r['result'] == 'NG' for r in results_data)
    #     has_ok = any(r['result'] == 'OK' for r in results_data)
    #     all_ok = all(r['result'] == 'OK' for r in results_data)
    #     
    #     if has_ng:
    #         result_text = 'NG'
    #         color = '#d00'
    #     elif all_ok:
    #         result_text = 'OK'
    #         color = '#0a0'
    #     else:
    #         result_text = '未実施'
    #         color = '#999'
    #     
    #     self.result_display.setText(result_text)
    #     self.result_display.setStyleSheet(f'color: {color}; font-weight: bold;')

    def update_item_display(self):
        text = self.item_edit.toPlainText()
        preview = text[:50] + ('...' if len(text) > 50 else '')
        self.summary_display.setText(preview)

    def update_number(self, number):
        self.number = number
        self.number_label.setText(f'No.{number}')

    def get_data(self, include_empty=False):
        # 新しいデータ構造: item と expected_results を使用
        return {
            'number': self.number,
            'item': self.item_edit.toPlainText(),
            'input_condition': self.input_edit.toPlainText(),
            'procedure': self.procedure_edit.toPlainText(),
            'expected_results': self.expected_results.get_all_data(include_empty=include_empty),
            'sheet': self.sheet_name,
            'input_images': self.input_images.get_images(),
            'result_images': self.result_images.get_images()
        }

    def load_data(self, data):
        prev_self_flag = self.is_undo_redo
        prev_main_flag = getattr(self.main_window, 'is_undo_redo', False)

        self.is_undo_redo = True
        self.main_window.is_undo_redo = True
        self.commit_timer.stop()

        try:
            # 後方互換性: 旧形式(summary/detail)から新形式(item)への変換
            if 'item' in data:
                item = data.get('item', '')
            else:
                summary = data.get('summary', '')
                detail = data.get('detail', '')

                if summary and detail:
                    item = f"{summary}\n\n{detail}"
                elif summary:
                    item = summary
                elif detail:
                    item = detail
                else:
                    item = ''

            self.item_edit.setPlainText(item)
            self.input_edit.setPlainText(data.get('input_condition', ''))
            self.procedure_edit.setPlainText(data.get('procedure', ''))

            # 期待結果の後方互換性処理
            if 'expected_results' in data:
                self.expected_results.set_all_data(data['expected_results'])
            elif 'expected' in data:
                old_data = [{
                    'expected': data.get('expected', ''),
                    'result': data.get('result', '未実施'),
                    'memo': data.get('result_memo', ''),
                    'executor': data.get('executor', ''),
                    'date': data.get('execution_date', '')
                }]
                self.expected_results.set_all_data(old_data)
            else:
                # expected_results が無い場合も空1行に戻すならこれ
                self.expected_results.set_all_data([])

            # executor/date がトップレベルにあれば最初の期待結果行へ移行
            executor = data.get('executor', '')
            execution_date = data.get('execution_date', '')

            if (executor or execution_date) and self.expected_results.rows:
                first_row = self.expected_results.rows[0]
                current_data = first_row.get_data()

                if not current_data['executor'] and executor:
                    first_row.executor_edit.setText(executor)

                if not current_data['date'] and execution_date:
                    first_row.date_edit.setText(execution_date)

            # 画像
            self.input_images.load_images(data.get('input_images', []))
            self.result_images.load_images(data.get('result_images', []))

            self.update_item_display()

            # ロード直後の状態をUndo/Redo基準にする
            self.last_committed_data = copy.deepcopy(self.get_data(include_empty=True))

        finally:
            self.is_undo_redo = prev_self_flag
            self.main_window.is_undo_redo = prev_main_flag
            self.commit_timer.stop()

    def prepare_delete(self):
        """削除前の後始末"""
        if hasattr(self, 'commit_timer'):
            self.commit_timer.stop()