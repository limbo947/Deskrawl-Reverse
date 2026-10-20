# -*- coding: utf-8 -*-
"""构建库（A6）：扫构建目录，把每份 JSON 的元信息（名称/等级/职业/DPS/备注）整理成列表。

此前只有「保存/加载」两个文件对话框：文件名成了唯一线索，多套方案只能靠记忆辨认。
这里不改存储格式（仍是 data/builds/*.json），只把「目录里有什么」变成可读的一屏。

单个文件损坏不得让整库打不开：该条记 error 照常列出（用户在列表里看到「（损坏）」，
而不是整页空着还以为文件没了）。
"""
import os
from dataclasses import dataclass
from typing import List, Optional

from .heroes import hero_class_label
from .profile import BUILDS_DIR, load_build

# 超过这个数量就不再算 DPS：每份要重建属性表（约 1ms），几十份就够让对话框开得发涩
DPS_LIMIT = 40


@dataclass
class BuildEntry:
    path: str
    name: str = ''
    level: int = 0
    hero_class_cn: str = ''
    assembled: int = 0
    note: str = ''
    mtime: float = 0.0
    dps: Optional[float] = None
    error: str = ''

    @property
    def filename(self) -> str:
        return os.path.basename(self.path)


def scan_builds(gd=None, dir_path: str = '', *, with_dps: bool = True) -> List[BuildEntry]:
    """列出目录内全部构建（按修改时间降序）。dir_path 空则用仓库/便携版的构建目录。"""
    folder = dir_path or BUILDS_DIR
    if not os.path.isdir(folder):
        return []
    names = sorted((n for n in os.listdir(folder) if n.lower().endswith('.json')),
                   key=lambda n: -_mtime(os.path.join(folder, n)))
    from .calc_service import baseline_dps

    out: List[BuildEntry] = []
    for name in names:
        path = os.path.join(folder, name)
        entry = BuildEntry(path=path, mtime=_mtime(path))
        try:
            prof = load_build(path)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            entry.name = os.path.splitext(name)[0]
            entry.error = f'{type(exc).__name__}: {exc}'
            out.append(entry)
            continue
        entry.name = prof.name or os.path.splitext(name)[0]
        entry.level = int(prof.level)
        entry.hero_class_cn = hero_class_label(gd, prof.hero_class) if gd is not None else ''
        entry.assembled = len(prof.assembled)
        entry.note = str(getattr(prof, 'note', '') or '')
        if with_dps and gd is not None and len(out) < DPS_LIMIT:
            try:
                entry.dps = float(baseline_dps(prof, gd))
            except (KeyError, ValueError, TypeError, ZeroDivisionError):
                entry.dps = None
        out.append(entry)
    return out


def _mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def set_note(path: str, note: str) -> None:
    """改备注：读→改→原地写回（不碰数值字段，避免重排序列化顺序带来的整份 diff）。"""
    from .profile import save_build

    prof = load_build(path)
    prof.note = str(note or '')
    save_build(prof, path)


__all__ = ['BuildEntry', 'scan_builds', 'set_note', 'DPS_LIMIT']
