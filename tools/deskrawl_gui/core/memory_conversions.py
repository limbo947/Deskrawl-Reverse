# -*- coding: utf-8 -*-
"""属性换算（`StatConversion`）的两条读取链：装备/符文注册表 + 天赋特效。

为什么单独成文件：`memory_import.py` 已越过 700 行阈值（只降不升），而这两条链只依赖
(进程读取器, IL2CPP 读取器, 偏移段) 三个输入、与快照构建的其余状态无关——整体搬出后
`memory_import` 只留两行委托，后续再加换算相关读取也不必再动快照编排。

换算为什么只能从内存/天赋点取：`Player.PanelStat`(0x503350) 在**读取时**调 `Player.ffq`(0x5054B0)
把 `+0x318`（装备侧）/`+0x350`（天赋侧）两表求和后加进平坦层，全程不写回聚合字典 →
面板复算与 DPS 装配都必须自己补这一层，静态表里也只有模板、没有「当前角色实际生效了几条」。
"""
from __future__ import annotations

import struct

from .memory_reader import MemoryReadError, offset, valid_ptr


def read_registered(pr, il, cfg, player, warn) -> list:
    """读已注册的换算（`player_conversions`：装备侧 `odd`@0x318 / 天赋侧 `odl`@0x350）。

    元素是内联 ValueTuple<StatType, StatType, double, StatusEffectData>（stride 0x18），
    不是对象指针数组 → 按首地址 + i*stride 直读；`StatusEffectData*` 非空表示需带该状态才生效。
    """
    if not cfg:
        return []
    stride = offset(cfg['stride'])
    out = []
    for key in ('odd', 'odl'):
        try:
            first, n = il.list_items(pr.u64(player + offset(cfg[key])))
        except MemoryReadError as e:
            warn(f'属性换算表 {key} 不可用：{e}')
            continue
        for i in range(n):
            p = first + i * stride
            src = pr.i32(p + offset(cfg['source']))
            tgt = pr.i32(p + offset(cfg['target']))
            raw = pr.read(p + offset(cfg['fraction']), 8)
            if src is None or tgt is None or not raw or len(raw) != 8:
                continue
            st = pr.u64(p + offset(cfg['status']))
            out.append({'source': int(src), 'target': int(tgt),
                        'fraction': struct.unpack('<d', raw)[0],
                        'status': int(st) if valid_ptr(st) else 0})
    return out


def read_talent(objs, pr, codec, cfg, klass_name) -> list:
    """读天赋侧换算模板（`TalentEffect_StatConversion`；`objs` = 已点天赋的 (特效对象, 点数)）。

    取值 = `Base + (点数-1)×PerLevel`（LeveledFloat 语义）。`klass_name(obj)` 由调用方提供，
    避免本模块反向依赖 ILCPP 读取器；`RequiredStatus` 非空（如 `SorcererTalent33` 需冰封）
    原样输出，由 profile 侧决定去留——静态工具没有自身状态流。
    """
    if not cfg:
        return []
    stride = offset(cfg['per_level_stride'])
    voff = offset(cfg['fraction'])
    out = []
    for obj, pts in objs:
        if klass_name(obj) != cfg['klass']:
            continue
        base = codec.obsc_float(obj + voff)
        per = codec.obsc_float(obj + voff + stride)
        if base is None or per is None:
            continue
        st = pr.u64(obj + offset(cfg['status']))
        out.append({'source': pr.i32(obj + offset(cfg['source'])),
                    'target': pr.i32(obj + offset(cfg['target'])),
                    'status': int(st) if valid_ptr(st) else 0,
                    'base': float(base), 'per': float(per),
                    'value': float(base) + (pts - 1) * float(per)})
    return out
