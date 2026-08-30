from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QPushButton, QLabel, 
                             QFileDialog, QListWidget, QMessageBox)
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QFont
import os

class StartupDialog(QDialog):
    """起動時に表示されるダイアログ"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_file = None
        self.settings = QSettings('InspectionTool', 'RecentFiles')
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle('検査成績書作成ツール')
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        layout = QVBoxLayout(self)
        
        # タイトル
        title = QLabel('検査成績書作成ツール')
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        layout.addSpacing(20)
        
        # 新規作成ボタン
        new_btn = QPushButton('新規プロジェクトを作成')
        new_btn.setMinimumHeight(50)
        new_btn.clicked.connect(self.create_new_project)
        layout.addWidget(new_btn)
        
        # ファイルを開くボタン
        open_btn = QPushButton('既存ファイルを開く')
        open_btn.setMinimumHeight(50)
        open_btn.clicked.connect(self.open_existing_file)
        layout.addWidget(open_btn)
        
        layout.addSpacing(10)
        
        # 最近使用したファイル
        recent_label = QLabel('最近使用したファイル:')
        layout.addWidget(recent_label)
        
        self.recent_files_list = QListWidget()
        self.recent_files_list.itemDoubleClicked.connect(self.open_recent_file)
        layout.addWidget(self.recent_files_list)
        
        # 最近使用したファイルを読み込み
        self.load_recent_files()
        
        # キャンセルボタン
        cancel_btn = QPushButton('キャンセル')
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)
    
    def create_new_project(self):
        """新規プロジェクトを作成"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            '新規ファイル作成', 
            '', 
            'Excel Files (*.xlsx)'
        )
        
        if file_path:
            if not file_path.endswith('.xlsx'):
                file_path += '.xlsx'
            
            self.selected_file = file_path
            self.add_to_recent_files(file_path)
            self.accept()
    
    def open_existing_file(self):
        """既存ファイルを開く"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            'ファイルを開く', 
            '', 
            'Excel Files (*.xlsx)'
        )
        
        if file_path:
            if not os.path.exists(file_path):
                QMessageBox.warning(self, '警告', f'ファイルが見つかりません: {file_path}')
                return
            
            self.selected_file = file_path
            self.add_to_recent_files(file_path)
            self.accept()
    
    def open_recent_file(self, item):
        """最近使用したファイルを開く"""
        file_path = item.text()
        
        if not os.path.exists(file_path):
            QMessageBox.warning(self, '警告', f'ファイルが見つかりません: {file_path}')
            self.remove_from_recent_files(file_path)
            self.load_recent_files()
            return
        
        self.selected_file = file_path
        self.add_to_recent_files(file_path)
        self.accept()
    
    def load_recent_files(self):
        """最近使用したファイルを読み込み"""
        self.recent_files_list.clear()
        recent_files = self.settings.value('recent_files', [])
        
        if not isinstance(recent_files, list):
            recent_files = []
        
        valid_files = [f for f in recent_files if os.path.exists(f)]
        
        for file_path in valid_files[:10]:
            self.recent_files_list.addItem(file_path)
    
    def add_to_recent_files(self, file_path):
        """最近使用したファイルに追加"""
        recent_files = self.settings.value('recent_files', [])
        
        if not isinstance(recent_files, list):
            recent_files = []
        
        if file_path in recent_files:
            recent_files.remove(file_path)
        
        recent_files.insert(0, file_path)
        recent_files = recent_files[:10]
        
        self.settings.setValue('recent_files', recent_files)
    
    def remove_from_recent_files(self, file_path):
        """最近使用したファイルから削除"""
        recent_files = self.settings.value('recent_files', [])
        
        if not isinstance(recent_files, list):
            recent_files = []
        
        if file_path in recent_files:
            recent_files.remove(file_path)
            self.settings.setValue('recent_files', recent_files)
    
    def get_selected_file(self):
        """選択されたファイルパスを取得"""
        return self.selected_file
