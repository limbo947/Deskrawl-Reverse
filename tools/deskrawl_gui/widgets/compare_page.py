# -*- coding: utf-8 -*-
"""装备对比页：左侧 11 槽位当前/候选双编辑 + DPS 对比结果，右侧目标设置 + 参考技能。

目标（受击方）与本页的对比计算强耦合，从旧「右 dock」并入本页后，改目标与看结果的
视线动线一致；参考技能同理（它是换装预测/循环系数的基线口径），挂到目标基础卡片下方。
EquipmentEditor 内部已含 CompareView，这里只做横向组合与刷新中转。
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QScrollArea, QSplitter, QVBoxLayout, QWidget

from ..core.glossary import CALIBER_TEXT
from ..core.skill_service import pick_main_row
from .common import (SplitterSizesMixin, apply_narrow_stacking, cap_page_width,
                     page_header)
from .dps_meter import GameDpsMeter
from .equipment_editor import EquipmentEditor
from .skill_card import SkillCard
from .target_editor import TargetEditor


class ComparePage(SplitterSizesMixin, QWidget):
    changed = Signal()

    def __init__(self, profile, gd, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.gd = gd

        self.equipment_editor = EquipmentEditor(profile, gd)
        self.target_editor = TargetEditor(profile)
        self.skill_card = SkillCard(profile, gd)
        # 就位在「目标基础」正下方（TargetEditor 统一管布局，右栏滚动区仍只有一段）
        self.target_editor.insert_below_basic(self.skill_card)

        self._splitter = QSplitter()
        self._init_splitter_sizes(self._splitter)
        # 编辑区包滚动区：竖排时（1280×720）分到的高度可能低于其最小高度 568，无滚动就会裁切
        editor_scroll = QScrollArea()
        editor_scroll.setWidgetResizable(True)
        editor_scroll.setWidget(self.equipment_editor)
        editor_scroll.setFrameShape(QScrollArea.NoFrame)
        self._splitter.addWidget(editor_scroll)
        # 目标设置是窄表单，滚动区兜底；固定较窄宽度把空间留给对比结果
        target_scroll = QScrollArea()
        target_scroll.setWidgetResizable(True)
        target_scroll.setWidget(self.target_editor)
        target_scroll.setFrameShape(QScrollArea.NoFrame)
        target_scroll.setMinimumWidth(340)
        # 实测卡片钉在右栏底部（滚动区之外）：它是轮询读数，目标设置再长也不该把它滚走
        self.dps_meter = GameDpsMeter()
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(12)
        right_lay.addWidget(target_scroll, 1)
        right_lay.addWidget(self.dps_meter, 0)
        self._splitter.addWidget(right)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        # 7/3 三页统一。不能取文档的 8/4：编辑器（双编辑卡 + 结论区）最小宽 ~890，
        # 8/4 需要 ≥1373 的窗宽才不出横向滚动；70/30 在 1321 就够（见 resizeEvent 阈值）
        self._splitter.setSizes([960, 412])

        root = QVBoxLayout()
        root.setContentsMargins(24, 12, 24, 12)
        root.setSpacing(8)    # 卡片垂直间距 12→8（三页统一，见 assembly_center）
        # 副标题只留一句话动线；「当前件只读」「多件同换」这类口径收进 ⓘ（V11）。
        # 职业只读展示上提到 hero 右侧：它说明技能表按谁列，属于页级口径而非编辑参数。
        root.addWidget(page_header(
            '装备对比', '选一个槽 → 填候选 → 看 Δ%', CALIBER_TEXT,
            right=self.equipment_editor.class_label))
        root.addWidget(self._splitter, 1)
        cap_page_width(self, root)    # 内容宽封顶 1440 居中

        self.target_editor.changed.connect(self.changed)
        self.skill_card.changed.connect(self.changed)         # 参考技能 → 技能表与预测基线
        self.equipment_editor.changed.connect(self.changed)   # 职业 → 技能下拉选项重建
        # 词条/候选/槽位改动只走本页局部刷新，必须据此重喂期望，否则「换装预测」停在旧基线
        self.equipment_editor.resultsChanged.connect(self._sync_meter)
        self.refresh()

    def _sync_meter(self):
        """把最新主力技能期望喂给实测框（换装预测 = 候选期望 × 系数）。

        空候选时技能行为空，若不说原因，诊断行会把「没填候选」误报成「没设参考技能」。
        """
        empty = bool(getattr(self.equipment_editor, 'last_candidate_empty', False))
        self.dps_meter.set_expectation(
            pick_main_row(self.equipment_editor.last_skill_rows, self.profile),
            note='候选未填写：填好候选后再给换装预测' if empty else '')

    def refresh(self):
        """重算参考技能卡与对比结果（职业/等级/符文的变化都在这里反映），并同步实测框期望。"""
        self.skill_card.refresh()
        self.equipment_editor.refresh()      # 内部会发 resultsChanged → _sync_meter
        self._sync_meter()                   # 期望未变时也保证重绘一次

    def reload(self):
        """换数据源后回填全部输入（装备编辑器 + 目标 + 参考技能），再重算。"""
        self.equipment_editor.reload()
        self.target_editor.reload()
        self.skill_card.reload()
        self.refresh()

    def resizeEvent(self, event):
        """窄窗口把「装备编辑器 | 目标栏」改为上下堆叠（见 common.apply_narrow_stacking）。

        阈值比其他页高（1360）：编辑器最小宽 ~890，7/3 分栏下需要 ≥1340 的窗宽才能并排
        不出横向滚动（8/4 则要 ≥1373）；竖排后主区拿到整宽，结论读得清。
        """
        super().resizeEvent(event)
        apply_narrow_stacking(self._splitter, event.size().width(), threshold=1360,
                              h_sizes=self._h_sizes)
        self.equipment_editor.set_result_first(self._splitter.orientation() == Qt.Vertical)
        self._remember_splitter()
