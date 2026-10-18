# -*- coding: utf-8 -*-
"""角色页：左侧角色面板编辑（等级/三维/巅峰点数）+ 右侧属性明细表。

参考技能的编辑入口在装备对比页（widgets/skill_card.py）：它只服务换装预测的口径，
与目标设置、实测框同屏才顺手；本页只留与角色本体相关的输入。
属性明细自动按「内存导入→游戏面板口径 / 手工构建→计算口径」切换。
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QScrollArea, QSplitter, QVBoxLayout, QWidget

from ..core.glossary import ROLE_PANEL_TEXT
from .common import SplitterSizesMixin, apply_narrow_stacking, page_header
from .panel_editor import PanelEditor
from .stat_table import StatTable


class RolePage(SplitterSizesMixin, QWidget):
    changed = Signal()

    def __init__(self, profile, gd, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.gd = gd

        self.panel_editor = PanelEditor(profile, gd)
        self.stat_table = StatTable()

        self._splitter = QSplitter()
        self._init_splitter_sizes(self._splitter)
        # 面板是固定宽度的表单，放进滚动区兜底小窗口；明细表吃剩余宽度
        panel_scroll = QScrollArea()
        panel_scroll.setWidgetResizable(True)
        panel_scroll.setWidget(self.panel_editor)
        panel_scroll.setFrameShape(QScrollArea.NoFrame)
        panel_scroll.setMinimumWidth(330)
        self._splitter.addWidget(panel_scroll)
        self._splitter.addWidget(self.stat_table)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        # 左栏内容实测约 300px 宽，给到 420 会留出一条无信息的空带；余量让给明细表
        self._splitter.setSizes([340, 840])

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.addWidget(page_header('角色', '编辑等级 / 职业主属性 / 巅峰点数',
                                   ROLE_PANEL_TEXT))
        root.addWidget(self._splitter, 1)

        self.panel_editor.changed.connect(self.changed)
        self.refresh()

    def resizeEvent(self, event):
        """窄窗口把「面板 | 明细表」改为上下堆叠（见 common.apply_narrow_stacking）。"""
        super().resizeEvent(event)
        apply_narrow_stacking(self._splitter, event.size().width())
        self._remember_splitter()

    def refresh(self):
        """重算属性明细（口径随 profile.panel 有无自动切换）。"""
        if self.profile.panel:
            self.stat_table.set_panel_view(self.profile.panel)
        else:
            self.stat_table.set_sheet(self.profile.to_sheet(self.gd))

    def reload(self):
        """换数据源（导入/加载构建）后回填编辑控件，再重算明细。"""
        self.panel_editor.reload()
        self.refresh()
