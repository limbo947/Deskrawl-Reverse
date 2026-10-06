# -*- coding: utf-8 -*-
"""装备对比结果区：两侧期望 DPS、Δ% 与乘区 A-D 分解条。

乘区取内核的确定性子式（type/crit/cond/vulnerable），不使用单次随机的暴击判定，
否则同一次对比的显示值会因 rng 抖动而无法与对拍锚点稳定一致。
"""
from PySide6.QtWidgets import (QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QProgressBar, QVBoxLayout, QWidget)

_MULT_ROWS = ['乘区A 类型/元素', '乘区B 暴击期望', '乘区C 条件池', '乘区D 易伤']


class _MultiplierBars(QWidget):
    """一侧的 4 条乘区条；同一类别在两侧之间归一化，便于横向比较。"""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        lay = QGridLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(QLabel(title), 0, 0, 1, 2)
        self.bars, self.values = [], []
        for i, name in enumerate(_MULT_ROWS, start=1):
            lay.addWidget(QLabel(name), i, 0)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setTextVisible(False)
            lay.addWidget(bar, i, 1)
            val = QLabel('—')
            val.setMinimumWidth(56)
            lay.addWidget(val, i, 2)
            self.bars.append(bar)
            self.values.append(val)

    def set_values(self, values, maxima):
        for bar, lab, v, m in zip(self.bars, self.values, values, maxima):
            bar.setValue(int(round(v / m * 100)) if m else 0)
            lab.setText(f'{v:.3f}')


class CompareView(QGroupBox):
    def __init__(self, parent=None):
        super().__init__('对比结果', parent)
        root = QVBoxLayout(self)

        head = QGridLayout()
        head.addWidget(QLabel('当前武器 DPS'), 0, 0)
        head.addWidget(QLabel('候选武器 DPS'), 0, 1)
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

        bars = QHBoxLayout()
        self.cur_bars = _MultiplierBars('当前武器乘区')
        self.cand_bars = _MultiplierBars('候选武器乘区')
        bars.addWidget(self.cur_bars, 1)
        bars.addWidget(self.cand_bars, 1)
        root.addLayout(bars)

        self.crit_info = QLabel('—')
        self.crit_info.setWordWrap(True)
        root.addWidget(self.crit_info)
        root.addStretch(1)

    @staticmethod
    def _multipliers(model, target) -> list:
        cc = model.crit_chance()
        cm = model.crit_multiplier()
        return [model.type_multiplier(), 1.0 + cc * (cm - 1.0),
                model.conditional_multiplier(target), 1.3 if target.vulnerable else 1.0]

    def set_result(self, result):
        self.cur_dps.setText(f'{result.current_dps:.1f}')
        self.cand_dps.setText(f'{result.candidate_dps:.1f}')
        self.delta.setText(f'{result.delta:+.1f} DPS（{result.delta_pct:+.2f}%）')
        # 涨/跌配色写在 style.qss 里，这里只切 objectName，避免颜色散落在代码中
        self.delta.setObjectName('deltaUp' if result.delta >= 0 else 'deltaDown')
        self.delta.style().unpolish(self.delta)
        self.delta.style().polish(self.delta)

        cur = self._multipliers(result.current_model, result.target)
        cand = self._multipliers(result.candidate_model, result.target)
        maxima = [max(a, b) for a, b in zip(cur, cand)]
        self.cur_bars.set_values(cur, maxima)
        self.cand_bars.set_values(cand, maxima)

        m0, m1 = result.current_model, result.candidate_model
        self.crit_info.setText(
            f'暴击率 {m0.crit_chance():.3f} → {m1.crit_chance():.3f}；'
            f'暴伤× {m0.crit_multiplier():.3f} → {m1.crit_multiplier():.3f}；'
            f'有效攻速已含武器基础攻速与面板攻速加成')
