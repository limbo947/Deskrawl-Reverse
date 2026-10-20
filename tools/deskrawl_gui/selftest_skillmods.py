# -*- coding: utf-8 -*-
"""天赋「按技能修正」的解析侧自检（纯数据，不需要 QApplication / 实机）。

为什么单独一组：2026-10-19 起 `TalentEffect_AbilityModifier` 不只有指针型（按技能），
还有 Tag 型（按 AbilityTag 展开），而 `memory_validate` 的行格式随之变成 3/4 元两种。
这两处都能用合成数据证伪，不必连游戏；实机只用来对拍面板数值。

`rep` 是 selftest.Report 的鸭子类型实例（不 import 以免与主模块循环引用）。
"""
from __future__ import annotations


def _talent_mod_checks(rep) -> None:
    """Tag 型展开到同类技能 + 指针型按名字落位 + 校验接受两种行格式。"""
    from deskrawl_calc import GameData

    from .core.memory_validate import _talent_mod_row_ok
    from .core.profile import _talent_ability_mods

    gd = GameData()
    names = gd.abilities_for_class(1)                     # Barbarian
    ptrs = [0x100000 + i for i in range(len(names))]      # 假指针：只验证「第 i 个 ↔ 第 i 个名字」
    strong = [sk['name'] for sk in gd.damage_skills(1) if 1 in (sk.get('tags') or [])]
    other = 'WarriorSpecial3'                             # tags=[2,7]：不含 StrongAttack
    out = _talent_ability_mods(ptrs, [[8, ptrs[1], 0.5], [2, 0, 0.3, 1]], 1, gd)

    ptr_ok = out.get(names[1], {}).get(8) == 0.5
    tag_ok = bool(strong) and all(out.get(n, {}).get(2) == 0.3 for n in strong)
    neg_ok = not (out.get(other) or {}).get(2)             # 反向：未命中 tag 的技能不受影响
    row_ok = (_talent_mod_row_ok([2, 0x100000, 0.5]) and _talent_mod_row_ok([2, 0, 0.5, 1])
              and not _talent_mod_row_ok([2, 0, 0.5])       # 指针 0 的 3 元组是脏数据
              and not _talent_mod_row_ok([2, 0, 0.5, 9999])  # Tag=None 不构成目标
              and not _talent_mod_row_ok([2, 0, float('nan'), 1]))
    rep.add(ptr_ok and tag_ok and neg_ok and row_ok,
            '天赋技能修正：指针型按技能落位 / Tag 型展开到同类技能（校验收 3·4 元组）',
            f'指针型 {names[1]}=0.5；Tag=1 展开 {len(strong)} 个技能={tag_ok}；'
            f'未命中技能不受影响={neg_ok}；行格式校验={row_ok}')


def _talent_stat_checks(rep) -> None:
    """天赋条件属性：Healthy/None 生效、场景条件不生效、装配只折进成立的那条。"""
    from deskrawl_calc import GameData

    from .core.profile import CharacterProfile, _condition_ok

    gd = GameData()
    t = CharacterProfile.demo().to_target()          # 默认目标满血（hp_fraction=1.0）
    cond_ok = (_condition_ok(1, t) and not _condition_ok(0, t) and _condition_ok(-1, t)
               and not any(_condition_ok(c, t) for c in (2, 3, 4, 5)))
    # 装配：Healthy(+3% 闪避) 与 Surrounded(+9%) 各一条，只有前者该进表
    p = CharacterProfile.demo()
    p.talent_stat_mods = [
        {'Condition': 1, 'Modifiers': [{'Stat': 22, 'Type': 0, 'Value': 0.03}]},
        {'Condition': 5, 'Modifiers': [{'Stat': 22, 'Type': 0, 'Value': 0.09}]},
    ]
    p0 = CharacterProfile.demo()
    p0.talent_stat_mods = []
    got = p.to_sheet(gd).final(22) - p0.to_sheet(gd).final(22)
    sheet_ok = abs(got - 0.03) < 1e-9
    rep.add(cond_ok and sheet_ok,
            '天赋条件属性（Healthy/None 生效、场景条件不生效、装配只加成立项）',
            f'条件判定={cond_ok}；装配 Δ闪避={got:.4f}（期望 0.03，Surrounded 的 0.09 不计）')


