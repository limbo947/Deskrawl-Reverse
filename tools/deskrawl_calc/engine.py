# -*- coding: utf-8 -*-
"""属性聚合（三层模型）与伤害计算引擎。

实现依据（全部来自指令级逆向，见 04-伤害计算与属性关联）：
  Final(stat) = (Base + ΣFlat) × (1 + ΣPercentAdd) × Π(1 + PercentMult)      ✅ 6.1
  bjr : attackDamage = (武器伤害 + Damage(3)) × (1 + Final(主属性)/100)       ✅ 6.2.0
  bkn : typeMul = 1 + Final(Damage<type>) + Final(DamagePercent)             ✅ 6.2.1
  bko : condMul = 1 + Σ(命中的条件伤害项)                                     ✅ 6.2.2
  crit: critChance = clamp(Final(CritChance)+buff+cond, 0, 0.85)             ✅ 6.2.3
        critMul    = 1 + Final(CritDamage)+equip
  封顶 1.0.2b：CDR 0.85→0.80；通用/元素减伤上限 90%（StatCap.GetCap@0x4AECB0 实证）
  armor: resist/(resist + 50 × max(1, level))                                ✅ 6.2.4
  减伤 : ×(1-armorResist)×(1-elemRed)×(1-DamageReduction)                    ✅
  最终减伤: − Final(FinalDamageReduction)，下限 0（乘区之后的一次绝对减法）      ✅ 6.2.7
  易伤 : ×1.3（固定），另 VulnerableDamage 计入条件池                          ✅ 6.2.5
  最低伤害 1；命中浮动 ×U(0.9,1.1)                                            ✅

标注 🔶 的部分为按代码结构推断（引擎已把它们做成可覆盖参数，便于日后校正）。
"""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .stattype import (StatType, ModifierType, DamageType, DAMAGE_TYPE_TO_STAT,
                       CORE, ALL_ELEMENTS, CONDITIONAL_DAMAGE, CAPPED_085, CAPPED_080,
                       CAPPED_090, ELEM_REDUCTION_BY_DAMAGE, name as stat_name)


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else (hi if v > hi else v)


# --------------------------------------------------------------------------- #
# 数值解析（兼容 so_dump 里的 Obscured* / LeveledFloat 结构）
# --------------------------------------------------------------------------- #
def unwrap(v):
    """从 dump 的嵌套结构里取出真实数值；取不到返回 None。

    支持：纯数、Obscured*({...,'value':x})、LeveledFloat({Base,PerLevel})。
    """
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    if isinstance(v, dict):
        if 'value' in v and isinstance(v['value'], (int, float)):
            return float(v['value'])
        if 'Base' in v:
            return unwrap(v['Base'])
    return None


def leveled_value(base, per_level, level: int) -> float:
    """LeveledFloat.wo(level) = Base + max(0, level-1) × PerLevel（等级 1 基）。✅"""
    b = unwrap(base) or 0.0
    p = unwrap(per_level) or 0.0
    return b + max(0, level - 1) * p


# --------------------------------------------------------------------------- #
# 修饰符与属性表
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Modifier:
    """最小数值单元 StatModifier：Stat + Type + Value。"""
    stat: int
    type: int = int(ModifierType.Flat)
    value: float = 0.0

    def describe(self) -> str:
        t = {0: 'Flat', 1: '%Add', 2: '%Mult'}[int(self.type)]
        return f'{stat_name(self.stat)} {self.value:+.3f} [{t}]'


