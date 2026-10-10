# -*- coding: utf-8 -*-
"""显示名本地化：把 AbilityData 的混淆 _name 映射为游戏简中名。

数据来自 tools/scripts/extract_localization.py 导出的 data/loc/abilities_zh.json
（Unity Localization 表的 Chinese (Simplified) 列，Key=AbilityData._name）。
GUI 层不引入内核依赖：与 calc_service.ability_names 同样从 gd.dir 相对定位，只读。
"""
from __future__ import annotations

import json
import os
from functools import lru_cache


@lru_cache(maxsize=4)
def _load(path: str) -> dict:
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def ability_display_name(gd, name: str) -> str:
    """技能 _name → 简中名；表缺失或键不存在时回落英文名（AbilityName → _name）。

    回落而不是抛错：本地化表属于「锦上添花」，缺表只应降级显示，不应阻断计算链。
    """
    path = os.path.join(getattr(gd, 'dir', ''), '..', 'loc', 'abilities_zh.json')
    zh = _load(os.path.normpath(path)).get(name)
    if zh:
        return zh
    return str(name)


__all__ = ['ability_display_name']
