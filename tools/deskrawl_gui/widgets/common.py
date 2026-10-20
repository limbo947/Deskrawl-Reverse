# -*- coding: utf-8 -*-
"""跨页面共享的轻量组件：模式横幅 / 删除确认 / 空态提示。

抽出的动机：α 降级横幅原本只在装备对比页有，装配中心合并后也需要同一套提示；
删除确认与空态是合并后新增的交互，集中于此避免各页面各写一套文案与样式。
"""
import contextlib

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QCursor, QFont
from PySide6.QtWidgets import (QApplication, QDoubleSpinBox, QFileDialog, QFrame,
                               QHBoxLayout, QLabel, QLayout, QMessageBox, QPushButton,
                               QScrollArea, QSizePolicy, QStyleOptionViewItem,
                               QStyledItemDelegate, QToolTip, QVBoxLayout, QWidget)

from ..core import export as export_mod
from ..core.format import fmt_qty

# α 聚合导入的统一降级说明（含「降级」关键词：selftest 文案锚点依赖它）
ALPHA_BANNER_TEXT = ('α 聚合模式（快照无逐件装备）：相关计算降级为「基线 vs 基线+候选词条」，'
                     '百分比类词条增量为近似值。')

# 装备对比页专用补充（F9）：α 下武器槽 Δ 语义偏高——当前武器词条并入基线、不随本轮对比卸下。
# 独立成段而非并入上面：装配中心也复用同一横幅，那句只在对比口径下成立。
ALPHA_WEAPON_NOTE = ('武器槽的 Δ 另有一层偏高：当前武器词条已并入基线、随本轮对比不会卸下，'
                     '故只反映候选增量。')


def preferred_window_size(default=(1440, 900), minimum=(1024, 680)) -> QSize:
    """初始窗口尺寸：默认按设计文档的产品界面 1440×900，但不超出可用屏幕的 94%/92%。

    为什么不让尺寸写死：1366×768 的笔记本上 900 高会连标题栏一起探出屏幕底边，
    用户第一眼看到的是被裁掉的结论区。可用高度还要扣任务栏，故留 8% 余量。
    """
    app = QApplication.instance()
    screen = app.primaryScreen() if app is not None else None
    if screen is None:
        return QSize(*default)
    avail = screen.availableGeometry().size()
    return QSize(max(minimum[0], min(default[0], int(avail.width() * 0.94))),
                 max(minimum[1], min(default[1], int(avail.height() * 0.92))))


# 数字字形栈：对应 DESIGN.md 的 BinancePlex（Consolas 等宽，汉字由雅黑逐字回落）
MONO_FAMILIES = ('Consolas', 'Microsoft YaHei UI', 'monospace')


def mono_font(base=None) -> QFont:
    """从 base 派生只换字族的字体：字号/字重/斜体仍归 base（通常是 QSS 定下的值）。

    为什么不给整张表设等宽：名称列是中文或内部名，属于正文（BinanceNova 位）；让它们也走
    等宽会变成「用等宽排中文」，文档明确禁止混用。所以只有数值列换字形，且按列挂委托。
    """
    font = QFont(base) if base is not None else QFont()
    font.setFamilies(list(MONO_FAMILIES))
    return font


class MonoDelegate(QStyledItemDelegate):
    """数值列委托：仅把字族换成等宽栈，绘制、选中与对齐全部交回基类。"""

    def initStyleOption(self, option, index):          # noqa: N802 —— Qt 覆写
        super().initStyleOption(option, index)
        option.font = mono_font(option.font)


def scroll_host(widget: QWidget, *, minimum_width: int = 0) -> QScrollArea:
    """把页面主区包进竖向滚动区：空间不够时出现滚动条，而不是静默裁掉内容。

    为什么必须兜底：QSplitter 分不到高度时不会自动产生滚动条，固定高度的表（11 槽总览）
    会被直接切掉——实测 1024×680 下装配中心候选表 viewport 高 0、角色页总览少 5 行，
    两张表都「看得见框、读不到行」。宁可让用户滚一下，也不让数据无声消失。
    """
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QScrollArea.NoFrame)
    area.setWidget(widget)
    if minimum_width:
        area.setMinimumWidth(int(minimum_width))
    return area


