# -*- coding: utf-8 -*-
"""构建库窗口（A6）：一屏看全 data/builds 里的方案，带等级/职业/DPS/备注。

为什么值得一窗：文件对话框只给文件名，几套方案（同一职业的几种配法）在文件名里几乎看不
出差别；这里把「这份构建算出来多少 DPS」直接摆在旁边，选哪份不用先载入再比对。
备注写回构建 JSON 的 `note` 字段（随文件走，换机器也在），不是另建索引文件——
索引与文件一旦不同步，用户看到的就是两个真相。
"""
import os
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout, QHeaderView,
                               QInputDialog, QLabel, QMessageBox, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout)

from ..core.build_library import scan_builds, set_note
from ..core.profile import BUILDS_DIR
from .common import confirm_delete, mono_font

_COLS = ['名称', '等级', '职业', '装配', '期望 DPS', '备注', '修改时间']


class BuildLibraryDialog(QDialog):
    """构建列表 + 载入/备注/删除/另存（load/save 由主窗口注入，本窗不直接改 profile）。"""

    def __init__(self, gd, on_load, on_save, parent=None):
        super().__init__(parent)
        self.gd = gd
        self._on_load = on_load
        self._on_save = on_save
        self._entries = []
        self.setWindowTitle('构建库')
        self.resize(860, 420)

        self.hint = QLabel('')
        self.hint.setObjectName('pageSubtitle')
        self.hint.setWordWrap(True)

        self.table = QTableWidget(0, len(_COLS))
        self.table.setHorizontalHeaderLabels(_COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.doubleClicked.connect(lambda *_: self._load_selected())

        load_btn = QPushButton('载入')
        load_btn.setObjectName('primary')      # 本窗的落点动作：黄底黑字，与主窗口 CTA 同一语义
        load_btn.clicked.connect(self._load_selected)
        note_btn = QPushButton('编辑备注…')
        note_btn.clicked.connect(self._edit_note)
        del_btn = QPushButton('删除…')
        del_btn.clicked.connect(self._delete_selected)
        save_btn = QPushButton('另存当前构建…')
        save_btn.clicked.connect(self._save_current)
        folder_btn = QPushButton('打开目录')
        folder_btn.clicked.connect(self._open_folder)
        close_btn = QPushButton('关闭')
        close_btn.clicked.connect(self.reject)

        bar = QHBoxLayout()
        bar.addWidget(load_btn)
        bar.addWidget(note_btn)
        bar.addWidget(del_btn)
        bar.addWidget(save_btn)
        bar.addWidget(folder_btn)
        bar.addStretch(1)
        bar.addWidget(close_btn)

        root = QVBoxLayout(self)
        root.addWidget(self.hint)
        root.addWidget(self.table, 1)
        root.addLayout(bar)
        self.reload()

    def reload(self):
        """重扫目录（另存/删除/改备注后都要重扫，避免界面与磁盘不一致）。"""
        self._entries = scan_builds(self.gd, BUILDS_DIR)
        self.table.setRowCount(len(self._entries))
        mono = mono_font(self.table.font())
        for row, e in enumerate(self._entries):
            cells = [e.name, f'Lv{e.level}' if e.level else '—', e.hero_class_cn or '—',
                     str(e.assembled),
                     f'{e.dps:.1f}' if e.dps is not None else '—',
                     e.note or '', _fmt_time(e.mtime)]
            if e.error:
                cells[0] = f'{e.name}（损坏）'
                cells[5] = e.error
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if col in (1, 3, 4):
                    item.setTextAlignment(int(Qt.AlignRight | Qt.AlignVCenter))
                    item.setFont(mono)
                item.setData(Qt.UserRole, row)
                if e.error:
                    item.setToolTip(f'{e.path}\n{e.error}')
                self.table.setItem(row, col, item)
        bad = sum(1 for e in self._entries if e.error)
        self.hint.setText(
            f'构建目录：{BUILDS_DIR}　共 {len(self._entries)} 份'
            + (f'（其中 {bad} 份无法读取，详情见悬停）' if bad else '')
            + '　·　双击载入；DPS 为当前目标口径下的基线期望值')

    def _selected(self):
        row = self.table.currentRow()
        if 0 <= row < len(self._entries):
            return self._entries[row]
        return None

    def _load_selected(self):
        entry = self._selected()
        if entry is None:
            return
        if entry.error:
            QMessageBox.warning(self, '无法载入', f'{entry.filename}\n{entry.error}')
            return
        self._on_load(entry.path)
        self.accept()

    def _edit_note(self):
        entry = self._selected()
        if entry is None or entry.error:
            return
        text, ok = QInputDialog.getMultiLineText(self, '编辑备注', f'{entry.name} 的备注：',
                                                 entry.note)
        if not ok:
            return
        try:
            set_note(entry.path, text)
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, '保存备注失败', str(exc))
            return
        self.reload()

    def _delete_selected(self):
        entry = self._selected()
        if entry is None:
            return
        if not confirm_delete(self, '删除构建文件',
                              f'将删除文件：\n{entry.path}\n此操作不可撤销。'):
            return
        try:
            os.remove(entry.path)
        except OSError as exc:
            QMessageBox.warning(self, '删除失败', str(exc))
            return
        self.reload()

    def _save_current(self):
        if self._on_save():
            self.reload()

    def _open_folder(self):
        """在资源管理器里打开构建目录（非 Windows 或无桌面环境时静默跳过）。"""
        try:
            os.startfile(BUILDS_DIR)          # noqa: S606 —— Windows 专用，其它平台无此属性
        except (AttributeError, OSError):
            QMessageBox.information(self, '打开目录', f'构建目录：{BUILDS_DIR}')


def _fmt_time(mtime: float) -> str:
    if not mtime:
        return '—'
    return time.strftime('%Y-%m-%d %H:%M', time.localtime(mtime))


def open_build_library(gd, on_load, on_save, parent=None):
    """弹出构建库；返回 QDialog.exec() 结果（测试/冒烟可直接构造对话框而不 exec）。"""
    return BuildLibraryDialog(gd, on_load, on_save, parent).exec()
