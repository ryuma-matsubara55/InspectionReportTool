import sys
import os
import ctypes
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QLockFile, QDir
from PyQt5.QtGui import QIcon
from ui.main_window import MainWindow
from ui.startup_dialog import StartupDialog

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def main():
    # Windowsでタスクバーのアイコンを正しく表示するための設定
    if os.name == 'nt':
        myappid = 'matsubara.inspectionreporttool.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # アプリケーションのアイコンを設定
    icon_path = resource_path('icon.ico')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    # 二重起動防止
    lock_file = QLockFile(QDir.temp().filePath('inspection_report_tool.lock'))
    if not lock_file.tryLock(100):
        # QMessageBox.warning(None, "警告", "アプリケーションは既に起動しています。")
        return

    # 起動ダイアログを表示
    startup_dialog = StartupDialog()
    if startup_dialog.exec_() != StartupDialog.Accepted:
        # キャンセルされた場合は終了
        return
    
    # 選択されたファイルパスを取得
    file_path = startup_dialog.get_selected_file()
    
    # メインウィンドウを起動
    window = MainWindow(file_path)
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
