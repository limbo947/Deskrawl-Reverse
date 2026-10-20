# -*- coding: utf-8 -*-
"""内存导入的后台执行（D3）：把只读快照放进 QThread，主线程不再假死。

为什么值得一个线程：`import_snapshot()` 要枚举进程、走多层指针、双读比对，慢盘或双读重试时
会阻塞数秒——期间窗口不重绘、浮层提示也刷不出来，用户看到的是「点了没反应」。

取消的边界：读内存是**不可中断**的（中途停下没有意义，也不能对游戏做任何干预），所以
`cancel()` 只表示「结果别用了」，线程仍会自然跑完。这是诚实的降级，不是完整的取消语义。
"""
from PySide6.QtCore import QThread, Signal


class ImportWorker(QThread):
    """一次导入：成功发 (结果, '', '')，失败发 (None, 错误码, 消息)。"""

    done = Signal(object, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancelled = False

    def cancel(self):
        """标记结果作废（线程会跑完，但不再发 done）。"""
        self._cancelled = True

    def run(self):
        from .memory_import import MemoryImportError, import_snapshot

        try:
            res = import_snapshot()
        except MemoryImportError as exc:
            if not self._cancelled:
                self.done.emit(None, str(getattr(exc, 'code', '') or ''), str(exc))
            return
        except Exception as exc:                  # noqa: BLE001 边界兜底：线程里不能裸抛
            if not self._cancelled:
                self.done.emit(None, 'data', f'{type(exc).__name__}: {exc}')
            return
        if not self._cancelled:
            self.done.emit(res, '', '')
