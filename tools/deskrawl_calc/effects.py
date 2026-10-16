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


def _cls(e: dict) -> str:
    return str((e or {}).get('_class') or '')


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


def crit_terms(effects: List[dict], target, *, status_names: Optional[Dict[int, str]] = None
               ) -> Tuple[float, float]:
    """条件暴击贡献 → (额外暴击率, 额外暴伤)，已按目标状态门控。

    · `ConditionalCritChance`：`Condition` 命中 → +`BonusCritChance`；
    · `ConditionalCritDamage`：`Condition`（+`Status`）命中 → +`BonusCritDamage`，
      `ScaleByStatusStacks` 为真时再 ×层数（🔶 层数语义待 REA）。
    """
    cc = 0.0
    cd = 0.0
    for e in effects or []:
        cls = _cls(e)
        if cls.endswith('ConditionalCritChance'):
            if condition_holds(e.get('Condition', -1), target):
                cc += float(unwrap(e.get('BonusCritChance')) or 0.0)
        elif cls.endswith('ConditionalCritDamage'):
            sn = _name_of(e.get('Status'), status_names)
            if condition_holds(e.get('Condition', -1), target, sn):
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
        if not _cls(e).endswith('AbilityTagCritDamage'):
            continue
        an = _name_of(e.get('Ability'), ability_names)
        if an is not None:
            if an == ability_name:
                out += float(unwrap(e.get('BonusCritDamage')) or 0.0)
        elif int(e.get('Tag', _ABILITY_TAG_NONE)) != _ABILITY_TAG_NONE:
            if int(e.get('Tag', _ABILITY_TAG_NONE)) in tset:
                out += float(unwrap(e.get('BonusCritDamage')) or 0.0)
    return out
