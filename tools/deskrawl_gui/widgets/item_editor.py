# -*- coding: utf-8 -*-
"""单件装备的编辑面板（任意槽通用；武器多出基础伤害/攻速/技能倍率三行）。

从 equipment_editor 拆出：装备对比页要按 11 个槽位复用同一套「名称 + 词条行 + 元信息」控件，
把它独立成 ItemEditor 后，equipment_editor 只负责槽位切换与装配，避免单文件膨胀。
控件直接写回传入的草稿（WeaponDraft / ItemDraft），改动只发 changed 信号。

两种受限态（都在 EquipmentEditor 里按导入来源决定）：
- set_locked：当前件即游戏里的既成事实，只读展示——基线被改脏则整页对比口径失效；
- current_of：候选侧专用（任意槽），「与当前装备相同（强化/宝石）」开关据此镜像当前件。
"""
from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox,
                               QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from deskrawl_calc import StatType, stat_name

from ..core.calc_service import MOD_TYPE_CN
from ..core.item_draft import apply_upgrade
from .common import QtySpinBox

# 类型中文名单一来源在 core（与候选摘要 describe_mods 共用），此处只做视图所需的查表
_MOD_LABELS = dict(MOD_TYPE_CN)

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
# 主属性提示（Player.CalcDamage@0x518230：攻击伤害 ×(1+Final(职业主属性)/100)，每点即 +1% 伤害加成）
_TIP_PRIMARY_STAT = ('主属性：仅「职业主属性」（左栏设定/内存导入自动识别）参与攻击伤害——'
                     '按游戏公式 ×(1+最终值/100)，每点 +1% 伤害加成；其余主属性只提供护甲/魔抗')


