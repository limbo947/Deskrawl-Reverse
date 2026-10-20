# -*- coding: utf-8 -*-
"""帮助面板（B5）：左目录 + 右正文 + 顶部检索，取代四个纯文本弹窗。

为什么换掉 QMessageBox：术语表这类要通读的内容在弹窗里既不能分节也不能搜；用户想确认
「条件池是什么」时只能从头扫。本窗按主题分节，检索同时过滤目录并高亮命中，正文仍可整段
复制（与旧弹窗保留的唯一能力一致）。
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPushButton, QSplitter, QTextBrowser,
                               QVBoxLayout, QWidget)


class HelpPanelDialog(QDialog):
    """帮助正文窗：topics = [(key, 标题, 正文)]，current 指定初始主题。"""

    def __init__(self, topics, current: str = '', parent=None):
        super().__init__(parent)
        self._topics = list(topics)
        self.setWindowTitle('帮助')
        self.resize(880, 560)
        self.setMinimumSize(560, 360)

        self.search = QLineEdit()
        self.search.setPlaceholderText('检索（标题与正文，回车跳到下一个命中）…')
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._on_search)
        self.search.returnPressed.connect(self._find_next)

        self.list = QListWidget()
        self.list.setObjectName('helpTopics')
        # 左边的「主题」是普通 QLabel、没有 buddy：不给可访问名，读屏器只会念「列表」
        self.list.setAccessibleName('帮助主题目录')
        self.list.setFixedWidth(190)
        for key, title, _body in self._topics:
            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, key)
            self.list.addItem(item)
        self.list.currentRowChanged.connect(self._on_topic)

        self.body = QTextBrowser()
        self.body.setOpenExternalLinks(False)
        self.body.setLineWrapMode(QTextBrowser.WidgetWidth)

        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(8)
        left_lay.addWidget(QLabel('主题'))
        left_lay.addWidget(self.list, 1)

        split = QSplitter()
        split.addWidget(left)
        split.addWidget(self.body)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([190, 690])
        split.setCollapsible(0, False)

        self.hint = QLabel('')
        self.hint.setObjectName('pageSubtitle')
        close_btn = QPushButton('关闭')
        close_btn.clicked.connect(self.accept)
        bar = QHBoxLayout()
        bar.addWidget(self.hint, 1)
        bar.addWidget(close_btn)

        root = QVBoxLayout(self)
        root.addWidget(self.search)
        root.addWidget(split, 1)
        root.addLayout(bar)

        row = 0
        for i, (key, _title, _body) in enumerate(self._topics):
            if key == current:
                row = i
                break
        self.list.setCurrentRow(row)

    # ---------------- 主题切换 ----------------
    def _on_topic(self, row: int):
        if not 0 <= row < len(self._topics):
            return
        self._show(self._topics[row])

    def _show(self, topic):
        _key, title, body = topic
        self.body.setPlainText(body)
        self.hint.setText(f'{title} · 共 {len(body.splitlines())} 行（正文可整段选中复制）')
        text = self.search.text().strip()
        if text:
            from PySide6.QtGui import QTextCursor

            self.body.moveCursor(QTextCursor.Start)     # 换主题后从顶部找起，命中才在第一处
            self._find_next()

    def current_key(self) -> str:
        row = self.list.currentRow()
        return self._topics[row][0] if 0 <= row < len(self._topics) else ''

    # ---------------- 检索 ----------------
    def _on_search(self, text: str):
        """过滤目录（标题或正文命中）+ 在正文里高亮首个命中。

        目录同步过滤而不是只搜正文：命中散落在多个主题时，用户需要先看到「哪几节有」。
        全部主题都被过滤掉时保留当前正文，只改提示——空列表 + 空正文会让人以为帮助丢了。
        """
        needle = text.strip().lower()
        shown = 0
        for i, (_key, title, body) in enumerate(self._topics):
            hit = (not needle) or needle in title.lower() or needle in body.lower()
            self.list.item(i).setHidden(not hit)
            shown += 1 if hit else 0
        if not needle:
            self.hint.setText('输入关键词检索；正文可整段选中复制')
            return
        if shown == 0:
            self.hint.setText(f'没有命中「{text.strip()}」的主题（正文仍停留在当前节）')
            return
        self.hint.setText(f'「{text.strip()}」命中 {shown} 个主题')
        if self.list.currentItem() is None or self.list.currentItem().isHidden():
            for i in range(self.list.count()):
                if not self.list.item(i).isHidden():
                    self.list.setCurrentRow(i)
                    break
        self._find_next()

    def _find_next(self):
        """正文内跳到下一个命中（循环由 QTextBrowser.find 处理）。"""
        needle = self.search.text().strip()
        if needle:
            self.body.find(needle)


def open_help(topics, current: str = '', parent=None) -> int:
    """弹出帮助面板（测试/冒烟可直接构造 HelpPanelDialog 而不 exec）。"""
    return HelpPanelDialog(topics, current, parent).exec()
