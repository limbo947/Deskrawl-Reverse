# -*- coding: utf-8 -*-
"""中央 Tab1：装备对比（11 槽位切换 + 当前/候选双编辑器 + 结果区）。

槽位 = 内存快照的 slot id（0=武器，1..10=其余十件，不含披风/Back=11）；武器槽沿用
WeaponDraft（多出基础伤害/攻速/技能倍率），其余槽用 ItemDraft。切换槽时按槽重建两侧编辑器并
把候选下拉改为该槽可用的背包/仓库装备。编辑只改 profile 草稿，改动刷新本 Tab 结果区
（装备词条在 compare 内部处理，不进 base sheet）。
"""
import copy

from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QSpinBox, QVBoxLayout, QWidget)

from ..core import calc_service, skill_service
from ..core.item_draft import ItemDraft
from ..core.profile import COMPARE_SLOTS, SLOT_EQUIP_TYPE, SLOT_LABELS
from .compare_view import CompareView
from .item_editor import ItemEditor

# 职业下拉（HeroClass 枚举值）：手工构建时用户自选；内存导入自动识别 HeroData.Class。
_HERO_CLASSES = [(None, '（未设置）'), (1, '野蛮人'), (2, '法师'), (4, '猎人'), (8, '武僧')]


class EquipmentEditor(QWidget):
    # α 聚合导入没有逐件装备可分解：当前槽没有真实数据，对比语义降级为
    # 「基线（=游戏面板）vs 基线+候选词条」，并把百分比类增量是近似这一点显式说明。
    ALPHA_NOTICE = ('α 聚合模式（快照无逐件装备）：当前装备不可分解，对比降级为'
                    '「基线 vs 基线+候选词条」；候选的百分比类词条增量为近似值。')

    def __init__(self, profile, gd, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.gd = gd

        self.slot_combo = QComboBox()
        for slot, label in COMPARE_SLOTS:
            self.slot_combo.addItem(label, slot)
        self.slot_combo.currentIndexChanged.connect(self._on_slot)

        # 候选快捷导入：内存导入冻结的背包/仓库装备（bag_items），按当前槽类型过滤。
        self.bag_combo = QComboBox()
        self.bag_combo.currentIndexChanged.connect(self._on_bag_selected)

        # 技能区参数：职业（决定列出哪些伤害技能）+ 统一技能等级（快照暂无逐技能等级）。
        self.class_combo = QComboBox()
        for value, label in _HERO_CLASSES:
            self.class_combo.addItem(label, value)
        self.class_combo.currentIndexChanged.connect(self._on_class)
        max_lv = max(1, int(self.gd.game_config().get('MaxAbilityLevel') or 20))
        self.skill_level_spin = QSpinBox()
        self.skill_level_spin.setRange(1, max_lv)
        self.skill_level_spin.valueChanged.connect(self._on_skill_level)

        self.compare_view = CompareView()

        self.alpha_banner = QLabel(self.ALPHA_NOTICE)
        self.alpha_banner.setWordWrap(True)
        self.alpha_banner.setVisible(False)

        self._cur_holder = QWidget()
        self._cur_lay = QVBoxLayout(self._cur_holder)
        self._cur_lay.setContentsMargins(0, 0, 0, 0)
        self._cand_holder = QWidget()
        self._cand_lay = QVBoxLayout(self._cand_holder)
        self._cand_lay.setContentsMargins(0, 0, 0, 0)
        self.current_editor = None
        self.candidate_editor = None

        cand_side = QWidget()
        cand_lay = QVBoxLayout(cand_side)
        cand_lay.setContentsMargins(0, 0, 0, 0)
        bag_bar = QHBoxLayout()
        bag_bar.addWidget(QLabel('从背包/仓库导入:'))
        bag_bar.addWidget(self.bag_combo, 1)
        cand_lay.addLayout(bag_bar)
        cand_lay.addWidget(self._cand_holder, 1)

        slot_bar = QHBoxLayout()
        slot_bar.addWidget(QLabel('装备槽'))
        slot_bar.addWidget(self.slot_combo)
        slot_bar.addSpacing(12)
        slot_bar.addWidget(QLabel('职业（技能表）'))
        slot_bar.addWidget(self.class_combo)
        slot_bar.addWidget(QLabel('技能等级'))
        slot_bar.addWidget(self.skill_level_spin)
        slot_bar.addStretch(1)

        top = QHBoxLayout()
        top.addWidget(self._cur_holder, 1)
        top.addWidget(cand_side, 1)
        root = QVBoxLayout(self)
        root.addLayout(slot_bar)
        root.addWidget(self.alpha_banner)
        root.addLayout(top)
        root.addWidget(self.compare_view, 1)

        self.reload()

    # ---------------- 槽位与草稿 ----------------
    def _drafts(self):
        """当前槽的 (current, candidate) 草稿；非武器槽按需就地建空草稿。"""
        slot = int(self.profile.compare_slot)
        if slot == 0:
            return slot, self.profile.weapon_current, self.profile.weapon_candidate
        cur = self.profile.slot_current.setdefault(slot, ItemDraft())
        cand = self.profile.slot_candidate.setdefault(slot, ItemDraft())
        return slot, cur, cand

    def _build_editors(self):
        """按当前槽重建两侧编辑器（武器槽多武器三行），并接回刷新信号。"""
        slot, cur, cand = self._drafts()
        # 首次进入某槽且候选为空时，用当前件预填候选：默认 Δ=0，用户改哪条就是哪条的影响
        if (not cand.name and not cand.affixes) and (cur.name or cur.affixes):
            cand.__dict__.update(copy.deepcopy(cur.__dict__))
        weapon = (slot == 0)
        label = SLOT_LABELS.get(slot, f'槽{slot}')
        self.current_editor = ItemEditor(f'当前{label}', cur, weapon=weapon)
        self.candidate_editor = ItemEditor(f'候选{label}', cand, weapon=weapon)
        self.current_editor.changed.connect(self.refresh)
        self.candidate_editor.changed.connect(self.refresh)
        self._replace(self._cur_lay, self.current_editor)
        self._replace(self._cand_lay, self.candidate_editor)

    @staticmethod
    def _replace(lay, widget):
        while lay.count():
            old = lay.takeAt(0).widget()
            if old is not None:
                old.deleteLater()
        lay.addWidget(widget)

    def _on_slot(self):
        self.profile.compare_slot = int(self.slot_combo.currentData())
        self._build_editors()
        self._reload_bag_combo()
        self.refresh()

    def _on_class(self, *_):
        value = self.class_combo.currentData()
        self.profile.hero_class = None if value is None else int(value)
        self.refresh()

    def _on_skill_level(self, value):
        self.profile.skill_level = int(value)
        self.refresh()

    # ---------------- 候选下拉 ----------------
    def _reload_bag_combo(self):
        """按当前槽的期望 EquipSlotType 过滤 bag_items（戒指两槽同为 7）。"""
        want_type = SLOT_EQUIP_TYPE.get(int(self.profile.compare_slot))
        self.bag_combo.blockSignals(True)
        self.bag_combo.clear()
        self.bag_combo.addItem('（手工输入候选）', -1)
        for i, rec in enumerate(getattr(self.profile, 'bag_items', None) or []):
            if want_type is not None and int(rec.get('equip_slot_type') or 0) != want_type:
                continue
            upg = int(rec.get('upgrade_level') or 0)
            label = (f"{rec.get('name') or '?'}（{rec.get('source')}·ilv"
                     f"{rec.get('item_level', 0)}{'·+' + str(upg) if upg else ''}）")
            self.bag_combo.addItem(label, i)
        self.bag_combo.blockSignals(False)

    def _on_bag_selected(self, index):
        """把选中的背包装备整件载入候选草稿（就地替换内容，保持对象引用与信号绑定）。"""
        idx = self.bag_combo.currentData()
        if idx is None or int(idx) < 0:
            return
        rec = (self.profile.bag_items or [])[int(idx)]
        slot, _cur, cand = self._drafts()
        cand.name = str(rec.get('name') or '')
        cand.affixes = [list(a) for a in (rec.get('affixes') or [])]
        cand.upgrade_level = int(rec.get('upgrade_level') or 0)
        cand.gems = list(rec.get('gems') or [])
        if slot == 0:
            cand.base_damage = 0.0        # 白字伤害以 WeaponDamage(20) 词条入池，与当前武器同口径
            cand.base_speed = float(rec.get('speed') or 1.0)
            cand.skill_multiplier = 1.0
        else:
            cand.equip_slot_type = int(rec.get('equip_slot_type') or 0)
            cand.item_level = int(rec.get('item_level') or 0)
            cand.rarity = int(rec.get('rarity') or 0)
            cand.source = str(rec.get('source') or '')
        self.candidate_editor.reload()
        self.refresh()

    # ---------------- 刷新 ----------------
    def _apply_mode(self):
        """按导入模式切换降级态；手工构建/β 导入时恢复完整对比（幂等，可反复调用）。"""
        alpha = getattr(self.profile, 'import_mode', '') == 'alpha'
        self.alpha_banner.setVisible(alpha)
        if self.current_editor is not None:
            self.current_editor.setEnabled(not alpha)

    def refresh(self):
        """重算并渲染结果区（纯计算，不改动输入控件）。"""
        self._apply_mode()
        result = calc_service.compare(self.profile, self.gd)
        rows = skill_service.skill_rows(self.profile, self.gd, result.current_sheet,
                                        result.candidate_sheet, result.target,
                                        level=int(self.skill_level_spin.value()))
        self.compare_view.set_result(result)
        self.compare_view.set_skills(rows)

    def reload(self):
        """从 profile 回填输入（换构建/导入时用），随后重算。"""
        self.slot_combo.blockSignals(True)
        si = self.slot_combo.findData(int(self.profile.compare_slot))
        self.slot_combo.setCurrentIndex(si if si >= 0 else 0)
        self.slot_combo.blockSignals(False)
        self.class_combo.blockSignals(True)
        ci = self.class_combo.findData(self.profile.hero_class)
        self.class_combo.setCurrentIndex(ci if ci >= 0 else 0)
        self.class_combo.blockSignals(False)
        self.skill_level_spin.blockSignals(True)
        self.skill_level_spin.setValue(max(1, int(self.profile.skill_level)))
        self.skill_level_spin.blockSignals(False)
        self._build_editors()
        self._reload_bag_combo()
        self.refresh()
