# -*- coding: utf-8 -*-
"""装备对比结果区：两侧期望 DPS、Δ% 与逐技能秒伤对比表。

展示原则「先结论后细节」：顶部三格只给 当前/候选/变化 三个数；暴击、主属性、攻速等
过程量不占行，收进 Δ 标签的 tooltip（要查再悬停）。技能表只留 技能/当前/候选/Δ% 四列。
技能秒伤由 skill_service 计算（🔶 估算口径，见其模块说明），本视图只负责渲染。
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QGridLayout, QGroupBox, QHeaderView,
                               QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout)

from deskrawl_calc import stat_name

_SKILL_COLS = ['技能', '当前', '候选', 'Δ%']


class CompareView(QGroupBox):
    def __init__(self, parent=None):
        super().__init__('对比结果', parent)
        root = QVBoxLayout(self)

        head = QGridLayout()
        self.cur_title = QLabel('当前 DPS')
        self.cand_title = QLabel('候选 DPS')
        head.addWidget(self.cur_title, 0, 0)
        head.addWidget(self.cand_title, 0, 1)
        head.addWidget(QLabel('变化'), 0, 2)
        self.cur_dps = QLabel('—')
        self.cur_dps.setObjectName('dpsBig')
        self.cand_dps = QLabel('—')
        self.cand_dps.setObjectName('dpsBig')
        self.delta = QLabel('—')
        self.delta.setObjectName('deltaUp')
        head.addWidget(self.cur_dps, 1, 0)
        head.addWidget(self.cand_dps, 1, 1)
        head.addWidget(self.delta, 1, 2)
        root.addLayout(head)

        self.skill_hint = QLabel('技能秒伤对比：—')
        root.addWidget(self.skill_hint)
        self.skill_table = QTableWidget(0, len(_SKILL_COLS))
        self.skill_table.setHorizontalHeaderLabels(_SKILL_COLS)
        self.skill_table.verticalHeader().setVisible(False)
        self.skill_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.skill_table.setAlternatingRowColors(True)
        self.skill_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        root.addWidget(self.skill_table, 1)

    @staticmethod
    def _primary_text(model) -> str:
        """攻击伤害的职业主属性加成（bjr：×(1+Final/100)）；未设置时明示。"""
        if model.primary_stat is None:
            return '主属性未设置'
        return f'{stat_name(int(model.primary_stat))} ×{model.primary_stat_multiplier():.3f}'

    def set_result(self, result):
        self.cur_title.setText(f'当前{result.slot_label} DPS')
        self.cand_title.setText(f'候选{result.slot_label} DPS')
        self.cur_dps.setText(f'{result.current_dps:.1f}')
        self.cand_dps.setText(f'{result.candidate_dps:.1f}')
        self.delta.setText(f'{result.delta:+.1f} DPS（{result.delta_pct:+.2f}%）')
        # 涨/跌配色写在 style.qss 里，这里只切 objectName，避免颜色散落在代码中
        self.delta.setObjectName('deltaUp' if result.delta >= 0 else 'deltaDown')
        self.delta.style().unpolish(self.delta)
        self.delta.style().polish(self.delta)

        # 过程量（暴击/暴伤/主属性/攻速）不占行：要查时悬停 Δ 即可
        m0, m1 = result.current_model, result.candidate_model
        self.delta.setToolTip(
            f'暴击率 {m0.crit_chance():.3f} → {m1.crit_chance():.3f}\n'
            f'暴伤× {m0.crit_multiplier():.3f} → {m1.crit_multiplier():.3f}\n'
            f'攻击伤害主属性加成 {self._primary_text(m0)} → {self._primary_text(m1)}\n'
            f'有效攻速已含武器基础攻速与面板攻速加成')

    def set_skills(self, rows):
        """渲染逐技能秒伤对比（技能 · 当前 · 候选 · Δ%）。空表给出原因提示。"""
        if not rows:
            self.skill_hint.setText('技能秒伤对比：未设置职业或无伤害技能（导入自动识别「职业」）')
            self.skill_table.setRowCount(0)
            return
        self.skill_hint.setText(f'技能秒伤对比（{len(rows)} 项，期望值口径；换装看 Δ% 即可）')
        self.skill_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            cells = [r.ability_name, f'{r.current_dps:.0f}', f'{r.candidate_dps:.0f}',
                     f'{r.delta_pct:+.2f}%']
            for j, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if j >= 1:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.skill_table.setItem(i, j, item)
