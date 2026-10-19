# -*- coding: utf-8 -*-
"""传奇词条文案自检（纯数据，不需要 QApplication）。

为什么从 selftest.py 拆出来：主文件有效行数已过 700，而文案检查与数值对拍毫无耦合，
搬出来既让主文件回落，也把「数据侧文案」凑成可单独阅读的一组。

`rep` 是 selftest.Report 的鸭子类型实例（不 import 以免与主模块循环引用）。
"""
from __future__ import annotations


def _legendary_checks(rep) -> None:
    """三层来源（整件 Desc / 特效前缀 / 类模板）+ 令牌填值（同表字段与跨表技能名）。"""
    from deskrawl_calc import GameData

    from .core.legendary import legendary_lines

    gd = GameData()
    sword = legendary_lines(gd, 'LegendarySword1')               # 整件 Desc（无令牌）
    neck = ' '.join(legendary_lines(gd, 'LegendaryNeck4'))       # 特效前缀 + {chance} ← ProcChance
    helm = ' '.join(legendary_lines(gd, 'DivineHelm3'))          # 类模板 + 倍率字段（1.2 → 20%）
    summon = ' '.join(legendary_lines(gd, 'LegendaryShoulder5'))  # {ability} ← SummoningAbility（AbilityData）
    unknown = legendary_lines(gd, '旧武器·双手剑')
    rep.add(sword == ['对易伤目标额外获得30%暴击几率。']
            and '30%' in neck and '20%' in helm and '40%' in helm
            and '灵体分身' in summon and '25%' in summon and unknown == [],
            '传奇词条文案（整件 Desc / 前缀匹配 / 类模板 / 跨表技能名 + 令牌填值；未知装备返回空）',
            f'剑={sword}；项链含30%={"30%" in neck}；头盔含20%/40%={"20%" in helm and "40%" in helm}；'
            f'肩甲={summon}；未知={unknown}')

    # 全量回归网：某件装备的模板冒出数据源之外的令牌时只有这里会红——单样例断言覆盖不到
    gaps, total = [], 0
    for name, rec in gd.items().items():
        if not rec.get('EquipmentEffects'):
            continue
        total += 1
        text = ' '.join(legendary_lines(gd, name))
        if not text or '{' in text:
            gaps.append(f'{name}（{text or "空"}）')
    rep.add(total >= 67 and not gaps,
            '传奇词条全量填值（带特效装备全部有文案且无残留令牌）',
            f'{total} 件，缺口 {len(gaps)} 件：{"；".join(gaps[:3]) or "无"}')
