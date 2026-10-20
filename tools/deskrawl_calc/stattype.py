# -*- coding: utf-8 -*-
"""StatType 枚举与分组表。

来源：《Deskrawl 数值设计文档》02-属性系统与枚举（指令级证据 ✅）。
注意：枚举值不连续，游戏内以稀疏 ID 参与存档/配置，禁止重排。
"""
from enum import IntEnum


class StatType(IntEnum):
    # 主属性
    Strength = 0            # 力量
    Dexterity = 1           # 敏捷
    Intelligence = 2        # 智力
    # 输出
    Damage = 3              # 通用增伤
    CritChance = 4          # 暴击几率        [封顶 0.85]
    CritDamage = 5          # 暴击伤害
    AttackSpeed = 6         # 攻击速度(%)
    # 生存
    MaxHealth = 7           # 最大生命(固定)
    MaxHealthPercent = 42   # 最大生命(%)
    Armor = 8               # 护甲
    ArmorPercent = 44       # 护甲(%)
    MagicResist = 9         # 魔抗
    MagicResistPercent = 59 # 魔抗(%)
    Dodge = 22              # 闪避率          [封顶 0.85]
    CritDamageReduction = 60
    DamageReduction = 64    # 全局减伤        [封顶 0.90]
    FinalDamageReduction = 66  # 最终减伤（1.0.3 新增；GetCap 落 inf 分支→无上限，见 docs/08 §14.3）
    PoisonDamageReduction = 49
    PhysicalDamageReduction = 51
    FireDamageReduction = 52
    ColdDamageReduction = 53
    LightningDamageReduction = 54
    ArcaneDamageReduction = 55
    # 机动
    MoveSpeed = 10
    MoveSpeedPercent = 57
    # 回复
    LifeOnHit = 11
    LifeOnKill = 12
    LifeRegen = 36
    HealingReceivedBonus = 56
    # 循环
    CooldownReduction = 13  # [封顶 0.80]
    MaxMana = 14
    ManaOnKill = 35
    ManaRegen = 47
    ManaCostReduction = 37  # [封顶 0.85]
    PotionCharges = 38
    # 收益
    GoldFind = 15
    MagicFind = 16
    HpPotionFind = 17
    Capacity = 18
    MaterialFind = 19
    XPGain = 41
    GemSlots = 50
    # 武器
    WeaponDamage = 20
    WeaponSpeed = 21
    # 元素乘区（与 DamagePercent 同池加算）
    DamagePhysical = 23
    DamageFire = 24
    DamageCold = 25
    DamageLightning = 26
    DamagePoison = 27
    DamageArcane = 28
    DamagePercent = 65      # 全伤害加成
    # 条件乘区（10 项同池加算）
    DamageVsHealthy = 29
    DamageVsInjured = 30
    DamageVsSlowed = 31
    DamageVsElite = 32
    VulnerableDamage = 40
    DamageVsImmobilized = 43
    DamageVsBleeding = 45
    DamageVsPoisoned = 46
    DamageVsDistant = 58
    DamageVsBurned = 63
    # 技能类型
    BasicAttackDamage = 33
    StrongAttackDamage = 34
    SpecialAbilityDamage = 61
    DamageOverTime = 62
    # 反伤
    Thorns = 39
    ThornsDamagePercent = 48


class ModifierType(IntEnum):
    Flat = 0          # 求和
    PercentAdd = 1    # 求和
    PercentMult = 2   # 连乘 (1+v)


class DamageType(IntEnum):
    Physical = 0
    Fire = 1
    Cold = 2
    Lightning = 3
    Poison = 4
    Arcane = 5


# 硬编码分组表（ItemizationConfig.StaticInit @ 0x715FE0，补丁前 ..cctor @ 0x6F6360）
CORE = [StatType.Strength, StatType.Dexterity, StatType.Intelligence]
ALL_ELEMENTS = [StatType.DamagePhysical, StatType.DamageFire, StatType.DamageCold,
                StatType.DamageLightning, StatType.DamagePoison, StatType.DamageArcane]
CONDITIONAL_DAMAGE = [StatType.DamageVsHealthy, StatType.DamageVsInjured, StatType.DamageVsSlowed,
                      StatType.DamageVsElite, StatType.VulnerableDamage, StatType.DamageVsImmobilized,
                      StatType.DamageVsBleeding, StatType.DamageVsPoisoned, StatType.DamageVsDistant,
                      StatType.DamageVsBurned]

# DamageType → StatType（跳转表在 Character.ElementDamageMultiplier@0x6884E0 内，与 ALL_ELEMENTS 一致）
DAMAGE_TYPE_TO_STAT = {
    DamageType.Physical: StatType.DamagePhysical,
    DamageType.Fire: StatType.DamageFire,
    DamageType.Cold: StatType.DamageCold,
    DamageType.Lightning: StatType.DamageLightning,
    DamageType.Poison: StatType.DamagePoison,
    DamageType.Arcane: StatType.DamageArcane,
}

