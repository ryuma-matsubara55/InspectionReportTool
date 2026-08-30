from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QTextEdit, QComboBox, QLineEdit, QFrame, QDialog)
from PyQt5.QtCore import Qt, pyqtSignal, QSignalBlocker
from datetime import datetime

class DoubleClickLineEdit(QLineEdit):
    """ダブルクリックされたときにシグナルを発火するQLineEdit"""
    doubleClicked = pyqtSignal()

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        self.doubleClicked.emit()


class MemoEditDialog(QDialog):
    """メモを大きな画面で編集・閲覧するためのダイアログ"""
    def __init__(self, parent=None, text=""):
        super().__init__(parent)
        self.setWindowTitle("メモの編集・閲覧")
        self.resize(500, 350)
        self.init_ui(text)

    def init_ui(self, text):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # ラベル
        label = QLabel("メモを入力してください（改行も可能です）:")
        label.setStyleSheet("font-weight: bold;")
        layout.addWidget(label)

        # テキストエディタ
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(text)
        self.text_edit.setPlaceholderText("メモを入力...")
        layout.addWidget(self.text_edit)

        # ボタン
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        cancel_btn = QPushButton("キャンセル")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("決定")
        ok_btn.setObjectName("primaryBtn")
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)

        layout.addLayout(btn_layout)

    def get_text(self):
        return self.text_edit.toPlainText().strip()


class DoubleClickComboBox(QComboBox):
    """ダブルクリックでのみポップアップが開くコンボボックス"""
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def mousePressEvent(self, event):
        # シングルクリックを無視（編集開始しない）
        pass

    def mouseDoubleClickEvent(self, event):
        # ダブルクリックでポップアップを表示
        self.showPopup()