class Card(QFrame):
    """内容卡片：标题行（标题 + 右侧动作）+ 可选说明 + 正文。

    为什么统一成一个容器：设计文档里的 markets-table-card / trust-badge / cta-band 都是
    「surface 面色块 + 12px 圆角 + 无阴影」，Qt 里 QGroupBox 自带标题栏语义（仅适合表单），
    纯内容区（属性表、候选表）需要一个不带边框线的卡片壳，才不至于「框套框」。
    """

    def __init__(self, title: str = '', parent=None):
        super().__init__(parent)
        self.setObjectName('card')
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(10)
        self._head = QHBoxLayout()
        self._head.setContentsMargins(0, 0, 0, 0)
        self._head.setSpacing(8)
        self.title_label = QLabel(title)
        self.title_label.setObjectName('cardTitle')
        self.title_label.setVisible(bool(title))
        self._head.addWidget(self.title_label)
        self._head.addStretch(1)
        root.addLayout(self._head)
        self.hint_label = QLabel('')
        self.hint_label.setObjectName('cardHint')
        self.hint_label.setWordWrap(True)
        self.hint_label.setVisible(False)
        root.addWidget(self.hint_label)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(8)
        root.addLayout(self.body, 1)

    def add_action(self, widget) -> None:
        """标题右侧的动作（筛选按钮、次要入口）：与标题同一行，不额外占一条工具栏。"""
        self._head.addWidget(widget)

    def set_hint(self, text: str) -> None:
        self.hint_label.setText(str(text or ''))
        self.hint_label.setVisible(bool(text))


class ReloadGuard:
    """回填 UI 期间的重入守卫：把「程序写控件」与「用户改控件」分开。

    为什么抽公共件：四个编辑器各写过一份 `_loading` 布尔与若干 `if` 判断（共 32 处），新增
    控件漏写就会「回填触发编辑 → 递归刷新」。上下文管理器把置位/复位绑在一起，中途抛异常
    也不会让编辑器永久停在「忽略用户操作」的状态。
    """

    def __init__(self, *args, **kwargs):
        self._reloading = False
        super().__init__(*args, **kwargs)

    @property
    def loading(self) -> bool:
        """是否正在回填（事件处理器应直接返回）。"""
        return self._reloading

    @contextlib.contextmanager
    def reloading(self):
        prev, self._reloading = self._reloading, True
        try:
            yield
        finally:
            self._reloading = prev


class ModeBanner(QLabel):
    """α/β 导入模式横幅：α 时显示降级说明，其余模式隐藏（幂等，可反复调用）。

    extra 供各页追加本页专属口径说明（默认空 = 只显示通用降级文案）。
    """

    def __init__(self, extra: str = '', parent=None):
        super().__init__(ALPHA_BANNER_TEXT + extra, parent)
        self.setObjectName('modeBanner')
        self.setWordWrap(True)
        self.setVisible(False)

    def update_mode(self, profile):
        alpha = getattr(profile, 'import_mode', '') == 'alpha'
        self.setVisible(alpha)
        return alpha


class QtySpinBox(QDoubleSpinBox):
    """数值输入框：内部按 decimals 存取（4 位），**显示**走 fmt_qty 去尾零。

    为什么不用 setDecimals(2) 一步到位：词条数值本身是 4 位精度（攻速 1.1845），砍到 2 位会
    把差异抹平；而直接留 4 位满屏「355.3500」。显示层与存储层分开，两头都不将就。
    """

    def __init__(self, parent=None, decimals: int = 4):
        super().__init__(parent)
        self.setDecimals(decimals)

    def textFromValue(self, value):        # noqa: N802 —— Qt 覆写
        return fmt_qty(value)

    def valueFromText(self, text):         # noqa: N802 —— Qt 覆写
        """去掉千分位后再解析；解析失败沿用当前值（默认实现会抛 ValueError → 焦点切换即崩）。"""
        try:
            return float(str(text).replace(',', '').strip())
        except ValueError:
            return self.value()


