# -*- coding: utf-8 -*-
"""同步计算服务：把「装配 + 计算」从 widget 抽离。

全部为纯函数（输入 profile/gd，输出视图数据）。将来若要把排序挪到线程，
只改这一个文件即可；v1 同步（全量排序实测远小于 1 秒）。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import List

from deskrawl_calc import (DamageModel, Modifier, StatSheet, StatType, Target, Weapon,
                           compare_weapons, effects, stat_name)

from .localization import item_internal_name
from .profile import (KIND_LABELS, SLOT_EQUIP_TYPE, SLOT_LABELS, CharacterProfile,
                      _gem_category)


@dataclass
class StatRow:
    """属性明细的一行：三层聚合分解。"""
    stat: int
    name: str
    base: float
    flat: float
    add: float
    mult: float
    final: float


@dataclass
class CompareResult:
    """一次装备对比的完整结果，供视图直接渲染。

    slot/slot_label 标明所选槽（0=武器，1..10=其余十件）；current_sheet/candidate_sheet 是
    两侧的完整属性表（已含武器词条与所选槽的当前/候选装备），供技能秒伤对比复用。
    """
    slot: int
    slot_label: str
    current_dps: float
    candidate_dps: float
    delta: float
    delta_pct: float
    current_model: DamageModel
    candidate_model: DamageModel
    current_sheet: StatSheet
    candidate_sheet: StatSheet
    target: Target
    warnings: List[str] = field(default_factory=list)
    # 两侧的传奇特效（保真 dict；含公共件 + 被对比槽各自件）。供技能秒伤对比按技能过滤
    # （AbilityTagCritDamage/AbilityModifier 等按技能/标签命中的特效），见 skill_service.skill_rows。
    current_effects: list = field(default_factory=list)
    candidate_effects: list = field(default_factory=list)


@dataclass
class CandidateRow:
    """候选排序的一行。delta 相对「当前构建（含当前武器词条）」的 DPS。"""
    name: str
    detail: str
    dps: float
    delta: float
    delta_pct: float
    modifiers: list = field(default_factory=list)


def stat_rows(sheet: StatSheet) -> List[StatRow]:
    """列出所有非零属性的 Base/Flat/%Add/Π/Final，按 |Final| 降序。"""
    rows = []
    for st in StatType:
        b = sheet.breakdown(st)
        if b['Base'] or b['Flat'] or b['PercentAdd'] or b['Final']:
            rows.append(StatRow(int(st), stat_name(st), b['Base'], b['Flat'],
                                b['PercentAdd'], b['PercentMultΠ'], b['Final']))
    rows.sort(key=lambda r: -abs(r.final))
    return rows


def _weapon_mods(profile):
    return profile.weapon_current.to_weapon().modifiers


def gem_category_for_slot(slot) -> int:
    """内存槽 id → 宝石加成组（0=护甲 1=饰品 2=武器）；未知槽回落护甲组。

    宝石组必须由**被对比的槽位**推导，不能读草稿自身的 equip_slot_type：手工候选草稿
    该字段恒为 0，戒指/项链槽会静默落到护甲组（CDR/主属性顶替饰品专属加成）。
    槽→EquipSlotType 取 SLOT_EQUIP_TYPE（与 memory_offsets 的实测表同源）。
    """
    return _gem_category(SLOT_EQUIP_TYPE.get(int(slot), 0))


def _effect_mods(gd, name) -> list:
    """装备名（简中显示名）→ 传奇特效词条。

    只有 StatModifier / AllStats 两类能入属性池（92 条特效里 80 条是触发/状态/技能修改类，
    本就不走属性池）；名字要反查回 ItemData 内部名才能取到 `EquipmentEffects` 引用。
    """
    return gd.item_effect_modifiers(item_internal_name(gd, str(name or '')))


def _effect_dicts(gd, name) -> list:
    """装备名（简中显示名）→ **全部**传奇特效（保真 dict，含触发/条件/技能修改类）。

    与 `_effect_mods` 同款名字反查；交给内核 `effects.py` 按类解释（条件暴击 / 标签暴伤 /
    技能修改 / 属性换算等）。
    """
    return gd.item_effects(item_internal_name(gd, str(name or '')))


def _equipped_effects(gd, profile, *, exclude_slot=None) -> list:
    """当前构建所有已装备件的传奇特效（保真 dict）：武器 + slot_current + 已装配符文套装。

    「当前件 ↔ 候选件」对比时，被对比槽位的件由调用方单独处理 → `exclude_slot` 排除该槽；
    其余件（含武器、其它槽、套装）对两侧**公共**，故同口径加入，仅被对比槽产生 Δ。
    """
    ex = -1 if exclude_slot is None else int(exclude_slot)
    out: list = []
    if ex != 0:
        out.extend(_effect_dicts(gd, getattr(profile.weapon_current, 'name', '')))
    for s, it in (getattr(profile, 'slot_current', None) or {}).items():
        if int(s) == ex:
            continue
        out.extend(_effect_dicts(gd, getattr(it, 'name', '')))
    for it in (getattr(profile, 'assembled', None) or []):
        if getattr(it, 'kind', '') == 'runeset':
            out.extend(gd.runeset_effects(str(it.name), int(it.level)))
    return out


def _crit_terms(gd, effs, target) -> tuple:
    """特效列表 → (条件额外暴击率, 条件额外暴伤)，按目标状态门控（effects.crit_terms）。"""
    return effects.crit_terms(effs, target, status_names=gd.status_name_by_pathid())


def _cond_damage(gd, effs, damage_type, target, ability_name=None) -> float:
    """特效列表 → 本次伤害类型的条件额外伤害（effects.conditional_damage，加进条件池）。"""
    return effects.conditional_damage(effs, damage_type, target,
                                      status_names=gd.status_name_by_pathid(),
                                      ability_names=gd.ability_name_by_pathid(),
                                      ability_name=ability_name)


def _add_item_mods(gd, item, slot=None) -> list:
    """一件装备对属性表的贡献：词条 + 孔位宝石 + 传奇特效。

    宝石加成组优先按对比槽位推导（见 gem_category_for_slot）；无槽位上下文时回落草稿自身的
    equip_slot_type（导入件该字段由实测映射填准，手工草稿为 0）。两侧对称：当前件与候选件
    用同一套取组规则，否则手工候选会得到与当前件不一致的宝石加成。
    """
    if item is None:
        return []
    out = list(item.to_mods())
    cat = _gem_category(getattr(item, 'equip_slot_type', 0)) if slot is None \
        else gem_category_for_slot(slot)
    for gname in (getattr(item, 'gems', None) or []):
        out.extend(gd.gem_modifiers(str(gname), cat))
    out.extend(_effect_mods(gd, getattr(item, 'name', '')))
    return out


def _negate(mods, warns=None, label=None) -> list:
    """取反以便从基线里「卸下」一件装备。装备词条实测恒为 Flat，可逆；%连乘(type 2)不可逆则跳过。

    跳过是静默丢数据：type≠0 的词条当前全仓不可达（UI 锁「加法」），但一旦出现会让基线漏项、
    Δ 失真，故向 warns 写显式告警（F8 防御——宁可红不出脏）。
    """
    out = []
    for m in mods:
        if int(m.type) == 2:
            if warns is not None:
                who = f'「{label}」' if label else ''
                warns.append(f'{who}含连乘(type 2)词条：卸下不可逆已跳过，Δ 可能失真')
            continue
        out.append(Modifier(int(m.stat), int(m.type), -float(m.value)))
    return out


def _weapon_gems(gd, draft) -> list:
    """武器孔位宝石的静态加成（加成组 = 武器 2，与 _gem_category 的实测锚定同源）。"""
    cat = _gem_category(1)              # EquipSlotType 1 = 武器
    out = []
    for gname in (getattr(draft, 'gems', None) or []):
        out.extend(gd.gem_modifiers(str(gname), cat))
    return out


def _weapon_with_gems(gd, draft) -> Weapon:
    """武器草稿 → Weapon（孔位宝石 + 传奇特效并入词条）：候选侧的宝石/特效因此能参与对比。

    内核的 Weapon 只认词条，宝石与特效加成原本不在它这里；把三者合并，是为了让
    「候选换一套宝石」或「换一把带属性类传奇特效的武器」这种对比有数值出口。
    """
    w = draft.to_weapon()
    return Weapon(w.name, w.base_damage, w.base_speed,
                  list(w.modifiers) + _weapon_gems(gd, draft) + _effect_mods(gd, draft.name),
                  skill_multiplier=w.skill_multiplier)


def _slot_sheets(profile, gd, slot, warns):
    """非武器槽的 (current_sheet, candidate_sheet)。

    当前件词条与**传奇特效**都已烘焙在 base 残差（特效此前不可分解）、宝石在 assembled 里；
    先克隆「完整构建（含武器词条）」再把当前槽当前件整体卸下（词条 + 宝石 + 特效三者都取反）
    得到干净基线，两侧分别装回当前件/候选件——于是当前侧 ≡ 基线，仅候选产生 Δ。
    孔位宝石的加成组一律按本槽位推导（gem_category_for_slot），故候选草稿的 equip_slot_type
    是否填准都不影响取组——手工候选与导入件因此得到同一口径。
    """
    base = profile.to_sheet(gd)
    base.add_mods(_weapon_mods(profile))
    cur_item = profile.slot_current.get(slot)
    if cur_item is not None:
        base.add_mods(_negate(cur_item.to_mods(), warns, cur_item.name))
        # 特效不在 assembled、而是留在 base 残差里；不取反就会「泄漏」给候选侧
        base.add_mods(_negate(_effect_mods(gd, cur_item.name), warns, cur_item.name))
    for it in profile.assembled:
        if it.kind == 'gem' and int(getattr(it, 'slot', -1)) == slot:
            base.add_mods(_negate(it.modifiers(gd), warns, '当前装备孔位宝石'))
    cur_sheet = base.clone()
    cur_sheet.add_mods(_add_item_mods(gd, cur_item, slot))
    cand_sheet = base.clone()
    cand_sheet.add_mods(_add_item_mods(gd, profile.slot_candidate.get(slot), slot))
    return cur_sheet, cand_sheet


def compare(profile: CharacterProfile, gd, slot=None) -> CompareResult:
    """对比所选槽的当前件/候选件（默认取 profile.compare_slot）。

    slot==0 走内核 compare_weapons（武器词条与各自孔位宝石都不在 base，由它两侧分别叠加）；
    slot 1..10 走「卸下当前件 → 分别装回」的对称路径（见 _slot_sheets）。
    """
    slot = int(profile.compare_slot if slot is None else slot)
    target = profile.to_target()
    label = SLOT_LABELS.get(slot, f'槽{slot}')
    warns: List[str] = []
    if slot == 0:
        sheet = profile.to_sheet(gd)
        # 当前武器的孔位宝石原本只在装配链里（assembled 的 slot=0 条目）→ 两侧都会看到「当前」的宝石。
        # 为让候选武器的宝石参与对比，先按槽卸下（宝石恒为 Flat，可逆），再并入各自武器词条：
        # 当前侧总量不变（卸下又装回），差异因此完全落在候选侧。
        for it in profile.assembled:
            if it.kind == 'gem' and int(getattr(it, 'slot', -1)) == 0:
                sheet.add_mods(_negate(it.modifiers(gd), warns, '当前武器孔位宝石'))
        # 当前武器的传奇特效同样留在 base 残差里（不在 assembled）→ 一并卸下，否则会泄漏给候选武器
        sheet.add_mods(_negate(_effect_mods(gd, profile.weapon_current.name), warns,
                               profile.weapon_current.name))
        cur = _weapon_with_gems(gd, profile.weapon_current)
        cand = _weapon_with_gems(gd, profile.weapon_candidate)
        # 逐侧条件暴击（武器特效差异：当前武器 ↔ 候选武器；其余件对两侧公共）
        common = _equipped_effects(gd, profile, exclude_slot=0)
        cur_eff = common + _effect_dicts(gd, profile.weapon_current.name)
        cand_eff = common + _effect_dicts(gd, profile.weapon_candidate.name)
        cc_c, cd_c = _crit_terms(gd, cur_eff, target)
        cc_k, cd_k = _crit_terms(gd, cand_eff, target)
        dmg_c = _cond_damage(gd, cur_eff, profile.damage_type, target)
        dmg_k = _cond_damage(gd, cand_eff, profile.damage_type, target)
        r = compare_weapons(sheet, cur, cand, target=target, damage_type=profile.damage_type,
                            primary_stat=profile.primary_stat,
                            current_kw={'conditional_crit': cc_c, 'equip_crit_damage': cd_c,
                                        'conditional_damage': dmg_c},
                            candidate_kw={'conditional_crit': cc_k, 'equip_crit_damage': cd_k,
                                          'conditional_damage': dmg_k})
        return CompareResult(0, label, r['current']['dps'], r['candidate']['dps'],
                             r['delta'], r['delta_pct'], r['current']['model'],
                             r['candidate']['model'], r['current']['sheet'],
                             r['candidate']['sheet'], target, warns,
                             current_effects=cur_eff, candidate_effects=cand_eff)

    cur_sheet, cand_sheet = _slot_sheets(profile, gd, slot, warns)
    w = profile.weapon_current.to_weapon()
    # 逐侧条件暴击（被对比槽两件不同；其余件公共）
    common = _equipped_effects(gd, profile, exclude_slot=slot)
    cur_eff = common + _effect_dicts(gd, getattr(profile.slot_current.get(slot), 'name', ''))
    cand_eff = common + _effect_dicts(gd, getattr(profile.slot_candidate.get(slot), 'name', ''))
    cc_c, cd_c = _crit_terms(gd, cur_eff, target)
    cc_k, cd_k = _crit_terms(gd, cand_eff, target)
    dmg_c = _cond_damage(gd, cur_eff, profile.damage_type, target)
    dmg_k = _cond_damage(gd, cand_eff, profile.damage_type, target)

    def model(sheet, cc, cd, cdmg):
        return DamageModel(sheet, profile.damage_type, weapon_damage=w.base_damage,
                           primary_stat=profile.primary_stat,
                           conditional_crit=cc, equip_crit_damage=cd,
                           conditional_damage=cdmg)

    cur_model, cand_model = (model(cur_sheet, cc_c, cd_c, dmg_c),
                             model(cand_sheet, cc_k, cd_k, dmg_k))
    cur_dps = cur_model.dps(target, w.base_speed) * w.skill_multiplier
    cand_dps = cand_model.dps(target, w.base_speed) * w.skill_multiplier
    return CompareResult(slot, label, cur_dps, cand_dps, cand_dps - cur_dps,
                         ((cand_dps / cur_dps - 1.0) * 100.0) if cur_dps else 0.0,
                         cur_model, cand_model, cur_sheet, cand_sheet, target, warns,
                         current_effects=cur_eff, candidate_effects=cand_eff)


def candidate_names(gd, kind: str) -> List[str]:
    src = {'gem': gd.gems, 'rune': gd.runes, 'talent': gd.talents, 'runeset': gd.runesets}[kind]
    return sorted(src().keys())


def ability_names(gd) -> List[str]:
    """技能名称清单。内核未暴露名称列表，这里按同一数据目录直读（只读，不碰内核私有方法）。"""
    path = os.path.join(getattr(gd, 'dir', ''), 'AbilityData.json')
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as f:
        rows = json.load(f)
    return sorted(r['_name'] for r in rows if r.get('_name'))


def candidate_modifiers(gd, kind: str, name: str, *, level: int = 1, category: int = 2) -> list:
    """取某候选的实际词条；参数语义与 AssemblyItem.modifiers 一致。"""
    if kind == 'gem':
        return gd.gem_modifiers(name, category)
    if kind == 'rune':
        return gd.rune_modifiers(name, level)
    if kind == 'talent':
        return gd.talent_modifiers(name, level)
    if kind == 'runeset':
        return gd.runeset_modifiers(name, level)
    return []


# 修饰符类型的界面用中文名（内核 Modifier.describe() 用的是 Flat/%Add/%Mult）；
# 词条摘要与词条编辑表共用这一份，避免两处定义漂移
MOD_TYPE_CN = {0: '加法', 1: '百分比加算', 2: '连乘'}


def describe_mods(mods) -> str:
    """候选词条摘要。属性名复用内核 stat_name()，类型记号本地化为中文，保证界面全中文。"""
    if not mods:
        return '（无属性词条）'
    return '；'.join(f'{stat_name(m.stat)} {m.value:+.3f}'
                     f'（{MOD_TYPE_CN.get(int(m.type), m.type)}）' for m in mods)


def _dps_with(profile: CharacterProfile, gd, extra_mods, extra_effects=None) -> float:
    """当前构建（含当前武器词条与已装备件的传奇特效）+ extra_mods/extra_effects 的期望 DPS。

    排序基线与候选增量共用这一条路径，保证 Δ 可被独立复现（self-test 用引擎直算对拍）。
    条件暴击类特效（`ConditionalCritChance/Damage`）走 `conditional_crit`/`equip_crit_damage`
    参数（不进属性表）；符文套装候选的套装特效由 `extra_effects` 传入。
    """
    sheet = profile.to_sheet(gd)
    w = profile.weapon_current.to_weapon()
    sheet.add_mods(w.modifiers)
    sheet.add_mods(extra_mods)
    target = profile.to_target()
    effs = _equipped_effects(gd, profile) + list(extra_effects or [])
    cc, cd = _crit_terms(gd, effs, target)
    dmg = _cond_damage(gd, effs, profile.damage_type, target)
    model = DamageModel(sheet, profile.damage_type, weapon_damage=w.base_damage,
                        primary_stat=profile.primary_stat,
                        conditional_crit=cc, equip_crit_damage=cd, conditional_damage=dmg)
    return model.dps(target, w.base_speed) * w.skill_multiplier


def candidate_effects(gd, kind: str, name: str, *, level: int = 1) -> list:
    """某候选的传奇特效（保真 dict）：目前仅符文套装带 `EquipmentEffect_*`。"""
    if kind == 'runeset':
        return gd.runeset_effects(name, level)
    return []


def baseline_dps(profile: CharacterProfile, gd) -> float:
    """排序基线：当前构建（含当前武器词条）的期望 DPS。"""
    return _dps_with(profile, gd, [])


def rank_candidates(profile: CharacterProfile, gd, kind: str, *,
                    level: int = 1, category: int = 2) -> List[CandidateRow]:
    """对某类别的全部候选按 ΔDPS 降序排序（基线 = 当前构建不加候选）。"""
    base_dps = baseline_dps(profile, gd)
    rows = []
    for name in candidate_names(gd, kind):
        mods = candidate_modifiers(gd, kind, name, level=level, category=category)
        effs = candidate_effects(gd, kind, name, level=level)
        dps = _dps_with(profile, gd, mods, extra_effects=effs)
        pct = (dps / base_dps - 1.0) * 100.0 if base_dps else 0.0
        rows.append(CandidateRow(name, describe_mods(mods), dps, dps - base_dps, pct, mods))
    rows.sort(key=lambda r: -r.delta)
    return rows


# --------------------------------------------------------------------------- #
# 游戏面板口径复算（Player.PanelStat@0x503350 反汇编还原；2026-10-08 与游戏「属性」页逐行对拍）
# --------------------------------------------------------------------------- #
# 面板行序 = 游戏「属性」页顺序（进攻 18 行 + 防御 5 行；21=攻击速度显示式行）
PANEL_ORDER = [0, 3, 21, 6, 4, 5, 23, 24, 25, 26, 27, 28, 29, 31, 45, 32, 40, 65,
               7, 42, 8, 44, 9]

# 面板按「百分比」显示的行（其余按整数千分位 / 攻速一位小数）
_PCT_DISPLAY = {4, 5, 6, 13, 15, 16, 17, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32,
                33, 34, 37, 40, 41, 42, 43, 44, 45, 46, 48, 49, 51, 52, 53, 54, 55,
                56, 57, 58, 59, 60, 61, 62, 63, 64, 65}

# 基础字段 → 属性（Character.BaseFieldToStat@0x686F60 与 Player.BaseFieldToStat@0x503A60 逐分支反汇编）
_BASE_FIELD_STAT = {
    'BaseDamage': 3, 'BaseCritChance': 4, 'BaseCritDamage': 5, 'BaseAttackSpeed': 6,
    'BaseMaxHealth': 7, 'BaseMoveSpeed': 10, 'BaseLifeOnHit': 11, 'BaseLifeOnKill': 12,
    'BaseCooldownReduction': 13, 'BaseMaxMana': 14, 'BaseDodgeChance': 22,
}
# 生命/护甲/魔抗/移速 再 ×(1+对应%属性)（bjd 尾部 cmp esi,7/8/9/10 分支）
_SPECIAL_PCT = {7: 42, 8: 44, 9: 59, 10: 57}
_FLAT_DICTS = ('nsq', 'nsu', 'ntc', 'nte', 'nsr')   # 平坦层字典
_PCT_DICTS = ('nsv', 'ntd')                          # 百分比加算层字典
_COND_CN = {0: '受伤中(<30%血)', 1: '健康(>80%血)', 2: '附近无敌', 3: '脱战',
            4: '单敌交战', 5: '被包围', -1: '常驻'}


def _lookup(d, stat):
    """字典取值（兼容 int 键与 JSON 往返后的 str 键）。"""
    if not d:
        return 0.0
    if stat in d:
        return float(d[stat])
    return float(d.get(str(stat), 0.0))


def build_panel(payload: dict) -> dict:
    """把内存快照复算成「游戏面板口径」属性表（bjd 反汇编还原，与游戏「属性」页逐行一致）。

    panel(stat) = cap( g3×(core + g1)×(1+g2) )
    core(stat)  = (Σ平坦字典 + 基础字段 + 主属性 + far(护甲←力量/魔抗←智力) + 条件表平坦)
                  × (1 + Σ百分比字典 + 条件表百分比)   [7/8/9/10 再 ×(1+对应%属性的 core)]
    条件求值：None(-1) 恒真；Healthy=血比例>0.8；Injured<0.3（Player.EvaluateCondition@0x513490 实证）；
    敌情类（2/3/4/5）与带技能/状态门控的条目无法从快照静态判定 → 不计入并记告警。
    返回 {'time','mode','hp_frac','rows','warnings'}；row = [stat, flat, cond, pct, mult, final, text]。
    """
    from deskrawl_calc.stattype import CAPPED_085, CAPPED_080, CAPPED_090

    player = payload.get('player') or {}
    dicts = player.get('stat_dicts') or {}
    f = player.get('fields') or {}
    meta = payload.get('meta') or {}
    warns: List[str] = []

    def warn(msg):
        if msg not in warns:
            warns.append(msg)

    def d(label):
        return {int(k): float(v) for k, v in (dicts.get(label) or {}).items()}

    flat_d = [d(x) for x in _FLAT_DICTS]
    pct_d = [d(x) for x in _PCT_DICTS]
    conds = player.get('conditionals') or {}
    smods = player.get('status_mods') or {}
    base_field = {st: float(f[name]) for name, st in _BASE_FIELD_STAT.items()
                  if f.get(name) is not None}
    pstat = player.get('primary_stat')
    if pstat is None:
        warn('主属性未导出：主属性的基础值贡献（BasePrimaryStat）未计入')
    hp = f.get('CurrentHealth')

    def cond_ok(cond, hp_frac):
        c = int(cond)
        if c == -1:
            return True
        if c == 1:
            return hp_frac > 0.8
        if c == 0:
            return hp_frac < 0.3
        warn(f'条件「{_COND_CN.get(c, c)}」属敌情类，快照无法静态判定，未计入')
        return False

    def fat(stat, mtype, hp_frac):
        total = 0.0
        for cond, _radius, s, t, v, gated in (conds.get('nuf') or []):
            if int(s) != stat or int(t) != mtype:
                continue
            if gated:
                warn('nuf 存在带技能门控的条目，未计入')
            elif cond_ok(cond, hp_frac):
                total += float(v)
        for cond, gated, s, t, v in (conds.get('nug') or []):
            if int(s) != stat or int(t) != mtype:
                continue
            if gated:
                warn('nug 存在带状态门控的条目，未计入')
            elif cond_ok(cond, hp_frac):
                total += float(v)
        return total

    def parts(stat, depth=0, hp_frac=1.0):
        flat = sum(x.get(stat, 0.0) for x in flat_d) + base_field.get(stat, 0.0)
        if pstat is not None and stat == int(pstat):
            flat += float(f.get('BasePrimaryStat') or 0.0)
        if depth == 0 and stat == 8:
            flat += core(0, depth + 1, hp_frac)      # far：护甲 ← 力量（bjd 会递归）
        elif depth == 0 and stat == 9:
            flat += core(2, depth + 1, hp_frac)      # far：魔抗 ← 智力
        cond = fat(stat, 0, hp_frac)
        pct = sum(x.get(stat, 0.0) for x in pct_d) + fat(stat, 1, hp_frac)
        mult = 1.0
        if depth == 0 and stat in _SPECIAL_PCT:
            mult = 1.0 + core(_SPECIAL_PCT[stat], depth + 1, hp_frac)
        return flat, cond, pct, mult, (flat + cond) * (1.0 + pct) * mult

    def core(stat, depth=0, hp_frac=1.0):
        return parts(stat, depth, hp_frac)[4]

    max_hp = parts(7, hp_frac=1.0)[4]
    if hp is None or max_hp <= 0:
        hp_frac = 1.0
        warn('当前生命/面板生命不可用：条件按满血（Health 全开）估算')
    else:
        hp_frac = max(0.0, min(1.0, float(hp) / max_hp))

    def bjc(stat):
        """cap(bgh(core))：StatusEffectController 三字典层 + 封顶（与 Char.bjc 一致）。"""
        flat_v = core(stat, hp_frac=hp_frac)
        g1 = _lookup(smods.get('flat'), stat)
        g2 = _lookup(smods.get('pct'), stat)
        g3 = _lookup(smods.get('mult'), stat) if smods.get('mult') else 1.0
        v = g3 * (flat_v + g1) * (1.0 + g2)
        if stat in CAPPED_085:
            v = max(0.0, min(v, 0.85))
        elif stat in CAPPED_080:
            v = max(0.0, min(v, 0.80))
        elif stat in CAPPED_090:
            v = max(0.0, min(v, 0.90))
        return v

    def fmt(stat, v):
        if stat == 21:
            return f'{v:.1f}'                     # 攻速按每秒一位小数（面板口径）
        if stat in _PCT_DISPLAY:
            s = f'{v * 100.0:.1f}'
            return (s[:-2] if s.endswith('.0') else s) + '%'
        return f'{v:,.0f}'

    rows = []
    for st in sorted(set(int(x) for x in StatType) | set(PANEL_ORDER)):
        flat, cond, pct, mult, _fin = parts(st, hp_frac=hp_frac)
        final = bjc(st)
        if st == 21:                              # 面板「攻击速度」= 武器速度 ×(1+攻速%)
            base21 = bjc(21)
            mult = 1.0 + bjc(6)
            flat, cond, pct = base21, 0.0, 0.0
            final = base21 * mult
        if not (flat or cond or pct or final):
            continue
        rows.append([st, flat, cond, pct, mult, final, fmt(st, final)])
    rows.sort(key=lambda r: (PANEL_ORDER.index(r[0]) if r[0] in PANEL_ORDER
                             else len(PANEL_ORDER) + 1, -abs(r[5])))
    return {'time': str(meta.get('time') or ''), 'mode': str(meta.get('mode') or ''),
            'hp_frac': hp_frac, 'rows': rows, 'warnings': warns}


__all__ = ['StatRow', 'CompareResult', 'CandidateRow', 'stat_rows', 'compare',
           'candidate_names', 'candidate_modifiers', 'describe_mods',
           'baseline_dps', 'rank_candidates', 'KIND_LABELS',
           'build_panel', 'PANEL_ORDER', 'MOD_TYPE_CN', 'gem_category_for_slot']
