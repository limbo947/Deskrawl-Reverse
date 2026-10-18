# -*- coding: utf-8 -*-
"""底部浮层提示：取代散落的 QStatusBar.showMessage，一处管级别、时长与位置。

为什么不用状态栏：它只有一行、无级别、最大化后离视线很远——「导入失败」和「已保存」在
视觉上完全一样，用户得主动去读。浮层固定在可视区底部中央，level 由 QSS 着色（代码不抄色值），
到时自动收起；同一条通道也保证消息不会同时出现在两处。
"""
from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import QLabel

# 级别集合与 QSS 的 [level="..."] 选择器一一对应（新增级别必须同时加样式，否则锚点对账会红）
LEVELS = ('info', 'warn', 'error')

_DEFAULT_TIMEOUT = 4000


class Toast(QLabel):
    """宿主窗口的浮层提示（不是独立窗口：不抢焦点、不进任务栏、随窗口一起关）。

    鼠标事件穿透：它只做提示，浮在内容上方若挡住点击会让人误以为界面卡住。
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName('toast')
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setVisible(False)
        self._level = 'info'
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        parent.installEventFilter(self)

    def eventFilter(self, obj, event):
        """跟随宿主尺寸变化重定位：浮层不在布局里，不自己贴边就会停在旧位置。"""
        if event.type() == QEvent.Resize:
            self._reposition()
        return super().eventFilter(obj, event)

    def notify(self, text: str, level: str = 'info', timeout: int = None) -> None:
        """显示一条提示；重复调用即刷新文本与计时（不排队，后到的覆盖前一条）。"""
        self._level = level if level in LEVELS else 'info'
        self.setProperty('level', self._level)
        self.setText(str(text))
        self.setToolTip(str(text))
        # 属性变了要重新 polish，否则同一条浮层会沿用上一次的配色
        self.style().unpolish(self)
        self.style().polish(self)
        self._reposition()
        self.setVisible(True)
        self._timer.start(int(timeout or _DEFAULT_TIMEOUT))

    def clear(self) -> None:
        """立即收起（关窗/测试收尾用，避免残留定时器在销毁后触发）。"""
        self._timer.stop()
        self.hide()

    def level(self) -> str:
        return self._level

    def _reposition(self) -> None:
        """按文本长度定宽、按换行结果定高，再贴到窗口底部中央。

        不用 sizeHint()：带 wordWrap 的 QLabel 会先按自身的换行策略给一个偏窄的建议宽度，
        短消息因此被折成三行（实测「已保存：…」在 242px 里排了三行）。这里按文本实际宽度
        取，只有超过窗口可用宽度时才换行。
        """
        parent = self.parentWidget()
        if parent is None:
            return
        max_width = max(240, parent.width() - 64)
        want = self.fontMetrics().horizontalAdvance(self.text()) + 40   # 左右 padding + 描边余量
        width = min(max(240, want), max_width)
        # heightForWidth 才是「按这个宽度换行后要几行」；sizeHint 是旧换行状态下的建议值，
        # 取 max 会让短消息保留上一次的三行高度（实测 72px 的框里只有一行字）。
        hfw = self.heightForWidth(width)
        height = min(max(hfw if hfw > 0 else self.sizeHint().height(), 28), 180)
        x = max(0, (parent.width() - width) // 2)
        y = max(0, parent.height() - height - 16)
        self.setGeometry(x, y, width, height)
