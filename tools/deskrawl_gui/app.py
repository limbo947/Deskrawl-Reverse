# -*- coding: utf-8 -*-
"""主窗口：左侧导航栏 + 页面堆栈（角色 / 装备对比 / 装配中心）；暗色主题。

主窗口只做四件事：装配页面、持有唯一事实源 profile、中转刷新信号、会话状态落盘/恢复
（persist_state 开启时；默认关闭，测试/冒烟构造路径不碰用户状态文件）。
页面内部组合见 widgets/role_page、compare_page、assembly_center；编辑控件下沉到 widgets/。

刷新协议（对称，重构自旧「部分 reload」的不对称链）：
- 编辑（词条/属性/目标等）→ 页面 changed → profileChanged → _refresh_all（轻量：重算视图，不全量重排排序表）；
- 换数据源（导入/加载构建）→ _reload_pages（每页 reload 回填输入 + 各自的深度重算）。
"""
import os
import sys
import time

from PySide6.QtCore import QByteArray, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout,
                               QMainWindow, QMessageBox, QStackedWidget,
                               QStatusBar, QWidget)

from deskrawl_calc import GameData, stat_name

from .core import calc_service, session_state
from .core.glossary import CALIBER_TEXT, DATA_SOURCE_TEXT, terms_text
from .core.memory_import import MemoryImportError, check_fingerprints, import_snapshot
from .core.memory_snapshot import load_offsets
from .core.profile import BUILDS_DIR, CharacterProfile, load_build, save_build
from .widgets.assembly_center import AssemblyCenter
from .widgets.common import confirm_delete
from .widgets.compare_page import ComparePage
from .widgets.navigation import SidebarNav
from .widgets.role_page import RolePage

_HERE = os.path.dirname(os.path.abspath(__file__))
QSS_PATH = os.path.join(_HERE, 'resources', 'style.qss')
ICON_PATH = os.path.join(_HERE, 'resources', 'app_icon.svg')

# 导入菜单项的基准文案：临时态（读盘中/节流等待）与指纹失配后缀都挂在它后面，
# 单一常量避免「从运行中的游戏导入（只读）…」这句在三处各写一遍
_IMPORT_LABEL = '从运行中的游戏导入（只读）…'

# 页面注册表：key 供快捷键/编程切页用，顺序即堆栈顺序
PAGES = [('role', '角色'), ('compare', '装备对比'), ('assembly', '装配中心')]
# 行号 → 页面 key（切页时用它判断「对比页是否可见」，DPS 计轮询只在该页开）
PAGE_ROW = {key: i for i, (key, _label) in enumerate(PAGES)}

# 六类错误态 → 中文文案。code 由 MemoryImportError 携带（不靠消息子串猜），
# 未识别的情况一律回落到「读取校验失败」，保证任何异常都不会裸抛英文堆栈给用户。
_IMPORT_ERROR_TEXTS = {
    'no_process': ('游戏未运行',
                   '未找到游戏进程。请先启动游戏并进入角色，再使用「数据导入」。'),
    'no_hero': ('角色未加载',
                '游戏在运行，但未检测到已加载的角色（可能停留在主菜单/加载中）。\n请进入角色后重试。'),
    'denied': ('权限不足',
               '打开游戏进程被拒绝：游戏可能以管理员身份运行。\n请以管理员身份重启本工具后重试。'),
    'py32': ('Python 位数不符',
             '当前 Python 为 32 位，无法读取 64 位游戏进程。\n请使用 64 位解释器运行本工具。'),
    'fingerprint': ('版本指纹不符',
                    '游戏版本或静态数据已变化，导入被拒绝（防止读出错位数据）。\n'
                    '请重新导出 schema/so_dump，并更新 memory_offsets.json 指纹后重试。'),
    'data': ('读取校验失败',
             '读取结果未通过结构/值域/双读一致性校验（游戏状态可能在变化）。\n'
             '请稍后重试（城镇/菜单中更稳定）。'),
}


def describe_import_error(exc) -> tuple:
    """导入异常 → (弹窗标题, 中文正文)。"""
    code = getattr(exc, 'code', '') or ''
    title, text = _IMPORT_ERROR_TEXTS.get(code, _IMPORT_ERROR_TEXTS['data'])
    return title, f'{text}\n\n（详情：{exc}）'


