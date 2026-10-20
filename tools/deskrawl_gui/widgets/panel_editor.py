# -*- coding: utf-8 -*-
"""角色页：面板编辑（等级 / 三维 / 巅峰点数）。

控件直接写回 CharacterProfile（唯一事实源），改动后发 changed 由主窗口统一刷新；
控件自身不做任何计算，避免同一份状态在两处维护。reload() 期间用 ReloadGuard 抑制事件，
防止「回填 UI」被误判成「用户编辑」而触发递归刷新。
参考技能卡片已迁往装备对比页（widgets/skill_card.py）：它是换装预测的基线口径，与目标设置同屏。
"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QComboBox, QFormLayout, QGroupBox, QLabel,
                               QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)
from PySide6.QtWidgets import QHeaderView

from deskrawl_calc import StatType, stat_name

from ..core.heroes import hero_class_options
from .common import QtySpinBox, ReloadGuard

# 基础面板里直接映射到 StatType 的输入项
_BASE_FIELDS = [(StatType.Strength, '力量'), (StatType.Dexterity, '敏捷'),
                (StatType.Intelligence, '智力'), (StatType.WeaponDamage, '武器伤害(面板)')]


class PanelEditor(ReloadGuard, QWidget):
    changed = Signal()

    def __init__(self, profile, gd, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.gd = gd
        self._base_spins = {}
        self._paragon_spins = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)
        root.addWidget(self._build_base_group())
        root.addWidget(self._build_paragon_group(), 1)
        self.reload()

    # ---------------- UI 构建 ----------------
    def _build_base_group(self) -> QGroupBox:
        box = QGroupBox('角色面板')
        form = QFormLayout(box)
        self.level_spin = QSpinBox()
        self.level_spin.setRange(1, max(2, int(self.gd.max_player_level() or 100)))
        self.level_spin.valueChanged.connect(self._on_level)
        form.addRow('等级', self.level_spin)
        # 职业是角色本体：它决定技能清单与技能倍率，归位到面板（B4）。
        # 对比页改为只读展示——同一概念两处入口，用户永远要先想「该在哪改」。
        self.class_combo = QComboBox()
        self.class_combo.addItem('（未设置）', None)
        for value, label in hero_class_options(self.gd):
            self.class_combo.addItem(label, value)
        self.class_combo.setToolTip('职业决定技能秒伤表列出哪些技能（HeroData.Class 派生）；'
                                    '内存导入会自动识别')
        self.class_combo.currentIndexChanged.connect(self._on_class)
        form.addRow('职业', self.class_combo)
        for st, label in _BASE_FIELDS:
            sp = QtySpinBox(decimals=2)
            sp.setRange(-1e6, 1e6)
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
        # 15 行里通常只有 2–3 行非零，光看一屏 0 分不清「没分配」与「这行没用」——用一句计数说清，
        # 而不隐藏 0 行：行一旦消失就没法从 0 加点（过滤式「只显示非零」在这里是反向的）。
        self.paragon_hint = QLabel('—')
        self.paragon_hint.setObjectName('pageSubtitle')
        self.paragon_hint.setWordWrap(True)     # 窄栏里一句话会被卡片边裁断，宁可折两行
        lay.addWidget(self.paragon_hint)
        stats = self.gd.paragon_stats()
        table = QTableWidget(len(stats), 2)
        table.setAccessibleName('巅峰点数分配表')
        table.setHorizontalHeaderLabels(['属性', '点数'])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        # 与其它四张表同一套行分隔语言：斑马纹替代网格线（默认会画出网格，成为全界面唯一的方格表）
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
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
        """把 profile 的值灌进控件；回填期间的事件不算用户编辑（见 ReloadGuard）。"""
        with self.reloading():
            self.level_spin.setValue(int(self.profile.level))
            for st, sp in self._base_spins.items():
                sp.setValue(float(self.profile.base.get(st, 0.0)))
            ps = self.profile.primary_stat
            idx = self.primary_combo.findData(int(ps)) if ps is not None else 0
            self.primary_combo.setCurrentIndex(idx if idx >= 0 else 0)
            hc = self.profile.hero_class
            ci = self.class_combo.findData(int(hc)) if hc is not None else 0
            self.class_combo.setCurrentIndex(ci if ci >= 0 else 0)
            for st, sp in self._paragon_spins.items():
                sp.setValue(int(self.profile.paragon.get(st, 0)))
        self._update_paragon_hint()

    def _update_paragon_hint(self):
        used = sum(1 for v in self.profile.paragon.values() if v)
        self.paragon_hint.setText(f'已分配 {used} 项 / 共 {len(self._paragon_spins)} 项；'
                                  f'未分配的行保留在此，可直接从 0 加点')

    def _on_level(self, v):
        if self.loading:
            return
        self.profile.level = int(v)
        self.changed.emit()

    def _on_base(self, stat, v):
        if self.loading:
            return
        self.profile.base[stat] = float(v)
        self.changed.emit()

    def _on_class(self, *_):
        """职业写回 profile：技能表列出哪些技能由它决定（对比页只读展示本值）。"""
        if self.loading:
            return
        data = self.class_combo.currentData()
        self.profile.hero_class = None if data is None else int(data)
        self.changed.emit()

    def _on_primary(self, *_):
        if self.loading:
            return
        data = self.primary_combo.currentData()
        self.profile.primary_stat = None if data is None else int(data)
        self.changed.emit()

    def _on_paragon(self, stat, pts):
        if self.loading:
            return
        if pts:
            self.profile.paragon[stat] = int(pts)
        else:
            self.profile.paragon.pop(stat, None)
        self._update_paragon_hint()
        self.changed.emit()
