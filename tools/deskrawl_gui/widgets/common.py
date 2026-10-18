# -*- coding: utf-8 -*-
"""跨页面共享的轻量组件：模式横幅 / 删除确认 / 空态提示。

抽出的动机：α 降级横幅原本只在装备对比页有，装配中心合并后也需要同一套提示；
删除确认与空态是合并后新增的交互，集中于此避免各页面各写一套文案与样式。
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDoubleSpinBox, QHBoxLayout, QLabel, QMessageBox, QVBoxLayout,
                               QWidget)

from ..core.format import fmt_qty

# α 聚合导入的统一降级说明（含「降级」关键词：selftest 文案锚点依赖它）
ALPHA_BANNER_TEXT = ('α 聚合模式（快照无逐件装备）：相关计算降级为「基线 vs 基线+候选词条」，'
                     '百分比类词条增量为近似值。')

# 装备对比页专用补充（F9）：α 下武器槽 Δ 语义偏高——当前武器词条并入基线、不随本轮对比卸下。
# 独立成段而非并入上面：装配中心也复用同一横幅，那句只在对比口径下成立。
ALPHA_WEAPON_NOTE = ('武器槽的 Δ 另有一层偏高：当前武器词条已并入基线、随本轮对比不会卸下，'
                     '故只反映候选增量。')


class ModeBanner(QLabel):
    """α/β 导入模式横幅：α 时显示降级说明，其余模式隐藏（幂等，可反复调用）。

    extra 供各页追加本页专属口径说明（默认空 = 只显示通用降级文案）。
    """

    def __init__(self, extra: str = '', parent=None):
        super().__init__(ALPHA_BANNER_TEXT + extra, parent)
        self.setObjectName('modeBanner')
        self.setWordWrap(True)
        self.setVisible(False)

    def update_mode(self, profile):
        alpha = getattr(profile, 'import_mode', '') == 'alpha'
        self.setVisible(alpha)
        return alpha


class QtySpinBox(QDoubleSpinBox):
    """数值输入框：内部按 decimals 存取（4 位），**显示**走 fmt_qty 去尾零。

    为什么不用 setDecimals(2) 一步到位：词条数值本身是 4 位精度（攻速 1.1845），砍到 2 位会
    把差异抹平；而直接留 4 位满屏「355.3500」。显示层与存储层分开，两头都不将就。
    """

    def __init__(self, parent=None, decimals: int = 4):
        super().__init__(parent)
        self.setDecimals(decimals)

    def textFromValue(self, value):        # noqa: N802 —— Qt 覆写
        return fmt_qty(value)

    def valueFromText(self, text):         # noqa: N802 —— Qt 覆写
        """去掉千分位后再解析；解析失败沿用当前值（默认实现会抛 ValueError → 焦点切换即崩）。"""
        try:
            return float(str(text).replace(',', '').strip())
        except ValueError:
            return self.value()


def confirm_delete(parent, title: str, text: str, yes_label: str = '删除') -> bool:
    """破坏性操作的二次确认；返回用户是否确认。

    用自定义中文按钮而非标准 Yes/No：Qt 未装中文翻译包时标准按钮会显示英文，
    与「界面全中文」约定冲突。yes_label 供非删除类操作（如「清除导入数据」）改写确认按钮。
    """
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Question)
    box.setWindowTitle(title)
    box.setText(text)
    yes = box.addButton(yes_label, QMessageBox.YesRole)
    box.addButton('取消', QMessageBox.NoRole)
    box.exec()
    return box.clickedButton() is yes


def empty_state(text: str) -> QLabel:
    """空态占位（弱化色，样式在 QSS 的 #emptyState）。"""
    label = QLabel(text)
    label.setObjectName('emptyState')
    label.setWordWrap(True)
    label.setAlignment(Qt.AlignCenter)
    return label


def apply_narrow_stacking(splitter, width: int, *, threshold: int = 1100):
    """窄窗口下把「左右分栏」改为「上下堆叠」。

    动机：两栏并排 + 绝对最小宽度在小屏或高缩放下会挤压（1920×1080 在 150% 缩放下只剩
    1280 逻辑点）。用 QSplitter 的 orientation 切换即可，不重建布局；宽回来再并排。
    """
    splitter.setOrientation(Qt.Vertical if width < threshold else Qt.Horizontal)


class SplitterSizesMixin:
    """把「横向分栏宽度」记成可持久化的值（三页各有一处 QSplitter，逻辑相同）。

    只在横向且宽度像样时记录：窄窗会切成竖排、构造期尚未布局时宽度是几百像素的假值，
    这两种情况的尺寸存进会话再套回去只会错位。拖动与窗口缩放都要刷新缓存，否则关窗时
    拿到的是上一次布局的值。
    """

    def _init_splitter_sizes(self, splitter) -> None:
        self._splitter_ref = splitter
        self._h_sizes = None
        splitter.splitterMoved.connect(lambda *_: self._remember_splitter())

    def _remember_splitter(self) -> None:
        # 阈值 800 而不是「比 0 大」：构造期分栏只有 600 多像素宽，尺寸是布局前的假值，
        # 存下来会在下次启动被当成用户意图（实测把默认 340/840 记成 340/296）。
        sp = self._splitter_ref
        if sp.orientation() == Qt.Horizontal and sp.width() >= 800:
            self._h_sizes = list(sp.sizes())

    def splitter_sizes(self):
        self._remember_splitter()      # 关窗时点布局已完成，取到的才是真值
        return self._h_sizes

    def set_splitter_sizes(self, sizes) -> None:
        if sizes and len(sizes) == self._splitter_ref.count():
            self._splitter_ref.setSizes([int(s) for s in sizes])


def page_header(title: str, subtitle: str = '', help_text: str = '') -> QWidget:
    """页面标题-副标题两级头部（统一样式锚点 #pageTitle / #pageSubtitle）。

    help_text 非空时在标题右侧挂一枚 ⓘ（悬停看说明）：副标题只留一句「这页干什么」，
    口径边界、上手说明这类长文收进 ⓘ 与帮助菜单，避免顶部被大段文字占满（V11）。
    """
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2)
    head = QHBoxLayout()
    head.setSpacing(6)
    t = QLabel(title)
    t.setObjectName('pageTitle')
    head.addWidget(t)
    if help_text:
        info = QLabel('ⓘ')
        info.setObjectName('helpHint')
        info.setToolTip(help_text)
        info.setCursor(Qt.PointingHandCursor)
        head.addWidget(info)
    head.addStretch(1)
    lay.addLayout(head)
    if subtitle:
        s = QLabel(subtitle)
        s.setObjectName('pageSubtitle')
        s.setWordWrap(True)
        lay.addWidget(s)
    return box
