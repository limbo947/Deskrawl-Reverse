# -*- coding: utf-8 -*-
"""装备对比结果区：两侧期望 DPS、Δ% 与逐技能秒伤对比表。

展示原则「先结论后细节」：顶部三格只给 当前/候选/变化 三个数；暴击、主属性、攻速等
过程量不占行，收进 Δ 标签的 tooltip（要查再悬停）。技能表只留 技能/当前/候选/Δ% 四列。
技能秒伤由 skill_service 计算（🔶 估算口径，见其模块说明），本视图只负责渲染。
"""
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QGridLayout, QGroupBox,
                               QHeaderView, QLabel, QStyle, QStyledItemDelegate,
                               QStyleOptionViewItem, QTableView, QVBoxLayout)

from deskrawl_calc import stat_name

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
            return (r.ability_name, f'{r.current_dps:.0f}', f'{r.candidate_dps:.0f}',
                    f'{r.delta_pct:+.2f}%')[col]
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


class _DeltaDelegate(QStyledItemDelegate):
    """Δ% 列只改文字颜色；背景与选中态仍交给基类（隔行底色在这里重画会丢）。"""

    def paint(self, painter, option, index):          # noqa: N802 —— Qt 覆写
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text, opt.text = opt.text, ''
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)
        painter.save()
        painter.setPen(_trend_color(index.data(Qt.UserRole) or 'flat'))
        painter.drawText(opt.rect.adjusted(0, 0, -4, 0), Qt.AlignRight | Qt.AlignVCenter, text)
        painter.restore()


class CompareView(QGroupBox):
    def __init__(self, parent=None):
        super().__init__('对比结果', parent)
        root = QVBoxLayout(self)

        head = QGridLayout()
        self.cur_title = QLabel('当前 DPS')
        self.cand_title = QLabel('候选 DPS')
        head.addWidget(self.cur_title, 0, 0)
        head.addWidget(self.cand_title, 0, 1)
        head.addWidget(QLabel('变化'), 0, 2)
        self.cur_dps = QLabel('—')
        self.cur_dps.setObjectName('dpsBig')
        self.cand_dps = QLabel('—')
        self.cand_dps.setObjectName('dpsBig')
        self.delta = QLabel('—')
        self.delta.setObjectName('deltaUp')
        head.addWidget(self.cur_dps, 1, 0)
        head.addWidget(self.cand_dps, 1, 1)
        head.addWidget(self.delta, 1, 2)
        root.addLayout(head)

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
        root.addWidget(self.skill_hint)
        # 逐技能行交给 model（刷新 = 一次 reset），Δ% 的三态由委托按 QSS 颜色绘制
        self.skill_model = _SkillModel(self)
        self.skill_table = QTableView()
        self.skill_table.setModel(self.skill_model)
        self.skill_table.verticalHeader().setVisible(False)
        self.skill_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.skill_table.setAlternatingRowColors(True)
        # 技能表已在「对比结果」分组框内：自身的表格框 + 网格线会叠加成多层矩形线框
        self.skill_table.setShowGrid(False)
        self.skill_table.setItemDelegateForColumn(3, _DeltaDelegate(self.skill_table))
        self.skill_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        # Δ% 是三态文本，列宽由表头文字算出来会偏窄 → 数字被挤到与上一列重叠；
        # 这里给三列数值定宽，窗口变窄时只压技能名列
        for col, width in ((1, 96), (2, 96), (3, 84)):
            self.skill_table.setColumnWidth(col, width)
        root.addWidget(self.skill_table, 1)

    @staticmethod
    def _primary_text(model) -> str:
        """攻击伤害的职业主属性加成（bjr：×(1+Final/100)）；未设置时明示。"""
        if model.primary_stat is None:
            return '主属性未设置'
        return f'{stat_name(int(model.primary_stat))} ×{model.primary_stat_multiplier():.3f}'

    def set_result(self, result, marginals=None):
        self.cur_title.setText(f'当前{result.slot_label} DPS')
        self.cand_title.setText(f'候选{result.slot_label} DPS')
        self.cur_dps.setText(f'{result.current_dps:.1f}')
        self.cand_dps.setText(f'{result.candidate_dps:.1f}')
        self.delta.setText(f'{result.delta_pct:+.2f}%（{result.delta:+.1f} DPS）')
        # 涨/跌配色写在 style.qss 里，这里只切 objectName，避免颜色散落在代码中
        self.delta.setObjectName(_delta_object_name(result.delta))
        self.delta.style().unpolish(self.delta)
        self.delta.style().polish(self.delta)

        self._show_marginals(result, marginals)

        warns = list(getattr(result, 'warnings', None) or [])
        self.warn_label.setVisible(bool(warns))
        if warns:
            self.warn_label.setText('对比口径告警：' + '；'.join(warns))

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
        """单独更新归因行（编辑后延时计算，避免每次按键都多跑 N 次 compare）。"""
        self._show_marginals(result, marginals)

    def _show_marginals(self, result, marginals):
        """边际影响一行：候选没有词条时整行隐藏（没有可归因的东西）。"""
        if not marginals:
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
        self.marginal.setText('边际影响（逐条移除）：' + '｜'.join(parts))
        self.marginal.setToolTip(
            '把该词条单独从候选件移除后重算，得到的是它的**边际**影响：正值 = 去掉它 DPS 会下降，'
            '说明这条在起作用。\n词条之间存在乘区交互（百分比同池、封顶、条件层），'
            '所以各条之和不必等于顶部总 Δ——按「边际影响」读，不要当占比相加。')
        self.marginal.setVisible(True)

    def set_skills(self, rows):
        """渲染逐技能秒伤对比（技能 · 当前 · 候选 · Δ%）。空表给出原因提示。

        旧实现每行给 Δ% 塞一个 QLabel 单元格控件，刷新时新建→旧控件 deleteLater 要等事件循环，
        期间按旧列宽绘制导致数字压列（窄窗稳定复现）。现在整表走 model reset，不存在半旧控件。
        """
        if not rows:
            self.skill_hint.setText('技能秒伤对比：未设置职业或无伤害技能（导入自动识别「职业」）')
            self.skill_model.set_rows([])
            return
        self.skill_hint.setText(f'技能秒伤对比（{len(rows)} 项，期望值口径；换装看 Δ% 即可）')
        self.skill_model.set_rows(rows)
