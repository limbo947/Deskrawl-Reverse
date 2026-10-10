# -*- coding: utf-8 -*-
"""主窗口组装：左 dock 角色面板 / 右 dock(Tab 化) 目标+属性 / 中央三 Tab；暗色主题。

布局与《桌面GUI开发计划》§3.4 一致；主窗口只做装配与信号中转，编辑控件下沉到 widgets/。
"""
import os
import sys
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QApplication, QDockWidget, QFileDialog, QLabel, QMainWindow,
                               QMessageBox, QStatusBar, QTabWidget)

from deskrawl_calc import GameData, stat_name

from .core import calc_service
from .core.memory_import import MemoryImportError, check_fingerprints, import_snapshot
from .core.profile import BUILDS_DIR, CharacterProfile, load_build, save_build
from .widgets.assembly_browser import AssemblyBrowser
from .widgets.candidate_rank_view import CandidateRankView
from .widgets.equipment_editor import EquipmentEditor
from .widgets.panel_editor import PanelEditor
from .widgets.stat_table import StatTable
from .widgets.target_editor import TargetEditor

_HERE = os.path.dirname(os.path.abspath(__file__))
QSS_PATH = os.path.join(_HERE, 'resources', 'style.qss')

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


def load_qss(path: str = QSS_PATH) -> str:
    """读取主题样式。文件缺失必须显式抛错：静默降级会让暗色主题失效却无人察觉。"""
    if not os.path.exists(path):
        raise FileNotFoundError(f'主题资源缺失：{path}')
    with open(path, encoding='utf-8') as f:
        return f.read()


