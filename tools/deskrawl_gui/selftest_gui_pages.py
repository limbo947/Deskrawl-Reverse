# -*- coding: utf-8 -*-
"""页面级导出/导航自检（A2/A3）：需要真实主窗口，故与 Qt-free 的鲁棒性组分开。

单独成文件的原因：selftest.py 已 700+ 行，而这两组只服务三个页面的可见契约；顺着 E3
「按页拆」的方向，新增检查不再往主文件里堆。检查项由调用方传入的 check() 记录，
便于复用主自检的 PASS/FAIL 输出格式。
"""


def _qss_text() -> str:
    """读主题源文件（用于断言某类规则确实存在，例如键盘焦点）。"""
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, 'resources', 'style.qss'), encoding='utf-8') as f:
        return f.read()


def min_size_checks(win, check):
    """最小窗口可用性 + 数值列字形 + 上下文条基线（回归锚）。

    为什么量像素而不只查属性：这三条都是「被挤小后不报错、只是静默读不到」的缺陷——
    1024×680 下候选表表体曾为 0 高、11 槽总览少 5 行、编辑一次基线 DPS 就从上下文条消失，
    而列数/行数类断言当时全绿。这里把它们钉成会变红的检查。
    """
    from PySide6.QtWidgets import QApplication, QScrollArea

    from deskrawl_calc import StatType

    from .widgets.common import MonoDelegate

    saved_row, saved_size = win.nav.currentRow(), win.size()
    side_w = table_h = list_h = 0
    overview_ok = main_scroll_ok = side_ok = typo_ok = False
    before = after = focus_ok = a11y_ok = False
    try:
        win.resize(1024, 680)
        win.nav.setCurrentRow(2)                    # 装配中心：候选表 + 已装配清单
        for _ in range(6):
            QApplication.processEvents()
        ac = win.assembly_center
        table_h, list_h = ac.table.viewport().height(), ac.assembled_list.height()

        win.nav.setCurrentRow(0)                    # 角色页：11 槽总览必须整表在位
        for _ in range(6):
            QApplication.processEvents()
        rp = win.role_page
        ov = rp.slot_overview
        overview_ok = ov.height() >= ov.table.height() >= 11 * 22
        main_scroll_ok = isinstance(rp._splitter.widget(0), QScrollArea)
        side_w = rp._splitter.sizes()[1]
        side_ok = side_w >= 120                     # 竖排时右栏不能被压成一条缝

        view = win.compare_page.equipment_editor.compare_view
        typo_ok = (isinstance(rp.stat_table.table.itemDelegateForColumn(1), MonoDelegate)
                   and isinstance(view.skill_table.itemDelegateForColumn(1), MonoDelegate)
                   and isinstance(ac.table.itemDelegateForColumn(2), MonoDelegate)
                   and 'Consolas' in ov.table.item(0, 2).font().families())

        # 上下文条基线：编辑一次（改面板数值再还原）后仍须在
        spin = rp.panel_editor._base_spins[int(StatType.WeaponDamage)]
        old = float(spin.value())
        before = '基线' in win.nav.summary.text()
        spin.setValue(old + 1.0)
        after = '基线' in win.nav.summary.text()
        spin.setValue(old)

        # flat 表必须单独出现在焦点规则里：它与「去框」规则特异性相同，删了就静默失去焦点提示
        sheet = _qss_text()
        focus_ok = ('QPushButton:focus' in sheet
                    and 'QTableView[flat="true"]:focus' in sheet)
        a11y_ok = (bool(win.nav.safe_badge.accessibleName())
                   and bool(rp.stat_table.table.accessibleName())
                   and bool(ac.table.accessibleName()))
    finally:
        win.nav.setCurrentRow(saved_row)
        win.resize(saved_size)
        for _ in range(4):
            QApplication.processEvents()

    mins = table_h >= 120 and list_h >= 60
    check(mins and overview_ok and main_scroll_ok and side_ok and typo_ok
          and before and after and focus_ok and a11y_ok,
          '最小窗口可用性（1024×680）/ 数值列等宽 / 基线常驻 / 焦点与可访问名',
          f'候选表 {table_h}px、已装配 {list_h}px；总览与表高一致={overview_ok}；'
          f'主区滚动={main_scroll_ok}、右栏 {side_w}px；等宽列={typo_ok}；'
          f'基线{"常驻" if before and after else "丢失"}；焦点规则（含 flat 表）={focus_ok}、'
          f'可访问名（徽标+表格）={a11y_ok}')


