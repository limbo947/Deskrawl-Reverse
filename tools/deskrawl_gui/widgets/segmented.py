# -*- coding: utf-8 -*-
"""分段标签：候选类别 / 装备槽的横向切换条（对应设计文档里 markets-table-card 的 tab 行）。

为什么不用 QComboBox：这两处选项都少（4 类 / 11 槽）且切换频繁，下拉要点两次、
展开时还会盖住结果；横向标签一次点击直达，选中态用黄色下划线表达——与顶部导航同一套语言。

为什么保留 QComboBox 的方法子集（addItem/findData/setCurrentIndex/currentData/
currentIndexChanged）：调用方与自检都按下拉的语义在用它（按 data 查、按 index 设、
回填时 blockSignals），换控件不该顺带改写一层业务代码。
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QPushButton


class SegmentedTabs(QFrame):
    """互斥的横向标签条；data 与按钮一一对应（禁用项也可保留，用于说明「为什么不参与」）。"""

    currentIndexChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('segTabs')
        self._buttons = []
        self._data = []
        self._index = -1
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(0)
        self._lay.addStretch(1)          # 标签左对齐；新项插在它前面

    # ---------------- 构建 ----------------
    def addItem(self, text: str, data=None, enabled: bool = True) -> int:
        """追加一项并返回索引；首项自动选中（与 QComboBox 一致）。"""
        btn = QPushButton(str(text))
        btn.setObjectName('segTab')
        btn.setCheckable(True)
        btn.setEnabled(bool(enabled))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip('' if enabled else '不参与对比（列在此处只为说明）')
        idx = len(self._buttons)
        self._group.addButton(btn, idx)
        btn.clicked.connect(lambda _=False, i=idx: self._on_clicked(i))
        self._lay.insertWidget(self._lay.count() - 1, btn)
        self._buttons.append(btn)
        self._data.append(data)
        if idx == 0:
            self._set_index(0, emit=False)
        return idx

    def set_tab_tooltip(self, index: int, text: str) -> None:
        if 0 <= index < len(self._buttons):
            self._buttons[index].setToolTip(str(text))

    # ---------------- 下拉语义子集 ----------------
    def count(self) -> int:
        return len(self._buttons)

    def currentIndex(self) -> int:          # noqa: N802 —— 与 QComboBox 同名
        return self._index

    def currentData(self):                  # noqa: N802
        if 0 <= self._index < len(self._data):
            return self._data[self._index]
        return None

    def findData(self, data) -> int:        # noqa: N802
        for i, item in enumerate(self._data):
            if item is None and data is None:
                return i
            if item is not None and data is not None and item == data:
                return i
        return -1

    def itemData(self, index: int):         # noqa: N802
        """下拉语义的直读通道（自检与夹具按索引取 data，不必先切过去）。"""
        if 0 <= int(index) < len(self._data):
            return self._data[int(index)]
        return None

    def setCurrentIndex(self, index: int) -> None:      # noqa: N802
        """编程式选中；越界忽略（调用方本就用 findData 的 -1 做回落判断）。"""
        if 0 <= int(index) < len(self._buttons):
            self._set_index(int(index), emit=True)

    # ---------------- 内部 ----------------
    def _on_clicked(self, index: int) -> None:
        if index == self._index:
            return
        self._set_index(index, emit=True)

    def _set_index(self, index: int, *, emit: bool) -> None:
        if not 0 <= index < len(self._buttons):
            return
        changed = index != self._index
        self._index = index
        self._buttons[index].setChecked(True)
        if emit and changed:
            self.currentIndexChanged.emit(index)
