from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QFileDialog, QScrollArea, QGridLayout, QFrame)
from PyQt5.QtCore import Qt, QByteArray, QBuffer, QIODevice, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage, QImageReader
from PIL import Image
import io

class ClickableLabel(QLabel):
    """クリック可能なQLabel"""
    clicked = pyqtSignal(int)
    
    def __init__(self, index=0):
        super().__init__()
        self._index = index
        
    def mousePressEvent(self, event):
        import sip
        if sip.isdeleted(self):
            return
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._index)
        try:
            super().mousePressEvent(event)
        except RuntimeError:
            pass # すでに削除されている場合は無視


class ImageWidget(QWidget):
    images_changed = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.images = []  # [(QPixmap, bytes), ...]
        self.thumbnail_size = 240  # サムネイル表示サイズ
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # ボタンエリア
        btn_layout = QHBoxLayout()

        add_btn = QPushButton('画像追加')
        add_btn.clicked.connect(self.add_image_from_file)
        btn_layout.addWidget(add_btn)

        paste_btn = QPushButton('クリップボードから貼り付け')
        paste_btn.clicked.connect(self.paste_from_clipboard)
        btn_layout.addWidget(paste_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 画像プレビューエリア
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(320)

        self.preview_widget = QWidget()
        self.preview_layout = QGridLayout(self.preview_widget)
        self.preview_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        scroll.setWidget(self.preview_widget)
        layout.addWidget(scroll)

    def add_image_from_file(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            '画像選択',
            '',
            'Images (*.png *.jpg *.jpeg *.bmp)'
        )

        for file_path in file_paths:
            reader = QImageReader(file_path)
            reader.setAutoTransform(True)  # JPEGの回転情報などを反映
            image = reader.read()

            if image.isNull():
                continue

            pixmap = QPixmap.fromImage(image)

            # 元画像をPNGバイトとして保持
            byte_array = QByteArray()
            buffer = QBuffer(byte_array)
            buffer.open(QIODevice.WriteOnly)
            pixmap.save(buffer, 'PNG', 100)
            buffer.close()

            self.images.append((pixmap, bytes(byte_array)))
        
        if file_paths:
            self.update_preview()
            self.images_changed.emit()

    def paste_from_clipboard(self):
        from PyQt5.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()

        if mime_data.hasImage():
            image = clipboard.image()

            if image.isNull():
                return

            pixmap = QPixmap.fromImage(image)

            byte_array = QByteArray()
            buffer = QBuffer(byte_array)
            buffer.open(QIODevice.WriteOnly)
            pixmap.save(buffer, 'PNG', 100)
            buffer.close()

            self.images.append((pixmap, bytes(byte_array)))
            self.update_preview()
            self.images_changed.emit()

    def update_preview(self):
        # 既存のプレビューをクリア
        for i in reversed(range(self.preview_layout.count())):
            widget = self.preview_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # プレビュー再描画
        for i, (pixmap, _) in enumerate(self.images):
            frame = QFrame()
            frame.setObjectName("imagePreviewFrame")
            frame.setFrameStyle(QFrame.Box)

            frame_layout = QVBoxLayout(frame)
            frame_layout.setContentsMargins(8, 8, 8, 8)
            frame_layout.setSpacing(6)

            # サムネイル
            label = ClickableLabel(i)
            label.setMinimumSize(self.thumbnail_size, self.thumbnail_size)
            label.setAlignment(Qt.AlignCenter)
            label.setCursor(Qt.PointingHandCursor)
            label.setScaledContents(False)

            scaled_pixmap = pixmap.scaled(
                self.thumbnail_size,
                self.thumbnail_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            label.setPixmap(scaled_pixmap)

            # clicked は int を渡すので、lambda 側でも受ける
            label.clicked.connect(self.show_image_preview)

            frame_layout.addWidget(label)

            edit_btn = QPushButton('編集')
            edit_btn.clicked.connect(lambda checked=False, idx=i: self.edit_image(idx))
            frame_layout.addWidget(edit_btn)

            delete_btn = QPushButton('削除')
            delete_btn.clicked.connect(lambda checked=False, idx=i: self.remove_image(idx))
            frame_layout.addWidget(delete_btn)

            move_layout = QHBoxLayout()
            left_btn = QPushButton('◀')
            left_btn.setToolTip('左へ移動')
            left_btn.clicked.connect(lambda checked=False, idx=i: self.move_image_left(idx))
            if i == 0:
                left_btn.setEnabled(False)
            move_layout.addWidget(left_btn)

            right_btn = QPushButton('▶')
            right_btn.setToolTip('右へ移動')
            right_btn.clicked.connect(lambda checked=False, idx=i: self.move_image_right(idx))
            if i == len(self.images) - 1:
                right_btn.setEnabled(False)
            move_layout.addWidget(right_btn)
            
            frame_layout.addLayout(move_layout)

            row = i // 3
            col = i % 3
            self.preview_layout.addWidget(frame, row, col)

    def remove_image(self, index):
        if 0 <= index < len(self.images):
            self.images.pop(index)
            self.update_preview()
            self.images_changed.emit()

    def move_image_left(self, index):
        if index > 0:
            img = self.images.pop(index)
            self.images.insert(index - 1, img)
            self.update_preview()
            self.images_changed.emit()

    def move_image_right(self, index):
        if index < len(self.images) - 1:
            img = self.images.pop(index)
            self.images.insert(index + 1, img)
            self.update_preview()
            self.images_changed.emit()

    def edit_image(self, index):
        """画像編集ダイアログを開く"""
        if not (0 <= index < len(self.images)):
            return
            
        from ui.image_editor_dialog import ImageEditorDialog
        pixmap, _ = self.images[index]
        
        dialog = ImageEditorDialog(pixmap, self)
        if dialog.exec_():
            new_pixmap = dialog.get_edited_pixmap()
            
            # PNGバイトとして保存
            from PyQt5.QtCore import QByteArray, QBuffer, QIODevice
            byte_array = QByteArray()
            buffer = QBuffer(byte_array)
            buffer.open(QIODevice.WriteOnly)
            new_pixmap.save(buffer, 'PNG', 100)
            buffer.close()
            
            self.images[index] = (new_pixmap, bytes(byte_array))
            self.update_preview()
            self.images_changed.emit()

    def get_images(self):
        """バイトデータのリストを返す"""
        return [img_bytes for _, img_bytes in self.images]

    def load_images(self, image_bytes_list):
        """バイトデータから画像を読み込む"""
        self.images.clear()

        for img_bytes in image_bytes_list:
            pixmap = QPixmap()
            pixmap.loadFromData(img_bytes)

            if not pixmap.isNull():
                self.images.append((pixmap, bytes(img_bytes)))

        self.update_preview()

    def show_image_preview(self, index):
        """画像プレビューダイアログを表示"""
        from ui.image_preview_dialog import ImagePreviewDialog
        
        if self.images:
            dialog = ImagePreviewDialog(self.images, index, self, test_case=getattr(self, 'test_case', None))
            dialog.exec_()
