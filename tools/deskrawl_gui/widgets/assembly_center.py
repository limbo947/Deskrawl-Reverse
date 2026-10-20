# -*- coding: utf-8 -*-
"""装配中心：候选排序 + 装配管理一体化（原「候选排序」与「装配浏览器」两页合并）。

合并动机：两页操作同一份 profile.assembled、复制了同款「部位/等级」参数控件三处；
统一为「一张可排序可搜索的候选表 + 已装配清单」后，参数只从 core/assembly_meta 取。
排序重算惰性：仅在装配项/参数变更或显式刷新时全量重排，词条编辑不再触发全量重算。
"""
from PySide6.QtCore import (QAbstractTableModel, QModelIndex, QSortFilterProxyModel,
                            Qt, QTimer, Signal)
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QFrame,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMenu, QPushButton, QSpinBox, QSplitter,
                               QStyle, QStyledItemDelegate, QStyleOptionViewItem,
                               QTableView, QVBoxLayout, QWidget)

from ..core import calc_service
from ..core.assembly_meta import (GEM_CATEGORIES, LEVEL_LABELS, assembled_extra_text,
                                  assembly_params, gem_label, kind_param_label)
from ..core.glossary import ASSEMBLY_TEXT
from ..core.localization import assembly_display_name
from ..core.profile import (KIND_LABELS, KIND_ORDER, SLOT_LABELS, AssemblyItem)
from .common import (Card, ModeBanner, MonoDelegate, SplitterSizesMixin, add_table_export,
                     apply_narrow_stacking, cap_page_width, confirm_delete, mono_font,
                     page_header, scroll_host)
from .compare_view import _trend_color
from .icons import icon
from .segmented import SegmentedTabs


class _RankModel(QAbstractTableModel):
    COLUMNS = ['名称', '效果', '期望 DPS', 'ΔDPS', 'Δ%']
    # 涨跌三态走独立角色：委托据此取 QSS 解析出的颜色（代码里不抄第二份色值）
    TREND_ROLE = Qt.UserRole + 2
    _FLAT_DELTA = 0.05
    _FLAT_PCT = 0.005

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

    @staticmethod
    def _arrow(value: float, limit: float) -> str:
        """涨跌箭头：与颜色并行的第二通道（色弱用户不必依赖红绿）。

        与技能表 Δ% 列同一取向：读成「+0.0」的差值不给箭头，否则「没变」会被看成「变了」。
        """
        if abs(float(value)) < limit:
            return ''
        return '▲ ' if value > 0 else '▼ '

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
            if col == 3:
                return f'{self._arrow(r.delta, self._FLAT_DELTA)}{r.delta:+.1f}'
            if col == 4:
                return f'{self._arrow(r.delta_pct, self._FLAT_PCT)}{r.delta_pct:+.2f}%'
            return [self._name_fn(r.name), detail, f'{r.dps:.1f}'][col]
        if role == self.TREND_ROLE and col in (3, 4):
            value = float(r.delta if col == 3 else r.delta_pct)
            limit = self._FLAT_DELTA if col == 3 else self._FLAT_PCT
            return 'flat' if abs(value) < limit else ('up' if value > 0 else 'down')
        if role == Qt.TextAlignmentRole and col >= 2:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return None


class _TrendDelegate(QStyledItemDelegate):
    """Δ 列只改文字颜色，背景/选中态仍交给基类（与技能表 Δ% 列同一实现思路）。"""

    def initStyleOption(self, option, index):         # noqa: N802 —— Qt 覆写
        # 覆写 paint 后这里才是「数值列换等宽字形」的唯一入口：字号仍随 opt.font（QSS）
        super().initStyleOption(option, index)
        option.font = mono_font(option.font)

    def paint(self, painter, option, index):          # noqa: N802 —— Qt 覆写
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        trend = index.data(_RankModel.TREND_ROLE)
        if not trend:
            super().paint(painter, option, index)
            return
        text, opt.text = opt.text, ''
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)
        painter.save()
        painter.setFont(opt.font)        # 自定义绘制要自己带字体，否则退回控件默认（非等宽）
        painter.setPen(_trend_color(trend))
        painter.drawText(opt.rect.adjusted(0, 0, -4, 0), Qt.AlignRight | Qt.AlignVCenter, text)
        painter.restore()


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


