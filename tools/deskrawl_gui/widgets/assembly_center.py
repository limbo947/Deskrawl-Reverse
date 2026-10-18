# -*- coding: utf-8 -*-
"""装配中心：候选排序 + 装配管理一体化（原「候选排序」与「装配浏览器」两页合并）。

合并动机：两页操作同一份 profile.assembled、复制了同款「部位/等级」参数控件三处；
统一为「一张可排序可搜索的候选表 + 已装配清单」后，参数只从 core/assembly_meta 取。
排序重算惰性：仅在装配项/参数变更或显式刷新时全量重排，词条编辑不再触发全量重算。
"""
from PySide6.QtCore import (QAbstractTableModel, QModelIndex, QSortFilterProxyModel,
                            Qt, Signal)
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu,
                               QPushButton, QSpinBox, QSplitter, QTableView, QVBoxLayout,
                               QWidget)

from ..core import calc_service
from ..core.assembly_meta import (GEM_CATEGORIES, LEVEL_LABELS, assembled_extra_text,
                                  assembly_params, gem_label, kind_param_label)
from ..core.glossary import ASSEMBLY_TEXT
from ..core.localization import assembly_display_name
from ..core.profile import (KIND_LABELS, KIND_ORDER, SLOT_LABELS, AssemblyItem)
from .common import (ModeBanner, SplitterSizesMixin, apply_narrow_stacking,
                     confirm_delete, page_header)


class _RankModel(QAbstractTableModel):
    COLUMNS = ['名称', '效果', '期望 DPS', 'ΔDPS', 'Δ%']

    def __init__(self, parent=None, name_fn=None):
        super().__init__(parent)
        self._rows = []
        self._alpha = False
        # 只影响「名称」列的显示：加入构建仍按内部名（计算链与去重都以 _name 为键）
        self._name_fn = name_fn or (lambda n: n)

    def set_alpha(self, alpha: bool):
        """α 聚合导入下，百分比类词条增量为近似（面板抹掉了池结构），行上加显式标注。"""
        self._alpha = bool(alpha)

    def set_rows(self, rows):
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def row_at(self, index: int):
        return self._rows[index]

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.COLUMNS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        r = self._rows[index.row()]
        col = index.column()
        if role == Qt.UserRole:      # 排序键：名称/效果按字符串，数值列按 float
            return [r.name, r.detail, r.dps, r.delta, r.delta_pct][col]
        if role == Qt.DisplayRole:
            detail = r.detail
            if col == 1 and self._alpha and any(int(m.type) != 0 for m in r.modifiers):
                detail += '（近似）'
            return [self._name_fn(r.name), detail, f'{r.dps:.1f}', f'{r.delta:+.1f}',
                    f'{r.delta_pct:+.2f}%'][col]
        if role == Qt.TextAlignmentRole and col >= 2:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return None


class _SearchProxy(QSortFilterProxyModel):
    """名称搜索同时匹配「中文显示名」与「内部名」。

    为什么不用 filterRole 二选一：界面显示中文，而攻略/存档里流传的是 GemDiamond5 这类内部名，
    用户两种都会敲；只按显示名过滤会让另一种输入直接 0 结果（实测冒烟因此变红）。
    """

    def filterAcceptsRow(self, source_row, source_parent):     # noqa: N802 —— Qt 覆写
        regex = self.filterRegularExpression()
        if not regex.pattern():
            return True
        index = self.sourceModel().index(source_row, 0, source_parent)
        for role in (Qt.DisplayRole, Qt.UserRole):
            text = str(self.sourceModel().data(index, role) or '')
            if regex.match(text).hasMatch():
                return True
        return False


