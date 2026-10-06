# -*- coding: utf-8 -*-
"""右 dock 页：属性明细表（非零属性的三层聚合分解）。"""
from PySide6.QtWidgets import (QAbstractItemView, QHeaderView, QLabel, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from deskrawl_calc import StatType

from ..core.calc_service import stat_rows


class StatTable(QWidget):
    COLUMNS = ['属性', '基础值', '加法', '百分比加算', '连乘系数', '最终值']

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        self.hint = QLabel('—')
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        lay.addWidget(self.hint)
        lay.addWidget(self.table)

    def set_sheet(self, sheet):
        rows = stat_rows(sheet)
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, text in enumerate([r.name, f'{r.base:.4g}', f'{r.flat:.4g}',
                                      f'{r.add:.4g}', f'{r.mult:.4g}', f'{r.final:.4g}']):
                self.table.setItem(i, j, QTableWidgetItem(text))
        self.hint.setText(f'非零属性 {len(rows)} 项 / 全表 {len(list(StatType))} 项')
