# -*- coding: utf-8 -*-
"""EquipmentEffect_* 语义解释（纯函数：保真 effect dict → 数值贡献）。

首批 A（《传奇特效清点清单》§3）接线用：条件暴击 / 标签暴伤 / 技能修改 / 属性换算 / 条件伤害。
本模块只做「effect dict (+ 目标/技能) → 数值」的解释，不依赖 GUI，可被内核自检直接回归。

判定口径（🔶 = 结构推断待 REA/实机复核，已登记 `docs/plan/文档置信度待核清单.md`）：
  · `_class` 与字段名取自 `data/schema/dump.cs` 的 `EquipmentEffect_*` 定义；
  · `Condition` 用 `TargetStateCondition`（0 Vulnerable / 1 Stunned / 2 Slowed / 3 Elite /
    4 Immobilized / 5 SpecificStatus / 6 Distant，见 docs/02）；
  · `Tag` 用 `AbilityTag`（9999 = None）；`Stat` 用 `TalentEffect_AbilityModifier.ModifiedStat`；
  · `Ability`/`Status`/`Effects` 是 `{fileID, pathID}` 引用，按 pathID 反查名称。
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .engine import unwrap
from .gamedata import _ref_pathid

# TargetStateCondition → Target 布尔字段（5 = SpecificStatus 另走状态名集合）
_TARGET_STATE_ATTR = {0: 'vulnerable', 1: 'stunned', 2: 'slowed', 3: 'elite',
                      4: 'immobilized', 6: 'distant'}

_ABILITY_TAG_NONE = 9999

# 已接线（进 DPS / 属性表）的特效类（去 `EquipmentEffect_` 前缀）。新增消费点必须同步这里，
# 否则「未计入 DPS」提示会对已算的装备误报。
CONSUMED_CLASSES = frozenset({
    'StatModifier', 'AllStats', 'ConditionalCritChance', 'ConditionalCritDamage',
    'AbilityTagCritDamage', 'ConditionalDamage', 'AbilityModifier',
    'AbilityChannelModifier', 'StatConversion', 'DivineHelmet3',
})

# 触发/行为类（清点清单 D 面 35 条）：面板口径本就不含触发链，属刻意排除而非缺口，
# 不参与「未计入」提示——否则 67 件里 23 件都会被标，提示就失去意义。
TRIGGER_CLASSES = frozenset({
    'StatusOnHit', 'TriggerEffectsOnPotionUse', 'StatusOnKill', 'AbilityTriggerAbility',
    'TriggerEffectsOnHit', 'StatusApplyStatus', 'TriggerAbilityCooldownReduction',
    'AbilitySummonAbility', 'SelfStatusStackTriggerAbility', 'IronThornFrenzy',
    'PotionDrops', 'StatusOnCritTaken', 'FreeCast', 'AbilityOnCastCount',
    'BeingHitTriggerAbility', 'TriggerAbilityTwice', 'TrapRearm', 'TriggerEffectsOnCrit',
    'ChannelAllowedCastTag', 'StatusOnLowHealth', 'StatusOnResourceConsumed',
    'TriggerKillEffectsOnHit',
})


def _cls(e: dict) -> str:
    return str((e or {}).get('_class') or '')


def _is(e: dict, short_name: str) -> bool:
    """类名精确匹配（剥资产前缀；仍精确，避免 `AlwaysHealthConditionalDamage` 误命中 `ConditionalDamage`）。

    装备与天赋两套前缀都剥：同名特效字段几乎同构（`Condition`/`BonusCritChance`），
    共用一套解释函数才不会出现「装备能算、天赋不能算」的分裂。
    """
    name = _cls(e).split('.')[-1]
    return name.removeprefix('EquipmentEffect_').removeprefix('TalentEffect_') == short_name


# 目标负面状态（🔶 集合口径，供 `DamagePerNegativeStatus` 计数；不含易伤/精英/远处）
_NEGATIVE_ATTRS = ('slowed', 'immobilized', 'bleeding', 'poisoned', 'burned', 'stunned')


def negative_status_count(target) -> int:
    """目标身上的负面状态数（`DamagePerNegativeStatus` 的乘数，🔶 集合待 REA 核实）。"""
    return sum(1 for a in _NEGATIVE_ATTRS if getattr(target, a, False))


def _name_of(ref, names: Optional[Dict[int, str]]) -> Optional[str]:
    pid = _ref_pathid(ref)
    if pid is None or not names:
        return None
    return names.get(int(pid))


def status_stacks(target, status_name: str) -> float:
    """目标身上某状态的层数（`Target.statuses`：名→层数）；不存在则 0。"""
    st = getattr(target, 'statuses', None) or {}
    return float(st.get(status_name, 0.0) or 0.0)


def condition_holds(cond, target, status_name: Optional[str] = None) -> bool:
    """`TargetStateCondition` 门控：目标当前是否满足该条件。

    ⚠️ 与 `Target.conditional_stats()`（`bko` 10 项条件伤害池）**分离**——那是一组 StatType，
    这里是特效自己的门控谓词，勿混用。
    """
    c = int(cond)
    if c == 5:                                   # SpecificStatus：按状态名匹配
        return bool(status_name) and status_stacks(target, status_name) > 0
    attr = _TARGET_STATE_ATTR.get(c)
    return bool(getattr(target, attr, False)) if attr else False


def _scope_hit(e: dict, ability_name: Optional[str], tags,
               ability_names: Optional[Dict[int, str]]) -> bool:
    """技能/标签限定是否命中：无限定恒真；有限定但调用方没给技能上下文 → 假。

    面板口径（不传技能）跳过限定项，是刻意的保守：把「某技能的 +100% 暴击」摊给
    所有技能会高估整张技能表。
    """
    tag = e.get('Tag')
    has_tag = tag is not None and int(tag) != _ABILITY_TAG_NONE
    has_ab = bool(e.get('Ability'))
    if not has_ab and not has_tag:
        return True
    if ability_name is None:
        return False
    if has_ab and _name_of(e.get('Ability'), ability_names) == ability_name:
        return True
    return bool(has_tag and int(tag) in {int(t) for t in (tags or [])})


def crit_terms(effects: List[dict], target, *, status_names: Optional[Dict[int, str]] = None,
               ability_names: Optional[Dict[int, str]] = None,
               ability_name: Optional[str] = None, tags=None) -> Tuple[float, float]:
    """条件暴击贡献 → (额外暴击率, 额外暴伤)，按目标状态门控 + 可选技能/标签限定。

    · `ConditionalCritChance`：`Condition` 命中 → +`BonusCritChance`；
    · `ConditionalCritDamage`：`Condition`（+`Status`）命中 → +`BonusCritDamage`，
      `ScaleByStatusStacks` 为真时再 ×层数（🔶 层数语义待 REA）；
    · `Status`（装备侧）与 `SpecifiedStatus`（天赋侧）是同义字段，统一按状态名匹配。
    """
    cc = 0.0
    cd = 0.0
    for e in effects or []:
        if not (_is(e, 'ConditionalCritChance') or _is(e, 'ConditionalCritDamage')):
            continue
        if not _scope_hit(e, ability_name, tags, ability_names):
            continue
        sn = _name_of(e.get('Status') or e.get('SpecifiedStatus'), status_names)
        if not condition_holds(e.get('Condition', -1), target, sn):
            continue
        if _is(e, 'ConditionalCritChance'):
            cc += float(unwrap(e.get('BonusCritChance')) or 0.0)
        else:
            v = float(unwrap(e.get('BonusCritDamage')) or 0.0)
            if e.get('ScaleByStatusStacks') and sn:
                v *= status_stacks(target, sn)
            cd += v
    return cc, cd


def ability_crit_damage(effects: List[dict], tags, ability_name: Optional[str], *,
                        ability_names: Optional[Dict[int, str]] = None) -> float:
    """`AbilityTagCritDamage` 对某技能的额外暴伤（按 `Ability` 名或 `Tag` 命中）。

    命中口径：`Ability` 非空 → 按技能名精确匹配；否则 `Tag` != None(9999) → 该 tag 在技能
    `Tags` 中即命中（元素标签 8/10/13 等）。两条件都缺省则不计。
    """
    tset = {int(t) for t in (tags or [])}
    out = 0.0
    for e in effects or []:
        if not _is(e, 'AbilityTagCritDamage'):
            continue
        an = _name_of(e.get('Ability'), ability_names)
        if an is not None:
            if an == ability_name:
                out += float(unwrap(e.get('BonusCritDamage')) or 0.0)
        elif int(e.get('Tag', _ABILITY_TAG_NONE)) != _ABILITY_TAG_NONE:
            if int(e.get('Tag', _ABILITY_TAG_NONE)) in tset:
                out += float(unwrap(e.get('BonusCritDamage')) or 0.0)
    return out


def conditional_damage(effects: List[dict], damage_type: int, target, *,
                       status_names: Optional[Dict[int, str]] = None,
                       ability_names: Optional[Dict[int, str]] = None,
                       ability_name: Optional[str] = None) -> float:
    """`ConditionalDamage` 对**本次伤害类型**的额外条件伤害，加进条件池乘区 C。

    命中三条件（🔶 归属待 REA：条件池加项 vs 元素池加算）：
      · `Condition` 成立（`Status` 用于 `SpecificStatus` 的名匹配）；
      · `DamageType` == 本次伤害类型（Neck7=物理、Shoulder4=冰霜/毒素）；
      · `Ability` 为空 或 等于本次技能名。
    数值 = `BonusDamage` + `DamagePerNegativeStatus` × 目标负面状态数。
    """
    out = 0.0
    for e in effects or []:
        if not _is(e, 'ConditionalDamage'):
            continue
        if int(e.get('DamageType', -1)) != int(damage_type):
            continue
        an = _name_of(e.get('Ability'), ability_names)
        if an is not None and an != ability_name:
            continue
        sn = _name_of(e.get('Status'), status_names)
        if not condition_holds(e.get('Condition', -1), target, sn):
            continue
        out += float(unwrap(e.get('BonusDamage')) or 0.0)
        out += (float(unwrap(e.get('DamagePerNegativeStatus')) or 0.0)
                * negative_status_count(target))
    return out


def enemy_class_multiplier(effects: List[dict], target) -> float:
    """`DivineHelmet3` 的对普通/精英敌人伤害倍率：按目标是否精英取 `Normal`/`Elite`，多条相乘。

    进 `damage_dealt_mult`（独立乘数）而不是条件池：字段名即 Multiplier、取值 >1（1.2/1.4），
    与「+X% 条件词条」的加项不同句式；⚠️ 计入方式属设计判断，待 REA 定案。
    """
    mult = 1.0
    elite = bool(getattr(target, 'elite', False))
    for e in effects or []:
        if not _is(e, 'DivineHelmet3'):
            continue
        v = unwrap(e.get('EliteEnemyMultiplier' if elite else 'NormalEnemyMultiplier'))
        if isinstance(v, (int, float)) and 0.0 < float(v) < 100.0:
            mult *= float(v)
    return mult


def unmodeled_classes(effects: List[dict]) -> List[str]:
    """本组特效里「数值型但当前口径没算」的类（清点清单 B/C 面），供 UI 标「未计入 DPS」。

    只报 B/C：触发类（D 面）属口径刻意排除，一并标出会让触发性装备全带提示，等于没提示。
    """
    out: List[str] = []
    for e in effects or []:
        name = _cls(e).split('.')[-1].removeprefix('EquipmentEffect_')
        if name and name not in CONSUMED_CLASSES and name not in TRIGGER_CLASSES \
                and name not in out:
            out.append(name)
    return out


def ability_mods_for(effects: List[dict], ability_name: Optional[str], tags, *,
                     ability_names: Optional[Dict[int, str]] = None,
                     channel_base: float = 0.0) -> Dict[int, float]:
    """该技能命中的 `AbilityModifier` / `AbilityChannelModifier` 修正 → {ModifiedStat: 值}（同键相加）。

    · `AbilityModifier`：`Ability` 非空 → 按技能名精确匹配；否则 `Tag` != None(9999) → tag ∈ 技能
      `Tags` 即命中 → `Stat`(ModifiedStat) += `Modifier`；
    · `AbilityChannelModifier`：`Ability` 名匹配 → ChannelSpeed(8) += `ChannelSpeedBonus`（比例）、
      ChannelDuration(13) += `AdditionalChannelDurationSeconds / channel_base`（秒 → 比例）。

    指令级依据（REA 反编译 `EquipmentEffect_AbilityChannelModifier.bzw` 0x1806f4220）：
    装备侧引导时长经 `FUN_18050ed40(player, Ability, AdditionalChannelDurationSeconds / *(float*)(Ability+0xd0), 0)`
    注册——**先除以技能基础引导时长归一为比例**；`EquipmentEffect_AbilityModifier.bzw`（0x1806f4c70）
    的 Stat=13 则把 `Modifier` **原值**（已是比例）走同一 `FUN_18050ed40`。故两者**同池按比例相加**，
    消费口径为 `dur = base × (1 + Σ比例)`（数值上等价于装备「秒数加算」：base×(1+s/base) = base+s）。

    返回的 `ModifiedStat`：2 Damage / 5 CritChance / 6 CritDamage / 0 Cooldown → 进 `_per_hit` 与
    `_rates`；8 ChannelSpeed / 9 StrikeCount / 13 ChannelDuration(比例) → 进 `_rates`；
    其余（如 1 ManaCost）当前不落伤害口径。
    """
    tagset = {int(t) for t in (tags or [])}
    out: Dict[int, float] = {}
    for e in effects or []:
        if _is(e, 'AbilityModifier'):
            an = _name_of(e.get('Ability'), ability_names)
            if an is not None:
                hit = (an == ability_name)
            else:
                tag = int(e.get('Tag', _ABILITY_TAG_NONE))
                hit = tag != _ABILITY_TAG_NONE and tag in tagset
            if hit:
                st = int(e.get('Stat', -1))
                out[st] = out.get(st, 0.0) + float(unwrap(e.get('Modifier')) or 0.0)
        elif _is(e, 'AbilityChannelModifier'):
            an = _name_of(e.get('Ability'), ability_names)
            if an is not None and an == ability_name:
                out[8] = out.get(8, 0.0) + float(unwrap(e.get('ChannelSpeedBonus')) or 0.0)
                if channel_base > 0:
                    out[13] = out.get(13, 0.0) + (float(
                        unwrap(e.get('AdditionalChannelDurationSeconds')) or 0.0) / float(channel_base))
    return out


def stat_conversions(effects: List[dict]) -> List[Tuple[int, int, float]]:
    """`StatConversion` → [(SourceStat, TargetStat, Fraction)]（🔶 语义待 REA）。

    调用方在属性表装配**完成后**逐条 `StatSheet.add_conversion(src, tgt, frac)`。
    """
    out: List[Tuple[int, int, float]] = []
    for e in effects or []:
        if _is(e, 'StatConversion'):
            out.append((int(e.get('SourceStat', -1)), int(e.get('TargetStat', -1)),
                        float(unwrap(e.get('Fraction')) or 0.0)))
    return out