def assembly_checks(win, check):
    """A7/B2/B6：重复加入需确认、目标口径可见、换数据源保留类别。"""
    from .widgets import assembly_center as ac_mod

    ac = win.assembly_center
    saved_kind = ac.current_kind()
    n0 = len(win.profile.assembled)

    # B2：目标口径只读摘要 + 跳转按钮（排序基线在本页必须可自查）
    target_ok = (ac.target_summary.text().startswith('排序目标：')
                 and hasattr(ac, 'target_btn'))

    # B6：换数据源（reload）后保留用户当前类别，而不是强制跳回「宝石」
    rune_idx = ac.kind_combo.findData('rune')
    if rune_idx >= 0:
        ac.kind_combo.setCurrentIndex(rune_idx)
    ac.reload()
    kept = ac.current_kind() == 'rune'

    # A7：与已装配条目完全相同的候选，取消确认后不得进入构建
    first = win.profile.assembled[0] if win.profile.assembled else None
    blocked = True
    if first is not None:
        ac.kind_combo.setCurrentIndex(ac.kind_combo.findData(first.kind))
        if first.kind == 'gem':
            gi = ac.slot_combo.findData(int(first.category))
            if gi >= 0:
                ac.slot_combo.setCurrentIndex(gi)
        else:
            ac.level_spin.setValue(int(first.level))
        saved_confirm = ac_mod.confirm_delete
        ac_mod.confirm_delete = lambda *a, **k: False      # 用户点了「取消」
        try:
            ac._add_name(first.name)
            blocked = len(win.profile.assembled) == n0
        finally:
            ac_mod.confirm_delete = saved_confirm

    ac.kind_combo.setCurrentIndex(ac.kind_combo.findData(saved_kind))
    ac.reload()
    check(target_ok and kept and blocked,
          '装配中心（目标口径摘要 / 换源保留类别 / 重复加入需确认）',
          f'目标摘要={target_ok}；保留类别={kept}；重复被拦={blocked}')


def affix_and_filter_checks(win, check):
    """A8/A9：百分比输入按 % 显示（后缀与步进都跟随单位）、属性表过滤与表头排序。"""
    from .widgets.common import AffixValueSpin
    from .widgets.stat_table import _StatModel

    st = win.role_page.stat_table
    total = st.model.rowCount()
    common = st.proxy.rowCount()
    # C10：默认只列常用项，按钮可展开整表。小数据集下"常用 == 全量"是合法的，不判死
    scope_ok = common == st._common_hits and common <= total
    st.toggle_scope()                       # 展开整表：名称过滤/排序仍按全量语义验收
    expanded_ok = st.proxy.rowCount() == total
    full = st.proxy.rowCount()
    st.filter_edit.setText('暴击')
    hits = [str(st.proxy.index(r, 0).data())
            for r in range(st.proxy.rowCount())]
    filtered = (0 < st.proxy.rowCount() < full
                and all('暴击' in h for h in hits))
    st.filter_edit.setText('')
    restored = st.proxy.rowCount() == full

    # A8：后缀 + 步进都必须跟着显示单位换。步进留在内部 1.0 时点一次上箭头
    # 会让 30% 变成 130%，等于用另一种方式重现了本项要消灭的 100 倍错误。
    spin = AffixValueSpin()
    spin.set_percent(True)
    spin.setValue(0.3)
    text_ok = spin.text() == '30%' and spin.suffix() == '%'
    back = spin.valueFromText('30')
    spin.stepBy(1)
    stepped = spin.value()
    step_ok = abs(stepped - 0.31) < 1e-9
    spin.set_percent(False)
    spin.setValue(12.5)
    plain_ok = spin.text() == '12.5' and spin.value() == 12.5 and spin.suffix() == ''

    # A9：表头排序按**数值**（按显示文本排会把 "1,234" 排在 "12.5%" 之前），
    # 首次点击才启用（默认行序本身有含义）；验完复位，不影响后续检查。
    default_head = str(st.proxy.index(0, 0).data())
    st.sort_by_column(5)
    finals = [float(st.proxy.index(r, 5).data(_StatModel.SORT_ROLE))
              for r in range(min(4, st.proxy.rowCount()))]
    sorted_ok = (st.table.isSortingEnabled()
                 and all(finals[i] >= finals[i + 1] for i in range(len(finals) - 1)))
    st.reset_sort()
    reset_ok = (not st.table.isSortingEnabled()
                and str(st.proxy.index(0, 0).data()) == default_head)
    st.toggle_scope()                       # 还原默认的「只看常用」态
    scope_back = st.proxy.rowCount() == common

    spin.deleteLater()
    check(scope_ok and expanded_ok and scope_back
          and filtered and restored and text_ok and step_ok and plain_ok and back == 0.3
          and sorted_ok and reset_ok,
          '属性表范围（常用↔全部）/ 名称过滤 / 百分比输入（% + 1% 步进）/ 表头按数值排序',
          f'常用 {common}/{total} 行、展开生效={expanded_ok}、还原={scope_back}；'
          f'过滤={filtered}（展开态 {full} 行）；还原={restored}；'
          f'「30%」步进后={stepped:.2f}；解析 30→{back}；'
          f'排序={finals}；复位={reset_ok}')


