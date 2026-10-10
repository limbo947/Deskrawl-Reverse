# -*- coding: utf-8 -*-
"""装备对比页：左侧 11 槽位当前/候选双编辑 + DPS 对比结果，右侧目标设置。

目标（受击方）与本页的对比计算强耦合，从旧「右 dock」并入本页后，改目标与看结果的
视线动线一致；EquipmentEditor 内部已含 CompareView，这里只做横向组合。
"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QSplitter, QVBoxLayout, QWidget

from ..core.skill_service import pick_main_row
from .common import page_header
from .dps_meter import GameDpsMeter
from .equipment_editor import EquipmentEditor
from .target_editor import TargetEditor


class ComparePage(QWidget):
    changed = Signal()

    def __init__(self, profile, gd, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.gd = gd

        self.equipment_editor = EquipmentEditor(profile, gd)
        self.target_editor = TargetEditor(profile)

        splitter = QSplitter()
        splitter.addWidget(self.equipment_editor)
        # 目标设置是窄表单，滚动区兜底；固定较窄宽度把空间留给对比结果
        target_scroll = QScrollArea()
        target_scroll.setWidgetResizable(True)
        target_scroll.setWidget(self.target_editor)
        target_scroll.setFrameShape(QScrollArea.NoFrame)
        target_scroll.setMinimumWidth(300)
        splitter.addWidget(target_scroll)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([980, 340])

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        head = QHBoxLayout()
        head.addWidget(page_header('装备对比', '选择槽位编辑当前/候选装备，或从背包载入候选；目标设置含「训练假人」预设（与游戏 DPS 计同口径）'), 1)
        # 游戏实测值：期望口径旁边随时可对照的真实计伤（只读轮询）
        self.dps_meter = GameDpsMeter()
        head.addWidget(self.dps_meter)
        root.addLayout(head)
        root.addWidget(splitter, 1)

        self.target_editor.changed.connect(self.changed)
        self.equipment_editor.changed.connect(self.changed)   # 职业 → 角色页技能选项同步
        # 词条/候选/槽位改动只走本页局部刷新，必须据此重喂期望，否则「换装预测」停在旧基线
        self.equipment_editor.resultsChanged.connect(self._sync_meter)
        self.refresh()

    def _sync_meter(self):
        """把最新主力技能期望喂给实测框（换装预测 = 候选期望 × 系数）。"""
        self.dps_meter.set_expectation(
            pick_main_row(self.equipment_editor.last_skill_rows, self.profile))

    def refresh(self):
        """重算对比结果，并同步实测框期望基线。"""
        self.equipment_editor.refresh()      # 内部会发 resultsChanged → _sync_meter
        self._sync_meter()                   # 期望未变时也保证重绘一次

    def reload(self):
        """换数据源后回填全部输入（装备编辑器 + 目标），再重算。"""
        self.equipment_editor.reload()
        self.target_editor.reload()
        self.refresh()
