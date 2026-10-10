# -*- coding: utf-8 -*-
"""每个伤害技能的秒伤对比（结果区用）。

秒伤 = 单次命中期望伤害 × 每秒命中次数（hits/sec）。两块拆开算：

1) 单次命中期望伤害：倍率/伤害类型来自 AbilityData 的 DamageEffect（已逆向，见 docs/04 §6.2）：
   attackDamage = (BaseDamage + AttackScaling.wo(level) × (Final(20)+Final(3))) × (1+Final(主属性)/100)，
   再吃乘区 A(type)/B(暴击期望)/C(条件)/D(易伤) 与减伤层。多段技能逐段按各自 DamageType 计算后求和。

2) 每秒命中次数 = 每次施放命中次数 ÷ 施放周期：
   每次施放命中次数 = 基础击数（StaggeredStrikesEffect.TargetCount，如 Rending Onslaught=3，
   无则为 1）+ StrikeCount 类天赋附加次数（屠夫韵律 +1 次/级）；
   · 引导技能（ChannelDuration>0 且 ChannelTickRate>0）→
       命中数/次 = 击数 × (1+ChannelSpeed) × Duration/TickRate（死神之刃等「通道速度」天赋
       按 (1+ChannelSpeed) 提高 tick 频率），周期 = 前摇+持续+收招+冷却×(1-CDR)——
       引导技能同样吃冷却（实测 7 个引导技能 6 个有 2.5~18s 冷却），不按「无限引导」计；
       冷却=0 时该式退化为 1/TickRate（与旧口径逐位相同，自检锚点 3.125/6.250 因此不变）；
   · 非引导有冷却 → 间隔 = 冷却×(1-CDR)；
   · 无冷却（普攻链）→ 间隔 = 1/有效攻速。
   天赋修正来自 profile.ability_mods（内存导入自角色已点天赋；见 memory_import._read_talent_ability_mods）。

🔶 估算口径（2026-10-10 按 AbilityData 全量复核收窄）：
   · 前摇/收招：124 个技能里各只有 1 个非零且是**敌人**技能（VolcanoDemonLordFlyingLaser），
     玩家技能恒 0——已计入，但实际不改任何玩家技能的数值；
   · StandingTime/IsStandingUponCasting 是「施法期间禁止移动」的位移锁，不是时间项，不入秒伤；
   · 法力：不做资源约束（蓝不够的停手不在模型里），mana_cost 仅随行展示；
   · 逐技能等级未接入：全表按 profile.skill_level 单一等级算倍率（Player+0x230 的逐技能
     等级容器是混淆字段，需实机定结构后另接，见文档置信度清单 ③-13）。
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
    """每秒命中次数 = 每次施放的命中次数 ÷ 施放周期，含 ChannelSpeed / StrikeCount 天赋修正。

    每次施放命中次数 = 基础击数（StaggeredStrikesEffect.TargetCount，如 Rending Onslaught=3；
    无则为 1）+ StrikeCount 天赋附加次数（如屠夫韵律 +1 次/级）。
    引导技能按「整段周期」计：命中数 = 击数×(1+通道速度)×Duration/TickRate，
    周期 = 前摇+持续+收招+冷却×(1-CDR)（引导技能同样吃冷却，实测 7 个里 6 个有冷却）；
    冷却=0 时退化为 1/TickRate，与旧口径逐位相同。非引导有冷却 = 冷却×(1-CDR)；否则 = 1/攻速。
    """
    channel_speed = float((mods or {}).get(CHANNEL_SPEED_STAT, 0.0))
    strike_bonus = float((mods or {}).get(STRIKE_COUNT_STAT, 0.0))
    strikes = int(skill.get('strikes', 1)) + strike_bonus
    if skill['channel_duration'] > 0 and skill['tick_rate'] > 0:
        dur = float(skill['channel_duration'])
        ticks = dur / float(skill['tick_rate'])
        cdr = min(0.85, max(0.0, sheet.final(StatType.CooldownReduction)))
        cycle = (float(skill.get('channel_windup') or 0.0) + dur
                 + float(skill.get('channel_recovery') or 0.0)
                 + float(skill['cooldown']) * (1.0 - cdr))
        if cycle <= 0:
            return strikes * (1.0 + channel_speed) / float(skill['tick_rate'])
        return strikes * (1.0 + channel_speed) * ticks / cycle
    cdr = min(0.85, max(0.0, sheet.final(StatType.CooldownReduction)))
    cd = float(skill['cooldown']) * (1.0 - cdr)
    interval = cd if cd > 0.05 else (1.0 / atk_speed if atk_speed > 0 else 1.0)
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
