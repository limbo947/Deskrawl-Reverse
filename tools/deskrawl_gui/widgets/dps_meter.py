# -*- coding: utf-8 -*-
"""游戏 DPS 计实测值组件：1s 轮询运行中游戏的 TrainingDpsMeterUI（只读）。

展示原则「先结论后细节」：主行只给一个答案——候选换上去后的预测实战 DPS 与涨跌%；
实测值/期望值/系数这三级诊断数字缩到次行弱化显示，细节进 tooltip，避免数字堆叠看不出重点。
换算：循环系数 = 实测 DPS ÷ 主力技能期望（当前侧，含全部天赋加成）；
      候选预测实战 = 主力技能期望（候选侧）× 系数（线性近似：换单件不改循环结构）。
读数失败（游戏未开/不在假人图）降级为弱化短文案，不弹窗打断。
"""
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from ..core.dps_meter import read_dps_meter
from ..core.memory_import import MemoryImportError

_POLL_MS = 1000


def fmt_compact(v: float) -> str:
    """游戏计伤的紧凑显示（27B / 23.0M / 1.2K）。"""
    for div, suffix in ((1e9, 'B'), (1e6, 'M'), (1e3, 'K')):
        if abs(v) >= div:
            return f'{v / div:.1f}{suffix}'
    return f'{v:.0f}'


# 常见失败态的短文案（长解释走 tooltip；完整分档见 app.describe_import_error）
_SHORT_ERROR = {
    'no_process': '游戏未运行',
    '': '未定位到 DPS 计（需在训练假人地图）',
}


class GameDpsMeter(QFrame):
    """只读实测框：主行 = 结论（候选预测实战 + 涨跌%），次行 = 诊断（实测/期望/系数）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('dpsMeter')
        self.setTitle = QLabel('游戏实测（训练假人）')
        self.setTitle.setObjectName('dpsMeterTitle')
        self.verdict = QLabel('—')
        self.verdict.setObjectName('dpsMeterValue')
        self.verdict.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.diag = QLabel('')
        self.diag.setObjectName('dpsMeterDiag')
        self.diag.setWordWrap(True)
        self.diag.setVisible(False)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(2)
        lay.addWidget(self.setTitle)
        lay.addWidget(self.verdict)
        lay.addWidget(self.diag)

        # 期望基线（当前/候选的主力技能期望，页面层在刷新链上喂进来）
        self._expect_cur = None
        self._expect_cand = None
        self._main_label = ''
        self._last = None          # 最近一次读数；编辑词条时据此即时重绘，不再重复读内存
        self._timer = QTimer(self)
        self._timer.setInterval(_POLL_MS)
        self._timer.timeout.connect(self.poll)
        self._timer.start()
        self.poll()

    def set_expectation(self, main_row):
        """喂入主力技能期望行（skill_service.pick_main_row 的结果；None=不可用）。

        只重绘不读内存：词条编辑会频繁触发，1s 定时器会负责刷新实测值。
        """
        if main_row is None or main_row.current_dps <= 0:
            self._expect_cur = self._expect_cand = None
        else:
            self._expect_cur = float(main_row.current_dps)
            self._expect_cand = float(main_row.candidate_dps)
            self._main_label = main_row.ability_name
        self._render()

    def _apply_trend(self, trend):
        """涨跌配色走 QSS 属性选择器（颜色不散落代码）；属性变更需重新 polish。"""
        self.verdict.setProperty('trend', trend or '')
        self.verdict.style().unpolish(self.verdict)
        self.verdict.style().polish(self.verdict)

    def poll(self):
        """一次轮询：读游戏实测值（失败降级短文案），再渲染。"""
        try:
            self._last = read_dps_meter()
        except MemoryImportError as exc:
            self._last = None
            self._error = exc
        self._render()

    def _render(self):
        """依据「最近读数 + 期望基线」渲染；无读数时显示失败短文案。"""
        if self._last is None:
            exc = getattr(self, '_error', None)
            code = getattr(exc, 'code', '') if exc else ''
            self.verdict.setText(_SHORT_ERROR.get(code, str(exc) if exc else '—'))
            self.verdict.setToolTip(str(exc) if exc else '')
            self._apply_trend(None)
            self.diag.setVisible(False)
            self.setProperty('state', 'offline')
            return
        self.setProperty('state', 'live')
        live, total = float(self._last['dps']), float(self._last['total'])
        base_tip = (f'精确值：当前每秒 {live:.2f}；总伤害 {total:.0f}\n'
                    f'（读自运行中游戏的 DPS 计，1s 轮询；游戏里点「重置」后重新累计）')
        if self._expect_cur and self._expect_cand and live > 0:
            self._show_prediction(live, base_tip)
        else:
            self.verdict.setText(f'当前每秒 {fmt_compact(live)}')
            self._apply_trend(None)
            self.verdict.setToolTip(base_tip)
            self.diag.setText('参考技能未设置：设好「参考技能」后这里会直接给候选预测')
            self.diag.setVisible(True)

    def _show_prediction(self, live: float, base_tip: str):
        """主行给结论（换装预测 + 涨跌），次行给诊断。"""
        factor = live / self._expect_cur
        predicted = self._expect_cand * factor
        pct = (predicted / live - 1.0) if live else 0.0
        self.verdict.setText(f'换装预测 {fmt_compact(predicted)}　{pct:+.1%}')
        self._apply_trend('up' if pct >= 0 else 'down')
        self.verdict.setToolTip(
            base_tip
            + f'\n\n推算：系数 = 实测 {live:.0f} ÷ 主力技能期望（当前侧，含天赋）'
              f'{self._expect_cur:.0f} = ×{factor:.2f}\n'
              f'换装预测 = 候选期望 {self._expect_cand:.0f} × 系数'
              f'（线性近似：换单件不改循环结构；基线技能：{self._main_label}）')
        self.diag.setText(f'实测 {fmt_compact(live)}　·　期望 {fmt_compact(self._expect_cur)}'
                          f'　·　系数 ×{factor:.1f}')
        self.diag.setVisible(True)