class StatSheet:
    """三层聚合表。可直接把来自装备/宝石/符文/天赋/Buff 的所有 Modifier 丢进来。"""

    def __init__(self, base: Optional[Dict[int, float]] = None):
        self.base: Dict[int, float] = dict(base or {})
        self.flat: Dict[int, float] = {}
        self.add: Dict[int, float] = {}
        self.mult: Dict[int, float] = {}   # 存的是 (1+v) 的连乘结果

    def add_mod(self, m: Modifier) -> 'StatSheet':
        s = int(m.stat)
        if int(m.type) == int(ModifierType.Flat):
            self.flat[s] = self.flat.get(s, 0.0) + m.value
        elif int(m.type) == int(ModifierType.PercentAdd):
            self.add[s] = self.add.get(s, 0.0) + m.value
        elif int(m.type) == int(ModifierType.PercentMult):
            self.mult[s] = self.mult.get(s, 1.0) * (1.0 + m.value)
        return self

    def add_mods(self, mods) -> 'StatSheet':
        for m in mods:
            self.add_mod(m)
        return self

    def clone(self) -> 'StatSheet':
        c = StatSheet(self.base)
        c.flat = dict(self.flat); c.add = dict(self.add); c.mult = dict(self.mult)
        return c

    def final(self, stat) -> float:
        """Final(stat) = (Base + ΣFlat) × (1 + ΣPercentAdd) × Π(1+PercentMult)。"""
        s = int(stat)
        return ((self.base.get(s, 0.0) + self.flat.get(s, 0.0))
                * (1.0 + self.add.get(s, 0.0))
                * self.mult.get(s, 1.0))

    def capped(self, stat) -> float:
        """按游戏规则 clamp：0.85（暴击/闪避/蓝耗）/0.80（CDR，1.0.2b）/0.90（减伤类，1.0.2b）。"""
        s = int(stat)
        v = self.final(s)
        if stat in CAPPED_085:
            return _clamp(v, 0.0, 0.85)
        if stat in CAPPED_080:
            return _clamp(v, 0.0, 0.80)
        if stat in CAPPED_090:
            return _clamp(v, 0.0, 0.90)
        return v

    def breakdown(self, stat) -> Dict[str, float]:
        s = int(stat)
        return {'Base': self.base.get(s, 0.0), 'Flat': self.flat.get(s, 0.0),
                'PercentAdd': self.add.get(s, 0.0),
                'PercentMultΠ': self.mult.get(s, 1.0), 'Final': self.final(s)}


# --------------------------------------------------------------------------- #
# 目标（受击方）模型
# --------------------------------------------------------------------------- #
@dataclass
class Target:
    level: int = 1
    hp_fraction: float = 1.0
    armor: float = 0.0
    magic_resist: float = 0.0
    elem_reduction: Dict[int, float] = field(default_factory=dict)  # DamageType -> 值
    damage_reduction: float = 0.0
    # 最终减伤（StatType.FinalDamageReduction=66，1.0.3 新增）：**绝对量**，在所有乘区之后一次性减法、下限 0。
    # 指令级依据：Character.ApplyDamage@0x1806893E0 尾部 `subsd xmm6, clamp(Final(66))` → `max(0, trunc(·))`，
    # 且该 stat 走 StatCap.Clamp（GetCap 落 inf 分支→无上限）。见 docs/04 §6.2.7。
    final_damage_reduction: float = 0.0
    # 暴击伤害减免（StatType.CritDamageReduction=60，**目标方**）：DOT 跳伤暴击按 (1−clamp01(·)) 折减。
    # 指令级依据：DamageOverTimeBehavior 暴击因子（ys）反汇编 `1 + (1−clamp01(target.Final(60)))×(Final(5)+bonus)`。
    crit_damage_reduction: float = 0.0
    vulnerable: bool = False
    slowed: bool = False
    immobilized: bool = False
    bleeding: bool = False
    poisoned: bool = False
    burned: bool = False
    elite: bool = False
    distant: bool = False

    def resist(self, damage_type: int) -> float:
        return self.armor if int(damage_type) == int(DamageType.Physical) else self.magic_resist

    def armor_resist(self, damage_type: int) -> float:
        """armorResist = resist / (resist + 50 × max(1, level))。常量 50 @ 0x183681610（补丁前 0x18363F120，见 docs/08 §13.2）。"""
        r = self.resist(damage_type)
        return r / (r + 50.0 * max(1, self.level)) if (r + 50.0) > 0 else 0.0

    def conditional_stats(self) -> List[StatType]:
        """按目标状态挑出生效的条件伤害属性（bko 10 项）。"""
        out = []
        if self.hp_fraction > 0.8: out.append(StatType.DamageVsHealthy)
        if self.hp_fraction < 0.3: out.append(StatType.DamageVsInjured)
        if self.slowed: out.append(StatType.DamageVsSlowed)
        if self.immobilized: out.append(StatType.DamageVsImmobilized)
        if self.bleeding: out.append(StatType.DamageVsBleeding)
        if self.poisoned: out.append(StatType.DamageVsPoisoned)
        if self.burned: out.append(StatType.DamageVsBurned)
        if self.distant: out.append(StatType.DamageVsDistant)
        if self.elite: out.append(StatType.DamageVsElite)
        if self.vulnerable: out.append(StatType.VulnerableDamage)
        return out


