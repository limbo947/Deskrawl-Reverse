# -*- coding: utf-8 -*-
"""单件装备的编辑面板（任意槽通用；武器多出基础伤害/攻速/技能倍率三行）。

从 equipment_editor 拆出：装备对比页要按 11 个槽位复用同一套「名称 + 词条行 + 元信息」控件，
把它独立成 ItemEditor 后，equipment_editor 只负责槽位切换与装配，避免单文件膨胀。
控件直接写回传入的草稿（WeaponDraft / ItemDraft），改动只发 changed 信号。
"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDoubleSpinBox, QFormLayout,
                               QGroupBox, QHeaderView, QLabel, QLineEdit, QPushButton,
                               QTableWidget, QVBoxLayout)

from deskrawl_calc import StatType, stat_name

_MOD_TYPES = [(0, '加法'), (1, '百分比加算'), (2, '连乘')]
_MOD_LABELS = dict(_MOD_TYPES)

# 装备词条的入池方式在游戏里固定为「加法」：ItemData 固定属性 43 条、宝石/符文/套装加成
# 255 条实测 100% 为 Type 0（仅 3 条天赋在护甲/魔抗/荆棘上用百分比加算，且不来自装备）。
# 故类型完全由属性自动决定、下拉一律禁用，用户没有填错的余地。
_ALLOWED_TYPES = [0]

# 百分比类属性：数值本身是小数形式的百分比（0.30 = 30%）。这类属性必须提示「按小数填写」，
# 否则很容易把 30% 填成 30 —— 差 100 倍且不报错。
_PERCENT_STATS = frozenset(
    {4, 5, 6, 13, 15, 16, 17, 19, 22, 37, 41, 56, 57, 65}     # 暴击/攻速/冷却/掉落/闪避等
    | set(range(23, 35))                                       # 元素乘区23–28 + 条件29–32 + 普攻·强攻33–34
    | {40, 42, 43, 44, 45, 46, 48, 49, 51, 52, 53, 54, 55, 58,
       59, 60, 61, 62, 63, 64}                                 # 其余条件/技能/生存百分比项
)

_TIP_PERCENT = '百分比类属性：数值按小数填写（0.3000 = 30%）；入池方式由游戏固定为「加法」'
_TIP_FLAT = '数值属性：直接填数值；入池方式由游戏固定为「加法」'
_TIP_VALUE_PERCENT = '按小数填写，例：0.3000 = 30%'
# 主属性提示（Player.CalcDamage@0x50E400：攻击伤害 ×(1+Final(职业主属性)/100)，每点即 +1% 伤害加成）
_TIP_PRIMARY_STAT = ('主属性：仅「职业主属性」（左栏设定/内存导入自动识别）参与攻击伤害——'
                     '按游戏公式 ×(1+最终值/100)，每点 +1% 伤害加成；其余主属性只提供护甲/魔抗')


class AffixTable(QTableWidget):
    """词条行表：属性（内核 StatType 全量中文名）/ 类型 / 数值 / 删除。"""

    changed = Signal()
    COLUMNS = ['属性', '类型', '数值', '']

    def __init__(self, parent=None):
        super().__init__(0, len(self.COLUMNS), parent)
        self._loading = False
        self.setHorizontalHeaderLabels(self.COLUMNS)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.setMinimumHeight(150)

    def set_affixes(self, affixes):
        self._loading = True
        self.setRowCount(0)
        for stat, mtype, value in affixes:
            self._add_row(stat, mtype, value)
        self._loading = False

    def affixes(self) -> list:
        out = []
        for r in range(self.rowCount()):
            out.append([int(self.cellWidget(r, 0).currentData()),
                        int(self.cellWidget(r, 1).currentData()),
                        float(self.cellWidget(r, 2).value())])
        return out

    def append_row(self):
        self._add_row(int(StatType.DamagePhysical), 0, 0.0)
        self._emit()

    def _add_row(self, stat, mtype, value):
        row = self.rowCount()
        self.insertRow(row)

        stat_combo = QComboBox()
        for st in StatType:
            stat_combo.addItem(stat_name(st), int(st))

        type_combo = QComboBox()
        spin = QDoubleSpinBox()
        spin.setRange(-1e6, 1e6)
        spin.setDecimals(4)

        btn = QPushButton('×')
        btn.setFixedWidth(28)

        self.setCellWidget(row, 0, stat_combo)
        self.setCellWidget(row, 1, type_combo)
        self.setCellWidget(row, 2, spin)
        self.setCellWidget(row, 3, btn)

        # 先填初值再接信号：构造期的索引/数值变化既不该触发刷新，也不能被误当作用户改属性
        idx = stat_combo.findData(int(stat))
        stat_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._fill_types(type_combo, int(mtype))
        self._apply_hints(int(stat_combo.currentData()), type_combo, spin)
        spin.setValue(float(value))

        stat_combo.currentIndexChanged.connect(
            lambda *_, sc=stat_combo, tc=type_combo, sp=spin: self._on_stat_changed(sc, tc, sp))
        type_combo.currentIndexChanged.connect(self._emit)
        spin.valueChanged.connect(self._emit)
        btn.clicked.connect(lambda: self._remove_row(btn))

    def _on_stat_changed(self, stat_combo, type_combo, spin):
        """属性切换 → 类型自动回到该属性的规范值（物品词条在游戏里恒为加法），并刷新填写提示。"""
        if self._loading:
            return
        stat = int(stat_combo.currentData())
        self._fill_types(type_combo, 0)
        self._apply_hints(stat, type_combo, spin)
        self._emit()

    def _fill_types(self, combo, keep):
        """类型栏固定展示游戏唯一入池方式「加法」并禁用；旧构建里的非常规组合原样只读展示，
        避免静默改写数据（保存时仍原样写回）。"""
        types = list(_ALLOWED_TYPES)
        if int(keep) not in types:
            types = [int(keep)]
        combo.blockSignals(True)
        combo.clear()
        for t in types:
            combo.addItem(_MOD_LABELS[t], t)
        combo.setCurrentIndex(0)
        combo.blockSignals(False)
        combo.setEnabled(False)

    def _apply_hints(self, stat, type_combo, spin):
        frac = int(stat) in _PERCENT_STATS
        type_combo.setToolTip(_TIP_PERCENT if frac else _TIP_FLAT)
        spin.setToolTip(_TIP_VALUE_PERCENT if frac else '')
        if int(stat) in (0, 1, 2):
            spin.setToolTip(_TIP_PRIMARY_STAT)

    def _remove_row(self, btn):
        for r in range(self.rowCount()):
            if self.cellWidget(r, 3) is btn:
                self.removeRow(r)
                break
        self._emit()

    def _emit(self, *_):
        if not self._loading:
            self.changed.emit()


class ItemEditor(QGroupBox):
    """一件装备的编辑面板。weapon=True 时多出 基础伤害/攻速/技能倍率 三行。"""

    changed = Signal()

    def __init__(self, title, draft, *, weapon=False, parent=None):
        super().__init__(title, parent)
        self._loading = False
        self.draft = draft
        self.weapon = bool(weapon)
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self._on_name)
        if self.weapon:
            self.damage_spin = self._spin(form, '基础伤害', 0.0, 1e6, 2, 'base_damage')
            self.speed_spin = self._spin(form, '攻速(次/秒)', 0.0, 20.0, 3, 'base_speed')
            self.skill_spin = self._spin(form, '技能倍率', 0.0, 100.0, 3, 'skill_multiplier')
        form.addRow('名称', self.name_edit)

        self.affixes = AffixTable()
        self.affixes.changed.connect(self._on_affixes)
        add_btn = QPushButton('添加词条')
        add_btn.clicked.connect(self.affixes.append_row)

        # 导入元信息（强化等级/镶嵌宝石），只读展示；手工构建恒为空
        self.meta_label = QLabel()
        self.meta_label.setWordWrap(True)
        self.meta_label.setObjectName('weaponMeta')
        self.meta_label.setVisible(False)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(self.meta_label)
        root.addWidget(self.affixes)
        root.addWidget(add_btn)
        self.reload()

    def _spin(self, form, label, lo, hi, decimals, attr) -> QDoubleSpinBox:
        sp = QDoubleSpinBox()
        sp.setRange(lo, hi)
        sp.setDecimals(decimals)
        sp.valueChanged.connect(lambda v, a=attr: self._on_num(a, v))
        form.addRow(label, sp)
        return sp

    def set_draft(self, draft):
        self.draft = draft
        self.reload()

    def reload(self):
        self._loading = True
        self.name_edit.setText(self.draft.name)
        if self.weapon:
            self.damage_spin.setValue(getattr(self.draft, 'base_damage', 0.0))
            self.speed_spin.setValue(getattr(self.draft, 'base_speed', 1.0))
            self.skill_spin.setValue(getattr(self.draft, 'skill_multiplier', 1.0))
        self.affixes.set_affixes(self.draft.affixes)
        self._reload_meta()
        self._loading = False

    def _reload_meta(self):
        """强化/宝石元信息（内存导入的装备才有）；同时说明词条口径为「强化后」。"""
        parts = []
        if int(getattr(self.draft, 'upgrade_level', 0) or 0) > 0:
            parts.append(f'强化 +{int(self.draft.upgrade_level)}（词条数值已按游戏强化规则'
                         f'折算为强化后口径）')
        gems = list(getattr(self.draft, 'gems', None) or [])
        if gems:
            parts.append('镶嵌宝石：' + '、'.join(gems))
        self.meta_label.setText('；'.join(parts))
        self.meta_label.setVisible(bool(parts))

    def _on_name(self, text):
        if self._loading:
            return
        self.draft.name = text
        self.changed.emit()

    def _on_num(self, attr, value):
        if self._loading:
            return
        setattr(self.draft, attr, float(value))
        self.changed.emit()

    def _on_affixes(self):
        self.draft.affixes = self.affixes.affixes()
        self.changed.emit()
