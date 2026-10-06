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

from deskrawl_calc import (DamageModel, StatSheet, StatType, Target,
                           compare_weapons, stat_name)

from .profile import CharacterProfile, KIND_LABELS


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
    """一次装备对比的完整结果，供视图直接渲染。"""
    current_dps: float
    candidate_dps: float
    delta: float
    delta_pct: float
    current_model: DamageModel
    candidate_model: DamageModel
    target: Target


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


def compare(profile: CharacterProfile, gd) -> CompareResult:
    """对比两把武器的期望 DPS 与变化百分比（走内核 compare_weapons）。"""
    sheet = profile.to_sheet(gd)
    target = profile.to_target()
    cur = profile.weapon_current.to_weapon()
    cand = profile.weapon_candidate.to_weapon()
    r = compare_weapons(sheet, cur, cand, target=target, damage_type=profile.damage_type)
    return CompareResult(current_dps=r['current']['dps'], candidate_dps=r['candidate']['dps'],
                         delta=r['delta'], delta_pct=r['delta_pct'],
                         current_model=r['current']['model'], candidate_model=r['candidate']['model'],
                         target=target)


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


# 修饰符类型的界面用中文名（内核 Modifier.describe() 用的是 Flat/%Add/%Mult）
_MOD_TYPE_CN = {0: '加法', 1: '百分比加算', 2: '连乘'}


def describe_mods(mods) -> str:
    """候选词条摘要。属性名复用内核 stat_name()，类型记号本地化为中文，保证界面全中文。"""
    if not mods:
        return '（无属性词条）'
    return '；'.join(f'{stat_name(m.stat)} {m.value:+.3f}'
                     f'（{_MOD_TYPE_CN.get(int(m.type), m.type)}）' for m in mods)


def _dps_with(profile: CharacterProfile, gd, extra_mods) -> float:
    """当前构建（含当前武器词条）+ extra_mods 的期望 DPS。

    排序基线与候选增量共用这一条路径，保证 Δ 可被独立复现（self-test 用引擎直算对拍）。
    """
    sheet = profile.to_sheet(gd)
    w = profile.weapon_current.to_weapon()
    sheet.add_mods(w.modifiers)
    sheet.add_mods(extra_mods)
    model = DamageModel(sheet, profile.damage_type, weapon_damage=w.base_damage)
    return model.dps(profile.to_target(), w.base_speed) * w.skill_multiplier


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
        dps = _dps_with(profile, gd, mods)
        pct = (dps / base_dps - 1.0) * 100.0 if base_dps else 0.0
        rows.append(CandidateRow(name, describe_mods(mods), dps, dps - base_dps, pct, mods))
    rows.sort(key=lambda r: -r.delta)
    return rows


__all__ = ['StatRow', 'CompareResult', 'CandidateRow', 'stat_rows', 'compare',
           'candidate_names', 'candidate_modifiers', 'describe_mods',
           'baseline_dps', 'rank_candidates', 'KIND_LABELS']