class AssemblyCenter(SplitterSizesMixin, QWidget):
    changed = Signal()

    def __init__(self, profile, gd, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.gd = gd

        # ---- 参数条：类别 / 部位或等级 / 搜索 ----
        self.kind_combo = QComboBox()
        self.kind_combo.setToolTip('候选来源类别：宝石 / 符文 / 天赋 / 套装。切换会重建候选表。')
        for kind, label in KIND_ORDER:
            self.kind_combo.addItem(label, kind)
        self.kind_combo.currentIndexChanged.connect(self._on_kind)

        self.level_spin = QSpinBox()
        self.level_spin.setRange(1, 999)
        self.level_spin.setToolTip('符文等级 / 天赋点数 / 套装件数（随类别变化）；改动会自动重排 ΔDPS。')
        self.level_spin.valueChanged.connect(lambda _: self.refresh(deep=True))

        self.slot_combo = QComboBox()
        self.slot_combo.setToolTip('宝石镶嵌部位：同一颗宝石在护甲 / 饰品 / 武器三类部位的加成不同。')
        for value, label in GEM_CATEGORIES:
            self.slot_combo.addItem(label, value)
        self.slot_combo.setCurrentIndex(2)      # 默认武器孔（历史默认值，勿改）
        self.slot_combo.currentIndexChanged.connect(lambda _: self.refresh(deep=True))

        self.param_label = QLabel('镶嵌部位')
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText('搜索名称…')
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search)

        bar = QHBoxLayout()
        bar.addWidget(QLabel('类别'))
        bar.addWidget(self.kind_combo)
        bar.addWidget(self.param_label)
        bar.addWidget(self.level_spin)
        bar.addWidget(self.slot_combo)
        bar.addWidget(self.search_edit, 1)
        # 这里刻意不放「刷新排序」按钮：类别/等级/部位变更各自会 deep 重排，而「基线被别处
        # 改动」（如角色页调巅峰点数）由 app 在切入本页时补一次重排——按钮只会误导用户以为
        # 改完参数得记得点它。

        # ---- 候选排序表 ----
        self.hint = QLabel('—')
        self.model = _RankModel(
            self, name_fn=lambda n: assembly_display_name(self.gd, self.current_kind(), n))
        self.proxy = _SearchProxy(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(Qt.UserRole)
        self.proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy.setFilterKeyColumn(0)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.doubleClicked.connect(self._on_double_clicked)
        # 键盘/右键两条快捷路径：列表行多时不必每回都把鼠标拖到左下角的「加入构建」
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_table_menu)
        enter_sc = QShortcut(QKeySequence(Qt.Key_Return), self.table)
        enter_sc.setContext(Qt.WidgetWithChildrenShortcut)
        enter_sc.activated.connect(self._add_selected)
        add_btn = QPushButton('加入构建')
        add_btn.clicked.connect(self._add_selected)

        table_box = QWidget()
        table_lay = QVBoxLayout(table_box)
        table_lay.setContentsMargins(0, 0, 0, 0)
        table_lay.addWidget(self.hint)
        table_lay.addWidget(self.table, 1)
        btn_bar = QHBoxLayout()
        btn_bar.addStretch(1)
        btn_bar.addWidget(add_btn)
        table_lay.addLayout(btn_bar)

        # ---- 已装配清单（就地改参数 + 删除确认）----
        self.assembled_list = QListWidget()
        self.assembled_list.setToolTip('已装配条目会进属性表与排序基线（即 ΔDPS 的比较基准）；'
                                       '选中条目可在下方就地改等级 / 镶嵌部位。')
        # 长名称在窄栏里会被省略号截断：两行显示（名称 / 种类·参数）+ 全量 tooltip，
        # 右键或 Delete 直接移除——不必先选中再跑到底部按「删除选中…」
        self.assembled_list.setWordWrap(True)
        self.assembled_list.currentRowChanged.connect(self._on_assembled_selected)
        self.assembled_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.assembled_list.customContextMenuRequested.connect(self._on_assembled_menu)
        remove_sc = QShortcut(QKeySequence.Delete, self.assembled_list)
        remove_sc.setContext(Qt.WidgetWithChildrenShortcut)
        remove_sc.activated.connect(self._remove_selected)
        self.edit_level_spin = QSpinBox()
        self.edit_level_spin.setRange(1, 999)
        self.edit_slot_combo = QComboBox()
        self.edit_slot_combo.setToolTip('宝石镶嵌部位：同一颗宝石在护甲 / 饰品 / 武器三类部位加成不同。')
        for value, label in GEM_CATEGORIES:
            self.edit_slot_combo.addItem(label, value)
        self.edit_label = QLabel('等级')
        apply_btn = QPushButton('应用修改')
        apply_btn.clicked.connect(self._apply_assembled_edit)
        remove_btn = QPushButton('删除选中…')
        remove_btn.clicked.connect(self._remove_selected)
        edit_bar = QHBoxLayout()
        edit_bar.addWidget(self.edit_label)
        edit_bar.addWidget(self.edit_level_spin)
        edit_bar.addWidget(self.edit_slot_combo)
        edit_bar.addWidget(apply_btn)
        right_box = QWidget()
        right_lay = QVBoxLayout(right_box)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.addWidget(QLabel('已装配（参与属性表与排序基线）'))
        right_lay.addWidget(self.assembled_list, 1)
        right_lay.addLayout(edit_bar)
        right_lay.addWidget(remove_btn)

        self._splitter = QSplitter()
        self._init_splitter_sizes(self._splitter)
        self._splitter.addWidget(table_box)
        self._splitter.addWidget(right_box)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        self._splitter.setSizes([860, 360])

        self.banner = ModeBanner()
        tip = QLabel('提示：双击候选行或点「加入构建」把该候选按当前等级/部位加入构建；'
                     '选中已装配条目可就地改等级/部位。')
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.addWidget(page_header('装配中心', '宝石 / 符文 / 天赋 / 套装：搜索、按 ΔDPS 排序、加入构建',
                                   ASSEMBLY_TEXT))
        root.addLayout(bar)
        root.addWidget(self.banner)
        root.addWidget(self._splitter, 1)
        root.addWidget(tip)

        self._on_kind()

    def resizeEvent(self, event):
        """窄窗口把「候选表 | 已装配栏」改为上下堆叠（见 common.apply_narrow_stacking）。"""
        super().resizeEvent(event)
        apply_narrow_stacking(self._splitter, event.size().width())
        self._remember_splitter()

    # ---------------- 参数 ----------------
    def current_kind(self) -> str:
        return self.kind_combo.currentData()

    def _params(self):
        """按类别归一化为 AssemblyItem(level, category)，语义单一来源在 core/assembly_meta。"""
        kind = self.current_kind()
        if kind == 'gem':
            return assembly_params(kind, level=1, category=int(self.slot_combo.currentData()))
        return assembly_params(kind, level=int(self.level_spin.value()), category=2)

    def _on_kind(self):
        kind = self.current_kind()
        is_gem = kind == 'gem'
        self.level_spin.setVisible(not is_gem)
        self.slot_combo.setVisible(is_gem)
        self.param_label.setText(kind_param_label(kind))
        self.refresh(deep=True)

    def _on_search(self, text):
        # 借代理模型整串过滤（对名称列子串匹配），列表不重建
        self.proxy.setFilterFixedString(text.strip())

    # ---------------- 计算与渲染 ----------------
    def refresh(self, deep: bool = False):
        """deep=True 才全量重排候选（编辑词条等轻量刷新只同步已装配清单与降级态）。"""
        self.banner.update_mode(self.profile)
        self._refresh_assembled()
        if deep:
            self._recompute()

    def _recompute(self):
        kind = self.current_kind()
        level, category = self._params()
        rows = calc_service.rank_candidates(self.profile, self.gd, kind,
                                            level=level, category=category)
        alpha = getattr(self.profile, 'import_mode', '') == 'alpha'
        self.model.set_alpha(alpha)
        self.model.set_rows(rows)
        self.table.sortByColumn(3, Qt.DescendingOrder)      # 新数据回填后回到 ΔDPS 降序
        hint = (f'{KIND_LABELS[kind]}候选 {len(rows)} 条；基线 DPS = '
                f'{calc_service.baseline_dps(self.profile, self.gd):.1f}')
        if alpha:
            hint += '；α 聚合导入：基线=游戏面板，百分比类（非加法）词条增量为近似'
        self.hint.setText(hint)

    def _refresh_assembled(self):
        current = self.assembled_list.currentRow()
        self.assembled_list.blockSignals(True)
        self.assembled_list.clear()
        for it in self.profile.assembled:
            extra = assembled_extra_text(it.kind, it.level, it.category,
                                         self._slot_label(it))
            kind_cn = KIND_LABELS.get(it.kind, it.kind)
            # 两行：第一行名称（窄栏里至少能读全名字），第二行种类与参数；全量信息进 tooltip。
            # 参数行不直接复用 extra：其中「｜@未标注」在单行里像半句话，悬停看全量更清楚。
            param = (f'{gem_label(it.category)}孔' if it.kind == 'gem'
                     else f'{LEVEL_LABELS.get(it.kind, "等级")} {it.level}')
            shown = assembly_display_name(self.gd, it.kind, it.name)
            item = QListWidgetItem(f'{shown}\n{kind_cn} · {param}')
            item.setToolTip(f'{kind_cn}｜{shown}（{it.name}）｜{extra}')
            self.assembled_list.addItem(item)
        row = min(current, len(self.profile.assembled) - 1)
        self.assembled_list.setCurrentRow(row)
        self.assembled_list.blockSignals(False)
        self._sync_edit_widgets()

    def _on_assembled_menu(self, pos):
        """右键菜单：只给「移除」——改等级/部位是选中后下方的控件，重复一份只会两处并存。"""
        row = self.assembled_list.indexAt(pos).row()
        if row < 0:
            return
        self.assembled_list.setCurrentRow(row)
        menu = QMenu(self)
        act = menu.addAction('移除该条目…')
        if menu.exec(self.assembled_list.mapToGlobal(pos)) is act:
            self._remove_selected()

    @staticmethod
    def _slot_label(item) -> str:
        """宝石的归属槽展示名：手工加入的宝石未标注（计入全部槽基线），导入件带实测槽 id。

        计算链按 `slot` 把宝石从对应槽的基线里减去，所以归属槽必须写出来可供核对。
        """
        if item.kind != 'gem':
            return ''
        slot = int(getattr(item, 'slot', -1))
        if slot < 0:
            return '未标注'
        return SLOT_LABELS.get(slot, f'槽{slot}')

    # ---------------- 加入构建 ----------------
    def _add_name(self, name: str):
        if not name:
            return
        kind = self.current_kind()
        level, category = self._params()
        self.profile.assembled.append(AssemblyItem(kind, name, level, category))
        self.refresh(deep=True)     # 装配项变更影响排序基线 → 本页立即全量重排
        self.changed.emit()

    def _on_table_menu(self, pos):
        """候选表右键：加入构建（与双击、回车同一入口，保证「同一动作只有一处实现」）。"""
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        self.table.setCurrentIndex(index)
        menu = QMenu(self)
        act = menu.addAction('加入构建')
        if menu.exec(self.table.viewport().mapToGlobal(pos)) is act:
            self._add_selected()

    def _on_double_clicked(self, proxy_index):
        src = self.proxy.mapToSource(proxy_index)
        if not src.isValid():
            return
        self._add_name(self.model.row_at(src.row()).name)

    def _add_selected(self):
        src = self.proxy.mapToSource(self.table.currentIndex())
        if not src.isValid():
            return
        self._add_name(self.model.row_at(src.row()).name)

    # ---------------- 已装配管理 ----------------
    def _on_assembled_selected(self, row):
        self._sync_edit_widgets()

    def _sync_edit_widgets(self):
        """按选中条目切换参数编辑控件：宝石调部位（等级恒 1），其余调等级；无选中则整组隐藏。"""
        row = self.assembled_list.currentRow()
        if row < 0 or row >= len(self.profile.assembled):
            self.edit_label.setText('选中条目后修改')
            self.edit_level_spin.setVisible(False)
            self.edit_slot_combo.setVisible(False)
            self.edit_level_spin.setEnabled(False)
            self.edit_slot_combo.setEnabled(False)
            return
        it = self.profile.assembled[row]
        is_gem = it.kind == 'gem'
        self.edit_level_spin.setVisible(not is_gem)
        self.edit_slot_combo.setVisible(is_gem)
        self.edit_label.setText('镶嵌部位' if is_gem else kind_param_label(it.kind))
        self.edit_level_spin.setEnabled(True)
        self.edit_slot_combo.setEnabled(True)
        if is_gem:
            idx = self.edit_slot_combo.findData(int(it.category))
            self.edit_slot_combo.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            self.edit_level_spin.setValue(max(1, int(it.level)))

    def _apply_assembled_edit(self):
        row = self.assembled_list.currentRow()
        if row < 0 or row >= len(self.profile.assembled):
            return
        it = self.profile.assembled[row]
        if it.kind == 'gem':
            it.category = int(self.edit_slot_combo.currentData())
        else:
            it.level = int(self.edit_level_spin.value())
        self.refresh(deep=True)
        self.changed.emit()

    def _remove_selected(self):
        row = self.assembled_list.currentRow()
        if row < 0 or row >= len(self.profile.assembled):
            return
        it = self.profile.assembled[row]
        if not confirm_delete(self, '删除已装配条目',
                              f'确定删除「{KIND_LABELS.get(it.kind, it.kind)}｜{it.name}」？'):
            return
        del self.profile.assembled[row]
        self.refresh(deep=True)
        self.changed.emit()

    def reload(self):
        """换数据源（导入/加载构建）后回填并全量重排。"""
        idx = self.kind_combo.findData('gem')
        self.kind_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._on_kind()
