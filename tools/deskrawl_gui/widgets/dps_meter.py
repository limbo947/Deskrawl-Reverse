# -*- coding: utf-8 -*-
"""游戏 DPS 计实测值组件：1s 轮询运行中游戏的 TrainingDpsMeterUI（只读）。

展示原则「先结论后细节」：主行只给一个答案——候选换上去后的预测实战 DPS 与涨跌%；
实测值/期望值/系数这三级诊断数字缩到次行弱化显示，细节进 tooltip，避免数字堆叠看不出重点。
换算：循环系数 = 实测 DPS ÷ 主力技能期望（当前侧，含全部天赋加成）；
      候选预测实战 = 主力技能期望（候选侧）× 系数（线性近似：换单件不改循环结构）。
读数失败（游戏未开/不在假人图）降级为弱化短文案，不弹窗打断。
"""
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout)

from ..core.dps_meter import read_dps_meter
from ..core.memory_import import MemoryImportError

_POLL_MS = 1000
# 离线态（游戏没开/不在假人图）降频：这类情形下每秒枚举一次进程+扫内存纯属浪费
_POLL_OFFLINE_MS = 5000


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

# 中性带：读数按 1 位小数百分比显示，|Δ| < 0.05% 读出来就是「+0.0%」——这时必须走中性色，
# 否则「换上与当前完全相同的候选」会显示成一次绿色上涨（与对比页/技能表的 flat 三态同义）
_FLAT_PREDICT = 0.0005


def trend_of(pct: float) -> str:
    """换装预测的涨跌三态：'up' / 'down' / ''（空 = 中性，沿用数值的黄系基色）。"""
    pct = float(pct)
    if abs(pct) < _FLAT_PREDICT:
        return ''
    return 'up' if pct > 0 else 'down'


