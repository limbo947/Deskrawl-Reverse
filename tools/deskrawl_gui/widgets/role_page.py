# -*- coding: utf-8 -*-
"""角色页：主区属性明细 + 当前装备总览，右侧角色面板（等级/三维/巅峰点数）。

布局按产品页「主区 + 侧栏」结构（三页统一 7/3，见 docs/plan/GUI设计规范 §5）：
主区放「读的东西」（两张宽表），侧栏放「调的东西」（表单）。
与旧版左右相反的理由：属性表 6 列、装备总览 4 列，窄栏里每列都挤；面板只有几个输入框，
放侧栏更稳，也让 11 槽总览能一次读全（不再被侧栏滚动区截掉后几行）。

参考技能的编辑入口在装备对比页（widgets/skill_card.py）：它只服务换装预测的口径，
与目标设置、实测框同屏才顺手；本页只留与角色本体相关的输入。
属性明细自动按「内存导入→游戏面板口径 / 手工构建→计算口径」切换。
"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget

from ..core.glossary import ROLE_PANEL_TEXT
from .common import (SplitterSizesMixin, apply_narrow_stacking, cap_page_width,
                     page_header, scroll_host)
from .panel_editor import PanelEditor
from .slot_overview import SlotOverview
from .stat_table import StatTable


class RolePage(SplitterSizesMixin, QWidget):
    changed = Signal()
    slotActivated = Signal(int)      # 总览双击 → 主窗口切页并选中该槽

    def __init__(self, profile, gd, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.gd = gd

        self.panel_editor = PanelEditor(profile, gd)
        self.slot_overview = SlotOverview(profile)
        self.stat_table = StatTable()

        self._splitter = QSplitter()
        self._init_splitter_sizes(self._splitter)
        # 主区 = 属性明细（吃剩余高度）+ 11 槽当前装备（固定 11 行高）：两张都是宽表
        main = QWidget()
        main_lay = QVBoxLayout(main)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(12)
        main_lay.addWidget(self.stat_table, 1)
        main_lay.addWidget(self.slot_overview, 0)
        # 两栏都进滚动区：主区是「宽表 + 固定 11 行」，窗口压到最小高度时它先被裁，
        # 而 11 槽总览关了自己的滚动条（避免双层滚动）——没有这一层就等于静默丢行。
        # 侧栏 = 角色面板（等级/三维/巅峰），同样由滚动接管溢出。
        self._splitter.addWidget(scroll_host(main))
        self._splitter.addWidget(scroll_host(self.panel_editor, minimum_width=340))
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        # 7/3 三页统一（8/4 需要更宽的侧栏放表单，且对比页编辑器有 ~890px 最小宽约束）
        self._splitter.setSizes([960, 412])

        root = QVBoxLayout()
        root.setContentsMargins(24, 12, 24, 12)
        root.setSpacing(8)    # 卡片垂直间距 12→8（三页统一，见 assembly_center）
        # 副标题手动断成两行：自动换行会折出三行、顶过 32px 大字（用户 2026-10-21）；
        # 断点放在「；」后，两行各说一件事（看什么 / 怎么生效）
        root.addWidget(page_header('角色', '主区看属性明细，右侧改角色面板与装备；\n改动即时重算',
                                   ROLE_PANEL_TEXT))
        root.addWidget(self._splitter, 1)
        cap_page_width(self, root)    # 内容宽封顶 1440 居中（超宽屏不把宽表拉成超长行）

        self.panel_editor.changed.connect(self.changed)
        self.slot_overview.slotActivated.connect(self.slotActivated)
        self.refresh()

    def resizeEvent(self, event):
        """窄窗口把「明细表 | 面板」改为上下堆叠（见 common.apply_narrow_stacking）。"""
        super().resizeEvent(event)
        apply_narrow_stacking(self._splitter, event.size().width(), h_sizes=self._h_sizes)
        self._remember_splitter()

    def refresh(self):
        """重算属性明细与当前装备总览（口径随 profile.panel 有无自动切换）。"""
        self.slot_overview.reload()
        if self.profile.panel:
            self.stat_table.set_panel_view(self.profile.panel)
        else:
            self.stat_table.set_sheet(self.profile.to_sheet(self.gd))

    def reload(self):
        """换数据源（导入/加载构建）后回填编辑控件，再重算明细。"""
        self.panel_editor.reload()
        self.refresh()
