# -*- coding: utf-8 -*-
"""GUI 会话状态：窗口几何/当前页 + 完整工作 profile 的落盘与恢复。

为什么单独落盘而不是复用 data/builds：会话文件是「上次关闭时的完整工作态」（含内存导入
冻结的 bag_items/panel），既不该出现在「加载构建」列表里，也不该进 git（.gitignore 排除）。
读写全容错：损坏/版本不符一律回落空状态（启动不阻断），下次正常关闭即自愈覆盖。
本模块保持 Qt-free（core 约定）：几何的 base64 编码由调用方（app.py）完成。
"""
from __future__ import annotations

import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.normpath(os.path.join(_HERE, '..', '..', '..', 'data', 'session_state.json'))
STATE_VERSION = 1


def load_state(path: str = None) -> dict:
    """读取会话状态；文件缺失/损坏/版本不符 → {}（调用方回落默认，不抛错）。"""
    path = path or STATE_PATH
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict) or int(data.get('version') or 0) != STATE_VERSION:
            return {}
    except (OSError, ValueError, TypeError):
        return {}
    return data


def save_state(payload: dict, path: str = None) -> str:
    """原子写（临时文件 + os.replace）：写到一半被打断也不会把好状态截成半个 JSON。"""
    path = path or STATE_PATH
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return path