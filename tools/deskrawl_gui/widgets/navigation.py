# -*- coding: utf-8 -*-
"""侧边导航栏：页面切换的唯一入口（图标留白 + 文字条目，当前页高亮 + 左侧强调条）。

用 QListWidget 而非一排按钮：选中态/键盘上下文航/焦点样式都能直接复用 QSS 的 item 态，
无需在每个按钮上手工维护互斥高亮。
"""
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QListWidget, QListWidgetItem


class SidebarNav(QListWidget):
    pageChanged = Signal(int)

    def __init__(self, pages, parent=None):
        """pages: [(key, label), ...]，顺序即页面顺序。"""
        super().__init__(parent)
        self.setObjectName('sidebar')
        self._keys = [key for key, _ in pages]
        for _key, label in pages:
            item = QListWidgetItem(label)
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            self.addItem(item)
        self.currentRowChanged.connect(self._on_current_changed)
        self.setCurrentRow(0)
        self.setFixedWidth(188)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def _on_current_changed(self, row):
        if row >= 0:
            self.pageChanged.emit(row)

    def key_of(self, row: int) -> str:
        return self._keys[row]

    def select_key(self, key: str):
        """编程式切页（快捷键/菜单用），不存在的 key 静默忽略。"""
        row = self._keys.index(key) if key in self._keys else -1
        if row >= 0:
            self.setCurrentRow(row)