class ExpectedResultRow(QFrame):
    """期待結果と合否のペアを表す1行のウィジェット"""
    def __init__(self, parent_widget, index=0):
        super().__init__()
        self.setObjectName("expectedResultRow")
        self.parent_widget = parent_widget
        self.index = index
        self.memo_full_text = ""  # 改行を含むフルテキスト保持用
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # 期待結果入力
        self.expected_edit = QTextEdit()
        self.expected_edit.setMinimumHeight(50)
        self.expected_edit.setMaximumHeight(50)
        self.expected_edit.setPlaceholderText('期待結果')
        self.expected_edit.setTabChangesFocus(True)
        self.expected_edit.textChanged.connect(self.on_changed)
        layout.addWidget(self.expected_edit, 3)

        # 合否コンボボックス
        self.result_combo = DoubleClickComboBox()
        self.result_combo.addItems(['未実施', 'OK', 'NG'])
        self.result_combo.setFixedWidth(80)
        self.result_combo.currentTextChanged.connect(self.on_changed)
        layout.addWidget(self.result_combo)

        # メモ入力と拡大ボタンのコンテナ
        memo_container = QHBoxLayout()
        memo_container.setContentsMargins(0, 0, 0, 0)
        memo_container.setSpacing(2)

        self.memo_edit = DoubleClickLineEdit()
        self.memo_edit.setPlaceholderText('メモ')
        self.memo_edit.setFixedWidth(120)
        self.memo_edit.textChanged.connect(self.on_changed)
        self.memo_edit.doubleClicked.connect(self.open_memo_dialog)
        memo_container.addWidget(self.memo_edit)

        self.memo_expand_btn = QPushButton('⛶')
        self.memo_expand_btn.setFixedSize(24, 24)
        self.memo_expand_btn.setStyleSheet("padding: 0px; font-size: 10px; font-weight: bold;")
        self.memo_expand_btn.setToolTip('メモを大きく表示・編集 (ダブルクリックでも可)')
        self.memo_expand_btn.clicked.connect(self.open_memo_dialog)
        memo_container.addWidget(self.memo_expand_btn)

        layout.addLayout(memo_container, 1)

        # 実施者入力
        self.executor_edit = QLineEdit()
        self.executor_edit.setPlaceholderText('実施者')
        self.executor_edit.setFixedWidth(80)
        self.executor_edit.textChanged.connect(self.on_changed)
        layout.addWidget(self.executor_edit)

        # 実施日入力
        self.date_edit = QLineEdit()
        self.date_edit.setPlaceholderText('実施日')
        self.date_edit.setFixedWidth(80)
        self.date_edit.textChanged.connect(self.on_changed)
        layout.addWidget(self.date_edit)

        # 削除ボタン
        del_btn = QPushButton('×')
        del_btn.setFixedWidth(30)
        del_btn.setObjectName("dangerBtn")
        del_btn.clicked.connect(self.remove_self)
        layout.addWidget(del_btn)

        # 上へボタン
        up_btn = QPushButton('↑')
        up_btn.setFixedSize(24, 24)
        up_btn.setStyleSheet("padding: 0px;")
        up_btn.setToolTip('上へ移動')
        up_btn.clicked.connect(self.move_up)
        layout.addWidget(up_btn)

        # 下へボタン
        down_btn = QPushButton('↓')
        down_btn.setFixedSize(24, 24)
        down_btn.setStyleSheet("padding: 0px;")
        down_btn.setToolTip('下へ移動')
        down_btn.clicked.connect(self.move_down)
        layout.addWidget(down_btn)

        self.setFrameStyle(QFrame.StyledPanel)
    
    
    def on_changed(self):
        """データが変更されたことを親に通知"""
        sender = self.sender()

        # 直接メモ欄が編集された場合、フルテキスト変数を更新する
        if sender == self.memo_edit:
            self.memo_full_text = self.memo_edit.text().strip()

        # 実施者が手動で変更された場合、グローバル設定を更新して保存する
        if sender == self.executor_edit:
            new_executor = self.executor_edit.text().strip()
            # 空文字の場合は、グローバルな「デフォルト実施者」をリセットしないようにする
            if not new_executor:
                return
                
            main_window = getattr(self.parent_widget, 'main_window', None)
            if main_window and hasattr(main_window, 'update_executor'):
                # 現在のグローバル設定と異なる場合のみ更新（再帰防止のため）
                if new_executor != getattr(main_window, 'executor', None):
                    main_window.update_executor(new_executor)

        if sender == self.result_combo:
            result = self.result_combo.currentText()
            if result in ['OK', 'NG']:
                # 実施者の自動入力
                if not self.executor_edit.text().strip():
                    main_window = getattr(self.parent_widget, 'main_window', None)
                    if main_window and getattr(main_window, 'executor', None):
                        with QSignalBlocker(self.executor_edit):
                            self.executor_edit.setText(main_window.executor)

                # 実施日の自動入力
                if not self.date_edit.text().strip():
                    today = datetime.now().strftime('%Y/%m/%d')
                    with QSignalBlocker(self.date_edit):
                        self.date_edit.setText(today)

            elif result == '未実施':
                with QSignalBlocker(self.executor_edit):
                    self.executor_edit.clear()
                with QSignalBlocker(self.date_edit):
                    self.date_edit.clear()

        self.parent_widget.on_row_changed()

    def remove_self(self):
        """この行を削除"""
        self.parent_widget.remove_row(self)

    def move_up(self):
        self.parent_widget.move_row_up(self)

    def move_down(self):
        self.parent_widget.move_row_down(self)

    def open_memo_dialog(self):
        """メモ編集ダイアログを開く"""
        dialog = MemoEditDialog(self, getattr(self, 'memo_full_text', ''))
        if dialog.exec_() == MemoEditDialog.Accepted:
            new_text = dialog.get_text()
            self.memo_full_text = new_text
            with QSignalBlocker(self.memo_edit):
                self.memo_edit.setText(new_text.replace('\n', ' '))
            self.on_changed()

    def get_data(self):
        """この行のデータを取得"""
        return {
            'expected': self.expected_edit.toPlainText().strip(),
            'result': self.result_combo.currentText(),
            'memo': getattr(self, 'memo_full_text', self.memo_edit.text().strip()),
            'executor': self.executor_edit.text().strip(),
            'date': self.date_edit.text().strip()
        }

    def set_data(self, data):
        """この行にデータを設定（ロード中は信号を出さない）"""
        self.memo_full_text = data.get('memo', '')
        with QSignalBlocker(self.expected_edit):
            self.expected_edit.setPlainText(data.get('expected', ''))
        with QSignalBlocker(self.result_combo):
            self.result_combo.setCurrentText(data.get('result', '未実施'))
        with QSignalBlocker(self.memo_edit):
            self.memo_edit.setText(self.memo_full_text.replace('\n', ' '))
        with QSignalBlocker(self.executor_edit):
            self.executor_edit.setText(data.get('executor', ''))
        with QSignalBlocker(self.date_edit):
            self.date_edit.setText(data.get('date', ''))


