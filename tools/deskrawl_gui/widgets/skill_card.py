# -*- coding: utf-8 -*-
"""参考技能卡片（装备对比页右栏，目标基础卡片下方）。

从 panel_editor 迁出并搬家：技能等级与倍率是「循环系数 / 换装预测」的基线口径，与目标设置、
实测框同屏才谈得上「设目标 → 定参考技能 → 读预测」的一步动线；留在角色页时用户得来回切页核对。
控件写回 profile（唯一事实源），改动只发 changed，由页面层转发进全局刷新链。
"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QLabel, QSpinBox

from ..core.localization import ability_display_name
from ..core.skill_service import ability_level_bonuses
from .common import ReloadGuard


class SkillCard(ReloadGuard, QGroupBox):
    """参考技能（唯一入口）：职业决定可选清单，倍率文案含符文带来的有效等级。"""

    changed = Signal()

    def __init__(self, profile, gd, parent=None):
        super().__init__('技能（仅作参考倍率）', parent)
        self.profile = profile
        self.gd = gd
        form = QFormLayout(self)
        self.skill_combo = QComboBox()
        self.skill_combo.currentIndexChanged.connect(self._on_skill)
        cfg = self.gd.game_config()
        self.skill_level_spin = QSpinBox()
        self.skill_level_spin.setRange(1, max(1, int(cfg.get('MaxAbilityLevel') or 20)))
        self.skill_level_spin.valueChanged.connect(self._on_skill)
        self.skill_info = QLabel('—')
        # 文案里带倍率数字：走等宽栈（#skillInfo 在 QSS 里定义字族），汉字仍由雅黑逐字回落
        self.skill_info.setObjectName('skillInfo')
        self.skill_info.setWordWrap(True)
        form.addRow('技能', self.skill_combo)
        form.addRow('等级', self.skill_level_spin)
        form.addRow('攻击倍率', self.skill_info)
        self._options_class = object()       # 哨兵：与任何 hero_class 都不同，强制首次构建
        self.refresh_skill_options()
        self.reload()

    def refresh(self):
        """页面刷新链入口：职业可能已变（重列技能），倍率文案随等级/符文更新。"""
        self.refresh_skill_options()
        self._update_skill_info()

    def refresh_skill_options(self):
        """按当前职业重建技能下拉（中文名），职业变更时由页面刷新链调用。

        数据源 = 该职业 HeroData.Abilities（排除敌人技能；未设职业取全职业并集兜底）。
        显示用简中名（本地化表），data 保留 _name 供倍率/主力技能查表；职业未变时跳过重建，
        避免每次全局刷新都打断用户正在进行的下拉选择。
        """
        hc = getattr(self.profile, 'hero_class', None)
        if hc == self._options_class:
            return
        self._options_class = hc
        if hc is not None:
            names = self.gd.abilities_for_class(hc)
        else:
            names = sorted({n for h in self.gd.heroes().values()
                            for n in self.gd.abilities_for_class(h.get('Class'))})
        current = self.profile.skill_name
        self.skill_combo.blockSignals(True)
        self.skill_combo.clear()
        self.skill_combo.addItem('（不使用）', '')
        for name in names:
            self.skill_combo.addItem(ability_display_name(self.gd, name), name)
        idx = self.skill_combo.findData(current)
        self.skill_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.skill_combo.blockSignals(False)

    # ---------------- 回填 / 事件 ----------------
    def reload(self):
        """把 profile 的值灌进控件；回填期间的事件不算用户编辑（见 ReloadGuard）。"""
        with self.reloading():
            idx = self.skill_combo.findData(self.profile.skill_name)
            self.skill_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self.skill_level_spin.setValue(int(self.profile.skill_level))
        self._update_skill_info()

    def _on_skill(self, *_):
        if self.loading:
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
        # 有效等级 = 基础等级 + 符文「技能等级+N」（如旋风斩 10+8=18，tooltip 185% 同源）
        bonus = ability_level_bonuses(self.profile, self.gd)
        eff = int(self.profile.skill_level) + bonus.get('*', 0) + bonus.get(name, 0)
        mult = self.gd.ability_attack_scaling(name, eff)
        extra = f'，有效等级 {eff}' if eff != int(self.profile.skill_level) else ''
        self.skill_info.setText(f'攻击倍率 ≈ {mult:.4f}（{extra}；参考值，实际以武器编辑区倍率为准）')
