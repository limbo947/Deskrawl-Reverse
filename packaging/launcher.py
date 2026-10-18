# -*- coding: utf-8 -*-
"""PyInstaller 便携包入口：同一个 windowed exe 分派 GUI / --selftest / --smoke / memdump。

为什么不拆「GUI 版 + 控制台版」两个 exe：仓库既有 `python -m deskrawl_gui` 与
`python -m deskrawl_gui.memdump` 两条命令行语义要原样保留，而 GUI 用户不该看到黑框；
于是同一个 windowed exe 按参数决定要不要把标准流接回来。

接管方式：**无条件**用系统句柄重建 sys.stdout/stderr（行缓冲），不复用 PyInstaller 装的流。
实测教训：windowed 构建在句柄有效时会给出带 locale 编码（中文 Windows 上是 GBK）的流，
复用它打印 U+2212 之类字符会抛 UnicodeEncodeError 直接崩掉 --selftest；而重建成本极低。
"""
from __future__ import annotations

import os
import shutil
import sys

# 非 frozen（直接跑本文件）时补上 tools 目录，使 deskrawl_gui 可导入——便于不起包先验本模块逻辑
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools')))


def _dbg(msg: str) -> None:
    """诊断打点，只在 DESKRAWL_DEBUG_STREAMS=1 时输出（排查冻结态流/退出问题用，平时静默）。"""
    if os.environ.get('DESKRAWL_DEBUG_STREAMS') != '1':
        return
    try:
        sys.stderr.write(f'[launcher] {msg}\n')
        sys.stderr.flush()
    except Exception:
        pass


def _reopen(handle, enc):
    """Win32 句柄 → 行缓冲文本流。closefd=False 不能省：否则退出时会把父进程的控制台/管道句柄关掉。

    行缓冲（buffering=1）不是性能取舍而是正确性取舍：块缓冲下若进程在收尾阶段崩掉，
    最后几 KB（含「自检结果：全部通过」）永远不会落盘，验收时就变成「看不到结论」。
    """
    import msvcrt
    fd = msvcrt.open_osfhandle(handle, os.O_WRONLY)
    return os.fdopen(fd, 'w', encoding=enc, errors='replace', buffering=1, closefd=False)


def _kernel32():
    """取 kernel32 并显式声明签名：默认 restype=c_int 会把 64 位句柄截断。"""
    import ctypes
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.GetStdHandle.restype = ctypes.c_void_p
    k.GetStdHandle.argtypes = [ctypes.c_int]
    k.GetFileType.restype = ctypes.c_uint
    k.GetFileType.argtypes = [ctypes.c_void_p]
    k.AttachConsole.restype = ctypes.c_bool
    k.AttachConsole.argtypes = [ctypes.c_uint]
    k.AllocConsole.restype = ctypes.c_bool
    k.AllocConsole.argtypes = []
    k.SetConsoleOutputCP.restype = ctypes.c_bool
    k.SetConsoleOutputCP.argtypes = [ctypes.c_uint]
    k.GetConsoleOutputCP.restype = ctypes.c_uint
    k.GetConsoleOutputCP.argtypes = []
    k.GetConsoleMode.restype = ctypes.c_bool
    k.GetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
    return k


def _is_console(k, handle) -> bool:
    """是否真控制台：用 GetConsoleMode 而非 GetFileType 判定。

    实测教训：重定向/管道句柄也会被 GetFileType 判成 CHAR(1)，于是本该 utf-8 的 CI 日志被写成
    代码页字节（中文全乱码）。GetConsoleMode 只有控制台句柄才成功，是可靠判据。
    """
    import ctypes
    try:
        mode = ctypes.c_uint()
        return bool(k.GetConsoleMode(handle, ctypes.byref(mode)))
    except (AttributeError, OSError, ValueError):
        return False


def _console_encoding(k) -> str:
    """控制台按当前代码页解码我们写出的字节；硬写 utf-8 会让中文在 CP936 控制台上变乱码。"""
    cp = int(k.GetConsoleOutputCP())
    return 'utf-8' if cp == 65001 else ('gbk' if cp == 936 else 'mbcs')


