import math
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, 
                             QGraphicsLineItem, QGraphicsRectItem, QGraphicsTextItem,
                             QColorDialog, QComboBox, QLabel, QInputDialog, QGraphicsItem,
                             QButtonGroup, QUndoStack, QUndoCommand, QShortcut)
from PyQt5.QtCore import Qt, QPointF, QLineF, QRectF
from PyQt5.QtGui import QPixmap, QColor, QPen, QFont, QPainter, QBrush, QPolygonF, QKeySequence

class ArrowItem(QGraphicsLineItem):
    def __init__(self, start_pos, end_pos, color, width):
        super().__init__(QLineF(start_pos, end_pos))
        self.color = color
        self.width = width
        self.setPen(QPen(color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable)

    def paint(self, painter, option, widget=None):
        line = self.line()
        if line.length() < 1:
            return

        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(self.pen())
        painter.drawLine(line)

        # 矢印の頭を計算
        angle = math.atan2(-line.dy(), line.dx())
        arrow_size = self.width * 4
        
        # 矢印の先端
        p2 = line.p2()
        
        # 二つの羽の点
        arrow_p1 = p2 - QPointF(math.cos(angle - math.pi / 6) * arrow_size,
                               -math.sin(angle - math.pi / 6) * arrow_size)
        arrow_p2 = p2 - QPointF(math.cos(angle + math.pi / 6) * arrow_size,
                               -math.sin(angle + math.pi / 6) * arrow_size)

        painter.setBrush(QBrush(self.color))
        painter.drawPolygon(QPolygonF([p2, arrow_p1, arrow_p2]))

class AddItemCommand(QUndoCommand):
    def __init__(self, scene, item, description):
        super().__init__(description)
        self.scene = scene
        self.item = item

    def redo(self):
        self.scene.addItem(self.item)

    def undo(self):
        self.scene.removeItem(self.item)

class MoveItemCommand(QUndoCommand):
    def __init__(self, item, old_pos, new_pos, description):
        super().__init__(description)
        self.item = item
        self.old_pos = old_pos
        self.new_pos = new_pos

    def redo(self):
        self.item.setPos(self.new_pos)

    def undo(self):
        self.item.setPos(self.old_pos)

class ImageEditorDialog(QDialog):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("画像編集")
        self.resize(1100, 850)
        
        self.original_pixmap = pixmap
        self.current_tool = "arrow" # select, arrow, rect, text
        self.current_color = QColor(Qt.red)
        self.current_width = 3
        
        self.start_point = None
        self.temp_item = None
        
        # 内部Undoスタック
        self.undo_stack = QUndoStack(self)
        
        self.init_ui()
        self.setup_shortcuts()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # ツールバー
        toolbar = QHBoxLayout()
        
        self.tool_group = QButtonGroup(self)
        
        tools = [
            ("select", "🖱️ 選択・移動"),
            ("arrow", "↗️ 矢印"),
            ("rect", "⬜ 枠線"),
            ("text", "Text テキスト")
        ]
        
        self.tool_buttons = {}
        for tool_id, label in tools:
            btn = QPushButton(label)
            btn.setCheckable(True)
            if tool_id == self.current_tool:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, t=tool_id: self.set_tool(t))
            self.tool_group.addButton(btn)
            self.tool_buttons[tool_id] = btn
            toolbar.addWidget(btn)
            
        toolbar.addSpacing(20)
        
        color_btn = QPushButton("🎨 色選択")
        color_btn.clicked.connect(self.choose_color)
        toolbar.addWidget(color_btn)
        
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(24, 24)
        self.update_color_preview()
        toolbar.addWidget(self.color_preview)
        
        toolbar.addSpacing(20)
        
        self.width_combo = QComboBox()
        self.width_combo.addItems(["1", "2", "3", "5", "8", "12", "16", "24"])
        self.width_combo.setCurrentText("3")
        self.width_combo.currentTextChanged.connect(self.set_width)
        toolbar.addWidget(QLabel("太さ:"))
        toolbar.addWidget(self.width_combo)

        toolbar.addSpacing(10)

        self.font_size_combo = QComboBox()
        self.font_size_combo.addItems(["12", "16", "20", "24", "32", "48", "64", "80", "120"])
        self.font_size_combo.setCurrentText("24")
        toolbar.addWidget(QLabel("文字サイズ:"))
        toolbar.addWidget(self.font_size_combo)
        
        toolbar.addStretch()
        
        # Undo/Redo ボタン
        self.undo_btn = QPushButton("↩️ 戻す")
        self.undo_btn.clicked.connect(self.undo_stack.undo)
        toolbar.addWidget(self.undo_btn)
        
        self.redo_btn = QPushButton("↪️ やり直し")
        self.redo_btn.clicked.connect(self.undo_stack.redo)
        toolbar.addWidget(self.redo_btn)
        
        toolbar.addSpacing(10)

        clear_btn = QPushButton("🗑️ 全クリア")
        clear_btn.clicked.connect(self.clear_annotations)
        toolbar.addWidget(clear_btn)
        
        layout.addLayout(toolbar)
        
        # 編集エリア
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setRenderHint(QPainter.SmoothPixmapTransform)
        
        self.pixmap_item = QGraphicsPixmapItem(self.original_pixmap)
        self.pixmap_item.setZValue(-1) # 常に最背面
        self.scene.addItem(self.pixmap_item)
        self.scene.setSceneRect(QRectF(self.original_pixmap.rect()))
        
        layout.addWidget(self.view)
        
        # 説明ラベル
        help_label = QLabel("ドラッグで描画。選択モードではアイテムを移動できます。テキストはクリックで追加。")
        help_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(help_label)
        
        # 確定・キャンセル
        btns = QHBoxLayout()
        btns.addStretch()
        ok_btn = QPushButton("適用して保存")
        ok_btn.setMinimumWidth(120)
        ok_btn.clicked.connect(self.accept)
        ok_btn.setObjectName("primaryBtn")
        btns.addWidget(ok_btn)
        
        cancel_btn = QPushButton("キャンセル")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)
        
        # イベントフィルタの設定
        self.scene.installEventFilter(self)
        self.update_tool_styles()
        
        # Undoスタックの状態監視
        self.undo_stack.canUndoChanged.connect(self.undo_btn.setEnabled)
        self.undo_stack.canRedoChanged.connect(self.redo_btn.setEnabled)
        self.undo_btn.setEnabled(False)
        self.redo_btn.setEnabled(False)

    def setup_shortcuts(self):
        # 内部Undo/Redoショートカット
        undo_sc = QShortcut(QKeySequence("Ctrl+Z"), self)
        undo_sc.activated.connect(self.undo_stack.undo)
        
        redo_sc1 = QShortcut(QKeySequence("Ctrl+Y"), self)
        redo_sc1.activated.connect(self.undo_stack.redo)
        redo_sc2 = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)
        redo_sc2.activated.connect(self.undo_stack.redo)

    def set_tool(self, tool):
        self.current_tool = tool
        self.update_tool_styles()
        
        # 選択モード以外では既存アイテムの移動を制限するか検討
        # ここではシンプルにフラグのみ管理
        if tool == "select":
            self.view.setDragMode(QGraphicsView.NoDrag)
            for item in self.scene.items():
                if item != self.pixmap_item:
                    item.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable)
        else:
            self.view.setDragMode(QGraphicsView.NoDrag)
            for item in self.scene.items():
                if item != self.pixmap_item:
                    item.setFlags(QGraphicsItem.ItemIsSelectable) # 移動不可にする

    def update_tool_styles(self):
        for tool_id, btn in self.tool_buttons.items():
            if btn.isChecked():
                btn.setStyleSheet("background-color: #3d5afe; color: white; font-weight: bold;")
            else:
                btn.setStyleSheet("")

    def choose_color(self):
        color = QColorDialog.getColor(self.current_color, self)
        if color.isValid():
            self.current_color = color
            self.update_color_preview()

    def update_color_preview(self):
        self.color_preview.setStyleSheet(f"background-color: {self.current_color.name()}; border: 2px solid white; border-radius: 4px;")

    def set_width(self, width):
        self.current_width = int(width)

    def clear_annotations(self):
        self.undo_stack.clear()
        for item in self.scene.items():
            if item != self.pixmap_item:
                self.scene.removeItem(item)

    def eventFilter(self, obj, event):
        if obj == self.scene:
            if event.type() == event.GraphicsSceneMousePress:
                if self.current_tool == "select":
                    # 移動開始時の位置を記録
                    self.moving_item = self.scene.itemAt(event.scenePos(), self.view.transform())
                    if self.moving_item and self.moving_item != self.pixmap_item:
                        self.old_pos = self.moving_item.pos()
                    else:
                        self.moving_item = None
                    return False 
                
                self.start_point = event.scenePos()
                if self.current_tool == "text":
                    self.add_text(self.start_point)
                    self.start_point = None
                return True
            
            elif event.type() == event.GraphicsSceneMouseMove:
                if self.start_point and self.current_tool != "select":
                    self.update_temp_item(event.scenePos())
                    return True
            
            elif event.type() == event.GraphicsSceneMouseRelease:
                if self.current_tool == "select" and getattr(self, 'moving_item', None):
                    if self.moving_item.pos() != self.old_pos:
                        command = MoveItemCommand(self.moving_item, self.old_pos, self.moving_item.pos(), "アイテム移動")
                        self.undo_stack.push(command)
                    self.moving_item = None
                    return False

                if self.start_point and self.current_tool != "select":
                    self.finalize_item(event.scenePos())
                    self.start_point = None
                    return True
                
        return super().eventFilter(obj, event)

    def update_temp_item(self, end_point):
        if self.temp_item:
            self.scene.removeItem(self.temp_item)
            self.temp_item = None
            
        if self.current_tool == "arrow":
            self.temp_item = ArrowItem(self.start_point, end_point, self.current_color, self.current_width)
        elif self.current_tool == "rect":
            rect = QRectF(self.start_point, end_point).normalized()
            self.temp_item = QGraphicsRectItem(rect)
            self.temp_item.setPen(QPen(self.current_color, self.current_width))
            
        if self.temp_item:
            self.temp_item.setOpacity(0.5) # プレビュー中は半透明
            self.scene.addItem(self.temp_item)

    def finalize_item(self, end_point):
        if self.temp_item:
            self.scene.removeItem(self.temp_item)
            self.temp_item = None
            
        item = None
        if self.current_tool == "arrow":
            if (end_point - self.start_point).manhattanLength() > 5:
                item = ArrowItem(self.start_point, end_point, self.current_color, self.current_width)
        elif self.current_tool == "rect":
            rect = QRectF(self.start_point, end_point).normalized()
            if rect.width() > 5 or rect.height() > 5:
                item = QGraphicsRectItem(rect)
                item.setPen(QPen(self.current_color, self.current_width))
                item.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable)
        
        if item:
            command = AddItemCommand(self.scene, item, f"{self.current_tool}描画")
            self.undo_stack.push(command)

    def add_text(self, pos):
        text, ok = QInputDialog.getMultiLineText(self, "テキスト入力", "表示するテキスト:")
        if ok and text.strip():
            item = QGraphicsTextItem(text)
            item.setDefaultTextColor(self.current_color)
            font_size = int(self.font_size_combo.currentText())
            font = QFont("Arial", font_size)
            item.setFont(font)
            item.setPos(pos)
            item.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable)
            
            command = AddItemCommand(self.scene, item, "テキスト追加")
            self.undo_stack.push(command)

    def get_edited_pixmap(self):
        # 選択状態を解除してからレンダリング（枠線が入らないように）
        self.scene.clearSelection()
        
        # 画像のサイズに合わせたQImageを作成
        size = self.original_pixmap.size()
        result = QPixmap(size)
        result.fill(Qt.transparent)
        
        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing)
        # シーン全体ではなく、pixmap_itemの範囲（＝元画像の範囲）のみをレンダリング
        self.scene.render(painter, QRectF(result.rect()), QRectF(self.original_pixmap.rect()))
        painter.end()
        return result
