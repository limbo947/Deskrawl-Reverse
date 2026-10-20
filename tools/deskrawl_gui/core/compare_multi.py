# -*- coding: utf-8 -*-
"""多槽整套替换的总 Δ（A4）：`compare()` 一次只处理一个槽，而真实换装常是多件同换。

为什么不能把各槽 Δ 相加：伤害是乘区组合（元素/暴伤/条件伤害/易伤），两件同时换的收益
不等于各自单独换的收益之和。所以要给的是「一次装回全部候选」的总 Δ，以及**逐槽边际**
（撤掉某一件会让总 DPS 掉多少）——后者才能回答「这套里哪件在撑」。

装配路径与 calc_service.compare 同源（同一批私有助手），只是把「装回侧」从单槽推广到集合；
`_dps_with(profile, gd, [])` 因此必须与 baseline_dps 逐位相等（selftest 有断言守着）。
"""
from dataclasses import dataclass, field
from typing import List

from deskrawl_calc import DamageModel, effects

from .calc_service import (_add_item_mods, _apply_conversions, _cond_damage, _crit_terms,
                           _draft_empty, _effect_dicts, _effect_mods, _equipped_effects,
                           _negate, _weapon_with_gems, baseline_dps)
from .profile import SLOT_LABELS


@dataclass
class MultiSlotRow:
    """一个槽在整套里的边际：撤掉它之后总 DPS 的变化。"""
    slot: int
    label: str
    marginal: float
    marginal_pct: float


@dataclass
class MultiResult:
    """整套对比结果：总数 + 逐槽边际 + 未参与原因。"""
    slots: List[int] = field(default_factory=list)
    base_dps: float = 0.0
    multi_dps: float = 0.0
    delta: float = 0.0
    delta_pct: float = 0.0
    rows: List[MultiSlotRow] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    skipped: List[int] = field(default_factory=list)   # 候选未填写的槽


def _side_draft(profile, slot: int, candidate: bool):
    """某槽的当前件/候选件草稿（武器槽走 weapon_*，其余走 slot_*）。"""
    if slot == 0:
        return profile.weapon_candidate if candidate else profile.weapon_current
    src = profile.slot_candidate if candidate else profile.slot_current
    return src.get(slot)


def active_slots(profile, slots=None) -> list:
    """有内容的候选槽（升序）。空候选不是一次换装，不参与整套。"""
    order = list(range(11)) if slots is None else sorted({int(s) for s in slots})
    return [s for s in order if not _draft_empty(_side_draft(profile, s, True))]


def skipped_slots(profile, slots=None) -> list:
    """被选中但候选还是空白的槽（界面据此说明「为什么只有这几件在算」）。"""
    order = list(range(11)) if slots is None else sorted({int(s) for s in slots})
    return [s for s in order if _draft_empty(_side_draft(profile, s, True))]


def _base_sheet(profile, gd, replaced, warns):
    """装回 replaced 之外的一切，并把被替换槽的当前件整体卸下（词条 + 特效 + 孔位宝石）。

    卸下用取反（_negate）而不是重算 base：导入件的 base 是「面板减可分解项」的残差，
    重算等于把用户/游戏侧的既有事实推翻；取反只撤掉这一件，其余分文不动。
    """
    sheet = profile.to_sheet(gd)
    if 0 not in replaced:
        sheet.add_mods(profile.weapon_current.to_weapon().modifiers)
    for slot in replaced:
        cur = _side_draft(profile, slot, False)
        if cur is not None:
            if slot != 0:      # 武器词条按上面的分支处理：被替换时根本没加进 sheet
                sheet.add_mods(_negate(cur.to_mods(), warns, cur.name))
            # 特效与当前武器一样留在 base 残差里；不取反会泄漏给候选侧
            sheet.add_mods(_negate(_effect_mods(gd, getattr(cur, 'name', '')), warns,
                                   getattr(cur, 'name', '')))
        for it in profile.assembled:
            if it.kind == 'gem' and int(getattr(it, 'slot', -1)) == slot:
                sheet.add_mods(_negate(it.modifiers(gd), warns, '当前装备孔位宝石'))
    return sheet


def _dps_with(profile, gd, replaced, warns=None) -> float:
    """把 replaced 这组槽的候选全部装回后的总 DPS（replaced=[] 时即当前构建）。"""
    if warns is None:
        warns = []
    replaced = [int(s) for s in replaced]
    sheet = _base_sheet(profile, gd, replaced, warns)
    weapon = profile.weapon_current.to_weapon()
    for slot in replaced:
        cand = _side_draft(profile, slot, True)
        if slot == 0:
            # 与 compare(slot=0) 同款：候选武器 = 词条 + 孔位宝石 + 属性类特效
            weapon = _weapon_with_gems(gd, cand)
            sheet.add_mods(weapon.modifiers)
        else:
            sheet.add_mods(_add_item_mods(gd, cand, slot))
    # 公共特效（未被替换的件 + 天赋）＋ 各候选件自己的特效
    effs = _equipped_effects(gd, profile, exclude_slots=replaced)
    for slot in replaced:
        effs.extend(_effect_dicts(gd, getattr(_side_draft(profile, slot, True), 'name', '')))
    target = profile.to_target()
    _apply_conversions(gd, sheet, effs)       # 换算须在全部 mods 之后（同 compare）
    cc, cd = _crit_terms(gd, effs, target)
    dmg = _cond_damage(gd, effs, profile.damage_type, target)
    model = DamageModel(sheet, profile.damage_type, weapon_damage=weapon.base_damage,
                        primary_stat=profile.primary_stat, conditional_crit=cc,
                        equip_crit_damage=cd, conditional_damage=dmg,
                        damage_dealt_mult=effects.enemy_class_multiplier(effs, target),
                        ignore_health=effects.always_health_conditions(effs))
    return model.dps(target, weapon.base_speed) * weapon.skill_multiplier


def multi_compare(profile, gd, slots=None) -> MultiResult:
    """整套对比：全部候选一起装回的总 Δ + 逐槽边际（撤掉该件后的落差）。

    边际是撤下该件的落差（正值 = 这件在撑总 DPS），不是它单独对自己槽的 Δ：
    多件同换时两者的乘区环境不同，界面上必须分开表述，不能相互换算。
    """
    replaced = active_slots(profile, slots)
    res = MultiResult(slots=replaced, skipped=skipped_slots(profile, slots))
    res.base_dps = baseline_dps(profile, gd)
    if not replaced:
        res.multi_dps = res.base_dps
        return res
    res.multi_dps = _dps_with(profile, gd, replaced, res.warnings)
    res.delta = res.multi_dps - res.base_dps
    res.delta_pct = ((res.multi_dps / res.base_dps - 1.0) * 100.0) if res.base_dps else 0.0
    for slot in replaced:
        rest = [s for s in replaced if s != slot]
        lowered = _dps_with(profile, gd, rest, res.warnings)
        marginal = res.multi_dps - lowered
        res.rows.append(MultiSlotRow(
            slot, SLOT_LABELS.get(slot, f'槽{slot}'), marginal,
            (marginal / lowered * 100.0) if lowered else 0.0))
    res.rows.sort(key=lambda r: -r.marginal)
    return res


__all__ = ['MultiResult', 'MultiSlotRow', 'multi_compare', 'active_slots', 'skipped_slots']