def empty_candidate_checks(win, check):
    """A1 交互契约：空候选不给假 Δ（技能表清空），恢复候选后回到正常口径。"""
    import copy

    from .core.profile import WeaponDraft

    ee = win.compare_page.equipment_editor
    saved_slot = win.profile.compare_slot
    saved_cand = copy.deepcopy(win.profile.weapon_candidate)
    win.profile.compare_slot = 0
    win.profile.weapon_candidate = WeaponDraft()
    ee.reload()
    view = ee.compare_view
    empty_ok = (ee.last_candidate_empty and view.delta.text() == '候选未填写'
                and view.skill_hint.text().startswith('候选未填写')
                and view.skill_model.rowCount() == 0)
    win.profile.weapon_candidate = saved_cand
    win.profile.compare_slot = saved_slot
    ee.reload()
    restored_ok = not ee.last_candidate_empty and view.delta.text() != '候选未填写'
    check(empty_ok and restored_ok, '空候选空态（Δ 改判「候选未填写」/ 技能表清空 / 恢复）',
          f'空态={empty_ok}（Δ=「{view.delta.text()}」）；恢复={restored_ok}')


def reload_guard_checks(win, check):
    """E5：回填期间不发 changed；用户编辑照常发（守卫覆盖面板与词条编辑器）。"""
    from deskrawl_calc import StatType

    pe = win.role_page.panel_editor
    panel_hits = []
    pe.changed.connect(lambda: panel_hits.append(1))
    pe.reload()
    silent = not panel_hits
    spin = pe._base_spins[int(StatType.WeaponDamage)]
    old = spin.value()
    spin.setValue(old + 1.0)
    fired = len(panel_hits) == 1
    spin.setValue(old)                     # 还原原值（会再发一次，无妨）

    ce = win.compare_page.equipment_editor.candidate_editor
    item_hits = []
    ce.changed.connect(lambda: item_hits.append(1))
    ce.reload()
    silent_item = not item_hits
    check(silent and fired and silent_item,
          '回填守卫（reload 不发 changed，用户编辑照常发；面板 + 词条编辑器）',
          f'面板回填静默={silent}、编辑触发={fired}（hits={len(panel_hits)}）；'
          f'词条回填静默={silent_item}')


