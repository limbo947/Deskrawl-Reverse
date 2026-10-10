# -*- coding: utf-8 -*-
"""左 dock：角色面板编辑（等级 / 三维 / 巅峰 / 技能）。

控件直接写回 CharacterProfile（唯一事实源），改动后发 changed 由主窗口统一刷新；
控件自身不做任何计算，避免同一份状态在两处维护。reload() 期间用 _loading 抑制信号，
防止「回填 UI」被误判成「用户编辑」而触发递归刷新。
"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox,
                               QLabel, QSpinBox, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)
from PySide6.QtWidgets import QHeaderView

from deskrawl_calc import StatType, stat_name

from ..core.calc_service import ability_names

# 基础面板里直接映射到 StatType 的输入项
_BASE_FIELDS = [(StatType.Strength, '力量'), (StatType.Dexterity, '敏捷'),
                (StatType.Intelligence, '智力'), (StatType.WeaponDamage, '武器伤害(面板)')]


class PanelEditor(QWidget):
    changed = Signal()

    def __init__(self, profile, gd, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.gd = gd
        self._loading = False
        self._base_spins = {}
        self._paragon_spins = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.addWidget(self._build_base_group())
        root.addWidget(self._build_paragon_group(), 1)
        root.addWidget(self._build_skill_group())
        self.reload()

    # ---------------- UI 构建 ----------------
    def _build_base_group(self) -> QGroupBox:
        box = QGroupBox('基础面板')
        form = QFormLayout(box)
        self.level_spin = QSpinBox()
        self.level_spin.setRange(1, max(2, int(self.gd.max_player_level() or 100)))
        self.level_spin.valueChanged.connect(self._on_level)
        form.addRow('等级', self.level_spin)
        for st, label in _BASE_FIELDS:
            sp = QDoubleSpinBox()
            sp.setRange(-1e6, 1e6)
            sp.setDecimals(2)
            sp.valueChanged.connect(lambda v, s=int(st): self._on_base(s, v))
            self._base_spins[int(st)] = sp
            form.addRow(label, sp)
        # 职业主属性：攻击伤害 ×(1+最终值/100)（Player.CalcDamage@0x50E400）；内存导入自动识别，手工构建在此选择
        self.primary_combo = QComboBox()
        self.primary_combo.addItem('（未设置）', None)
        for st, label in ((StatType.Strength, '力量'), (StatType.Dexterity, '敏捷'),
                          (StatType.Intelligence, '智力')):
            self.primary_combo.addItem(label, int(st))
        self.primary_combo.setToolTip('职业主属性：攻击伤害按 ×(1+该属性最终值/100) 加成'
                                      '（游戏公式 Player.CalcDamage@0x50E400）；内存导入自动识别')
        self.primary_combo.currentIndexChanged.connect(self._on_primary)
        form.addRow('职业主属性', self.primary_combo)
        return box

    def _build_paragon_group(self) -> QGroupBox:
        box = QGroupBox('巅峰点数')
        lay = QVBoxLayout(box)
        stats = self.gd.paragon_stats()
        table = QTableWidget(len(stats), 2)
        table.setHorizontalHeaderLabels(['属性', '点数'])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for i, p in enumerate(stats):
            st = int(p['Stat'])
            table.setItem(i, 0, QTableWidgetItem(stat_name(st)))
            sp = QSpinBox()
            cap = int(p.get('MaxPoints') or 0)
            sp.setRange(0, cap if cap > 0 else 999)
            sp.valueChanged.connect(lambda v, s=st: self._on_paragon(s, v))
            self._paragon_spins[st] = sp
            table.setCellWidget(i, 1, sp)
        lay.addWidget(table)
        return box

    def _build_skill_group(self) -> QGroupBox:
        box = QGroupBox('技能（仅作参考倍率）')
        form = QFormLayout(box)
        self.skill_combo = QComboBox()
        self.skill_combo.addItem('（不使用）', '')
        for name in ability_names(self.gd):
            self.skill_combo.addItem(name, name)
        self.skill_combo.currentIndexChanged.connect(self._on_skill)
        cfg = self.gd.game_config()
        self.skill_level_spin = QSpinBox()
        self.skill_level_spin.setRange(1, max(1, int(cfg.get('MaxAbilityLevel') or 20)))
        self.skill_level_spin.valueChanged.connect(self._on_skill)
        self.skill_info = QLabel('—')
        self.skill_info.setWordWrap(True)
        form.addRow('技能', self.skill_combo)
        form.addRow('等级', self.skill_level_spin)
        form.addRow('攻击倍率', self.skill_info)
        return box

    # ---------------- 回填 / 事件 ----------------
    def reload(self):
        """把 profile 的值灌进控件。期间置 _loading，避免触发 changed 递归。"""
        self._loading = True
        self.level_spin.setValue(int(self.profile.level))
        for st, sp in self._base_spins.items():
            sp.setValue(float(self.profile.base.get(st, 0.0)))
        ps = self.profile.primary_stat
        idx = self.primary_combo.findData(int(ps)) if ps is not None else 0
        self.primary_combo.setCurrentIndex(idx if idx >= 0 else 0)
        for st, sp in self._paragon_spins.items():
            sp.setValue(int(self.profile.paragon.get(st, 0)))
        idx = self.skill_combo.findData(self.profile.skill_name)
        self.skill_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.skill_level_spin.setValue(int(self.profile.skill_level))
        self._loading = False
        self._update_skill_info()

    def _on_level(self, v):
        if self._loading:
            return
        self.profile.level = int(v)
        self.changed.emit()

    def _on_base(self, stat, v):
        if self._loading:
            return
        self.profile.base[stat] = float(v)
        self.changed.emit()

    def _on_primary(self, *_):
        if self._loading:
            return
        data = self.primary_combo.currentData()
        self.profile.primary_stat = None if data is None else int(data)
        self.changed.emit()

    def _on_paragon(self, stat, pts):
        if self._loading:
            return
        if pts:
            self.profile.paragon[stat] = int(pts)
        else:
            self.profile.paragon.pop(stat, None)
        self.changed.emit()

    def _on_skill(self, *_):
        if self._loading:
            return
        self.profile.skill_name = self.skill_combo.currentData() or ''
        self.profile.skill_level = int(self.skill_level_spin.value())
        self._update_skill_info()
        self.changed.emit()

    def _update_skill_info(self):
        name = self.profile.skill_name
        if not name:
            self.skill_info.setText('（不使用技能；倍率请直接填在武器编辑区）')
            return
        mult = self.gd.ability_attack_scaling(name, int(self.profile.skill_level))
        self.skill_info.setText(f'攻击倍率 ≈ {mult:.4f}（参考值；实际计算以武器编辑区的技能倍率为准）')
