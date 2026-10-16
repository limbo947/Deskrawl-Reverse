# -*- coding: utf-8 -*-
"""Deskrawl 数值计算内核（公式/数据层，UI 后置）。

用法：
    from deskrawl_calc import GameData, StatSheet, Modifier, Weapon, Target, compare_weapons

见 cli.py 的 selftest 与 demo。
"""
from .stattype import (StatType, ModifierType, DamageType, STAT_NAMES, name as stat_name,
                       CORE, ALL_ELEMENTS, CONDITIONAL_DAMAGE)
from .engine import (Modifier, StatSheet, Target, DamageModel, DamageBreakdown,
                     Weapon, compare_weapons, unwrap, leveled_value)
from .gamedata import GameData
from . import effects

__all__ = ['StatType', 'ModifierType', 'DamageType', 'STAT_NAMES', 'stat_name',
           'CORE', 'ALL_ELEMENTS', 'CONDITIONAL_DAMAGE',
           'Modifier', 'StatSheet', 'Target', 'DamageModel', 'DamageBreakdown',
           'Weapon', 'compare_weapons', 'unwrap', 'leveled_value', 'GameData',
           'effects']