def layout_checks(win, check):
    """B1/C1 布局契约：窄窗竖排保住结果区；编辑卡片可纵向扩展。

    为什么要切页：隐藏的堆栈页不会参与布局（仍停在 640×480），必须在对比页上量。
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QAbstractScrollArea, QApplication, QSizePolicy

    cp = win.compare_page
    ee = cp.equipment_editor
    saved_row, size0 = win.nav.currentRow(), win.size()
    win.nav.setCurrentRow(1)
    win.resize(1280, 720)
    QApplication.processEvents()
    vertical = cp._splitter.orientation() == Qt.Vertical
    sizes = cp._splitter.sizes()
    skill_h = ee.compare_view.skill_table.height()
    # 横向滚动条 = 静默裁切的同义词：规范要求卡片/表格不横向滚动。本页曾出现两个
    # （结论区 Δ 单行把最小宽顶到 1276、右栏两枚三位小数微调框各要 169px）
    hscroll = [f'{type(a).__name__}({a.objectName() or "-"})max={a.horizontalScrollBar().maximum()}'
               for a in cp.findChildren(QAbstractScrollArea)
               if a.horizontalScrollBar().isVisible() and a.horizontalScrollBar().maximum() > 0]
    win.nav.setCurrentRow(saved_row)
    win.resize(size0)
    QApplication.processEvents()

    policy_ok = (ee.current_editor.sizePolicy().verticalPolicy() == QSizePolicy.Expanding
                 and ee.candidate_editor.sizePolicy().verticalPolicy() == QSizePolicy.Expanding)
    low = min(sizes) if sizes else 0
    check(vertical and low >= 150 and skill_h >= 120 and policy_ok and not hscroll,
          '窄窗堆叠（竖排按 sizeHint 分配，结果区不被压没）+ 编辑卡片可纵向扩展 + 无横向滚动',
          f'竖排={vertical}；分栏={sizes}（最小 {low}px）；技能表 {skill_h}px；'
          f'卡片可扩展={policy_ok}；横向滚动={hscroll or "无"}')


def structure_export_checks(win, check):
    """A2/A3 结构契约：总览 11 槽、复制结论按钮、两张表的右键导出入口。"""
    from PySide6.QtCore import Qt

    st = win.role_page.stat_table
    view = win.compare_page.equipment_editor.compare_view
    ov = win.role_page.slot_overview
    st_headers, _st_rows = st.export_rows()
    sk_headers, _sk_rows = view.export_rows()
    # 按钮文案在「复制结论/已复制」间切换（行为检查可能刚点过），故只判存在与启用态
    check(ov.table.rowCount() == 11 and ov.table.columnCount() == 4
          and ov.table.item(0, 0) is not None
          and hasattr(view, 'copy_btn') and view.copy_btn.isEnabled()
          and hasattr(st, 'filter_edit') and st.table.contextMenuPolicy() == Qt.CustomContextMenu
          and hasattr(win.assembly_center, 'target_summary')
          and win.nav.summary.text().splitlines()
          and win.profile.name in win.nav.summary.text()
          and view.skill_table.contextMenuPolicy() == Qt.CustomContextMenu
          and len(st_headers) == 6 and len(sk_headers) == 4
          and hasattr(win.compare_page.equipment_editor, 'multi_btn'),
          '装备总览（11 槽）+ 导出入口（复制结论 / 属性表与技能表右键 / 整套对比）',
          f'总览 {ov.table.rowCount()}×{ov.table.columnCount()}；'
          f'表头 {len(st_headers)}/{len(sk_headers)} 列；'
          f'按钮=「{view.copy_btn.text()}」；'
          f'右键菜单={st.table.contextMenuPolicy() == Qt.CustomContextMenu}')


def sidebar_summary_checks(win, check):
    """B3：顶栏上下文条的构建摘要（名称/等级/职业）常驻，收起导航时随上下文条一起隐藏。

    为什么用独立实例验收起态：拿真实导航收起会在检查链中途改窗口几何，影响后面的
    布局断言（layout_checks 量的是分栏像素）。
    """
    from .widgets.navigation import TopNav

    nav = TopNav([('a', '甲'), ('b', '乙'), ('c', '丙')])
    nav.set_profile_summary('测试构建 · Lv70 · 野蛮人', '提示')
    text_ok = '测试构建' in nav.summary.text() and 'Lv70' in nav.summary.text()
    nav.toggle_collapsed()
    collapsed_ok = (not nav.summary.isVisibleTo(nav) and not nav.badge.isVisibleTo(nav)
                    and nav._items[0].text() == '' and nav.collapsed())
    nav.toggle_collapsed()
    expanded_ok = nav.summary.isVisibleTo(nav) and nav._items[0].text() == '甲'
    nav.deleteLater()
    real_ok = bool(win.nav.summary.text()) and '测试构建' not in win.nav.summary.text()
    check(text_ok and collapsed_ok and expanded_ok and real_ok,
          '上下文条构建摘要（名称/等级/职业；收起时上下文条与链接文字一起隐藏）',
          f'摘要文本={text_ok}；收起隐藏={collapsed_ok}；展开恢复={expanded_ok}；'
          f'主窗口摘要={win.nav.summary.text().splitlines()[:1]}')


def import_worker_checks(win, check):
    """D3：导入线程三条出口（错误码透传 / 成功交回结果 / 作废后不发结果）。

    直接调 run() 而不 start()：这三条是信号契约，不需要真的跨线程；真跑线程还要等事件循环，
    在冒烟里只会变慢或变脆。
    """
    from .core import import_worker as iw_mod
    from .core import memory_import
    from .core.memory_import import MemoryImportError

    hits = []
    orig = memory_import.import_snapshot
    try:
        def boom():
            raise MemoryImportError('模拟读取失败', 'env', code='no_process')

        memory_import.import_snapshot = boom
        worker = iw_mod.ImportWorker()
        worker.done.connect(lambda res, code, msg: hits.append((res, code, msg)))
        worker.run()
        err_ok = bool(hits) and hits[-1][0] is None and hits[-1][1] == 'no_process'

        memory_import.import_snapshot = lambda: 'SNAP'
        hits.clear()
        worker.run()
        ok_ok = bool(hits) and hits[-1][0] == 'SNAP' and hits[-1][1] == ''

        hits.clear()
        worker.cancel()
        worker.run()
        cancel_ok = not hits
        worker.deleteLater()
    finally:
        memory_import.import_snapshot = orig
    check(err_ok and ok_ok and cancel_ok and win._import_worker is None,
          '导入线程（错误码透传 / 结果交回主线程 / 作废后不发结果）',
          f'错误出口={err_ok}；成功出口={ok_ok}；作废={cancel_ok}；主窗口无线程残留='
          f'{win._import_worker is None}')


def theme_checks(win, check):
    """A12 交互契约：视图菜单可切主题，切换后 QSS 整体换色、再切回来。

    断言用 theme 模块的画布常量而不是写死色值：色板换代时这里不该跟着改（否则「换配色」
    必然要动自检，测试就变成了在保护旧颜色，而不是保护「浅色不残留暗底」这件事）。
    """
    from PySide6.QtWidgets import QApplication

    from .core import theme

    view_menu = next((a.menu() for a in win.menuBar().actions() if a.text() == '视图'), None)
    menu_ok = view_menu is not None and any('主题' in a.text() for a in view_menu.actions())
    saved = win._theme

    win._set_theme('light', notify=False)
    light_sheet = QApplication.instance().styleSheet().upper()
    light_ok = theme.CANVAS_LIGHT in light_sheet and theme.CANVAS_DARK not in light_sheet
    win._set_theme(saved, notify=False)
    back_ok = theme.CANVAS_DARK in QApplication.instance().styleSheet().upper()
    check(menu_ok and light_ok and back_ok,
          '主题切换（视图 → 主题 / 顶栏开关：浅色整体换色且不残留暗底，可切回）',
          f'菜单={menu_ok}；浅色生效={light_ok}；切回={back_ok}；当前={win._theme}')


def icon_checks(win, check):
    """C5：3 个页面条目与 4 个高频动作都有真实装载的图标（资源缺失时这里先红）。"""
    from .widgets.icons import icon

    page_ok = all(not btn.icon().isNull() for btn in win.nav._items)
    ee = win.compare_page.equipment_editor
    buttons = [('播种', ee.seed_btn), ('整套对比', ee.multi_btn),
               ('复制结论', ee.compare_view.copy_btn), ('加入构建', win.assembly_center.add_btn)]
    missing = [name for name, btn in buttons if btn.icon().isNull()]
    check(page_ok and not missing and not icon('page_role').isNull(),
          '图标（3 页条目 + 4 个高频动作；SVG 资源真的被 QIcon 载入）',
          f'页面图标={page_ok}；动作按钮缺失={missing or "无"}；'
          f'icon() 兜底可用={not icon("page_role").isNull()}')


def help_checks(win, check):
    """B5 交互契约：帮助面板分节 + 检索过滤目录（术语表仍可见）+ 无命中时给提示。"""
    from .core.glossary import help_topics
    from .widgets.help_panel import HelpPanelDialog

    topics = help_topics('关于本文')
    dlg = HelpPanelDialog(topics, 'terms', win)
    keys = [t[0] for t in topics]
    initial_ok = keys[:4] == ['workflow', 'terms', 'caliber', 'source'] and dlg.current_key() == 'terms'

    dlg.search.setText('条件池')
    visible = [dlg.list.item(i).text() for i in range(dlg.list.count())
               if not dlg.list.item(i).isHidden()]
    search_ok = '术语表' in visible and 0 < len(visible) < len(topics)

    dlg.search.setText('ZZZ不可能出现的词')
    none_ok = '没有命中' in dlg.hint.text()
    body_ok = bool(dlg.body.toPlainText())       # 检索无命中时正文不能被清空（否则像帮助丢了）

    help_menu = next((a.menu() for a in win.menuBar().actions() if a.text() == '帮助'), None)
    menu_ok = help_menu is not None and any('可检索' in a.text() for a in help_menu.actions())
    dlg.deleteLater()
    check(initial_ok and search_ok and none_ok and body_ok and menu_ok,
          '帮助面板（分节 + 检索过滤目录 + 无命中提示 + 菜单入口）',
          f'分节={keys}；「条件池」命中 {len(visible)} 节；'
          f'无命中提示={none_ok}；菜单入口={menu_ok}')


def class_location_checks(win, check):
    """B4 概念归位：职业唯一入口在角色页面板，对比页只读跟随（含技能表联动）。"""
    pe = win.role_page.panel_editor
    ee = win.compare_page.equipment_editor
    saved = win.profile.hero_class
    has_owner = hasattr(pe, 'class_combo') and not hasattr(ee, 'class_combo')

    idx = pe.class_combo.findData(1)                 # 野蛮人
    pe.class_combo.setCurrentIndex(idx if idx >= 0 else 0)
    wrote = win.profile.hero_class == 1
    label_text = ee.class_label.text()          # 还原前取文案：还原后这里会变回「未设置」
    label_ok = '野蛮人' in label_text
    skill_ok = win.compare_page.skill_card._options_class == 1

    pe.class_combo.setCurrentIndex(0 if saved is None else pe.class_combo.findData(saved))
    restored = win.profile.hero_class == saved
    check(has_owner and wrote and label_ok and skill_ok and restored,
          '职业归位（角色页选择 → 对比页只读跟随 + 技能表重列）',
          f'唯一入口={has_owner}；写回={wrote}；只读标签=「{label_text}」；'
          f'技能下拉职业=1；还原={restored}')


def library_checks(win, check):
    """A6 交互契约：文件菜单有构建库入口，窗口能按目录内容出行（不 exec，避免阻塞）。"""
    from .widgets.build_library import BuildLibraryDialog

    file_menu = next((a.menu() for a in win.menuBar().actions() if a.text() == '文件'), None)
    menu_ok = file_menu is not None and any('构建库' in a.text() for a in file_menu.actions())
    dlg = BuildLibraryDialog(win.gd, lambda p: None, lambda: False, win)
    rows_ok = dlg.table.rowCount() == len(dlg._entries)
    cols_ok = dlg.table.columnCount() == 7 and '构建目录' in dlg.hint.text()
    dlg.deleteLater()
    check(menu_ok and rows_ok and cols_ok,
          '构建库（文件菜单入口 + 按目录出行 + 7 列元信息）',
          f'菜单={menu_ok}；{dlg.table.rowCount()} 份；列数={dlg.table.columnCount()}')


def undo_checks(win, check):
    """A5 交互契约：面板数值可撤销/重做，且「切槽」这类视图态不占撤销步。"""
    from deskrawl_calc import StatType

    spin = win.role_page.panel_editor._base_spins[int(StatType.WeaponDamage)]
    before = float(spin.value())
    n0 = win.undo_stack.count()
    spin.setValue(before + 5.0)
    pushed = win.undo_stack.count() == n0 + 1
    label_ok = win.undo_action.text().startswith('撤销') and '面板' in win.undo_action.text()

    win.undo_action.trigger()
    after_undo = float(win.role_page.panel_editor
                       ._base_spins[int(StatType.WeaponDamage)].value())
    win.redo_action.trigger()
    after_redo = float(win.role_page.panel_editor
                       ._base_spins[int(StatType.WeaponDamage)].value())
    win.undo_action.trigger()                       # 收回编辑，避免污染后续检查

    # 撤销之后再做一次编辑，新步骤的 before 必须是「当前实际状态」：否则再撤销会跳到
    # 用户从没见过的值（快照基线与栈指针不同步的经典症状，这里钉住）
    spin.setValue(before + 7.0)
    win.undo_action.trigger()
    after_chain = float(win.role_page.panel_editor
                        ._base_spins[int(StatType.WeaponDamage)].value())
    chain_ok = abs(after_chain - before) < 1e-9

    ee = win.compare_page.equipment_editor
    n1 = win.undo_stack.count()
    ee.slot_combo.setCurrentIndex(ee.slot_combo.findData(2))     # 只是看一眼别的槽
    view_ok = win.undo_stack.count() == n1
    ee.slot_combo.setCurrentIndex(ee.slot_combo.findData(0))
    check(pushed and label_ok and abs(after_undo - before) < 1e-9
          and abs(after_redo - (before + 5.0)) < 1e-9 and chain_ok and view_ok,
          '撤销/重做（面板数值一步一回；撤销后再编辑仍回到当前状态；切槽不入栈）',
          f'入栈={pushed}（{n0}→{n1}）；菜单「{win.undo_action.text()}」；'
          f'撤销后={after_undo:g}（原 {before:g}）、重做后={after_redo:g}；'
          f'撤销→编辑→撤销={after_chain:g}（应 {before:g}）；切槽后步数不变={view_ok}')


def multi_compare_checks(win, check):
    """A4 交互契约：整套对比窗口按参与槽出行，且明确「不可相加」的口径。"""
    from .core.compare_multi import multi_compare
    from .widgets.multi_compare import MultiCompareDialog

    res = multi_compare(win.profile, win.gd)
    dlg = MultiCompareDialog(win.profile, win.gd, win)
    rows_ok = dlg.table.rowCount() == len(res.slots) and len(res.slots) >= 1
    head_ok = '参与' in dlg.head.text() and '不能相加' in dlg.note.text()
    enabled_ok = win.compare_page.equipment_editor.multi_btn.isEnabled() == bool(res.slots)
    dlg.deleteLater()
    check(rows_ok and head_ok and enabled_ok,
          '整套对比（按参与槽出行 + 口径注脚 + 空候选时入口禁用）',
          f'参与 {len(res.slots)} 槽、表 {dlg.table.rowCount()} 行；'
          f'总 Δ={res.delta_pct:+.2f}%；入口可用={enabled_ok}')


def behavior_export_checks(win, check):
    """A2/A3 交互契约：总览双击跳槽（走既有下拉信号）+ 复制结论进剪贴板。"""
    from PySide6.QtWidgets import QApplication

    view = win.compare_page.equipment_editor.compare_view
    ov = win.role_page.slot_overview

    # 双击 → 切到对比页并选中该槽；结束后还原页面与槽位，避免污染后续检查
    saved_page, saved_slot = win.nav.currentRow(), win.profile.compare_slot
    ov.table.cellDoubleClicked.emit(3, 0)
    jump_ok = (win.nav.currentRow() == 1 and win.profile.compare_slot == 3
               and win.compare_page.equipment_editor.slot_combo.currentData() == 3)
    win._open_compare_slot(saved_slot)
    win.nav.setCurrentRow(saved_page)
    check(jump_ok, '装备总览双击 → 对比页对应槽',
          f'切页={jump_ok}；还原后页={win.nav.currentRow()}、槽={win.profile.compare_slot}')

    # 复制结论：结论行 + 口径注脚一起进剪贴板（截屏之外的第二出口）
    view.copy_btn.click()
    copied = QApplication.clipboard().text()
    check('变化' in copied and '口径：' in copied and view.copy_btn.text() == '已复制',
          '复制结论（结论行 + 口径注脚进剪贴板，按钮即时反馈）',
          f'长度={len(copied)}；首行=「{copied.splitlines()[0][:40]}…」')