class AffixValueSpin(QtySpinBox):
    """词条数值输入：百分比属性按「%」显示（0.30 ↔ 30），内部仍存小数。

    为什么：词条百分比一直按小数填写，30% 填成 30 就是 3000% 且不报错；改用 % 显示后
    输入单位与游戏 tooltip 一致，数量级错误从「无声」变成「一眼可见」。
    步进必须随显示单位一起换（内部 0.01 = 显示 1）：QDoubleSpinBox 的 singleStep 作用在
    **内部值**上，若沿用默认 1.0，点一次上箭头会让 30% 变成 130%——等于用另一种方式重现
    了当初要消灭的 100 倍错误。
    """

    _STEP_PERCENT = 0.01
    _STEP_FLAT = 1.0

    # 类级默认值：QDoubleSpinBox.__init__ 内部就会调 textFromValue，那时实例属性还没赋值
    _percent = False

    def __init__(self, parent=None):
        super().__init__(parent)
        self._percent = False
        self.setSingleStep(self._STEP_FLAT)

    def set_percent(self, flag: bool) -> None:
        """切换显示单位：后缀、步进、显示三者一起换（任一漏改都会静默错位）。"""
        flag = bool(flag)
        if flag == self._percent:
            return
        self._percent = flag
        self.setSingleStep(self._STEP_PERCENT if flag else self._STEP_FLAT)
        self.setSuffix('%' if flag else '')
        self.setValue(self.value())

    def textFromValue(self, value):        # noqa: N802 —— Qt 覆写
        return f'{value * 100:g}' if self._percent else fmt_qty(value)

    def valueFromText(self, text):         # noqa: N802 —— Qt 覆写
        try:
            v = float(str(text).replace(',', '').replace('%', '').strip())
        except ValueError:
            return self.value()
        return v / 100.0 if self._percent else v


def confirm_delete(parent, title: str, text: str, yes_label: str = '删除') -> bool:
    """破坏性操作的二次确认；返回用户是否确认。

    用自定义中文按钮而非标准 Yes/No：Qt 未装中文翻译包时标准按钮会显示英文，
    与「界面全中文」约定冲突。yes_label 供非删除类操作（如「清除导入数据」）改写确认按钮。
    """
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Question)
    box.setWindowTitle(title)
    box.setText(text)
    yes = box.addButton(yes_label, QMessageBox.YesRole)
    box.addButton('取消', QMessageBox.NoRole)
    box.exec()
    return box.clickedButton() is yes


def add_table_export(menu, rows_fn, parent=None, title: str = '表格') -> None:
    """往已有右键菜单追加「复制为 TSV / 导出 CSV」。

    rows_fn() 在点击时才取数：表内容随编辑变化，构造菜单时快照会导出旧数据。
    三张表共用这一处落盘与错误处理——包括 utf-8-sig（Excel 是这条功能的默认去向）。
    """
    def _rows():
        headers, rows = rows_fn()
        return list(headers), [list(r) for r in rows]

    def copy_tsv():
        headers, rows = _rows()
        if not rows:
            QToolTip.showText(QCursor.pos(), '没有可导出的行')
            return
        QApplication.clipboard().setText(export_mod.rows_to_tsv(headers, rows))
        QToolTip.showText(QCursor.pos(), f'已复制 {len(rows)} 行（制表符分隔，可直接粘进表格）')

    def save_csv():
        headers, rows = _rows()
        if not rows:
            QToolTip.showText(QCursor.pos(), '没有可导出的行')
            return
        path, _ = QFileDialog.getSaveFileName(parent, f'导出 {title}',
                                              f'{title}.csv', 'CSV (*.csv)')
        if not path:
            return
        try:
            n = export_mod.write_csv(path, headers, rows)
        except OSError as exc:
            QMessageBox.warning(parent, '导出失败', str(exc))
            return
        QToolTip.showText(QCursor.pos(), f'已导出 {n} 行：{path}')

    menu.addSeparator()
    menu.addAction('复制为 TSV（可直接粘进表格）', copy_tsv)
    menu.addAction('导出 CSV…', save_csv)


