# -*- coding: utf-8 -*-
"""中央 Tab3：装配浏览器（宝石/符文/天赋/套装，搜索 + 加入构建）。

左侧按类别分 Tab 列出全部候选并可设等级/点数后加入构建；右侧是已装配清单。
控件只负责改 profile.assembled，随后发 changed 由主窗口统一刷新（属性表/排序基线随之更新）。
"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget)

from ..core import calc_service
from ..core.profile import KIND_LABELS, KIND_ORDER, AssemblyItem

_SLOTS = [(0, '护甲'), (1, '饰品'), (2, '武器')]
_LEVEL_LABEL = {'rune': '符文等级', 'talent': '天赋点数', 'runeset': '套装件数'}


class AssemblyBrowser(QWidget):
    changed = Signal()

    def __init__(self, profile, gd, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.gd = gd
        self._lists = {}
        self._level_spins = {}
        self._slot_combos = {}
        self._searches = {}

        self.cat_tabs = QTabWidget()
        for kind, label in KIND_ORDER:
            self.cat_tabs.addTab(self._build_tab(kind), label)

        self.assembled_list = QListWidget()
        remove_btn = QPushButton('删除选中')
        remove_btn.clicked.connect(self._remove_selected)
        right = QWidget()
        rlay = QVBoxLayout(right)
        rlay.addWidget(QLabel('已装配（参与属性表与排序基线）'))
        rlay.addWidget(self.assembled_list, 1)
        rlay.addWidget(remove_btn)

        root = QHBoxLayout(self)
        root.addWidget(self.cat_tabs, 3)
        root.addWidget(right, 2)
        self.refresh()

    # ---------------- UI 构建 ----------------
    def _build_tab(self, kind: str) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        search = QLineEdit()
        search.setPlaceholderText('搜索名称…')
        search.textChanged.connect(lambda text, k=kind: self._filter(k, text))
        listing = QListWidget()
        for name in calc_service.candidate_names(self.gd, kind):
            listing.addItem(name)
        self._searches[kind] = search
        self._lists[kind] = listing

        bar = QHBoxLayout()
        if kind == 'gem':
            bar.addWidget(QLabel('镶嵌部位'))
            combo = QComboBox()
            for value, label in _SLOTS:
                combo.addItem(label, value)
            combo.setCurrentIndex(2)            # 默认武器孔，与候选排序表保持一致
            bar.addWidget(combo)
            self._slot_combos[kind] = combo
        else:
            bar.addWidget(QLabel(_LEVEL_LABEL[kind]))
            spin = QSpinBox()
            spin.setRange(1, 999)
            spin.setValue(1)
            bar.addWidget(spin)
            self._level_spins[kind] = spin
        add_btn = QPushButton('加入构建')
        add_btn.clicked.connect(lambda _, k=kind: self._add_selected(k))
        bar.addWidget(add_btn)
        bar.addStretch(1)

        lay.addWidget(search)
        lay.addWidget(listing, 1)
        lay.addLayout(bar)
        return page

    # ---------------- 交互 ----------------
    def _filter(self, kind: str, text: str):
        needle = text.strip().lower()
        for i in range(self._lists[kind].count()):
            item = self._lists[kind].item(i)
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def _params(self, kind: str):
        if kind == 'gem':
            return 1, int(self._slot_combos[kind].currentData())
        return int(self._level_spins[kind].value()), 2

    def _add_selected(self, kind: str):
        item = self._lists[kind].currentItem()
        if item is None or item.isHidden():
            return
        level, category = self._params(kind)
        self.profile.assembled.append(AssemblyItem(kind, item.text(), level, category))
        self.changed.emit()

    def _remove_selected(self):
        row = self.assembled_list.currentRow()
        if row < 0 or row >= len(self.profile.assembled):
            return
        del self.profile.assembled[row]
        self.changed.emit()

    # ---------------- 回填 ----------------
    def refresh(self):
        self.assembled_list.clear()
        for it in self.profile.assembled:
            extra = f'部位{_SLOTS[it.category][1]}' if it.kind == 'gem' else f'{_LEVEL_LABEL.get(it.kind, "等级")}{it.level}'
            self.assembled_list.addItem(f'{KIND_LABELS.get(it.kind, it.kind)}｜{it.name}｜{extra}')
