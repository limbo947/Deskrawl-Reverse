# -*- coding: utf-8 -*-
"""装备对比结果区：两侧期望 DPS、Δ% 与逐技能秒伤对比表。

展示原则「先结论后细节」：顶部三格只给 当前/候选/变化 三个数；暴击、主属性、攻速等
过程量不占行，收进 Δ 标签的 tooltip（要查再悬停）。技能表只留 技能/当前/候选/Δ% 四列。
技能秒伤由 skill_service 计算（🔶 估算口径，见其模块说明），本视图只负责渲染。
"""
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QTimer, Signal
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QFrame, QGridLayout,
                               QGroupBox, QHBoxLayout, QHeaderView, QLabel, QMenu,
                               QPushButton, QStyle, QStyledItemDelegate, QStyleOptionViewItem,
                               QTableView, QVBoxLayout, QWidget)

from deskrawl_calc import stat_name

from ..core.format import fmt_dps
from .common import MonoDelegate, add_table_export, mono_font
from .delta_bar import DeltaBar
from .icons import icon

_SKILL_COLS = ['技能', '当前', '候选', 'Δ%']

# Δ 中性阈值：界面按 1 位小数显示，|Δ| < 0.05 时读出来就是"+0.0"——这种情况必须用中性色，
# 否则「没变化」会被读成「提升」（旧实现 `delta >= 0 → deltaUp` 把 Δ=0 也上绿）。
_FLAT_DELTA = 0.05
# 技能表 Δ% 列同一取向：按 2 位小数显示，|Δ%| < 0.005 读出来就是"+0.00%"，同样归中性色
_FLAT_DELTA_PCT = 0.005


def _delta_object_name(delta: float) -> str:
    """Δ 三态 → QSS 的 objectName（颜色只在 style.qss 定义）。"""
    if abs(float(delta)) < _FLAT_DELTA:
        return 'deltaFlat'
    return 'deltaUp' if delta > 0 else 'deltaDown'


_trend_colors = {}


def reset_trend_colors():
    """主题切换后清空颜色缓存：这里缓存的是「当前 QSS 解析出的色值」，换主题必须先失效。"""
    _trend_colors.clear()


def _trend_color(trend: str):
    """Δ% 三态颜色：从 QSS 解析后的调色板读回，代码里不抄第二份色值。

    借一枚探针 QLabel（#deltaCell[trend=…]）polish 后取前景色——颜色仍只在 style.qss 定义，
    换主题时这里自动跟随；若改用 setForeground 就得把三个色值在代码里再写一遍。
    """
    color = _trend_colors.get(trend)
    if color is None:
        probe = QLabel('')
        probe.setObjectName('deltaCell')
        probe.setProperty('trend', trend)
        probe.ensurePolished()
        color = probe.palette().color(QPalette.WindowText)
        _trend_colors[trend] = color
    return color