# --------------------------------------------------------------------------- #
# 伤害计算
# --------------------------------------------------------------------------- #
@dataclass
class DamageBreakdown:
    base_damage: float
    type_mult: float          # 乘区 A
    crit_chance: float
    crit_mult: float          # 乘区 B（命中时）
    cond_mult: float          # 乘区 C
    vulnerable_mult: float    # 乘区 D（1.0 或 1.3）
    armor_mult: float
    elem_red_mult: float
    global_red_mult: float
    final_mult: float         # A×B×C×D×减伤（不含随机与最低伤害）
    expected_mult: float      # 用暴击期望替代暴击判定后的期望倍率
    effective_dps: float = 0.0


class DamageModel:
    """攻击方模型：把角色面板参数与目标一起喂进来即可算伤害/DPS。"""

    def __init__(self, sheet: StatSheet, damage_type=DamageType.Physical, *,
                 level: int = 1,
                 buff_crit: float = 0.0,      # SEC.bgm 提供的暴击率加成
                 conditional_crit: float = 0.0,  # 装备/天赋条件暴击（bkl）
                 equip_crit_damage: float = 0.0,  # 装备/天赋额外的暴伤加成
                 damage_dealt_mult: float = 1.0,  # 攻击方 SEC.bgl 增/减伤
                 weapon_damage: float = 0.0,  # 武器基础伤害（面板）
                 primary_stat: Optional[int] = None,  # 职业主属性 StatType 0/1/2；None=不启用
                 skill_scaling: float = 1.0,  # 技能倍率 AttackScaling.wo(level)；1.0=普攻
                 armor_pen: float = 0.0):     # 破甲（占位，引擎未证实存在）
        self.sheet = sheet
        self.damage_type = int(damage_type)
        self.level = level
        self.buff_crit = buff_crit
        self.conditional_crit = conditional_crit
        self.equip_crit_damage = equip_crit_damage
        self.damage_dealt_mult = damage_dealt_mult
        self.weapon_damage = weapon_damage
        self.primary_stat = primary_stat
        self.skill_scaling = float(skill_scaling)
        self.armor_pen = armor_pen

    # --- 乘区 A ---
    def type_multiplier(self) -> float:
        elem = self.sheet.final(DAMAGE_TYPE_TO_STAT[DamageType(self.damage_type)])
        allpct = self.sheet.final(StatType.DamagePercent)
        return 1.0 + elem + allpct

    # --- 乘区 C ---
    def conditional_multiplier(self, target: Target) -> float:
        return 1.0 + sum(self.sheet.final(s) for s in target.conditional_stats())

    # --- 暴击 ---
    def crit_chance(self) -> float:
        return _clamp(self.sheet.final(StatType.CritChance) + self.buff_crit + self.conditional_crit, 0.0, 0.85)

    def crit_multiplier(self) -> float:
        return 1.0 + self.sheet.final(StatType.CritDamage) + self.equip_crit_damage

    # --- 攻击方基础伤害（Player.CalcDamage@0x518230：武器伤害 + 通用增伤(3)，再乘主属性加成）---
    def primary_stat_multiplier(self) -> float:
        """×(1 + Final(职业主属性)/100)。主属性由 Player.PrimaryStatValue@0x500CA0 给出
        （英雄职业主属性：0=力量/1=敏捷/2=智力，Barbarian=0 实证）；None=不启用。

        游戏内力量 tooltip「当前提升 451% 伤害」即 451 代入本式（×5.51），2026-10-09 截图实证。
        """
        if self.primary_stat is None:
            return 1.0
        return 1.0 + self.sheet.final(int(self.primary_stat)) / 100.0

    def attack_damage(self) -> float:
        """单次攻击基础伤害 = (武器伤害 + 技能倍率×(武器伤害%+ 通用增伤)) ×(1 + 主属性/100)。

        技能倍率走 bjr（docs/04 §6.2）：(BaseDamage + scaling×(Final(20)+Final(3)))×主属性因子；
        weapon_damage 即公式里的 BaseDamage（不被 scaling 放大）。skill_scaling=1.0 时逐位退化为
        普攻口径（保留原结合顺序，避免浮点末位偏差）。
        """
        return self._scaled_attack_damage(self.skill_scaling)

    def _scaled_attack_damage(self, scaling: float) -> float:
        """把技能倍率换成任意系数（DOT 跳伤传 DamagePerTick，复用同一结合顺序）。"""
        core = self.weapon_damage + scaling * self.sheet.final(StatType.WeaponDamage)
        return (core + scaling * self.sheet.final(StatType.Damage)) * self.primary_stat_multiplier()

    def dot_tick_damage(self, target: Target, damage_per_tick: float,
                        *, can_crit: bool = False) -> float:
        """DOT 每跳伤害（DamageOverTimeBehavior tick 链：apply `yt`（存实例 lxt）→ tick `yp`）。

        `tick = (Clamp(Final(62)) + 元素乘区) × base × 条件池`——
        · `(62 + 元素乘区)` 同池加算（`yt` 反汇编 `addsd`，语义别名见 aliases.json）；
        · `base` 为武器伤害按 DamagePerTick 折算的攻击伤害（对应 apply 时 `Character.<m>(0, DamagePerTick)`）；
        · `条件池` = `engine.conditional_multiplier(target)`——指令级：tick 内 `[caster_klass+0x228]` 运行时
          解析为 `Character.ConditionalDamagePool`（`blw`，.Player/.Enemy klass+0x228 实证）；
        · CanCrit 时暴击因子 `1 + 暴击率 × (1 − clamp01(target.Final(60))) × (Final(5)+暴伤加成)`（`ys` 反汇编）；
        · 最后按 `ApplyDamage` 收口减伤层（与直击同）。
        实例层叠层由调用方按占空比上限折算（`skill_service._dot_dps`）。

        ⚠️ 边界（已定）：技能类型标签乘区 33/34/61 **不**参与 DOT——tick 的 vtable+0x228 已证实是条件池
        （`blw`），标签乘区只在直击 `DamageEffect` 应用点生效；实例倍率 `bl.lxp`(@0x30) 在 `.ctor` 与
        apply（`StatusEffectController.bgw`）均写死 `1.0f`，本式按 1.0 与实机一致。
        """
        atk = self._scaled_attack_damage(damage_per_tick)
        pool = self.type_multiplier() + self.sheet.final(StatType.DamageOverTime)
        tick = atk * pool * self.conditional_multiplier(target)
        if can_crit:
            cd_red = _clamp(target.crit_damage_reduction, 0.0, 1.0)
            tick *= 1.0 + self.crit_chance() * (1.0 - cd_red) * (self.crit_multiplier() - 1.0)
        am, er, gr = self.mitigation(target)
        return max(1.0, tick * am * er * gr)

    # --- 减伤层 ---
    def mitigation(self, target: Target):
        ar = target.armor_resist(self.damage_type)
        if self.armor_pen:
            ar = ar * (1.0 - _clamp(self.armor_pen, 0.0, 1.0))
        er = _clamp(target.elem_reduction.get(self.damage_type, 0.0), 0.0, 0.90)
        gr = _clamp(target.damage_reduction, 0.0, 0.90)
        return (1.0 - ar), (1.0 - er), (1.0 - gr)

    # --- 完整计算 ---
    def compute(self, target: Target, *, rng: Optional[random.Random] = None,
                attack_speed: Optional[float] = None) -> DamageBreakdown:
        rng = rng or random.Random()
        atk = self.attack_damage()
        type_mul = self.type_multiplier()
        cc = self.crit_chance()
        cm = self.crit_multiplier()
        cond = self.conditional_multiplier(target)
        vuln = 1.3 if target.vulnerable else 1.0
        am, er, gr = self.mitigation(target)

        # 伤害（含暴击判定 + 命中浮动）
        dmg = atk * type_mul
        is_crit = rng.random() < cc
        if is_crit:
            dmg *= cm
        dmg *= rng.uniform(0.9, 1.1)
        dmg *= cond
        dmg = round(dmg)
        dmg *= vuln
        dmg *= self.damage_dealt_mult
        dmg *= am * er * gr
        # 最终减伤：乘区之后的**绝对减法**（非倍率），下限 0（游戏 trunc+max(0,·)，见 docs/04 §6.2.7）
        if target.final_damage_reduction:
            dmg = max(0.0, dmg - max(0.0, target.final_damage_reduction))
        dmg = max(1.0, dmg)

        # 期望倍率（暴击期望，用于装备对比，避免随机噪声）。
        # 注：最终减伤是绝对量、无法折进倍率，故 expected/final_mult **不含**它——装备对比走倍率口径，
        # 该项只影响单次绝对伤害（对攻击方 DPS 无影响：66 是受击方属性）。
        expected = type_mul * (1.0 + cc * (cm - 1.0)) * cond * vuln * self.damage_dealt_mult * am * er * gr
        final_mult = type_mul * (cm if is_crit else 1.0) * cond * vuln * self.damage_dealt_mult * am * er * gr

        bd = DamageBreakdown(base_damage=atk, type_mult=type_mul, crit_chance=cc,
                             crit_mult=(cm if is_crit else 1.0), cond_mult=cond,
                             vulnerable_mult=vuln, armor_mult=am, elem_red_mult=er,
                             global_red_mult=gr, final_mult=final_mult,
                             expected_mult=expected)
        if attack_speed is not None:
            # 最终减伤折进**绝对**期望伤害（不是倍率）：exp_hit = max(1, atk×expected − Final(66))
            exp_hit = atk * expected
            if target.final_damage_reduction:
                exp_hit = max(1.0, exp_hit - max(0.0, target.final_damage_reduction))
            bd.effective_dps = exp_hit * attack_speed
        return bd

    def effective_attack_speed(self, base_speed: float) -> float:
        """🔶 攻速：面板 % 加成按 Flat/加法入池，故 乘 (1 + Final(AttackSpeed))。"""
        return base_speed * (1.0 + self.sheet.final(StatType.AttackSpeed))

    def dps(self, target: Target, base_speed: float) -> float:
        """期望 DPS = 单次期望伤害 × 每秒攻击次数。"""
        speed = self.effective_attack_speed(base_speed)
        return self.compute(target, attack_speed=speed).effective_dps


