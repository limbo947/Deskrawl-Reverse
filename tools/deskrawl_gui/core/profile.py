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
from typing import Dict, List, Optional

from deskrawl_calc import DamageType, Modifier, StatSheet, StatType, Target, Weapon

from .item_draft import ItemDraft, apply_upgrade
from .localization import equipment_display_name

# 四类装配/候选来源；顺序即界面 Tab 顺序，两处 widget 共用同一份定义避免漂移
KIND_ORDER = [('gem', '宝石'), ('rune', '符文'), ('talent', '天赋'), ('runeset', '套装')]
KIND_LABELS = dict(KIND_ORDER)

# 构建存档目录（仓库内 data/builds/，与 so_dump 同级）
_HERE = os.path.dirname(os.path.abspath(__file__))
BUILDS_DIR = os.path.normpath(os.path.join(_HERE, '..', '..', '..', 'data', 'builds'))

# EquipSlotType → 宝石加成组（GemData 的 Weapon/Accessory/Armor Bonuses）。
# 实测锚定：武器槽 2、戒指(7)/项链(8) 1、其余（含腰带）0 —— 三键宝石加成逐位对上内存面板。
_GEM_CATEGORY_BY_EQUIP_TYPE = {1: 2, 7: 1, 8: 1}

# 装备对比支持的 11 个内存槽（键 = 快照 slot id；不含披风/Back=11）。
# 顺序按槽 id；注意 slot 9=护肩、slot 10=手套（与直觉相反，与 memory_offsets.json 实测表一致）。
COMPARE_SLOTS = [(0, '武器'), (1, '头盔'), (2, '胸甲'), (3, '裤子'), (4, '靴子'), (5, '腰带'),
                 (6, '戒指1'), (7, '戒指2'), (8, '项链'), (9, '护肩'), (10, '手套')]
SLOT_LABELS = dict(COMPARE_SLOTS)
# 内存槽 id → EquipSlotType（同 memory_offsets.json.equip_slot_id_to_type；戒指1/2 同为 7）。
SLOT_EQUIP_TYPE = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 7, 8: 8, 9: 10, 10: 9}

# 强化缩放模型（apply_upgrade）与单件装备草稿 ItemDraft 已拆到 item_draft.py：它们是独立概念，
# 且 profile 在 from_snapshot 里要用 ItemDraft.from_record，同文件会绕成循环依赖。


def _gem_category(equip_slot_type) -> int:
    """装备槽类型 → 宝石镶嵌部位（0=护甲 1=饰品 2=武器）。"""
    return _GEM_CATEGORY_BY_EQUIP_TYPE.get(int(equip_slot_type or 0), 0)


def _panel_finals(payload: dict) -> dict:
    """游戏面板最终值 {stat: final}（build_panel 复算，与「属性」页逐行一致）。

    基座必须用面板最终值而非 nsq 单字典：nsq 只是平坦层的一部分，其余值散在 nsu/ntc/nte/nsr
    字典、BasePrimaryStat 基础字段与条件表里。实测（2026-10-10 ExampleHeroB，武器 A/B 两轮）：若拿 nsq
    当基座，暴伤少 230%、暴击率少 15%、物理伤害少 75%、对易伤少 80%、全伤害少 75%（且与武器无关），
    旋风斩单跳因此系统性偏低数倍。
    """
    from . import calc_service          # 延迟导入：calc_service 顶层引 profile，避免循环导入
    try:
        rows = calc_service.build_panel(payload)['rows']
    except Exception:
        return {}
    return {int(r[0]): float(r[5]) for r in rows if r[5] is not None}


def _rune_items(player, gd, warns) -> list:
    """符文槽 → [AssemblyItem('rune', 名称, 等级)]。

    符文属性走 gd.rune_modifiers（与 RuneData.Attributes 同源）；「技能等级+N」由
    skill_service.ability_level_bonuses 直接按名称+等级读 RuneData.AbilityLevels，
    因此即使属性解析不到（名称形态异常）也仍计入条目——等级加成不能丢。
    """
    out = []
    for r in player.get('runes') or []:
        name = str(r.get('name') or '')
        if not name:
            continue
        item = AssemblyItem('rune', name, max(1, int(r.get('level') or 1)))
        if gd is not None and not item.modifiers(gd):
            warns.append(f'符文 {name} 未在 RuneData 命中属性（等级加成仍生效）')
        out.append(item)
    return out


