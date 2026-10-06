# -*- coding: utf-8 -*-
"""构建档案模型：GUI 的唯一事实源（可存 JSON）。

把 cli.demo() 里散落的手写局部变量收敛成一个可序列化结构：面板编辑、构建存取、
计算入口全部围绕它转，避免各 widget 各自为政。装配顺序与 cli.demo 保持一致，
这样 GUI 复算才能与内核直算对拍。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List

from deskrawl_calc import DamageType, Modifier, StatSheet, StatType, Target, Weapon

# 四类装配/候选来源；顺序即界面 Tab 顺序，两处 widget 共用同一份定义避免漂移
KIND_ORDER = [('gem', '宝石'), ('rune', '符文'), ('talent', '天赋'), ('runeset', '套装')]
KIND_LABELS = dict(KIND_ORDER)

# 构建存档目录（仓库内 data/builds/，与 so_dump 同级）
_HERE = os.path.dirname(os.path.abspath(__file__))
BUILDS_DIR = os.path.normpath(os.path.join(_HERE, '..', '..', '..', 'data', 'builds'))


@dataclass
class WeaponDraft:
    """一把武器的可编辑草稿。affixes 用 [stat, type, value] 三元组存，便于 JSON 往返。"""

    name: str = ''
    base_damage: float = 0.0
    base_speed: float = 1.0
    skill_multiplier: float = 1.0
    affixes: List[list] = field(default_factory=list)

    def to_weapon(self) -> Weapon:
        return Weapon(self.name, self.base_damage, self.base_speed,
                      [Modifier(int(s), int(t), float(v)) for s, t, v in self.affixes],
                      skill_multiplier=self.skill_multiplier)

    def to_dict(self) -> dict:
        return {'name': self.name, 'base_damage': self.base_damage, 'base_speed': self.base_speed,
                'skill_multiplier': self.skill_multiplier,
                'affixes': [[int(s), int(t), float(v)] for s, t, v in self.affixes]}

    @classmethod
    def from_dict(cls, d: dict) -> 'WeaponDraft':
        return cls(name=d.get('name', ''), base_damage=float(d.get('base_damage', 0.0)),
                   base_speed=float(d.get('base_speed', 1.0)),
                   skill_multiplier=float(d.get('skill_multiplier', 1.0)),
                   affixes=[[int(s), int(t), float(v)] for s, t, v in (d.get('affixes') or [])])


@dataclass
class AssemblyItem:
    """一条已装配条目。level 语义随 kind 变化：符文等级 / 天赋点数 / 套装件数。"""

    kind: str
    name: str
    level: int = 1
    category: int = 2          # 仅宝石用：0=护甲 1=饰品 2=武器

    def modifiers(self, gd) -> List[Modifier]:
        if self.kind == 'gem':
            return gd.gem_modifiers(self.name, self.category)
        if self.kind == 'rune':
            return gd.rune_modifiers(self.name, self.level)
        if self.kind == 'talent':
            return gd.talent_modifiers(self.name, self.level)
        if self.kind == 'runeset':
            return gd.runeset_modifiers(self.name, self.level)
        return []

    def to_dict(self) -> dict:
        return {'kind': self.kind, 'name': self.name, 'level': self.level, 'category': self.category}

    @classmethod
    def from_dict(cls, d: dict) -> 'AssemblyItem':
        return cls(kind=d.get('kind', ''), name=d.get('name', ''),
                   level=int(d.get('level', 1)), category=int(d.get('category', 2)))


@dataclass
class TargetDraft:
    """受击方草稿；字段与内核 Target 一一对应，便于直接构造。"""

    level: int = 70
    hp_fraction: float = 1.0
    armor: float = 0.0
    magic_resist: float = 0.0
    damage_reduction: float = 0.0
    elite: bool = False
    vulnerable: bool = False
    slowed: bool = False
    immobilized: bool = False
    bleeding: bool = False
    poisoned: bool = False
    burned: bool = False
    distant: bool = False

    def to_target(self) -> Target:
        return Target(level=self.level, hp_fraction=self.hp_fraction, armor=self.armor,
                      magic_resist=self.magic_resist, damage_reduction=self.damage_reduction,
                      elite=self.elite, vulnerable=self.vulnerable, slowed=self.slowed,
                      immobilized=self.immobilized, bleeding=self.bleeding,
                      poisoned=self.poisoned, burned=self.burned, distant=self.distant)

    def to_dict(self) -> dict:
        return dict(self.__dict__)


@dataclass
class CharacterProfile:
    """一个完整构建：基础面板 + 巅峰 + 装配条目 + 双武器 + 目标。"""

    version: int = 1
    name: str = '示例构建'
    level: int = 70
    damage_type: int = int(DamageType.Physical)
    base: Dict[int, float] = field(default_factory=dict)
    paragon: Dict[int, int] = field(default_factory=dict)
    assembled: List[AssemblyItem] = field(default_factory=list)
    weapon_current: WeaponDraft = field(default_factory=WeaponDraft)
    weapon_candidate: WeaponDraft = field(default_factory=WeaponDraft)
    target: TargetDraft = field(default_factory=TargetDraft)
    skill_name: str = ''
    skill_level: int = 1

    # --- 计算装配 ---
    def to_sheet(self, gd) -> StatSheet:
        """按 base → 宝石/符文/天赋/套装 → 巅峰 的顺序装配（与 cli.demo 一致）。"""
        sheet = StatSheet({int(k): float(v) for k, v in self.base.items()})
        for item in self.assembled:
            sheet.add_mods(item.modifiers(gd))
        sheet.add_mods(gd.paragon_modifiers({int(k): int(v) for k, v in self.paragon.items()}))
        return sheet

    def to_target(self) -> Target:
        return self.target.to_target()

    # --- 序列化 ---
    def to_dict(self) -> dict:
        return {
            'version': self.version, 'name': self.name, 'level': self.level,
            'damage_type': self.damage_type,
            'base': {str(int(k)): float(v) for k, v in self.base.items()},
            'paragon': {str(int(k)): int(v) for k, v in self.paragon.items()},
            'assembled': [it.to_dict() for it in self.assembled],
            'weapon_current': self.weapon_current.to_dict(),
            'weapon_candidate': self.weapon_candidate.to_dict(),
            'target': self.target.to_dict(),
            'skill_name': self.skill_name, 'skill_level': self.skill_level,
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'CharacterProfile':
        tgt = {k: v for k, v in (d.get('target') or {}).items()
               if k in TargetDraft.__dataclass_fields__}
        return cls(
            version=int(d.get('version', 1)), name=d.get('name', ''), level=int(d.get('level', 70)),
            damage_type=int(d.get('damage_type', int(DamageType.Physical))),
            base={int(k): float(v) for k, v in (d.get('base') or {}).items()},
            paragon={int(k): int(v) for k, v in (d.get('paragon') or {}).items()},
            assembled=[AssemblyItem.from_dict(x) for x in (d.get('assembled') or [])],
            weapon_current=WeaponDraft.from_dict(d.get('weapon_current') or {}),
            weapon_candidate=WeaponDraft.from_dict(d.get('weapon_candidate') or {}),
            target=TargetDraft(**tgt),
            skill_name=d.get('skill_name', ''), skill_level=int(d.get('skill_level', 1)),
        )

    # --- 出厂示例（照抄 cli.demo 场景，用作锚点对拍与首启动演示）---
    @classmethod
    def demo(cls) -> 'CharacterProfile':
        return cls(
            name='示例构建·猎人', level=70, damage_type=int(DamageType.Physical),
            base={int(StatType.WeaponDamage): 0.0},
            paragon={int(StatType.CritChance): 50},
            assembled=[AssemblyItem('gem', 'GemAmethyst3', 1, 2),
                       AssemblyItem('rune', 'HunterSetRune1_4', 3),
                       AssemblyItem('talent', 'HunterTalent19', 5)],
            weapon_current=WeaponDraft('旧武器·双手剑', 100.0, 1.0, 1.0,
                                       [[int(StatType.DamagePhysical), 0, 0.50]]),
            weapon_candidate=WeaponDraft('新武器·战斧', 110.0, 0.95, 1.0,
                                         [[int(StatType.DamagePhysical), 0, 0.30],
                                          [int(StatType.CritDamage), 0, 0.20],
                                          [int(StatType.DamageVsElite), 0, 0.25]]),
            target=TargetDraft(level=70, hp_fraction=1.0, elite=True, vulnerable=True),
        )

    def replace_with(self, other: 'CharacterProfile'):
        """就地替换内容而保持对象引用不变——加载构建时各 widget 无需重新绑定。"""
        self.__dict__.update(other.__dict__)


def save_build(profile: CharacterProfile, path: str) -> str:
    """把构建写盘（自动建目录），返回实际写入路径。"""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)
    return path


def load_build(path: str) -> CharacterProfile:
    with open(path, encoding='utf-8') as f:
        return CharacterProfile.from_dict(json.load(f))
