# -*- coding: utf-8 -*-
"""快照硬校验：结构 / 键域 / 值域 / UID 唯一性（宁红不脏的第二道闸）。

自 memory_import.py 拆出（原文件 749 有效行，已过 700 拆分行阈值）。拆出理由：校验是
**纯 payload 函数**——只读快照字典与偏移表，不碰进程内存，与定位链、读取链无共享状态；
独立成文件后可以直接用构造的 payload 单测它，而不必先连上游戏。
"""
from __future__ import annotations

import math

from .memory_errors import MemoryImportError
from .memory_reader import valid_ptr

# 合法英雄职业：1=野蛮人 / 2=法师 / 4=猎人 / 8=武僧（HeroData.Class 枚举值）
_HERO_CLASSES = (1, 2, 4, 8)


def _talent_mod_row_ok(row) -> bool:
    """天赋「按技能修正」行：3 元 = `[stat, ability_ptr, val]`，4 元 = `[stat, 0, val, tag]`。

    Tag 型是 2026-10-19 补的：天赋数据 54 条里 26 条按 AbilityTag 命中（Ability 为空），
    只认指针型会把一半的伤害/暴击/冷却类天赋判成脏数据而拒绝导入。
    """
    try:
        if not isinstance(row, (list, tuple)) or len(row) not in (3, 4):
            return False
        val = float(row[2])
        if not math.isfinite(val) or abs(val) > 1e6:
            return False
        if len(row) == 3:
            return bool(valid_ptr(row[1]))
        return int(row[1]) == 0 and 0 <= int(row[3]) < 9999
    except (TypeError, ValueError):
        return False


def _talent_crit_row_ok(rec) -> bool:
    """天赋条件暴击行：类名白名单 + 条件枚举 + 有限 Base/Per + 指针域。

    状态/技能在内存里只有指针（0 = 无），名字由 profile 按指纹反查静态表——
    这里只保证读到的东西不是垃圾（撕裂读/结构漂移）。
    """
    try:
        if not isinstance(rec, dict) or rec.get('klass') not in (
                'TalentEffect_ConditionalCritChance', 'TalentEffect_ConditionalCritDamage'):
            return False
        if int(rec.get('condition', -99)) not in (-1, 0, 1, 2, 3, 4, 5, 6):
            return False
        for k in ('base', 'per', 'value'):
            v = float(rec[k])
            if not math.isfinite(v) or abs(v) > 1e3:
                return False
        for k in ('status', 'ability'):
            if k in rec and int(rec[k]) < 0:
                return False
        if 'tag' in rec and not -1 <= int(rec['tag']) <= 9999:
            return False
        return True
    except (KeyError, TypeError, ValueError):
        return False


def _talent_bonus_row_ok(rec) -> bool:
    """天赋条件加伤行：指针域 + bool + 有限数值（状态名由 profile 指纹反查，这里只挡垃圾）。"""
    try:
        if not isinstance(rec, dict) or not isinstance(rec.get('self'), bool):
            return False
        for k in ('status', 'ability'):
            if int(rec[k]) < 0:
                return False
        if not -1 <= int(rec['tag']) <= 9999:
            return False
        for k in ('base', 'per', 'value'):
            v = float(rec[k])
            if not math.isfinite(v) or abs(v) > 1e3:
                return False
        return True
    except (KeyError, TypeError, ValueError):
        return False


