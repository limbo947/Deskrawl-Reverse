# -*- coding: utf-8 -*-
"""公式/数据层自检 + 换武器对比示例。

运行：python -m deskrawl_calc.cli     （在 tools 目录下执行）
"""
import sys
from .stattype import StatType, ModifierType, DamageType, stat_name
from .engine import Modifier, StatSheet, Target, Weapon, compare_weapons, DamageModel
from .gamedata import GameData


def selftest():
    """用《04 篇》给出的可对照数值做断言，确保公式实现与逆向证据一致。"""
    ok = []

    # 1) 三层聚合：base100 flat50 add0.5 mult1.2 → 150×1.5×1.2 = 270
    s = StatSheet({StatType.WeaponDamage: 100})
    s.add_mod(Modifier(StatType.WeaponDamage, ModifierType.Flat, 50))
    s.add_mod(Modifier(StatType.WeaponDamage, ModifierType.PercentAdd, 0.5))
    s.add_mod(Modifier(StatType.WeaponDamage, ModifierType.PercentMult, 0.2))
    ok.append(('三层聚合 = 270', abs(s.final(StatType.WeaponDamage) - 270.0) < 1e-9))

    # 2) 乘区A：物理 312.4% + 全伤害 88.3% → 1+3.124+0.883 = 5.007（同池加算）
    s = StatSheet()
    s.add_mod(Modifier(StatType.DamagePhysical, ModifierType.Flat, 3.124))
    s.add_mod(Modifier(StatType.DamagePercent, ModifierType.Flat, 0.883))
    m = DamageModel(s, DamageType.Physical)
    ok.append(('乘区A = 5.007', abs(m.type_multiplier() - 5.007) < 1e-9))

    # 3) 暴击：暴伤 381.2% → 4.812；暴击率封顶 0.85
    s = StatSheet()
    s.add_mod(Modifier(StatType.CritDamage, ModifierType.Flat, 3.812))
    s.add_mod(Modifier(StatType.CritChance, ModifierType.Flat, 0.9))
    m = DamageModel(s, DamageType.Physical)
    ok.append(('暴伤× = 4.812', abs(m.crit_multiplier() - 4.812) < 1e-9))
    ok.append(('暴击率封顶 0.85', abs(m.crit_chance() - 0.85) < 1e-9))

    # 3b) 封顶 1.0.2b：CDR 0.80、减伤 0.90（StatCap.GetCap@0x4AECB0 实证）
    s2 = StatSheet()
    s2.add_mod(Modifier(StatType.CooldownReduction, ModifierType.Flat, 0.95))
    s2.add_mod(Modifier(StatType.DamageReduction, ModifierType.Flat, 0.95))
    ok.append(('CDR 封顶 0.80（1.0.2b）', abs(s2.capped(StatType.CooldownReduction) - 0.80) < 1e-9))
    ok.append(('减伤封顶 0.90（1.0.2b）', abs(s2.capped(StatType.DamageReduction) - 0.90) < 1e-9))

    # 4) 护甲曲线：500 / (500 + 50×70) = 0.125
    t = Target(level=70, armor=500)
    ok.append(('护甲减伤 = 0.125', abs(t.armor_resist(DamageType.Physical) - 0.125) < 1e-9))

    # 5) 条件池：健康(>80%) + 精英 → 1 + 1.0 + 0.5 = 2.5（同池加算）
    s = StatSheet()
    s.add_mod(Modifier(StatType.DamageVsHealthy, ModifierType.Flat, 1.0))
    s.add_mod(Modifier(StatType.DamageVsElite, ModifierType.Flat, 0.5))
    m = DamageModel(s, DamageType.Physical)
    t = Target(hp_fraction=1.0, elite=True)
    ok.append(('条件池 = 2.5', abs(m.conditional_multiplier(t) - 2.5) < 1e-9))

    # 6) 易伤：带标记时 VulnerableDamage 进入条件池；倍率为固定 1.3
    import random as _rnd
    ok.append(('易伤进入条件池', StatType.VulnerableDamage in Target(vulnerable=True).conditional_stats()))
    mt = DamageModel(StatSheet(), DamageType.Physical)
    e0 = mt.compute(Target(hp_fraction=0.5), rng=_rnd.Random(0)).expected_mult
    e1 = mt.compute(Target(hp_fraction=0.5, vulnerable=True), rng=_rnd.Random(0)).expected_mult
    ok.append(('易伤倍率 = 1.3', abs(e1 / e0 - 1.3) < 1e-9))

    # 7) 主属性加成（Player.CalcDamage@0x518230，补丁前 bjr@0x509D80）：(武器伤害 + Damage(3)) ×(1 + Final(主属性)/100)
    s = StatSheet({StatType.WeaponDamage: 100, StatType.Damage: 50, StatType.Strength: 451})
    m = DamageModel(s, DamageType.Physical, primary_stat=StatType.Strength)
    ok.append(('主属性 ×5.51（力量 451 实测值）', abs(m.attack_damage() - 150.0 * 5.51) < 1e-9))
    ok.append(('未设主属性 ×1.0（兼容非玩家路径）',
               abs(DamageModel(s, DamageType.Physical).attack_damage() - 150.0) < 1e-9))

    # 8) 最终减伤（FinalDamageReduction=66，1.0.3 新增）：乘区之后的一次**绝对减法**、下限 0
    #    指令级依据：Character.ApplyDamage@0x1806893E0 尾部 `subsd xmm6, clamp(Final(66))` → max(0, trunc(·))
    s = StatSheet({StatType.WeaponDamage: 1000})
    m = DamageModel(s, DamageType.Physical)
    base = m.compute(Target(level=70), attack_speed=1.0, rng=_rnd.Random(0)).effective_dps
    red = m.compute(Target(level=70, final_damage_reduction=50.0), attack_speed=1.0,
                    rng=_rnd.Random(0)).effective_dps
    ok.append(('最终减伤 = 绝对减法（DPS −50）', abs(base - red - 50.0) < 1e-6))
    floor = m.compute(Target(level=70, final_damage_reduction=1e9), attack_speed=1.0,
                      rng=_rnd.Random(0)).effective_dps
    ok.append(('最终减伤下限：伤害不为负（保底 1/击）', abs(floor - 1.0) < 1e-9))

    # 9) DOT 跳伤（DamageOverTimeBehavior.TickDamage，语义别名见 aliases.json）：tick = (元素池 + Final(62)) × base
    #    指令级依据：`addsd xmm0(clamp(Final(62))), xmm6(ElementDamageMultiplier)`——62 与元素乘区**同池加算**（不是相乘）
    t0 = DamageModel(StatSheet({StatType.WeaponDamage: 100}), DamageType.Physical)
    tick0 = t0.dot_tick_damage(Target(level=1), 0.5)
    t1 = DamageModel(StatSheet({StatType.WeaponDamage: 100, StatType.DamageOverTime: 1.0}),
                     DamageType.Physical)
    tick1 = t1.dot_tick_damage(Target(level=1), 0.5)
    ok.append(('DOT 跳伤：62 与元素乘区同池加算（+1.0 使池 1.0→2.0，tick ×2）',
               abs(tick1 - 2.0 * tick0) < 1e-9))

    # 10) DOT tick 吃条件池（乘区 C）：tick 内 `[caster_klass+0x228]` 运行时解析为 Character.ConditionalDamagePool
    #     （指令级：live 读 .Player/.Enemy klass+0x228 → Player$$blw / Character$$blw）
    t2 = DamageModel(StatSheet({StatType.WeaponDamage: 100, StatType.DamageVsHealthy: 0.5}),
                     DamageType.Physical)
    tick2 = t2.dot_tick_damage(Target(level=1, hp_fraction=1.0), 0.5)
    ok.append(('DOT 跳伤吃条件池（完好 +0.5 → tick ×1.5）', abs(tick2 - 1.5 * tick0) < 1e-9))

    # 11) DOT 暴击按**目标方「暴击伤害减免(60)」**折减（ys 反汇编：1 + 暴击率×(1−clamp01(60))×(暴伤+加成)）
    t3 = DamageModel(StatSheet({StatType.CritChance: 0.5, StatType.CritDamage: 1.0}),
                     DamageType.Physical, weapon_damage=100)
    crit0 = t3.dot_tick_damage(Target(level=1), 0.5, can_crit=True)
    crit1 = t3.dot_tick_damage(Target(level=1, crit_damage_reduction=1.0), 0.5, can_crit=True)
    ok.append(('DOT 暴击按目标暴伤减免(60)折减（0→1.5×，1.0→1.0×）', abs(crit0 / crit1 - 1.5) < 1e-9))

    # 12) 传奇特效（EquipmentEffect_*）语义解释（effects.py；结构推断，见 docs/04 §6.3）
    from . import effects as _eff
    _sword = {'_class': 'EquipmentEffect_ConditionalCritChance', 'Condition': 0,
              'BonusCritChance': 0.30}
    ok.append(('特效·条件暴击率：易伤命中 → +0.30；目标未易伤 → 0',
               abs(_eff.crit_terms([_sword], Target(vulnerable=True))[0] - 0.30) < 1e-9
               and _eff.crit_terms([_sword], Target(vulnerable=False))[0] == 0.0))
    _ring = {'_class': 'EquipmentEffect_ConditionalCritDamage', 'Condition': 5,
             'Status': {'fileID': 0, 'pathID': 5385}, 'BonusCritDamage': 0.05,
             'ScaleByStatusStacks': True}
    ok.append(('特效·条件暴伤：SpecificStatus 按状态名命中并 ×层数（0.05×3=0.15）；无状态 → 0',
               abs(_eff.crit_terms([_ring], Target(statuses={'Brittle': 3}),
                                   status_names={5385: 'Brittle'})[1] - 0.15) < 1e-9
               and _eff.crit_terms([_ring], Target())[1] == 0.0))
    _glove = {'_class': 'EquipmentEffect_AbilityTagCritDamage', 'Tag': 9999,
              'Ability': {'fileID': 2, 'pathID': 59950}, 'BonusCritDamage': 1.5}
    _pants = {'_class': 'EquipmentEffect_AbilityTagCritDamage', 'Tag': 8,
              'Ability': None, 'BonusCritDamage': 1.5}
    ok.append(('特效·标签暴伤：Ability 名精确匹配；无 Ability 时按 Tag 命中技能标签',
               abs(_eff.ability_crit_damage([_glove], [0], 'SomeAbility',
                                            ability_names={59950: 'SomeAbility'}) - 1.5) < 1e-9
               and abs(_eff.ability_crit_damage([_pants], [8, 2], 'X') - 1.5) < 1e-9
               and _eff.ability_crit_damage([_pants], [2], 'X') == 0.0))

    # 13) 传奇特效·条件伤害（ConditionalDamage）：按 DamageType 过滤 + 条件门控 + 每负面状态递增
    _cd = {'_class': 'EquipmentEffect_ConditionalDamage', 'Condition': 3, 'Status': None,
           'DamageType': 2, 'BonusDamage': 0.9, 'Ability': None,
           'BaseBonusDamage': 0.0, 'DamagePerNegativeStatus': 0.0}
    ok.append(('特效·条件伤害：按 DamageType 过滤 + 精英门控（冰霜 0.9 命中；物理/非精英 0）',
               abs(_eff.conditional_damage([_cd], 2, Target(elite=True)) - 0.9) < 1e-9
               and _eff.conditional_damage([_cd], 0, Target(elite=True)) == 0.0
               and _eff.conditional_damage([_cd], 2, Target(elite=False)) == 0.0))
    _cd2 = {'_class': 'EquipmentEffect_ConditionalDamage', 'Condition': 1, 'Status': None,
            'DamageType': 0, 'BonusDamage': 0.5, 'Ability': None,
            'BaseBonusDamage': 0.0, 'DamagePerNegativeStatus': 0.25}
    _m2 = DamageModel(StatSheet(), DamageType.Physical, conditional_damage=0.75)
    ok.append(('特效·条件伤害：每负面状态递增（眩晕 → 0.5+0.25×1=0.75）且进条件池（×1.75）',
               abs(_eff.conditional_damage([_cd2], 0, Target(stunned=True)) - 0.75) < 1e-9
               and abs(_m2.conditional_multiplier(Target()) - 1.75) < 1e-9))

    # 14) 传奇特效·技能修正（AbilityModifier / AbilityChannelModifier）→ {ModifiedStat: 值}
    _am = {'_class': 'EquipmentEffect_AbilityModifier', 'Tag': 8, 'Ability': None,
           'Stat': 2, 'Modifier': 0.6}
    _cm = {'_class': 'EquipmentEffect_AbilityChannelModifier', 'Tag': 9999,
           'Ability': {'fileID': 2, 'pathID': 59959}, 'ChannelSpeedBonus': 0.25,
           'AdditionalChannelDurationSeconds': 3.0}
    ok.append(('特效·技能修正：AbilityModifier 按 Tag 命中 → Damage(2) +0.6；未命中 → 空',
               _eff.ability_mods_for([_am], 'WarriorHeavyAttack1', [1, 8]) == {2: 0.6}
               and _eff.ability_mods_for([_am], 'X', [0]) == {}))
    _m_cm = _eff.ability_mods_for([_cm], 'WarriorHeavyAttack3', [1],
                                  ability_names={59959: 'WarriorHeavyAttack3'}, channel_base=4.0)
    ok.append(('特效·引导修改：ChannelSpeed(8) +0.25；附加时长按 base 归一为比例 3/4=0.75（REA 实证）',
               abs(_m_cm.get(8, 0.0) - 0.25) < 1e-9 and abs(_m_cm.get(13, 0.0) - 0.75) < 1e-9
               and _eff.ability_mods_for([_cm], 'Other', []) == {}))
    _am13 = {'_class': 'EquipmentEffect_AbilityModifier', 'Tag': 9999,
             'Ability': {'fileID': 2, 'pathID': 59959}, 'Stat': 13, 'Modifier': 0.5}
    ok.append(('特效·技能修正：ModifiedStat.ChannelDuration(13) 是**比例**（原值 0.5 → dur = base×1.5）',
               abs(_eff.ability_mods_for([_am13], 'WarriorHeavyAttack3', [1],
                                         ability_names={59959: 'WarriorHeavyAttack3'})
                   .get(13, 0.0) - 0.5) < 1e-9))

    # 15) 属性换算（StatConversion）：TargetStat += Final(SourceStat) × Fraction（显式后步）
    _sc = {'_class': 'EquipmentEffect_StatConversion', 'SourceStat': 0, 'TargetStat': 39,
           'Fraction': 0.1}
    _s3 = StatSheet({StatType.Strength: 100})
    _s3.add_conversion(0, 39, 0.1)
    ok.append(('特效·属性换算：力量 100 → 荆棘 += 10（Final(源)×Fraction）；src==tgt 跳过',
               abs(_s3.final(StatType.Thorns) - 10.0) < 1e-9
               and _eff.stat_conversions([_sc]) == [(0, 39, 0.1)]
               and StatSheet({StatType.Strength: 100}).add_conversion(0, 0, 0.5)
                   .final(StatType.Strength) == 100.0))

    for desc, good in ok:
        print(f'  [{"PASS" if good else "FAIL"}] {desc}')
    return all(g for _, g in ok)


