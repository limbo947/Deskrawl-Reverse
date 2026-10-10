# -*- coding: utf-8 -*-
"""角色页：左侧角色面板编辑（等级/三维/巅峰/技能）+ 右侧属性明细表。

技能等级的唯一编辑入口在此页（历史上装备对比页也有一个，已随重构移除）；
属性明细自动按「内存导入→游戏面板口径 / 手工构建→计算口径」切换。
"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QScrollArea, QSplitter, QVBoxLayout, QWidget

from .common import page_header
from .panel_editor import PanelEditor
from .stat_table import StatTable


class RolePage(QWidget):
    changed = Signal()

    def __init__(self, profile, gd, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.gd = gd

        self.panel_editor = PanelEditor(profile, gd)
        self.stat_table = StatTable()

        splitter = QSplitter()
        # 面板是固定宽度的表单，放进滚动区兜底小窗口；明细表吃剩余宽度
        panel_scroll = QScrollArea()
        panel_scroll.setWidgetResizable(True)
        panel_scroll.setWidget(self.panel_editor)
        panel_scroll.setFrameShape(QScrollArea.NoFrame)
        panel_scroll.setMinimumWidth(330)
        splitter.addWidget(panel_scroll)
        splitter.addWidget(self.stat_table)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([420, 760])

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.addWidget(page_header('角色', '编辑等级 / 主属性 / 巅峰点数与参考技能；右侧为属性明细（内存导入后自动切换游戏面板口径）'))
        root.addWidget(splitter, 1)

        self.panel_editor.changed.connect(self.changed)
        self.refresh()

    def refresh(self):
        """重算属性明细（口径随 profile.panel 有无自动切换）；顺带同步技能下拉的职业选项。"""
        self.panel_editor.refresh_skill_options()
        if self.profile.panel:
            self.stat_table.set_panel_view(self.profile.panel)
        else:
            self.stat_table.set_sheet(self.profile.to_sheet(self.gd))

    def reload(self):
        """换数据源（导入/加载构建）后回填编辑控件，再重算明细。"""
        self.panel_editor.reload()
        self.refresh()
