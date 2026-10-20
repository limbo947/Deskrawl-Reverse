# -*- coding: utf-8 -*-
"""`python -m deskrawl_gui` 入口：派发 GUI / --smoke / --selftest 三种模式。

三模式互斥且职责单一：--selftest 纯数值（不建 QApplication，headless 友好），
--smoke 建窗口后立即计数退出（无事件循环），默认进 GUI。
两种检查模式都支持按组运行（E3）：`--selftest import panel`、`--smoke behavior`；
不带组名即全跑——CI 与打包门禁走的正是这条，行为与拆分前一致。
"""
import sys


def _harden_output() -> None:
    """把「写不进去」的 stdout/stderr 换成 UTF-8 或哑流。

    窗模式冻结包（console=False）里 stdout 可能是 None 或无效句柄：任何 print 都会抛
    `OSError: [Errno 22] Invalid argument`，于是 `--selftest` 变成「Unhandled exception」
    崩溃对话框——v1.0.0 的 Release 门禁就是栽在 selftest 打印内核自检那一段。
    顺序：先试 UTF-8 + errors=replace（管道/重定向场景保住日志），仍不可写就换成丢弃输出的
    StringIO——自检的结论看退出码，不该被「终端不存在」绑架。
    """
    import io
    for name in ('stdout', 'stderr'):
        stream = getattr(sys, name, None)
        if stream is None:
            setattr(sys, name, io.StringIO())
            continue
        try:
            stream.write('')
            stream.flush()
            continue
        except (OSError, ValueError):
            pass
        fixed = False
        # UTF-8 优先：CI 日志按 UTF-8 渲染，换成 cp1252+replace 会把中文全变成 '?'
        for kwargs in ({'encoding': 'utf-8', 'errors': 'replace'}, {'errors': 'replace'}):
            try:
                stream.reconfigure(**kwargs)
                stream.write('')
                stream.flush()
                fixed = True
                break
            except (OSError, ValueError, AttributeError):
                continue
        if not fixed:
            setattr(sys, name, io.StringIO())


def _group_args(argv, flag: str) -> list:
    """取 flag 之后的组名（到下一个 `-` 开头的参数或结尾为止）。"""
    i = argv.index(flag)
    out = []
    for a in argv[i + 1:]:
        if a.startswith('-'):
            break
        out.append(a)
    return out


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    _harden_output()      # 冻结包无终端时先兜住 stdout，否则第一句 print 就崩
    if '--selftest' in argv:
        from .selftest import run_selftest
        code = run_selftest(_group_args(argv, '--selftest'))
    elif '--smoke' in argv:
        from .selftest import run_smoke
        code = run_smoke(_group_args(argv, '--smoke'))
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
