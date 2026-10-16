# -*- coding: utf-8 -*-
"""数据层：加载 so_dump 下的 ScriptableObject 实测数据，产出可直接入池的 Modifier。

可用性（基于对 dump 的实测）：
  ✅ 完整可解析：GemData / RuneData / TalentData / RuneSetData / ItemizationConfig / GameConfig
  ✅ 已解码并接入：AbilityData 技能效果(`_managedRefs`)、EquipmentEffect_* 传奇特效
     （仅 StatModifier/AllStats 类入属性池，触发/状态/技能修改类未建模）、
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
    # DOT（StatusEffectData 的 DamageOverTimeBehavior + 技能 ApplyStatusEffectEffect 引用）
    # ------------------------------------------------------------------ #
    def dot_specs(self) -> Dict[int, dict]:
        """pathID → DOT 规格：StatusEffectData 里含 DamageOverTimeBehavior 的状态（≤6 条）。

        字段：damage_per_tick（武器伤害比例）/ damage_type / can_crit / reapply_mode /
        tick_rate / duration(Base) / stackable / max_stacks。数据为 dump 实测，逐字段原值。
        """
        cached = getattr(self, '_dot_by_pid', None)
        if cached is not None:
            return cached
        out: Dict[int, dict] = {}
        for rec in self._load('StatusEffectData.json'):
            pid = rec.get('_pathid')
            if pid is None:
                continue
            beh = next((e for e in (rec.get('_managedRefs') or {}).get('__items__', [])
                        if e.get('__type__') == 'DamageOverTimeBehavior'), None)
            if not beh:
                continue
            dur = rec.get('Duration') or {}
            out[int(pid)] = {
                'name': rec.get('_name'),
                'damage_per_tick': float(unwrap(beh.get('DamagePerTick')) or 0.0),
                'damage_type': int(beh.get('DamageType') or 0),
                'can_crit': bool(beh.get('CanCrit')),
                'reapply_mode': int(beh.get('ReapplyMode') or 0),
                'tick_rate': float(unwrap(rec.get('TickRate')) or 0.0),
                'duration': leveled_value(dur.get('Base'), dur.get('PerLevel'), 1),
                'stackable': bool(rec.get('Stackable')),
                'max_stacks': int(rec.get('MaxStacks') or 1),
            }
        self._dot_by_pid = out
        return out

    def ability_dot(self, ability_name: str, level: int = 1) -> List[dict]:
        """该技能每次施放施加的 DOT（ApplyStatusEffectEffect → StatusEffect.pathID → DOT 规格）。

        只收「带 DamageOverTimeBehavior 的状态」；Chance 按技能等级 Base+(lv-1)×PerLevel。
        玩家侧的 DOT 状态为 Bleeding/Burn/HunterPoison（武器/胸甲池可滚出 62 词条的消费入口）。
        """
        specs = self.dot_specs()
        cache = getattr(self, '_dot_by_ability', None)
        if cache is None:
            cache = self._dot_by_ability = {}
        key = (ability_name, int(level))
        if key in cache:
            return cache[key]
        rec = self._index(self._load('AbilityData.json')).get(ability_name) or {}
        out = []
        for e in (rec.get('_managedRefs') or {}).get('__items__', []):
            if e.get('__type__') != 'ApplyStatusEffectEffect':
                continue
            spec = specs.get(int((e.get('StatusEffect') or {}).get('pathID') or 0))
            if not spec:
                continue
            ch = e.get('Chance') or {}
            out.append({**spec, 'chance': leveled_value(ch.get('Base'), ch.get('PerLevel'), level)})
        cache[key] = out
        return out

    # ------------------------------------------------------------------ #
    # 英雄职业 → 伤害技能清单（HeroData.Abilities 用 pathID 引用 AbilityData）
    # ------------------------------------------------------------------ #
    def heroes(self) -> Dict[str, dict]:
        return self._index(self._load('HeroData.json'))

    def hero_for_class(self, hero_class) -> Optional[dict]:
        """按 HeroData.Class 取职业记录（Class 唯一：Barbarian=1/Hunter=4/Sorcerer=2/Monk=8）。"""
        if hero_class is None:
            return None
        for h in self._load('HeroData.json'):
            if int(h.get('Class', -1)) == int(hero_class):
                return h
        return None

    def abilities_for_class(self, hero_class) -> List[str]:
        """该职业的 AbilityData._name 列表（HeroData.Abilities 里的 pathID → _name）。"""
        h = self.hero_for_class(hero_class)
        if not h:
            return []
        by_pid = {int(r['_pathid']): r['_name'] for r in self._load('AbilityData.json')
                  if r.get('_pathid') is not None}
        return [by_pid[int(a['pathID'])] for a in (h.get('Abilities') or [])
                if int(a.get('pathID', 0)) in by_pid]

    def _base_strikes(self, rec: dict) -> int:
        """每次施放的基础命中次数：取 StaggeredStrikesEffect.TargetCount（错峰打击，
        AllowRepeatWhenNoOtherTargets=True 时单目标会重复命中），无该效果则为 1。

        实测 Rending Onslaught = 3（屠夫韵律「额外劈砍」类天赋在此之上 +N 次）。
        """
        for e in (rec.get('_managedRefs') or {}).get('__items__', []):
            if e.get('__type__') == 'StaggeredStrikesEffect':
                n = unwrap(e.get('TargetCount'))
                if n:
                    return max(1, int(n))
        return 1

    def damage_skills(self, hero_class, level: int = 1) -> List[dict]:
        """该职业的全部伤害技能（含 DamageEffect）逐段倍率/伤害类型/冷却/基础命中次数。

        多段技能（多个 DamageEffect）逐段返回，供上层按各自 DamageType 分别入乘区。
        冷却字段多数技能的 Obscured 为默认 0（dump 中 hash=723851361、值≈denormal），
        上层按「≈0 视为无冷却，回退攻速」处理（见 skill_service）。
        """
        out = []
        index = self._index(self._load('AbilityData.json'))
        for name in self.abilities_for_class(hero_class):
            rec = index.get(name)
            if not rec:
                continue
            effs = self.ability_damage_effects(name)
            if not effs:
                continue
            cd = rec.get('Cooldown') or {}
            mc = rec.get('ManaCost') or {}
            out.append({
                'name': name, 'ability_name': str(rec.get('AbilityName') or name),
                'level_req': int(rec.get('LevelRequirement') or 0),
                'mana_cost': leveled_value(mc.get('Base'), mc.get('PerLevel'), level),
                'tags': [int(t) for t in (rec.get('Tags') or [])],
                'strikes': self._base_strikes(rec),
                'effects': [{'damage_type': int(e['DamageType']),
                             'scaling': leveled_value(e['AttackScalingBase'],
                                                      e['AttackScalingPerLevel'], level),
                             'base_damage': unwrap(e.get('BaseDamage')) or 0.0,
                             'can_crit': bool(e.get('CanCrit'))} for e in effs],
                'cooldown': leveled_value(cd.get('Base'), cd.get('PerLevel'), level),
                'channel_duration': unwrap(rec.get('ChannelDuration')) or 0.0,
                'tick_rate': unwrap(rec.get('ChannelTickRate')) or 0.0,
                # 前摇/收招：实测 124 个技能里各只有 1 个非零且是敌人技能（VolcanoDemonLordFlyingLaser），
                # 玩家技能恒 0——带上它们是为了口径完备，不改变任何玩家技能的数值
                'channel_windup': unwrap(rec.get('ChannelWindup')) or 0.0,
                'channel_recovery': unwrap(rec.get('ChannelRecovery')) or 0.0,
            })
        return out

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

    def item_effect_pathids(self, item_name: str) -> List[int]:
        """装备 ItemData._name → EquipmentEffect pathID 列表（ItemData.EquipmentEffects 引用）。"""
        rec = self.items().get(str(item_name or ''))
        out = []
        for e in (rec or {}).get('EquipmentEffects') or []:
            pid = e.get('pathID') if isinstance(e, dict) else None
            if pid:
                out.append(int(pid))
        return out

    def item_effect_modifiers(self, item_name: str) -> List[Modifier]:
        """装备的传奇特效词条（**仅** StatModifier / AllStats 类可解析，触发/状态类返回空）。

        92 条 EquipmentEffects 中 80 条是触发/状态/技能修改类，本就不走属性池——所以
        「返回空」是正常的未建模，不是异常；调用方不要据此判定装备无特效。
        """
        out = []
        for pid in self.item_effect_pathids(item_name):
            out.extend(self.equipment_effect_modifiers(pid))
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
