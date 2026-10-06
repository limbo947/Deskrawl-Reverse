import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, TOOLS)
from deskrawl_calc import GameData, StatType, stat_name

gd = GameData()

print('=== 1) 技能伤害倍率（DamageEffect.AttackScaling）===')
for ab in ('FireElementalMeteor', 'EnemyBasicAttackLongerRange'):
    effs = gd.ability_damage_effects(ab)
    for e in effs:
        print(f'  {ab:<28} {e["type"]:<22} Base={e["AttackScalingBase"]:.4f} PerLv={e["AttackScalingPerLevel"]:.5f} '
              f'CanCrit={e["CanCrit"]} DmgType={e["DamageType"]}')
    print(f'  -> 1级倍率 = {gd.ability_attack_scaling(ab,1):.4f}   10级倍率 = {gd.ability_attack_scaling(ab,10):.4f}')

print('\n=== 2) 传奇特效 ===')
for pid, label in ((4796, 'DivineHelm2'), (4810, 'LegendaryChestArmor6(转化)'), (4795, 'DivineHelm1_AllStats')):
    e = gd.equipment_effect(pid)
    mods = gd.equipment_effect_modifiers(pid)
    base = {k: v for k, v in (e or {}).items() if k not in ('_managedRefs',)}
    print(f'  [{pid}] {e and e["_class"]}: ' + ', '.join(m.describe() for m in mods) or ' (无词条)')
    if e and str(e.get('_class', '')).endswith('StatConversion'):
        print(f'        转化: {stat_name(e["SourceStat"])} → {stat_name(e["TargetStat"])} × {e["Fraction"]}')

print('\n=== 3) 词条 Roll 区间（公式还原）===')
cases = [(4, '暴击率', 70, 3), (5, '暴击伤害', 70, 3), (65, '全伤害加成%', 70, 3),
         (23, '物理伤害%', 70, 2), (20, '武器伤害', 70, 0), (7, '最大生命', 70, 3)]
for stat, nm, lvl, rar in cases:
    lo, hi = gd.affix_range(stat, lvl, rar)
    print(f'  Lv{lvl} {["Common","Uncommon","Rare","Legendary"][rar]:<9} {nm:<10} 区间 [{lo:g}, {hi:g}]')
