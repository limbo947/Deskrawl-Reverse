# -*- coding: utf-8 -*-
"""右 dock 页：属性明细表（QAbstractTableModel + QTableView）。

两种口径（同一张表）：
- set_sheet：计算口径——非零属性的三层聚合分解（手工构建 / demo）；
- set_panel_view：游戏面板口径——内存导入时冻结的复算结果（与游戏「属性」页逐行一致）。

为什么改成 model/view：这张表最多 67 行 × 6 列，每格一个 QTableWidgetItem，刷新 = 402 个对象
的创建/销毁；而数据本身就是「重算一整批行」，交给 model 的 reset 只需一次 begin/endResetModel，
视图自己重绘。同时刷新期间的半成品状态（行数已改、单元格未填）也从根源消失。
"""
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import (QAbstractItemView, QHeaderView, QLineEdit, QMenu,
                               QPushButton, QTableView, QVBoxLayout, QWidget)

from deskrawl_calc import StatType, stat_name

from ..core.calc_service import stat_rows
from ..core.format import fmt_layer, fmt_qty
from .common import Card, MonoDelegate, add_table_export

# 首屏默认只列这 12 项：41 行全量表是「核对游戏面板」用的，日常看的是「我的角色强不强」。
# 用 StatType 而不是中文名字面量：中文名改文案时这里跟着走，不会静默失配成空表。
_COMMON_STATS = (StatType.WeaponDamage, StatType.Damage, StatType.AttackSpeed,
                 StatType.Strength, StatType.Dexterity, StatType.Intelligence,
                 StatType.MaxHealth, StatType.Armor, StatType.MagicResist,
                 StatType.CritChance, StatType.CritDamage, StatType.MoveSpeed)
_COMMON_NAMES = frozenset(stat_name(int(s)) for s in _COMMON_STATS)


