# -*- coding: utf-8 -*-
"""中央 Tab1：装备对比（11 槽位切换 + 当前/候选双编辑器 + 结果区）。

槽位 = 内存快照的 slot id（0=武器，1..10=其余十件，不含披风/Back=11）；武器槽沿用
WeaponDraft（多出基础伤害/攻速/技能倍率），其余槽用 ItemDraft。切换槽时按槽重建两侧编辑器并
把候选下拉改为该槽可用的背包/仓库装备。编辑只改 profile 草稿，改动刷新本 Tab 结果区
（装备词条在 compare 内部处理，不进 base sheet）。
"""
import copy

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
                               QVBoxLayout, QWidget)

from ..core import calc_service, compare_multi, skill_service
from ..core.heroes import hero_class_label
from ..core.item_draft import ItemDraft
from ..core.legendary import legendary_lines
from ..core.profile import COMPARE_SLOTS, SLOT_EQUIP_TYPE, SLOT_LABELS
from .common import ALPHA_WEAPON_NOTE, ModeBanner
from .compare_view import CompareView
from .icons import icon
from .item_editor import ItemEditor
from .multi_compare import open_multi_compare
from .segmented import SegmentedTabs

# 职业下拉由 HeroData.Class 派生（见 core/heroes）：补丁新增职业时不会漏，中文名缺失回落内部名

# 单侧编辑卡片的最小高度：够放下名称/三行武器数值/词条表的 2–3 行，再多由窗口高度决定
_EDITOR_MIN_H = 296