class AffixTable(QTableWidget):
    """词条行表：属性（内核 StatType 全量中文名）/ 类型（只读文本「加法」）/ 数值 / 删除。

    类型为什么不做成下拉：装备词条的入池方式由游戏固定（ItemData 与宝石/符文/套装实测
    100% 为加法），单值用下拉承载会误导——实测被禁用下拉与启用中的输入框外观一致（底色
    同为 #262B30），用户会反复尝试点它。故类型列只用文本陈述事实；旧构建里的非常规组合
    原样展示并标「非常规」，不静默改写。
    """

    changed = Signal()
    # 某行的属性/数值变化 → (stat, value)：外围据此刷新区间提示（不参与计算，只做提示）
    rowTouched = Signal(int, float)
    # 某行被删除 → (行号, [属性, 类型, 数值])：外围据此给一次性的「撤销删除」入口（误点可回退）
    rowRemoved = Signal(int, list)
    COLUMNS = ['属性', '类型', '数值', '']

    def __init__(self, parent=None):
        super().__init__(0, len(self.COLUMNS), parent)
        self._loading = False
        self._locked = False
        self.setHorizontalHeaderLabels(self.COLUMNS)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        # 单元格里已是带描边的控件，再叠网格线会形成"表格框+网格+控件框"三层线（视觉噪音）
        self.setShowGrid(False)
        self.setAlternatingRowColors(True)
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
            type_item = self.item(r, 1)
            out.append([int(self.cellWidget(r, 0).currentData()),
                        int(type_item.data(Qt.UserRole) if type_item is not None else 0),
                        float(self.cellWidget(r, 2).value())])
        return out

    def append_row(self):
        if self._locked:
            return
        self._add_row(int(StatType.DamagePhysical), 0, 0.0)
        self._emit()

    def insert_row(self, row, stat, mtype, value):
        """把一行按原位置放回（撤销删除用）。

        顺序不影响计算，但按原位置放回才是用户预期的「撤销」——否则词条会跳到表尾，
        用户还得自己判断放回去的是不是同一条。
        """
        if self._locked:
            return
        self._add_row(stat, mtype, value, row=row)
        self._emit()

    def set_locked(self, locked):
        """整表只读化（当前件固定态）：属性/数值不可改、删除按钮隐藏，仍是可读的事实展示。"""
        self._locked = bool(locked)
        # 整列隐藏而不是只藏按钮：留一个没有内容的空列会在右侧撕出一条无意义的留白
        self.setColumnHidden(3, self._locked)
        for row in range(self.rowCount()):
            self._apply_lock(row)

    def _apply_lock(self, row):
        self.cellWidget(row, 0).setEnabled(not self._locked)
        self.cellWidget(row, 2).setReadOnly(self._locked)
        self.cellWidget(row, 3).setVisible(not self._locked)

    def _row_of(self, widget, col=0) -> int:
        """按控件身份反查所在行：行号会随删行前移，建行时捕获的索引不可靠。"""
        for r in range(self.rowCount()):
            if self.cellWidget(r, col) is widget:
                return r
        return -1

    def _add_row(self, stat, mtype, value, row=None):
        row = self.rowCount() if row is None else max(0, min(int(row), self.rowCount()))
        self.insertRow(row)

        stat_combo = QComboBox()
        for st in StatType:
            stat_combo.addItem(stat_name(st), int(st))

        spin = QtySpinBox()
        spin.setRange(-1e6, 1e6)

        btn = QPushButton('×')
        btn.setFixedWidth(28)

        self.setCellWidget(row, 0, stat_combo)
        self.setItem(row, 1, QTableWidgetItem(''))
        self.setCellWidget(row, 2, spin)
        self.setCellWidget(row, 3, btn)

        # 先填初值再接信号：构造期的索引/数值变化既不该触发刷新，也不能被误当作用户改属性
        idx = stat_combo.findData(int(stat))
        stat_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._set_type_cell(row, int(mtype))
        self._apply_hints(row, int(stat_combo.currentData()), spin)
        spin.setValue(float(value))

        stat_combo.currentIndexChanged.connect(
            lambda *_, sc=stat_combo, sp=spin: self._on_stat_changed(sc, sp))
        spin.valueChanged.connect(lambda v, sp=spin: self._touch(sp, v))
        spin.valueChanged.connect(self._emit)
        btn.clicked.connect(lambda: self._remove_row(btn))
        self._apply_lock(row)

    def _touch(self, spin, value):
        """行内数值变化 → 播报 (stat, value) 给外围做区间提示；回填期间不播报。"""
        if self._loading:
            return
        row = self._row_of(spin, 2)
        if row >= 0:
            self.rowTouched.emit(int(self.cellWidget(row, 0).currentData()), float(value))

    def _on_stat_changed(self, stat_combo, spin):
        """属性切换 → 类型自动回到该属性的规范值（物品词条在游戏里恒为加法），并刷新填写提示。"""
        if self._loading:
            return
        row = self._row_of(stat_combo)
        if row < 0:
            return
        stat = int(stat_combo.currentData())
        self._set_type_cell(row, 0)
        self._apply_hints(row, stat, spin)
        self._touch(spin, spin.value())
        self._emit()

    def _set_type_cell(self, row, mtype):
        """类型列写文本（游戏唯一入池方式「加法」）；词条值原样存 UserRole 供 affixes() 读回。

        旧构建里的非常规组合（非加法）原样展示并标「非常规」：保存时仍原样写回，不静默改写。
        """
        label = _MOD_LABELS.get(int(mtype), str(mtype))
        if int(mtype) not in _ALLOWED_TYPES:
            label += '（非常规）'
        item = self.item(row, 1)
        if item is None:
            return
        item.setText(label)
        item.setData(Qt.UserRole, int(mtype))
        item.setTextAlignment(Qt.AlignCenter)

    def _apply_hints(self, row, stat, spin):
        frac = int(stat) in _PERCENT_STATS
        item = self.item(row, 1)
        if item is not None:
            item.setToolTip(_TIP_PERCENT if frac else _TIP_FLAT)
        spin.setToolTip(_TIP_VALUE_PERCENT if frac else '')
        if int(stat) in (0, 1, 2):
            spin.setToolTip(_TIP_PRIMARY_STAT)

    def _remove_row(self, btn):
        """删行即时生效并播报被删内容：外围据此给「撤销」入口，不用确认框打断连续编辑。"""
        for r in range(self.rowCount()):
            if self.cellWidget(r, 3) is btn:
                type_item = self.item(r, 1)
                snapshot = [int(self.cellWidget(r, 0).currentData()),
                            int(type_item.data(Qt.UserRole) if type_item is not None else 0),
                            float(self.cellWidget(r, 2).value())]
                self.removeRow(r)
                self.rowRemoved.emit(r, snapshot)
                break
        self._emit()

    def _emit(self, *_):
        if not self._loading:
            self.changed.emit()


