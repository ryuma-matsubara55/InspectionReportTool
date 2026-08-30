from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QGraphicsView, QGraphicsScene,
                             QGraphicsPixmapItem)
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPixmap, QKeyEvent, QPainter, QKeySequence
from PyQt5.QtWidgets import QShortcut

class ImagePreviewDialog(QDialog):
    """画像を拡大表示するダイアログ"""
    
    def __init__(self, images, current_index=0, parent=None, titles=None, test_case=None):
        """
        Args:
            images: list of (QPixmap, bytes) tuples
            current_index: 現在表示する画像のインデックス
            parent: 親ウィジェット
            titles: list of str (各画像の表示名)
        """
        super().__init__(parent)
        self.images = images
        self.titles = titles
        self.current_index = current_index
        self.zoom_factor = 1.0
        self.pixmap_item = None
        self.test_case = test_case # オプション: Undo時に再取得するため
        
        self.setWindowTitle('画像プレビュー')
        self.resize(1000, 800)
        self.init_ui()
        self.show_current_image()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 画像表示エリア
        self.view = QGraphicsView()
        self.scene = QGraphicsScene()
        self.view.setScene(self.scene)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)

        # マウス位置基準でズームする
        self.view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.view.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        
        # 高品質レンダリング設定
        self.view.setRenderHint(QPainter.Antialiasing, True)
        self.view.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.view.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing, False)
        
        layout.addWidget(self.view)
        
        # コントロールエリア
        control_layout = QHBoxLayout()
        
        # 前へボタン
        self.prev_btn = QPushButton('← 前へ (Left)')
        self.prev_btn.clicked.connect(self.show_previous)
        control_layout.addWidget(self.prev_btn)
        
        # 画像番号表示
        self.index_label = QLabel()
        self.index_label.setAlignment(Qt.AlignCenter)
        control_layout.addWidget(self.index_label)
        
        # 次へボタン
        self.next_btn = QPushButton('次へ → (Right)')
        self.next_btn.clicked.connect(self.show_next)
        control_layout.addWidget(self.next_btn)
        
        # ズームリセット
        reset_btn = QPushButton('ズームリセット (R)')
        reset_btn.clicked.connect(self.reset_zoom)
        control_layout.addWidget(reset_btn)
        
        # 等倍表示
        actual_btn = QPushButton('等倍表示 (1)')
        actual_btn.clicked.connect(self.show_actual_size)
        control_layout.addWidget(actual_btn)

        # 編集ボタン
        self.edit_btn = QPushButton('編集 (E)')
        self.edit_btn.setObjectName("primaryBtn")
        self.edit_btn.clicked.connect(self.edit_current_image)
        control_layout.addWidget(self.edit_btn)

        # 閉じるボタン
        close_btn = QPushButton('閉じる (ESC)')
        close_btn.clicked.connect(self.close)
        control_layout.addWidget(close_btn)
        
        layout.addLayout(control_layout)
        
        # ズーム説明
        help_label = QLabel('マウスホイール: ズームイン/アウト | ドラッグ: 移動')
        help_label.setAlignment(Qt.AlignCenter)
        help_label.setStyleSheet('color: gray; font-size: 10px;')
        layout.addWidget(help_label)
        
        # ショートカット設定
        self.setup_shortcuts()

    def setup_shortcuts(self):
        # Undo
        undo_sc = QShortcut(QKeySequence("Ctrl+Z"), self)
        undo_sc.activated.connect(self.undo_action)
        
        # Redo
        redo_sc1 = QShortcut(QKeySequence("Ctrl+Y"), self)
        redo_sc1.activated.connect(self.redo_action)
        redo_sc2 = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)
        redo_sc2.activated.connect(self.redo_action)

    def undo_action(self):
        main_window = self.get_main_window()
        if main_window:
            main_window.undo()
            self.refresh_from_test_case()
            self.show_current_image()

    def redo_action(self):
        main_window = self.get_main_window()
        if main_window:
            main_window.redo()
            self.refresh_from_test_case()
            self.show_current_image()

    def refresh_from_test_case(self):
        """テストケースから最新の画像を再取得する"""
        if not self.test_case:
            return
            
        # 再取得ロジック（IntegratedViewWidget.show_image_preview と合わせる）
        new_images = []
        new_titles = []
        
        # 入力画像
        for i, (pixmap, data) in enumerate(self.test_case.input_images.images):
            new_images.append((pixmap, data))
            new_titles.append(f"入力画像 {i+1}/{len(self.test_case.input_images.images)}")
            
        # 結果画像
        for i, (pixmap, data) in enumerate(self.test_case.result_images.images):
            new_images.append((pixmap, data))
            new_titles.append(f"結果画像 {i+1}/{len(self.test_case.result_images.images)}")
            
        self.images = new_images
        self.titles = new_titles

    def get_main_window(self):
        """MainWindowのインスタンスを探索"""
        curr = self.parent()
        while curr:
            from ui.main_window import MainWindow
            if isinstance(curr, MainWindow):
                return curr
            curr = curr.parent()
        return None
        
    def show_current_image(self):
        """現在のインデックスの画像を表示"""
        if not self.images:
            self.scene.clear()
            self.index_label.setText("画像がありません")
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            return

        # インデックスの範囲外チェックと補正
        if self.current_index < 0:
            self.current_index = 0
        elif self.current_index >= len(self.images):
            self.current_index = len(self.images) - 1

        self.scene.clear()

        pixmap, _ = self.images[self.current_index]

        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.pixmap_item.setTransformationMode(Qt.SmoothTransformation)
        self.scene.addItem(self.pixmap_item)
        self.scene.setSceneRect(QRectF(pixmap.rect()))

        self.fit_image_without_upscale()

        title_str = ""
        if getattr(self, 'titles', None) and self.current_index < len(self.titles):
            title_str = f"{self.titles[self.current_index]} - "

        self.index_label.setText(
            f'{title_str}{self.current_index + 1} / {len(self.images)} '
            f'({pixmap.width()} x {pixmap.height()} px)'
        )

        self.prev_btn.setEnabled(self.current_index > 0)
        self.next_btn.setEnabled(self.current_index < len(self.images) - 1)
    
    def show_previous(self):
        """前の画像を表示"""
        if self.current_index > 0:
            self.current_index -= 1
            self.show_current_image()
            
    def show_next(self):
        """次の画像を表示"""
        if self.current_index < len(self.images) - 1:
            self.current_index += 1
            self.show_current_image()
    
    def fit_image_without_upscale(self):
        """
        画像を表示領域に合わせる。
        ただし、元画像より大きくは拡大しない。
        """
        if not self.pixmap_item:
            return

        self.view.resetTransform()

        scene_rect = self.scene.sceneRect()
        viewport_rect = self.view.viewport().rect()

        if scene_rect.isEmpty() or viewport_rect.isEmpty():
            return

        scale_x = viewport_rect.width() / scene_rect.width()
        scale_y = viewport_rect.height() / scene_rect.height()
        scale = min(scale_x, scale_y)

        # 重要：1.0を超える場合は拡大しない
        scale = min(scale, 1.0)

        self.view.scale(scale, scale)
        self.zoom_factor = scale
        self.view.centerOn(self.pixmap_item)

    def reset_zoom(self):
        """画面に合わせる。ただし元画像より拡大しない"""
        self.fit_image_without_upscale()

    def show_actual_size(self):
        """画像を等倍表示する"""
        if not self.pixmap_item:
            return

        self.view.resetTransform()
        self.zoom_factor = 1.0
        self.view.centerOn(self.pixmap_item)

    def edit_current_image(self):
        """現在の画像を編集ダイアログで開く"""
        if not self.images or self.current_index < 0 or self.current_index >= len(self.images):
            return
            
        from ui.image_editor_dialog import ImageEditorDialog
        pixmap, _ = self.images[self.current_index]
        
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
            
            # リスト（参照）を更新
            self.images[self.current_index] = (new_pixmap, bytes(byte_array))
            
            # 親（ImageWidget）に通知
            if hasattr(self.parent(), 'images_changed'):
                self.parent().update_preview()
                self.parent().images_changed.emit()
            
            # プレビューを再表示
            self.show_current_image()
    
    def keyPressEvent(self, event: QKeyEvent):
        """キーボードイベント処理"""
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.key() == Qt.Key_Left:
            self.show_previous()
        elif event.key() == Qt.Key_Right:
            self.show_next()
        elif event.key() == Qt.Key_R:
            self.reset_zoom()
        elif event.key() == Qt.Key_1:
            self.show_actual_size()
        elif event.key() == Qt.Key_E:
            self.edit_current_image()
        else:
            super().keyPressEvent(event)
            
    def wheelEvent(self, event):
        """マウスホイールでズーム"""
        if not self.pixmap_item:
            return

        delta = event.angleDelta().y()
        scale_factor = 1.25 if delta > 0 else 0.8

        new_zoom = self.zoom_factor * scale_factor

        if new_zoom < 0.05:
            scale_factor = 0.05 / self.zoom_factor
            self.zoom_factor = 0.05
        elif new_zoom > 8.0:
            scale_factor = 8.0 / self.zoom_factor
            self.zoom_factor = 8.0
        else:
            self.zoom_factor = new_zoom

        self.view.scale(scale_factor, scale_factor)