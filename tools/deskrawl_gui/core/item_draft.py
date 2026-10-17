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
# 2026-10-12 实机逐位重定（+1/+2/+3/+4 武器 nsq[20]/[21] 对拍，见审计报告 F7）：
#   · 每个升级等级给 2 条词条各 +5%（从 idx0 顺序推进），到末尾绕回开头——即前 2L 个槽位
#     各吃一次 +5%；当 2L > 词条数 n 时溢出部分绕回，早期词条会吃到第二次（+10%）。
#   · 实测 7 词条武器：L=1/2/3 时 [21](idx0)/[20](idx1) 均 ×1.05、idx6 恒 ×1.0；
#     L=4（2L=8 溢出 1）→ idx0 [21] ×1.10、其余 ×1.05（累计命中按加算 v×(1+0.05×命中数)）。
#   · 旧模型给 [20]/[21] 单列 ×(1+0.0125L)/×(1+0.025L) 是错的（L=1 预测 ×1.0125/×1.025，
#     实测均 ×1.05）；旧「+4 全条 ×1.05 + [21] 单列 ×1.10」也源于漏了绕回。
#   影响面：仅「+N 背包武器/装备候选」的预测值（已装备武器由 nsq 单源覆写，见 profile 步骤 2）。
#   边界：L≥5 时「每级 2 条轮转」与「前 2L 槽位取模」两解不可分（无样本），按后者实现。
_UPGRADE_AFFIX_STEP = 0.05


def apply_upgrade(modifiers, upgrade_level):
    """按实测模型折算强化后的词条值（[[stat,type,value],...] → (affixes, weapon_speed)）。

    每级给 2 条词条各 +5%（从 idx0 顺序推进、末尾绕回）；值按累计命中次数加算
    （v×(1+0.05×命中数)），故 2L 溢出时早期词条可得 ×1.10。武器速度(21) 的折算值同时
    作为武器基础攻速的来源（与面板 nsq[21] 同语义）。
    """
    lv = int(upgrade_level or 0)
    n = len(modifiers)
    hits = [0] * n
    if lv and n:
        for k in range(2 * lv):
            hits[k % n] += 1
    out, speed = [], 1.0
    for i, row in enumerate(modifiers):
        s, t, v = int(row[0]), int(row[1]), float(row[2])
        if hits[i]:
            v *= 1.0 + _UPGRADE_AFFIX_STEP * hits[i]
        if s == int(StatType.WeaponSpeed):
            speed = v
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

    def is_empty(self) -> bool:
        """是否仍是出厂空草稿：序列化时据此剔除「只被切槽看过、从没写过」的槽草稿。

        与默认值整体比较（而非只查名称/词条）：任何字段被写过都算有内容，宁可多留也不
        误删用户数据。equipment_editor 用 setdefault 建草稿给控件当写回目标，切槽看一眼
        就会留下一个空壳；不滤掉它们会随会话状态与构建存档落盘成幻影条目。
        """
        return self == ItemDraft()

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
