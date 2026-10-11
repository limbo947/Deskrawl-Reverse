# -*- coding: utf-8 -*-
"""非武器装备槽的可编辑草稿（ItemDraft）与强化（UpgradeLevel）缩放模型。

从 profile.py 拆出：profile 仍是构建档案的唯一事实源，但「一件装备的草稿」与「强化折算
规则」是独立概念，放这里可让 profile 与视图共用而不互相缠绕（也避免单文件膨胀）。
武器槽另有 WeaponDraft（含基础攻速/技能倍率），本模块只服务防具/饰品槽。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from deskrawl_calc import Modifier, StatType

# ---- 强化（UpgradeLevel）缩放模型 ------------------------------------------------
# 2026-10-08 与活体面板（nsq）逐位对拍实证，证据链见 PROGRESS「强化缩放」：
#   · +1 装备（靴/手套/腰带共 15 条词条）：仅 modifiers 数组前 2 条 ×1.05，其余原值；
#   · +4 武器（7 条词条）：全部 ×1.05（前 2L=8 ≥ 7），逐位闭合（nsq[12]=93×1.05 等）；
#   · 武器伤害(20) ×(1+0.0125L)、武器速度(21) ×(1+0.025L)：+4 时 ×1.05/×1.10 逐位闭合，
#     与「前 2L 条」规则对 20 号自洽（21 号若走同规则应为 ×1.05，实测 ×1.10 → 单列）。
# 边界说明：L∈{2,3} 与「前 2L」在 L>4、词条数>8 时未取到实证，模型按现有证据外推
# （记录于 BLOCKED）；当前武器的 20/21 两键始终用 nsq 面板值覆写，不依赖外推。
_UPGRADE_AFFIX_RATE = 1.05
_UPGRADE_DAMAGE_PER_LV = 0.0125
_UPGRADE_SPEED_PER_LV = 0.025


def apply_upgrade(modifiers, upgrade_level):
    """按实测模型折算强化后的词条值（[[stat,type,value],...] → (affixes, weapon_speed)）。

    等级 0 原样返回；武器速度(21) 折算值同时作为武器基础攻速的来源（与面板 nsq[21] 同语义）。
    """
    lv = int(upgrade_level or 0)
    out, speed = [], 1.0
    for i, row in enumerate(modifiers):
        s, t, v = int(row[0]), int(row[1]), float(row[2])
        if s == int(StatType.WeaponSpeed):
            speed = v * (1.0 + _UPGRADE_SPEED_PER_LV * lv) if lv else v
        elif s == int(StatType.WeaponDamage):
            v *= 1.0 + _UPGRADE_DAMAGE_PER_LV * lv
        elif lv and i < 2 * lv:
            v *= _UPGRADE_AFFIX_RATE
        out.append([s, t, v])
    return out, speed


@dataclass
class ItemDraft:
    """一件非武器装备的可编辑草稿（名称 / 词条 / 强化 / 宝石 + 溯源元信息）。

    affixes 用 [stat, type, value] 三元组存，便于 JSON 往返；upgrade_level/gems/item_level 等
    是内存导入的展示元信息（gem 加成已进 assembled 装配链，此处只展示）。
    """

    name: str = ''
    affixes: List[list] = field(default_factory=list)
    upgrade_level: int = 0
    gems: List[str] = field(default_factory=list)
    equip_slot_type: int = 0
    item_level: int = 0
    rarity: int = 0
    source: str = ''
    # 候选侧「与当前装备相同（强化/宝石）」开关：raw_modifiers 保留背包里的强化前原貌
    # （折叠后不可反推），own_* 记下取消勾选时要还原的自身原貌。语义与 WeaponDraft 同款。
    raw_modifiers: List[list] = field(default_factory=list)
    like_current: bool = False
    own_upgrade_level: int = 0
    own_gems: List[str] = field(default_factory=list)

    def to_mods(self) -> List[Modifier]:
        return [Modifier(int(s), int(t), float(v)) for s, t, v in self.affixes]

    def to_dict(self) -> dict:
        return {'name': self.name,
                'affixes': [[int(s), int(t), float(v)] for s, t, v in self.affixes],
                'upgrade_level': int(self.upgrade_level),
                'gems': [str(g) for g in self.gems],
                'equip_slot_type': int(self.equip_slot_type),
                'item_level': int(self.item_level), 'rarity': int(self.rarity),
                'source': self.source,
                'raw_modifiers': [[int(s), int(t), float(v)] for s, t, v in self.raw_modifiers],
                'like_current': bool(self.like_current),
                'own_upgrade_level': int(self.own_upgrade_level),
                'own_gems': [str(g) for g in self.own_gems]}

    @classmethod
    def from_dict(cls, d: dict) -> 'ItemDraft':
        return cls(name=d.get('name', ''),
                   affixes=[[int(s), int(t), float(v)] for s, t, v in (d.get('affixes') or [])],
                   upgrade_level=int(d.get('upgrade_level', 0) or 0),
                   gems=[str(g) for g in (d.get('gems') or [])],
                   equip_slot_type=int(d.get('equip_slot_type', 0) or 0),
                   item_level=int(d.get('item_level', 0) or 0),
                   rarity=int(d.get('rarity', 0) or 0),
                   source=str(d.get('source', '')),
                   raw_modifiers=[[int(s), int(t), float(v)]
                                  for s, t, v in (d.get('raw_modifiers') or [])],
                   like_current=bool(d.get('like_current', False)),
                   own_upgrade_level=int(d.get('own_upgrade_level', 0) or 0),
                   own_gems=[str(g) for g in (d.get('own_gems') or [])])

    @classmethod
    def from_record(cls, rec: dict, *, source: str = '') -> 'ItemDraft':
        """从内存快照的装备/背包条目建草稿（词条按强化模型折算为「强化后」口径）。"""
        affixes, _speed = apply_upgrade(rec.get('modifiers') or [], rec.get('upgrade_level'))
        return cls(name=str(rec.get('name') or ''), affixes=affixes,
                   upgrade_level=int(rec.get('upgrade_level') or 0),
                   gems=[str(g) for g in (rec.get('socketed_gems') or [])],
                   equip_slot_type=int(rec.get('equip_slot_type') or 0),
                   item_level=int(rec.get('item_level') or 0),
                   rarity=int(rec.get('rarity') or 0), source=source)
