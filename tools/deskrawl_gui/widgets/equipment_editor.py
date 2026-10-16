# -*- coding: utf-8 -*-
"""中央 Tab1：装备对比（11 槽位切换 + 当前/候选双编辑器 + 结果区）。

槽位 = 内存快照的 slot id（0=武器，1..10=其余十件，不含披风/Back=11）；武器槽沿用
WeaponDraft（多出基础伤害/攻速/技能倍率），其余槽用 ItemDraft。切换槽时按槽重建两侧编辑器并
把候选下拉改为该槽可用的背包/仓库装备。编辑只改 profile 草稿，改动刷新本 Tab 结果区
（装备词条在 compare 内部处理，不进 base sheet）。
"""
import copy

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget)

from ..core import calc_service, skill_service
from ..core.item_draft import ItemDraft
from ..core.profile import COMPARE_SLOTS, SLOT_EQUIP_TYPE, SLOT_LABELS
from .common import ALPHA_WEAPON_NOTE, ModeBanner
from .compare_view import CompareView
from .item_editor import ItemEditor

# 职业下拉（HeroClass 枚举值）：手工构建时用户自选；内存导入自动识别 HeroData.Class。
_HERO_CLASSES = [(None, '（未设置）'), (1, '野蛮人'), (2, '法师'), (4, '猎人'), (8, '武僧')]


