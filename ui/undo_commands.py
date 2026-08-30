import copy
from PyQt5.QtWidgets import QUndoCommand
from typing import List, Dict, Any

class TestCaseDataCommand(QUndoCommand):
    """テストケースのデータ変更を記録するコマンド"""

    def __init__(self, sheet_view, index: int, old_data: Dict[str, Any], new_data: Dict[str, Any], description: str):
        super().__init__(description)

        self.main_window = sheet_view.main_window
        self.sheet_name = sheet_view.sheet_name
        self.index = index

        self.old_data = copy.deepcopy(old_data)
        self.new_data = copy.deepcopy(new_data)

        # 重要：push直後のredoはスキップする
        # 画面側では既に変更済みなので、ここで再適用するとrefreshが走ってitemが消える
        self._first_redo = True

    def redo(self):
        if self._first_redo:
            self._first_redo = False
            return

        self._apply(self.new_data)

    def undo(self):
        self._apply(self.old_data)

    def _apply(self, data):
        sheet_view = self.main_window.sheet_views.get(self.sheet_name)
        if sheet_view is None:
            return

        if not (0 <= self.index < len(sheet_view.test_cases)):
            return

        test_case = sheet_view.test_cases[self.index]

        self.main_window.is_undo_redo = True
        test_case.is_undo_redo = True

        try:
            test_case.load_data(copy.deepcopy(data))
            test_case.last_committed_data = copy.deepcopy(data)
        finally:
            test_case.is_undo_redo = False
            self.main_window.is_undo_redo = False

        self.main_window.integrated_view.refresh()
        self.main_window.dashboard.refresh()
        self.main_window.mark_as_modified()
        
        # フォーカスを当てる
        if hasattr(self.main_window, 'focus_on_test_case'):
            self.main_window.focus_on_test_case(self.sheet_name, self.index)

class AddRemoveTestCaseCommand(QUndoCommand):
    """テストケースの追加・削除を記録するコマンド"""

    def __init__(self, sheet_view, index: int, data: Dict[str, Any], is_add: bool, description: str):
        super().__init__(description)

        self.main_window = sheet_view.main_window
        self.sheet_name = sheet_view.sheet_name
        self.index = index
        self.data = copy.deepcopy(data)
        self.is_add = is_add

    def _get_sheet_view(self):
        return self.main_window.sheet_views.get(self.sheet_name)

    def redo(self):
        if self.is_add:
            self._add()
        else:
            self._remove()

    def undo(self):
        if self.is_add:
            self._remove()
        else:
            self._add()

    def _add(self):
        sheet_view = self._get_sheet_view()
        if sheet_view is None:
            return

        from ui.test_case_widget import TestCaseWidget

        self.main_window.is_undo_redo = True
        try:
            index = min(self.index, len(sheet_view.test_cases))

            test_case = TestCaseWidget(
                index + 1,
                sheet_view.sheet_name,
                sheet_view.main_window,
                sheet_view
            )
            test_case.load_data(copy.deepcopy(self.data))

            sheet_view.test_cases.insert(index, test_case)
            sheet_view.refresh_order()
            
            # 追加された項目にフォーカス
            if hasattr(self.main_window, 'focus_on_test_case'):
                self.main_window.focus_on_test_case(self.sheet_name, index, highlight=True)
        finally:
            self.main_window.is_undo_redo = False

    def _remove(self):
        sheet_view = self._get_sheet_view()
        if sheet_view is None:
            return

        if not (0 <= self.index < len(sheet_view.test_cases)):
            return

        self.main_window.is_undo_redo = True
        try:
            test_case = sheet_view.test_cases.pop(self.index)
            test_case.prepare_delete()
            sheet_view.test_cases_layout.removeWidget(test_case)
            test_case.deleteLater()
            sheet_view.refresh_order()
            
            # 削除された位置（の一つ上）にフォーカス
            if hasattr(self.main_window, 'focus_on_test_case'):
                focus_index = max(0, self.index - 1)
                self.main_window.focus_on_test_case(self.sheet_name, focus_index)
        finally:
            self.main_window.is_undo_redo = False

