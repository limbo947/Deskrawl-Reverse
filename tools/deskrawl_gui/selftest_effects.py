# -*- coding: utf-8 -*-
"""特效消费侧自检（纯数据，不需要 QApplication / 实机）。

为什么单独一组：`selftest_fixture.py` 已逼近 800 行上限，而这类「一条特效一个口径」的
断言彼此独立、不依赖夹具，拆出来反而便于按需阅读。

`rep` 是 selftest.Report 的鸭子类型实例（不 import 以免与主模块循环引用）。
"""
from __future__ import annotations


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
