import sys
from PyQt5.QtWidgets import QApplication
from ui.expected_results_widget import ExpectedResultsWidget

app = QApplication(sys.argv)

widget = ExpectedResultsWidget()
# Initial state: 1 empty row
print(f"Initial rows: {len(widget.rows)}")
print(f"Initial data: {widget.get_all_data()}")

# Add data to first row
widget.rows[0].expected_edit.setPlainText("Expected 1")
print(f"After setting expected: {widget.get_all_data()}")

# Add another empty row
widget.add_row()
print(f"After adding empty row: {len(widget.rows)}")
print(f"Data with 1 valid, 1 empty: {widget.get_all_data()}")

# Set result only on second row (expected empty)
widget.rows[1].result_combo.setCurrentText("OK")
print(f"After setting result on empty expected: {widget.get_all_data()}")
