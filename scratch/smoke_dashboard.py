import sys

sys.path.insert(0, r"c:\Users\ryuma.matsubara\Desktop\InspectionReportTool\Source")

from PyQt5.QtWidgets import QApplication
from ui import styles
from ui.dashboard_widget import DashboardWidget


class FakeView:
    def __init__(self, data):
        self._d = data

    def get_all_data(self):
        return self._d


def items(*result_groups):
    return [{"expected_results": [{"result": r} for r in rs]} for rs in result_groups]


class FakeMainWindow:
    def __init__(self, theme="dark"):
        self.current_theme = theme
        self.sheet_views = {
            "Sheet1": FakeView(items(["OK"] * 5 + ["NG", "未実施"])),
            "Sheet2": FakeView(items(["OK", "NG", "NG"])),
            "Sheet3": FakeView([]),
        }


def main(theme):
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(styles.DARK_THEME_QSS if theme == "dark" else styles.LIGHT_THEME_QSS)
    w = DashboardWidget(FakeMainWindow(theme))
    w.resize(1080, 820)
    w.refresh()
    app.processEvents()
    out = rf"c:\Users\ryuma.matsubara\Desktop\InspectionReportTool\Source\scratch\dashboard_{theme}.png"
    w.grab().save(out)
    print("saved:", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "dark")