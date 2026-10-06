# -*- coding: utf-8 -*-
"""数据层：加载 so_dump 下的 ScriptableObject 实测数据，产出可直接入池的 Modifier。

可用性（基于对 dump 的实测）：
  ✅ 完整可解析：GemData / RuneData / TalentData / RuneSetData / ItemizationConfig / GameConfig
  ✅ 已解码并接入：AbilityData 技能效果(`_managedRefs`)、EquipmentEffect_* 传奇特效、
     TalentEffect_*/LifeSkillEffect_* 特效、词条 Roll 公式(`AffixRollTable`)
  ⬜ 仍需外部输入：角色面板基础值（联机数据不在本地）；装备具体 roll 值可用 `affix_range()` 估算
"""
from __future__ import annotations
import json, os
from typing import Dict, List, Optional

from .engine import Modifier, leveled_value, unwrap
from .stattype import ModifierType, StatType

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DIR = next((p for p in (
    os.path.normpath(os.path.join(_HERE, '..', '..', 'data', 'so_dump')),   # 本仓库结构
    r'C:\Users\<user>\tools\so_dump',                                          # 原始工作目录
) if os.path.isdir(p)), r'C:\Users\<user>\tools\so_dump')


def _as_mod(stat, mtype, value) -> Optional[Modifier]:
    v = unwrap(value)
    if stat is None or v is None:
        return None
    t = 0 if mtype is None else int(mtype)
    return Modifier(int(stat), t, v)