def preserved_import(profile: CharacterProfile, payload: dict, gd) -> CharacterProfile:
    """从内存快照构建新档案，但保留用户的「口径设置」，导入只换角色数据。

    目标（图二）/参考技能/伤害类型是用户为「看什么数」选的，与游戏角色无关；「与当前装备
    相同」开关记忆同理（导入后候选草稿全换新，记忆位决定下一件候选是否自动沿用）。若有人
    把这几个字段改回从快照默认值走，selftest 的「导入保留用户口径」会立刻变红。
    """
    imported = CharacterProfile.from_snapshot(payload, gd)
    imported.target = profile.target
    imported.damage_type = int(profile.damage_type)
    imported.skill_name = profile.skill_name
    imported.skill_level = int(profile.skill_level)
    imported.like_current_pref = bool(getattr(profile, 'like_current_pref', False))
    return imported


_QSS_ARROWS = {
    '@ARROW_UP': 'arrow_up.svg',
    '@ARROW_DOWN': 'arrow_down.svg',
    '@ARROW_UP_DISABLED': 'arrow_up_disabled.svg',
    '@ARROW_DOWN_DISABLED': 'arrow_down_disabled.svg',
}


def load_qss(path: str = QSS_PATH) -> str:
    """读取主题样式。文件缺失必须显式抛错：静默降级会让暗色主题失效却无人察觉。

    @ARROW_* 在这里换成与 qss 同目录的绝对路径：QSS 的 url() 按**进程工作目录**解析（不是 qss
    文件位置），冻结态/从别处启动时会指错，箭头就静默消失。Windows 路径须用正斜杠。
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f'主题资源缺失：{path}')
    with open(path, encoding='utf-8') as f:
        text = f.read()
    base = os.path.dirname(os.path.abspath(path)).replace('\\', '/')
    # 长键先替换：@ARROW_UP 是 @ARROW_UP_DISABLED 的前缀，按短键先换会把后者截断成
    # "arrow_up.svg_DISABLED"（图片路径指错，禁用态箭头静默消失）。
    for token in sorted(_QSS_ARROWS, key=len, reverse=True):
        text = text.replace(token, f'{base}/{_QSS_ARROWS[token]}')
    return text


def load_app_icon(path: str = ICON_PATH):
    """应用/任务栏图标（resources/app_icon.svg）；不可用时返回 None。

    与 load_qss 的取向相反——图标是纯观感项：文件缺失或平台没有 SVG 图像插件时静默跳过
    （同 V12 暗标题栏的「尽力而为」），不为此让窗口打不开。返回 None 由调用方决定是否设置。
    """
    icon = QIcon(path)
    return None if icon.isNull() else icon


class MainWindow(QMainWindow):
    """主窗口：侧边导航 + 页面堆栈，持有 profile 并中转刷新信号。

    persist_state 默认关闭：测试/冒烟等构造路径不读写用户的会话文件；
    生产入口 run_gui 显式开启——关闭时落盘窗口几何/当前页 + 完整 profile，启动自动恢复。
    """

    profileChanged = Signal()

    def __init__(self, parent=None, *, persist_state=False):
        super().__init__(parent)
        self.setWindowTitle('Deskrawl 数值计算台')
        self.resize(1360, 860)
        self.setMinimumSize(960, 640)

        self._persist_state = bool(persist_state)
        self._restore_note = ''                  # 恢复失败时的状态栏说明（不阻断启动）
        self._pending_splits = {}                # 待首次显示后套用的分栏宽度（见 showEvent）
        state = session_state.load_state() if self._persist_state else {}
        if self._persist_state and not state and os.path.exists(session_state.STATE_PATH):
            # 文件在但读不出（损坏/版本不符）：明确说明，避免「为什么没恢复」的静默
            self._restore_note = '上次会话状态无法恢复（已回到默认状态；文件损坏或版本不符）'
        self.gd = GameData()
        # 恢复必须早于页面构造：各页在 __init__ 里直接读 profile（对比页会按槽建编辑器）
        self.profile = self._initial_profile(state)
        self._last_import_mono = float('-inf')   # 手动导入节流（≥1s）
        # 节流命中后的恢复：1s 后把菜单项从「请稍候…」切回指纹结论（一次性定时器）
        self._import_timer = QTimer(self)
        self._import_timer.setSingleShot(True)
        self._import_timer.timeout.connect(lambda: self._set_import_busy(False))

        # 页面装配：每页自带标题头部，导航只切页
        self.nav = SidebarNav(PAGES)
        self.stack = QStackedWidget()
        self.role_page = RolePage(self.profile, self.gd)
        self.compare_page = ComparePage(self.profile, self.gd)
        self.assembly_center = AssemblyCenter(self.profile, self.gd)
        for page in (self.role_page, self.compare_page, self.assembly_center):
            self.stack.addWidget(page)

        central = QWidget()
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.nav)
        lay.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.nav.pageChanged.connect(self._on_page_changed)
        self._bind_page_shortcuts()

        self.setStatusBar(QStatusBar(self))
        self._build_menus()
        self._update_source_badge()

        # 任何编辑 → profileChanged → 统一轻量刷新（同步；全量重排只在装配中心内部按需触发）
        self.role_page.changed.connect(self.profileChanged)
        self.compare_page.changed.connect(self.profileChanged)
        self.assembly_center.changed.connect(self.profileChanged)
        self.profileChanged.connect(self._refresh_all)
        self._refresh_all()
        self._on_page_changed(self.nav.currentRow())   # 让 DPS 计按当前页决定是否轮询
        if self._persist_state:
            self._restore_session_window(state)

    # ---------------- 会话持久化（窗口几何/当前页 + 完整 profile） ----------------
    def _initial_profile(self, state: dict) -> CharacterProfile:
        """启动初始 profile：会话里有就恢复，否则示例构建。

        损坏/旧版状态一律回落（记 _restore_note 供状态栏说明），不阻断启动——
        会话恢复是便利性功能，任何失败都不该让窗口打不开。
        """
        prof = state.get('profile')
        if isinstance(prof, dict):
            try:
                return CharacterProfile.from_dict(prof)
            except (TypeError, ValueError, KeyError) as exc:
                self._restore_note = f'上次会话数据无法恢复（已用示例构建）：{exc}'
        return CharacterProfile.demo()

    def _restore_session_window(self, state: dict):
        """恢复窗口几何（含最大化）与上次所在页；随后在状态栏说明恢复结果。"""
        if state:
            win = state.get('window') or {}
            geo = win.get('geometry')
            if isinstance(geo, str) and geo:
                self.restoreGeometry(QByteArray.fromBase64(geo.encode('ascii')))
            try:
                row = int(win.get('page') or 0)
            except (TypeError, ValueError):
                row = 0
            self.nav.setCurrentRow(max(0, min(row, len(PAGES) - 1)))
            # 分栏宽度按页恢复（用户拖过一次的比例应跨会话保留，否则每次启动都要重拖）。
            # 只登记、不立即 setSizes：构造期分栏还没有最终几何，此时设的像素值会被按当前窄宽度
            # 等比压缩（实测保存 330/844，恢复成 330/272），必须等窗口真正显示后再套用。
            saved = win.get('splitters') or {}
            self._pending_splits = {k: v for k, v in saved.items()
                                    if isinstance(v, list) and len(v) == 2}
        # _refresh_all 的静默刷新在前，这里给一次性说明（用户先看到自己关心的结果）
        if not state:
            # 首启动：给一条三步动线，别让用户对着示例构建发呆（此后由会话恢复接管）
            self.statusBar().showMessage(
                '首次使用：① 菜单「数据导入」读运行中的角色，或直接在左栏手工录入 → '
                '② 选装备槽与目标 → ③ 读 Δ%；术语与口径见「帮助」菜单', 20000)
        elif self._restore_note:
            self.statusBar().showMessage(self._restore_note, 12000)
        elif state:
            self.statusBar().showMessage('已恢复上次关闭前的会话（窗口与数据）', 10000)

    def showEvent(self, event):
        """窗口首次显示后套用会话里的分栏宽度。

        延到下一轮事件循环（singleShot(0)）：showEvent 时子控件尚未完成布局，此刻 setSizes 依旧
        会被按当时的窄宽度等比压缩——实测连 showEvent 里设也得到 330/272（应为 330/844）。
        """
        super().showEvent(event)
        if self._pending_splits:
            QTimer.singleShot(0, self._apply_pending_splits)

    def _apply_pending_splits(self):
        pending, self._pending_splits = self._pending_splits, {}
        for key, page in self._pages():
            sizes = pending.get(key)
            if sizes:
                page.set_splitter_sizes(sizes)

    def _pages(self):
        """(会话键, 页面) 三元组：分栏尺寸的存取都按这份映射走，避免两处各写一遍键名。"""
        return (('role', self.role_page), ('compare', self.compare_page),
                ('assembly', self.assembly_center))

    def _splitter_state(self) -> dict:
        """三页分栏宽度。窄窗竖排时各页返回 None——竖排的尺寸换回横向只会错位，故跳过。"""
        out = {}
        for key, page in self._pages():
            sizes = page.splitter_sizes()
            if sizes:
                out[key] = list(sizes)
        return out

    def _save_session_state(self):
        """关闭时落盘：窗口几何/当前页/分栏宽度 + 完整 profile。失败弹窗说明但不阻断关闭。"""
        try:
            payload = {'version': session_state.STATE_VERSION,
                       'window': {'geometry': bytes(self.saveGeometry().toBase64()).decode('ascii'),
                                  'page': int(self.nav.currentRow()),
                                  'splitters': self._splitter_state()},
                       'profile': self.profile.to_dict()}
            session_state.save_state(payload)
        except OSError as exc:
            QMessageBox.warning(self, '会话保存失败', f'{exc}\n（下次启动将回到默认状态）')

    def closeEvent(self, event):
        if self._persist_state:
            self._save_session_state()
        super().closeEvent(event)

    def _on_page_changed(self, row: int):
        """切页：DPS 计只在对比页可见时才轮询；进装配中心时补一次候选重排。

        候选 ΔDPS 相对「当前构建」排序，而该基线会被角色页（面板/巅峰）的编辑改动——那类
        编辑走轻量刷新、不重排候选表。故进页时补一次 deep 重排让列表与基线一致；这也正是不再
        需要「刷新排序」按钮的原因（类别/等级/部位变更本就会自动重排）。
        """
        self.stack.setCurrentIndex(row)
        self.compare_page.dps_meter.set_active(row == PAGE_ROW['compare'])
        if row == PAGE_ROW['assembly']:
            self.assembly_center.refresh(deep=True)

    def _bind_page_shortcuts(self):
        """Ctrl+1/2/3 直达对应页面；挂 QAction 以便菜单外也能生效。Ctrl+B 收起/展开侧栏。"""
        for i, (_key, _label) in enumerate(PAGES):
            act = QAction(self)
            act.setShortcut(f'Ctrl+{i + 1}')
            act.triggered.connect(lambda _=False, row=i: self.nav.setCurrentRow(row))
            self.addAction(act)
        toggle = QAction(self)
        toggle.setShortcut('Ctrl+B')
        toggle.triggered.connect(self.nav.toggle_collapsed)
        self.addAction(toggle)

    # ---- 旧布局时代的控件别名（保持对外属性稳定，供 selftest 与脚本使用；新代码请走页面 ----
    #      如 self.compare_page.equipment_editor，别名只为一处修改面服务，不承担新接口职责）
    @property
    def panel_editor(self):
        return self.role_page.panel_editor

    @property
    def stat_table(self):
        return self.role_page.stat_table

    @property
    def target_editor(self):
        return self.compare_page.target_editor

    @property
    def equipment_editor(self):
        return self.compare_page.equipment_editor

    # ---------------- 菜单 ----------------
    def _build_menus(self):
        bar = self.menuBar()
        file_menu = bar.addMenu('文件')
        self._add_action(file_menu, '新建空白构建', self._new_blank_build)
        # 导入后当前件会锁成只读，必须给退出口（菜单项常驻，便于用户随时回到手工程序）
        self._add_action(file_menu, '清除导入数据（回到手工程序）…', self._clear_import)
        file_menu.addSeparator()
        self._add_action(file_menu, '保存构建…', self._save_build, 'Ctrl+S')
        self._add_action(file_menu, '加载构建…', self._load_build, 'Ctrl+O')
        file_menu.addSeparator()
        self._add_action(file_menu, '退出', self.close, 'Ctrl+Q')

        tools_menu = bar.addMenu('工具')
        self._add_action(tools_menu, '运行内核自检', self._show_kernel_selftest)

        # 数据导入：菜单项仅在版本指纹自检通过时可用（P2：失配 → 禁用 + 中文原因）
        import_menu = bar.addMenu('数据导入')
        self._import_action = self._add_action(
            import_menu, _IMPORT_LABEL, self._import_from_game)
        self._apply_fingerprint_state()

        # 帮助：术语与口径是上手这道工具最陡的台阶，集中一处可读（这些文案是文档的浓缩版）
        help_menu = bar.addMenu('帮助')
        self._add_action(help_menu, '术语表…', lambda: self._show_help('术语表', terms_text()))
        self._add_action(help_menu, '口径说明…',
                         lambda: self._show_help('口径说明', CALIBER_TEXT))
        self._add_action(help_menu, '数据来源与只读约束…',
                         lambda: self._show_help('数据来源与只读约束', DATA_SOURCE_TEXT))
        help_menu.addSeparator()
        self._add_action(help_menu, '关于…', lambda: self._show_help('关于', self._about_text()))

    def _show_help(self, title: str, body: str):
        """帮助类弹窗：正文可整段选中复制（用户常要拿去和文档/群友对照）。

        不用 setDetailedText：长文会被折在「显示详细信息」后面，术语表这种要通读的内容
        藏起来等于没给。
        """
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle(title)
        box.setText(body)
        box.setTextInteractionFlags(Qt.TextSelectableByMouse)
        box.exec()

    def _fingerprint_summary(self) -> str:
        """构建指纹摘要：GameAssembly.dll 的 SHA-256 前 12 位 + so_dump 条目数记录。

        为什么值得在界面上显示：补丁后所有重锚定结论都对着某一版构建（docs/08 §12 记同一个
        值），要核对「这份报告/这组数出自哪次构建」时不必再翻文档。
        """
        try:
            fp = load_offsets().get('fingerprints') or {}
        except (OSError, ValueError, TypeError):
            return '（偏移表不可读）'
        sha = str(fp.get('game_assembly_sha256') or '')
        short = f'GameAssembly.dll SHA-256 {sha[:12]}…' if sha else 'GameAssembly.dll 未记录'
        n = fp.get('so_dump_itemdata_entries')
        return f'{short}；so_dump/ItemData {n} 条' if n is not None else short

    def _about_text(self) -> str:
        """关于：版本 / 数据目录与规模 / 构建指纹 / 当前数据源 / 只读约束。

        这些此前都无处可查（版本没有出处、构建 SHA 只在文档里、导入时间只在侧栏徽标一闪），
        集中一处后才能整段复制下来与文档、构建档案互相核对。
        """
        from . import __version__

        try:
            items = len(self.gd.items())
        except (OSError, ValueError, TypeError):
            items = 0
        mode = str(getattr(self.profile, 'import_mode', '') or '')
        if mode:
            src = f'内存导入 {"β 逐件" if mode == "beta" else "α 聚合（降级）"}'
            if self.profile.import_time:
                src += f'（快照 {self.profile.import_time}）'
        else:
            src = '手工构建 / 构建文件（未读游戏内存）'
        return ('Deskrawl 数值计算台\n\n'
                f'版本：deskrawl_gui {__version__}\n'
                f'内核：deskrawl_calc（公式与静态数值分层的纯 Python 实现，零第三方依赖）\n'
                f'数据目录：{getattr(self.gd, "dir", "") or "（未定位）"}\n'
                f'装备条目：{items} 条\n'
                f'构建指纹：{self._fingerprint_summary()}\n'
                f'版本指纹：{"通过（可导入）" if self._fingerprint_ok else "不符（导入已禁用）"}\n'
                f'当前数据源：{src}\n\n'
                '本工具只读：不写入游戏进程、不修改游戏安装目录内任何文件。\n'
                '术语与口径见「帮助 → 术语表 / 口径说明」。')

    def _apply_fingerprint_state(self, problems=None):
        """启动/导入后刷新导入入口：problems 显式传入时不再重算（导入路径上不重跑哈希）。

        导入项的文案、可用性与 tooltip 只在这里判定（含「版本指纹不符，已禁用」这句话），
        临时态结束后一律回到本方法的结论，避免同一句话在别处再写一份而慢慢走样。
        """
        if problems is None:
            problems = check_fingerprints()
        self._fingerprint_problems = list(problems)
        self._fingerprint_ok = not problems
        if problems:
            self._import_action.setEnabled(False)
            self._import_action.setText(f'{_IMPORT_LABEL}（版本指纹不符，已禁用）')
            self._import_action.setToolTip(
                '；'.join(problems) + '。请重新导出 schema/so_dump 并更新 memory_offsets.json 指纹。')
            self.statusBar().showMessage('数据导入已禁用：版本指纹不符（请重新导出 schema/so_dump）')
            return
        self._import_action.setEnabled(True)
        self._import_action.setText(_IMPORT_LABEL)
        self._import_action.setToolTip('')

    def _set_import_busy(self, busy: bool, hint: str = '导入中…'):
        """导入入口的临时态：读盘中或命中节流时禁用菜单项并写明在等什么。

        为什么需要：命中 1s 节流时界面此前只有一闪而过的状态栏，连点者会以为「没反应」；
        读内存期间也只有等待光标。恢复走缓存下来的指纹结论（不重跑哈希）。
        """
        if not busy:
            self._apply_fingerprint_state(self._fingerprint_problems)
            return
        self._import_action.setEnabled(False)
        self._import_action.setText(f'{_IMPORT_LABEL}（{hint}）')

    def _import_from_game(self):
        """主线程同步导入（实测 0.37s 级；等待光标即可，不引入线程/异步框架）。

        节流 ≥1s：连点/快捷键连发不会重复触发昂贵的内存双读与指纹哈希；命中节流时把菜单项
        切成「请稍候…」（1s 后恢复），读内存期间切成「导入中…」并常驻一条状态栏说明——
        否则连点者看到的只是「什么也没发生」。
        导入成功即完成 ``profile.from_snapshot`` 并走 _reload_pages 全页回填。
        """
        now = time.monotonic()
        if now - self._last_import_mono < 1.0:
            self._set_import_busy(True, '请稍候…')
            self.statusBar().showMessage('导入过于频繁：两次导入至少间隔 1 秒', 3000)
            self._import_timer.start(1000)
            return
        self._last_import_mono = now
        self._set_import_busy(True)
        self.statusBar().showMessage('正在读取游戏内存（只读）…')
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            res = import_snapshot()
        except MemoryImportError as exc:
            title, text = describe_import_error(exc)
            if exc.code == 'fingerprint':
                self._apply_fingerprint_state()      # 指纹状态已变：缓存的结论不能再用，必须重算
            QMessageBox.warning(self, title, text)
            return
        finally:
            # 先停掉上一次节流的恢复定时器：它若在导入收尾之后才触发，会把菜单项改回错误状态
            self._import_timer.stop()
            self._set_import_busy(False)
            QApplication.restoreOverrideCursor()
        payload = res.payload
        self.profile.replace_with(preserved_import(self.profile, payload, self.gd))
        try:
            # 游戏面板口径复算（bjd 反汇编还原）：属性明细与游戏「属性」页同口径。
            # 复算异常不阻断导入：回退计算口径（属性明细的既有行为）并在状态栏说明。
            self.profile.panel = calc_service.build_panel(payload)
        except Exception as exc:                                # noqa: BLE001 边界兜底
            self.profile.panel = None
            self.statusBar().showMessage(f'游戏面板口径复算失败（属性明细退回计算口径）：{exc}', 8000)
        self._reload_pages()      # 内含数据源徽标刷新
        mode_cn = 'β 逐件' if res.mode == 'beta' else 'α 聚合'
        msg = self._import_summary(res, payload, mode_cn)
        # 详情放 DetailedText：内容长且可整段复制（旧版只有正文，长告警列表不便留存）
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle('导入成功')
        box.setText(f'已从运行中的游戏导入（{mode_cn}）')
        box.setDetailedText(msg)
        box.exec()
        self.statusBar().showMessage(f'已从运行中的游戏导入（{mode_cn}）', 8000)

    def _import_summary(self, res, payload, mode_cn) -> str:
        """导入结果摘要（放 DetailedText，可复制）。"""
        counts = (f"装备 {len(payload.get('equipment') or [])} 件 / "
                  f"仓库 {len(payload.get('storage') or [])} 件 / "
                  f"背包 {len(payload.get('inventory') or [])} 件 / "
                  f"候选装备 {len(self.profile.bag_items)} 件（背包+仓库，见装备对比页下拉）")
        warns = payload['meta'].get('warnings') or []
        panel = self.profile.panel or {}
        pw = panel.get('warnings') or []
        # 职业主属性伤害加成（Player.CalcDamage@0x518230）：面板值代入 ×(1+值/100)，与游戏 tooltip 同源
        pri_line = ''
        ps = self.profile.primary_stat
        if ps is not None and panel.get('rows'):
            prow = next((r for r in panel['rows'] if int(r[0]) == int(ps)), None)
            if prow:
                pri_line = (f'主属性：{stat_name(int(ps))}（攻击伤害 ×'
                            f'{1.0 + float(prow[5]) / 100.0:.3f}，即游戏「当前提升 '
                            f'{float(prow[5]):.0f}% 伤害」）\n')
        msg = (f'快照时间：{res.time}\n模式：{mode_cn}\n物品：{counts}\n{pri_line}'
               f'属性明细：游戏面板口径（与游戏「属性」页一致，血比例 '
               f'{panel.get("hp_frac", 0.0):.0%}）\n告警：{len(warns)} 条')
        if warns:
            msg += '\n- ' + '\n- '.join(warns[:5])
        if pw:
            msg += f'\n面板复算说明：{len(pw)} 条\n- ' + '\n- '.join(pw[:5])
        return msg

    def _add_action(self, menu, label, slot, shortcut=None) -> QAction:
        action = QAction(label, self)
        if shortcut:
            action.setShortcut(shortcut)
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def _save_build(self):
        os.makedirs(BUILDS_DIR, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, '保存构建', os.path.join(BUILDS_DIR, f'{self.profile.name}.json'),
            'JSON (*.json)')
        if not path:
            return
        try:
            save_build(self.profile, path)
        except OSError as exc:
            QMessageBox.warning(self, '保存失败', str(exc))
            return
        self.statusBar().showMessage(f'已保存：{path}', 8000)

    def _load_build(self):
        os.makedirs(BUILDS_DIR, exist_ok=True)
        path, _ = QFileDialog.getOpenFileName(self, '加载构建', BUILDS_DIR, 'JSON (*.json)')
        if not path:
            return
        try:
            loaded = load_build(path)
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, '加载失败', str(exc))
            return
        self.profile.replace_with(loaded)      # 就地替换，widget 引用不失效
        self._reload_pages()
        self.statusBar().showMessage(f'已加载：{path}', 8000)

    def _kernel_selftest_message(self) -> tuple:
        """返回自检弹窗要显示的内容（与 --selftest 同源，便于无显示环境校验）。"""
        from .selftest import kernel_selftest_result

        ok, passes, fails, text = kernel_selftest_result()
        return ok, f'内核公式自检：{passes} PASS / {fails} FAIL', text

    def _show_kernel_selftest(self):
        ok, summary, detail = self._kernel_selftest_message()
        box = QMessageBox(self)
        box.setWindowTitle('内核自检')
        box.setIcon(QMessageBox.Information if ok else QMessageBox.Warning)
        box.setText(summary)
        box.setDetailedText(detail.strip())
        box.exec()

    # ---------------- 刷新协议 ----------------
    def _refresh_all(self):
        """轻量刷新：属性表 / 对比结果 / 已装配清单一次到位；排序表不全量重排。

        刻意**不发状态栏消息**：刷新是持续状态而非事件（一次编辑即触发），而状态栏承载的是
        导入摘要/会话恢复/指纹告警这类一次性事件——每次编辑都改写状态栏会把它们不可逆冲掉。
        """
        self.role_page.refresh()
        self.compare_page.refresh()
        self.assembly_center.refresh()

    def _reload_pages(self):
        """换数据源后的全页回填（导入/加载构建），各页 reload 内含深度重算。"""
        self._update_source_badge()
        self.role_page.reload()
        self.compare_page.reload()
        self.assembly_center.reload()

    def _update_source_badge(self):
        """侧栏底部的数据源徽标：手工 / 内存导入 α·β + 快照时间。

        此前这三条信息散在状态栏右侧、当前件标题后缀与 α 横幅里，切页就丢；徽标是常驻的
        单一出处，也让「我现在看的是哪套数」在三个页面上都成立。
        """
        mode = str(getattr(self.profile, 'import_mode', '') or '')
        if not mode:
            self.nav.set_source_badge('数据源：手工构建',
                                      '当前数值来自手工录入或构建文件，未读取游戏内存。')
            return
        mode_cn = 'β 逐件' if mode == 'beta' else 'α 聚合（降级）'
        time_cn = self.profile.import_time or '未知时间'
        self.nav.set_source_badge(f'数据源：内存导入 {mode_cn}\n快照 {time_cn}',
                                  '角色数据来自运行中游戏的只读内存快照（不写入游戏进程）。\n'
                                  'α 聚合无逐件装备数据，百分比类词条增量为近似值。')

    def _new_blank_build(self):
        """新建空白构建：只换角色数据，保留用户选的目标/参考技能/伤害类型口径。"""
        blank = CharacterProfile(name='新构建')
        blank.target = self.profile.target
        blank.damage_type = int(self.profile.damage_type)
        blank.skill_name = self.profile.skill_name
        blank.skill_level = int(self.profile.skill_level)
        self.profile.replace_with(blank)
        self._reload_pages()
        self.statusBar().showMessage('已新建空白构建（从手工录入开始）', 8000)

    def _clear_import(self):
        """清除导入数据 → 回到手工程序（进入容易退出也要容易）。

        导入会把当前件锁成只读，此前没有任何退出口。这里清掉导入态（只读/背包候选/面板口径），
        保留面板数值与目标/技能口径——用户可在此基础上继续手工试算。
        """
        if not self.profile.import_mode:
            self.statusBar().showMessage('当前不是内存导入的数据，无需清除', 5000)
            return
        if not confirm_delete(self, '清除导入数据',
                              '将移除内存导入的角色数据：当前件解锁为可编辑、背包候选清空、'
                              '属性明细退回计算口径。面板数值与目标/技能口径保留。\n继续？',
                              yes_label='清除'):
            return
        self.profile.import_mode = ''
        self.profile.import_time = ''
        self.profile.panel = None
        self.profile.bag_items = []
        self.profile.slot_current = {}
        self.profile.slot_candidate = {}
        self.profile.like_current_pref = False
        self._reload_pages()
        self.statusBar().showMessage('已清除导入数据：当前件可编辑，可继续手工试算', 10000)


def build_application(argv=None) -> QApplication:
    """建 QApplication、定样式、挂主题。主题缺失会自 load_qss 抛出，启动即失败（不静默）。

    为什么显式设 Fusion：QSS 覆盖不到的子控件（复选框指示器/下拉箭头/微调按钮/排序指示/
    分隔手柄）默认由平台样式绘制，在暗底上会漏出白色方块与浅色图形，且各 Windows 版本
    表现不一。Fusion 是 Qt 自带的跨平台实现，配合本主题的调色板可让未覆盖控件也走可控路径。
    图标在 app 上设一次即可覆盖主窗与所有弹窗（任务栏/Alt-Tab 也用它），须在建窗之前设。
    """
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName('Deskrawl 数值计算台')
    app.setStyle('Fusion')
    app.setStyleSheet(load_qss())
    icon = load_app_icon()
    if icon is not None:
        app.setWindowIcon(icon)
    return app


def _apply_dark_titlebar(win):
    """Windows 上把系统标题栏切成暗色（DWMWA_USE_IMMERSIVE_DARK_MODE）。

    只为消掉窗口顶端那条亮色横带：实测系统标题栏是纯白 #FFFFFF，与暗色应用形成割裂。
    必须在窗口**首次显示前**调用（winId() 会先建出原生窗口）——实测在 show() 之后再设，
    API 虽返回 S_OK 却不再生效，标题栏保持原样；Win10 1809 与 Win11 的属性号不同（19/20），
    两个都试，任一成功即返回；非 Windows 或旧版本不生效属预期，静默跳过（纯观感优化）。
    """
    if sys.platform != 'win32':
        return
    import ctypes
    try:
        hwnd = int(win.winId())
        enabled = ctypes.c_int(1)
        for attr in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    ctypes.c_void_p(hwnd), attr, ctypes.byref(enabled),
                    ctypes.sizeof(enabled)) == 0:
                return
    except (AttributeError, OSError, ValueError):
        pass


def shutdown_application() -> None:
    """有序拆除 Qt 对象图再交还控制权（无参：取当前 QApplication，没有则什么都不做）。

    为什么不能交给解释器：控件与 QApplication 会留到进程退出才析构，而 Qt 的 C++ 静态析构
    顺序不定，实测约 50% 概率在 ucrtbase 里 abort（0xC0000409）——输出已完整打印、退出码却非 0，
    会让 CI 的 `exe --selftest` 门禁随机判红。先 deleteLater + 跑一轮事件消化删除请求，再
    shutdown()，把析构提前到解释器仍健康时。`os._exit` 解决不了：它仍会走 DLL 卸载的静态析构。
    """
    app = QApplication.instance()
    if app is None:
        return
    for w in list(app.topLevelWidgets()):
        w.deleteLater()
    app.processEvents()
    try:
        app.shutdown()                        # Qt 6.6+；旧版无此 API 时保持原行为
    except AttributeError:
        pass


def run_gui(argv=None) -> int:
    app = build_application(argv)
    win = MainWindow(persist_state=True)      # 生产入口：关闭落盘 / 启动恢复会话状态
    _apply_dark_titlebar(win)                 # 须在 show() 之前：之后设 API 返回 S_OK 但不生效
    win.show()
    code = app.exec()
    shutdown_application()
    return code