def _talent_bonus_checks(rep) -> None:
    """天赋条件加伤：指纹反查（含「同指纹必须丢弃」） + 状态门控 + RequireOnSelf 跳过。"""
    from deskrawl_calc import GameData, Target, effects

    from .core.profile import _talent_bonus_effects

    gd = GameData()
    snames = gd.status_name_by_pathid()
    # 唯一指纹：Increase Damage On Dazed（0.15/0.15，无 Ability）
    raw = [{'status': 111, 'ability': 0, 'tag': 9999, 'self': False,
            'base': 0.15000000596046448, 'per': 0.15000000596046448, 'value': 0.30}]
    effs = _talent_bonus_effects(raw, gd)
    uniq_ok = len(effs) == 1 and abs(effs[0]['BonusDamage'] - 0.30) < 1e-9
    # Burn / Electrostatic 的 (Tag, 有无 Ability, Base, Per) 完全相同 → 必须丢弃而不是猜
    dup = [{'status': 222, 'ability': 1, 'tag': 9999, 'self': False,
            'base': 0.05999999865889549, 'per': 0.05999999865889549, 'value': 0.06}]
    dup_ok = _talent_bonus_effects(dup, gd) == []
    # 状态门控：目标带 [恍惚] 才计入
    sn = snames.get(60551, '')
    on = effects.conditional_bonus_damage(effs, Target(level=70, statuses={sn: 1}),
                                          status_names=snames)
    off = effects.conditional_bonus_damage(effs, Target(level=70), status_names=snames)
    # RequireOnSelf（嗜血：状态在自身）静态无自身状态数据 → 恒 0
    self_eff = {'_class': 'TalentEffect_ConditionalBonusDamage', 'RequireOnSelf': True,
                'RequiredStatus': {'pathID': 60599}, 'BonusDamage': 0.5}
    self_ok = effects.conditional_bonus_damage(
        [self_eff], Target(level=70, statuses={snames.get(60599, ''): 1}),
        status_names=snames) == 0.0
    rep.add(uniq_ok and dup_ok and abs(on - 0.30) < 1e-9 and off == 0.0 and self_ok,
            '天赋条件加伤（指纹反查 / 同指纹丢弃 / 目标状态门控 / RequireOnSelf 跳过）',
            f'唯一指纹={uniq_ok}；同指纹丢弃={dup_ok}；带[恍惚] {on:.2f}、无状态 {off:.2f}；'
            f'自身状态条目不误算={self_ok}')


def _talent_crit_checks(rep) -> None:
    """天赋条件暴击/暴伤：内存行 → 静态表指纹反查 → 目标门控 → 技能限定。

    这三段串起来才证明链路真实：只测 crit_terms 会漏「名字补不上」，只测指纹会漏「门控没生效」。
    """
    from deskrawl_calc import GameData, Target, effects

    from .core.profile import _talent_crit_effects

    gd = GameData()
    snames = gd.status_name_by_pathid()
    anames = gd.ability_name_by_pathid()

    # 1) 指纹反查：Higher Crit to Distant（Condition=6、0.03/级，无 Ability/Tag 限定）
    raw = [{'klass': 'TalentEffect_ConditionalCritChance', 'condition': 6, 'status': 111,
            'base': 0.029999999329447746, 'per': 0.029999999329447746,
            'value': 0.09, 'ability': 0, 'tag': 9999}]
    effs = _talent_crit_effects(raw, gd)
    look_ok = (len(effs) == 1 and effs[0]['Condition'] == 6
               and abs(effs[0]['BonusCritChance'] - 0.09) < 1e-9
               and effs[0].get('SpecifiedStatus') is not None)
    # 2) 门控：远处目标才计入（Condition=6）
    cc_far, _ = effects.crit_terms(effs, Target(level=70, distant=True), status_names=snames)
    cc_near, _ = effects.crit_terms(effs, Target(level=70), status_names=snames)
    gate_ok = abs(cc_far - 0.09) < 1e-9 and cc_near == 0.0
    # 3) 技能限定：带 Ability 的条目只在命中该技能时计入，面板口径（无技能上下文）跳过
    bleeding = {'_class': 'TalentEffect_ConditionalCritChance', 'Condition': 5,
                'Ability': {'pathID': 59963}, 'Tag': 9999,
                'SpecifiedStatus': {'pathID': 60528}, 'BonusCritChance': 1.0}
    sk, sn = anames.get(59963, ''), snames.get(60528, '')
    t_on = Target(level=70, statuses={sn: 1} if sn else {})
    cc_hit, _ = effects.crit_terms([bleeding], t_on, status_names=snames, ability_names=anames,
                                   ability_name=sk, tags=[])
    cc_miss, _ = effects.crit_terms([bleeding], t_on, status_names=snames, ability_names=anames,
                                    ability_name='NotThisSkill', tags=[])
    cc_panel, _ = effects.crit_terms([bleeding], t_on, status_names=snames, ability_names=anames)
    scope_ok = abs(cc_hit - 1.0) < 1e-9 and cc_miss == 0.0 and cc_panel == 0.0
    rep.add(look_ok and gate_ok and scope_ok,
            '天赋条件暴击（指纹反查状态名 / 目标门控 / 技能限定不入面板口径）',
            f'指纹命中={look_ok}（{effs[0].get("BonusCritChance") if effs else "无"}）；'
            f'远处 {cc_far:.2f} / 近处 {cc_near:.2f}；'
            f'限定技能 {sk} 命中={cc_hit:.2f}、他技能={cc_miss:.2f}、面板口径={cc_panel:.2f}')
