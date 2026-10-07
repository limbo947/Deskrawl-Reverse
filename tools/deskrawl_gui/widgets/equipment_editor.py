# -*- coding: utf-8 -*-
"""中央 Tab1：装备对比（双武器编辑 + 结果区）。

武器编辑控件直接写回 profile 的 WeaponDraft；改动只需刷新本 Tab 的结果区，
不影响属性明细（武器词条在 compare_weapons 内部叠加，不进 base sheet）。
"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDoubleSpinBox,
                               QFormLayout, QGroupBox, QHBoxLayout, QHeaderView,
                               QLineEdit, QPushButton, QTableWidget, QVBoxLayout,
                               QWidget)

from deskrawl_calc import StatType, stat_name

from ..core import calc_service
from .compare_view import CompareView

_MOD_TYPES = [(0, '加法'), (1, '百分比加算'), (2, '连乘')]
_MOD_LABELS = dict(_MOD_TYPES)

# 装备词条的入池方式在游戏里是固定的「加法」：ItemData 固定属性 43 条、宝石/符文/套装加成
# 255 条实测 100% 为 Type 0（仅 3 条天赋在护甲/魔抗/荆棘上用百分比加算，且不来自装备）。
# 故类型完全由属性自动决定、下拉一律禁用，用户没有填错的余地。
_ALLOWED_TYPES = [0]

# 百分比类属性：数值本身是小数形式的百分比（0.30 = 30%）。这类属性必须提示「按小数填写」，
# 否则很容易把 30% 填成 30 —— 差 100 倍且不报错。
_PERCENT_STATS = frozenset(
    {4, 5, 6, 13, 15, 16, 17, 19, 22, 37, 41, 56, 57, 65}     # 暴击/攻速/冷却/掉落/闪避等
    | set(range(23, 35))                                       # 元素乘区23–28 + 条件29–32 + 普攻·强攻33–34
    | {40, 42, 43, 44, 45, 46, 48, 49, 51, 52, 53, 54, 55, 58,
       59, 60, 61, 62, 63, 64}                                 # 其余条件/技能/生存百分比项
)

_TIP_PERCENT = '百分比类属性：数值按小数填写（0.3000 = 30%）；入池方式由游戏固定为「加法」'
_TIP_FLAT = '数值属性：直接填数值；入池方式由游戏固定为「加法」'
_TIP_VALUE_PERCENT = '按小数填写，例：0.3000 = 30%'


class AffixTable(QTableWidget):
    """武器词条行表：属性（内核 StatType 全量中文名）/ 类型 / 数值 / 删除。"""

    changed = Signal()
    COLUMNS = ['属性', '类型', '数值', '']

    def __init__(self, parent=None):
        super().__init__(0, len(self.COLUMNS), parent)
        self._loading = False
        self.setHorizontalHeaderLabels(self.COLUMNS)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.setMinimumHeight(150)

    def set_affixes(self, affixes):
        self._loading = True
        self.setRowCount(0)
        for stat, mtype, value in affixes:
            self._add_row(stat, mtype, value)
        self._loading = False

    def affixes(self) -> list:
        out = []
        for r in range(self.rowCount()):
            out.append([int(self.cellWidget(r, 0).currentData()),
                        int(self.cellWidget(r, 1).currentData()),
                        float(self.cellWidget(r, 2).value())])
        return out

    def append_row(self):
        self._add_row(int(StatType.DamagePhysical), 0, 0.0)
        self._emit()

    def _add_row(self, stat, mtype, value):
        row = self.rowCount()
        self.insertRow(row)

        stat_combo = QComboBox()
        for st in StatType:
            stat_combo.addItem(stat_name(st), int(st))

        type_combo = QComboBox()
        spin = QDoubleSpinBox()
        spin.setRange(-1e6, 1e6)
        spin.setDecimals(4)

        btn = QPushButton('×')
        btn.setFixedWidth(28)

        self.setCellWidget(row, 0, stat_combo)
        self.setCellWidget(row, 1, type_combo)
        self.setCellWidget(row, 2, spin)
        self.setCellWidget(row, 3, btn)

        # 先填初值再接信号：构造期的索引/数值变化既不该触发刷新，也不能被误当作用户改属性
        idx = stat_combo.findData(int(stat))
        stat_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._fill_types(type_combo, int(mtype))
        self._apply_hints(int(stat_combo.currentData()), type_combo, spin)
        spin.setValue(float(value))

        stat_combo.currentIndexChanged.connect(
            lambda *_, sc=stat_combo, tc=type_combo, sp=spin: self._on_stat_changed(sc, tc, sp))
        type_combo.currentIndexChanged.connect(self._emit)
        spin.valueChanged.connect(self._emit)
        btn.clicked.connect(lambda: self._remove_row(btn))

    def _on_stat_changed(self, stat_combo, type_combo, spin):
        """属性切换 → 类型自动回到该属性的规范值（物品词条在游戏里恒为加法），并刷新填写提示。"""
        if self._loading:
            return
        stat = int(stat_combo.currentData())
        self._fill_types(type_combo, 0)
        self._apply_hints(stat, type_combo, spin)
        self._emit()

    def _fill_types(self, combo, keep):
        """类型栏固定展示游戏唯一入池方式「加法」并禁用；旧构建里的非常规组合原样只读展示，
        避免静默改写数据（保存时仍原样写回）。"""
        types = list(_ALLOWED_TYPES)
        if int(keep) not in types:
            types = [int(keep)]
        combo.blockSignals(True)
        combo.clear()
        for t in types:
            combo.addItem(_MOD_LABELS[t], t)
        combo.setCurrentIndex(0)
        combo.blockSignals(False)
        combo.setEnabled(False)

    def _apply_hints(self, stat, type_combo, spin):
        """百分比类属性必须明示「按小数填写」，否则很容易把 30% 填成 30。"""
        frac = int(stat) in _PERCENT_STATS
        type_combo.setToolTip(_TIP_PERCENT if frac else _TIP_FLAT)
        spin.setToolTip(_TIP_VALUE_PERCENT if frac else '')

    def _remove_row(self, btn):
        for r in range(self.rowCount()):
            if self.cellWidget(r, 3) is btn:
                self.removeRow(r)
                break
        self._emit()

    def _emit(self, *_):
        if not self._loading:
            self.changed.emit()


class WeaponEditor(QGroupBox):
    """一把武器的编辑面板（名称 / 基础伤害 / 攻速 / 技能倍率 / 词条行）。"""

    changed = Signal()

    def __init__(self, title, draft, parent=None):
        super().__init__(title, parent)
        self._loading = False
        self.draft = draft
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self._on_name)
        self.damage_spin = self._spin(form, '基础伤害', 0.0, 1e6, 2, 'base_damage')
        self.speed_spin = self._spin(form, '攻速(次/秒)', 0.0, 20.0, 3, 'base_speed')
        self.skill_spin = self._spin(form, '技能倍率', 0.0, 100.0, 3, 'skill_multiplier')
        form.addRow('名称', self.name_edit)

        self.affixes = AffixTable()
        self.affixes.changed.connect(self._on_affixes)
        add_btn = QPushButton('添加词条')
        add_btn.clicked.connect(self.affixes.append_row)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(self.affixes)
        root.addWidget(add_btn)
        self.reload()

    def _spin(self, form, label, lo, hi, decimals, attr) -> QDoubleSpinBox:
        sp = QDoubleSpinBox()
        sp.setRange(lo, hi)
        sp.setDecimals(decimals)
        sp.valueChanged.connect(lambda v, a=attr: self._on_num(a, v))
        form.addRow(label, sp)
        return sp

    def set_draft(self, draft):
        self.draft = draft
        self.reload()

    def reload(self):
        self._loading = True
        self.name_edit.setText(self.draft.name)
        self.damage_spin.setValue(self.draft.base_damage)
        self.speed_spin.setValue(self.draft.base_speed)
        self.skill_spin.setValue(self.draft.skill_multiplier)
        self.affixes.set_affixes(self.draft.affixes)
        self._loading = False

    def _on_name(self, text):
        if self._loading:
            return
        self.draft.name = text
        self.changed.emit()

    def _on_num(self, attr, value):
        if self._loading:
            return
        setattr(self.draft, attr, float(value))
        self.changed.emit()

    def _on_affixes(self):
        self.draft.affixes = self.affixes.affixes()
        self.changed.emit()


class EquipmentEditor(QWidget):
    def __init__(self, profile, gd, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.gd = gd
        self.current_editor = WeaponEditor('当前武器', profile.weapon_current)
        self.candidate_editor = WeaponEditor('候选武器', profile.weapon_candidate)
        self.compare_view = CompareView()

        top = QHBoxLayout()
        top.addWidget(self.current_editor, 1)
        top.addWidget(self.candidate_editor, 1)
        root = QVBoxLayout(self)
        root.addLayout(top)
        root.addWidget(self.compare_view, 1)

        self.current_editor.changed.connect(self.refresh)
        self.candidate_editor.changed.connect(self.refresh)
        self.refresh()

    def refresh(self):
        """重算并渲染结果区（纯计算，不改动输入控件）。"""
        self.compare_view.set_result(calc_service.compare(self.profile, self.gd))

    def reload(self):
        """从 profile 回填输入（换构建时用），随后重算。"""
        self.current_editor.set_draft(self.profile.weapon_current)
        self.candidate_editor.set_draft(self.profile.weapon_candidate)
        self.refresh()
