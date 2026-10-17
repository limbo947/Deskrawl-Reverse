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

# Δ 中性阈值：界面按 1 位小数显示，|Δ| < 0.05 时读出来就是"+0.0"——这种情况必须用中性色，
# 否则「没变化」会被读成「提升」（旧实现 `delta >= 0 → deltaUp` 把 Δ=0 也上绿）。
_FLAT_DELTA = 0.05


def _delta_object_name(delta: float) -> str:
    """Δ 三态 → QSS 的 objectName（颜色只在 style.qss 定义）。"""
    if abs(float(delta)) < _FLAT_DELTA:
        return 'deltaFlat'
    return 'deltaUp' if delta > 0 else 'deltaDown'


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

        # 对比口径告警（F8）：_negate 卸下不可逆词条（连乘 type 2）时会丢项使 Δ 失真，
        # 内容非空才显示；用 modeBanner 的告警样式，与 α 横幅同一视觉语言。
        self.warn_label = QLabel('')
        self.warn_label.setObjectName('modeBanner')
        self.warn_label.setWordWrap(True)
        self.warn_label.setVisible(False)
        root.addWidget(self.warn_label)

        self.skill_hint = QLabel('技能秒伤对比：—')
        root.addWidget(self.skill_hint)
        self.skill_table = QTableWidget(0, len(_SKILL_COLS))
        self.skill_table.setHorizontalHeaderLabels(_SKILL_COLS)
        self.skill_table.verticalHeader().setVisible(False)
        self.skill_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.skill_table.setAlternatingRowColors(True)
        # 技能表已在「对比结果」分组框内：自身的表格框 + 网格线会叠加成多层矩形线框
        self.skill_table.setShowGrid(False)
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
        self.delta.setText(f'{result.delta_pct:+.2f}%（{result.delta:+.1f} DPS）')
        # 涨/跌配色写在 style.qss 里，这里只切 objectName，避免颜色散落在代码中
        self.delta.setObjectName(_delta_object_name(result.delta))
        self.delta.style().unpolish(self.delta)
        self.delta.style().polish(self.delta)

        warns = list(getattr(result, 'warnings', None) or [])
        self.warn_label.setVisible(bool(warns))
        if warns:
            self.warn_label.setText('对比口径告警：' + '；'.join(warns))

        # 过程量（暴击/暴伤/主属性/攻速）不占行：要查时悬停 Δ 即可。末尾一句说明顶部 Δ 的
        # 口径边界（F6）：它是不带技能标签的普攻期望，标签/冷却类词条只体现在下方技能表。
        m0, m1 = result.current_model, result.candidate_model
        self.delta.setToolTip(
            f'暴击率 {m0.crit_chance():.3f} → {m1.crit_chance():.3f}\n'
            f'暴伤× {m0.crit_multiplier():.3f} → {m1.crit_multiplier():.3f}\n'
            f'攻击伤害主属性加成 {self._primary_text(m0)} → {self._primary_text(m1)}\n'
            f'有效攻速已含武器基础攻速与面板攻速加成\n'
            f'顶部 Δ 为无标签普攻口径：普攻/强攻伤害(33/34)与冷却缩减(13)只作用于下方技能表')

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
