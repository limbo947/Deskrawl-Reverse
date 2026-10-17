# -*- coding: utf-8 -*-
"""右 dock 页：属性明细表。

两种口径（同一张表）：
- set_sheet：计算口径——非零属性的三层聚合分解（手工构建 / demo）；
- set_panel_view：游戏面板口径——内存导入时冻结的复算结果（与游戏「属性」页逐行一致）。
"""
from PySide6.QtWidgets import (QAbstractItemView, QHeaderView, QLabel, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from deskrawl_calc import StatType, stat_name

from ..core.calc_service import stat_rows


class StatTable(QWidget):
    COLUMNS = ['属性', '基础值', '加法', '百分比加算', '连乘系数', '最终值']
    # 面板口径下同一张表的列含义不同（第 2 列是条件层、第 3 列才是百分比加算），表头必须跟着
    # 口径走——否则用户会把条件层当成加法层读，只有上方小字 hint 能区分（V7）。
    PANEL_COLUMNS = ['属性', '平坦层', '条件层', '百分比加算', '乘区', '面板显示']

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        self.hint = QLabel('—')
        self.table = QTableWidget(0, len(self.COLUMNS))
        self._set_headers(self.COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        lay.addWidget(self.hint)
        lay.addWidget(self.table)

    def _set_headers(self, labels):
        self.table.setHorizontalHeaderLabels(labels)

    def _fill(self, rows):
        self.table.setRowCount(len(rows))
        for i, cells in enumerate(rows):
            for j, text in enumerate(cells):
                self.table.setItem(i, j, QTableWidgetItem(text))

    def set_sheet(self, sheet):
        rows = stat_rows(sheet)
        self._set_headers(self.COLUMNS)
        self._fill([[r.name, f'{r.base:.4g}', f'{r.flat:.4g}',
                     f'{r.add:.4g}', f'{r.mult:.4g}', f'{r.final:.4g}'] for r in rows])
        self.hint.setText(f'非零属性 {len(rows)} 项 / 全表 {len(list(StatType))} 项')

    def set_panel_view(self, panel: dict):
        """游戏面板口径（导入时冻结）：列 = 平坦层 / 条件层 / 百分比加算 / 乘区 / 面板显示值。"""
        rows = panel.get('rows') or []
        self._set_headers(self.PANEL_COLUMNS)
        self._fill([
            [stat_name(stat), f'{flat:.6g}', f'{cond:+.4g}' if cond else '0',
             f'{pct:.4g}', f'{mult:.4g}', text]
            for stat, flat, cond, pct, mult, _final, text in rows])
        mode_cn = {'beta': 'β 逐件', 'alpha': 'α 聚合'}.get(panel.get('mode'), '')
        suffix = f'，{mode_cn}' if mode_cn else ''
        self.hint.setText(
            f'游戏面板口径（快照 {panel.get("time", "")}{suffix}；'
            f'血比例 {panel.get("hp_frac", 0.0):.0%}）— 与游戏「属性」页一致；'
            f'「最终值」列即面板显示，其余列为复算分解；编辑左侧面板不改变本表')