# --------------------------------------------------------------------------- #
# 装备对比
# --------------------------------------------------------------------------- #
@dataclass
class Weapon:
    name: str
    base_damage: float
    base_speed: float                       # 每秒攻击次数
    modifiers: List[Modifier] = field(default_factory=list)
    skill_multiplier: float = 1.0           # 🔶 技能倍率（DamageEffect.BaseDamage×AttackScaling），按需填


def compare_weapons(base_sheet: StatSheet, current: Weapon, candidate: Weapon, *,
                    target: Optional[Target] = None, damage_type=DamageType.Physical,
                    **attacker_kw) -> Dict:
    """比较两把武器：返回各自期望 DPS 与变化百分比。"""
    target = target or Target()
    out = {}
    for tag, w in (('current', current), ('candidate', candidate)):
        sheet = base_sheet.clone().add_mods(w.modifiers)
        model = DamageModel(sheet, damage_type, weapon_damage=w.base_damage, **attacker_kw)
        dps = model.dps(target, w.base_speed) * w.skill_multiplier
        out[tag] = {'weapon': w.name, 'dps': dps, 'sheet': sheet, 'model': model}
    cur, cand = out['current']['dps'], out['candidate']['dps']
    out['delta'] = (cand - cur)
    out['delta_pct'] = (cand / cur - 1.0) * 100.0 if cur else float('inf')
    return out
