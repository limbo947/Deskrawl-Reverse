# -*- coding: utf-8 -*-
"""职业清单与显示名（数据派生）。

为什么从 HeroData 取：职业枚举写死在 widget 里时，游戏补丁新增/调整职业不会体现在下拉与
侧栏摘要里；Class 与 _name 都在 HeroData.json，派生一次即可（中文名缺失回落内部名）。
"""
from __future__ import annotations

from typing import List

# 中文名是本地化表未覆盖的部分，这里只做「已知职业」的友好名；未知职业回落内部名而非隐藏
_HERO_CLASS_CN = {1: '野蛮人', 2: '法师', 4: '猎人', 8: '武僧'}


def hero_class_options(gd) -> List[tuple]:
    """[(Class, 显示名), ...] 按 Class 升序；HeroData 不可用时回落内置四职业。"""
    out = []
    try:
        for h in (gd.heroes() or {}).values():
            cls = h.get('Class')
            if cls is None:
                continue
            cls = int(cls)
            name = str(h.get('_name') or f'Class{cls}')
            out.append((cls, _HERO_CLASS_CN.get(cls, name)))
    except (OSError, ValueError, TypeError, AttributeError):
        out = []
    if not out:
        out = sorted(_HERO_CLASS_CN.items())
    return sorted(out, key=lambda x: x[0])


def hero_class_label(gd, hero_class) -> str:
    """职业显示名（未设置/未知回落「未设职业」）。"""
    if hero_class is None:
        return '未设职业'
    for cls, label in hero_class_options(gd):
        if cls == int(hero_class):
            return label
    return '未设职业'