# 属性封顶表（StatCap.GetCap@0x4AECB0 反汇编实证，1.0.2b；旧统一 0.85 掩码 0x402010 已拆分）：
#   0.85 = 暴击率(4)/闪避(22)/蓝耗缩减(37)；0.80 = 冷却缩减(13)（1.0.2b 由 0.85 下调，见更新说明）；
#   0.90 = 通用减伤(64)与各元素减伤(49/51-55)（1.0.2b 由无上限收紧为 90%）；其余无上限（inf）。
CAPPED_085 = {StatType.CritChance, StatType.Dodge, StatType.ManaCostReduction}
CAPPED_080 = {StatType.CooldownReduction}
# 减伤类封顶 0.90（旧 CLAMP_01 的 1.0 口径已被 1.0.2b 取代）
CAPPED_090 = {StatType.DamageReduction, StatType.PoisonDamageReduction, StatType.PhysicalDamageReduction,
              StatType.FireDamageReduction, StatType.ColdDamageReduction, StatType.LightningDamageReduction,
              StatType.ArcaneDamageReduction}

# 以「小数」表示百分比的属性（存档/词条里 0.30 = 30%）。GUI 输入框据此切换单位：显示 30、
# 内部存 0.3——否则 30% 填成 30 就是 3000% 且不报错。
# 注意与「面板显示格式」（下面的 PERCENT_DISPLAY_STATS）是两件事，语义不同不可合并。
FRACTIONAL_STATS = frozenset(
    {4, 5, 6, 13, 15, 16, 17, 19, 22, 37, 41, 56, 57, 65}
    | set(range(23, 35))                       # 元素乘区 23–28 + 条件 29–32 + 普攻·强攻 33–34
    | {40, 42, 43, 44, 45, 46, 48, 49, 51, 52, 53, 54, 55, 58,
       59, 60, 61, 62, 63, 64})


def is_fractional(stat) -> bool:
    """该属性是否以小数形式表示百分比（决定输入框显示 % 还是数值）。"""
    return int(stat) in FRACTIONAL_STATS


# 「面板按百分比显示」的属性（46 项，与游戏「属性」页逐行对拍所得）。只决定显示格式，
# 与上面的输入单位是两套元数据：例如 21 武器速度按一位小数、7 生命按千分位，
# 而 0/1/2 主属性显示数值——这些属性在 FRACTIONAL_STATS 里都不存在。
# 为什么下沉到内核：原先它是 core/calc_service 里的一份字面量，新增属性要在两处各判一次，
# 漏改的表现是「面板显示成 3000%」这种静默错误；放进 stattype 与 CAPPED_* 同一层。
PERCENT_DISPLAY_STATS = frozenset({
    4, 5, 6, 13, 15, 16, 17, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32,
    33, 34, 37, 40, 41, 42, 43, 44, 45, 46, 48, 49, 51, 52, 53, 54, 55,
    56, 57, 58, 59, 60, 61, 62, 63, 64, 65})


def is_percent_display(stat) -> bool:
    """该属性在面板口径里是否按百分比显示（决定格式化，不涉及输入单位）。"""
    return int(stat) in PERCENT_DISPLAY_STATS

# 元素减伤 StatType 按伤害类型（跳转表在 Character.ApplyDamage@0x6893E0 内）
ELEM_REDUCTION_BY_DAMAGE = {
    DamageType.Physical: StatType.PhysicalDamageReduction,
    DamageType.Fire: StatType.FireDamageReduction,
    DamageType.Cold: StatType.ColdDamageReduction,
    DamageType.Lightning: StatType.LightningDamageReduction,
    DamageType.Poison: StatType.PoisonDamageReduction,
    DamageType.Arcane: StatType.ArcaneDamageReduction,
}

STAT_NAMES = {
    0: '力量', 1: '敏捷', 2: '智力', 3: '通用增伤', 4: '暴击率', 5: '暴击伤害', 6: '攻击速度%',
    7: '最大生命', 8: '护甲', 9: '魔抗', 10: '移动速度', 11: '击中回血', 12: '击杀回血', 13: '冷却缩减',
    14: '最大法力', 15: '金币获取', 16: '魔法装备获取', 17: '药水掉落', 18: '背包容量', 19: '材料获取',
    20: '武器伤害', 21: '武器速度', 22: '闪避', 23: '物理伤害%', 24: '火焰伤害%', 25: '冰霜伤害%',
    26: '闪电伤害%', 27: '毒素伤害%', 28: '奥术伤害%', 29: '对健康敌人', 30: '对受伤敌人', 31: '对减速敌人',
    32: '对精英', 33: '普攻伤害', 34: '强力攻击伤害', 35: '击杀回蓝', 36: '生命回复', 37: '法力消耗缩减',
    38: '药水充能', 39: '荆棘', 40: '对易伤敌人', 41: '经验获取', 42: '最大生命%', 43: '对定身敌人',
    44: '护甲%', 45: '对流血的敌人', 46: '对中毒的敌人', 47: '法力回复', 48: '荆棘伤害%', 49: '毒素减伤',
    50: '宝石孔位', 51: '物理减伤', 52: '火焰减伤', 53: '冰霜减伤', 54: '闪电减伤', 55: '奥术减伤',
    56: '受治疗效果加成', 57: '移动速度%', 58: '对远处敌人', 59: '魔抗%', 60: '暴击伤害减免',
    61: '特殊技能加成伤害', 62: '持续伤害', 63: '对灼烧的敌人', 64: '全局减伤', 65: '全伤害加成%',
    66: '最终减伤',
}


def name(stat) -> str:
    """属性 ID → 中文名（未知则返回数值）。"""
    try:
        return STAT_NAMES.get(int(stat), f'Stat{int(stat)}')
    except (TypeError, ValueError):
        return str(stat)


stat_name = name  # 别名，便于外部 import