class GameData:
    def __init__(self, dump_dir: str = DEFAULT_DIR):
        self.dir = dump_dir
        self._cache: Dict[str, list] = {}

    # --- 原始加载 ---
    def _load(self, fname: str) -> list:
        if fname not in self._cache:
            p = os.path.join(self.dir, fname)
            self._cache[fname] = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else []
        return self._cache[fname]

    @staticmethod
    def _index(rows: list) -> Dict[str, dict]:
        return {r['_name']: r for r in rows if r.get('_name')}

    # --- 物品 / 宝石 / 符文 ---
    def items(self) -> Dict[str, dict]:
        return self._index(self._load('ItemData.json'))

    def gems(self) -> Dict[str, dict]:
        return self._index(self._load('GemData.json'))

    def runes(self) -> Dict[str, dict]:
        return self._index(self._load('RuneData.json'))

    def gem_modifiers(self, gem_name: str, equip_category: int = 2) -> List[Modifier]:
        """equip_category: 0=Armor, 1=Accessory, 2=Weapon（镶嵌部位）。"""
        g = self.gems().get(gem_name)
        if not g:
            return []
        key = {0: 'ArmorBonuses', 1: 'AccessoryBonuses', 2: 'WeaponBonuses'}.get(int(equip_category), 'WeaponBonuses')
        out = []
        for b in g.get(key) or []:
            m = _as_mod(b.get('Stat'), b.get('Modifier'), b.get('Value'))
            if m:
                out.append(m)
        return out

    def rune_modifiers(self, rune_name: str, rune_level: int = 1) -> List[Modifier]:
        r = self.runes().get(rune_name)
        if not r:
            return []
        out = []
        for a in r.get('Attributes') or []:
            lv = a.get('Value') or {}
            v = leveled_value(lv.get('Base'), lv.get('PerLevel'), rune_level)
            out.append(Modifier(int(a['Stat']), int(a.get('Modifier', 0)), v))
        return out

    # --- 天赋 ---
    def talents(self) -> Dict[str, dict]:
        return self._index(self._load('TalentData.json'))

    def talent_modifiers(self, talent_name: str, points: int = 1) -> List[Modifier]:
        t = self.talents().get(talent_name)
        if not t:
            return []
        out = []
        for s in t.get('StatModifiers') or []:
            lv = s.get('Value') or {}
            v = leveled_value(lv.get('Base'), lv.get('PerLevel'), points)
            out.append(Modifier(int(s['Stat']), int(s.get('Type', 0)), v))
        return out

    # --- 符文套装 ---
    def runesets(self) -> Dict[str, dict]:
        return self._index(self._load('RuneSetData.json'))

    def runeset_modifiers(self, set_name: str, equipped_count: int) -> List[Modifier]:
        s = self.runesets().get(set_name)
        if not s:
            return []
        out = []
        for b in s.get('Bonuses') or []:
            if int(b.get('RequiredCount', 0)) <= equipped_count:
                for mm in b.get('Modifiers') or []:
                    m = _as_mod(mm.get('Stat'), mm.get('Type'), mm.get('Value'))
                    if m:
                        out.append(m)
        return out

    # --- 物品化配置 ---
    def itemization(self) -> dict:
        rows = self._load('ItemizationConfig.json')
        return rows[0] if rows else {}

    def slot_pools(self, slot: int):
        for p in self.itemization().get('SlotPools', []):
            if int(p.get('Slot')) == int(slot):
                return p.get('Primary', []), p.get('Secondary', [])
        return [], []

    def slot_sockets(self, slot: int) -> int:
        for g in self.itemization().get('GemSocketsBySlot', []):
            if int(g.get('Slot')) == int(slot):
                return int(g.get('MaxSockets', 0))
        return 0

    def min_level_for_sockets(self) -> int:
        return int(self.itemization().get('MinLevelForSockets', 0))

    # --- 全局配置 ---
    def game_config(self) -> dict:
        rows = self._load('GameConfig.json')
        for r in rows:
            if r.get('_name') == 'GameConfig':
                return r
        return rows[0] if rows else {}

    def paragon_stats(self) -> List[dict]:
        return self.game_config().get('ParagonStats', [])

    def paragon_modifiers(self, allocation: Dict[int, int]) -> List[Modifier]:
        """allocation: {StatType: points}。每点 ValuePerPoint（Flat）。"""
        out = []
        for p in self.paragon_stats():
            st = int(p['Stat'])
            pts = int(allocation.get(st, 0))
            if pts:
                out.append(Modifier(st, int(ModifierType.Flat), pts * float(p['ValuePerPoint'])))
        return out

    def difficulty_tiers(self) -> List[dict]:
        return self.game_config().get('DifficultyTiers', [])

    def max_player_level(self) -> int:
        return int(self.game_config().get('MaxPlayerLevel', 0))

    # ------------------------------------------------------------------ #
    # 技能效果（AbilityData.Effects = [SerializeReference]，载荷已解码）
    # ------------------------------------------------------------------ #
    def ability_effects(self, ability_name: str) -> List[dict]:
        rec = self._index(self._load('AbilityData.json')).get(ability_name)
        refs = (rec or {}).get('_managedRefs') or {}
        return refs.get('__items__', [])

    def ability_damage_effects(self, ability_name: str) -> List[dict]:
        """技能伤害倍率：AttackScaling.Base + (level-1) × AttackScaling.PerLevel。"""
        out = []
        for e in self.ability_effects(ability_name):
            if e.get('__type__') in ('DamageEffect', 'StatScaledDamageEffect'):
                lv = e.get('AttackScaling') or {}
                out.append({
                    'type': e['__type__'],
                    'BaseDamage': e.get('BaseDamage', 0),
                    'AttackScalingBase': unwrap(lv.get('Base')) or 0.0,
                    'AttackScalingPerLevel': unwrap(lv.get('PerLevel')) or 0.0,
                    'CanCrit': e.get('CanCrit'),
                    'DamageType': int(e.get('DamageType', 0)),
                })
        return out

    def ability_attack_scaling(self, ability_name: str, level: int = 1) -> float:
        effs = self.ability_damage_effects(ability_name)
        return sum(leveled_value(e['AttackScalingBase'], e['AttackScalingPerLevel'], level) for e in effs)

    # ------------------------------------------------------------------ #
    # 传奇/天赋/生活技能 特效（SO 资产，已解码）
    # ------------------------------------------------------------------ #
    def equipment_effects(self) -> List[dict]:
        return self._load('EquipmentEffects.json')

    def equipment_effect(self, pathid: int) -> Optional[dict]:
        for e in self.equipment_effects():
            if int(e.get('_pathid', -1)) == int(pathid):
                return e
        return None

    def equipment_effect_modifiers(self, pathid: int) -> List[Modifier]:
        e = self.equipment_effect(pathid)
        if not e:
            return []
        out = []
        for m in e.get('StatModifiers') or []:
            v = unwrap(m.get('Value'))
            if v is not None:
                out.append(Modifier(int(m['Stat']), int(m.get('Type', 0)), v))
        if str(e.get('_class', '')).endswith('AllStats') and e.get('Bonus'):
            for s in (StatType.Strength, StatType.Dexterity, StatType.Intelligence):
                out.append(Modifier(int(s), 0, float(e['Bonus'])))
        return out

    # ------------------------------------------------------------------ #
    # 词条 Roll（gg.dna / gg.dnt 还原）
    # ------------------------------------------------------------------ #
    def affix_table(self) -> dict:
        if '_affix' not in self._cache:
            p = os.path.join(self.dir, 'AffixRollTable.json')
            self._cache['_affix'] = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}
        return self._cache['_affix']

    def affix_value(self, stat: int, item_level: int, rarity=0, use_max: bool = False,
                    rng=None) -> float:
        """装备词条数值 = (1 + 稀有度系数) × 等级 × 每级系数[stat] × Random(0.85,1.15)。

        稀有度：Common0/Uncommon1/Rare2/Legendary3 的系数为 0.2/0.4/0.5/0.6，其余为 0。
        """
        import random
        t = self.affix_table()
        if not t:
            return 0.0
        per = next((e['PerLevel'] for e in t['entries'] if int(e['Stat']) == int(stat)), None)
        if per is None:
            return 0.0
        rar = int(rarity) if isinstance(rarity, int) else {'Common': 0, 'Uncommon': 1, 'Rare': 2,
                                                           'Legendary': 3, 'Divine': 4, 'RuneSet': 5}[rarity]
        rar_mul = t['rarityMul'].get(['Common', 'Uncommon', 'Rare', 'Legendary', 'Divine', 'RuneSet'][rar],
                                     0.0)
        base = item_level * per + (5.0 if int(stat) == int(StatType.WeaponDamage) else 0.0)
        factor = t['rollFactor']['max'] if use_max else (rng or random).uniform(*t['rollFactor']['random'])
        v = (1.0 + rar_mul) * base * factor
        v = round(v * 1000.0) / 1000.0
        return max(t.get('min', 0.001), v)

    def affix_range(self, stat: int, item_level: int, rarity=0) -> tuple:
        """该词条在给定等级/稀有度下的取值区间 [min, max]。"""
        return (self._affix_at(stat, item_level, rarity, 0.85),
                self._affix_at(stat, item_level, rarity, 1.15))

    def _affix_at(self, stat, item_level, rarity, factor):
        import random
        class _C:
            def __init__(self, v): self.v = v
            def uniform(self, a, b): return self.v
        return self.affix_value(stat, item_level, rarity, rng=_C(factor))