def demo():
    gd = GameData()
    print(f'\n数据层：物品 {len(gd.items())} / 宝石 {len(gd.gems())} / 符文 {len(gd.runes())} / '
          f'天赋 {len(gd.talents())} / 符文套 {len(gd.runesets())}')

    # 角色基础（面板基础字段；真实工具里由用户输入或从存档/内存读取）
    base = StatSheet({StatType.WeaponDamage: 0})
    # 从数据层自动装配：宝石 + 符文 + 天赋 + 巅峰
    base.add_mods(gd.gem_modifiers('GemAmethyst3', equip_category=2))     # 武器孔：奥术+20%
    base.add_mods(gd.rune_modifiers('HunterSetRune1_4', rune_level=3))    # 暴伤曲线
    base.add_mods(gd.talent_modifiers('HunterTalent19', points=5))        # 毒伤/击中回血
    base.add_mods(gd.paragon_modifiers({4: 50}))                          # 巅峰：暴击率 50 点

    print('  已装配词条：')
    for st in (StatType.DamageArcane, StatType.CritDamage, StatType.CritChance, StatType.DamagePoison):
        b = base.breakdown(st)
        if b['Final']:
            print(f'    {stat_name(st):<10} Final={b["Final"]:.4f}  (Base {b["Base"]}, Flat {b["Flat"]}, '
                  f'%Add {b["PercentAdd"]}, Π{base.mult.get(int(st),1.0):.3f})')

    # 两把候选武器（词条取自实际掉落/面板；此处为示例）
    current = Weapon('旧武器·双手剑', base_damage=100, base_speed=1.0,
                     modifiers=[Modifier(StatType.DamagePhysical, ModifierType.Flat, 0.50)])
    candidate = Weapon('新武器·战斧', base_damage=110, base_speed=0.95,
                       modifiers=[Modifier(StatType.DamagePhysical, ModifierType.Flat, 0.30),
                                  Modifier(StatType.CritDamage, ModifierType.Flat, 0.20),
                                  Modifier(StatType.DamageVsElite, ModifierType.Flat, 0.25)])

    target = Target(level=70, elite=True, hp_fraction=1.0, vulnerable=True)
    r = compare_weapons(base, current, candidate, target=target, damage_type=DamageType.Physical)

    print('\n  === 换武器对比（目标：70 级精英·满血·易伤）===')
    for tag, w in (('current', current), ('candidate', candidate)):
        d = r[tag]
        m = d['model']
        print(f'  {d["weapon"]:<12} DPS={d["dps"]:.1f}  (基础伤害 {w.base_damage}, 攻速 {w.base_speed})')
        print(f'      乘区A={m.type_multiplier():.3f}  暴击率={m.crit_chance():.3f}  '
              f'暴伤×={m.crit_multiplier():.3f}  条件池={m.conditional_multiplier(target):.3f}  '
              f'有效攻速={m.effective_attack_speed(w.base_speed):.3f}')
    print(f'  → 变化：{r["delta"]:+.1f} DPS  ({r["delta_pct"]:+.2f}%)')


if __name__ == '__main__':
    print('=== 公式自检（对照 04 篇证据）===')
    allok = selftest()
    if len(sys.argv) > 1 and sys.argv[1] == 'selftest':
        sys.exit(0 if allok else 1)
    demo()
    print('\n自检', '全部通过 ✅' if allok else '存在失败 ❌')
