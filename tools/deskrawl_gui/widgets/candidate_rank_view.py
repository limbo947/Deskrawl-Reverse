# -*- coding: utf-8 -*-
"""中央 Tab2：候选排序表（名称/效果/DPS/ΔDPS/Δ%，可排序，双击加入构建）。

排序由 QSortFilterProxyModel 完成；为数值列提供 UserRole 排序键，避免按字符串排序出错。
计算走 calc_service.rank_candidates（基线 = 当前构建不加候选）。
"""
from PySide6.QtCore import (QAbstractTableModel, QModelIndex, QSortFilterProxyModel,
                            Qt, Signal)
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView,
                               QLabel, QPushButton, QSpinBox, QTableView, QVBoxLayout,
                               QWidget)

from ..core import calc_service
from ..core.profile import KIND_LABELS, KIND_ORDER, AssemblyItem

_SLOTS = [(0, '护甲'), (1, '饰品'), (2, '武器')]
_LEVEL_LABEL = {'rune': '符文等级', 'talent': '天赋点数', 'runeset': '套装件数'}


class _RankModel(QAbstractTableModel):
    COLUMNS = ['名称', '效果', '期望 DPS', 'ΔDPS', 'Δ%']

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []
        self._alpha = False

    def set_alpha(self, alpha: bool):
        """α 聚合导入下，百分比类词条增量为近似（面板抹掉了池结构），行上加显式标注。"""
        self._alpha = bool(alpha)

    def set_rows(self, rows):
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def row_at(self, index: int):
        return self._rows[index]

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.COLUMNS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        r = self._rows[index.row()]
        col = index.column()
        if role == Qt.UserRole:      # 排序键：名称/效果按字符串，数值列按 float
            return [r.name, r.detail, r.dps, r.delta, r.delta_pct][col]
        if role == Qt.DisplayRole:
            detail = r.detail
            if col == 1 and self._alpha and any(int(m.type) != 0 for m in r.modifiers):
                detail += '（近似）'
            return [r.name, detail, f'{r.dps:.1f}', f'{r.delta:+.1f}',
                    f'{r.delta_pct:+.2f}%'][col]
        if role == Qt.TextAlignmentRole and col >= 2:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return None


class CandidateRankView(QWidget):
    changed = Signal()

    def __init__(self, profile, gd, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.gd = gd

        self.kind_combo = QComboBox()
        for kind, label in KIND_ORDER:
            self.kind_combo.addItem(label, kind)
        self.kind_combo.currentIndexChanged.connect(self._on_kind)

        self.level_spin = QSpinBox()
        self.level_spin.setRange(1, 999)
        self.level_spin.valueChanged.connect(self.refresh)

        self.slot_combo = QComboBox()
        for value, label in _SLOTS:
            self.slot_combo.addItem(label, value)
        self.slot_combo.setCurrentIndex(2)      # 默认武器孔：本工具以「武器对比」为主，护甲孔宝石多半不加 DPS
        self.slot_combo.currentIndexChanged.connect(self.refresh)

        self.param_label = QLabel('镶嵌部位')
        refresh_btn = QPushButton('刷新排序')
        refresh_btn.clicked.connect(self.refresh)

        bar = QHBoxLayout()
        bar.addWidget(QLabel('类别'))
        bar.addWidget(self.kind_combo)
        bar.addWidget(self.param_label)
        bar.addWidget(self.level_spin)
        bar.addWidget(self.slot_combo)
        bar.addWidget(refresh_btn)
        bar.addStretch(1)

        self.hint = QLabel('—')
        self.model = _RankModel()
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(Qt.UserRole)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.doubleClicked.connect(self._on_double_clicked)

        tip = QLabel('提示：双击一行可把该候选按当前等级/点数加入构建。')
        root = QVBoxLayout(self)
        root.addLayout(bar)
        root.addWidget(self.hint)
        root.addWidget(self.table, 1)
        root.addWidget(tip)
        self._on_kind()

    # ---------------- 参数 ----------------
    def current_kind(self) -> str:
        return self.kind_combo.currentData()

    def _params(self):
        kind = self.current_kind()
        if kind == 'gem':
            return 1, int(self.slot_combo.currentData())
        return int(self.level_spin.value()), 2

    def _on_kind(self):
        kind = self.current_kind()
        is_gem = kind == 'gem'
        self.level_spin.setVisible(not is_gem)
        self.slot_combo.setVisible(is_gem)
        self.param_label.setText('镶嵌部位' if is_gem else _LEVEL_LABEL[kind])
        self.refresh()

    # ---------------- 计算与渲染 ----------------
    def refresh(self):
        kind = self.current_kind()
        level, category = self._params()
        rows = calc_service.rank_candidates(self.profile, self.gd, kind,
                                           level=level, category=category)
        alpha = getattr(self.profile, 'import_mode', '') == 'alpha'
        self.model.set_alpha(alpha)
        self.model.set_rows(rows)
        hint = (f'{KIND_LABELS[kind]}候选 {len(rows)} 条；基线 DPS = '
                f'{calc_service.baseline_dps(self.profile, self.gd):.1f}')
        if alpha:
            hint += '；α 聚合导入：基线=游戏面板，百分比类（非加法）词条增量为近似'
        self.hint.setText(hint)

    def _on_double_clicked(self, proxy_index):
        src = self.proxy.mapToSource(proxy_index)
        if not src.isValid():
            return
        row = self.model.row_at(src.row())
        kind = self.current_kind()
        level, category = self._params()
        self.profile.assembled.append(AssemblyItem(kind, row.name, level, category))
        self.changed.emit()