# 目标状态 → 中文（顺序与 target_editor 的勾选框一致；只用于本页的只读摘要）
_COND_CN = (('elite', '精英'), ('vulnerable', '易伤'), ('slowed', '减速'),
            ('immobilized', '定身'), ('bleeding', '流血'), ('poisoned', '中毒'),
            ('burned', '灼烧'), ('distant', '远处'), ('stunned', '眩晕'))


class AssemblyCenter(SplitterSizesMixin, QWidget):
    changed = Signal()
    targetRequested = Signal()      # 「目标设置 →」：切到对比页（目标口径在那里改）

    def __init__(self, profile, gd, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.gd = gd

        # ---- 参数条：类别（横向标签，对应 markets-table-card 的 tab 行）/ 部位或等级 / 搜索 ----
        self.kind_combo = SegmentedTabs()
        for kind, label in KIND_ORDER:
            self.kind_combo.addItem(label, kind)
            self.kind_combo.set_tab_tooltip(self.kind_combo.count() - 1,
                                            f'候选来源：{label}。切换会重建候选表。')
        self.kind_combo.currentIndexChanged.connect(self._on_kind)

        # 参数变更走 120ms 合并：连点微调/键入两位数时不必每步都跑一次全量重排（符文实测 14ms/次）
        self._deep_timer = QTimer(self)
        self._deep_timer.setSingleShot(True)
        self._deep_timer.setInterval(120)
        self._deep_timer.timeout.connect(lambda: self.refresh(deep=True))

        self.level_spin = QSpinBox()
        self.level_spin.setRange(1, 999)
        self.level_spin.setToolTip('符文等级 / 天赋点数 / 套装件数（随类别变化）；改动会自动重排 ΔDPS。')
        self.level_spin.valueChanged.connect(lambda _: self._deep_timer.start())

        self.slot_combo = QComboBox()
        self.slot_combo.setToolTip('宝石镶嵌部位：同一颗宝石在护甲 / 饰品 / 武器三类部位的加成不同。')
        for value, label in GEM_CATEGORIES:
            self.slot_combo.addItem(label, value)
        self.slot_combo.setCurrentIndex(2)      # 默认武器孔（历史默认值，勿改）
        self.slot_combo.currentIndexChanged.connect(lambda _: self._deep_timer.start())

        self.param_label = QLabel('镶嵌部位')
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText('搜索名称…')
        self.search_edit.setAccessibleName('按名称搜索候选（中文名或内部名）')
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search)

        # 排序基线依赖目标口径，但目标控件在对比页：这里给只读摘要 + 跳转，否则本页无法自查
        self.target_summary = QLabel('—')
        self.target_summary.setObjectName('pageSubtitle')
        # 单行：hero 右侧的高度不能被三行摘要撑起来（完整口径在 tooltip 与对比页）
        self.target_summary.setWordWrap(False)
        self.target_summary.setToolTip('ΔDPS 的比较基线所用的目标口径；在「装备对比 → 目标基础」里修改')
        self.target_btn = QPushButton('目标设置 →')
        self.target_btn.setToolTip('跳到装备对比页修改目标（等级/护甲/魔抗/状态/伤害类型）')
        self.target_btn.clicked.connect(self.targetRequested)

        # ---- 工具栏卡片：第一行参数 + 搜索（类别标签条在下方候选表卡内，见 table_card） ----
        toolbar = QFrame()
        toolbar.setObjectName('card')
        tool_lay = QVBoxLayout(toolbar)
        tool_lay.setContentsMargins(16, 14, 16, 16)   # 与 Card 同款内距（原来 12 不在档位上）
        tool_lay.setSpacing(10)
        row1 = QHBoxLayout()
        row1.setSpacing(10)
        row1.addWidget(self.param_label)
        row1.addWidget(self.level_spin)
        row1.addWidget(self.slot_combo)
        row1.addStretch(1)
        self.search_edit.setFixedWidth(240)
        row1.addWidget(self.search_edit)
        tool_lay.addLayout(row1)
        # 这里刻意不放「刷新排序」按钮：类别/等级/部位变更各自会 deep 重排，而「基线被别处
        # 改动」（如角色页调巅峰点数）由 app 在切入本页时补一次重排——按钮只会误导用户以为
        # 改完参数得记得点它。

        # ---- 候选排序表（卡片：标题行右侧是动线落点，正文只有表格） ----
        self.model = _RankModel(
            self, name_fn=lambda n: assembly_display_name(self.gd, self.current_kind(), n))
        self.proxy = _SearchProxy(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(Qt.UserRole)
        self.proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy.setFilterKeyColumn(0)
        self.table = QTableView()
        self.table.setAccessibleName('候选排序表')
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        head = self.table.horizontalHeader()
        head.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        head.setSectionResizeMode(1, QHeaderView.Stretch)
        for col in (2, 3, 4):        # 数值列按内容定宽：Δ 带方向箭头后，定宽会把符号挤掉
            head.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.setItemDelegateForColumn(2, MonoDelegate(self.table))
        for col in (3, 4):
            self.table.setItemDelegateForColumn(col, _TrendDelegate(self.table))
        self.table.doubleClicked.connect(self._on_double_clicked)
        # 键盘/右键两条快捷路径：列表行多时不必每回都把鼠标拖到卡片角落的「加入构建」
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_table_menu)
        enter_sc = QShortcut(QKeySequence(Qt.Key_Return), self.table)
        enter_sc.setContext(Qt.WidgetWithChildrenShortcut)
        enter_sc.activated.connect(self._add_selected)
        # 保留引用：图标/启用态的结构断言要用到它（此前是局部变量，外部无从核对）
        # 黄色 CTA 上的图标必须用墨色版：浅灰描边在 #FCD535 上几乎看不见
        self.add_btn = QPushButton(icon('act_add_dark'), '加入构建')
        self.add_btn.setObjectName('primary')     # 本页动线的落点，唯一强调底按钮
        self.add_btn.setToolTip('把选中的候选按当前等级/部位加入构建（双击行也可以）')
        self.add_btn.clicked.connect(self._add_selected)

        self.table_card = Card('候选排序')
        self.table_card.add_action(self.add_btn)
        self.hint = self.table_card.hint_label
        self.table_card.set_hint('—')
        # 类别标签条放进表卡第一行（对应 markets-table-card 的「卡内 tab 行 + 表格」解剖）：
        # 原先它与表格分处两张卡，选类目和看结果之间隔着一条卡缝
        self.table_card.body.insertWidget(0, self.kind_combo)
        self.table_card.body.addWidget(self.table, 1)

        # ---- 已装配清单（就地改参数 + 删除确认）----
        self.assembled_list = QListWidget()
        self.assembled_list.setAccessibleName('已装配条目清单')
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
        edit_bar.setSpacing(8)
        edit_bar.addWidget(self.edit_label)
        edit_bar.addWidget(self.edit_level_spin)
        edit_bar.addWidget(self.edit_slot_combo)
        edit_bar.addWidget(apply_btn)
        self.assembled_card = Card('已装配（参与属性表与排序基线）')
        self.assembled_card.body.addWidget(self.assembled_list, 1)
        self.assembled_card.body.addLayout(edit_bar)
        self.assembled_card.body.addWidget(remove_btn)

        self._splitter = QSplitter()
        self._init_splitter_sizes(self._splitter)
        self._splitter.addWidget(self.table_card)
        self._splitter.addWidget(self.assembled_card)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        self._splitter.setSizes([960, 412])   # 7/3 三页统一（同 role_page/compare_page）
        # 两张卡的下限：矮窗里若允许无限压缩，候选表的表体会先被压成 0 高（框还在、行没了），
        # 已装配清单则会缩到一行都看不见。下限写在「表/清单」上，卡片随内容撑开。
        # 表体下限按「表头 30 + 边框 ≈ 34」反推：170 才能保证 viewport ≥ 136（自检口径 120），
        # 原来 150 只换到 116——最小窗口下候选表刚好差 4px 被判「不可用」
        self.table.setMinimumHeight(170)
        self.assembled_list.setMinimumHeight(96)
        self.table_card.setMinimumHeight(260)     # 170 + 卡头/标签行/提示行 ≈ 89
        self.assembled_card.setMinimumHeight(220)

        self.banner = ModeBanner()
        tip = QLabel('双击候选行即可加入构建；选中右侧已装配条目可就地改等级/部位。')
        tip.setObjectName('cardHint')
        # 目标口径摘要与跳转放在 hero 右侧：它是「排序基线是什么」的答案，不该藏在参数条里
        hero_right = QWidget()
        hr = QHBoxLayout(hero_right)
        hr.setContentsMargins(0, 0, 0, 0)
        hr.setSpacing(10)
        hr.addWidget(self.target_summary)
        hr.addWidget(self.target_btn)
        root = QVBoxLayout()
        root.setContentsMargins(24, 12, 24, 12)
        root.setSpacing(8)    # 卡片垂直间距 12→8（用户 2026-10-21）：hero 一行化后 12 显得松
        # 副标题固定两行（同角色页）：自动换行会被挤成三行，且顶过 32px 大字
        root.addWidget(page_header('装配中心', '找一件更强的：按 ΔDPS 排序，\n双击加入构建',
                                   ASSEMBLY_TEXT, right=hero_right))
        root.addWidget(toolbar)
        root.addWidget(self.banner)
        root.addWidget(self._splitter, 1)
        root.addWidget(tip)
        # 整页进滚动区：hero + 参数条 + 两张卡的最小高度合起来高于窗口时必须能滚动，
        # 否则最小尺寸下候选表会被推到视口外（实测 1024×680 表体 0px）。
        content = QWidget()
        cap_page_width(content, root)     # 内容宽封顶 1440 居中（root 随之迁入 body）
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(scroll_host(content))

        self._on_kind()

    def resizeEvent(self, event):
        """窄窗口把「候选表 | 已装配栏」改为上下堆叠（见 common.apply_narrow_stacking）。"""
        super().resizeEvent(event)
        apply_narrow_stacking(self._splitter, event.size().width(), h_sizes=self._h_sizes)
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
        if deep:
            self._deep_timer.stop()      # 显式重排已覆盖待触发的合并重排
        self.banner.update_mode(self.profile)
        self._refresh_assembled()
        self._refresh_target()
        if deep:
            self._recompute()

    def _refresh_target(self):
        """目标口径只读摘要：排序 Δ 的基线是它，本页必须能看见（B2）。"""
        t = self.profile.target
        states = [cn for attr, cn in _COND_CN if bool(getattr(t, attr, False))]
        frac = float(getattr(t, 'hp_fraction', 1.0))
        if frac > 0.8:
            states.append('健康')
        elif frac < 0.3:
            states.append('受伤')
        # 一行写完（hero 右侧没有第二行可用）：状态用「/」串起来，收起长解释留给 tooltip
        self.target_summary.setText(
            f'排序目标：Lv{int(t.level)} · 护甲 {float(t.armor):g} · 魔抗 '
            f'{float(t.magic_resist):g} · {"/".join(states) if states else "无状态"}')

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
        # 同 (类别, 名称, 等级, 部位) 重复加入会按两份叠加进属性表，而 ΔDPS 未必看得出来
        same = next((it for it in self.profile.assembled
                     if it.kind == kind and it.name == name
                     and int(it.level) == int(level)
                     and (kind != 'gem' or int(it.category) == int(category))), None)
        if same is not None and not confirm_delete(
                self, '候选已在构建中',
                f'「{name}」与已装配条目完全相同（同类/同等级/同部位）。\n'
                '重复加入会按两份叠加计入属性表。\n仍要加入吗？',
                yes_label='仍要加入'):
            return
        self.profile.assembled.append(AssemblyItem(kind, name, level, category))
        self.refresh(deep=True)     # 装配项变更影响排序基线 → 本页立即全量重排
        self.changed.emit()

    def _on_table_menu(self, pos):
        """候选表右键：加入构建（与双击、回车同一入口，保证「同一动作只有一处实现」）+ 导出。"""
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        self.table.setCurrentIndex(index)
        menu = QMenu(self)
        add_act = menu.addAction('加入构建')
        add_table_export(menu, self._export_rows, self, '候选排序')
        if menu.exec(self.table.viewport().mapToGlobal(pos)) is add_act:
            self._add_selected()

    def _export_rows(self):
        """导出代理模型的可见行：用户看到的是「当前排序 + 搜索过滤」后的列表，导出应与之一致。"""
        headers = list(self.model.COLUMNS)
        rows = [[str(self.proxy.index(r, c).data(Qt.DisplayRole))
                 for c in range(len(headers))] for r in range(self.proxy.rowCount())]
        return headers, rows

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
        """换数据源（导入/加载构建）后回填并全量重排；保留用户当前类别（原来强制跳回宝石）。"""
        idx = self.kind_combo.findData(self.current_kind())
        if idx >= 0 and idx != self.kind_combo.currentIndex():
            self.kind_combo.blockSignals(True)      # 下面 _on_kind 会统一重排，避免双触发
            self.kind_combo.setCurrentIndex(idx)
            self.kind_combo.blockSignals(False)
        self._on_kind()