def _align_primary_stat(prof, payload, gd):
    """把职业主属性键位的 base 对准游戏面板口径（bjr 伤害公式读 Final(主属性)＝bjd 复合值）。

    nsq 只是聚合字典层；面板在其上还叠加 nsu/ntc/nte/nsr 平坦字典与 BasePrimaryStat 基础字段
    （本构建实测 377+50+14+10=451）。差值除以该键位 (%) 因子后并入 base，使
    sheet.final(主属性) ≡ 面板值——DPS 的主属性加成因此与游戏 tooltip「当前提升 451% 伤害」
    一致，且编辑仍按 +1%/点 生效（游戏公式本征斜率，编辑路径不受对齐影响）。
    """
    ps = getattr(prof, 'primary_stat', None)
    if ps is None or gd is None:
        return
    from . import calc_service     # 延迟导入：calc_service 顶层引 profile，避免循环导入
    row = {int(r[0]): r for r in calc_service.build_panel(payload)['rows']}.get(int(ps))
    if not row:
        return
    sheet = prof.to_sheet(gd)
    b = sheet.breakdown(int(ps))
    factor = (1.0 + b['PercentAdd']) * b['PercentMultΠ']
    # 当前武器的平坦贡献由计算路径另行叠加（残差反解时已从 base 扣除）→ 这里同样扣除
    w_flat = sum(float(m.value) for m in prof.weapon_current.to_weapon().modifiers
                 if int(m.stat) == int(ps) and int(m.type) == 0)
    delta = (float(row[5]) - sheet.final(int(ps))) / factor - w_flat
    if delta:
        prof.base[int(ps)] = float(prof.base.get(int(ps), 0.0)) + delta


def _talent_ability_mods(ptrs, raw, hero_class, gd) -> Dict[str, Dict[int, float]]:
    """运行时 AbilityData* → 技能名并汇总天赋「按技能修正」为 {技能名: {stat: 值}}。

    指针→名字靠顺序对齐：HeroData.Abilities 的运行时 List 顺序与 so_dump HeroData.Abilities
    一致（2026-10-09 活体实证 14 项逐位对应），故第 i 个指针即第 i 个技能名。
    数据/职业缺失时返回 {}（技能表降级），不影响数值导入。
    """
    if gd is None or hero_class is None or not ptrs:
        return {}
    names = gd.abilities_for_class(hero_class)
    by_ptr = {int(p): names[i] for i, p in enumerate(ptrs) if i < len(names)}
    out: Dict[str, Dict[int, float]] = {}
    for stat, ap, val in raw:
        nm = by_ptr.get(int(ap))
        if not nm:
            continue
        d = out.setdefault(nm, {})
        d[int(stat)] = d.get(int(stat), 0.0) + float(val)
    return out


@dataclass
class WeaponDraft:
    """一把武器的可编辑草稿。affixes 用 [stat, type, value] 三元组存，便于 JSON 往返。

    affixes 是**强化后**口径（导入链按 apply_upgrade 折算）；raw_modifiers 保留背包里的
    强化前原貌，改强化等级（含「与当前武器相同」开关）时据此重算，否则无法从折叠值反推。
    upgrade_level / gems 参与候选侧对比：武器孔位宝石按侧计入（calc_service.compare slot=0）。
    """

    name: str = ''
    base_damage: float = 0.0
    base_speed: float = 1.0
    skill_multiplier: float = 1.0
    affixes: List[list] = field(default_factory=list)
    upgrade_level: int = 0
    gems: List[str] = field(default_factory=list)
    # 候选侧「与当前武器相同（强化/宝石）」开关，连同取消时要还原的自身原貌
    raw_modifiers: List[list] = field(default_factory=list)
    like_current: bool = False
    own_upgrade_level: int = 0
    own_gems: List[str] = field(default_factory=list)

    def to_weapon(self) -> Weapon:
        return Weapon(self.name, self.base_damage, self.base_speed,
                      [Modifier(int(s), int(t), float(v)) for s, t, v in self.affixes],
                      skill_multiplier=self.skill_multiplier)

    def to_dict(self) -> dict:
        return {'name': self.name, 'base_damage': self.base_damage, 'base_speed': self.base_speed,
                'skill_multiplier': self.skill_multiplier,
                'affixes': [[int(s), int(t), float(v)] for s, t, v in self.affixes],
                'upgrade_level': int(self.upgrade_level),
                'gems': [str(g) for g in self.gems],
                'raw_modifiers': [[int(s), int(t), float(v)] for s, t, v in self.raw_modifiers],
                'like_current': bool(self.like_current),
                'own_upgrade_level': int(self.own_upgrade_level),
                'own_gems': [str(g) for g in self.own_gems]}

    @classmethod
    def from_dict(cls, d: dict) -> 'WeaponDraft':
        return cls(name=d.get('name', ''), base_damage=float(d.get('base_damage', 0.0)),
                   base_speed=float(d.get('base_speed', 1.0)),
                   skill_multiplier=float(d.get('skill_multiplier', 1.0)),
                   affixes=[[int(s), int(t), float(v)] for s, t, v in (d.get('affixes') or [])],
                   upgrade_level=int(d.get('upgrade_level', 0) or 0),
                   gems=[str(g) for g in (d.get('gems') or [])],
                   raw_modifiers=[[int(s), int(t), float(v)]
                                  for s, t, v in (d.get('raw_modifiers') or [])],
                   like_current=bool(d.get('like_current', False)),
                   own_upgrade_level=int(d.get('own_upgrade_level', 0) or 0),
                   own_gems=[str(g) for g in (d.get('own_gems') or [])])


