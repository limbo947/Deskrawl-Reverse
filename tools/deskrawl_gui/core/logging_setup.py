# -*- coding: utf-8 -*-
"""未捕获异常的落盘与一次性提示。

为什么需要：便携版是 windowed exe，没有控制台；槽函数里抛出的异常若只走默认 excepthook，
traceback 会写向不存在的 stderr 后消失，用户只能看到「点了没反应」，反馈里没有任何可复盘的
信息。本模块保持 Qt-free（core 约定）：提示框由调用方以回调注入，CLI/自检不传即只落盘。
"""
from __future__ import annotations

import datetime
import faulthandler
import os
import sys
import threading
import traceback

from . import data_dir

_fatal_file = None               # faulthandler 要求句柄活到进程结束，必须留引用
_state = {'path': '', 'notify': None}
_installed = False
_notified = False


def log_dir() -> str:
    """日志目录：用户级应用目录下的 `logs`（与哈希缓存同一父目录，见 core/data_dir）。"""
    return os.path.join(data_dir.appdata_dir(), 'logs')


def log_path() -> str:
    return os.path.join(log_dir(), f'app-{datetime.date.today():%Y%m%d}.log')


def append(text: str, path: str = None) -> str:
    """追加一段文本并返回实际路径；写不进去就静默跳过——记日志失败不能把原异常再炸一次。"""
    path = path or _state['path'] or log_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'a', encoding='utf-8') as f:
            f.write(text if text.endswith('\n') else text + '\n')
    except OSError:
        pass
    return path


def install(path: str = None, notify=None) -> str:
    """装 excepthook（主线程 + 子线程）与 faulthandler，返回日志路径。

    Ctrl+C 与 SystemExit 交回默认处理：正常退出不该被记成崩溃。重复调用只更新路径与回调、
    不叠 hook——自检/冒烟会多次建窗口，重复包装会把同一条异常写两遍，排障时看不出真实次数。
    path 显式传入时（自检的临时文件）跳过 faulthandler：那是进程级开关，不该被测试改动。
    """
    global _installed
    explicit = path is not None
    _state['path'] = path or log_path()
    if notify is not None:
        _state['notify'] = notify
    if not _installed:
        sys.excepthook = _hook
        threading.excepthook = _thread_hook
        if not explicit:
            _enable_faulthandler()
        _installed = True
    append(f'===== {datetime.datetime.now():%Y-%m-%d %H:%M:%S} 启动 =====')
    return _state['path']


def uninstall() -> None:
    """还原 hook（自检用：不留全局副作用）。"""
    global _installed
    if not _installed:
        return
    sys.excepthook = sys.__excepthook__
    threading.excepthook = threading.__excepthook__
    _installed = False


def _hook(exc_type, exc, tb):
    if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
        sys.__excepthook__(exc_type, exc, tb)
        return
    append(''.join(traceback.format_exception(exc_type, exc, tb)))
    _show_once(exc)


def _thread_hook(args):
    if args.exc_type in (SystemExit, KeyboardInterrupt):
        return
    append(''.join(traceback.format_exception(args.exc_type, args.exc_value,
                                              args.exc_traceback)))
    _show_once(args.exc_value)


def _show_once(exc) -> None:
    """只在有 GUI 时提示一次：无 QApplication 的环境（自检/CLI）静默落盘即可。"""
    global _notified
    notify = _state['notify']
    if notify is None or _notified:
        return
    _notified = True
    try:
        notify(_state['path'], exc)
    except Exception:            # noqa: BLE001 —— 提示失败不能盖住原异常
        pass


def _enable_faulthandler() -> None:
    """原生崩溃（如 Qt 静态析构 abort）也留一份栈：这种情形下 Python 的 hook 根本不会触发。"""
    global _fatal_file
    try:
        _fatal_file = open(_state['path'] + '.fatal', 'a', encoding='utf-8')
        faulthandler.enable(_fatal_file, all_threads=True)
    except (OSError, AttributeError, ValueError):
        _fatal_file = None
