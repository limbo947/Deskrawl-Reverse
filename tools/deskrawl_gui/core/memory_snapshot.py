# -*- coding: utf-8 -*-
"""快照配套：偏移表加载 / 快照成品与指纹 / P2 版本指纹校验（自 memory_import.py 拆出）。

拆分动机：memory_import.py 已 460+ 有效行，本张书还要为错误态加「错误码」与权限包装；
把与「读取通道」无关的偏移表加载、快照数据类、指纹与版本校验独立出来，行数留余量。

指纹校验的动机（P2）：游戏更新会同时移动偏移与静态数据（so_dump）。宁可明确拒绝导入并
提示重新导出 schema/so_dump，也绝不给出「像模像样的脏数据」——指纹就是这条红线的哨兵。
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import List

_HERE = os.path.dirname(os.path.abspath(__file__))
_OFFSETS_PATH = os.path.join(_HERE, 'memory_offsets.json')
_REPO_ROOT = os.path.normpath(os.path.join(_HERE, '..', '..', '..'))


def _hexify(node):
    """offsets.json 递归转 int（"0x.." → int；其余原样），代码侧免写 offset() 噪音。"""
    if isinstance(node, dict):
        return {k: _hexify(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_hexify(v) for v in node]
    if isinstance(node, str) and node.startswith('0x'):
        return int(node, 16)
    return node


def load_offsets(path=None) -> dict:
    with open(path or _OFFSETS_PATH, encoding='utf-8') as f:
        return _hexify(json.load(f))


@dataclass
class SnapshotResult:
    """一次导入的成品：payload 为可 JSON 化的快照（§3.1 数据模型）。"""

    time: str
    pid: int
    mode: str                    # 'beta'（含装备逐件明细） | 'alpha'（仅字典/物品）
    town_mode: bool
    warnings: List[str] = field(default_factory=list)
    payload: dict = field(default_factory=dict)


def _section_diff(a: dict, b: dict) -> List[str]:
    """双读各段逐值比较；返回不一致的段名列表（用于重试记录/报错文案）。"""
    return [k for k in ('level', 'fields', 'dicts', 'inventory', 'storage',
                        'equipment', 'hero', 'town', 'hero_abilities',
                        'talent_ability_mods', 'talent_crit_effects', 'talent_bonus_effects',
                        'talent_stat_mods', 'talent_stat_conversions', 'paragon', 'runes')
               if a[k] != b[k]]


def _fingerprints(payload: dict) -> dict:
    """逐值指纹：字典段（键序归一）与物品 UID 段（保持数组序）。
    供 CLI/GUI 快速判定「两次快照是否逐值相等」，比整段 diff 更适合日志。"""

    def h(obj):
        raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=repr)
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]

    dicts = {lb: [[k, v] for k, v in sorted(kv.items())] for lb, kv in payload['dicts'].items()}
    uids = {'inventory': [it['uid'] for it in payload['inventory']],
            'storage': [it['uid'] for it in payload['storage']],
            'equipment': [s['uid'] for s in (payload['equipment'] or [])]}
    return {'dicts': h(dicts), 'uids': h(uids)}


def sha256_file(path: str) -> str:
    """流式摘要（GameAssembly.dll 60MB+，避免整读进内存）。"""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def check_fingerprints(off=None) -> List[str]:
    """校验 GameAssembly.dll / global-metadata.dat / so_dump 条目数与表内记录是否一致。

    返回中文问题列表（空=通过）。游戏目录默认取 offsets 的 game_dir，可用环境变量
    DESKRAWL_GAME 覆盖（与 tools/scripts/paths.py 同一约定；GUI 包不 import 逆向脚本）。
    """
    off = off or load_offsets()
    fp = off.get('fingerprints') or {}
    game_dir = os.environ.get('DESKRAWL_GAME') or fp.get('game_dir') or ''
    problems = []
    for label, path, want in (
            ('GameAssembly.dll', os.path.join(game_dir, 'GameAssembly.dll'),
             fp.get('game_assembly_sha256')),
            ('global-metadata.dat',
             os.path.join(game_dir, 'Deskrawl_Data', 'il2cpp_data', 'Metadata',
                          'global-metadata.dat'),
             fp.get('global_metadata_sha256'))):
        if not want:
            problems.append(f'{label} 校验记录缺失（memory_offsets.json 未写入指纹）')
        elif not os.path.exists(path):
            problems.append(f'{label} 不存在：{path}')
        elif sha256_file(path) != want:
            problems.append(f'{label} 指纹不符（游戏已更新？）')
    want_n = fp.get('so_dump_itemdata_entries')
    itemdata = os.path.join(_REPO_ROOT, 'data', 'so_dump', 'ItemData.json')
    if want_n is None:
        problems.append('so_dump/ItemData.json 条目数记录缺失')
    elif not os.path.exists(itemdata):
        problems.append(f'so_dump/ItemData.json 不存在：{itemdata}')
    else:
        try:
            with open(itemdata, encoding='utf-8') as f:
                got_n = len(json.load(f))
        except (OSError, ValueError) as e:
            problems.append(f'so_dump/ItemData.json 解析失败：{e}')
        else:
            if got_n != int(want_n):
                problems.append(f'so_dump/ItemData.json 条目数不符（记录 {want_n}，实测 {got_n}）')
    return problems