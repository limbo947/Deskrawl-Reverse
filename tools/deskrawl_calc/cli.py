# -*- coding: utf-8 -*-
"""公式/数据层自检 + 换武器对比示例。

运行：python -m deskrawl_calc.cli     （在 C:\\Users\\cc\\tools 下执行）
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

    # 3b) 封顶 1.0.2b：CDR 0.80、减伤 0.90（StatCap.GetCap@0x4AC490 实证）
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

    # 7) 主属性加成（Player.CalcDamage@0x511060，补丁前 bjr@0x509D80）：(武器伤害 + Damage(3)) ×(1 + Final(主属性)/100)
    s = StatSheet({StatType.WeaponDamage: 100, StatType.Damage: 50, StatType.Strength: 451})
    m = DamageModel(s, DamageType.Physical, primary_stat=StatType.Strength)
    ok.append(('主属性 ×5.51（力量 451 实测值）', abs(m.attack_damage() - 150.0 * 5.51) < 1e-9))
    ok.append(('未设主属性 ×1.0（兼容非玩家路径）',
               abs(DamageModel(s, DamageType.Physical).attack_damage() - 150.0) < 1e-9))

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
