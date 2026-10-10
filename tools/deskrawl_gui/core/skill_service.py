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

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional

from deskrawl_calc import DamageModel, StatType

from .localization import ability_display_name

__all__ = ['SkillRow', 'skill_rows', 'pick_main_row', 'ability_level_bonuses']

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


def _tag_multiplier(skill: dict, sheet) -> float:
    """技能标签对应的增伤（普攻 33 / 强力攻击 34）。

    AbilityTag：BasicAttack=0 / StrongAttack=1（旋风斩 Tags=[1,3,7] → 吃强力攻击伤害，
    角色页实测 108.3%）。属性页把这两项列在「进攻」里，此前未被任何计算路径消费。
    """
    tags = skill.get('tags') or []
    if 1 in tags:
        stat = int(StatType.StrongAttackDamage)
    elif 0 in tags:
        stat = int(StatType.BasicAttackDamage)
    else:
        return 1.0
    return 1.0 + sheet.final(stat)


def _per_hit(skill: dict, sheet, target, *, weapon, primary_stat) -> float:
    """每次命中的期望伤害（多段求和 × 普攻/强攻标签增伤）。"""
    total = 0.0
    for e in skill['effects']:
        model = DamageModel(sheet, e['damage_type'], weapon_damage=weapon.base_damage,
                            primary_stat=primary_stat, skill_scaling=e['scaling'])
        bd = model.compute(target)
        total += bd.base_damage * bd.expected_mult
    return total * _tag_multiplier(skill, sheet)


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


def ability_level_bonuses(profile, gd) -> dict:
    """已装配符文的「技能等级+N」汇总：{ability_name: bonus}（AllAbilities → '*')。

    数据源：RuneData.AbilityLevels[{Ability(pathID), Levels, EveryNRuneLevels}]。
    加成公式（实测锚定）：bonus = Levels × (rune_level // EveryNRuneLevels)——语义即「每
    EveryNRuneLevels 级符文等级授予一次 Levels」；RareRune_WarriorHeavyAttack3（Levels=2、
    EveryNRuneLevels=3）在 6/6 时 +4，两个符文 +8 → 旋风斩 10+8=18 级，与游戏 tooltip 185% 逐位一致。
    解析失败返回空表（降级为无加成）。
    """
    out = {}
    try:
        path = os.path.join(getattr(gd, 'dir', ''), 'RuneData.json')
        with open(path, encoding='utf-8') as f:
            runes = json.load(f)
    except (OSError, ValueError):
        return out
    for it in getattr(profile, 'assembled', None) or []:
        if it.kind != 'rune':
            continue
        rec = next((r for r in runes if r.get('_name') == it.name), None)
        if not rec:
            continue
        for al in rec.get('AbilityLevels') or []:
            levels = int(al.get('Levels') or 0)
            every = max(1, int(al.get('EveryNRuneLevels') or 1))
            bonus = levels * (int(it.level) // every)
            if not bonus:
                continue
            if al.get('AllAbilities'):
                out['*'] = out.get('*', 0) + bonus
                continue
            ability = (al.get('Ability') or {}).get('pathID')
            name = ability_names_by_pathid(gd).get(int(ability)) if ability else None
            if name:
                out[name] = out.get(name, 0) + bonus
    return out


@lru_cache(maxsize=4)
def ability_names_by_pathid(gd) -> dict:
    """AbilityData pathID → _name（gd.dir 直读，与 calc_service.ability_names 同一约定）。"""
    try:
        path = os.path.join(getattr(gd, 'dir', ''), 'AbilityData.json')
        with open(path, encoding='utf-8') as f:
            rows = json.load(f)
        return {int(r['_pathid']): r['_name'] for r in rows if r.get('_pathid') is not None}
    except (OSError, ValueError, TypeError):
        return {}


def skill_rows(profile, gd, cur_sheet, cand_sheet, target,
               level: Optional[int] = None) -> List[SkillRow]:
    """当前职业每个伤害技能的秒伤对比（hero_class 未知时返回空表）。

    cur_sheet/cand_sheet 来自 calc_service.compare（已含武器词条与所选槽的当前/候选装备）。
    两侧各用自己的武器（攻速与白字基础伤害都取自对应武器草稿）——武器槽对比时候选换的正是
    速度/白字，若两侧共用当前武器会漏掉这部分差异，候选列会停滞不动。
    每技能有效等级 = 基础等级 + 符文「技能等级+N」（旋风斩 10+8=18 实测，tooltip 185% 与
    缩放曲线逐位一致）；有加成的技能按有效等级重算各段 scaling。
    """
    hero_class = getattr(profile, 'hero_class', None)
    if hero_class is None:
        return []
    lv = int(profile.skill_level if level is None else level)
    bonuses = ability_level_bonuses(profile, gd)
    wildcard = bonuses.get('*', 0)
    skills = gd.damage_skills(hero_class, lv)
    w_cur = profile.weapon_current.to_weapon()
    # 非武器槽对比时两件装备不同但武器相同 → 候选侧沿用当前武器
    w_cand = (profile.weapon_candidate.to_weapon()
              if int(getattr(profile, 'compare_slot', 0)) == 0 else w_cur)
    ps = profile.primary_stat
    all_mods = getattr(profile, 'ability_mods', None) or {}

    def atk_speed(sheet, weapon) -> float:
        return weapon.base_speed * (1.0 + sheet.final(StatType.AttackSpeed))

    rows = []
    for sk in skills:
        eff_lv = lv + wildcard + bonuses.get(sk['name'], 0)
        if eff_lv != lv:
            # 按有效等级重算各段倍率（damage_skills 返回的 scaling 是基础等级口径）
            effs = gd.ability_damage_effects(sk['name'])
            for e, r in zip(sk['effects'], effs):
                e['scaling'] = (float(r['AttackScalingBase'])
                                + float(r['AttackScalingPerLevel']) * (eff_lv - 1))
        mods = all_mods.get(sk['name'], {})
        cur_rate = _hits_per_sec(sk, cur_sheet, atk_speed(cur_sheet, w_cur), mods)
        cand_rate = _hits_per_sec(sk, cand_sheet, atk_speed(cand_sheet, w_cand), mods)
        cur = _per_hit(sk, cur_sheet, target, weapon=w_cur, primary_stat=ps) * cur_rate
        cand = _per_hit(sk, cand_sheet, target, weapon=w_cand, primary_stat=ps) * cand_rate
        # 展示名用游戏本地化的简中名（表缺失回落英文），name 保留 _name 供天赋修正查表
        rows.append(SkillRow(name=sk['name'],
                             ability_name=ability_display_name(gd, sk['name']),
                             level_req=sk['level_req'], current_dps=cur, candidate_dps=cand,
                             delta=cand - cur,
                             delta_pct=((cand / cur - 1.0) * 100.0) if cur else 0.0,
                             hits_per_sec=cur_rate,
                             interval=(1.0 / cur_rate) if cur_rate > 0 else 0.0))
    return rows


def pick_main_row(rows: List[SkillRow], profile) -> Optional[SkillRow]:
    """选「主力技能」行：优先 profile.skill_name（角色页参考技能），否则取当前秒伤最高行。

    实战输出高度集中于主力技能（用户实测口径），循环系数与候选预测都应以它为期望基座——
    技能行含全部天赋加成（被动走属性表、引导/击数走 ability_mods），比武器倍率口径更完整。
    """
    want = getattr(profile, 'skill_name', '') or ''
    if want:
        for r in rows:
            if r.name == want:
                return r
    return max(rows, key=lambda r: r.current_dps, default=None)
