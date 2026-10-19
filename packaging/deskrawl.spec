# -*- mode: python ; coding: utf-8 -*-
"""便携包 spec：one-folder + windowed 单 exe，承载 GUI / 自检 / 内存快照三入口。

关键约束（改前先读）：PyInstaller 6.x 的 one-folder 把「除 exe 外的一切」放进内容目录
`_internal/`，且 `datas` 的 dest **相对 `_internal/`**。仓库里六处数据定位全是 `__file__`
相对跳转，只有让「与代码同级的小资源」镜像到 `_internal/<pkg>/…` 原位，那些 `..` 才会落到
与源码布局相同的层级。**绝不能**设 `--contents-directory "."`：那会让六处跳转一起错开一层。
`data/` 不走 datas —— 由 build_portable.ps1 拷到 exe 同级，同样是为了维持这套同构。
"""
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))          # SPECPATH 由 PyInstaller 注入
TOOLS = os.path.join(ROOT, 'tools')
GUI = os.path.join(TOOLS, 'deskrawl_gui')
NAME = os.environ.get('DESKRAWL_EXE_NAME') or 'Deskrawl计算台'   # 单一开关：构建脚本设此环境变量

# --smoke 的 QSS 锚点对账要 `os.walk(包目录)` 全文扫描包内 .py 取锚点；frozen 下模块只存在于
# PYZ、磁盘没有源码，扫描结果为空会把全部 QSS 选择器误判成「死选择器」。故把包内 .py 以
# **非导入路径** `_src/` 镜像进来：os.walk 照样能扫到全文，又不会与 PYZ 的模块加载抢解析权。
_SRC_MIRROR = []
for _dp, _dns, _fns in os.walk(GUI):
    _dns[:] = [d for d in _dns if d != '__pycache__']
    for _fn in _fns:
        if _fn.endswith('.py'):
            _full = os.path.join(_dp, _fn)
            _rel = os.path.relpath(_full, GUI)
            _SRC_MIRROR.append((_full, os.path.join('deskrawl_gui', '_src', os.path.dirname(_rel))))

a = Analysis(
    [os.path.join(ROOT, 'packaging', 'launcher.py')],
    pathex=[TOOLS],                       # deskrawl_calc / deskrawl_gui 都在 tools/ 下（tools 无 __init__）
    datas=[
        # 与代码同级、必须原地镜像的小资源：app.py(QSS/图标)、memory_snapshot(偏移表)、测试夹具
        (os.path.join(GUI, 'resources'), 'deskrawl_gui/resources'),
        (os.path.join(GUI, 'core', 'memory_offsets.json'), 'deskrawl_gui/core'),
        (os.path.join(GUI, 'fixtures'), 'deskrawl_gui/fixtures'),
    ] + _SRC_MIRROR,
    # 防 modulegraph 漏收懒加载入口（都写在函数内 import）；成本近乎 0
    hiddenimports=['deskrawl_calc.cli', 'deskrawl_gui.selftest',
                   'deskrawl_gui.selftest_fixture', 'deskrawl_gui.selftest_legendary',
                   'deskrawl_gui.selftest_skillmods', 'deskrawl_gui.memdump'],
    # excludes 只排「Python 模块」：Qt 的 DLL 仍按真实 import 传递依赖收集，故本名单是
    # 「防 PySide6 hook 过度收集」的安全网。本项目只用 QtCore/QtGui/QtWidgets + QtSvg(图标是 svg)。
    excludes=[
        'PySide6.QtNetwork', 'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuickWidgets',
        'PySide6.QtQuickControls2', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebChannel', 'PySide6.QtWebSockets', 'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets', 'PySide6.Qt3DCore', 'PySide6.Qt3DRender',
        'PySide6.Qt3DInput', 'PySide6.Qt3DLogic', 'PySide6.Qt3DAnimation', 'PySide6.Qt3DExtras',
        'PySide6.QtCharts', 'PySide6.QtDataVisualization', 'PySide6.QtGraphs',
        'PySide6.QtGraphsWidgets', 'PySide6.QtSql', 'PySide6.QtTest', 'PySide6.QtHelp',
        'PySide6.QtDesigner', 'PySide6.QtUiTools', 'PySide6.QtBluetooth', 'PySide6.QtNfc',
        'PySide6.QtPositioning', 'PySide6.QtLocation', 'PySide6.QtSerialPort',
        'PySide6.QtSerialBus', 'PySide6.QtRemoteObjects', 'PySide6.QtScxml',
        'PySide6.QtSensors', 'PySide6.QtSpatialAudio', 'PySide6.QtPdf',
        'PySide6.QtPdfWidgets', 'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets',
        'PySide6.QtSvgWidgets', 'PySide6.QtDBus', 'PySide6.QtStateMachine',
        'PySide6.QtTextToSpeech', 'PySide6.QtXml', 'PySide6.QtConcurrent', 'PySide6.QtAsyncio',
        'tkinter', 'pydoc', 'pydoc_data', 'lib2to3', 'test', 'setuptools', 'pkg_resources',
        'pip', 'wheel', 'pytest', 'numpy', 'PIL', 'matplotlib', 'IPython', 'sqlite3',
    ],
    noarchive=False,
)

# 体积过滤：PySide6 hook 默认把 Qt 自己的 translations/(58.8MB)、resources/(101.4MB)、
# qml/(25.4MB) 全收进来。**必须按 `PySide6/` 前缀判断**——若用 `\resources\` 之类子串匹配，
# 会连我们自己的 `deskrawl_gui/resources/style.qss` 一起删掉，GUI 启动即抛 FileNotFoundError。
_BULK = ('PySide6/translations/', 'PySide6/qml/', 'PySide6/resources/')
a.datas[:] = [d for d in a.datas if not d[0].replace('\\', '/').startswith(_BULK)]
a.binaries[:] = [b for b in a.binaries if 'opengl32sw' not in b[0].lower()]

pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name=NAME, console=False,
    upx=False,            # 不装 UPX：压过的 Qt DLL 更易被杀软误判
)

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=NAME)
