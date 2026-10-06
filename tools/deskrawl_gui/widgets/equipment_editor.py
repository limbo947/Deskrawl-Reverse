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
        idx = stat_combo.findData(int(stat))
        stat_combo.setCurrentIndex(idx if idx >= 0 else 0)
        stat_combo.currentIndexChanged.connect(self._emit)

        type_combo = QComboBox()
        for t, label in _MOD_TYPES:
            type_combo.addItem(label, t)
        idx = type_combo.findData(int(mtype))
        type_combo.setCurrentIndex(idx if idx >= 0 else 0)
        type_combo.currentIndexChanged.connect(self._emit)

        spin = QDoubleSpinBox()
        spin.setRange(-1e6, 1e6)
        spin.setDecimals(4)
        spin.setValue(float(value))
        spin.valueChanged.connect(self._emit)

        btn = QPushButton('×')
        btn.setFixedWidth(28)
        btn.clicked.connect(lambda: self._remove_row(btn))

        self.setCellWidget(row, 0, stat_combo)
        self.setCellWidget(row, 1, type_combo)
        self.setCellWidget(row, 2, spin)
        self.setCellWidget(row, 3, btn)

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
