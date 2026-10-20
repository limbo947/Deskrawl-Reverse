# -*- coding: utf-8 -*-
"""线性图标（C5）：resources/icons/*.svg 的 QIcon 包装（带缓存）。

为什么统一成一套单色描边图标而不是各按钮各配一个：这是工具界面，图标只承担「扫读定位」
（哪个是播种、哪个是整套对比），配色与插画性反而干扰对数值的注意力。

描边色是 #7E8896（theme.LIGHT_MAP 的「图标中性灰」）：SVG 不参与 QSS 换色，所以它不能
用某个主题专属令牌——原来的 #929AA5 在白底上只有 2.75:1，浅色主题下图标会淡到看不见。

图标是纯观感项：文件缺失时返回空 QIcon，不为它让窗口打不开（与 load_app_icon 同一取向）。
"""
import os

from PySide6.QtGui import QIcon

_ICON_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         'resources', 'icons')
_CACHE = {}


def icon(name: str) -> QIcon:
    """按文件名取图标（不含扩展名）；不存在或平台缺 SVG 插件时返回空图标。"""
    cached = _CACHE.get(name)
    if cached is not None:
        return cached
    path = os.path.join(_ICON_DIR, f'{name}.svg')
    gui_icon = QIcon(path) if os.path.exists(path) else QIcon()
    if gui_icon.isNull() and os.path.exists(path):
        gui_icon = QIcon()          # 平台缺 SVG 插件：留空，不让调用方拿到「有但画不出」的对象
    _CACHE[name] = gui_icon
    return gui_icon


__all__ = ['icon']
