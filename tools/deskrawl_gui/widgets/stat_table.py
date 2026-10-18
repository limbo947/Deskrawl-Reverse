# -*- coding: utf-8 -*-
"""右 dock 页：属性明细表（QAbstractTableModel + QTableView）。

两种口径（同一张表）：
- set_sheet：计算口径——非零属性的三层聚合分解（手工构建 / demo）；
- set_panel_view：游戏面板口径——内存导入时冻结的复算结果（与游戏「属性」页逐行一致）。

为什么改成 model/view：这张表最多 67 行 × 6 列，每格一个 QTableWidgetItem，刷新 = 402 个对象
的创建/销毁；而数据本身就是「重算一整批行」，交给 model 的 reset 只需一次 begin/endResetModel，
视图自己重绘。同时刷新期间的半成品状态（行数已改、单元格未填）也从根源消失。
"""
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import (QAbstractItemView, QHeaderView, QLabel, QTableView, QVBoxLayout,
                               QWidget)

from deskrawl_calc import StatType, stat_name

from ..core.calc_service import stat_rows
from ..core.format import fmt_layer, fmt_qty


class _StatModel(QAbstractTableModel):
    """只读的属性行模型：表头与行文本都由调用方整批给入，模型不持有业务状态。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._headers = []
        self._rows = []

    def set_rows(self, headers, rows):
        self.beginResetModel()
        self._headers = list(headers)
        self._rows = [list(r) for r in rows]
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):        # noqa: N802 —— Qt 覆写
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):     # noqa: N802 —— Qt 覆写
        return 0 if parent.isValid() else len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            return self._rows[index.row()][index.column()]
        # 数值列右对齐：与技能表同口径，扫一列数字时小数点才对得齐
        if role == Qt.TextAlignmentRole and index.column() >= 1:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):   # noqa: N802 —— Qt 覆写
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._headers[section]
        return None

    def cell_text(self, row, col) -> str:
        """取值直通道：自检与调试按 (行, 列) 读文本，不必绕回视图。"""
        return str(self._rows[row][col])


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
        self.model = _StatModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        lay.addWidget(self.hint)
        lay.addWidget(self.table)

    def set_sheet(self, sheet):
        rows = stat_rows(sheet)
        self.model.set_rows(self.COLUMNS, [
            [r.name, fmt_qty(r.base), fmt_layer(r.flat, identity=0),
             fmt_layer(r.add, identity=0), fmt_layer(r.mult, identity=1), fmt_qty(r.final)]
            for r in rows])
        self.hint.setText(f'非零属性 {len(rows)} 项 / 全表 {len(list(StatType))} 项')

    def set_panel_view(self, panel: dict):
        """游戏面板口径（导入时冻结）：列 = 平坦层 / 条件层 / 百分比加算 / 乘区 / 面板显示值。"""
        rows = panel.get('rows') or []
        # 条件层 0 / 百分比 0 / 乘区 1 都是「本层无贡献」：显示成 —，否则一屏十几个 0 与 1 会把
        # 真正有值的那几行淹掉（面板显示值仍是原始文本，不动）
        self.model.set_rows(self.PANEL_COLUMNS, [
            [stat_name(stat), fmt_qty(flat), fmt_layer(cond, identity=0),
             fmt_layer(pct, identity=0), fmt_layer(mult, identity=1), text]
            for stat, flat, cond, pct, mult, _final, text in rows])
        mode_cn = {'beta': 'β 逐件', 'alpha': 'α 聚合'}.get(panel.get('mode'), '')
        suffix = f'，{mode_cn}' if mode_cn else ''
        self.hint.setText(
            f'游戏面板口径（快照 {panel.get("time", "")}{suffix}；'
            f'血比例 {panel.get("hp_frac", 0.0):.0%}）— 与游戏「属性」页一致；'
            f'「最终值」列即面板显示，其余列为复算分解；编辑左侧面板不改变本表')