@dataclass
class AssemblyItem:
    """一条已装配条目。level 语义随 kind 变化：符文等级 / 天赋点数 / 套装件数。"""

    kind: str
    name: str
    level: int = 1
    category: int = 2          # 仅宝石用：0=护甲 1=饰品 2=武器
    slot: int = -1             # 宝石归属的内存槽 id（0..11；-1=未标注/手工）

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
        return {'kind': self.kind, 'name': self.name, 'level': self.level,
                'category': self.category, 'slot': self.slot}

    @classmethod
    def from_dict(cls, d: dict) -> 'AssemblyItem':
        return cls(kind=d.get('kind', ''), name=d.get('name', ''),
                   level=int(d.get('level', 1)), category=int(d.get('category', 2)),
                   slot=int(d.get('slot', -1)))


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
    # 眩晕：仅作传奇特效条件门控（TargetStateCondition.Stunned=1，不进 bko 条件池）。
    stunned: bool = False

    def to_target(self) -> Target:
        return Target(level=self.level, hp_fraction=self.hp_fraction, armor=self.armor,
                      magic_resist=self.magic_resist, damage_reduction=self.damage_reduction,
                      elite=self.elite, vulnerable=self.vulnerable, slowed=self.slowed,
                      immobilized=self.immobilized, bleeding=self.bleeding,
                      poisoned=self.poisoned, burned=self.burned, distant=self.distant,
                      stunned=self.stunned)

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
    # 内存导入溯源：''=手工/构建文件；'beta'=逐件导入；'alpha'=聚合导入。
    # 由 widget 侧据此展示 α 降级提示（近似标注/对比降级），并存档往返保留语义。
    import_mode: str = ''
    import_time: str = ''
    # 职业主属性（0=力量/1=敏捷/2=智力；None=不启用）：攻击伤害 ×(1+Final/100)（Player.CalcDamage@0x518230）。
    # 内存导入自动取 HeroData.PrimaryStat（Player.PrimaryStatValue@0x500CA0 链）；手工构建由左栏「职业主属性」选择。
    primary_stat: Optional[int] = None
    # 游戏面板口径复算结果（导入时冻结，见 calc_service.build_panel）：
    # {'time','mode','hp_frac','rows','warnings'}；None=手工构建，属性明细退回计算口径展示。
    panel: dict = None
    # 背包/仓库内未装备的**全部装备**（导入时冻结，供任意槽的候选快捷载入；[] = 手工/α 降级）。
    # 每项：{'source' 背包|仓库, 'name', 'equip_slot_type', 'item_level', 'rarity',
    #        'upgrade_level', 'gems', 'affixes'（已按强化模型折算）, 'speed',
    #        'modifiers'（强化前原貌，改强化等级时重算用）}。
    bag_items: List[dict] = field(default_factory=list)
    # 装备对比页当前选中的内存槽 id：0=武器，1..10=其余十件（不含披风/Back=11）。
    compare_slot: int = 0
    # 候选侧「与当前装备相同」开关的选择记忆（跨槽保持；随会话状态/构建持久化）。
    like_current_pref: bool = False
    # 非武器槽的当前件/候选件草稿（键 = 内存槽 id 1..10）。武器槽仍用 weapon_current/candidate。
    slot_current: Dict[int, ItemDraft] = field(default_factory=dict)
    slot_candidate: Dict[int, ItemDraft] = field(default_factory=dict)
    # HeroData.Class（1=Barbarian/2=Sorcerer/4=Hunter/8=Monk）；None=未知（手工构建/未导入）。
    # 用于结果区列出「当前职业的伤害技能」。
    hero_class: Optional[int] = None
    # 天赋带来的「按技能修正」：{技能名: {ModifiedStat: 值}}。目前只收会改变每秒命中次数的
    # ChannelSpeed(8) / StrikeCount(9)（读到自 Player+0x248 天赋表 → TalentEffect_AbilityModifier）。
    ability_mods: Dict[str, Dict[int, float]] = field(default_factory=dict)

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
            'import_mode': self.import_mode, 'import_time': self.import_time,
            'primary_stat': self.primary_stat,
            'panel': self.panel, 'bag_items': self.bag_items,
            'compare_slot': int(self.compare_slot),
            'like_current_pref': bool(self.like_current_pref),
            'slot_current': {str(int(k)): v.to_dict() for k, v in self.slot_current.items()},
            'slot_candidate': {str(int(k)): v.to_dict() for k, v in self.slot_candidate.items()},
            'hero_class': self.hero_class,
            'ability_mods': {k: {str(int(s)): float(v) for s, v in vv.items()}
                             for k, vv in self.ability_mods.items()},
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
            import_mode=d.get('import_mode', ''), import_time=d.get('import_time', ''),
            primary_stat=(None if d.get('primary_stat') is None else int(d['primary_stat'])),
            panel=d.get('panel'),
            bag_items=[dict(x) for x in (d.get('bag_items') or [])],
            compare_slot=int(d.get('compare_slot', 0) or 0),
            like_current_pref=bool(d.get('like_current_pref', False)),
            slot_current={int(k): ItemDraft.from_dict(v)
                          for k, v in (d.get('slot_current') or {}).items()},
            slot_candidate={int(k): ItemDraft.from_dict(v)
                            for k, v in (d.get('slot_candidate') or {}).items()},
            hero_class=(None if d.get('hero_class') is None else int(d['hero_class'])),
            ability_mods={str(k): {int(s): float(v) for s, v in (vv or {}).items()}
                          for k, vv in (d.get('ability_mods') or {}).items()},
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

    # --- 内存快照导入（memdump --json 同款 payload）---
    @classmethod
    def from_snapshot(cls, payload: dict, gd=None) -> 'CharacterProfile':
        """把内存快照映射为构建档案（α 聚合 / β 逐件），见《内存导入计划》§3.2。

        为什么 base 采用「面板减可分解项」而非直接照抄或纯装备重建：nsq 面板含快照无法
        分解的来源（天赋/巅峰/传奇特效），照抄会让装配链把武器/宝石再计一次；纯装备
        重建又填不满（实测 12 个键位有残差）。折中——能分解的真分解（武器/宝石）并从面板中
        扣除，其余残差留在 base，于是「面板闭环」与「可分解部分可独立对拍」同时成立。
        扣减必须按内核同一求和顺序做，否则链式复算会出现末位偏差（实测同序时逐键闭合）。
        武器词条按强化模型折算（apply_upgrade，面板口径=游戏 tooltip）；强化后的
        nsq[20]/[21] 是武器单源精确值，直接覆写折算值，残差反解自然吸收原值差。
        主属性取 HeroData.PrimaryStat（fak 链），并把该键位 base 对齐到面板口径
        （_align_primary_stat）——DPS 的攻击伤害 ×(1+Final(主属性)/100) 与游戏一致。
        装备名经 Equipments 本地化表翻成简中（equipment_display_name，与游戏内显示一致；
        缺表/未覆盖时回落内部名）。同时冻结非武器槽当前件（slot_current，供任意槽对比）与
        背包/仓库全部装备（bag_items，候选快捷载入的数据源），并记录 HeroData.Class
        （hero_class，用于技能表）。
        """
        meta = payload.get('meta') or {}
        player = payload.get('player') or {}
        equip = payload.get('equipment')
        nsq = {int(k): float(v) for k, v in (player.get('base') or {}).items()}
        # 基座 = 面板最终值（nsq 单字典只是平坦层，会系统性少读；build_panel 失败时回落 nsq）
        panel_final = _panel_finals(payload) or dict(nsq)
        warns = meta.setdefault('warnings', [])   # 映射告警并回写 meta，随导入对话框一并展示
        hero = meta.get('hero') or {}
        ps = player.get('primary_stat')
        cls_raw = player.get('hero_class', hero.get('class'))
        prof = cls(name=(f"{hero.get('name')}·内存导入" if hero.get('name') else '内存导入'),
                   level=int(player.get('level') or 70),
                   import_mode=('beta' if equip else 'alpha'),
                   import_time=str(meta.get('time') or ''),
                   primary_stat=(int(ps) if ps is not None else None),
                   hero_class=(int(cls_raw) if cls_raw is not None else None))
        prof.base = dict(panel_final)             # α 即终态；β 在此基础上扣减可分解项
        # 天赋「按技能修正」（技能频次）：与 α/β 无关，先于早退分支落位（技能表两侧都要用）
        prof.ability_mods = _talent_ability_mods(player.get('hero_abilities') or [],
                                                 player.get('talent_ability_mods') or [],
                                                 prof.hero_class, gd)
        # 巅峰点数分配：面板 base 已含其贡献，这里落 allocation 供展示/编辑，
        # 并把贡献从 base 反向扣除（paragon_modifiers 恒为 Flat，可精确逆运算）——
        # 否则 to_sheet 再叠加一次会重复计伤；用户随后改点数时按新 allocation 全量重算，语义仍正确。
        paragon = player.get('paragon') or {}
        if paragon and gd is not None:
            prof.paragon = {int(k): int(v) for k, v in paragon.items()}
            for m in gd.paragon_modifiers(prof.paragon):
                prof.base[int(m.stat)] = prof.base.get(int(m.stat), 0.0) - float(m.value)
        # 符文槽（RuneManager）：与 α/β 无关——「技能等级+N」只能来自符文（旋风斩 10+8=18），
        # 所以 α 也必须计入。β 的残差反解（步骤 4）会自动扣减其贡献；α 无残差步骤，这里手工扣 Flat。
        rune_items = _rune_items(player, gd, warns)
        prof.assembled.extend(rune_items)
        if not equip and gd is not None:
            for item in rune_items:
                for m in item.modifiers(gd):
                    if int(m.type) == 0:
                        prof.base[int(m.stat)] = prof.base.get(int(m.stat), 0.0) - float(m.value)
        if not equip:
            _align_primary_stat(prof, payload, gd)
            return prof

        # 1) 孔位宝石 → assembled（静态 GemData 与实际加成同源，实测三键逐位一致）。
        #    记录宝石归属槽（AssemblyItem.slot）：非武器槽对比时要按槽把该件宝石从基线中减去。
        for rec in equip:
            for gname in (rec.get('socketed_gems') or []):
                item = AssemblyItem('gem', str(gname), 1, _gem_category(rec.get('equip_slot_type', 0)),
                                    slot=int(rec.get('slot', -1)))
                if gd is None or not item.modifiers(gd):
                    warns.append(f'孔位宝石 {gname} 无法在 GemData 解析，未计入装配')
                    continue
                prof.assembled.append(item)
            if int(rec.get('rune_level') or 0) > 0:
                warns.append(f"{rec.get('name') or rec.get('slot')} 带有符文等级但快照未含符文标识，未计入装配")

        # 2) 武器 → weapon_current：词条按强化模型折算（面板口径与游戏 tooltip 一致）。
        #    强化武器的 nsq[20]/[21] 是「强化后」的单源精确值（仅武器持有这两键），直接
        #    覆写折算结果——不依赖模型外推；原值已由残差反解吸收，闭环不受影响。
        wrec = next((r for r in equip if int(r.get('slot', -1)) == 0), None)
        if wrec is None:
            warns.append('快照未含武器槽：当前武器留空，装备对比基线=面板')
        else:
            affixes, speed = apply_upgrade(wrec.get('modifiers') or [],
                                           wrec.get('upgrade_level'))
            if int(wrec.get('upgrade_level') or 0):
                for a in affixes:
                    if a[0] == int(StatType.WeaponDamage) and int(StatType.WeaponDamage) in nsq:
                        a[2] = nsq[int(StatType.WeaponDamage)]
                    if a[0] == int(StatType.WeaponSpeed) and int(StatType.WeaponSpeed) in nsq:
                        a[2] = nsq[int(StatType.WeaponSpeed)]
                        speed = nsq[int(StatType.WeaponSpeed)]
            # base_damage=0：游戏白字伤害以 WeaponDamage(20) 词条形式存在于面板，填在这里会双计
            prof.weapon_current = WeaponDraft(
                name=equipment_display_name(gd, str(wrec.get('name') or '')),
                base_damage=0.0,
                base_speed=float(speed) or 1.0, affixes=affixes,
                upgrade_level=int(wrec.get('upgrade_level') or 0),
                gems=[str(g) for g in (wrec.get('socketed_gems') or [])])

        # 2b) 非武器槽当前件 → slot_current（键 1..10；不含披风/Back=11）。词条同按强化模型折算，
        #     使「当前件 ≡ 面板」；对比时从基线里减去该件即可得到「未装备本件」的干净基线。
        for rec in equip:
            slot = int(rec.get('slot', -1))
            if 1 <= slot <= 10:
                draft = ItemDraft.from_record(rec, source='装备')
                draft.name = equipment_display_name(gd, draft.name)
                prof.slot_current[slot] = draft

        # 3) 背包/仓库未装备装备 → bag_items（任意槽候选快捷载入的数据源）。
        #    仅收 UID 命中实例表的装备（有逐件词条）；α 降级无实例数据，按「无实例数据」汇总一条告警。
        missing = 0
        for where, label in (('inventory', '背包'), ('storage', '仓库')):
            for it in payload.get(where) or []:
                if not 1 <= int(it.get('equip_slot_type') or 0) <= 11:
                    continue
                if it.get('modifiers') is None:
                    missing += 1
                    continue
                affixes, speed = apply_upgrade(it['modifiers'], it.get('upgrade_level'))
                prof.bag_items.append({
                    'source': label,
                    'name': equipment_display_name(gd, str(it.get('name') or '')),
                    'equip_slot_type': int(it.get('equip_slot_type') or 0),
                    'item_level': int(it.get('item_level') or 0),
                    'rarity': int(it.get('rarity') or 0),
                    'upgrade_level': int(it.get('upgrade_level') or 0),
                    'gems': [str(g) for g in (it.get('socketed_gems') or [])],
                    'affixes': affixes, 'speed': float(speed) or 1.0,
                    # 强化前原貌：候选改强化等级（「与当前武器相同」）时据此重算，折叠值不可反推
                    'modifiers': [[int(s), int(t), float(v)] for s, t, v in (it['modifiers'] or [])],
                })
        if missing:
            warns.append(f'背包/仓库有 {missing} 件装备无实例数据（α 模式降级），未列入候选')

        # 4) 残差反解：按 to_sheet/add_mod 的同序累计各层，再从面板中扣除
        flat, add, mult = {}, {}, {}
        def _acc(mods):
            for m in mods:
                s, t, v = int(m.stat), int(m.type), float(m.value)
                if t == 0:
                    flat[s] = flat.get(s, 0.0) + v
                elif t == 1:
                    add[s] = add.get(s, 0.0) + v
                else:
                    mult[s] = mult.get(s, 1.0) * (1.0 + v)
        if gd is not None:
            for item in prof.assembled:
                _acc(item.modifiers(gd))
        _acc(prof.weapon_current.to_weapon().modifiers)
        for s in flat:
            base_v = panel_final.get(s, 0.0) - flat[s]
            factor = (1.0 + add.get(s, 0.0)) * mult.get(s, 1.0)
            prof.base[s] = (base_v / factor) if factor != 1.0 else base_v

        # 5) 主属性键位对准面板口径（在残差反解之后：反解可能已改写该键位）
        _align_primary_stat(prof, payload, gd)
        return prof


def save_build(profile: CharacterProfile, path: str) -> str:
    """把构建写盘（自动建目录），返回实际写入路径。"""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)
    return path


def load_build(path: str) -> CharacterProfile:
    with open(path, encoding='utf-8') as f:
        return CharacterProfile.from_dict(json.load(f))
