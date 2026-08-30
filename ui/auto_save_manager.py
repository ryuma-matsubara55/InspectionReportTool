from PyQt5.QtCore import QTimer, QObject, pyqtSignal
from excel.excel_generator import ExcelGenerator
from datetime import datetime

class AutoSaveManager(QObject):
    """自動保存を管理するクラス"""
    
    save_started = pyqtSignal()
    save_completed = pyqtSignal(str)
    save_failed = pyqtSignal(str)
    
    def __init__(self, file_path, main_window):
        super().__init__()
        self.file_path = file_path
        self.main_window = main_window
        
        self.save_timer = QTimer()
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.save)
        self.debounce_delay = 2000
        
        self.is_saving = False
    
    def schedule_save(self):
        """保存をスケジュール（デバウンス）"""
        if not self.is_saving:
            self.save_timer.start(self.debounce_delay)
    
    def save_now(self):
        """即座に保存"""
        self.save_timer.stop()
        self.save()
    
    def save(self):
        """実際に保存を実行"""
        if self.is_saving:
            return
        
        self.is_saving = True
        self.save_started.emit()
        
        try:
            all_data = []
            for sheet_name, sheet_view in self.main_window.sheet_views.items():
                for test_case in sheet_view.test_cases:
                    data = test_case.get_data()
                    all_data.append(data)
            
            excel_gen = ExcelGenerator()
            excel_gen.create_excel(all_data, self.file_path)
            
            save_time = datetime.now().strftime('%H:%M:%S')
            self.save_completed.emit(save_time)
            
        except Exception as e:
            error_msg = f'保存エラー: {str(e)}'
            self.save_failed.emit(error_msg)
            print(error_msg)
        
        finally:
            self.is_saving = False
    
    def set_file_path(self, new_path):
        """ファイルパスを変更"""
        self.file_path = new_path
    
    def get_file_path(self):
        """ファイルパスを取得"""
        return self.file_path
