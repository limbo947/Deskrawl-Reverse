# -*- coding: utf-8 -*-
"""显示名本地化：把 AbilityData / ItemData 的混淆 _name 映射为游戏简中名。

数据来自 tools/scripts/extract_localization.py 导出的 data/loc/*.json
（Unity Localization 表 Abilities / Equipments 的 Chinese (Simplified) 列）。
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


def _table(gd, filename: str) -> dict:
    """定位并懒加载 data/loc/<filename>（相对 gd.dir）；缺表返回 {}，由调用方回落原名。"""
    path = os.path.normpath(os.path.join(getattr(gd, 'dir', ''), '..', 'loc', filename))
    return _load(path)


def ability_display_name(gd, name: str) -> str:
    """技能 _name → 简中名；表缺失或键不存在时回落英文名（AbilityName → _name）。

    回落而不是抛错：本地化表属于「锦上添花」，缺表只应降级显示，不应阻断计算链。
    """
    zh = _table(gd, 'abilities_zh.json').get(name)
    return zh or str(name)


def equipment_display_name(gd, name: str) -> str:
    """装备 _name（ItemData 内部名如 LegendarySword1）→ 游戏简中名。

    数据源为 Equipments 表（2026-10-11 导出 566 条，可穿戴 209 件 100% 覆盖；宝箱等
    非装备条目按内部名回落）。导入链冻结 profile 时即本地化，GUI 全程只见中文名。
    """
    zh = _table(gd, 'equipments_zh.json').get(str(name))
    return zh or str(name)


__all__ = ['ability_display_name', 'equipment_display_name']