def _restore_streams() -> bool:
    """重建标准流；返回 True = 控制台是本次自建的（退出前要暂停让用户读完）。

    三级阶梯按代价排：① 复用已继承的句柄（CI 的管道与 `> out.txt` 全靠它，AttachConsole 做不到）
    → ② 挂父进程控制台（交互式终端里跑本 exe）→ ③ 自建控制台（资源管理器双击）。
    只写 AllocConsole 会让 CI 一个字节都收不到，是最常见的坑。
    """
    if sys.platform != 'win32':
        return False
    k = _kernel32()
    out, err = k.GetStdHandle(-11), k.GetStdHandle(-12)   # STD_OUTPUT / STD_ERROR
    ft = int(k.GetFileType(out))                      # 1=CHAR(控制台) 2=PIPE 3=DISK 0=未知
    _dbg(f'rebuild: ft_out={ft} ft_err={int(k.GetFileType(err))}')
    if ft in (1, 2, 3):                               # ① 句柄本身可用，直接复用
        err_h = err if int(k.GetFileType(err)) in (1, 2, 3) else out
        sys.stdout = _reopen(out, _console_encoding(k) if _is_console(k, out) else 'utf-8')
        sys.stderr = _reopen(err_h, _console_encoding(k) if _is_console(k, err_h) else 'utf-8')
        _dbg(f'branch=inherited stdout_is_console={_is_console(k, out)}')
        return False
    own = not bool(k.AttachConsole(-1))               # -1 = ATTACH_PARENT_PROCESS
    if own:
        k.AllocConsole()
        k.SetConsoleOutputCP(65001)                   # 只动自建的控制台，不污染父进程
    enc = _console_encoding(k)
    # 已 AttachConsole 时 GetStdHandle 未必有效，按设备名打开最稳
    sys.stdout = open('CONOUT$', 'w', encoding=enc, errors='replace', buffering=1)
    sys.stderr = open('CONOUT$', 'w', encoding=enc, errors='replace', buffering=1)
    if own:
        try:
            sys.stdin = open('CONIN$', 'r', encoding=enc, errors='replace')
        except OSError:
            pass
    _dbg(f'branch=console-selfmade own={own} enc={enc}')
    return own


def _flush() -> None:
    """收尾前强制落盘：块缓冲 + 进程级异常会让最后几行结论凭空消失。"""
    for s in (sys.stdout, sys.stderr):
        try:
            s.flush()
        except (AttributeError, OSError, ValueError):
            pass


def _pause(own: bool) -> None:
    """自建控制台随进程退出一起消失（双击运行），停一下让用户读完自检结论。"""
    if not own or os.environ.get('DESKRAWL_NO_PAUSE') == '1':
        return
    try:
        sys.stdout.write('\n按 Enter 键退出…')
        sys.stdout.flush()
        input()
    except (EOFError, OSError, RuntimeError, ValueError):
        pass


def _env_var() -> str:
    """键名从 core/data_dir 导入，保持单一事实源（不在此重写常量，避免与 core 漂移）。"""
    from deskrawl_gui.core.data_dir import ENV_VAR
    return ENV_VAR


def _redirect_writable_data() -> None:
    """便携包落在只读目录（如 Program Files）时，把可写数据根指向 %LOCALAPPDATA%。

    判据不是「目录存在」而是「真能建文件」：Program Files 下的目录可读不可写，只有实写一次
    才分得清。源码运行（非 frozen）直接返回——不建探针、不改环境，行为逐字不变。必须在
    `import deskrawl_gui.app` 之前调用：session_state/profile 在模块导入时就求值数据根。
    """
    if not getattr(sys, 'frozen', False) or os.environ.get(_env_var()):
        return
    side = os.path.dirname(os.path.abspath(sys.executable))
    try:
        probe = os.path.join(side, '.deskrawl_write_probe')
        with open(probe, 'w'):
            pass
        os.remove(probe)
        return
    except OSError:
        pass
    root = os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'),
                        'Deskrawl', 'data')
    os.makedirs(os.path.join(root, 'builds'), exist_ok=True)
    # 示例构建只在 exe 侧；重定向后看不到了，补种一次（个人构建不在包内，无需搬运）
    src = os.path.join(side, 'data', 'builds', 'demo-hunter.json')
    dst = os.path.join(root, 'builds', 'demo-hunter.json')
    if os.path.exists(src) and not os.path.exists(dst):
        shutil.copyfile(src, dst)
    os.environ[_env_var()] = root
    _dbg(f'writable data redirected -> {root}')


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    head = argv[0] if argv else ''
    if head == 'memdump':
        own = _restore_streams()
        from deskrawl_gui.memdump import main as entry
        code = entry(argv[1:])
    elif head in ('--selftest', '--smoke'):
        own = _restore_streams()
        from deskrawl_gui.__main__ import main as entry
        code = entry(argv)                             # 选项原样透传，语义与 python -m 一致
    else:
        _redirect_writable_data()                      # 只影响写盘目标，不影响任何读路径
        from deskrawl_gui.app import run_gui           # GUI 无输出需求，不接控制台（省一个黑框）
        own, code = False, run_gui()
    _dbg(f'entry returned {code}')
    _flush()
    _pause(own)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
