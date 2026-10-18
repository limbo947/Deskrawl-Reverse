# -*- coding: utf-8 -*-
"""可写数据根解析：源码运行时 = 仓库 data/；便携包落在只读目录时 = DESKRAWL_DATA_DIR 指向处。

为什么单独成文件：session_state 与 profile 各要一份，两处各写一遍迟早漂移。只读安装的动机：
便携包解压到 Program Files 后写盘必失败（app._save_build 的 makedirs 在 try 之外会抛穿），
启动器遂把可写目录导到环境变量里。本模块保持 Qt-free（core 约定）。
"""
from __future__ import annotations

import os

ENV_VAR = 'DESKRAWL_DATA_DIR'
_HERE = os.path.dirname(os.path.abspath(__file__))
_DEFAULT = os.path.normpath(os.path.join(_HERE, '..', '..', '..', 'data'))


def data_root() -> str:
    """环境变量优先，否则回落仓库 data/（与拆分前逐字同值）。"""
    return os.environ.get(ENV_VAR) or _DEFAULT