class _SkillModel(QAbstractTableModel):
    """逐技能秒伤行：文本进 DisplayRole，Δ% 的三态进 UserRole（颜色由委托解析）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []

    def set_rows(self, rows):
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):        # noqa: N802 —— Qt 覆写
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):     # noqa: N802 —— Qt 覆写
        return 0 if parent.isValid() else len(_SKILL_COLS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        r = self._rows[index.row()]
        col = index.column()
        if role == Qt.DisplayRole:
            if col == 3:      # Δ% 与主结论同款双通道：箭头 + 颜色（数字本身已带正负号）
                arrow = ('' if abs(float(r.delta_pct)) < _FLAT_DELTA_PCT
                         else ('▲ ' if r.delta_pct > 0 else '▼ '))
                return f'{arrow}{r.delta_pct:+.2f}%'
            return (r.ability_name, f'{r.current_dps:.0f}', f'{r.candidate_dps:.0f}')[col]
        if role == Qt.UserRole and col == 3:
            return 'flat' if abs(float(r.delta_pct)) < _FLAT_DELTA_PCT else (
                'up' if r.delta_pct > 0 else 'down')
        if role == Qt.TextAlignmentRole and col >= 1:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):   # noqa: N802 —— Qt 覆写
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return _SKILL_COLS[section]
        return None

    def trend(self, row: int) -> str:
        """自检/调试直读三态（等价于 data(UserRole)，但不必构造 QModelIndex）。"""
        pct = float(self._rows[row].delta_pct)
        return 'flat' if abs(pct) < _FLAT_DELTA_PCT else ('up' if pct > 0 else 'down')

    def rows(self) -> list:
        """导出/复制通道：拿原始 SkillRow，避免再从显示文本反解析。"""
        return list(self._rows)


class _DeltaDelegate(QStyledItemDelegate):
    """Δ% 列只改文字颜色；背景与选中态仍交给基类（隔行底色在这里重画会丢）。"""

    def initStyleOption(self, option, index):         # noqa: N802 —— Qt 覆写
        # 自定义绘制会绕过基类 paint，字形只能在这里补：数值列统一等宽栈
        super().initStyleOption(option, index)
        option.font = mono_font(option.font)

    def paint(self, painter, option, index):          # noqa: N802 —— Qt 覆写
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text, opt.text = opt.text, ''
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)
        painter.save()
        painter.setFont(opt.font)
        painter.setPen(_trend_color(index.data(Qt.UserRole) or 'flat'))
        painter.drawText(opt.rect.adjusted(0, 0, -4, 0), Qt.AlignRight | Qt.AlignVCenter, text)
        painter.restore()


class CompareView(QGroupBox):
    # 空态里的「用当前件填入候选」：本视图不持有档案，实际播种由 EquipmentEditor 执行
    seedRequested = Signal()

    def __init__(self, parent=None):
        super().__init__('对比结果', parent)
        self._empty = False                  # 候选未填写（set_result 每帧刷新）
        root = QVBoxLayout(self)

        # 三格数值卡（对应 stat-callout-card）：标签弱化、数值走等宽字体；
        # 中间用细竖线分隔而不是三张卡片——同一件事的三个面，分开反而读不出关系
        head = QGridLayout()
        head.setContentsMargins(0, 0, 0, 6)
        head.setHorizontalSpacing(20)
        head.setVerticalSpacing(2)
        self.cur_title = QLabel('当前 DPS')
        self.cur_title.setObjectName('statLabel')
        self.cand_title = QLabel('候选 DPS')
        self.cand_title.setObjectName('statLabel')
        change_title = QLabel('变化')
        change_title.setObjectName('statLabel')
        head.addWidget(self.cur_title, 0, 0)
        head.addWidget(self.cand_title, 0, 2)
        head.addWidget(change_title, 0, 4)
        self.cur_dps = QLabel('—')
        self.cur_dps.setObjectName('dpsBig')
        self.cand_dps = QLabel('—')
        self.cand_dps.setObjectName('dpsBig')
        self.delta = QLabel('—')
        self.delta.setObjectName('deltaUp')
        # Δ% 与绝对 ΔDPS 分两级：32px 只承载「涨跌多少」，绝对值降为 12px 附注。合成一行时
        # （「▲ +14.32%（+28.389 DPS）」）单行最小宽度约 400px，会把整页最小宽顶到 1276，
        # 而 8/4 分栏下主区只有约 990——结果区只能横向滚动、数字读不全
        self.delta_abs = QLabel('')
        self.delta_abs.setObjectName('statLabel')
        self.delta_abs.setVisible(False)
        delta_box = QWidget()
        delta_lay = QVBoxLayout(delta_box)
        delta_lay.setContentsMargins(0, 0, 0, 0)
        delta_lay.setSpacing(0)
        delta_lay.addWidget(self.delta)
        delta_lay.addWidget(self.delta_abs)
        head.addWidget(self.cur_dps, 1, 0)
        head.addWidget(self.cand_dps, 1, 2)
        head.addWidget(delta_box, 1, 4)
        for col in (1, 3):
            divider = QFrame()
            divider.setObjectName('statDivider')
            divider.setFrameShape(QFrame.VLine)
            head.addWidget(divider, 0, col, 2, 1)
        for col in (0, 2, 4):
            head.setColumnStretch(col, 1)
        # 一键复制结论：截屏贴群是当前唯一出口，而结论需要连带技能表与口径注脚才不会被误读
        self.copy_btn = QPushButton('复制结论')
        self.copy_btn.setFixedHeight(28)
        self.copy_btn.setIcon(icon('act_copy'))
        self.copy_btn.setToolTip('复制结论行、边际归因与技能表（制表符分隔，可直接粘进表格/聊天）')
        self.copy_btn.clicked.connect(self._copy_summary)
        head.addWidget(self.copy_btn, 1, 5, Qt.AlignRight | Qt.AlignVCenter)
        root.addLayout(head)

        # 图形通道：两根条的长度差 = 换装幅度（数字之外的第二种读法，空候选时整块隐藏）
        self.delta_bar = DeltaBar()
        root.addWidget(self.delta_bar)

        # 空态不能只报告事实（「候选未填写」），要给下一步动作：用户在结论区读到这句时，
        # 工具条上的播种按钮在编辑区上方，视线已经跳过去了
        self.empty_row = QWidget()
        self.empty_row.setObjectName('inlineRow')   # 卡片内的行容器必须透明，否则刷出画布色暗带
        empty_lay = QHBoxLayout(self.empty_row)
        empty_lay.setContentsMargins(0, 0, 0, 0)
        empty_lay.setSpacing(8)
        self.empty_hint = QLabel('候选栏还是空的：可以手工填，也可以直接沿用当前件再改。')
        self.empty_hint.setObjectName('pageSubtitle')
        # 与工具条上的「以当前件为起点」是同一个动作：同一屏只保留一个黄 CTA（工具条那个），
        # 空态里这枚用次级按钮样式，避免两个黄按钮互相稀释
        self.seed_btn_inline = QPushButton('用当前件填入候选')
        self.seed_btn_inline.clicked.connect(self.seedRequested)
        empty_lay.addWidget(self.empty_hint)
        empty_lay.addWidget(self.seed_btn_inline)
        empty_lay.addStretch(1)
        self.empty_row.setVisible(False)
        root.addWidget(self.empty_row)

        # 归因：只回答「这次 Δ 主要由哪几条词条撑着」，不承担加总（见 set_result 的 tooltip 口径）
        self.marginal = QLabel('')
        self.marginal.setObjectName('pageSubtitle')
        self.marginal.setWordWrap(True)
        self.marginal.setVisible(False)
        root.addWidget(self.marginal)

        # 对比口径告警（F8）：_negate 卸下不可逆词条（连乘 type 2）时会丢项使 Δ 失真，
        # 内容非空才显示；用 modeBanner 的告警样式，与 α 横幅同一视觉语言。
        self.warn_label = QLabel('')
        self.warn_label.setObjectName('modeBanner')
        self.warn_label.setWordWrap(True)
        self.warn_label.setVisible(False)
        root.addWidget(self.warn_label)

        self.skill_hint = QLabel('技能秒伤对比：—')
        self.skill_hint.setObjectName('cardHint')   # 说明文字：12px 次级色，不占正文层级
        root.addWidget(self.skill_hint)
        # 逐技能行交给 model（刷新 = 一次 reset），Δ% 的三态由委托按 QSS 颜色绘制
        self.skill_model = _SkillModel(self)
        self.skill_table = QTableView()
        self.skill_table.setAccessibleName('逐技能秒伤对比表')
        self.skill_table.setModel(self.skill_model)
        self.skill_table.verticalHeader().setVisible(False)
        self.skill_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.skill_table.setAlternatingRowColors(True)
        # 技能表已在「对比结果」分组框内：自身的表格框 + 网格线会叠加成多层矩形线框
        self.skill_table.setShowGrid(False)
        self.skill_table.setProperty('flat', 'true')      # 去掉表格外框，只留卡片描边（QSS）
        self.skill_table.verticalHeader().setDefaultSectionSize(26)   # 12px 行高挤，26px 才扫得动
        # 竖排/小屏时至少保住约四行：此前 1280×720 下它被压到 70px（两行），结论等于看不见
        self.skill_table.setMinimumHeight(120)
        self.skill_table.setItemDelegateForColumn(1, MonoDelegate(self.skill_table))
        self.skill_table.setItemDelegateForColumn(2, MonoDelegate(self.skill_table))
        self.skill_table.setItemDelegateForColumn(3, _DeltaDelegate(self.skill_table))
        self.skill_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        # Δ% 是三态文本，列宽由表头文字算出来会偏窄 → 数字被挤到与上一列重叠；
        # 这里给三列数值定宽，窗口变窄时只压技能名列
        for col, width in ((1, 96), (2, 96), (3, 84)):
            self.skill_table.setColumnWidth(col, width)
        self.skill_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.skill_table.customContextMenuRequested.connect(self._on_skill_menu)
        root.addWidget(self.skill_table, 1)

    @staticmethod
    def _primary_text(model) -> str:
        """攻击伤害的职业主属性加成（bjr：×(1+Final/100)）；未设置时明示。"""
        if model.primary_stat is None:
            return '主属性未设置'
        return f'{stat_name(int(model.primary_stat))} ×{model.primary_stat_multiplier():.3f}'

    def set_result(self, result, marginals=None):
        self._empty = bool(getattr(result, 'candidate_empty', False))
        self.cur_title.setText(f'当前{result.slot_label} DPS')
        self.cand_title.setText(f'候选{result.slot_label} DPS')
        self.cur_dps.setText(fmt_dps(result.current_dps))
        self.cur_dps.setToolTip(f'{result.current_dps:,.1f} DPS（完整精度；缩写只影响显示）')
        if self._empty:
            # 空候选不是一次换装：空武器算出来恰好 0 DPS，直接显示会是「−100%」这种假结论
            self.cand_dps.setText('—')
            self.delta.setText('候选未填写')
            self.delta_abs.setVisible(False)
            self.delta.setObjectName('deltaFlat')
            self.delta.setToolTip('候选栏还没有内容：填名称/词条，或用工具条的'
                                  '「从背包/仓库导入」载入一件。\n未填之前不给 Δ。')
            self.delta_bar.setVisible(False)
            self.empty_row.setVisible(True)
        else:
            self.cand_dps.setText(fmt_dps(result.candidate_dps))
            self.cand_dps.setToolTip(f'{result.candidate_dps:,.1f} DPS（完整精度）')
            # 箭头与颜色双通道：色弱用户扫主结论时不依赖红绿
            arrow = ('' if abs(result.delta_pct) < _FLAT_DELTA_PCT
                     else ('▲ ' if result.delta_pct > 0 else '▼ '))
            delta_txt = fmt_dps(abs(result.delta))
            sign = '-' if result.delta < 0 else '+'
            self.delta.setText(f'{arrow}{result.delta_pct:+.2f}%')
            self.delta_abs.setText(f'{sign}{delta_txt} DPS')
            self.delta_abs.setVisible(True)
            self.delta.setObjectName(_delta_object_name(result.delta))
            self.delta_bar.set_slot(result.slot_label)
            self.delta_bar.set_values(result.current_dps, result.candidate_dps)
            self.delta_bar.set_trend('up' if result.delta > 0 else (
                'down' if result.delta < 0 else ''))
            self.delta_bar.setVisible(True)
            self.empty_row.setVisible(False)
        # 涨/跌配色写在 style.qss 里，这里只切 objectName，避免颜色散落在代码中
        self.delta.style().unpolish(self.delta)
        self.delta.style().polish(self.delta)

        self.set_marginals(result, marginals)

        warns = list(getattr(result, 'warnings', None) or [])
        self.warn_label.setVisible(bool(warns))
        if warns:
            self.warn_label.setText('对比口径告警：' + '；'.join(warns))

        if self._empty:
            return       # 候选未填：Δ 的悬停口径无意义（没有可解释的差）
        # 过程量（暴击/暴伤/主属性/攻速）不占行：要查时悬停 Δ 即可。末尾一句说明顶部 Δ 的
        # 口径边界（F6）：它是不带技能标签的普攻期望，标签/冷却类词条只体现在下方技能表。
        m0, m1 = result.current_model, result.candidate_model
        self.delta.setToolTip(
            f'暴击率 {m0.crit_chance():.3f} → {m1.crit_chance():.3f}\n'
            f'暴伤× {m0.crit_multiplier():.3f} → {m1.crit_multiplier():.3f}\n'
            f'攻击伤害主属性加成 {self._primary_text(m0)} → {self._primary_text(m1)}\n'
            f'有效攻速已含武器基础攻速与面板攻速加成\n'
            f'顶部 Δ 为无标签普攻口径：普攻/强攻伤害(33/34)与冷却缩减(13)只作用于下方技能表')

    def set_marginals(self, result, marginals):
        """边际影响一行：候选没有词条时整行隐藏（没有可归因的东西）。

        编辑后延时 250ms 才调用（见 equipment_editor），避免每次按键都多跑 N 次 compare。
        """
        if self._empty or not marginals:
            self.marginal.setVisible(False)
            return
        base = float(result.candidate_dps or 0.0)
        parts = []
        for stat, delta, _value in marginals:
            pct = (float(delta) / base * 100.0) if base else 0.0
            # 与技能表 Δ% 同阈值：显示成 +0.00% 的条目不占位（如条件词条在目标无该状态时）
            if abs(pct) < _FLAT_DELTA_PCT:
                continue
            parts.append(f'{stat_name(int(stat))} {pct:+.2f}%')
        if not parts:
            self.marginal.setVisible(False)
            return
        # 文案避开「边际」这个内部术语：界面主语是「这条词条帮了多少」
        self.marginal.setText('各词条贡献（单独移除后）：' + '｜'.join(parts))
        self.marginal.setToolTip(
            '把该词条单独从候选件移除后重算：正值 = 去掉它 DPS 会下降，说明这条在起作用。\n'
            '词条之间会互相影响（百分比同池、封顶、条件层），所以各条之和不必等于顶部总 Δ——'
            '看单条的作用即可，不要当占比相加。')
        self.marginal.setVisible(True)

    def set_skills(self, rows):
        """渲染逐技能秒伤对比（技能 · 当前 · 候选 · Δ%）。空表给出原因提示。

        旧实现每行给 Δ% 塞一个 QLabel 单元格控件，刷新时新建→旧控件 deleteLater 要等事件循环，
        期间按旧列宽绘制导致数字压列（窄窗稳定复现）。现在整表走 model reset，不存在半旧控件。
        """
        if self._empty:
            self.skill_hint.setText('候选未填写：填好候选后再给逐技能 Δ%')
            self.skill_model.set_rows([])
            return
        if not rows:
            self.skill_hint.setText('没有可对比的技能：先在角色页选职业（导入角色会自动识别）')
            self.skill_model.set_rows([])
            return
        self.skill_hint.setText(f'技能秒伤（{len(rows)} 项，期望口径；换装只看 Δ%）')
        self.skill_model.set_rows(rows)

    def set_seed_enabled(self, enabled: bool) -> None:
        """空态里的播种按钮跟工具条那个同权限：当前件没有内容时点了也只会得到空拷贝。"""
        self.seed_btn_inline.setEnabled(bool(enabled))

    # ---------------- 导出 ----------------
    def export_rows(self):
        """(表头, 行)：与表格显示同文本（导出不另算一份口径）。"""
        rows = [[r.ability_name, f'{r.current_dps:.0f}', f'{r.candidate_dps:.0f}',
                 f'{r.delta_pct:+.2f}%'] for r in self.skill_model.rows()]
        return list(_SKILL_COLS), rows

    def _on_skill_menu(self, pos):
        menu = QMenu(self)
        add_table_export(menu, self.export_rows, self, '技能对比')
        menu.exec(self.skill_table.viewport().mapToGlobal(pos))

    def summary_text(self) -> str:
        """「复制结论」的正文：结论行 + 边际归因 + 技能表 + 口径注脚。

        为什么要带口径注脚：截图/粘贴出去后没有界面上下文，读者很容易把期望值 Δ 当实测值。
        """
        # 界面上 Δ% 与绝对 ΔDPS 分两级显示，复制出去要合成一行（脱离界面后看不出层级）
        change = self.delta.text()
        # 用 isHidden 而不是 isVisible：后者在窗口尚未显示时一律 False，会把绝对值漏掉
        if not self.delta_abs.isHidden() and self.delta_abs.text():
            change += f'（{self.delta_abs.text()}）'
        head = (f'{self.cur_title.text()} {self.cur_dps.text()}｜'
                f'{self.cand_title.text()} {self.cand_dps.text()}｜变化 {change}')
        if self._empty:
            return head + '\n（候选未填写）'
        lines = [head]
        if not self.marginal.isHidden() and self.marginal.text():
            lines.append(self.marginal.text())
        lines.append('\t'.join(_SKILL_COLS))
        for r in self.skill_model.rows():
            lines.append(f'{r.ability_name}\t{r.current_dps:.0f}\t'
                         f'{r.candidate_dps:.0f}\t{r.delta_pct:+.2f}%')
        lines.append('口径：期望值（未含实测修正）；Δ% 为两侧同口径对比，详见「帮助→口径说明」。')
        return '\n'.join(lines)

    def _copy_summary(self):
        """按钮文案改「已复制」1.2 秒：不弹框、不抢焦点，连续复制也看得见反馈。"""
        QApplication.clipboard().setText(self.summary_text())
        self.copy_btn.setText('已复制')
        QTimer.singleShot(1200, self._reset_copy_text)

    def _reset_copy_text(self):
        try:
            self.copy_btn.setText('复制结论')
        except RuntimeError:
            pass        # 延迟回调可能晚于控件的 C++ 析构（窗口已关）
