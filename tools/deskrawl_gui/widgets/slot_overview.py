# -*- coding: utf-8 -*-
"""当前装备总览（11 槽只读表）：导入后「我现在穿的是什么」的唯一一览。

为什么放角色页：这是角色本体状态；对比页一次只看一个槽，逐槽点开才能拼出全貌。
双击某行即跳到对比页对应槽，把「发现哪个槽可换」直接接上「立刻去比」。
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QGroupBox, QHeaderView, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from ..core.profile import COMPARE_SLOTS, SLOT_LABELS
from .common import mono_font


class SlotOverview(QGroupBox):
    slotActivated = Signal(int)

    COLUMNS = ['槽位', '装备', '强化', '宝石']
    _ROW_H = 22

    def __init__(self, profile, parent=None):
        super().__init__('当前装备（双击跳到对比）', parent)
        self.profile = profile
        self._slots = [int(slot) for slot, _label in COMPARE_SLOTS]
        self.table = QTableWidget(len(self._slots), len(self.COLUMNS))
        self.table.setAccessibleName('当前装备 11 槽总览')
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(self._ROW_H)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        # 关掉两层滚动条：表格给固定高度装下 11 行，外层由角色页的滚动区负责
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        head = self.table.horizontalHeader()
        head.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        head.setSectionResizeMode(1, QHeaderView.Stretch)
        head.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        head.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setToolTip('双击某行跳到「装备对比」并选中该槽；「—」表示该槽没有记录。')
        self.table.cellDoubleClicked.connect(self._on_double_clicked)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)   # 8 + QSS padding 4 = 12：与嵌入卡内距统一
        lay.addWidget(self.table)
        self.reload()

    def _current_items(self):
        """槽 id → 当前件草稿：武器槽在 weapon_current，其余在 slot_current。"""
        yield 0, getattr(self.profile, 'weapon_current', None)
        slots = getattr(self.profile, 'slot_current', None) or {}
        for slot in self._slots[1:]:
            yield slot, slots.get(slot)

    def reload(self):
        """按 profile 重建 11 行（每次编辑都会走到；44 个单元格的开销可忽略）。"""
        keep = self.table.currentRow()
        self.table.blockSignals(True)
        mono = mono_font(self.table.font())     # 强化/宝石是数值列：等宽才一眼对齐
        for row, (slot, item) in enumerate(self._current_items()):
            name = str(getattr(item, 'name', '') or '').strip()
            level = int(getattr(item, 'upgrade_level', 0) or 0)
            gems = list(getattr(item, 'gems', None) or [])
            cells = [SLOT_LABELS.get(slot, f'槽{slot}'), name or '—',
                     f'+{level}' if level else '—', str(len(gems)) if gems else '—']
            for col, text in enumerate(cells):
                cell = QTableWidgetItem(text)
                if col >= 2:
                    cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    cell.setFont(mono)
                if col == 1:
                    cell.setToolTip(name or '该槽没有记录（手工构建只填了部分槽时属正常）')
                self.table.setItem(row, col, cell)
        if 0 <= keep < self.table.rowCount():
            self.table.selectRow(keep)
        self.table.blockSignals(False)
        self._fit_height()

    def _fit_height(self):
        header = self.table.horizontalHeader()
        h = header.height() if header.height() > 0 else header.sizeHint().height()
        self.table.setFixedHeight(h + self._ROW_H * self.table.rowCount() + 4)

    def _on_double_clicked(self, row, _col):
        if 0 <= row < len(self._slots):
            self.slotActivated.emit(self._slots[row])