class _ScopeProxy(QSortFilterProxyModel):
    """「只看常用」范围过滤 + 既有的名称搜索：两级条件同时生效。

    为什么放在代理而不是裁剪模型：模型保持全量，面板改动后的实时断言（自检读 model 找
    「武器伤害」）与非折叠路径都不受影响；视图/导出看到的是同一份过滤结果。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._only_common = True

    def set_only_common(self, flag: bool) -> None:
        self._only_common = bool(flag)
        self.invalidateFilter()

    def only_common(self) -> bool:
        return self._only_common

    def filterAcceptsRow(self, source_row, source_parent):     # noqa: N802 —— Qt 覆写
        if self._only_common:
            index = self.sourceModel().index(source_row, 0, source_parent)
            if str(index.data(Qt.DisplayRole) or '') not in _COMMON_NAMES:
                return False
        return super().filterAcceptsRow(source_row, source_parent)


class _StatModel(QAbstractTableModel):
    """只读的属性行模型：表头与行文本都由调用方整批给入，模型不持有业务状态。"""

    # 排序用的原始数值：显示文本是格式化过的（"12.5%" / "1,234"），按字符串排会得到
    # 1,234 < 12.5% 这种错序；所以另存一份数值专供排序，界面仍只看 DisplayRole
    SORT_ROLE = Qt.UserRole + 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self._headers = []
        self._rows = []
        self._raw = []

    def set_rows(self, headers, rows, raw=None):
        """rows = 显示文本；raw = 同形数值行（供排序与断言读；缺省时退回显示文本）。"""
        self.beginResetModel()
        self._headers = list(headers)
        self._rows = [list(r) for r in rows]
        self._raw = [list(r) for r in raw] if raw is not None else [list(r) for r in rows]
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
        if role == self.SORT_ROLE:
            return self._raw[index.row()][index.column()]
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

    # 导出通道：表头与整行原文（显示文本）——导出应与人眼所见一致，不另算一份口径
    def headers(self) -> list:
        return list(self._headers)

    def raw_rows(self) -> list:
        return [list(r) for r in self._rows]


class StatTable(QWidget):
    COLUMNS = ['属性', '基础值', '加法', '百分比加算', '连乘系数', '最终值']
    _DETAIL_COLUMNS = (2, 3, 4)      # 三层分解列：常用态下收起（见 _update_scope_ui）
    # 面板口径下同一张表的列含义不同（第 2 列是条件层、第 3 列才是百分比加算），表头必须跟着
    # 口径走——否则用户会把条件层当成加法层读，只有上方小字 hint 能区分（V7）。
    PANEL_COLUMNS = ['属性', '平坦层', '条件层', '百分比加算', '乘区', '面板显示']

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.model = _StatModel(self)
        # 过滤走代理模型（67 行里找一条属性不必靠滚）：不重建模型，筛选即时生效
        self.proxy = _ScopeProxy(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterKeyColumn(0)
        self.proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy.setSortRole(_StatModel.SORT_ROLE)     # 按数值排，不按显示文本排
        self._common_hits = 0
        self.scope_btn = QPushButton('显示全部')
        self.scope_btn.setObjectName('statScope')
        self.scope_btn.setToolTip('默认只列最常看的属性。点这里展开整张表（导出与屏幕一致，'
                                  '展开后再右键导出即得全量）。')
        self.scope_btn.clicked.connect(self.toggle_scope)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText('筛选属性名…')
        self.filter_edit.setClearButtonEnabled(True)
        # 只有占位符时读屏器拿不到名字：占位符一输入就消失，可访问名必须单列
        self.filter_edit.setAccessibleName('按属性名筛选')
        self.filter_edit.textChanged.connect(self._apply_filter)
        self.table = QTableView()
        self.table.setAccessibleName('属性明细表')
        self.table.setModel(self.proxy)
        # 数值列换等宽字形（第 0 列是属性名，属于正文）：小数点对齐才扫得动一列数
        for col in range(1, len(self.COLUMNS)):
            self.table.setItemDelegateForColumn(col, MonoDelegate(self.table))
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(26)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        head = self.table.horizontalHeader()
        head.setSectionResizeMode(0, QHeaderView.Stretch)
        # 表头排序（A9）：首次点击才启用。不一开始就 setSortingEnabled(True)——Qt 会立刻按
        # 「第 0 列升序」重排，把默认顺序（计算口径 |最终值| 降序 / 面板口径=游戏属性页行序）打散，
        # 而这两个顺序本身是「一眼先看到大项」的信息。
        head.setSectionsClickable(True)
        head.setSortIndicatorShown(False)
        head.sectionClicked.connect(self.sort_by_column)
        # 右键导出：属性表是「拿去核对/贴给别人的」第一张表，不能只能截屏
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_table_menu)
        # 卡片头一行收拢「标题 + 筛选 + 范围切换」，正文只留表格：与设计文档里
        # markets-table-card 的「tab 行在卡片内、表格紧随」的结构一致，也省掉一条工具栏
        self.card = Card('属性明细')
        self.filter_edit.setFixedWidth(220)
        self.card.add_action(self.filter_edit)
        self.card.add_action(self.scope_btn)
        self.hint = self.card.hint_label
        self.card.set_hint('—')
        self.card.body.addWidget(self.table, 1)
        lay.addWidget(self.card)

    def set_sheet(self, sheet):
        rows = stat_rows(sheet)
        self.model.set_rows(
            self.COLUMNS,
            [[r.name, fmt_qty(r.base), fmt_layer(r.flat, identity=0),
              fmt_layer(r.add, identity=0), fmt_layer(r.mult, identity=1), fmt_qty(r.final)]
             for r in rows],
            [[r.name, r.base, r.flat, r.add, r.mult, r.final] for r in rows])
        self.hint.setText(f'非零属性 {len(rows)} 项 / 全表 {len(list(StatType))} 项')
        self._refresh_scope()

    def set_panel_view(self, panel: dict):
        """游戏面板口径（导入时冻结）：列 = 平坦层 / 条件层 / 百分比加算 / 乘区 / 面板显示值。"""
        rows = panel.get('rows') or []
        # 条件层 0 / 百分比 0 / 乘区 1 都是「本层无贡献」：显示成 —，否则一屏十几个 0 与 1 会把
        # 真正有值的那几行淹掉（面板显示值仍是原始文本，不动）
        self.model.set_rows(
            self.PANEL_COLUMNS,
            [[stat_name(stat), fmt_qty(flat), fmt_layer(cond, identity=0),
              fmt_layer(pct, identity=0), fmt_layer(mult, identity=1), text]
             for stat, flat, cond, pct, mult, _final, text in rows],
            [[stat_name(stat), flat, cond, pct, mult, final]
             for stat, flat, cond, pct, mult, final, _text in rows])
        mode_cn = {'beta': 'β 逐件', 'alpha': 'α 聚合'}.get(panel.get('mode'), '')
        suffix = f'，{mode_cn}' if mode_cn else ''
        self.hint.setText(
            f'游戏面板口径（快照 {panel.get("time", "")}{suffix}；'
            f'血比例 {panel.get("hp_frac", 0.0):.0%}）— 与游戏「属性」页一致；'
            f'「最终值」列即面板显示，其余列为复算分解；编辑右侧角色面板不改变本表')
        self._refresh_scope()

    # ---------------- 常用 / 全部 ----------------
    def toggle_scope(self):
        """在「只看常用」与整表之间切换（默认常用）。"""
        self.proxy.set_only_common(not self.proxy.only_common())
        self._update_scope_ui()

    def _refresh_scope(self):
        """换口径后重算「常用项在本表里有几行」：一项都没有时自动退回全表，别给空表。"""
        self._common_hits = sum(
            1 for r in range(self.model.rowCount())
            if str(self.model.index(r, 0).data()) in _COMMON_NAMES)
        if not self._common_hits:
            self.proxy.set_only_common(False)
        self._update_scope_ui()

    def _update_scope_ui(self):
        only = self.proxy.only_common()
        total = self.model.rowCount()
        self.scope_btn.setEnabled(self._common_hits > 0)
        self.scope_btn.setText(f'显示全部 {total} 项' if only else '只看常用')
        # 常用态下收起三层分解列：内存导入的面板口径里它们整列都是「—」，白占一半宽度；
        # 要看分解点「显示全部 41 项」。只隐藏视图列，模型与导出列数仍是 6（自检守着）。
        for col in self._DETAIL_COLUMNS:
            self.table.setColumnHidden(col, only)
        self.hint.setToolTip(
            f'当前只列最常看的 {self._common_hits} 项；其余 {max(0, total - self._common_hits)} 项'
            '在「显示全部」里' if only else '当前显示整张表')

    # ---------------- 排序 ----------------
    def sort_by_column(self, col: int):
        """表头点击排序：数值列首次降序（先看大项），再点同列翻转；名称列首次升序。"""
        head = self.table.horizontalHeader()
        if self.table.isSortingEnabled() and head.sortIndicatorSection() == col:
            order = (Qt.AscendingOrder if head.sortIndicatorOrder() == Qt.DescendingOrder
                     else Qt.DescendingOrder)
        else:
            order = Qt.DescendingOrder if col >= 1 else Qt.AscendingOrder
        self.table.setSortingEnabled(True)     # 会先按当前指示器排一次，下面立即覆盖
        head.setSortIndicatorShown(True)
        self.table.sortByColumn(col, order)

    def reset_sort(self):
        """回到模型自身顺序（计算口径 |最终值| 降序 / 面板口径=游戏属性页行序）。"""
        self.proxy.sort(-1)
        self.table.setSortingEnabled(False)
        self.table.horizontalHeader().setSortIndicatorShown(False)

    def _apply_filter(self, text: str):
        self.proxy.setFilterFixedString(text.strip())

    def export_rows(self):
        """(表头, 行)：与屏幕一致（当前过滤后的行、当前显示的文本）。"""
        rows = [[self.proxy.index(r, c).data(Qt.DisplayRole)
                 for c in range(self.proxy.columnCount())]
                for r in range(self.proxy.rowCount())]
        return self.model.headers(), rows

    def _on_table_menu(self, pos):
        menu = QMenu(self)
        add_table_export(menu, self.export_rows, self, '属性明细')
        menu.exec(self.table.viewport().mapToGlobal(pos))
