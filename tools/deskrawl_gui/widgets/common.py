# -*- coding: utf-8 -*-
"""跨页面共享的轻量组件：模式横幅 / 删除确认 / 空态提示。

抽出的动机：α 降级横幅原本只在装备对比页有，装配中心合并后也需要同一套提示；
删除确认与空态是合并后新增的交互，集中于此避免各页面各写一套文案与样式。
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMessageBox, QVBoxLayout, QWidget

# α 聚合导入的统一降级说明（含「降级」关键词：selftest 文案锚点依赖它）
ALPHA_BANNER_TEXT = ('α 聚合模式（快照无逐件装备）：相关计算降级为「基线 vs 基线+候选词条」，'
                     '百分比类词条增量为近似值。')


class ModeBanner(QLabel):
    """α/β 导入模式横幅：α 时显示降级说明，其余模式隐藏（幂等，可反复调用）。"""

    def __init__(self, parent=None):
        super().__init__(ALPHA_BANNER_TEXT, parent)
        self.setObjectName('modeBanner')
        self.setWordWrap(True)
        self.setVisible(False)

    def update_mode(self, profile):
        alpha = getattr(profile, 'import_mode', '') == 'alpha'
        self.setVisible(alpha)
        return alpha


def confirm_delete(parent, title: str, text: str) -> bool:
    """删除类操作的二次确认；返回用户是否确认。

    用自定义中文按钮而非标准 Yes/No：Qt 未装中文翻译包时标准按钮会显示英文，
    与「界面全中文」约定冲突。
    """
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Question)
    box.setWindowTitle(title)
    box.setText(text)
    yes = box.addButton('删除', QMessageBox.YesRole)
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


def page_header(title: str, subtitle: str = '') -> QWidget:
    """页面标题-副标题两级头部（统一样式锚点 #pageTitle / #pageSubtitle）。"""
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2)
    t = QLabel(title)
    t.setObjectName('pageTitle')
    lay.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setObjectName('pageSubtitle')
        s.setWordWrap(True)
        lay.addWidget(s)
    return box
