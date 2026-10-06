# -*- coding: utf-8 -*-
"""`python -m deskrawl_gui` 入口：派发 GUI / --smoke / --selftest 三种模式。

三模式互斥且职责单一：--selftest 纯数值（不建 QApplication，headless 友好），
--smoke 建窗口后立即计数退出（无事件循环），默认进 GUI。
"""
import sys


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if '--selftest' in argv:
        from .selftest import run_selftest
        return run_selftest()
    if '--smoke' in argv:
        from .selftest import run_smoke
        return run_smoke()
    from .app import run_gui
    return run_gui()


if __name__ == '__main__':
    raise SystemExit(main())