class EquipmentEditor(QWidget):
    changed = Signal()          # 职业等跨页参数变更（页面层转发给全局刷新链）
    resultsChanged = Signal()   # 本页结果已重算（词条/候选/槽位变化）：页面层据此同步实测框期望

    def __init__(self, profile, gd, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.gd = gd

        self.slot_combo = QComboBox()
        for slot, label in COMPARE_SLOTS:
            self.slot_combo.addItem(label, slot)
        # 披风（内存槽 11）按用户要求不纳入对比（COMPARE_SLOTS 有意排除）；尾挂一条禁用项把
        # 「为什么列表里没有披风」显式化，避免玩家反复找（F5）。禁用项无 data、不可选中。
        self.slot_combo.addItem('披风（Back）不参与对比')
        self.slot_combo.model().item(self.slot_combo.count() - 1).setEnabled(False)
        self.slot_combo.currentIndexChanged.connect(self._on_slot)

        # 候选快捷导入：内存导入冻结的背包/仓库装备（bag_items），按当前槽类型过滤。
        self.bag_combo = QComboBox()
        self.bag_combo.currentIndexChanged.connect(self._on_bag_selected)

        # 技能区参数：职业决定列出哪些伤害技能；技能等级唯一入口在角色页（消除双入口互同步）
        self.class_combo = QComboBox()
        for value, label in _HERO_CLASSES:
            self.class_combo.addItem(label, value)
        self.class_combo.currentIndexChanged.connect(self._on_class)

        self.compare_view = CompareView()

        self.alpha_banner = ModeBanner(ALPHA_WEAPON_NOTE)

        self._cur_holder = QWidget()
        self._cur_lay = QVBoxLayout(self._cur_holder)
        self._cur_lay.setContentsMargins(0, 0, 0, 0)
        self._cand_holder = QWidget()
        self._cand_lay = QVBoxLayout(self._cand_holder)
        self._cand_lay.setContentsMargins(0, 0, 0, 0)
        self.current_editor = None
        self.candidate_editor = None
        self.last_skill_rows = []          # 最近一次 refresh 的技能秒伤行（页面层复用）

        cand_side = QWidget()
        cand_lay = QVBoxLayout(cand_side)
        cand_lay.setContentsMargins(0, 0, 0, 0)
        cand_lay.addWidget(self._cand_holder, 1)

        slot_bar = QHBoxLayout()
        slot_bar.addWidget(QLabel('装备槽'))
        slot_bar.addWidget(self.slot_combo)
        slot_bar.addSpacing(12)
        slot_bar.addWidget(QLabel('职业（技能秒伤表）'))
        slot_bar.addWidget(self.class_combo)
        slot_bar.addSpacing(12)
        # 背包导入上移到工具条：候选列与当前列从此行数对齐（旧布局候选列多一行，双侧错位）
        slot_bar.addWidget(QLabel('从背包/仓库导入:'))
        slot_bar.addWidget(self.bag_combo, 1)

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
        # 候选侧的「与当前装备相同」以本槽当前件为镜像源（武器与非武器槽通用）；α 下当前件
        # 被整块禁用，开关实质上也不会被用到
        self.candidate_editor = ItemEditor(f'候选{label}', cand, weapon=weapon,
                                          current_of=lambda: cur)
        self.candidate_editor.likeCurrentChanged.connect(self._on_like_current_pref)
        self._auto_like_current(cur)     # 跨槽保持：上一次勾选则本槽自动沿用
        self.current_editor.changed.connect(self.refresh)
        self.candidate_editor.changed.connect(self.refresh)
        self._replace(self._cur_lay, self.current_editor)
        self._replace(self._cand_lay, self.candidate_editor)

    # ---------------- 「与当前装备相同」选择记忆 ----------------
    def _on_like_current_pref(self, checked):
        """把开关选择写回 profile：跨槽保持，且随会话状态/构建存档持久化。"""
        self.profile.like_current_pref = bool(checked)

    def _auto_like_current(self, cur):
        """记忆为开时自动勾选新槽/新载入件的开关；当前件无可镜像内容（手工空卡）则不勾。

        勾了没有可镜像的强化/宝石只会多出提示噪音，也会把「候选=当前件拷贝」误标成镜像态。
        """
        if not bool(getattr(self.profile, 'like_current_pref', False)):
            return
        if not (int(getattr(cur, 'upgrade_level', 0) or 0)
                or list(getattr(cur, 'gems', None) or [])):
            return
        self.candidate_editor.like_current.setChecked(True)

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
        # 职业影响角色页技能下拉与技能表：发 changed 走全局刷新链（角色页选项随之重建）
        self.changed.emit()
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
        slot, cur, cand = self._drafts()
        cand.name = str(rec.get('name') or '')
        cand.affixes = [list(a) for a in (rec.get('affixes') or [])]
        cand.upgrade_level = int(rec.get('upgrade_level') or 0)
        cand.gems = list(rec.get('gems') or [])
        # 记下该件在背包里的原貌与强化前词条（任意槽）：供「与当前装备相同」开关镜像/还原/重算
        cand.raw_modifiers = [[int(s), int(t), float(v)]
                              for s, t, v in (rec.get('modifiers') or [])]
        cand.like_current = False
        cand.own_upgrade_level = int(rec.get('upgrade_level') or 0)
        cand.own_gems = list(rec.get('gems') or [])
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
        self._auto_like_current(cur)     # 保持选择：上次勾选则新载入的背包件自动沿用镜像
        self.refresh()

    # ---------------- 刷新 ----------------
    def _apply_mode(self):
        """按导入模式切换受限态（幂等，可反复调用）。

        当前件是游戏里的既成事实：只要来自导入就置为只读（β 仍可读可对比、但不可改），
        α 没有逐件数据则整块禁用。把「基线不可编辑」写进模式判定，用户不必记住哪侧是事实。
        """
        alpha = self.alpha_banner.update_mode(self.profile)
        imported = bool(getattr(self.profile, 'import_mode', ''))
        if self.current_editor is not None:
            self.current_editor.setEnabled(not alpha)
            self.current_editor.set_locked(imported)

    def refresh(self):
        """重算并渲染结果区（纯计算，不改动输入控件）。"""
        self._apply_mode()
        result = calc_service.compare(self.profile, self.gd)
        rows = skill_service.skill_rows(self.profile, self.gd, result.current_sheet,
                                        result.candidate_sheet, result.target,
                                        level=int(self.profile.skill_level),
                                        cur_effects=result.current_effects,
                                        cand_effects=result.candidate_effects)
        # 留存技能行供页面层（循环系数/候选预测）复用，避免同帧重复计算
        self.last_skill_rows = rows
        self.compare_view.set_result(result)
        self.compare_view.set_skills(rows)
        # 词条/候选改动只走本页刷新，页面层靠这条信号重喂实测框期望（否则预测停留在旧基线）
        self.resultsChanged.emit()

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
        self._build_editors()
        self._reload_bag_combo()
        self.refresh()