class GameDpsMeter(QFrame):
    """只读实测框：主行 = 结论（候选预测实战 + 涨跌%），次行 = 诊断（实测/期望/系数）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('dpsMeter')
        self.title_label = QLabel('游戏实测（训练假人）')
        self.title_label.setObjectName('dpsMeterTitle')
        self.verdict = QLabel('—')
        self.verdict.setObjectName('dpsMeterValue')
        self.verdict.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.diag = QLabel('')
        self.diag.setObjectName('dpsMeterDiag')
        self.diag.setWordWrap(True)
        self.diag.setVisible(False)

        # 轮询开关：由页面可见性驱动（app 切页置位）+ 用户可关实时刷新改手动
        self._active = False
        self._live = True
        self.live_check = QCheckBox('实时')
        self.live_check.setChecked(True)
        self.live_check.setToolTip('每秒读一次运行中游戏的 DPS 计（只读内存）。\n'
                                  '关掉后不再自动读；停在其它页面时本组件也会自动暂停。')
        self.live_check.toggled.connect(self._on_live_toggled)
        self.read_btn = QPushButton('读一次')
        self.read_btn.setToolTip('现在读一次游戏 DPS 计（关掉「实时」后用它手动刷新）。')
        self.read_btn.clicked.connect(self.poll)
        ctrl = QHBoxLayout()
        ctrl.setSpacing(6)
        ctrl.addWidget(self.title_label)
        ctrl.addStretch(1)
        ctrl.addWidget(self.live_check)
        ctrl.addWidget(self.read_btn)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)   # 紧凑卡统一 12px 内距（原上下 8 偏挤）
        lay.setSpacing(2)
        lay.addLayout(ctrl)
        lay.addWidget(self.verdict)
        lay.addWidget(self.diag)

        # 期望基线（当前/候选的主力技能期望，页面层在刷新链上喂进来）
        self._expect_cur = None
        self._expect_cand = None
        self._main_label = ''
        self._expect_note = ''      # 期望缺失时的原因（候选未填写 ≠ 参考技能未设置）
        self._last = None          # 最近一次读数；编辑词条时据此即时重绘，不再重复读内存
        self._has_read = False     # 是否读过一次：未读之前不把「没读到」当结论显示
        self._timer = QTimer(self)
        self._timer.setInterval(_POLL_MS)
        self._timer.timeout.connect(self.poll)
        self._sync_timer()
        # 构造期只画中性占位、不读内存：停在角色页/装配中心（甚至没开对比页）时不该扫进程。
        # 首次切到对比页由 set_active 触发真读（因此这里也不能显示「未定位到 DPS 计」那种结论）。
        self._render()

    # ---------------- 轮询启停 ----------------
    def set_active(self, active: bool):
        """页面可见性驱动的启停：停在角色页/装配中心时不该在后台每秒扫游戏内存。"""
        active = bool(active)
        if active == self._active:
            return
        self._active = active
        self._sync_timer()
        if active:
            self.poll()

    def _on_live_toggled(self, checked):
        """用户关掉「实时」→ 停表（改手动点「读一次」），并顺带说明当前状态。"""
        self._live = bool(checked)
        self._sync_timer()
        if self._live:
            self.poll()

    def _sync_timer(self):
        """唯一的启停口：可见（_active）∧ 用户开关（_live）→ 跑定时器；离线态降频到 5s。

        间隔随「上次有没有读到」变：读到值才值得每秒看一次，读不到（游戏没开/不在假人图）
        就放宽，避免持续做无效的进程枚举与内存扫描。
        """
        want = _POLL_MS if self._last is not None else _POLL_OFFLINE_MS
        if self._timer.interval() != want:
            self._timer.setInterval(want)
        running = self._active and self._live
        if running and not self._timer.isActive():
            self._timer.start()
        elif not running and self._timer.isActive():
            self._timer.stop()

    def set_expectation(self, main_row, note: str = ''):
        """喂入主力技能期望行（skill_service.pick_main_row 的结果；None=不可用）。

        只重绘不读内存：词条编辑会频繁触发，1s 定时器会负责刷新实测值。
        note 说明「为什么没有期望」：空候选与未设参考技能是两种情形，诊断行不该都说成后者。
        """
        self._expect_note = str(note or '')
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

    def _apply_state(self, state):
        """运行态属性同时挂到卡片与结论标签：QSS 分别用来弱化描边与降级字号。

        必须挂两个：旧实现只挂在卡片上，而 `#dpsMeterValue[state=...]` 是给标签写的规则，
        于是失败态一直按 18px 半粗大字渲染（实测截图里与 DPS 结论抢焦点）。
        """
        for widget in (self, self.verdict):
            widget.setProperty('state', state)
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def poll(self):
        """一次轮询：读游戏实测值（失败降级短文案），再渲染。"""
        try:
            self._last = read_dps_meter()
        except MemoryImportError as exc:
            self._last = None
            self._error = exc
        self._has_read = True
        self._render()
        self._sync_timer()          # 读到了才知道要不要恢复 1s（离线态已降频到 5s）

    def _render(self):
        """依据「最近读数 + 期望基线」渲染；无读数时显示失败短文案。"""
        if self._last is None:
            if not self._has_read:
                # 一次都没读过（构造期）：给中性占位，别凭空断言「未定位到 DPS 计」
                self.verdict.setText('—')
                self.verdict.setToolTip('打开本页时读取运行中游戏的 DPS 计（只读内存）。')
                self._apply_trend(None)
                self.diag.setVisible(False)
                self._apply_state('offline')
                return
            exc = getattr(self, '_error', None)
            code = getattr(exc, 'code', '') if exc else ''
            self.verdict.setText(_SHORT_ERROR.get(code, str(exc) if exc else '—'))
            self.verdict.setToolTip(str(exc) if exc else '')
            self._apply_trend(None)
            self.diag.setVisible(False)
            self._apply_state('offline')
            return
        self._apply_state('live')
        live, total = float(self._last['dps']), float(self._last['total'])
        base_tip = (f'精确值：当前每秒 {live:.2f}；总伤害 {total:.0f}\n'
                    f'（读自运行中游戏的 DPS 计，1s 轮询；游戏里点「重置」后重新累计）')
        if self._expect_cur and self._expect_cand and live > 0:
            self._show_prediction(live, base_tip)
        else:
            self.verdict.setText(f'当前每秒 {fmt_compact(live)}')
            self._apply_trend(None)
            self.verdict.setToolTip(base_tip)
            self.diag.setText(self._expect_note
                              or '参考技能未设置：设好「参考技能」后这里会直接给候选预测')
            self.diag.setVisible(True)

    def _show_prediction(self, live: float, base_tip: str):
        """主行给结论（换装预测 + 涨跌），次行给诊断。"""
        factor = live / self._expect_cur
        predicted = self._expect_cand * factor
        pct = (predicted / live - 1.0) if live else 0.0
        self.verdict.setText(f'换装预测 {fmt_compact(predicted)}　{pct:+.1%}')
        self._apply_trend(trend_of(pct))
        self.verdict.setToolTip(
            base_tip
            + f'\n\n推算：系数 = 实测 {live:.0f} ÷ 主力技能期望（当前侧，含天赋）'
              f'{self._expect_cur:.0f} = ×{factor:.2f}\n'
              f'换装预测 = 候选期望 {self._expect_cand:.0f} × 系数'
              f'（线性近似：换单件不改循环结构；基线技能：{self._main_label}）')
        self.diag.setText(f'实测 {fmt_compact(live)}　·　期望 {fmt_compact(self._expect_cur)}'
                          f'　·　系数 ×{factor:.1f}')
        self.diag.setVisible(True)
