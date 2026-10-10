# -*- coding: utf-8 -*-
"""每个伤害技能的秒伤对比（结果区用）。

秒伤 = 单次命中期望伤害 × 每秒命中次数（hits/sec）。两块拆开算：

1) 单次命中期望伤害：倍率/伤害类型来自 AbilityData 的 DamageEffect（已逆向，见 docs/04 §6.2）：
   attackDamage = (BaseDamage + AttackScaling.wo(level) × (Final(20)+Final(3))) × (1+Final(主属性)/100)，
   再吃乘区 A(type)/B(暴击期望)/C(条件)/D(易伤) 与减伤层。多段技能逐段按各自 DamageType 计算后求和。

2) 每秒命中次数 = 每次施放命中次数 ÷ 施放间隔：
   每次施放命中次数 = 基础击数（StaggeredStrikesEffect.TargetCount，如 Rending Onslaught=3，
   无则为 1）+ StrikeCount 类天赋附加次数（屠夫韵律 +1 次/级）；
   · 引导技能（ChannelDuration>0 且 ChannelTickRate>0）→ 间隔 = ChannelTickRate/(1+ChannelSpeed)，
     死神之刃等「通道速度」天赋按 (1+ChannelSpeed) 提高命中频率；
   · 非引导有冷却 → 间隔 = 冷却×(1-CDR)；
   · 无冷却（普攻链）→ 间隔 = 1/有效攻速。
   天赋修正来自 profile.ability_mods（内存导入自角色已点天赋；见 memory_import._read_talent_ability_mods）。

🔶 估算口径：引导按整段持续、忽略前摇/收招与法力；多段同 rate；错峰打击按基础击数计。
绝对值为估算，但「当前↔候选」Δ% 在两侧同 rate 时可靠。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from deskrawl_calc import DamageModel, StatType

# TalentEffect_AbilityModifier.ModifiedStat：只处理改变「每秒命中次数」的两项
CHANNEL_SPEED_STAT = 8
STRIKE_COUNT_STAT = 9


@dataclass
class SkillRow:
    """一个伤害技能的对比行（current/candidate 为秒伤）。"""
    name: str
    ability_name: str
    level_req: int
    current_dps: float
    candidate_dps: float
    delta: float
    delta_pct: float
    hits_per_sec: float          # 当前侧的每秒命中次数（展示用）
    interval: float              # 当前侧的单次间隔（秒）


def _per_hit(skill: dict, sheet, target, *, weapon, primary_stat) -> float:
    """每次命中的期望伤害（多段求和）。"""
    total = 0.0
    for e in skill['effects']:
        model = DamageModel(sheet, e['damage_type'], weapon_damage=weapon.base_damage,
                            primary_stat=primary_stat, skill_scaling=e['scaling'])
        bd = model.compute(target)
        total += bd.base_damage * bd.expected_mult
    return total


def _hits_per_sec(skill: dict, sheet, atk_speed: float, mods) -> float:
    """每秒命中次数 = 每次施放的命中次数 ÷ 施放间隔，含 ChannelSpeed / StrikeCount 天赋修正。

    每次施放命中次数 = 基础击数（StaggeredStrikesEffect.TargetCount，如 Rending Onslaught=3；
    无则为 1）+ StrikeCount 天赋附加次数（如屠夫韵律 +1 次/级）。
    间隔：引导技能 = ChannelTickRate/(1+ChannelSpeed)；非引导有冷却 = 冷却×(1-CDR)；否则 = 1/攻速。
    """
    channel_speed = float((mods or {}).get(CHANNEL_SPEED_STAT, 0.0))
    strike_bonus = float((mods or {}).get(STRIKE_COUNT_STAT, 0.0))
    if skill['channel_duration'] > 0 and skill['tick_rate'] > 0:
        interval = skill['tick_rate'] / (1.0 + channel_speed)
    else:
        cdr = min(0.85, max(0.0, sheet.final(StatType.CooldownReduction)))
        cd = float(skill['cooldown']) * (1.0 - cdr)
        interval = cd if cd > 0.05 else (1.0 / atk_speed if atk_speed > 0 else 1.0)
    strikes = int(skill.get('strikes', 1)) + strike_bonus
    return strikes / interval if interval > 0 else 0.0


def skill_rows(profile, gd, cur_sheet, cand_sheet, target,
               level: Optional[int] = None) -> List[SkillRow]:
    """当前职业每个伤害技能的秒伤对比（hero_class 未知时返回空表）。

    cur_sheet/cand_sheet 来自 calc_service.compare（已含武器词条与所选槽的当前/候选装备）。
    """
    hero_class = getattr(profile, 'hero_class', None)
    if hero_class is None:
        return []
    lv = int(profile.skill_level if level is None else level)
    skills = gd.damage_skills(hero_class, lv)
    weapon = profile.weapon_current.to_weapon()
    ps = profile.primary_stat
    all_mods = getattr(profile, 'ability_mods', None) or {}

    def atk_speed(sheet) -> float:
        return weapon.base_speed * (1.0 + sheet.final(StatType.AttackSpeed))

    rows = []
    for sk in skills:
        mods = all_mods.get(sk['name'], {})
        cur_rate = _hits_per_sec(sk, cur_sheet, atk_speed(cur_sheet), mods)
        cand_rate = _hits_per_sec(sk, cand_sheet, atk_speed(cand_sheet), mods)
        cur = _per_hit(sk, cur_sheet, target, weapon=weapon, primary_stat=ps) * cur_rate
        cand = _per_hit(sk, cand_sheet, target, weapon=weapon, primary_stat=ps) * cand_rate
        rows.append(SkillRow(name=sk['name'], ability_name=sk['ability_name'],
                             level_req=sk['level_req'], current_dps=cur, candidate_dps=cand,
                             delta=cand - cur,
                             delta_pct=((cand / cur - 1.0) * 100.0) if cur else 0.0,
                             hits_per_sec=cur_rate,
                             interval=(1.0 / cur_rate) if cur_rate > 0 else 0.0))
    return rows
