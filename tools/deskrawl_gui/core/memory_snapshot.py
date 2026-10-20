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

from . import data_dir

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
                        'talent_stat_mods', 'talent_stat_conversions', 'conversions',
                        'paragon', 'runes')
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


# ---------------- 摘要/条目数缓存（启动期只算一次） ----------------
# 动机：check_fingerprints 在窗口显示前同步跑，实测 83.5ms（DLL 哈希 + metadata + ItemData 解析），
# 占 MainWindow 构造的 58%；而游戏文件不更新时这两份摘要完全不变。
# 失效判定用 (size, mtime_ns)：补丁替换文件必然改变其一；同尺寸同时间戳的替换不在支持范围内
# （要防这一点只能每次整文件重算，缓存就失去意义）——风险与收益在启动体验上明显偏向缓存。

def _cache_path() -> str:
    return os.path.join(data_dir.appdata_dir(), 'cache', 'sha256.json')


def _load_cache() -> dict:
    try:
        with open(_cache_path(), encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_cache(cache: dict) -> None:
    """原子写；失败静默——缓存只影响启动速度，不影响校验结论。"""
    path = _cache_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        pass


def _entry(path: str, cache: dict) -> dict:
    rec = cache.get(os.path.abspath(path))
    return dict(rec) if isinstance(rec, dict) else {}


def _fresh(rec: dict, st) -> bool:
    return rec.get('size') == st.st_size and rec.get('mtime') == st.st_mtime_ns


def cached_sha256(path: str, cache: dict) -> str:
    """带 (size, mtime) 缓存的 SHA-256；命中时不再读文件。"""
    st = os.stat(path)
    rec = _entry(path, cache)
    digest = rec.get('sha256')
    if _fresh(rec, st) and isinstance(digest, str) and len(digest) == 64:
        return digest
    digest = sha256_file(path)
    cache[os.path.abspath(path)] = dict(rec, size=st.st_size, mtime=st.st_mtime_ns,
                                        sha256=digest)
    return digest


def cached_json_count(path: str, cache: dict) -> int:
    """JSON 数组条目数的缓存版（ItemData.json 的 json.load 也占启动时间）。"""
    st = os.stat(path)
    rec = _entry(path, cache)
    count = rec.get('count')
    if _fresh(rec, st) and isinstance(count, int):
        return count
    with open(path, encoding='utf-8') as f:
        count = len(json.load(f))
    cache[os.path.abspath(path)] = dict(rec, size=st.st_size, mtime=st.st_mtime_ns,
                                        count=int(count))
    return int(count)


def check_fingerprints(off=None) -> List[str]:
    """校验 GameAssembly.dll / global-metadata.dat / so_dump 条目数与表内记录是否一致。

    返回中文问题列表（空=通过）。游戏目录默认取 offsets 的 game_dir，可用环境变量
    DESKRAWL_GAME 覆盖（与 tools/scripts/paths.py 同一约定；GUI 包不 import 逆向脚本）。
    """
    off = off or load_offsets()
    fp = off.get('fingerprints') or {}
    game_dir = os.environ.get('DESKRAWL_GAME') or fp.get('game_dir') or ''
    problems = []
    cache = _load_cache()          # 命中即跳过哈希/解析；失效由 (size, mtime_ns) 判定
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
        else:
            try:
                got = cached_sha256(path, cache)
            except OSError as exc:
                problems.append(f'{label} 无法读取：{exc}')
                continue
            if got != want:
                problems.append(f'{label} 指纹不符（游戏已更新？）')
    want_n = fp.get('so_dump_itemdata_entries')
    itemdata = os.path.join(_REPO_ROOT, 'data', 'so_dump', 'ItemData.json')
    if want_n is None:
        problems.append('so_dump/ItemData.json 条目数记录缺失')
    elif not os.path.exists(itemdata):
        problems.append(f'so_dump/ItemData.json 不存在：{itemdata}')
    else:
        try:
            got_n = cached_json_count(itemdata, cache)
        except (OSError, ValueError) as e:
            problems.append(f'so_dump/ItemData.json 解析失败：{e}')
        else:
            if got_n != int(want_n):
                problems.append(f'so_dump/ItemData.json 条目数不符（记录 {want_n}，实测 {got_n}）')
    _save_cache(cache)
    return problems