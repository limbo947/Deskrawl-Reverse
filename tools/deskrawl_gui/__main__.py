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
        code = run_selftest()
    elif '--smoke' in argv:
        from .selftest import run_smoke
        code = run_smoke()
    else:
        from .app import run_gui
        return run_gui()
    # 两个无事件循环的模式统一收尾：不先拆 Qt 就会在进程退出期偶发 abort（见 shutdown_application），
    # 于是「自检全绿但退出码非 0」——CI 门禁与本地验收都会被误判。
    from .app import shutdown_application
    shutdown_application()
    return code


if __name__ == '__main__':
    raise SystemExit(main())
