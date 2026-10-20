# -*- coding: utf-8 -*-
"""左侧边栏（页面链接 + 底部操作簇）+ 上下文条（横向顶栏，由主窗口取用）。

为什么 2026-10-20 从顶栏改回侧栏：顶栏里「去哪」（页签）在左、「做什么」（只读/主题/导入）
在右，扫视动线要横穿整条 64px；改回侧栏后「去哪」成左列、「做什么」钉在底部，
上下文条（构建 / 数据源 / 只读承诺）独占横向顶栏——切页也不丢「现在算的是哪套角色、数从哪来」。
代价是横向让出 176px，因此保留收起（Ctrl+B：只留图标 + 隐藏上下文条，64px）。

对外接口保持稳定（pageChanged / setCurrentRow / currentRow / set_source_badge /
set_profile_summary / toggle_collapsed / _keys / ticker），页面与自检无需感知导航形态。
"""
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (QButtonGroup, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout, QWidget)

from ..core.theme import THEME_LABELS
from .icons import icon

# 页面 key → 图标文件：收起态链接只留图标，缺图会变成一排空白按钮
_PAGE_ICONS = {'role': 'page_role', 'compare': 'page_compare', 'assembly': 'page_assembly'}

# 侧栏宽度：展开 176 放得下「装配中心」四字 + 图标；收起 64 只留 46px 图标按钮
_WIDTH_EXPANDED = 176
_WIDTH_COLLAPSED = 64
# 窗宽低于此值自动收起：给内容区让出 112px——最小窗宽（1024）下对比页编辑器最小宽 ~870，
# 不收起就会长出 ~70px 横向滚动条（§5「横向滚动为零」的回归口径）
_AUTO_COLLAPSE_BELOW = 1180