class EquipmentEditor(QWidget):
    changed = Signal()          # 职业等跨页参数变更（页面层转发给全局刷新链）
    resultsChanged = Signal()   # 本页结果已重算（词条/候选/槽位变化）：页面层据此同步实测框期望

    def __init__(self, profile, gd, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.gd = gd

        # 槽位切换用横向标签条（11 项一次点到位，下拉要点两次还会盖住结果区）
        self.slot_combo = SegmentedTabs()
        for slot, label in COMPARE_SLOTS:
            self.slot_combo.addItem(label, slot)
            self.slot_combo.set_tab_tooltip(self.slot_combo.count() - 1,
                                            f'切换到「{label}」：两侧编辑器与结果区一起换')
        # 披风（内存槽 11）按用户要求不纳入对比（COMPARE_SLOTS 有意排除）；尾挂一条禁用项把
        # 「为什么列表里没有披风」显式化，避免玩家反复找（F5）。禁用项无 data、不可选中。
        self.slot_combo.addItem('披风', None, enabled=False)
        self.slot_combo.set_tab_tooltip(self.slot_combo.count() - 1,
                                        '披风（Back）不参与对比，列在此处只为说明它被有意排除')
        self.slot_combo.currentIndexChanged.connect(self._on_slot)

        # 候选快捷导入：内存导入冻结的背包/仓库装备（bag_items），按当前槽类型过滤。
        self.bag_combo = QComboBox()
        self.bag_combo.currentIndexChanged.connect(self._on_bag_selected)

        # 职业唯一入口已归位到角色页「基础面板」（B4）：这里是只读展示，说清技能表按哪个职业列
        # （同一概念两处入口，用户永远要先想「该在哪改」，也容易出现两处不同步）
        self.class_label = QLabel('')
        self.class_label.setObjectName('pageSubtitle')
        self.class_label.setToolTip('职业决定本页技能秒伤表列出哪些技能。\n'
                                    '修改入口：「角色 → 基础面板 → 职业」'
                                    '（导入角色由游戏数据自动识别）')

        self.compare_view = CompareView()

        self.alpha_banner = ModeBanner(ALPHA_WEAPON_NOTE)

        self._cur_holder = QWidget()
        self._cur_lay = QVBoxLayout(self._cur_holder)
        self._cur_lay.setContentsMargins(0, 0, 0, 0)
        self._cand_holder = QWidget()
        self._cand_lay = QVBoxLayout(self._cand_holder)
        self._cand_lay.setContentsMargins(0, 0, 0, 0)
        # 纵向可扩展：卡片原来只按 sizeHint 取高（1600×1000 下仍是 395px），多出的高度全被
        # 下方对比区吃掉；显式 Expanding 后窗口变高会把空间分给词条表。
        for w in (self._cur_holder, self._cand_holder):
            w.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.current_editor = None
        self.candidate_editor = None
        self.last_skill_rows = []          # 最近一次 refresh 的技能秒伤行（页面层复用）
        self.last_candidate_empty = False  # 候选未填写（结果区走空态、实测框不出预测）
        self._last_result = None           # 最近一次对比结果（归因延时计算用）
        self._marginal_timer = QTimer(self)
        self._marginal_timer.setSingleShot(True)
        self._marginal_timer.setInterval(250)
        self._marginal_timer.timeout.connect(self._refresh_marginals)

        cand_side = QWidget()
        cand_side.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        cand_lay = QVBoxLayout(cand_side)
        cand_lay.setContentsMargins(0, 0, 0, 0)
        cand_lay.addWidget(self._cand_holder, 1)

        # 候选播种要显式点：切槽不再自动深拷贝当前件（那会让「看一眼」也写进构建/会话状态）
        self.seed_btn = QPushButton('以当前件为起点')
        self.seed_btn.setObjectName('primary')      # 动线主操作：全屏唯一带强调底的按钮
        self.seed_btn.setToolTip(
            '把本槽当前装备整件复制成候选（得到 Δ=0 的基线，之后改哪条就看哪条的影响）。\n'
            '不再自动预填：只是切槽看一眼不该改写你的构建数据。')
        self.seed_btn.setIcon(icon('act_seed_dark'))      # 黄底 CTA 用墨色图标
        self.seed_btn.clicked.connect(self._seed_candidate)
        # 多件同换是跨槽问题（逐槽 Δ 不能相加），入口放在槽位条上一眼可见，但结果单独成窗
        self.multi_btn = QPushButton('整套对比…')
        self.multi_btn.setToolTip('把已填写候选的槽一起换掉，算总 Δ 与逐槽边际；'
                                  '逐槽 Δ 不能相加，故单开一窗给合计数')
        self.multi_btn.setIcon(icon('act_multi'))
        self.multi_btn.clicked.connect(self._open_multi)
        self.compare_view.seedRequested.connect(self._seed_candidate)   # 结果区空态的就地按钮

        # 工具条拆两行：第一行「改哪个槽」（槽位标签条 + 跨槽的整套对比），第二行「怎么填候选」。
        # 主操作（播种）用黄色 CTA，与顶栏「从游戏导入」同属动线的落点。
        slot_bar = QHBoxLayout()
        slot_bar.setSpacing(12)
        slot_bar.addWidget(self.slot_combo, 1)
        slot_bar.addWidget(self.multi_btn)

        load_bar = QHBoxLayout()
        load_bar.setSpacing(8)
        load_bar.addWidget(QLabel('从背包/仓库载入'))
        load_bar.addWidget(self.bag_combo, 1)
        load_bar.addWidget(self.seed_btn)

        top = QHBoxLayout()
        top.setSpacing(16)
        top.addWidget(self._cur_holder, 1)
        top.addWidget(cand_side, 1)
        # 编辑器整体包成一个 widget：窄窗时结论要挪到它上面（见 set_result_first）
        self._editors_box = QWidget()
        self._editors_box.setLayout(top)
        self._root = root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)
        root.addLayout(slot_bar)
        root.addLayout(load_bar)
        root.addWidget(self.alpha_banner)
        root.addWidget(self._editors_box, 2)
        root.addWidget(self.compare_view, 3)
        self._result_first = False

        self.reload()

    def resizeEvent(self, event):
        """编辑卡片给一个固定下限（300px），其余高度交给结果区。

        为什么不再按自身高度的比例算：本控件在对比页的滚动区里，高度本身由内容最小高度
        决定——用 height×0.5 当最小高度会形成正反馈（406→813→…），最终把结果区顶出首屏。
        固定下限 + 布局 stretch 已能随窗口长高，且不会反过来定义自己的高度。
        """
        super().resizeEvent(event)
        for holder in (self._cur_holder, self._cand_holder):
            if holder.minimumHeight() != _EDITOR_MIN_H:
                holder.setMinimumHeight(_EDITOR_MIN_H)

    def set_result_first(self, first: bool) -> None:
        """窄窗把结论区挪到编辑器上方（宽窗保持「先编辑、下看结果」）。

        为什么需要：1280×720 下左栏只有约 280px 高，内容总高约 660px；结论若排在编辑器
        之后，首屏只能看到两个空卡片，Δ 要滚动才出现。窄窗把结论置顶，首屏即可读结论，
        编辑器往下滚——两条路都保住「先看到结论」。只在模式切换时重建顺序，不参与每次 resize。
        """
        first = bool(first)
        if first == self._result_first:
            return
        self._result_first = first
        self._root.removeWidget(self.compare_view)
        self._root.removeWidget(self._editors_box)
        if first:
            self._root.insertWidget(3, self.compare_view, 0)
            self._root.insertWidget(4, self._editors_box, 1)
        else:
            self._root.insertWidget(3, self._editors_box, 2)
            self._root.insertWidget(4, self.compare_view, 3)

    # ---------------- 槽位与草稿 ----------------
    def select_slot(self, slot: int):
        """编程式选槽（角色页总览双击用）：走下拉信号，避免绕过 _on_slot 造成 UI 与 profile 不同步。"""
        idx = self.slot_combo.findData(int(slot))
        if idx < 0:
            return
        if idx == self.slot_combo.currentIndex():
            self._on_slot()          # 同槽也要重算（可能刚导入/刚清空）
        else:
            self.slot_combo.setCurrentIndex(idx)

    def _drafts(self):
        """当前槽的 (current, candidate) 草稿；非武器槽按需就地建空草稿。"""
        slot = int(self.profile.compare_slot)
        if slot == 0:
            return slot, self.profile.weapon_current, self.profile.weapon_candidate
        cur = self.profile.slot_current.setdefault(slot, ItemDraft())
        cand = self.profile.slot_candidate.setdefault(slot, ItemDraft())
        return slot, cur, cand

    def _build_editors(self):
        """按当前槽重建两侧编辑器（武器槽多武器三行），并接回刷新信号。

        候选不再自动预填当前件：只切槽看一眼也会把整件深拷贝写进 profile（随会话状态与构建
        存档落盘），长出「没碰过却存在」的幻影候选。需要基线时由用户点「以当前件为起点」。
        """
        slot, cur, cand = self._drafts()
        weapon = (slot == 0)
        label = SLOT_LABELS.get(slot, f'槽{slot}')
        # 名称能否命中装备表由 core 判定（与 compare 的告警同源）：两侧都要，候选侧据此描警示边
        resolve = lambda n: calc_service.name_known(self.gd, n)
        hint = lambda s, v, il, ra: calc_service.affix_hint(self.gd, s, v, il, ra)
        legend = lambda n: legendary_lines(self.gd, n)
        self.current_editor = ItemEditor(f'当前{label}', cur, weapon=weapon,
                                        name_resolver=resolve, range_hint=hint,
                                        legendary_fn=legend)
        # 候选侧的「与当前装备相同」以本槽当前件为镜像源（武器与非武器槽通用）；α 下当前件
        # 被整块禁用，开关实质上也不会被用到
        self.candidate_editor = ItemEditor(f'候选{label}', cand, weapon=weapon,
                                          current_of=lambda: cur, name_resolver=resolve,
                                          range_hint=hint, legendary_fn=legend)
        self.candidate_editor.likeCurrentChanged.connect(self._on_like_current_pref)
        for w in (self.current_editor, self.candidate_editor):
            w.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self._auto_like_current(cur, cand)   # 跨槽保持：上一次勾选且候选有内容则本槽自动沿用
        self.current_editor.changed.connect(self.refresh)
        self.candidate_editor.changed.connect(self.refresh)
        self._replace(self._cur_lay, self.current_editor)
        self._replace(self._cand_lay, self.candidate_editor)

    def _seed_candidate(self):
        """显式把当前件复制成候选（唯一写入候选内容的入口，除背包载入外）。

        播种后立刻走一次镜像记忆：记忆位为开时「以当前件为起点」就该得到镜像态，
        否则用户还得手动再勾一次开关（与跨槽保持的语义不一致）。
        """
        _slot, cur, cand = self._drafts()
        cand.__dict__.update(copy.deepcopy(cur.__dict__))
        cand.like_current = False
        self.candidate_editor.reload()
        self._auto_like_current(cur, cand)
        self.refresh()

    def _update_seed_btn(self, cur, cand):
        """播种按钮只在「当前件有内容 且 候选还空着」时可用：其余情况点它没有意义。"""
        has_cur = bool(cur.name or cur.affixes or list(getattr(cur, 'gems', None) or []))
        empty_cand = not (cand.name or cand.affixes
                          or list(getattr(cand, 'gems', None) or []))
        self.seed_btn.setEnabled(has_cur and empty_cand)
        # 结果区空态里的同名按钮同权限：当前件为空时它只会得到一份空拷贝
        self.compare_view.set_seed_enabled(has_cur)

    def _update_multi_btn(self):
        """整套对比按钮：标注参与槽数（0 时禁用——空候选没有可算的整除数）。"""
        n = len(compare_multi.active_slots(self.profile))
        self.multi_btn.setText(f'整套对比…（{n} 槽）' if n else '整套对比…')
        self.multi_btn.setEnabled(n > 0)

    def _open_multi(self):
        """打开整套对比（计算与渲染都在 core/widgets 里，这里只做入口）。"""
        open_multi_compare(self.profile, self.gd, self)

    # ---------------- 「与当前装备相同」选择记忆 ----------------
    def _on_like_current_pref(self, checked):
        """把开关选择写回 profile：跨槽保持，且随会话状态/构建存档持久化。"""
        self.profile.like_current_pref = bool(checked)

    def _auto_like_current(self, cur, cand):
        """记忆为开时自动勾选新槽/新载入件的开关；当前件无可镜像内容或候选为空则不勾。

        勾了没有可镜像的强化/宝石只会多出提示噪音；而候选为空时勾上只会得到「有宝石没词条」的
        半成品（不再自动预填后尤其明显），也会把「候选=当前件拷贝」误标成镜像态。
        """
        if not bool(getattr(self.profile, 'like_current_pref', False)):
            return
        if not (bool(cand.name) or bool(cand.affixes)
                or list(getattr(cand, 'gems', None) or [])):
            return
        if not (int(getattr(cur, 'upgrade_level', 0) or 0)
                or list(getattr(cur, 'gems', None) or [])):
            return
        self.candidate_editor.like_current.setChecked(True)

    @staticmethod
    def _replace(lay, widget):
        """换掉抽屉里的卡片：显式脱离布局再 deleteLater。

        只 deleteLater 不够确定——回收依赖事件循环，离屏/无循环场景（如 --smoke）里旧件会一直
        挂在父对象下（实测 widget 计数虚高到 1172）。先 setParent(None) 让它在当帧就退出布局
        与可见树，随后由事件循环回收。
        """
        while lay.count():
            old = lay.takeAt(0).widget()
            if old is not None:
                old.setParent(None)
                old.deleteLater()
        lay.addWidget(widget)

    def _on_slot(self):
        self.profile.compare_slot = int(self.slot_combo.currentData())
        self._build_editors()
        self._reload_bag_combo()
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
        self._auto_like_current(cur, cand)   # 保持选择：上次勾选则新载入的背包件自动沿用镜像
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
        self._update_class_label()      # 职业在角色页改，这里只跟随显示
        _slot, cur, cand = self._drafts()
        self._update_seed_btn(cur, cand)
        self._update_multi_btn()
        result = calc_service.compare(self.profile, self.gd)
        # 空候选不跑技能表：否则「当前 vs 空装备」的负 Δ 会污染技能表与实测框预测，
        # 也白付一次全职业技能计算（实测 6.8ms / 10 个技能）
        rows = [] if result.candidate_empty else skill_service.skill_rows(
            self.profile, self.gd, result.current_sheet,
            result.candidate_sheet, result.target,
            level=int(self.profile.skill_level),
            cur_effects=result.current_effects,
            cand_effects=result.candidate_effects)
        self.last_candidate_empty = bool(result.candidate_empty)
        # 留存技能行供页面层（循环系数/候选预测）复用，避免同帧重复计算
        self.last_skill_rows = rows
        self.compare_view.set_result(result)
        # 归因要再跑 N 次 compare（N=候选词条数，实测 3 条约 28ms）：放到停止编辑 250ms 后再算，
        # 否则逐字符输入时每次按键都多一截卡顿，而用户只在停下来看结论时才需要这行
        self._last_result = result
        self._marginal_timer.start()
        self.compare_view.set_skills(rows)
        # 词条/候选改动只走本页刷新，页面层靠这条信号重喂实测框期望（否则预测停留在旧基线）
        self.resultsChanged.emit()

    def _refresh_marginals(self):
        """停止编辑后补算归因（为什么延时见 refresh 里的注释）；只更新对比视图那一行。"""
        if self._last_result is None:
            return
        self.compare_view.set_marginals(
            self._last_result, calc_service.affix_marginals(self.profile, self.gd))

    def reload(self):
        """从 profile 回填输入（换构建/导入时用），随后重算。"""
        self.slot_combo.blockSignals(True)
        si = self.slot_combo.findData(int(self.profile.compare_slot))
        self.slot_combo.setCurrentIndex(si if si >= 0 else 0)
        self.slot_combo.blockSignals(False)
        self._update_class_label()
        self._build_editors()
        self._reload_bag_combo()
        self.refresh()

    def _update_class_label(self):
        """只读职业展示：说清技能表按哪个职业列，并指回唯一修改入口（B4）。"""
        hc = getattr(self.profile, 'hero_class', None)
        if hc is None:
            self.class_label.setText('未选职业（技能表列全部职业）')
            return
        self.class_label.setText(f'技能按「{hero_class_label(self.gd, hc)}」列出')