class ExpectedResultsWidget(QWidget):
    """複数の期待結果と合否のペアを管理するウィジェット"""
    data_changed = pyqtSignal()
    
    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.rows = []
        self.init_ui()
        # 初期値として1行追加
        self.add_row()

    def init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        # 行のコンテナ
        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setAlignment(Qt.AlignTop)
        self.main_layout.addWidget(self.rows_container)

        # 追加ボタン
        add_btn = QPushButton('+ 期待結果を追加')
        add_btn.setObjectName("primaryBtn")
        add_btn.clicked.connect(self.add_row)
        self.main_layout.addWidget(add_btn)

    
    def add_row(self, data=None):
        """新しい期待結果行を追加"""
        if isinstance(data, bool):
            data = None
            
        row = ExpectedResultRow(self, len(self.rows))
        if data:
            row.set_data(data)
        self.rows.append(row)
        self.rows_layout.addWidget(row)
        self.data_changed.emit()

    def remove_row(self, row):
        """指定された行を削除"""
        if len(self.rows) <= 1:
            # 最低1行は残す
            return
        self.rows.remove(row)
        self.rows_layout.removeWidget(row)
        row.deleteLater()
        # インデックスを再計算
        for i, r in enumerate(self.rows):
            r.index = i
        self.data_changed.emit()

    def move_row_up(self, row):
        idx = self.rows.index(row)
        if idx > 0:
            self.rows.pop(idx)
            self.rows.insert(idx - 1, row)
            self._rebuild_layout()
            self.data_changed.emit()

    def move_row_down(self, row):
        idx = self.rows.index(row)
        if idx < len(self.rows) - 1:
            self.rows.pop(idx)
            self.rows.insert(idx + 1, row)
            self._rebuild_layout()
            self.data_changed.emit()

    def _rebuild_layout(self):
        with QSignalBlocker(self):
            for r in self.rows:
                self.rows_layout.removeWidget(r)
            for i, r in enumerate(self.rows):
                r.index = i
                self.rows_layout.addWidget(r)
    
    def on_row_changed(self):
        """行のデータが変更されたときに呼ばれる"""
        self.data_changed.emit()

    def get_all_data(self, include_empty=False):
        """全ての期待結果データを取得"""
        if include_empty:
            return [row.get_data() for row in self.rows]
        return [row.get_data() for row in self.rows if row.get_data()['expected']]

    
    def set_all_data(self, data_list):
        """全ての期待結果データを設定（再構築中は信号停止）"""
        with QSignalBlocker(self):
            # 既存の行をクリア
            for row in self.rows[:]:
                self.rows_layout.removeWidget(row)
                row.deleteLater()
            self.rows.clear()

            # 新しいデータで行を作成
            if data_list:
                for data in data_list:
                    # add_row 内で emit しないようにするなら、ここだけ手動で作ってもOK
                    row = ExpectedResultRow(self, len(self.rows))
                    row.set_data(data)
                    self.rows.append(row)
                    self.rows_layout.addWidget(row)
            else:
                # データがない場合は1行追加
                row = ExpectedResultRow(self, 0)
                self.rows.append(row)
                self.rows_layout.addWidget(row)

        # 再構築完了後に一回だけ通知
        self.data_changed.emit()

        
    def update_result(self, index, key, value):
        """
        指定 index の行を更新（indexは self.rows の絶対index）
        足りない場合は自動で行追加して整合を取る
        """
        # 行が足りなければ追加
        while len(self.rows) <= index:
            row = ExpectedResultRow(self, len(self.rows))
            self.rows.append(row)
            self.rows_layout.addWidget(row)

        row = self.rows[index]

        # ロード・反映中の多重通知を避ける
        if key == 'expected':
            with QSignalBlocker(row.expected_edit):
                row.expected_edit.setPlainText(value)
        elif key == 'result':
            with QSignalBlocker(row.result_combo):
                row.result_combo.setCurrentText(value)
        elif key == 'memo':
            row.memo_full_text = value
            with QSignalBlocker(row.memo_edit):
                row.memo_edit.setText(value.replace('\n', ' '))
        elif key == 'executor':
            with QSignalBlocker(row.executor_edit):
                row.executor_edit.setText(value)
        elif key == 'date':
            with QSignalBlocker(row.date_edit):
                row.date_edit.setText(value)

        self.data_changed.emit()
        return row.get_data()

