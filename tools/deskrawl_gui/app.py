# -*- coding: utf-8 -*-
"""主窗口：顶部导航 + 上下文条 + 页面堆栈（角色 / 装备对比 / 装配中心）；深色为主。

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
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QMainWindow,
                               QMessageBox, QStackedWidget, QVBoxLayout, QWidget)

from deskrawl_calc import GameData, stat_name

from . import single_instance
from .core import calc_service, logging_setup, session_state
from .core.format import fmt_dps
from .core.glossary import help_topics
from .core.heroes import hero_class_label
from .core.import_worker import ImportWorker
from .core.memory_errors import describe_import_error
from .core.memory_import import MemoryImportError, check_fingerprints
from .core.memory_snapshot import load_offsets
from .core.theme import THEME_LABELS, THEME_NAMES, load_qss
from .core.profile import BUILDS_DIR, CharacterProfile, load_build, save_build
from .widgets.assembly_center import AssemblyCenter
from .widgets.build_library import open_build_library
from .widgets.common import confirm_delete, preferred_window_size
from .widgets.help_panel import open_help
from .widgets.icons import icon
from .widgets.compare_page import ComparePage
from .widgets.navigation import TopNav
from .widgets.role_page import RolePage
from .widgets.toast import Toast
from .undo import ProfileUndoStack

_HERE = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(_HERE, 'resources', 'app_icon.svg')

# 导入菜单项的基准文案：临时态（读盘中/节流等待）与指纹失配后缀都挂在它后面，
# 单一常量避免「从运行中的游戏导入（只读）…」这句在三处各写一遍
_IMPORT_LABEL = '从运行中的游戏导入（只读）…'

# 页面注册表：key 供快捷键/编程切页用，顺序即堆栈顺序
PAGES = [('role', '角色'), ('compare', '装备对比'), ('assembly', '装配中心')]
# 行号 → 页面 key（切页时用它判断「对比页是否可见」，DPS 计轮询只在该页开）
PAGE_ROW = {key: i for i, (key, _label) in enumerate(PAGES)}

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
        # 1440×900 对应设计文档「产品界面 1440 宽」；小屏按可用区域收缩（见 common）
        self.resize(preferred_window_size())
        self.setMinimumSize(1024, 680)

        self._persist_state = bool(persist_state)
        self._theme = 'dark'                     # 会话恢复可能改写（见 _restore_session_window）
        self._restore_note = ''                  # 恢复失败时的浮层说明（不阻断启动）
        self._pending_splits = {}                # 待首次显示后套用的分栏宽度（见 showEvent）
        state = session_state.load_state() if self._persist_state else {}
        if self._persist_state and not state and os.path.exists(session_state.STATE_PATH):
            # 文件在但读不出（损坏/版本不符）：明确说明，避免「为什么没恢复」的静默
            self._restore_note = '上次会话状态无法恢复（已回到默认状态；文件损坏或版本不符）'
        self.gd = GameData()
        # 恢复必须早于页面构造：各页在 __init__ 里直接读 profile（对比页会按槽建编辑器）
        self.profile = self._initial_profile(state)
        self._baseline_dps = None                # 上下文条的基线 DPS 缓存（见 _update_side_summary）
        self._last_import_mono = float('-inf')   # 手动导入节流（≥1s）
        self._import_worker = None               # 后台导入线程（D3；同一时刻只允许一个）
        # 节流命中后的恢复：1s 后把菜单项从「请稍候…」切回指纹结论（一次性定时器）
        self._import_timer = QTimer(self)
        self._import_timer.setSingleShot(True)
        self._import_timer.timeout.connect(lambda: self._set_import_busy(False))

        # 页面装配：导航是顶部横条（品牌 + 页面链接 + 导入 CTA），页面堆栈在其下方整宽铺开
        self.nav = TopNav(PAGES)
        self.stack = QStackedWidget()
        self.role_page = RolePage(self.profile, self.gd)
        self.compare_page = ComparePage(self.profile, self.gd)
        self.assembly_center = AssemblyCenter(self.profile, self.gd)
        for page in (self.role_page, self.compare_page, self.assembly_center):
            self.stack.addWidget(page)

        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.nav.ticker)           # 上下文条：横向顶栏（构建/数据源/只读承诺）
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self.nav)                 # 左侧边栏：页面链接 + 底部操作簇
        body.addWidget(self.stack, 1)
        lay.addLayout(body, 1)
        self.setCentralWidget(central)
        self.nav.pageChanged.connect(self._on_page_changed)
        # 侧栏的导入 CTA 与菜单项是同一个动作的两个入口：都走 _import_from_game（含节流/指纹判定）
        self.nav.importRequested.connect(self._import_from_game)
        self.nav.themeToggled.connect(self._toggle_theme)
        self.role_page.slotActivated.connect(self._open_compare_slot)
        self._bind_page_shortcuts()

        # 提示统一走浮层（取代状态栏）：一处管级别/时长，也避免同一条消息出现在两个位置
        self.toast = Toast(self)
        # 撤销栈必须在建菜单之前就位（编辑菜单的撤销/重做动作由它创建）
        self._undo_busy = False
        self.undo_stack = ProfileUndoStack(self.profile, self._apply_undo, self)
        self._build_menus()
        self._update_source_badge()

        # 任何编辑 → profileChanged → 统一轻量刷新（同步；全量重排只在装配中心内部按需触发）
        self.role_page.changed.connect(self.profileChanged)
        self.compare_page.changed.connect(self.profileChanged)
        self.assembly_center.changed.connect(self.profileChanged)
        self.assembly_center.targetRequested.connect(
            lambda: self.nav.setCurrentRow(PAGE_ROW['compare']))
        self.profileChanged.connect(self._refresh_all)
        # 词条/候选编辑只走本页刷新（不发 profileChanged），但同样属于「可撤销的编辑」：
        # 撤销栈的触发点必须覆盖这两条入口，否则删一条词条后按 Ctrl+Z 会撤销更早的别处改动
        self.profileChanged.connect(self._capture_undo)
        self.compare_page.equipment_editor.resultsChanged.connect(self._capture_undo)
        self._refresh_all()
        self._on_page_changed(self.nav.currentRow())   # 让 DPS 计按当前页决定是否轮询
        if self._persist_state:
            self._restore_session_window(state)

    # ---------------- 会话持久化（窗口几何/当前页 + 完整 profile） ----------------
    def _initial_profile(self, state: dict) -> CharacterProfile:
        """启动初始 profile：会话里有就恢复，否则示例构建。

        损坏/旧版状态一律回落（记 _restore_note 供浮层说明），不阻断启动——
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
        """恢复窗口几何（含最大化）与上次所在页；随后在浮层说明恢复结果。"""
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
            theme = str(win.get('theme') or '')
            if theme in THEME_NAMES:
                self._set_theme(theme, notify=False)      # 静默：恢复不是事件
            saved = win.get('splitters') or {}
            self._pending_splits = {k: v for k, v in saved.items()
                                    if isinstance(v, list) and len(v) == 2}
        # _refresh_all 的静默刷新在前，这里给一次性说明（用户先看到自己关心的结果）
        if not state:
            # 首启动：给一条三步动线，别让用户对着示例构建发呆（此后由会话恢复接管）
            self.toast.notify(
                '首次使用：① 点右上角「从游戏导入」读运行中的角色，或直接在角色页手工录入 → '
                '② 选装备槽与目标 → ③ 读 Δ%；术语与口径见「帮助」菜单', timeout=20000)
        elif self._restore_note:
            self.toast.notify(self._restore_note, 'warn', 12000)
        elif state:
            self.toast.notify('已恢复上次关闭前的会话（窗口与数据）', timeout=10000)

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
                                  'theme': self._theme,
                                  'splitters': self._splitter_state()},
                       'profile': self.profile.to_dict()}
            session_state.save_state(payload)
        except OSError as exc:
            QMessageBox.warning(self, '会话保存失败', f'{exc}\n（下次启动将回到默认状态）')

    def resizeEvent(self, event):
        """窄窗自动收起侧栏（见 TopNav.set_collapsed_auto）：1024 最小宽下对比页才不出横向滚动。"""
        super().resizeEvent(event)
        if getattr(self, 'nav', None) is not None:
            self.nav.set_collapsed_auto(event.size().width())

    def closeEvent(self, event):
        if self._import_worker is not None:
            # 读内存不可中断：先让它作废结果并等它跑完，别把活着的 QThread 随窗口析构掉
            self._import_worker.cancel()
            self._import_worker.wait(3000)
            self._import_worker = None
        if self._persist_state:
            self._save_session_state()
        super().closeEvent(event)

    def _open_compare_slot(self, slot: int):
        """角色页装备总览双击 → 对比页该槽（选槽走既有下拉信号，不另开一份槽位状态）。"""
        self.compare_page.equipment_editor.select_slot(int(slot))
        self.nav.setCurrentRow(PAGE_ROW['compare'])

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
        """Ctrl+1/2/3 直达对应页面；挂 QAction 以便菜单外也能生效。Ctrl+B 收起/展开顶部导航。"""
        for i, (_key, _label) in enumerate(PAGES):
            act = QAction(self)
            act.setShortcut(f'Ctrl+{i + 1}')
            act.triggered.connect(lambda _=False, row=i: self.nav.setCurrentRow(row))
            self.addAction(act)
        toggle = QAction(self)
        toggle.setShortcut('Ctrl+B')
        toggle.triggered.connect(self.nav.toggle_collapsed)
        self.addAction(toggle)

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
        # 构建库：文件对话框之外的第二条路——多套方案靠文件名辨认时根本选不出来
        lib_action = self._add_action(file_menu, '构建库…', self._open_build_library,
                                      'Ctrl+Shift+O')
        lib_action.setIcon(icon('act_library'))
        file_menu.addSeparator()
        self._add_action(file_menu, '退出', self.close, 'Ctrl+Q')

        # 编辑：撤销/重做走档案快照（见 undo.py），菜单文案会带动作名（「撤销 面板数值」）
        edit_menu = bar.addMenu('编辑')
        self.undo_action = self.undo_stack.createUndoAction(self, '撤销')
        self.redo_action = self.undo_stack.createRedoAction(self, '重做')
        self.undo_action.setShortcut('Ctrl+Z')
        self.redo_action.setShortcut('Ctrl+Shift+Z')
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)

        # 视图 → 主题：浅色用于强光环境（A12）。切换即时生效，选择随会话持久化
        view_menu = bar.addMenu('视图')
        theme_menu = view_menu.addMenu('主题')
        self._theme_actions = {}
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        for key in THEME_NAMES:
            act = QAction(THEME_LABELS[key], self)
            act.setCheckable(True)
            act.setChecked(key == self._theme)
            act.triggered.connect(lambda _checked=False, k=key: self._set_theme(k))
            theme_group.addAction(act)
            theme_menu.addAction(act)
            self._theme_actions[key] = act

        # 数据导入：菜单项仅在版本指纹自检通过时可用（P2：失配 → 禁用 + 中文原因）
        import_menu = bar.addMenu('数据导入')
        self._import_action = self._add_action(
            import_menu, _IMPORT_LABEL, self._import_from_game)
        self._apply_fingerprint_state()

        # 帮助：术语与口径是上手这道工具最陡的台阶，集中一处可读（这些文案是文档的浓缩版）
        help_menu = bar.addMenu('帮助')
        self._add_action(help_menu, '帮助与术语（可检索）…', lambda: self._open_help('workflow'), 'F1')
        help_menu.addSeparator()
        self._add_action(help_menu, '术语表…', lambda: self._open_help('terms'))
        self._add_action(help_menu, '口径说明…', lambda: self._open_help('caliber'))
        self._add_action(help_menu, '数据来源与只读约束…', lambda: self._open_help('source'))
        help_menu.addSeparator()
        # 内核自检是诊断入口，不是日常功能：放帮助里，避免独占一级菜单（原「工具」菜单只有它一项）
        self._add_action(help_menu, '运行内核自检…', self._show_kernel_selftest)
        help_menu.addSeparator()
        self._add_action(help_menu, '关于…', lambda: self._open_help('about'))

    def _open_help(self, topic: str = 'workflow'):
        """帮助面板（可检索、可分节）：菜单各项只是「打开并定位到某一节」。

        为什么不再用 QMessageBox：术语表要通读，弹窗里既不能搜也不能分节；正文仍可整段复制。
        """
        open_help(help_topics(self._about_text()), topic, self)

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
            # 顶栏 CTA 与菜单项同一结论：禁用时给出原因，而不是留一个点了没反应的黄按钮
            self.nav.set_import_state(False, '导入不可用',
                                      '版本指纹不符，已禁用。' + self._import_action.toolTip())
            self.toast.notify('数据导入已禁用：版本指纹不符（请重新导出 schema/so_dump）',
                              'error', 12000)
            return
        self._import_action.setEnabled(True)
        self._import_action.setText(_IMPORT_LABEL)
        self._import_action.setToolTip('')
        self.nav.set_import_state(True, '从游戏导入',
                                  '读取运行中游戏的角色数据（只读内存，需游戏内已进入角色）')

    def _set_import_busy(self, busy: bool, hint: str = '导入中…'):
        """导入入口的临时态：读盘中或命中节流时禁用菜单项并写明在等什么。

        为什么需要：命中 1s 节流时界面此前只有一闪而过的提示，连点者会以为「没反应」；
        读内存期间也只有等待光标。恢复走缓存下来的指纹结论（不重跑哈希）。
        """
        if not busy:
            self._apply_fingerprint_state(self._fingerprint_problems)
            return
        self._import_action.setEnabled(False)
        self._import_action.setText(f'{_IMPORT_LABEL}（{hint}）')
        self.nav.set_import_state(False, hint, '正在读取游戏内存（只读），完成前不会重复触发')

    def _import_from_game(self):
        """后台线程导入（D3）：读内存期间窗口保持响应，结果回主线程再换档案。

        节流 ≥1s：连点/快捷键连发不会重复触发昂贵的内存双读与指纹哈希；命中节流时把菜单项
        切成「请稍候…」（1s 后恢复），读内存期间切成「导入中…」并常驻一条浮层说明——
        否则连点者看到的只是「什么也没发生」。widget 只在主线程动，线程里只读快照。
        """
        now = time.monotonic()
        if now - self._last_import_mono < 1.0:
            self._set_import_busy(True, '请稍候…')
            self.toast.notify('导入过于频繁：两次导入至少间隔 1 秒', 'warn', 3000)
            self._import_timer.start(1000)
            return
        if self._import_worker is not None:
            self._set_import_busy(True, '上一轮仍在读取…')
            self.toast.notify('上一次导入还在读取，请稍候', 'warn', 3000)
            return
        self._last_import_mono = now
        self._set_import_busy(True)
        self.toast.notify('正在读取游戏内存（只读）…', timeout=30000)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        worker = ImportWorker(self)
        worker.done.connect(self._on_import_done)
        self._import_worker = worker
        worker.start()

    def _on_import_done(self, res, code, message):
        """导入线程收尾：先恢复界面状态（含等待光标），再处理结果或错误。

        错误与成功走同一出口：任何路径都不会留下「导入中…」卡住的菜单项。
        """
        self._import_timer.stop()
        self._set_import_busy(False)
        QApplication.restoreOverrideCursor()
        worker, self._import_worker = self._import_worker, None
        if worker is not None:
            worker.wait(2000)          # 已经发完信号，这里只是确保线程对象可安全回收
            worker.deleteLater()
        if res is None:
            if code == 'fingerprint':
                self._apply_fingerprint_state()   # 指纹状态已变：缓存结论不能再用，必须重算
            exc = MemoryImportError(message, 'env', code=code)
            title, text = describe_import_error(exc)
            QMessageBox.warning(self, title, text)
            return
        self._apply_snapshot(res)

    def _apply_snapshot(self, res):
        """快照 → 档案：只换角色数据（保留用户口径），复算面板口径，再全页回填并给摘要。"""
        payload = res.payload
        self.profile.replace_with(preserved_import(self.profile, payload, self.gd))
        try:
            # 游戏面板口径复算（bjd 反汇编还原）：属性明细与游戏「属性」页同口径。
            # 复算异常不阻断导入：回退计算口径（属性明细的既有行为）并在浮层说明。
            self.profile.panel = calc_service.build_panel(payload)
        except Exception as exc:                                # noqa: BLE001 边界兜底
            self.profile.panel = None
            self.toast.notify(f'游戏面板口径复算失败（属性明细退回计算口径）：{exc}', 'warn', 8000)
        self.undo_stack.reset()   # 换数据源不入撤销栈：导入是一条新起点，不是一次编辑
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

    def _save_build(self) -> bool:
        """保存构建（对话框路径）；返回是否真的写了盘——构建库的「另存当前」复用这个返回值。"""
        os.makedirs(BUILDS_DIR, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, '保存构建', os.path.join(BUILDS_DIR, f'{self.profile.name}.json'),
            'JSON (*.json)')
        if not path:
            return False
        try:
            save_build(self.profile, path)
        except OSError as exc:
            QMessageBox.warning(self, '保存失败', str(exc))
            return False
        self.toast.notify(f'已保存：{path}', timeout=8000)
        return True

    def _open_build_library(self):
        """构建库窗口：载入与另存都回到本窗口的统一路径（不另写一份加载逻辑）。"""
        open_build_library(self.gd, self._apply_build, self._save_build, self)

    def _apply_build(self, path: str):
        """按路径载入构建（文件对话框与构建库共用；失败弹窗但不关调用方窗口）。"""
        try:
            loaded = load_build(path)
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, '加载失败', str(exc))
            return
        self.profile.replace_with(loaded)      # 就地替换，widget 引用不失效
        self.undo_stack.reset()
        self._reload_pages()
        self.toast.notify(f'已加载：{path}', timeout=8000)

    def _load_build(self):
        os.makedirs(BUILDS_DIR, exist_ok=True)
        path, _ = QFileDialog.getOpenFileName(self, '加载构建', BUILDS_DIR, 'JSON (*.json)')
        if path:
            self._apply_build(path)

    def _set_theme(self, name: str, notify: bool = True):
        """切换主题：整套 QSS 重设 + 清掉按 QSS 颜色缓存的三态色（否则 Δ% 仍是旧主题色）。"""
        from .widgets.compare_view import reset_trend_colors

        name = name if name in THEME_NAMES else 'dark'
        self._theme = name
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(load_qss(theme=name))
        reset_trend_colors()
        act = getattr(self, '_theme_actions', {}).get(name)
        if act is not None:
            act.setChecked(True)
        # 顶栏开关写「点它会切到哪」：切完立刻换文案，避免按钮读起来像当前状态
        self.nav.set_theme_state(name)
        _apply_dark_titlebar(self, name == 'dark')      # 标题栏跟随主题（best-effort）
        if notify:
            self.toast.notify(f'已切换到{THEME_LABELS[name]}主题', timeout=4000)

    def _toggle_theme(self):
        """顶栏主题开关：深↔浅一步切换（菜单里仍可显式选，两处共享同一状态）。"""
        self._set_theme('light' if self._theme == 'dark' else 'dark')

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

    # ---------------- 撤销 / 重做 ----------------
    def _capture_undo(self):
        """一次编辑结束：比对档案快照，变了就压一步（细节见 undo 模块）。

        为什么挂在这里而不是各编辑器里：编辑入口十几个，逐个埋点必然漏；而 profile 是
        唯一事实源，刷新链（含对比页的 resultsChanged 分支）已经覆盖了全部写入路径。
        """
        if self._undo_busy:
            return
        self.undo_stack.capture()

    def _apply_undo(self):
        """撤销/重做已把档案灌回 profile：整页回填重建编辑器。

        必须整页重建：撤销替换了 profile 里的草稿对象，旧控件仍握着一份已经被丢弃的引用，
        只刷数值会让后续编辑写进「幽灵对象」（界面看着改了，算出来的没变）。
        """
        self._undo_busy = True
        try:
            self._reload_pages()
        finally:
            self._undo_busy = False

    # ---------------- 刷新协议 ----------------
    def _refresh_all(self):
        """轻量刷新：属性表 / 对比结果 / 已装配清单一次到位；排序表不全量重排。

        刻意**不发浮层提示**：刷新是持续状态而非事件（一次编辑即触发），而浮层承载的是
        导入摘要/会话恢复/指纹告警这类一次性事件——每次编辑都弹一遍会把它们不可逆冲掉。
        """
        self.role_page.refresh()
        self.compare_page.refresh()
        self.assembly_center.refresh()
        self._update_side_summary()

    def _update_side_summary(self, with_dps: bool = False):
        """上下文条摘要：名称/等级/职业常驻，基线 DPS 缓存后同样常驻。

        为什么缓存而不是每次重算：整表基线约 1ms，编辑时每次按键都算不值得；但只在换数据源时
        算又会让「基线」在第一次编辑后消失（规范要求它常驻）。故首次/换源算一次并记住，其余
        编辑复用——它是「现在算的是哪套数」的锚，实时变化在对比页已经给到。
        """
        prof = self.profile
        cls = hero_class_label(self.gd, getattr(prof, 'hero_class', None))
        if with_dps or self._baseline_dps is None:
            try:
                self._baseline_dps = fmt_dps(calc_service.baseline_dps(prof, self.gd))
            except (OSError, ValueError, TypeError):
                self._baseline_dps = ''
        dps = f' · 基线 {self._baseline_dps}' if self._baseline_dps else ''
        self.nav.set_profile_summary(
            f'{prof.name} · Lv{int(prof.level)} · {cls}{dps}',
            '当前构建：名称 / 等级 / 职业 / 基线期望 DPS。存取构建见「文件」菜单。')

    def _reload_pages(self):
        """换数据源后的全页回填（导入/加载构建），各页 reload 内含深度重算。"""
        self._update_source_badge()
        self.role_page.reload()
        self.compare_page.reload()
        self.assembly_center.reload()
        self._update_side_summary(with_dps=True)

    def _update_source_badge(self):
        """侧栏底部的数据源徽标：手工 / 内存导入 α·β + 快照时间。

        此前这三条信息散在状态栏右侧、当前件标题后缀与 α 横幅里，切页就丢；徽标是常驻的
        单一出处，也让「我现在看的是哪套数」在三个页面上都成立。
        """
        mode = str(getattr(self.profile, 'import_mode', '') or '')
        if not mode:
            self.nav.set_source_badge('手工构建',
                                      '当前数值来自手工录入或构建文件，未读取游戏内存。')
            return
        mode_cn = 'β 逐件' if mode == 'beta' else 'α 聚合（降级）'
        time_cn = self.profile.import_time or '未知时间'
        self.nav.set_source_badge(f'内存导入 {mode_cn} · 快照 {time_cn}',
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
        self.undo_stack.reset()
        self._reload_pages()
        self.toast.notify('已新建空白构建（从手工录入开始）', timeout=8000)

    def _clear_import(self):
        """清除导入数据 → 回到手工程序（进入容易退出也要容易）。

        导入会把当前件锁成只读，此前没有任何退出口。这里清掉导入态（只读/背包候选/面板口径），
        保留面板数值与目标/技能口径——用户可在此基础上继续手工试算。
        """
        if not self.profile.import_mode:
            self.toast.notify('当前不是内存导入的数据，无需清除', timeout=5000)
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
        self.undo_stack.reset()
        self._reload_pages()
        self.toast.notify('已清除导入数据：当前件可编辑，可继续手工试算', timeout=10000)


def build_application(argv=None, theme: str = 'dark') -> QApplication:
    """建 QApplication、定样式、挂主题。主题缺失会自 load_qss 抛出，启动即失败（不静默）。

    为什么显式设 Fusion：QSS 覆盖不到的子控件（复选框指示器/下拉箭头/微调按钮/排序指示/
    分隔手柄）默认由平台样式绘制，在暗底上会漏出白色方块与浅色图形，且各 Windows 版本
    表现不一。Fusion 是 Qt 自带的跨平台实现，配合本主题的调色板可让未覆盖控件也走可控路径。
    图标在 app 上设一次即可覆盖主窗与所有弹窗（任务栏/Alt-Tab 也用它），须在建窗之前设。
    """
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName('Deskrawl 数值计算台')
    app.setStyle('Fusion')
    app.setStyleSheet(load_qss(theme=theme))
    icon = load_app_icon()
    if icon is not None:
        app.setWindowIcon(icon)
    return app


def _apply_dark_titlebar(win, enabled: bool = True):
    """Windows 上按主题切换系统标题栏明暗（DWMWA_USE_IMMERSIVE_DARK_MODE）。

    只为消掉窗口顶端那条与画布割裂的横带：暗色应用配纯白标题栏、浅色应用配深色标题栏
    都像另一套程序。必须在窗口**首次显示前**调用（winId() 会先建出原生窗口）——实测在
    show() 之后再设，API 虽返回 S_OK 却不再生效，标题栏保持原样；运行期切主题时这里是
    best-effort（较新 Win10/11 生效，旧版本要下次启动才变），不为此弹提示。
    Win10 1809 与 Win11 的属性号不同（19/20），两个都试，任一成功即返回；
    非 Windows 或不支持时静默跳过（纯观感优化）。
    """
    if sys.platform != 'win32':
        return
    import ctypes
    try:
        hwnd = int(win.winId())
        enabled = ctypes.c_int(1 if enabled else 0)
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


def _notify_unhandled(path: str, exc) -> None:
    """崩溃提示：只在已有 QApplication 时弹窗（无显示环境的自检/CLI 不弹，避免挂住）。"""
    if QApplication.instance() is None:
        return
    QMessageBox.critical(None, '程序遇到未处理的错误',
                         f'{exc}\n\n详细信息已写入日志：\n{path}\n请把该文件附在反馈里。')


def run_gui(argv=None) -> int:
    # 先装兜底再建窗口：QSS/图标缺失这类启动期异常同样需要留下可复盘的记录
    logging_setup.install(notify=_notify_unhandled)
    app = build_application(argv)
    server, why = single_instance.acquire()    # 引用活到 exec 结束：server 被回收锁就没了
    if server is None:
        if why == 'exists':
            QMessageBox.information(None, '已在运行',
                                    'Deskrawl 数值计算台已有一个实例在运行，已把它切到前台。\n'
                                    '本实例将退出，避免两份会话状态互相覆盖。')
            shutdown_application()            # 这条早退同样要拆 Qt，否则偶发析构 abort
            return 0
        # 监听失败：提示但继续（宁可少一层保护，也不让工具打不开）
        QMessageBox.warning(None, '单实例保护不可用',
                            f'{why}\n本次仍会启动，但双开可能互相覆盖会话状态。')
    win = MainWindow(persist_state=True)      # 生产入口：关闭落盘 / 启动恢复会话状态
    if server is not None:
        server.newConnection.connect(lambda: single_instance.activate(win, server))
        single_instance.activate(win, server)  # 补收「抢锁→建窗」之间到达的连接
    # 须在 show() 之前：之后设 API 返回 S_OK 但不生效；会话恢复的主题也要在这里生效
    _apply_dark_titlebar(win, win._theme == 'dark')
    win.show()
    code = app.exec()
    shutdown_application()
    return code
