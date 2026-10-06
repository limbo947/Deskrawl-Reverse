# -*- coding: utf-8 -*-
"""主窗口组装：左 dock 角色面板 / 右 dock(Tab 化) 目标+属性 / 中央三 Tab；暗色主题。

布局与《桌面GUI开发计划》§3.4 一致；主窗口只做装配与信号中转，编辑控件下沉到 widgets/。
"""
import os
import sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QApplication, QDockWidget, QFileDialog, QMainWindow,
                               QMessageBox, QStatusBar, QTabWidget)

from deskrawl_calc import GameData

from .core.profile import BUILDS_DIR, CharacterProfile, load_build, save_build
from .widgets.assembly_browser import AssemblyBrowser
from .widgets.candidate_rank_view import CandidateRankView
from .widgets.equipment_editor import EquipmentEditor
from .widgets.panel_editor import PanelEditor
from .widgets.stat_table import StatTable
from .widgets.target_editor import TargetEditor

_HERE = os.path.dirname(os.path.abspath(__file__))
QSS_PATH = os.path.join(_HERE, 'resources', 'style.qss')


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

        # 存档导入 v1 明确不实现，只保留禁用占位，避免用户误以为可用
        save_menu = bar.addMenu('存档')
        for label in ('导入存档…（v1 未实现）', '读取运行时内存…（v1 未实现）'):
            action = QAction(label, self)
            action.setEnabled(False)
            save_menu.addAction(action)

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
        """单一刷新入口：属性表 / 对比结果 / 排序表 / 已装配清单一次到位。"""
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
