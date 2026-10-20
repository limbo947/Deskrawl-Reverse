# -*- coding: utf-8 -*-
"""结论对比条：当前 DPS 与候选 DPS 的横向长度对比。

为什么在 Δ% 之外再画两根条：主结论是六位数量级的数字（199042），读「涨了还是跌了」得先比
数字头一位；两根条的长度差是同一件事的图形通道，一眼可判，且对色弱用户不依赖红绿。
刻度取 1000 而不是 100：百分比刻度下 1.2% 的差异会被量化成 1 格，看不出换装级差异。

为什么不再给两根条各配一行文字：上方三格已经写着「当前 / 候选 / 变化」与两个精确值，
重复的标签只占高度；条的身份由顺序（上=当前、下=候选）与悬停说明承担。

空候选时不画条（返回值交给调用方决定是否整块隐藏）：0 DPS 的条会读成「暴跌」。
"""
from PySide6.QtWidgets import QProgressBar, QVBoxLayout, QWidget

from ..core.format import fmt_dps

_SCALE = 1000


class DeltaBar(QWidget):
    """上下两根细条（上=当前、下=候选），按两侧较大者归一，候选侧总是占满。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._slot = ''
        self.cur_bar = self._bar('deltaBarCur')
        self.cand_bar = self._bar('deltaBarCand')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(4)
        lay.addWidget(self.cur_bar)
        lay.addWidget(self.cand_bar)
        self.setToolTip('上：当前装备｜下：候选装备（长度按较大者归一）')

    @staticmethod
    def _bar(object_name: str) -> QProgressBar:
        bar = QProgressBar()
        bar.setObjectName(object_name)      # 颜色只在 style.qss 定义，代码不抄色值
        bar.setRange(0, _SCALE)
        bar.setTextVisible(False)
        # 高度与 QSS 的 #deltaBar* min/max-height 取同一个值：setFixedHeight 会盖掉 QSS，
        # 两边不一致时改样式表不生效（原先代码 6 / QSS 8）
        bar.setFixedHeight(8)
        return bar

    def set_values(self, current_dps: float, candidate_dps: float):
        """按较大者归一；两侧相等时两根都满格（Δ=0 的正确读法）。"""
        cur, cand = max(0.0, float(current_dps)), max(0.0, float(candidate_dps))
        top = max(cur, cand)
        if top <= 0:
            self.cur_bar.setValue(0)
            self.cand_bar.setValue(0)
        else:
            self.cur_bar.setValue(int(round(cur / top * _SCALE)))
            self.cand_bar.setValue(int(round(cand / top * _SCALE)))
        self.cur_bar.setToolTip(f'当前{self._slot}：{fmt_dps(cur)} DPS')
        self.cand_bar.setToolTip(f'候选{self._slot}：{fmt_dps(cand)} DPS')

    def set_slot(self, slot_label: str) -> None:
        """记下槽名（写进 tooltip，避免用户以为这两根条是「全部装备」的总 DPS）。"""
        self._slot = str(slot_label or '')

    def set_trend(self, trend: str) -> None:
        """候选条按涨跌着色（QSS 的 [trend] 选择器）：与上方 Δ 数字同一条语义通道。"""
        trend = trend if trend in ('up', 'down') else ''
        self.cand_bar.setProperty('trend', trend)
        self.cand_bar.style().unpolish(self.cand_bar)
        self.cand_bar.style().polish(self.cand_bar)


__all__ = ['DeltaBar']
