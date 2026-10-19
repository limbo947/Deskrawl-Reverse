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


def _table_path(dir_key: str, filename: str) -> str:
    """data/loc/<filename> 的绝对路径（相对 so_dump 目录）；dir_key 为空时返回空串。"""
    return os.path.normpath(os.path.join(dir_key, '..', 'loc', filename)) if dir_key else ''


def _table(gd, filename: str) -> dict:
    """定位并懒加载 data/loc/<filename>（相对 gd.dir）；缺表返回 {}，由调用方回落原名。"""
    return _load(_table_path(getattr(gd, 'dir', ''), filename))


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


def equipments_text(gd) -> dict:
    """Equipments 表全文（名字之外还含 `*.Desc` 传奇词条描述），供 legendary.py 查询。

    单独开口而不是让调用方用 `_table`：描述文案与显示名同表，但用途完全不同，留一个
    公开入口便于将来换表（如换成独立的效果文案表）时只改这里。
    """
    return _table(gd, 'equipments_zh.json')


# 四类装配件的显示名表：宝石/符文/套装都在 Equipments 表，天赋单独在 Talents 表
# （2026-10-17 实测：Equipments 命中 gem 36/36、rune 199/199、runeset 13/13，talent 0/186；
# Talents 表导出 356 条后天赋覆盖 186/186）
_ASSEMBLY_TABLES = {'gem': 'equipments_zh.json', 'rune': 'equipments_zh.json',
                    'runeset': 'equipments_zh.json', 'talent': 'talents_zh.json'}


def assembly_display_name(gd, kind: str, name: str) -> str:
    """装配件内部名（GemDiamond5 / HunterSetRune1_1 / HunterTalent19）→ 游戏简中名。

    缺表/缺键回落内部名：与装备本地化同取向，只降级显示，不阻断排序与计算。
    """
    table = _ASSEMBLY_TABLES.get(str(kind))
    if not table:
        return str(name)
    return _table(gd, table).get(str(name)) or str(name)


@lru_cache(maxsize=4)
def _reverse_names(dir_key: str, items_sig: int) -> dict:
    """{简中显示名: 内部 _name}，由 ItemData 逐条正推显示名后倒排。

    为什么不直接倒排本地化表：表里混有 `Xxx.Desc` 等非物品键，且 4 组描述文本重名；
    以 ItemData 为准倒排可保证「装备 → 内部名」全覆盖，且没有描述键污染。
    items_sig 是条目数签名——它变说明 so_dump 换了，缓存自然失效。
    """
    import json as _json
    try:
        with open(os.path.join(dir_key, 'ItemData.json'), encoding='utf-8') as f:
            rows = _json.load(f)
    except (OSError, ValueError):
        return {}
    table = _load(_table_path(dir_key, 'equipments_zh.json'))
    rev = {}
    for r in rows:
        nm = r.get('_name')
        if nm:
            rev.setdefault(table.get(nm, nm), str(nm))
    return rev


def item_internal_name(gd, display_name: str) -> str:
    """装备简中显示名 → ItemData 内部 _name；查不到时原样返回（按内部名或手工名回落）。

    传奇特效按 ItemData 的 `EquipmentEffects` 引用解析，而 profile 冻结的是简中名——
    故计算链取特效前需要这一次反查。回落而非抛错：手工输入的装备名本就不在表内。
    """
    name = str(display_name or '')
    if not name:
        return name
    d = os.path.normpath(str(getattr(gd, 'dir', '') or ''))
    if not d:
        return name
    try:
        sig = len(gd.items())
    except (OSError, ValueError, TypeError):
        return name
    return _reverse_names(d, sig).get(name, name)


__all__ = ['ability_display_name', 'assembly_display_name', 'equipment_display_name',
           'item_internal_name']
