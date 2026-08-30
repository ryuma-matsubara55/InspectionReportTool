import sys
import os
from PyQt5.QtWidgets import QApplication

# プロジェクトルートをパスに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ui.expected_results_widget import ExpectedResultsWidget, ExpectedResultRow
from excel.excel_generator import ExcelGenerator

def test_widget_memo_flow():
    print("--- Testing expected_results_widget memo flow ---")
    
    # PyQtのウィジェット生成にはQApplicationが必要
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    # 親ダミーオブジェクトの作成
    class DummyMainWindow:
        def __init__(self):
            self.is_undo_redo = False
            self.executor = "TestUser"
        def mark_as_modified(self):
            pass
        def update_executor(self, val):
            pass

    dummy_main = DummyMainWindow()
    widget = ExpectedResultsWidget(dummy_main)
    
    # 期待結果行を1つ取得
    row = widget.rows[0]
    
    # 1. 直接テキストをQLineEditに入力した場合のテスト (改行なし)
    print("1. Testing QLineEdit direct editing...")
    row.memo_edit.setText("Direct Memo")
    data = row.get_data()
    print(f"   Data content: {data}")
    assert data['memo'] == "Direct Memo", f"Expected 'Direct Memo', got '{data['memo']}'"
    assert row.memo_full_text == "Direct Memo", f"Expected memo_full_text to be 'Direct Memo', got '{row.memo_full_text}'"
    print("   PASS: Direct QLineEdit editing works.")
    
    # 2. 改行入りのデータをset_dataしたときのテスト
    print("2. Testing set_data with multiline memo...")
    multiline_text = "Line 1\nLine 2\nLine 3"
    test_data = {
        'expected': 'Test Expected',
        'result': 'OK',
        'memo': multiline_text,
        'executor': 'User1',
        'date': '2026/05/19'
    }
    row.set_data(test_data)
    
    # 内部の保持用変数を確認
    print(f"   Internal full text: {repr(row.memo_full_text)}")
    assert row.memo_full_text == multiline_text, "memo_full_text mismatch"
    
    # QLineEditの表示用テキストを確認（改行がスペースに置換されているか）
    displayed_text = row.memo_edit.text()
    print(f"   Displayed text in QLineEdit: {repr(displayed_text)}")
    assert displayed_text == "Line 1 Line 2 Line 3", f"Expected space-separated preview, got '{displayed_text}'"
    
    # get_dataで改行入りのデータが取得できるか確認
    retrieved_data = row.get_data()
    print(f"   Retrieved data: {repr(retrieved_data['memo'])}")
    assert retrieved_data['memo'] == multiline_text, "get_data output mismatch"
    print("   PASS: set_data / get_data with multiline text works.")
    
    # 3. update_resultのテスト
    print("3. Testing ExpectedResultsWidget.update_result...")
    widget.update_result(0, 'memo', "Updated\nMultiline\nText")
    retrieved_data_updated = row.get_data()
    print(f"   Updated Retrieved memo: {repr(retrieved_data_updated['memo'])}")
    assert retrieved_data_updated['memo'] == "Updated\nMultiline\nText", "update_result mismatch"
    assert row.memo_edit.text() == "Updated Multiline Text", "QLineEdit display mismatch after update_result"
    print("   PASS: update_result with multiline text works.")


def test_excel_generation():
    print("\n--- Testing Excel Generator integration with multiline memo ---")
    generator = ExcelGenerator()
    output_path = 'test_memo_output.xlsx'
    
    multiline_memo = "Excel Memo\nRow 2\nRow 3"
    
    test_cases = [
        {
            'number': 1,
            'sheet': 'MemoTestSheet',
            'item': 'Item 1',
            'input_condition': 'Input 1',
            'procedure': 'Procedure 1',
            'expected_results': [
                {
                    'expected': 'Exp 1',
                    'result': 'OK',
                    'executor': 'User',
                    'date': '2026-05-19',
                    'memo': multiline_memo
                }
            ],
            'input_images': [],
            'result_images': []
        }
    ]
    
    print("1. Generating Excel with multiline memo...")
    try:
        generator.create_excel(test_cases, output_path)
        print("   PASS: Excel file created successfully.")
    except Exception as e:
        print(f"   FAIL: Excel creation failed: {e}")
        return

    print("2. Reading generated Excel and checking memo...")
    try:
        loaded = generator.load_excel(output_path)
        loaded_memo = loaded[0]['expected_results'][0]['memo']
        print(f"   Loaded memo from Excel: {repr(loaded_memo)}")
        # excel_generatorが改行をそのまま書き込み・ロードしているか確認
        assert loaded_memo == multiline_memo, f"Expected '{repr(multiline_memo)}', got '{repr(loaded_memo)}'"
        print("   PASS: Excel roundtrip with multiline memo verified.")
    except Exception as e:
        print(f"   FAIL: Excel loading or verification failed: {e}")
    finally:
        if os.path.exists(output_path):
            os.remove(output_path)

if __name__ == "__main__":
    test_widget_memo_flow()
    test_excel_generation()