def validate_snapshot(payload: dict, off: dict):
    """硬校验（宁红不脏）：等级/字段/字典键域值域/UID 唯一性；任一失败抛 MemoryImportError。

    顺带把「哪个字典是最终聚合字典」写回 payload['final_dict']（取 7 号键最大者——
    最大生命只有在最终聚合层才是完整值），后续面板口径复算据此取基座。
    """
    lo, hi = off['player_level_range']
    lvl = payload['level']
    if not isinstance(lvl, int) or not lo <= lvl <= hi:
        raise MemoryImportError(f'等级值域异常：{lvl}（应为 [{lo},{hi}] 内整数）')
    hp = payload['fields']['BaseMaxHealth']
    if not isinstance(hp, int) or not 1 <= hp <= 10 ** 9:
        raise MemoryImportError(f'BaseMaxHealth 值域异常：{hp}')
    crit = payload['fields']['BaseCritChance']
    if crit is None or not 0.0 <= crit <= 1.0:
        raise MemoryImportError(f'BaseCritChance 值域异常：{crit}')
    klo, khi = off['stat_key_range']
    for label, kv in payload['dicts'].items():
        for k, v in kv.items():
            if not klo <= k <= khi:
                raise MemoryImportError(f'字典 {label} 出现非法键 {k}（解码/结构异常）')
            if v is None or not math.isfinite(v) or abs(v) > 1e9:
                raise MemoryImportError(f'字典 {label}[{k}] 值域异常：{v}（解码/撕裂读）')
    hp_cands = [(lb, kv[7]) for lb, kv in payload['dicts'].items() if 7 in kv]
    if not hp_cands:
        raise MemoryImportError('7 个聚合字典中均无最大生命键（结构漂移？）')
    fin_lb, fin_hp = max(hp_cands, key=lambda t: t[1])
    payload['final_dict'] = fin_lb
    if fin_hp < hp:
        raise MemoryImportError(f'聚合生命 {fin_lb}={fin_hp} < 基础生命 {hp}（解码异常）')
    fin = payload['dicts'][fin_lb]
    if 4 in fin and not 0.0 <= fin[4] <= 1.0:
        raise MemoryImportError(f'{fin_lb} 暴击率值域异常：{fin[4]}')
    if 0 in fin and not fin[0] > 0:
        raise MemoryImportError(f'{fin_lb} 力量值域异常：{fin[0]}')
    cds = payload['fields'].get('BaseCritDamage')
    if cds is None or not 0.0 <= cds <= 100.0:
        raise MemoryImportError(f'BaseCritDamage 值域异常：{cds}')
    hp_cur = payload['fields'].get('CurrentHealth')
    if not isinstance(hp_cur, int) or not 0 <= hp_cur <= 10 ** 9:
        raise MemoryImportError(f'CurrentHealth 值域异常：{hp_cur}')
    ps = payload.get('primary_stat')
    if ps is not None and ps not in (0, 1, 2):
        raise MemoryImportError(f'primary_stat 值域异常：{ps}')
    hc = payload.get('hero_class')
    if hc is not None and hc not in _HERO_CLASSES:
        raise MemoryImportError(f'hero_class 值域异常：{hc}')
    for k, v in (payload.get('paragon') or {}).items():
        if not klo <= k <= khi or not isinstance(v, int) or not 0 < v <= 999:
            raise MemoryImportError(f'巅峰分配条目异常：{k}={v}')
    for r in payload.get('runes') or []:
        if not isinstance(r.get('name'), str) or not r['name'] \
                or not 0 <= int(r.get('level') or 0) <= 6:
            raise MemoryImportError(f'符文槽条目异常：{r}')
    for row in payload.get('talent_ability_mods') or []:
        if not _talent_mod_row_ok(row):
            raise MemoryImportError(f'技能天赋修正条目异常：{row}')
    for rec in payload.get('talent_crit_effects') or []:
        if not _talent_crit_row_ok(rec):
            raise MemoryImportError(f'天赋条件暴击条目异常：{rec}')
    for rec in payload.get('talent_bonus_effects') or []:
        if not _talent_bonus_row_ok(rec):
            raise MemoryImportError(f'天赋条件加伤条目异常：{rec}')
    for label, rows in payload.get('conditionals', {}).items():
        for r in rows:
            if (r[0] not in (-1, 0, 1, 2, 3, 4, 5) or not klo <= r[2] <= khi
                    or r[3] not in (0, 1, 2) or not math.isfinite(r[4])
                    or abs(r[4]) > 1e9):
                raise MemoryImportError(f'{label} 条件属性表条目异常：{r}')
    for label, kv in payload.get('status_mods', {}).items():
        for k, v in kv.items():
            if not klo <= k <= khi or v is None or not math.isfinite(v) or abs(v) > 1e9:
                raise MemoryImportError(f'status_mods.{label}[{k}] 值域异常：{v}')
    for name in ('inventory', 'storage'):
        uids = [it['uid'] for it in payload[name] if it['uid']]
        if len(set(uids)) != len(uids):
            raise MemoryImportError(f'{name} 出现重复 UID（撕裂读？）')
    if payload['equipment'] is not None:
        uids = [s['uid'] for s in payload['equipment']]
        if len(set(uids)) != len(uids):
            raise MemoryImportError('装备出现重复 UID')
