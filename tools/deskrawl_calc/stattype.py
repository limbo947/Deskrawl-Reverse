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
    DamageReduction = 64    # 全局减伤        [clamp 0,1]
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
    CooldownReduction = 13  # [封顶 0.85]
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


# 硬编码分组表（ItemizationConfig.StaticInit @ 0x706A50，补丁前 ..cctor @ 0x6F6360）
CORE = [StatType.Strength, StatType.Dexterity, StatType.Intelligence]
ALL_ELEMENTS = [StatType.DamagePhysical, StatType.DamageFire, StatType.DamageCold,
                StatType.DamageLightning, StatType.DamagePoison, StatType.DamageArcane]
CONDITIONAL_DAMAGE = [StatType.DamageVsHealthy, StatType.DamageVsInjured, StatType.DamageVsSlowed,
                      StatType.DamageVsElite, StatType.VulnerableDamage, StatType.DamageVsImmobilized,
                      StatType.DamageVsBleeding, StatType.DamageVsPoisoned, StatType.DamageVsDistant,
                      StatType.DamageVsBurned]

# DamageType → StatType（跳转表在 Character.ElementDamageMultiplier@0x67D010 内，与 ALL_ELEMENTS 一致）
DAMAGE_TYPE_TO_STAT = {
    DamageType.Physical: StatType.DamagePhysical,
    DamageType.Fire: StatType.DamageFire,
    DamageType.Cold: StatType.DamageCold,
    DamageType.Lightning: StatType.DamageLightning,
    DamageType.Poison: StatType.DamagePoison,
    DamageType.Arcane: StatType.DamageArcane,
}

# 封顶 0.85 的 4 项（StatCap.Clamp@0x4A91C0，掩码 0x402010 + 特判 37）
CAPPED_085 = {StatType.CritChance, StatType.CooldownReduction, StatType.Dodge, StatType.ManaCostReduction}
# clamp[0,1] 的减伤项
CLAMP_01 = {StatType.DamageReduction, StatType.PoisonDamageReduction, StatType.PhysicalDamageReduction,
            StatType.FireDamageReduction, StatType.ColdDamageReduction, StatType.LightningDamageReduction,
            StatType.ArcaneDamageReduction}

# 元素减伤 StatType 按伤害类型（跳转表在 Character.ApplyDamage@0x67E320 内）
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
}


def name(stat) -> str:
    """属性 ID → 中文名（未知则返回数值）。"""
    try:
        return STAT_NAMES.get(int(stat), f'Stat{int(stat)}')
    except (TypeError, ValueError):
        return str(stat)


stat_name = name  # 别名，便于外部 import
