# -*- coding: utf-8 -*-
"""侧边导航栏：页面切换的唯一入口（条目列表 + 底部数据源徽标）。

用 QListWidget 而非一排按钮：选中态/键盘上下文航/焦点样式都能直接复用 QSS 的 item 态，
无需在每个按钮上手工维护互斥高亮。

为什么外面再套一层 QWidget：底部的数据源徽标（手工 / 内存导入 α·β + 快照时间）需要常驻在
条目列表 之下——QListWidget 自身放不下额外控件。对外接口（pageChanged/setCurrentRow/
currentRow/key_of/select_key）原样保留，调用方无需改动。
"""
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (QLabel, QListWidget, QListWidgetItem, QPushButton,
                               QVBoxLayout, QWidget)


class SidebarNav(QWidget):
    pageChanged = Signal(int)

    def __init__(self, pages, parent=None):
        """pages: [(key, label), ...]，顺序即页面顺序。"""
        super().__init__(parent)
        self.setObjectName('sidebarPane')
        self._keys = [key for key, _ in pages]
        self._collapsed = False

        # 收起按钮：窄窗口/高缩放下侧栏占的 188px 很贵，给一个明确的让宽度入口
        self.toggle = QPushButton('‹ 收起侧栏')
        self.toggle.setObjectName('navToggle')
        self.toggle.clicked.connect(self.toggle_collapsed)

        self._list = QListWidget()
        self._list.setObjectName('sidebar')
        for _key, label in pages:
            item = QListWidgetItem(label)
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            self._list.addItem(item)
        self._list.currentRowChanged.connect(self._on_current_changed)
        self._list.setCurrentRow(0)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # 数据源徽标：把「数值从哪来」固定在常驻位置（此前散在状态栏/卡片标题/α 横幅里，切页就丢）
        self.badge = QLabel('数据源：手工构建')
        self.badge.setObjectName('sourceBadge')
        self.badge.setWordWrap(True)
        self.badge.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.toggle)
        lay.addWidget(self._list, 1)
        lay.addWidget(self.badge)
        self.setFixedWidth(188)

    def toggle_collapsed(self):
        """收起/展开：收起后只留一条窄条（条目与徽标隐藏，给内容区让出宽度）。"""
        self._collapsed = not self._collapsed
        self._list.setVisible(not self._collapsed)
        self.badge.setVisible(not self._collapsed)
        self.toggle.setText('›' if self._collapsed else '‹ 收起侧栏')
        self.toggle.setToolTip('展开侧栏（Ctrl+B）' if self._collapsed else '收起侧栏（Ctrl+B）')
        self.setFixedWidth(30 if self._collapsed else 188)

    def _on_current_changed(self, row):
        if row >= 0:
            self.pageChanged.emit(row)

    # ---- 对外接口（与原 QListWidget 版一致，调用方无感）----
    def currentRow(self) -> int:
        return self._list.currentRow()

    def setCurrentRow(self, row: int):
        self._list.setCurrentRow(row)

    def key_of(self, row: int) -> str:
        return self._keys[row]

    def select_key(self, key: str):
        """编程式切页（快捷键/菜单用），不存在的 key 静默忽略。"""
        row = self._keys.index(key) if key in self._keys else -1
        if row >= 0:
            self._list.setCurrentRow(row)

    def set_source_badge(self, text: str, tooltip: str = ''):
        """底部徽标文案（手工 / 内存导入 α·β + 快照时间）；tooltip 写清含义。"""
        self.badge.setText(text)
        self.badge.setToolTip(tooltip)
