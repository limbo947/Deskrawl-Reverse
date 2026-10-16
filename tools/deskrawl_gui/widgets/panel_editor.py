# -*- coding: utf-8 -*-
"""角色页：面板编辑（等级 / 三维 / 巅峰点数）。

控件直接写回 CharacterProfile（唯一事实源），改动后发 changed 由主窗口统一刷新；
控件自身不做任何计算，避免同一份状态在两处维护。reload() 期间用 _loading 抑制信号，
防止「回填 UI」被误判成「用户编辑」而触发递归刷新。
参考技能卡片已迁往装备对比页（widgets/skill_card.py）：它是换装预测的基线口径，与目标设置同屏。
"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox,
                               QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)
from PySide6.QtWidgets import QHeaderView

from deskrawl_calc import StatType, stat_name

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
        # 职业主属性：攻击伤害 ×(1+最终值/100)（Player.CalcDamage@0x518230）；内存导入自动识别，手工构建在此选择
        self.primary_combo = QComboBox()
        self.primary_combo.addItem('（未设置）', None)
        for st, label in ((StatType.Strength, '力量'), (StatType.Dexterity, '敏捷'),
                          (StatType.Intelligence, '智力')):
            self.primary_combo.addItem(label, int(st))
        self.primary_combo.setToolTip('职业主属性：攻击伤害按 ×(1+该属性最终值/100) 加成'
                                      '（游戏公式 Player.CalcDamage@0x518230）；内存导入自动识别')
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
        self._loading = False

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