def apply_narrow_stacking(splitter, width: int, *, threshold: int = 1100, h_sizes=None):
    """窄窗口下把「左右分栏」改为「上下堆叠」。

    动机：两栏并排 + 绝对最小宽度在小屏或高缩放下会挤压（1920×1080 在 150% 缩放下只剩
    1280 逻辑点）。用 QSplitter 的 orientation 切换即可，不重建布局；宽回来再并排。

    换向必须重设比例：横向像素值（如 830/306）搬到竖向后下栏只剩百来像素（实测 1280×720
    结果区 128px、技能表 70px）。两栏按 3:2 分（主输入 | 辅助）；回横排时用 h_sizes 还原用户的拖动。
    """
    for i in range(splitter.count()):
        splitter.setCollapsible(i, False)     # 允许拖到 0 会让某一栏彻底消失且找不回来
    if not getattr(splitter, '_drag_hooked', False):
        splitter._drag_hooked = True
        splitter._user_moved = False
        # 用户拖过就尊重他的比例；没拖过才由代码维持 0.6/0.4
        splitter.splitterMoved.connect(lambda *_: setattr(splitter, '_user_moved', True))
    want = Qt.Vertical if width < threshold else Qt.Horizontal
    if splitter.orientation() == want:
        if want == Qt.Vertical and not splitter._user_moved:
            _stack_by_height(splitter)     # 随窗口缩放保持默认比例（比例曾定在错误总高上）
        return
    splitter.setOrientation(want)
    splitter._user_moved = False
    if want == Qt.Horizontal:
        if h_sizes and len(h_sizes) == splitter.count():
            splitter.setSizes([int(s) for s in h_sizes])
        return
    # 换向发生在 resizeEvent 里，此刻 splitter 高度还是上一轮的：直接按它算 0.6/0.4 会
    # 把比例定在错误的总高上（实测 1024×680 候选表只剩 116px、装配卡却是 239）。推迟到
    # 布局完成后再分配一次，比例才落在真实可用高度上。
    QTimer.singleShot(0, lambda: _stack_by_height(splitter))


def _stack_by_height(splitter) -> None:
    """竖向堆叠的比例分配（换向后延迟调用，见 apply_narrow_stacking）。"""
    if splitter.orientation() != Qt.Vertical:
        return
    height = splitter.height()
    if height <= 0:
        return
    count = splitter.count()
    if count == 2:
        # 不按 sizeHint：编辑区包了滚动区后 hint 很小，实测会给成 284/343——主输入栏反而更窄
        top = int(height * 0.6)
        splitter.setSizes([top, height - top])
        return
    hints = [max(120, splitter.widget(i).sizeHint().height()) for i in range(count)]
    total = sum(hints)
    if total > 0:
        splitter.setSizes([max(1, int(height * h / total)) for h in hints])


class SplitterSizesMixin:
    """把「横向分栏宽度」记成可持久化的值（三页各有一处 QSplitter，逻辑相同）。

    只在横向且宽度像样时记录：窄窗会切成竖排、构造期尚未布局时宽度是几百像素的假值，
    这两种情况的尺寸存进会话再套回去只会错位。拖动与窗口缩放都要刷新缓存，否则关窗时
    拿到的是上一次布局的值。
    """

    def _init_splitter_sizes(self, splitter) -> None:
        self._splitter_ref = splitter
        self._h_sizes = None
        splitter.splitterMoved.connect(lambda *_: self._remember_splitter())

    def _remember_splitter(self) -> None:
        # 阈值 800 而不是「比 0 大」：构造期分栏只有 600 多像素宽，尺寸是布局前的假值，
        # 存下来会在下次启动被当成用户意图（实测把默认 340/840 记成 340/296）。
        sp = self._splitter_ref
        if sp.orientation() == Qt.Horizontal and sp.width() >= 800:
            self._h_sizes = list(sp.sizes())

    def splitter_sizes(self):
        self._remember_splitter()      # 关窗时点布局已完成，取到的才是真值
        return self._h_sizes

    def set_splitter_sizes(self, sizes) -> None:
        if sizes and len(sizes) == self._splitter_ref.count():
            self._splitter_ref.setSizes([int(s) for s in sizes])