class ItemEditor(QGroupBox):
    """一件装备的编辑面板。weapon=True 时多出 基础伤害/攻速/技能倍率 三行。

    current_of 只在候选侧传入（返回「当前件」草稿，任意槽通用）：勾选「与当前装备相同」时
    镜像当前件的强化等级与镶嵌宝石，并按原始词条重算数值——「同强化同宝石谁更强」是换装
    对比的常见问题，对所有槽位同样成立。
    """

    changed = Signal()
    # 开关选择本身也播报（EquipmentEditor 据此写 profile.like_current_pref，实现跨槽保持）
    likeCurrentChanged = Signal(bool)

    def __init__(self, title, draft, *, weapon=False, current_of=None, name_resolver=None,
                 range_hint=None, parent=None):
        """name_resolver: (装备名) -> 是否能在游戏装备表命中。
        range_hint: (stat, value, item_level, rarity) -> 区间提示文案（内核 affix_range 口径）。

        前者是「名字不对会让传奇特效消失」的判定来源（calc_service.name_known），后者把
        词条数值折算成「在该物品等级/稀有度下的位置」；都不传则关闭对应提示（测试/离线路径）。
        """
        super().__init__(title, parent)
        self._base_title = title
        self._loading = False
        self._locked = False
        self._spins = []
        self.draft = draft
        self.weapon = bool(weapon)
        self._current_of = current_of
        self._name_resolver = name_resolver
        self._range_hint = range_hint
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self._on_name)
        form.addRow('名称', self.name_edit)
        if self.weapon:
            self.damage_spin = self._spin(form, '基础伤害', 0.0, 1e6, 2, 'base_damage')
            self.speed_spin = self._spin(form, '攻速(次/秒)', 0.0, 20.0, 3, 'base_speed')
            self.skill_spin = self._spin(form, '技能倍率', 0.0, 100.0, 3, 'skill_multiplier')
        if current_of is not None:
            self.like_current = QCheckBox()
            self.like_current.setToolTip(
                '勾选：候选沿用当前装备的强化等级与镶嵌宝石，并按背包原始词条重算「强化后」数值\n'
                '（即「同强化同宝石谁更强」的对照）；取消：回到该件在背包里的原貌。')
            self.like_current.toggled.connect(self._on_like_current)
            form.addRow('强化/宝石', self.like_current)
        else:
            # 候选侧这一行是「与当前装备相同」开关；当前侧留同一行的只读事实——两侧表单行数
            # 相等，下方词条表才严格同高，逐行比对（V8）不会一边高一边低；这一行同时也是
            # 「候选勾上会镜像什么」的答案（+N 与宝石数），比翻下面那行元信息更快。
            self.fact_label = QLabel('—')
            self.fact_label.setObjectName('weaponMeta')
            form.addRow('强化/宝石', self.fact_label)

        self.affixes = AffixTable()
        self.affixes.changed.connect(self._on_affixes)
        self.affixes.rowTouched.connect(self._on_row_touched)
        self.affixes.rowRemoved.connect(self._on_row_removed)
        self.add_btn = QPushButton('添加词条')
        self.add_btn.clicked.connect(self.affixes.append_row)

        # 删除撤销条：删行即时生效（不打断连续编辑），误点则有一处可回退——只在最近一次删除后
        # 出现片刻，不常驻占位。为什么不做确认框：删一条词条很轻，弹框反而让连续删改变慢。
        self.undo_label = QLabel('')
        self.undo_label.setObjectName('inlineNotice')
        self.undo_btn = QPushButton('撤销')
        self.undo_bar = QWidget()
        undo_lay = QHBoxLayout(self.undo_bar)
        undo_lay.setContentsMargins(0, 0, 0, 0)
        undo_lay.setSpacing(8)
        undo_lay.addWidget(self.undo_label)
        undo_lay.addWidget(self.undo_btn)
        undo_lay.addStretch(1)
        self.undo_bar.setVisible(False)
        self._undo_state = None          # (行号, [属性, 类型, 数值])：仅提示条可见期间有效
        self._undo_timer = QTimer(self)
        self._undo_timer.setSingleShot(True)
        self._undo_timer.setInterval(8000)
        self._undo_timer.timeout.connect(self._hide_undo)
        self.undo_btn.clicked.connect(self._undo_delete)

        # 导入元信息（强化等级/镶嵌宝石），只读展示；手工构建恒为空
        self.meta_label = QLabel()
        self.meta_label.setWordWrap(True)
        self.meta_label.setObjectName('weaponMeta')
        self.meta_label.setVisible(False)

        # 词条区间提示（改某条数值时刷新）：同一数值在不同物品等级/稀有度下评价完全不同
        self.range_label = QLabel('')
        self.range_label.setObjectName('weaponMeta')
        self.range_label.setWordWrap(True)
        self.range_label.setVisible(False)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(self.meta_label)
        root.addWidget(self.affixes)
        root.addWidget(self.undo_bar)
        root.addWidget(self.range_label)
        root.addWidget(self.add_btn)
        self.reload()

    # ---- 删除撤销 ----
    def _on_row_removed(self, row, snapshot):
        """记下被删行并亮出撤销条；8 秒后自动收起（只保留最近一次，避免堆积提示）。"""
        if self._loading or self._locked:
            return
        self._undo_state = (int(row), [int(snapshot[0]), int(snapshot[1]), float(snapshot[2])])
        self.undo_label.setText(
            f'已删除词条「{stat_name(int(snapshot[0]))}」（{float(snapshot[2]):g}）')
        self.undo_bar.setVisible(True)
        self._undo_timer.start()

    def _undo_delete(self):
        """把最近删掉的一行按原位置放回；数值原样保留，故无需用户重填。"""
        if self._undo_state is None:
            return
        row, (stat, mtype, value) = self._undo_state
        self.affixes.insert_row(row, stat, mtype, value)   # 内部 emit changed → 回写草稿 + 刷新
        self._hide_undo()

    def _hide_undo(self):
        self._undo_state = None
        self._undo_timer.stop()
        self.undo_bar.setVisible(False)

    def _on_row_touched(self, stat, value):
        """就地给出「本条落在什么区间」——手工录入时最需要它，否则无从判断这条词条算高还是算低。"""
        if self._range_hint is None:
            return
        text = self._range_hint(stat, value, int(getattr(self.draft, 'item_level', 0) or 0),
                                int(getattr(self.draft, 'rarity', 0) or 0))
        self.range_label.setText(text)
        self.range_label.setVisible(bool(text))

    def _spin(self, form, label, lo, hi, decimals, attr) -> QtySpinBox:
        sp = QtySpinBox(decimals=decimals)
        sp.setRange(lo, hi)
        sp.valueChanged.connect(lambda v, a=attr: self._on_num(a, v))
        form.addRow(label, sp)
        self._spins.append(sp)
        return sp

    def set_draft(self, draft):
        self.draft = draft
        self.reload()

    def set_locked(self, locked):
        """固定本卡片（当前件 = 游戏里的既成事实）：只读展示。

        基线是整页对比的口径来源，改脏它会得到「看起来合理但无意义」的 Δ，所以宁可不给输入口。
        """
        locked = bool(locked)
        self._locked = locked
        self.name_edit.setReadOnly(locked)
        for sp in self._spins:
            sp.setReadOnly(locked)
        self.affixes.set_locked(locked)
        self.add_btn.setEnabled(not locked)
        self.setTitle(self._base_title + ('（已固定·不可编辑）' if locked else ''))
        self.setToolTip('当前装备来自游戏导入，数值已固定为只读；要试验改动请在候选侧进行。'
                        if locked else '')

    def reload(self):
        self._loading = True
        self._hide_undo()        # 内容被整体换掉（换槽/载入导入件）后，旧的行号与数值都不再对应
        self.name_edit.setText(self.draft.name)
        if self.weapon:
            self.damage_spin.setValue(getattr(self.draft, 'base_damage', 0.0))
            self.speed_spin.setValue(getattr(self.draft, 'base_speed', 1.0))
            self.skill_spin.setValue(getattr(self.draft, 'skill_multiplier', 1.0))
        self.affixes.set_affixes(self.draft.affixes)
        self._reload_meta()
        if hasattr(self, 'like_current'):
            self.like_current.setChecked(bool(getattr(self.draft, 'like_current', False)))
            self._update_like_text()
        else:
            self.fact_label.setText(self._fact_text())
        self._mark_name(self.draft.name)
        self._loading = False

    def _mark_name(self, text):
        """名称不在装备表命中时给输入框描警示边并写明后果（特效会被静默丢掉）。

        回填（reload）也要走一遍：导入件的名字可能是本地化表缺项，那时候用户根本没编辑过。
        """
        bad = bool(str(text).strip()) and self._name_resolver is not None \
            and not bool(self._name_resolver(str(text).strip()))
        self.name_edit.setProperty('invalid', 'true' if bad else '')
        self.name_edit.style().unpolish(self.name_edit)
        self.name_edit.style().polish(self.name_edit)
        self.name_edit.setToolTip(
            '该名称未在游戏装备表中命中：这件装备的传奇特效将不计入计算。\n'
            '名称需与游戏内一致（可在装备槽工具条的「从背包/仓库导入」里整件载入）。'
            if bad else '')

    def _reload_meta(self):
        """强化/宝石元信息（内存导入的装备才有）；同时说明词条口径为「强化后」。"""
        parts = []
        if int(getattr(self.draft, 'upgrade_level', 0) or 0) > 0:
            parts.append(f'强化 +{int(self.draft.upgrade_level)}（词条数值已按游戏强化规则'
                         f'折算为强化后口径）')
        gems = list(getattr(self.draft, 'gems', None) or [])
        if gems:
            parts.append('镶嵌宝石：' + '、'.join(gems))
        if (getattr(self.draft, 'like_current', False)
                and not (getattr(self.draft, 'raw_modifiers', None) or [])):
            parts.append('已镜像当前装备的强化/宝石；该件无强化前原貌，词条数值未重算')
        self.meta_label.setText('；'.join(parts))
        self.meta_label.setVisible(bool(parts))

    # ---- 「与当前装备相同（强化/宝石）」 ----
    def _on_like_current(self, checked):
        if self._loading or self._locked or self._current_of is None:
            return
        cur = self._current_of()
        checked = bool(checked)
        if checked and not getattr(self.draft, 'like_current', False):
            # 记下自身原貌：取消勾选要能原样还原（背包里的 +N 与宝石）
            self.draft.own_upgrade_level = int(getattr(self.draft, 'upgrade_level', 0) or 0)
            self.draft.own_gems = list(getattr(self.draft, 'gems', None) or [])
        self.draft.like_current = checked
        if checked:
            level = int(getattr(cur, 'upgrade_level', 0) or 0)
            self.draft.gems = list(getattr(cur, 'gems', None) or [])
        else:
            level = int(getattr(self.draft, 'own_upgrade_level', 0) or 0)
            self.draft.gems = list(getattr(self.draft, 'own_gems', None) or [])
        self.draft.upgrade_level = level
        self._refold(level)
        self.reload()
        self.likeCurrentChanged.emit(checked)
        self.changed.emit()

    def _refold(self, level):
        """按背包原始词条重算「强化后」数值（与导入链 apply_upgrade 同一模型）。

        原始词条缺失（手工逐条输入）时不动数值——没有强化前基线就推不出强化后的值，
        此时 _reload_meta 会显式说明，避免用户误以为改动已生效。
        """
        raw = [[int(s), int(t), float(v)]
               for s, t, v in (getattr(self.draft, 'raw_modifiers', None) or [])]
        if not raw:
            return False
        affixes, speed = apply_upgrade(raw, level)
        self.draft.affixes = [[int(s), int(t), float(v)] for s, t, v in affixes]
        # 攻速词条(21) 的折算值就是武器基础攻速的来源（与面板 nsq[21] 同语义）
        if any(int(s) == int(StatType.WeaponSpeed) for s, _t, _v in raw):
            self.draft.base_speed = float(speed) or float(getattr(self.draft, 'base_speed', 1.0))
        return True

    def _update_like_text(self):
        """开关文案写出当前件的强化与宝石数——用户不必切页核对当前装备。"""
        cur = self._current_of() if self._current_of is not None else None
        lv = int(getattr(cur, 'upgrade_level', 0) or 0)
        gems = len(list(getattr(cur, 'gems', None) or []))
        now = f'强化 +{lv}' if lv else '无强化'
        gs = f'{gems} 颗宝石' if gems else '无宝石'
        self.like_current.setText(f'与当前装备相同（{now}、{gs}）')

    def _fact_text(self) -> str:
        """当前件的强化/宝石事实（当前侧的只读行），词序与候选侧开关文案同款，便于左右对照。"""
        lv = int(getattr(self.draft, 'upgrade_level', 0) or 0)
        gems = len(list(getattr(self.draft, 'gems', None) or []))
        parts = ([f'强化 +{lv}'] if lv else []) + ([f'{gems} 颗宝石'] if gems else [])
        return '、'.join(parts) if parts else '无强化、无宝石'

    def _on_name(self, text):
        if self._loading or self._locked:
            return
        self.draft.name = text
        self._mark_name(text)
        self.changed.emit()

    def _on_num(self, attr, value):
        if self._loading or self._locked:
            return
        setattr(self.draft, attr, float(value))
        self.changed.emit()

    def _on_affixes(self):
        if self._loading or self._locked:
            return
        self.draft.affixes = self.affixes.affixes()
        self.changed.emit()
