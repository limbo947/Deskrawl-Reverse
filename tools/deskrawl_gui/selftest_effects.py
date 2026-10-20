# -*- coding: utf-8 -*-
"""特效消费侧自检（纯数据，不需要 QApplication / 实机）。

为什么单独一组：`selftest_fixture.py` 已逼近 800 行上限，而这类「一条特效一个口径」的
断言彼此独立、不依赖夹具，拆出来反而便于按需阅读。

`rep` 是 selftest.Report 的鸭子类型实例（不 import 以免与主模块循环引用）。
"""
from __future__ import annotations


def _conversion_panel_checks(rep) -> None:
    """面板复算补换算：目标行 += 源面板值×系数（进平坦层），且基座口径不掺换算。

    两个口径都要断言：只测「含换算」会漏掉重复计（base 也含了换算 → DPS 算两遍），
    只测「不含」会漏掉面板偏低。用 β 夹具造两条换算（一条带状态门控），差异可手算。
    """
    import copy

    from .core import calc_service
    from .selftest_fixture import _load_fixture

    beta = _load_fixture('snapshot_beta.json')
    base = {r[0]: r for r in calc_service.build_panel(beta, with_conversions=False)['rows']}
    hp = float(base[7][5])                     # 面板生命（源；已含 1.505 特殊%）
    payload = copy.deepcopy(beta)
    payload['player']['conversions'] = [
        {'source': 7, 'target': 36, 'fraction': 0.05, 'status': 0},
        {'source': 7, 'target': 2, 'fraction': 0.10, 'status': 0x1234},    # 需状态 → 不计
    ]
    panel = calc_service.build_panel(payload)
    rows = {r[0]: r for r in panel['rows']}
    want = 0.05 * hp * (1.0 + rows[36][3]) * rows[36][4]
    got = rows[36][5] - base[36][5]
    same_base = ([r for r in calc_service.build_panel(payload, with_conversions=False)['rows']]
                 == calc_service.build_panel(beta, with_conversions=False)['rows'])
    gated_ok = 2 not in rows and any('依赖状态' in w for w in panel['warnings'])
    rep.add(abs(got - want) < 1e-9 and same_base and gated_ok,
            '面板复算·属性换算（目标 += 源面板×系数进平坦层；基座口径不掺换算）',
            f'生命回复 Δ={got:.4f}（期望 {want:.4f}=生命 {hp:.0f}×0.05×缩放）；'
            f'with_conversions=False 与原行逐项相等={same_base}；'
            f'带状态条目跳过并告警={gated_ok}')


def _health_condition_checks(rep) -> None:
    """`AlwaysHealthConditionalDamage`：置位后健康(29)与受伤(30)两条件**同时**成立。

    指令级依据（`Character.ConditionalDamagePool` @`0x1806885C0`）：两处血线判断都是
    `if (this+0x15c || hp 阈值)`，所以不是「只视为健康」——这条断言就是防止把它写回去。
    """
    from deskrawl_calc import DamageModel, StatSheet, StatType, Target, effects

    eff = {'_class': 'EquipmentEffect_AlwaysHealthConditionalDamage'}
    sheet = StatSheet(base={StatType.DamageVsHealthy: 0.75, StatType.DamageVsInjured: 0.5})
    t_mid = Target(level=70)
    t_mid.hp_fraction = 0.5              # 两个阈值都不满足：健康要 >0.8、受伤要 <0.3

    def pool(flag: bool) -> float:
        return DamageModel(sheet, 1, ignore_health=flag).conditional_multiplier(t_mid)

    off, on = pool(False), pool(True)
    rep.add(abs(off - 1.0) < 1e-9 and abs(on - 2.25) < 1e-9
            and effects.always_health_conditions([eff])
            and not effects.always_health_conditions([])
            and not effects.unmodeled_classes([eff]),
            '传奇特效·无视血线（AlwaysHealthConditionalDamage：健康29 与 受伤30 同时成立）',
            f'hp=50% 无特效={off:.2f}（健康/受伤都不满足）；有特效={on:.2f}'
            f'（期望 2.25=1+0.75+0.5）；已计入不再标「未计入」='
            f'{not effects.unmodeled_classes([eff])}')
