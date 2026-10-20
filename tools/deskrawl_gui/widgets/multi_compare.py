# -*- coding: utf-8 -*-
"""整套对比对话框（A4）：把「已填候选的槽一起换掉」的总 Δ 与逐槽边际摊开。

为什么单独成窗而不是塞进对比页：本页一次只编辑一个槽，「多件同换」是跨槽问题；
塞进结果区会让单槽结论与整套结论混在一屏，用户很难看出哪个数对应哪件事。

口径边界写在窗口底部（与 CALIBER_TEXT 第 3 条同义）：逐槽边际不等于各槽单独对比的 Δ，
两者不能相加也不能互换——这是本窗口存在的理由，不能省。
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QDialog, QFileDialog,
                               QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout)

from ..core import export as export_mod
from ..core.compare_multi import active_slots, multi_compare
from ..core.profile import SLOT_LABELS
from .common import mono_font
from .compare_view import _delta_object_name

_COLS = ['槽位', '当前件', '候选件', '边际 ΔDPS', '边际 Δ%']
_NOTE = ('口径：整套 = 这些槽的候选同时装回后的总 DPS 与基线之差；边际 = 撤掉该件后总 DPS 的落差。\n'
         '逐槽边际之间、以及它们与单槽对比的 Δ 都不能相加（乘区交互：百分比同池、封顶、条件层）。')


def _name_of(draft) -> str:
    """草稿的展示名；没填名称时给一句可辨认的占位（而不是空白格）。"""
    name = str(getattr(draft, 'name', '') or '').strip()
    if name:
        return name
    return '（未命名候选）' if (getattr(draft, 'affixes', None) or []) else '（空）'


class MultiCompareDialog(QDialog):
    """整套对比结果：总数 + 逐槽边际表（只读）+ 导出。"""

    def __init__(self, profile, gd, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.gd = gd
        self.result = multi_compare(profile, gd)
        self.setWindowTitle('整套对比（多槽同时替换）')
        self.resize(760, 420)

        head = QLabel('')
        head.setObjectName('pageSubtitle')
        head.setWordWrap(True)
        self.head = head
        self.delta_label = QLabel('—')
        self.delta_label.setObjectName('dpsBig')
        self.delta_label.setToolTip('整套 DPS − 当前构建基线 DPS')

        top = QHBoxLayout()
        top.addWidget(head, 1)
        top.addWidget(self.delta_label, 0)

        self.table = QTableWidget(0, len(_COLS))
        self.table.setHorizontalHeaderLabels(_COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)

        self.note = QLabel(_NOTE)
        self.note.setObjectName('pageSubtitle')
        self.note.setWordWrap(True)

        copy_btn = QPushButton('复制为 TSV')
        copy_btn.clicked.connect(self._copy)
        csv_btn = QPushButton('导出 CSV…')
        csv_btn.clicked.connect(self._export)
        close_btn = QPushButton('关闭')
        close_btn.clicked.connect(self.reject)
        bar = QHBoxLayout()
        bar.addWidget(copy_btn)
        bar.addWidget(csv_btn)
        bar.addStretch(1)
        bar.addWidget(close_btn)

        root = QVBoxLayout(self)
        root.addLayout(top)
        root.addWidget(self.table, 1)
        root.addWidget(self.note)
        root.addLayout(bar)
        self._fill()

    def _fill(self):
        res = self.result
        self.head.setText(
            f'参与 {len(res.slots)} 槽：{"、".join(SLOT_LABELS.get(s, f"槽{s}") for s in res.slots)}'
            f'｜基线 {res.base_dps:.1f} → 整套 {res.multi_dps:.1f}'
            + (f'｜候选未填写 {len(res.skipped)} 槽未参与' if res.skipped else ''))
        arrow = '' if abs(res.delta_pct) < 0.005 else ('▲ ' if res.delta_pct > 0 else '▼ ')
        self.delta_label.setText(f'{arrow}{res.delta_pct:+.2f}%（{res.delta:+.1f} DPS）')
        # 涨跌配色只在 style.qss 定义，这里只切 objectName（同 CompareView）
        self.delta_label.setObjectName(_delta_object_name(res.delta))
        self.delta_label.style().unpolish(self.delta_label)
        self.delta_label.style().polish(self.delta_label)

        rows = self.export_rows()[1]
        mono = mono_font(self.table.font())
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for c, text in enumerate(row):
                item = QTableWidgetItem(text)
                if c >= 3:
                    item.setTextAlignment(int(Qt.AlignRight | Qt.AlignVCenter))
                    item.setFont(mono)
                self.table.setItem(i, c, item)

    def export_rows(self):
        """(表头, 行)：与屏幕同文本（导出不另算一份口径）。"""
        out = []
        for row in self.result.rows:
            cur = self.profile.weapon_current if row.slot == 0 \
                else self.profile.slot_current.get(row.slot)
            cand = self.profile.weapon_candidate if row.slot == 0 \
                else self.profile.slot_candidate.get(row.slot)
            out.append([row.label, _name_of(cur), _name_of(cand),
                        f'{row.marginal:+.1f}', f'{row.marginal_pct:+.2f}%'])
        return list(_COLS), out

    def _copy(self):
        headers, rows = self.export_rows()
        body = export_mod.rows_to_tsv(headers, rows)
        header = f'整套对比\t基线 {self.result.base_dps:.1f}\t整套 {self.result.multi_dps:.1f}\t' \
                 f'总 {self.result.delta_pct:+.2f}%\n'
        QApplication.clipboard().setText(header + body + '\n' + _NOTE)

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, '导出整套对比', '整套对比.csv', 'CSV (*.csv)')
        if not path:
            return
        try:
            export_mod.write_csv(path, *self.export_rows())
        except OSError as exc:
            QMessageBox.warning(self, '导出失败', str(exc))


def open_multi_compare(profile, gd, parent=None) -> int:
    """弹出整套对比（空候选时给出说明而不是空白表）。返回值同 QDialog.exec()。"""
    if not active_slots(profile):
        QMessageBox.information(parent, '整套对比',
                                '还没有填写任何候选件。\n'
                                '先在本页给若干槽填上候选（或「从背包/仓库导入」），再来算整套替换。')
        return QDialog.Rejected
    return MultiCompareDialog(profile, gd, parent).exec()
