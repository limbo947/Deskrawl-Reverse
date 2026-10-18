# -*- coding: utf-8 -*-
"""界面数值格式化：把「显示多少位小数」收敛到一处。

为什么单独成模块：同一屏曾同时出现 0.00 / 1.299 / 355.3500 / 1.0815 四种精度（输入框固定
decimals=4，表格各写 .4g/.6g），读数时要先分辨哪几位是真的。这里只做**显示**：四舍五入到
最多 3 位并去尾零；存储精度不受影响（QDoubleSpinBox 仍按 decimals 存 float）。
"""
import math

_MAX_DIGITS = 3

# 表格里「这一层没有贡献」的占位：比 0 / 1 更容易一眼跳过（颜色仍由 QSS 管，不用前景色区分）
NO_INFO = '—'


def fmt_qty(value) -> str:
    """数值 → 紧凑显示串（≤3 位小数、去尾零、整数不带小数点）。"""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return NO_INFO
    if math.isnan(num) or math.isinf(num):
        return NO_INFO
    text = f'{num:.{_MAX_DIGITS}f}'.rstrip('0').rstrip('.')
    return '0' if text in ('', '-0') else text


def fmt_layer(value, *, identity=None) -> str:
    """分层列专用：等于 identity（如乘区 1、条件层 0）时返回 NO_INFO，避免整列被无效值填满。"""
    if identity is not None:
        try:
            if float(value) == float(identity):
                return NO_INFO
        except (TypeError, ValueError):
            return NO_INFO
    return fmt_qty(value)