def _show_help_text(anchor: QWidget, text: str) -> None:
    """展开 hero ⓘ 的全文：正文可选中复制（tooltip 会随鼠标移开消失，长文读不完）。"""
    box = QMessageBox(anchor.window())
    box.setWindowTitle('说明')
    box.setText(text)
    box.setTextInteractionFlags(Qt.TextSelectableByMouse)
    box.setStandardButtons(QMessageBox.Close)
    box.button(QMessageBox.Close).setText('关闭')
    box.exec()


def cap_page_width(page: QWidget, root: QLayout, cap: int = 1440) -> None:
    """页面主体宽度封顶并居中（对应文档「产品面内容宽 1440」）。

    为什么用「迁移布局 + 两侧 0 拉伸」：body 以 Expanding 吃满可用宽、碰到 maximumWidth
    后剩余空间均分给左右两个 stretch——不加这两侧，超宽屏下内容会贴在左边而不是居中。
    cap 只约束横向：纵向仍由各页的滚动区/分栏自己分配。
    """
    body = QWidget()
    body.setLayout(root)          # root 必须是尚未挂到任何 widget 上的布局
    body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    body.setMaximumWidth(cap)
    outer = QHBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.addStretch()
    outer.addWidget(body, 1)
    outer.addStretch()


def page_header(title: str, subtitle: str = '', help_text: str = '',
                right: QWidget = None) -> QWidget:
    """页面 hero band：标题（32px/600）+ 副标题（同行右侧）+ ⓘ，底部细边线与内容分隔。

    副标题与标题同行（2026-10-21）：hero 从两行变一行，纵向省约 26px；小字用 AlignBottom
    再抬 6px，让它落在大字的基线附近而不是吊在半空。
    right 给页面级动作留位（如装配中心的「目标设置 →」）：动作与标题同处 hero，
    不必在内容区再插一条工具栏——与设计文档里 section head + 右侧 CTA 的结构一致。
    help_text 非空时在标题右侧挂一枚 ⓘ（悬停看摘要，点击展开全文）：副标题只留一句
    「这页干什么」，口径边界、上手说明这类长文收进 ⓘ 与帮助菜单，避免顶部被大段文字占满（V11）。
    """
    box = QWidget()
    box.setObjectName('pageHero')
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 4)
    lay.setSpacing(4)
    head = QHBoxLayout()
    head.setSpacing(8)
    t = QLabel(title)
    t.setObjectName('pageTitle')
    head.addWidget(t)
    if help_text:
        # 用按钮而不是 QLabel：纯悬停的说明对键盘用户等于不存在（Tab 到不了、回车点不开），
        # 而它承载的正是「口径边界」这类不看就会误读的长文（点开后仍可整段复制）。
        info = QPushButton('ⓘ')
        info.setObjectName('helpHint')
        info.setToolTip(help_text)
        info.setCursor(Qt.PointingHandCursor)
        info.setAccessibleName('口径说明')
        info.setFlat(True)
        info.clicked.connect(lambda _=False, text=help_text, w=info: _show_help_text(w, text))
        head.addWidget(info)
    if subtitle:
        s = QLabel(subtitle)
        s.setObjectName('pageSubtitle')
        # 不开 wordWrap：换行版 QLabel 在 HBox 里只拿到「可断点」级别的窄 sizeHint，
        # 结果被挤成三行（2026-10-21 实测）；断点交给调用方用 \n 控制，宽度 = 最长一行，
        # 再 AlignBottom 贴齐大字底边——高度自然不超过标题（两行 ~36px < 32px 字的行高）
        head.addWidget(s, 0, Qt.AlignBottom)
    head.addStretch(1)
    if right is not None:
        head.addWidget(right)
    lay.addLayout(head)
    return box