class TopNav(QWidget):
    """左侧边栏；上下文条（34px 横条）单独暴露，由主窗口放到内容列顶部。"""

    pageChanged = Signal(int)
    importRequested = Signal()
    themeToggled = Signal()

    def __init__(self, pages, parent=None):
        """pages: [(key, label), ...]，顺序即页面顺序。"""
        super().__init__(parent)
        self.setObjectName('navBar')
        self._keys = [key for key, _ in pages]
        self._labels = [label for _key, label in pages]
        self._index = 0
        self._collapsed = False

        # ---- 页面链接：侧栏上部，选中态用 3px 黄左边线 ----
        self._items = []
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        links = QVBoxLayout()
        links.setContentsMargins(8, 8, 8, 8)
        links.setSpacing(2)
        for i, (key, label) in enumerate(pages):
            btn = QPushButton(label)
            btn.setObjectName('navLink')
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            page_icon = icon(_PAGE_ICONS.get(key, ''))
            if not page_icon.isNull():
                btn.setIcon(page_icon)
                btn.setIconSize(QSize(16, 16))
            btn.clicked.connect(lambda _=False, row=i: self._on_link(row))
            self._group.addButton(btn, i)
            links.addWidget(btn)
            self._items.append(btn)
        self._items[0].setChecked(True)

        # ---- 操作簇：钉在侧栏底部（顺序 = 使用频率：状态承诺 → 主题 → 主 CTA） ----
        # 只读徽标：把「不写入游戏」这条硬约束放在动作区最上方
        self.safe_badge = QLabel('只读')
        self.safe_badge.setObjectName('safeBadge')
        self.safe_badge.setFixedHeight(22)     # 胶囊高度固定：靠 padding 撑会在侧栏里长成一块黄砖
        self.safe_badge.setAlignment(Qt.AlignCenter)
        self.safe_badge.setToolTip('本工具只读游戏内存：不写入进程、不修改游戏安装目录内任何文件。')
        self.safe_badge.setAccessibleName('只读：不写入游戏进程、不修改安装目录')

        self.theme_btn = QPushButton('')
        self.theme_btn.setObjectName('navGhost')
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.clicked.connect(self.themeToggled)
        self.set_theme_state('dark')

        self.import_btn = QPushButton('从游戏导入')
        self.import_btn.setObjectName('primary')
        self.import_btn.setCursor(Qt.PointingHandCursor)
        self.import_btn.setToolTip('读取运行中游戏的角色数据（只读内存，需游戏内已进入角色）')
        self.import_btn.clicked.connect(self.importRequested)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addLayout(links)
        root.addStretch(1)
        # 操作簇按内容宽居中、不撑满侧栏：三个宽度悬殊的控件撑满同一栏会读成三块色带；
        # 垂直 14px 间距把它们分成三个可点的独立目标
        cluster = QVBoxLayout()
        cluster.setContentsMargins(12, 8, 12, 16)
        cluster.setSpacing(14)
        cluster.addWidget(self.safe_badge, 0, Qt.AlignHCenter)
        cluster.addWidget(self.theme_btn, 0, Qt.AlignHCenter)
        cluster.addWidget(self.import_btn, 0, Qt.AlignHCenter)
        root.addLayout(cluster)
        self.setFixedWidth(_WIDTH_EXPANDED)

        # ---- 上下文条：构建摘要 + 数据源（横向顶栏，由主窗口放到内容列上方；切页不丢） ----
        self.summary = QLabel('')
        self.summary.setObjectName('buildSummary')
        self.summary.setToolTip('当前构建：名称 / 等级 / 职业 / 基线期望 DPS。存取构建见「文件」菜单。')
        self.badge = QLabel('数据源：手工构建')
        self.badge.setObjectName('sourceBadge')
        ticker = QWidget()
        ticker.setObjectName('tickerBar')
        tick_lay = QHBoxLayout(ticker)
        tick_lay.setContentsMargins(16, 0, 16, 0)
        tick_lay.setSpacing(8)
        for text, widget in (('构建', self.summary), ('数据源', self.badge)):
            label = QLabel(text)
            label.setObjectName('tickerLabel')
            tick_lay.addWidget(label)
            tick_lay.addWidget(widget)
            tick_lay.addSpacing(18)
        tick_lay.addStretch(1)
        hint = QLabel('只读 · 不写入游戏进程')
        hint.setObjectName('tickerHint')
        tick_lay.addWidget(hint)
        # 34px：一行 12–13px 文字 + 上下留白；比 40px 省下的高度全部让给内容区
        ticker.setFixedHeight(34)
        # 不进自身布局：主窗口把它放到「侧栏右侧的内容列」顶部（见 app._build_ui）
        self.ticker = ticker

    # ---------------- 页面切换 ----------------
    def _on_link(self, row: int) -> None:
        if row == self._index:
            return
        self._index = row
        self.pageChanged.emit(row)

    def currentRow(self) -> int:
        return self._index

    def setCurrentRow(self, row: int) -> None:
        """编程式切页（快捷键 / 会话恢复 / 双击装备槽）：与点击走同一条信号。"""
        row = int(row)
        if not 0 <= row < len(self._items):
            return
        changed = row != self._index
        self._index = row
        self._items[row].setChecked(True)
        if changed:
            self.pageChanged.emit(row)

    # ---------------- 收起 / 展开 ----------------
    def toggle_collapsed(self) -> None:
        """Ctrl+B：手动在收起/展开间切换。"""
        self.set_collapsed(not self._collapsed)

    def set_collapsed_auto(self, window_width: int) -> None:
        """窗口变窄时自动收起（随拉宽自动展开）：收起态是「窄窗的形态」，不是持久偏好。"""
        self.set_collapsed(window_width < _AUTO_COLLAPSE_BELOW)

    def set_collapsed(self, collapsed: bool) -> None:
        """收起：链接只留图标、操作簇与上下文条整条隐藏，把横向空间还给内容区。

        动作簇收起后走菜单等效入口：「数据导入」菜单 = 导入 CTA、「视图 → 主题」= 主题开关。
        """
        collapsed = bool(collapsed)
        if collapsed == self._collapsed:
            return
        self._collapsed = collapsed
        for btn, label in zip(self._items, self._labels):
            btn.setText('' if collapsed else label)
            btn.setToolTip(label if collapsed else '')
            if collapsed:
                btn.setFixedWidth(46)          # 只留图标：宽度固定，避免空按钮按边距撑开
            else:
                # 不能用 setFixedWidth(0)：那是把最小/最大宽度都钉成 0，按钮会彻底消失
                btn.setMinimumWidth(0)
                btn.setMaximumWidth(16777215)  # QWIDGETSIZE_MAX
        for w in (self.safe_badge, self.theme_btn, self.import_btn, self.ticker):
            w.setVisible(not collapsed)
        self.setFixedWidth(_WIDTH_COLLAPSED if collapsed else _WIDTH_EXPANDED)

    def collapsed(self) -> bool:
        return self._collapsed

    # ---------------- 状态 ----------------
    def set_profile_summary(self, text: str, tooltip: str = '') -> None:
        self.summary.setText(text)
        if tooltip:
            self.summary.setToolTip(tooltip)

    def set_source_badge(self, text: str, tooltip: str = '') -> None:
        self.badge.setText(text)
        if tooltip:
            self.badge.setToolTip(tooltip)

    def set_theme_state(self, theme: str) -> None:
        """主题按钮写「点它会切到哪」而不是「当前是什么」：按钮语义是动作。"""
        target = 'light' if theme == 'dark' else 'dark'
        self.theme_btn.setText(f'{THEME_LABELS[target]}主题')
        self.theme_btn.setToolTip(f'切换到{THEME_LABELS[target]}主题')

    def set_import_state(self, enabled: bool, text: str = None, tooltip: str = '') -> None:
        """导入 CTA 与菜单项同源：可用性/临时态文案都由主窗口的指纹结论驱动。"""
        self.import_btn.setEnabled(bool(enabled))
        self.import_btn.setText(text or '从游戏导入')
        if tooltip:
            self.import_btn.setToolTip(tooltip)