class MoveTestCaseCommand(QUndoCommand):
    """テストケースの移動を記録するコマンド"""

    def __init__(self, sheet_view, old_index: int, new_index: int, description: str):
        super().__init__(description)

        self.main_window = sheet_view.main_window
        self.sheet_name = sheet_view.sheet_name
        self.old_index = old_index
        self.new_index = new_index

    def _get_sheet_view(self):
        return self.main_window.sheet_views.get(self.sheet_name)

    def redo(self):
        self._move(self.old_index, self.new_index)

    def undo(self):
        self._move(self.new_index, self.old_index)

    def _move(self, src, dst):
        sheet_view = self._get_sheet_view()
        if sheet_view is None:
            return

        count = len(sheet_view.test_cases)

        if not (0 <= src < count):
            return
        if not (0 <= dst < count):
            return

        self.main_window.is_undo_redo = True
        try:
            item = sheet_view.test_cases.pop(src)
            sheet_view.test_cases.insert(dst, item)
            sheet_view.refresh_order()
            
            # 移動先にフォーカス
            if hasattr(self.main_window, 'focus_on_test_case'):
                self.main_window.focus_on_test_case(self.sheet_name, dst)
        finally:
            self.main_window.is_undo_redo = False

class SheetCommand(QUndoCommand):
    """シートの操作を記録するコマンド"""
    def __init__(self, main_window, operation: str, sheet_name: str, data: List[Dict[str, Any]] = None, old_name: str = None, description: str = ""):
        super().__init__(description)
        self.main_window = main_window
        self.operation = operation # 'add', 'remove', 'rename'
        self.sheet_name = sheet_name
        self.data = copy.deepcopy(data) if data else None
        self.old_name = old_name

    def redo(self):
        if self.operation == 'add': self._add()
        elif self.operation == 'remove': self._remove()
        elif self.operation == 'rename': self._rename(self.old_name, self.sheet_name)

    def undo(self):
        if self.operation == 'add': self._remove()
        elif self.operation == 'remove': self._add()
        elif self.operation == 'rename': self._rename(self.sheet_name, self.old_name)

    def _add(self):
        from ui.main_window import SheetTabWidget
        if self.sheet_name not in self.main_window.sheets:
            self.main_window.sheets.append(self.sheet_name)
            view = SheetTabWidget(self.sheet_name, self.main_window)
            self.main_window.sheet_views[self.sheet_name] = view
            self.main_window.tabs.addTab(view, self.sheet_name)
            if self.data:
                view.load_data(self.data)
            self.main_window.integrated_view.update_sheet_filter()
            self.main_window.integrated_view.refresh()

    def _remove(self):
        if self.sheet_name in self.main_window.sheet_views:
            view = self.main_window.sheet_views.pop(self.sheet_name)
            self.main_window.sheets.remove(self.sheet_name)
            idx = self.main_window.tabs.indexOf(view)
            if idx != -1: self.main_window.tabs.removeTab(idx)
            view.deleteLater()
            self.main_window.integrated_view.update_sheet_filter()
            self.main_window.integrated_view.refresh()

    def _rename(self, old_name, new_name):
        if old_name in self.main_window.sheet_views:
            view = self.main_window.sheet_views.pop(old_name)
            self.main_window.sheet_views[new_name] = view
            idx = self.main_window.sheets.index(old_name)
            self.main_window.sheets[idx] = new_name
            view.sheet_name = new_name
            tab_idx = self.main_window.tabs.indexOf(view)
            if tab_idx != -1: self.main_window.tabs.setTabText(tab_idx, new_name)
            for tc in view.test_cases: tc.sheet_name = new_name
            self.main_window.integrated_view.update_sheet_filter()
            self.main_window.integrated_view.refresh()