class MainWindow(QMainWindow):
    """主窗口：只负责 dock/tab 布局、持有唯一事实源 profile，并中转刷新信号。"""

    profileChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Deskrawl 数值计算台')
        self.resize(1360, 860)

        self.gd = GameData()
        self.profile = CharacterProfile.demo()
        self._last_import_mono = float('-inf')   # 手动导入节流（≥1s）

        self.panel_editor = PanelEditor(self.profile, self.gd)
        self.addDockWidget(Qt.LeftDockWidgetArea,
                           self._make_dock('角色面板', 'dockPanel', self.panel_editor))

        self.target_editor = TargetEditor(self.profile)
        self.stat_table = StatTable()
        right_tabs = QTabWidget()
        right_tabs.addTab(self.target_editor, '目标设置')
        right_tabs.addTab(self.stat_table, '属性明细')
        self.addDockWidget(Qt.RightDockWidgetArea,
                           self._make_dock('目标 / 属性', 'dockRight', right_tabs))

        self.tabs = QTabWidget()
        self.equipment_editor = EquipmentEditor(self.profile, self.gd)
        self.candidate_rank_view = CandidateRankView(self.profile, self.gd)
        self.assembly_browser = AssemblyBrowser(self.profile, self.gd)
        self.tabs.addTab(self.equipment_editor, '装备对比')
        self.tabs.addTab(self.candidate_rank_view, '候选排序')
        self.tabs.addTab(self.assembly_browser, '装配浏览器')
        self.setCentralWidget(self.tabs)

        self.setStatusBar(QStatusBar(self))
        # 快照时间戳常驻状态栏（普通提示消息仍走临时消息区，互不覆盖）
        self._snapshot_label = QLabel('快照：未导入')
        self._snapshot_label.setObjectName('snapshotLabel')
        self.statusBar().addPermanentWidget(self._snapshot_label)
        self._build_menus()

        # 任何编辑 → profileChanged → 统一刷新（同步，实测 <50ms）
        self.panel_editor.changed.connect(self.profileChanged)
        self.target_editor.changed.connect(self.profileChanged)
        self.assembly_browser.changed.connect(self.profileChanged)
        self.candidate_rank_view.changed.connect(self.profileChanged)
        self.profileChanged.connect(self._refresh_all)
        self._refresh_all()

    def _make_dock(self, title: str, obj_name: str, widget) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setObjectName(obj_name)
        dock.setWidget(widget)
        return dock

    # ---------------- 菜单 ----------------
    def _build_menus(self):
        bar = self.menuBar()
        file_menu = bar.addMenu('文件')
        self._add_action(file_menu, '保存构建…', self._save_build, 'Ctrl+S')
        self._add_action(file_menu, '加载构建…', self._load_build, 'Ctrl+O')
        file_menu.addSeparator()
        self._add_action(file_menu, '退出', self.close, 'Ctrl+Q')

        tools_menu = bar.addMenu('工具')
        self._add_action(tools_menu, '运行内核自检', self._show_kernel_selftest)

        # 数据导入：菜单项仅在版本指纹自检通过时可用（P2：失配 → 禁用 + 中文原因）
        import_menu = bar.addMenu('数据导入')
        self._import_action = self._add_action(
            import_menu, '从运行中的游戏导入（只读）…', self._import_from_game)
        self._apply_fingerprint_state()

    def _apply_fingerprint_state(self):
        """启动即校验一次版本指纹；失配则禁用导入入口并写明原因（宁可禁用，不读脏数据）。"""
        problems = check_fingerprints()
        self._fingerprint_ok = not problems
        if problems:
            self._import_action.setEnabled(False)
            self._import_action.setText('从运行中的游戏导入（只读）…（版本指纹不符，已禁用）')
            self._import_action.setToolTip(
                '；'.join(problems) + '。请重新导出 schema/so_dump 并更新 memory_offsets.json 指纹。')
            self.statusBar().showMessage('数据导入已禁用：版本指纹不符（请重新导出 schema/so_dump）')

    def _import_from_game(self):
        """主线程同步导入（实测 0.37s 级；等待光标即可，不引入线程/异步框架）。

        节流 ≥1s：连点/快捷键连发不会重复触发昂贵的内存双读与指纹哈希；
        导入成功即完成 ``profile.from_snapshot`` 并走既有 profileChanged 刷新链。
        """
        now = time.monotonic()
        if now - self._last_import_mono < 1.0:
            self.statusBar().showMessage('导入过于频繁：两次导入至少间隔 1 秒', 3000)
            return
        self._last_import_mono = now
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            res = import_snapshot()
        except MemoryImportError as exc:
            title, text = describe_import_error(exc)
            if exc.code == 'fingerprint':
                self._import_action.setEnabled(False)
                self._import_action.setText('从运行中的游戏导入（只读）…（版本指纹不符，已禁用）')
            QMessageBox.warning(self, title, text)
            return
        finally:
            QApplication.restoreOverrideCursor()
        payload = res.payload
        self.profile.replace_with(CharacterProfile.from_snapshot(payload, self.gd))
        try:
            # 游戏面板口径复算（bjd 反汇编还原）：属性明细与游戏「属性」页同口径。
            # 复算异常不阻断导入：回退计算口径（属性明细的既有行为）并在状态栏说明。
            self.profile.panel = calc_service.build_panel(payload)
        except Exception as exc:                                # noqa: BLE001 边界兜底
            self.profile.panel = None
            self.statusBar().showMessage(f'游戏面板口径复算失败（属性明细退回计算口径）：{exc}', 8000)
        self.panel_editor.reload()
        self.target_editor.reload()
        self.equipment_editor.reload()
        self._refresh_all()
        mode_cn = 'β 逐件' if res.mode == 'beta' else 'α 聚合'
        self._snapshot_label.setText(f'快照：{res.time}（{mode_cn}）')
        counts = (f"装备 {len(payload.get('equipment') or [])} 件 / "
                  f"仓库 {len(payload.get('storage') or [])} 件 / "
                  f"背包 {len(payload.get('inventory') or [])} 件 / "
                  f"候选装备 {len(self.profile.bag_items)} 件（背包+仓库，见装备对比页下拉）")
        warns = payload['meta'].get('warnings') or []
        panel = self.profile.panel or {}
        pw = panel.get('warnings') or []
        # 职业主属性伤害加成（Player.CalcDamage@0x50E400）：面板值代入 ×(1+值/100)，与游戏 tooltip 同源
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
        QMessageBox.information(self, '导入成功', msg)
        self.statusBar().showMessage(f'已从运行中的游戏导入（{mode_cn}）')

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
        self.statusBar().showMessage(f'已保存：{path}')

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
        self.panel_editor.reload()
        self.target_editor.reload()
        self.equipment_editor.reload()
        self._refresh_all()
        self.statusBar().showMessage(f'已加载：{path}')

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

    def _refresh_all(self):
        """单一刷新入口：属性表 / 对比结果 / 排序表 / 已装配清单一次到位。

        属性明细口径：内存导入的构建显示「游戏面板口径」（导入时冻结，与游戏属性页一致）；
        手工构建无面板数据，退回既有「计算口径」聚合分解。
        """
        if self.profile.panel:
            self.stat_table.set_panel_view(self.profile.panel)
        else:
            self.stat_table.set_sheet(self.profile.to_sheet(self.gd))
        self.equipment_editor.refresh()
        self.candidate_rank_view.refresh()
        self.assembly_browser.refresh()
        self.statusBar().showMessage(f'构建「{self.profile.name}」已刷新')


def build_application(argv=None) -> QApplication:
    """建 QApplication 并挂主题。主题缺失会自 load_qss 抛出，启动即失败（不静默）。"""
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName('Deskrawl 数值计算台')
    app.setStyleSheet(load_qss())
    return app


def run_gui(argv=None) -> int:
    app = build_application(argv)
    win = MainWindow()
    win.show()
    return app.exec()
