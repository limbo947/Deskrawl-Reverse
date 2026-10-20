# -*- coding: utf-8 -*-
"""主题令牌：一份 QSS 描述结构，一张色值表负责明暗两套配色。

为什么不做成 style_light.qss：两份文件必然漂移——改暗色里的圆角/间距时没人会记得同步浅色，
最后两套视觉各自演化。这里把「结构（规则）」与「配色（值）」分开：rules 只写暗色令牌值，
浅色由一张映射表整体替换，结构改一处两套同时生效。

色板取自 DESIGN.md（Binance 设计语言）：深近黑画布 + 单一黄色强调，绿色/红色只表达涨跌。
品牌色（黄、涨绿、跌红、聚焦蓝）在两种主题下取值相同——它们是语义令牌，不随底色翻转；
因此 LIGHT_MAP 允许「键 == 值」的恒等映射，而浅色残留检查只针对真正的暗色专属令牌。
"""
import os
import re

THEME_NAMES = ('dark', 'light')
THEME_LABELS = {'dark': '深色', 'light': '浅色'}

# 画布色单独抽出：自检要断言「浅色下不残留暗画布」，两处引用同一个字符串才不会各写一份
CANVAS_DARK = '#0B0E11'
CANVAS_LIGHT = '#FFFFFF'

# 暗色令牌 → 浅色令牌（键集合 = style.qss 里出现的全部色值；新增色值必须在此登记，
# 否则浅色主题下会残留一块暗色——selftest 的「主题令牌覆盖」断言会先红）。
# 恒等映射（主黄/涨绿/跌红/聚焦蓝/中性灰）是刻意的：这些令牌跨主题不变，见模块说明。
LIGHT_MAP = {
    CANVAS_DARK: CANVAS_LIGHT,   # 画布：深近黑 ↔ 纯白
    '#1E2329': '#FAFAFA',        # 卡片面/输入框/菜单（dark surface-card-dark）
    '#2B3139': '#EAECEF',        # 抬升面/悬停/全部细边线（dark hairline-on-dark）
    '#1A1F25': '#F5F5F5',        # 卡片内的次级面：斑马纹、已装配清单、实测框
    '#14181D': '#F5F5F5',        # 禁用控件底（比卡片再沉一档）
    '#FCD535': '#FCD535',        # 主黄：CTA / 品牌字 / 关键数值
    '#F0B90B': '#F0B90B',        # 主黄按压
    '#3A3A1F': '#EFE6C7',        # 主黄禁用（浅色下不能是一块深黄）
    '#181A20': '#181A20',        # 黄底上的黑字 / 浅色主文字
    '#EAECEF': '#181A20',        # 暗色正文 ↔ 浅色正文
    '#FFFFFF': '#181A20',        # 暗色高对比标题 ↔ 浅色主文字
    '#FFD84D': '#8A6200',        # 黄系文字链接：主黄在白底上对比度不足，浅色改用深金
    '#707A8A': '#707A8A',        # 仅禁用态文字（卡片面 3.65:1，低于 AA，不做可读正文）
    '#929AA5': '#5E6673',        # 次级弱化文字：浅底上要更深
    # 图标/箭头中性灰：SVG 不参与 QSS 换色，所以它必须自身跨主题可用——深浅两种画布上
    # 都 ≥3:1（WCAG 1.4.11 非文字对比），故取恒等映射而非跟随翻转
    '#7E8896': '#7E8896',
    '#0ECB81': '#0ECB81',        # Δ 上涨
    '#F6465D': '#F6465D',        # Δ 下跌 / 错误
    '#3B82F6': '#3B82F6',        # 聚焦环
}
# 不参与替换的色值：勾选框勾标记等「永远要黑/白」的图形（映射表故意不含它们）
_KEEP = set()


QSS_PATH = os.path.normpath(os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'resources', 'style.qss'))

# QSS 里的资源占位符 → 相对 resources 的文件名。长键先替换（见 load_qss）。
QSS_ASSETS = {
    '@ARROW_UP': 'arrow_up.svg',
    '@ARROW_DOWN': 'arrow_down.svg',
    '@ARROW_UP_DISABLED': 'arrow_up_disabled.svg',
    '@ARROW_DOWN_DISABLED': 'arrow_down_disabled.svg',
    '@CHECK': 'icons/check.svg',
}


def load_qss(path: str = None, theme: str = 'dark') -> str:
    """读取主题样式（theme='light' 时按色值表整体换色）。文件缺失必须显式抛错：
    静默降级会让主题失效却无人察觉。

    @ARROW_* / @CHECK 在这里换成与 qss 同目录的绝对路径：QSS 的 url() 按**进程工作目录**
    解析（不是 qss 文件位置），冻结态/从别处启动时会指错，箭头与勾标记就静默消失。
    Windows 路径须用正斜杠。
    """
    path = path or QSS_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(f'主题资源缺失：{path}')
    with open(path, encoding='utf-8') as f:
        text = f.read()
    base = os.path.dirname(os.path.abspath(path)).replace('\\', '/')
    # 长键先替换：@ARROW_UP 是 @ARROW_UP_DISABLED 的前缀，按短键先换会把后者截断成
    # "arrow_up.svg_DISABLED"（图片路径指错，禁用态箭头静默消失）。
    for token in sorted(QSS_ASSETS, key=len, reverse=True):
        text = text.replace(token, f'{base}/{QSS_ASSETS[token]}')
    return apply_theme(text, theme)


def apply_theme(qss_text: str, theme: str = 'dark') -> str:
    """把暗色 QSS 文本换成指定主题（未知主题名按暗色处理，不做静默半替换）。"""
    if theme not in THEME_NAMES or theme == 'dark':
        return qss_text
    pattern = re.compile('|'.join(re.escape(k) for k in LIGHT_MAP), re.IGNORECASE)
    return pattern.sub(lambda m: LIGHT_MAP.get(m.group(0).upper(), m.group(0)), qss_text)


def unknown_colors(qss_text: str) -> list:
    """QSS 里未登记进色值表的颜色（自检用：新增令牌忘了登记会在这里出现）。

    先去掉注释：文件头的色板说明里列了大量色值（且含「刻意例外」的例子），照扫会误报。
    """
    stripped = re.sub(r'/\*.*?\*/', '', qss_text, flags=re.S)
    found = {m.upper() for m in re.findall(r'#[0-9A-Fa-f]{6}', stripped)}
    return sorted(found - set(LIGHT_MAP) - _KEEP)


def theme_specific_tokens() -> list:
    """需要翻转的暗色令牌（键 != 值）；恒等映射的品牌色不在此列。"""
    return [k for k, v in LIGHT_MAP.items() if k.upper() != v.upper()]


__all__ = ['THEME_NAMES', 'THEME_LABELS', 'CANVAS_DARK', 'CANVAS_LIGHT', 'LIGHT_MAP',
           'QSS_PATH', 'QSS_ASSETS', 'load_qss', 'apply_theme', 'unknown_colors',
           'theme_specific_tokens']
