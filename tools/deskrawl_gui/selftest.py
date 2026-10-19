# -*- coding: utf-8 -*-
"""命令行自检。

--smoke    ：实例化主窗口并统计 widget 数，验证骨架在无显示环境下可跑通。
--selftest ：内核公式自检 + GUI 服务层与引擎直算对拍（逐项补齐）。

对拍原则：GUI 侧（CharacterProfile → calc_service）与引擎侧（直接构造 StatSheet/Weapon）
走两条独立路径，比对期望 DPS 与 Δ%，误差阈值 <0.5%。
"""
import contextlib
import io
import json
import os
import re
import sys

# demo 场景锚点（2026-10-07 实测，随内核一起冻结）
ANCHORS = {'current_dps': 197.9, 'candidate_dps': 226.3, 'delta_pct': 14.32}
TOL_PCT = 0.5

# QSS 锚点对账的显式豁免表（选择性跳过，理由必须随条写清）。
# 目前为空：全部 #objectName、[属性] 选择器都能与代码双向对上，不靠豁免消红。
QSS_ANCHOR_EXEMPT = set()


def _rel_pct(a: float, b: float) -> float:
    """相对误差（百分点）。"""
    if b == 0:
        return 0.0 if a == 0 else float('inf')
    return abs(a - b) / abs(b) * 100.0


class Report:
    """收集并打印 [PASS]/[FAIL]，避免各处自己拼字符串。"""

    def __init__(self):
        self.checks = []

    def add(self, ok, label, detail=''):
        ok = bool(ok)
        self.checks.append((ok, label))
        tail = f'：{detail}' if detail else ''
        print(f'  [{"PASS" if ok else "FAIL"}] {label}{tail}')
        return ok

    def ok(self) -> bool:
        return all(c[0] for c in self.checks)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c[0])


def run_smoke() -> int:
    """建窗口后立即计数退出（不进事件循环），用于自动化验证骨架。"""
    from PySide6.QtWidgets import QWidget

    from .app import MainWindow, build_application

    app = build_application(['deskrawl_gui', '--smoke'])
    win = MainWindow()
    win.show()
    app.processEvents()
    count = len(win.findChildren(QWidget)) + 1
    print(f'[smoke] 主窗口就绪：widget 计数 = {count}')

    # 顺带校验菜单结构与自检弹窗文案（走生产代码路径，不 mock）
    menu_titles = [a.text() for a in win.menuBar().actions()]
    tools_menu = next((a.menu() for a in win.menuBar().actions() if a.text() == '工具'), None)
    kernel_action = next((a for a in tools_menu.actions() if '内核自检' in a.text()), None) \
        if tools_menu else None
    import_menu = next((a.menu() for a in win.menuBar().actions() if a.text() == '数据导入'), None)
    import_action = next((a for a in import_menu.actions() if '从运行中的游戏导入' in a.text()),
                         None) if import_menu else None
    # 帮助入口是术语门槛的对策落点，缺了就等于把用户推回文档——与导入项同样做结构断言
    help_menu = next((a.menu() for a in win.menuBar().actions() if a.text() == '帮助'), None)
    help_ok = help_menu is not None and any('术语表' in a.text() for a in help_menu.actions()) \
        and any('口径说明' in a.text() for a in help_menu.actions())
    # 导入项可用性必须与指纹自检结果一致（一致性断言，任何环境都可判定）
    import_state_ok = (import_action is not None and import_action.isEnabled() == win._fingerprint_ok)
    print(f'[smoke] 菜单：{menu_titles}')
    print(f'[smoke] 工具→内核自检：{"已就绪" if kernel_action and kernel_action.isEnabled() else "缺失"}；'
          f'数据导入{"已就绪（指纹通过）" if win._fingerprint_ok else "已禁用（指纹不符，中文提示已就位）"}，'
          f'可用性一致={import_state_ok}；帮助菜单（术语表/口径说明）={"已就绪" if help_ok else "缺失"}')
    ok, summary, _ = win._kernel_selftest_message()
    print(f'[smoke] 内核自检弹窗文案：{summary}（通过={ok}）')

    print('[smoke] 交互检查：')
    behavior_ok = _gui_behavior_checks(win)

    print('[smoke] 会话持久化检查：')
    state_ok = _session_state_smoke_checks()

    print('[smoke] QSS 锚点对账：')
    qss_ok = _qss_anchor_checks()

    print('[smoke] 结构锚点：')
    struct_ok = _structure_checks(win)

    if count <= 0:
        print('[smoke] 失败：widget 计数为 0', file=sys.stderr)
        return 1
    if kernel_action is None or not kernel_action.isEnabled() or not import_state_ok or not ok:
        print('[smoke] 失败：菜单/自检弹窗校验未通过', file=sys.stderr)
        return 1
    if not help_ok:
        print('[smoke] 失败：帮助菜单（术语表/口径说明）缺失', file=sys.stderr)
        return 1
    if not behavior_ok:
        print('[smoke] 失败：交互检查未通过', file=sys.stderr)
        return 1
    if not state_ok:
        print('[smoke] 失败：会话持久化检查未通过', file=sys.stderr)
        return 1
    if not qss_ok:
        print('[smoke] 失败：QSS 锚点对账未通过', file=sys.stderr)
        return 1
    if not struct_ok:
        print('[smoke] 失败：结构锚点缺失', file=sys.stderr)
        return 1
    return 0


def _session_state_smoke_checks() -> bool:
    """会话持久化端到端（headless）：改数据 → close 落盘 → 新窗口恢复尺寸/页面/数据。

    全程在临时目录上进行（monkeypatch STATE_PATH），不触碰真实 data/session_state.json；
    冒烟的主窗口走默认 persist_state=False（不读写用户状态），这里显式开启生产路径。
    """
    import tempfile

    from .app import MainWindow
    from .core import session_state

    tmp = os.path.join(tempfile.mkdtemp(prefix='deskrawl_state_'), 'state.json')
    old_path = session_state.STATE_PATH
    session_state.STATE_PATH = tmp
    try:
        w1 = MainWindow(persist_state=True)
        w1.profile.name = '会话恢复测试'
        w1.nav.setCurrentRow(1)
        w1.resize(1000, 700)
        w1.close()                                   # closeEvent → 落盘
        saved = os.path.exists(tmp)
        w2 = MainWindow(persist_state=True)          # 启动路径：读盘恢复
        ok = (saved and w2.profile.name == '会话恢复测试'
              and w2.nav.currentRow() == 1 and w2.stack.currentIndex() == 1
              and w2.size() == w1.size())
        print(f'  [{"PASS" if ok else "FAIL"}] 会话持久化（close 落盘 → 新窗口恢复尺寸/页面/数据）：'
              f'落盘={saved}，数据「{w2.profile.name}」，页={w2.nav.currentRow()}，'
              f'尺寸 {w2.size().width()}x{w2.size().height()}（期望 {w1.size().width()}x{w1.size().height()}）')
        return ok
    finally:
        session_state.STATE_PATH = old_path


def _structure_checks(win) -> bool:
    """关键结构与入口的锚点断言（不追像素，只固化「哪些东西必须在」）。

    为什么补：--selftest 全是数值断言、--smoke 原本只有 widget 计数与少量行为断言——布局/入口
    被重构掉（比如撤掉帮助菜单、数据源徽标、候选播种按钮）不会有人发现。这里把本轮新增的
    可见契约钉住，后续改动若拆掉它们会直接变红。
    """
    from PySide6.QtWidgets import QCheckBox, QLabel

    results = []

    def check(cond, label, detail=''):
        results.append(bool(cond))
        print(f'  [{"PASS" if cond else "FAIL"}] {label}' + (f'：{detail}' if detail else ''))

    cv = win.compare_page
    ee = cv.equipment_editor
    ac = win.assembly_center
    view = ee.compare_view

    # 一屏一个结论：Δ 是最大号的那个；两个 DPS 数字同号（样式锚点同源）
    delta_ids = {'deltaUp', 'deltaDown', 'deltaFlat'}
    two_dps = [w for w in view.findChildren(QLabel) if w.objectName() == 'dpsBig']
    check(len(two_dps) == 2 and view.delta.objectName() in delta_ids,
          '对比结果三格（2×dpsBig + Δ 三态之一）',
          f'dpsBig={len(two_dps)}；Δ={view.delta.objectName()}')

    # 侧栏：3 个页面 + 收起按钮 + 数据源徽标（U4/V9 的可见契约）
    nav_ok = (win.nav.currentRow() >= 0 and len(win.nav._keys) == 3
              and win.nav.toggle.isVisible() and bool(win.nav.badge.text()))
    check(nav_ok, '侧栏 3 页 + 收起按钮 + 数据源徽标',
          f'页数={len(win.nav._keys)}；徽标=「{win.nav.badge.text().splitlines()[0]}」')

    # 装备对比页：候选播种入口 + 词条区间提示位 + α 横幅（可隐）
    check(hasattr(ee, 'seed_btn') and hasattr(ee.candidate_editor, 'range_label')
          and hasattr(ee, 'alpha_banner'),
          '对比页入口（播种按钮 / 区间提示位 / α 横幅）',
          f'播种可用={ee.seed_btn.isEnabled()}（当前候选非空时应为 False）')

    # 目标栏：血线条件提示行 + 伤害类型 + 9 个勾选（I5 的可见契约）。
    # 按 _cond_checks 清点而不是 findChildren(QCheckBox)：实测 DPS 计卡片也挂在目标栏内，
    # 它自带「实时」勾选框，子树扫描会把外部卡片的控件算进来（曾因此误报 10 项）。
    te = cv.target_editor
    conds = list(te._cond_checks.values())
    check('血线判定' in te.hp_cond_label.text() and len(conds) == 9,
          '目标栏（血线条件提示 + 9 项条件勾选）',
          f'提示=「{te.hp_cond_label.text()}」；勾选={len(conds)}')

    # 装配中心：5 列候选表 + 已装配清单 + 参数条
    check(ac.model.columnCount() == 5 and ac.assembled_list is not None,
          '装配中心（5 列候选表 + 已装配清单）',
          f'列数={ac.model.columnCount()}')

    # DPS 计：轮询归页面可见性管（T2 的可见契约）
    meter = cv.dps_meter
    check(hasattr(meter, '_active') and hasattr(meter, 'live_check'),
          'DPS 计带可见性启停与「实时」开关',
          f'active={meter._active}（当前页 row={win.nav.currentRow()}）；'
          f'定时器运行={meter._timer.isActive()}')

    # 应用/任务栏图标：SVG 资源被 QIcon 真载入（资源被删或平台缺 SVG 插件时这里先红）
    from PySide6.QtWidgets import QApplication

    icon = QApplication.instance().windowIcon()
    check(not icon.isNull(), '应用/任务栏图标已装载（resources/app_icon.svg）',
          f'可用尺寸={[f"{s.width()}x{s.height()}" for s in icon.availableSizes()][:2]}')

    # 两张显示表走 model/view：行列数由模型给出（QTableWidget 的 item 通道已移除，
    # 后续若有人改回逐格 setItem，这里的 isinstance/列数断言会先红）
    from PySide6.QtCore import QAbstractTableModel

    st = win.stat_table
    check(isinstance(st.model, QAbstractTableModel)
          and isinstance(view.skill_model, QAbstractTableModel)
          and st.model.columnCount() == 6 and view.skill_model.columnCount() == 4,
          '属性表 / 技能表改 model-view（6 列 / 4 列）',
          f'属性 {st.model.rowCount()} 行；技能 {view.skill_model.rowCount()} 行；'
          f'视图={type(st.table).__name__}')

    # 提示只剩浮层一条通道：状态栏整个移除（两处并存会让同一条消息出现在两个位置）
    from PySide6.QtWidgets import QStatusBar

    toast = win.toast
    check(toast.objectName() == 'toast' and not toast.isVisible()
          and win.findChild(QStatusBar) is None,
          '浮层提示已装配（#toast，初始隐藏；状态栏已移除）',
          f'objectName={toast.objectName()}；可见={toast.isVisible()}；'
          f'状态栏={win.findChild(QStatusBar)}')

    return all(results)


def _qss_anchors(qss_text: str, code_text: str) -> tuple:
    """(QSS 文本, 代码文本) → (死选择器, 无规则的属性, 无规则的 objectName)。

    抽成纯函数是为能自证：用一对合成的错锚点要求它必须报红——否则断言本身就是摆设
    （同 rva_audit 的 --falsify 口径）。判定向：QSS 的 #id 要在代码里出现过（objectName
    允许由辅助函数产出，故按"出现过字面量"判）；setProperty/setObjectName 字面量要有规则。
    """
    stripped = re.sub(r'/\*.*?\*/', '', qss_text, flags=re.S)   # 去注释：色值形似 id，会误报
    ids, props = set(), set()
    for block in stripped.split('{'):
        head = block.rsplit('}', 1)[-1]          # '{' 之前、上一个 '}' 之后 = 该块的选择器
        ids.update(re.findall(r'#([A-Za-z_]\w*)', head))
        props.update(re.findall(r'\[([A-Za-z_]\w*)', head))
    set_names = set(re.findall(r"setObjectName\(\s*['\"]([A-Za-z_]\w*)['\"]", code_text))
    set_props = set(re.findall(r"setProperty\(\s*['\"]([A-Za-z_]\w*)['\"]", code_text))
    literals = set(re.findall(r"['\"]([A-Za-z_]\w*)['\"]", code_text))
    ids -= QSS_ANCHOR_EXEMPT
    props -= QSS_ANCHOR_EXEMPT
    return (sorted(ids - literals), sorted(set_props - props), sorted(set_names - ids))


def _qss_anchor_checks() -> bool:
    """style.qss 选择器 ↔ 代码锚点 双向对账（零依赖，挂 --smoke）。

    为什么需要：style.qss 是唯一视觉事实源，但选择器与 setObjectName/setProperty 之间原本
    没有任何约束——已出现过 setProperty('state') 写了而 QSS 无对应规则的死钩子，失败态因此
    被按 18px 大字渲染。豁免表 QSS_ANCHOR_EXEMPT 里的每一条都必须写清理由，不许用来消红。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    qss_path = os.path.join(here, 'resources', 'style.qss')
    if not os.path.exists(qss_path):
        print('  [FAIL] QSS 锚点对账：主题文件缺失', file=sys.stderr)
        return False
    with open(qss_path, encoding='utf-8') as f:
        qss_text = f.read()
    code_text = ''
    for root, _dirs, files in os.walk(here):
        for name in files:
            # 跳过自检自身：它里面的合成锚点字面量（ghostId/ghostProp/ghostName）会污染实扫
            if name.endswith('.py') and not name.startswith('selftest'):
                with open(os.path.join(root, name), encoding='utf-8') as f:
                    code_text += f.read() + '\n'
    dead, unruled, orphan = _qss_anchors(qss_text, code_text)
    # 自证：合成的错锚点必须被判红（三向各一），否则判定逻辑本身失效
    f_dead, f_unruled, f_orphan = _qss_anchors(
        '#ghostId { color: #FFFFFF; }',
        "setProperty('ghostProp', 1)\nsetObjectName('ghostName')")
    falsified = (f_dead == ['ghostId'] and f_unruled == ['ghostProp'] and f_orphan == ['ghostName'])
    ok = falsified and not dead and not unruled and not orphan
    print(f'  [{"PASS" if ok else "FAIL"}] QSS 锚点双向对账：'
          f'死选择器={dead or "无"}；无规则的属性={unruled or "无"}；'
          f'无规则的 objectName={orphan or "无"}；自证={falsified}')
    return ok


def _gui_behavior_checks(win) -> bool:
    """在已建好的主窗口上跑一遍关键交互（真实控件 + 真实信号链），headless 可验证。

    覆盖任务书里的交互要求：词条下拉用内核全量中文名、面板改动→属性表实时刷新、
    装配中心搜索/加入/就地改参数/删除确认、排序表按数值排序、双击加入构建。
    检查完逐个还原，避免污染 demo 构建。
    """
    import copy

    from PySide6.QtCore import Qt

    from deskrawl_calc import StatType

    from .widgets import assembly_center as _ac_mod

    results = []

    # 删除类操作会弹模态确认框：全程短路为「确认」。原先只在步骤 3 局部打补丁，步骤 5 的
    # 双添加→删除收尾调用的是真对话框，非交互环境会挂死在等待点击上（实测每次跑都卡）。
    saved_confirm = _ac_mod.confirm_delete
    _ac_mod.confirm_delete = lambda *a, **k: True

    def check(cond, label, detail=''):
        results.append(bool(cond))
        print(f'  [{"PASS" if cond else "FAIL"}] {label}' + (f'：{detail}' if detail else ''))

    def stat_final(name):
        model = win.stat_table.model
        for r in range(model.rowCount()):
            if model.cell_text(r, 0) == name:
                return float(model.cell_text(r, 5))
        return None

    # 1) 武器词条下拉 = 内核 StatType 全量中文名
    editor = win.equipment_editor.candidate_editor
    saved = copy.deepcopy(editor.draft.affixes)
    editor.affixes.append_row()
    combo = editor.affixes.cellWidget(0, 0)
    labels = [combo.itemText(i) for i in range(combo.count())]
    check(combo.count() == len(list(StatType)) and not any(s.startswith('Stat') for s in labels),
          '词条下拉含内核全部属性中文名', f'{combo.count()} 项，示例 {labels[:3]}')
    editor.draft.affixes = saved
    editor.reload()

    # 1b) 类型列 = 只读文本（游戏固定「加法」），随属性刷新填写提示；百分比类附小数提示
    saved = copy.deepcopy(editor.draft.affixes)
    editor.affixes.append_row()
    r = editor.affixes.rowCount() - 1
    s_combo = editor.affixes.cellWidget(r, 0)
    t_item = editor.affixes.item(r, 1)
    v_spin = editor.affixes.cellWidget(r, 2)

    def add_only_text():
        """类型列必须是文本、不是控件：用下拉（哪怕禁用）承载单值会让人以为能改。"""
        return (editor.affixes.cellWidget(r, 1) is None
                and t_item is not None and t_item.text() == '加法'
                and int(t_item.data(Qt.UserRole)) == 0)

    pct_ok = add_only_text() and '小数' in t_item.toolTip() and '小数' in v_spin.toolTip()
    s_combo.setCurrentIndex(s_combo.findData(int(StatType.Strength)))
    num_ok = add_only_text() and '加法' in t_item.toolTip()
    check(pct_ok and num_ok, '词条类型为只读文本「加法」（无下拉；提示随属性刷新）',
          f'物理伤害%：文本加法+小数提示={pct_ok}；力量：仍为加法={num_ok}')
    editor.draft.affixes = saved
    editor.reload()

    # 1c) 词条删除：× 即删（不弹确认框打断连续编辑）+ 一次性撤销条把该行按原位置放回
    saved = copy.deepcopy(editor.draft.affixes)
    editor.affixes.append_row()
    r = editor.affixes.rowCount() - 1
    n0 = editor.affixes.rowCount()
    editor.affixes.cellWidget(r, 3).click()          # 点该行的「×」
    n1 = editor.affixes.rowCount()
    pending = editor._undo_state is not None and '已删除' in editor.undo_label.text()
    editor.undo_btn.click()
    n2 = editor.affixes.rowCount()
    check(n1 == n0 - 1 and pending and n2 == n0 and editor._undo_state is None,
          '词条删除可撤销（× 即删 + 撤销按原位置放回）',
          f'{n0} 行 → 删后 {n1} 行 → 撤销后 {n2} 行；撤销条就绪={pending}')
    editor.draft.affixes = saved
    editor.reload()

    # 2) 面板改动 → 属性表实时刷新
    spin = win.panel_editor._base_spins[int(StatType.WeaponDamage)]
    before = stat_final('武器伤害')
    spin.setValue(37.0)
    after = stat_final('武器伤害')
    check(after is not None and abs(after - 37.0) < 1e-9, '面板改动 → 属性表实时刷新',
          f'武器伤害 最终值 {"（无该行）" if before is None else before} → {after}')
    spin.setValue(0.0)

    # 2b) 职业主属性下拉写回 profile（DPS 加成因子由 _snapshot_checks 用夹具覆盖）
    pc = win.panel_editor.primary_combo
    pc.setCurrentIndex(pc.findData(int(StatType.Strength)))
    wrote = win.profile.primary_stat == int(StatType.Strength)
    pc.setCurrentIndex(0)
    check(wrote and win.profile.primary_stat is None,
          '职业主属性下拉写回 profile（力量 → 未设置还原）',
          f'{pc.count()} 个选项；写回={wrote}')

    # 2c) 参考技能卡已迁到对比页「目标基础」正下方，仍是唯一入口（角色页不再持有技能控件）
    sc = win.compare_page.skill_card
    te = win.compare_page.target_editor
    saved_skill, saved_idx = win.profile.skill_name, sc.skill_combo.currentIndex()
    pos_ok = te.layout().indexOf(sc) == 1
    idx = sc.skill_combo.findData('WarriorHeavyAttack3')
    sc.skill_combo.setCurrentIndex(idx if idx >= 0 else sc.skill_combo.count() - 1)
    wrote_skill = win.profile.skill_name == 'WarriorHeavyAttack3'
    sc.skill_combo.setCurrentIndex(saved_idx)
    restored = win.profile.skill_name == saved_skill
    check(pos_ok and wrote_skill and restored
          and not hasattr(win.panel_editor, 'skill_combo'),
          '参考技能卡在对比页目标基础下方（唯一入口，写回 profile）',
          f'布局序号={te.layout().indexOf(sc)}（应 1）；写回={wrote_skill}；'
          f'还原={restored}；角色页无技能控件={not hasattr(win.panel_editor, "skill_combo")}')

    # 3) 装配中心：搜索过滤 + 加入/删除（删除有确认对话框，测试里短路为「确认」）
    ac = win.assembly_center
    saved_confirm = _ac_mod.confirm_delete
    _ac_mod.confirm_delete = lambda *a, **k: True       # headless 走通删除全路径
    try:
        total = ac.model.rowCount()
        ac.search_edit.setText('GemAmethyst')
        filtered = ac.proxy.rowCount()
        check(0 < filtered < total, '装配中心搜索过滤生效',
              f'{total} 项中剩余 {filtered} 项')
        ac.search_edit.setText('')

        n0 = len(win.profile.assembled)
        ac.table.setCurrentIndex(ac.proxy.index(0, 0))
        ac._add_selected()
        n1 = len(win.profile.assembled)
        check(n1 == n0 + 1, '装配中心「加入构建」生效', f'{n0} → {n1} 项')

        # 3b) 已装配就地改参数：宝石改部位（等级恒 1）、非宝石改等级
        ac.assembled_list.setCurrentRow(n1 - 1)
        gem_edit_ok = (win.profile.assembled[n1 - 1].kind == 'gem'
                       and ac.edit_label.text() == '镶嵌部位')
        ac.edit_slot_combo.setCurrentIndex(0)               # 武器孔 → 护甲
        ac._apply_assembled_edit()
        cat_ok = win.profile.assembled[n1 - 1].category == 0
        check(gem_edit_ok and cat_ok, '已装配宝石就地改部位',
              f'标签={ac.edit_label.text()}；category → {win.profile.assembled[n1 - 1].category}')

        ri = next(i for i in range(ac.kind_combo.count())
                  if ac.kind_combo.itemData(i) == 'rune')
        ac.kind_combo.setCurrentIndex(ri)
        ac.table.setCurrentIndex(ac.proxy.index(0, 0))
        ac._add_selected()
        n2 = len(win.profile.assembled)
        ac.assembled_list.setCurrentRow(n2 - 1)
        rune_edit_ok = (win.profile.assembled[n2 - 1].kind == 'rune'
                        and ac.edit_label.text() == '符文等级')
        ac.edit_level_spin.setValue(7)
        ac._apply_assembled_edit()
        lvl_ok = win.profile.assembled[n2 - 1].level == 7
        check(rune_edit_ok and lvl_ok, '已装配符文就地改等级',
              f'标签={ac.edit_label.text()}；level → {win.profile.assembled[n2 - 1].level}')

        while len(win.profile.assembled) > n0:
            ac.assembled_list.setCurrentRow(len(win.profile.assembled) - 1)
            ac._remove_selected()
        check(len(win.profile.assembled) == n0, '装配中心「删除选中」（含确认）生效',
              f'回到 {len(win.profile.assembled)} 项')
    finally:
        _ac_mod.confirm_delete = saved_confirm

    # 4) 排序表：四列均可排序，且 ΔDPS 按数值而非字符串排
    table = ac.table
    model = table.model()       # QSortFilterProxyModel（排序键 UserRole 经由代理透传）
    head_flips = []
    for col in (0, 2, 3, 4):
        table.sortByColumn(col, Qt.DescendingOrder)
        head_desc = model.index(0, col).data(Qt.UserRole)
        table.sortByColumn(col, Qt.AscendingOrder)
        head_asc = model.index(0, col).data(Qt.UserRole)
        head_flips.append(head_desc != head_asc)
    check(all(head_flips), '名称/DPS/ΔDPS/Δ% 四列均可排序',
          f'各列降序/升序首行不同：{head_flips}')

    table.sortByColumn(3, Qt.DescendingOrder)
    top_desc = float(model.index(0, 3).data(Qt.DisplayRole))
    low_desc = float(model.index(model.rowCount() - 1, 3).data(Qt.DisplayRole))
    table.sortByColumn(3, Qt.AscendingOrder)
    top_asc = float(model.index(0, 3).data(Qt.DisplayRole))
    check(top_desc > low_desc and abs(low_desc - top_asc) < 1e-6, 'ΔDPS 按数值排序（非字符串）',
          f'降序 {top_desc:+.1f} … {low_desc:+.1f}；升序首行 {top_asc:+.1f}')

    # 5) 排序表双击 → 加入构建
    n0 = len(win.profile.assembled)
    table.doubleClicked.emit(ac.proxy.index(0, 0))
    n1 = len(win.profile.assembled)
    check(n1 == n0 + 1, '候选排序表双击加入构建', f'{n0} → {n1} 项')
    ac.assembled_list.setCurrentRow(n1 - 1)
    ac._remove_selected()

    # 6) 导入入口的临时态：读盘中/命中节流要显式改文案并禁用，结束后回到指纹结论
    #    （不真跑导入：那会弹模态框、在非交互环境挂住；这里只验状态机本身）
    win._set_import_busy(True, '请稍候…')
    busy_text = win._import_action.text()
    busy_ok = not win._import_action.isEnabled() and '请稍候' in busy_text
    win._set_import_busy(False)
    restored = (win._import_action.isEnabled() == win._fingerprint_ok
                and win._import_action.text().startswith('从运行中的游戏导入（只读）…'))
    check(busy_ok and restored, '导入入口临时态（读盘中/节流等待：禁用 + 文案，结束恢复）',
          f'临时态={busy_ok}（「{busy_text}」）；恢复={restored}'
          f'（指纹通过={win._fingerprint_ok}）')

    # 7) 浮层提示：级别进属性（QSS 据此着色）、文本即时生效、贴底且不占满宽度、可立即收起
    toast = win.toast
    toast.notify('测试提示', 'warn', 500)
    anchored = (toast.y() + toast.height() <= win.height()
                and toast.width() < win.width())
    shown = (toast.isVisible() and toast.text() == '测试提示'
             and toast.property('level') == 'warn' and anchored)
    geo = toast.geometry().getRect()
    toast.clear()
    check(shown and not toast.isVisible(), '浮层提示（级别属性 + 贴底定位 + 即时收起）',
          f'可见={shown}；level={toast.level()}；rect={geo}；收起={not toast.isVisible()}')

    _ac_mod.confirm_delete = saved_confirm
    return all(results)


# --------------------------------------------------------------------------- #
# 对拍基准：用引擎公开 API 直算 demo 场景（独立于 GUI 服务层的一条路径）
# --------------------------------------------------------------------------- #
def _demo_direct() -> dict:
    from deskrawl_calc import (DamageType, GameData, Modifier, ModifierType, StatSheet,
                               StatType, Target, Weapon, compare_weapons)

    gd = GameData()
    base = StatSheet({StatType.WeaponDamage: 0})
    base.add_mods(gd.gem_modifiers('GemAmethyst3', equip_category=2))
    base.add_mods(gd.rune_modifiers('HunterSetRune1_4', rune_level=3))
    base.add_mods(gd.talent_modifiers('HunterTalent19', points=5))
    base.add_mods(gd.paragon_modifiers({4: 50}))          # 4 = CritChance
    current = Weapon('旧武器·双手剑', base_damage=100, base_speed=1.0,
                     modifiers=[Modifier(StatType.DamagePhysical, ModifierType.Flat, 0.50)])
    candidate = Weapon('新武器·战斧', base_damage=110, base_speed=0.95,
                       modifiers=[Modifier(StatType.DamagePhysical, ModifierType.Flat, 0.30),
                                  Modifier(StatType.CritDamage, ModifierType.Flat, 0.20),
                                  Modifier(StatType.DamageVsElite, ModifierType.Flat, 0.25)])
    target = Target(level=70, elite=True, hp_fraction=1.0, vulnerable=True)
    r = compare_weapons(base, current, candidate, target=target, damage_type=DamageType.Physical)
    return {'current_dps': r['current']['dps'], 'candidate_dps': r['candidate']['dps'],
            'delta': r['delta'], 'delta_pct': r['delta_pct']}


def kernel_selftest_result() -> tuple:
    """跑内核自检，返回 (是否全通过, PASS 数, FAIL 数, 原始输出)。

    透传而非改写内核结论；PASS/FAIL 数量取自真实打印，不写死。
    GUI 的「运行内核自检」菜单也复用本函数。
    """
    from deskrawl_calc.cli import selftest

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ok = selftest()
    text = buf.getvalue()
    passes, fails = text.count('[PASS]'), text.count('[FAIL]')
    return bool(ok) and fails == 0, passes, fails, text


def _print_kernel_selftest() -> bool:
    ok, passes, fails, text = kernel_selftest_result()
    print(text, end='')
    print(f'内核自检：{passes} PASS / {fails} FAIL')
    return ok


def _engine_ok(rep: Report):
    """GUI 服务层复算 vs 引擎直算，并对照锚点。"""
    from deskrawl_calc import GameData

    from .core import calc_service
    from .core.profile import CharacterProfile

    gd = GameData()
    svc = calc_service.compare(CharacterProfile.demo(), gd)
    direct = _demo_direct()
    print('  --- demo 场景对拍（目标：70 级精英·满血·易伤）---')
    print(f'  直算值：旧 ={direct["current_dps"]:9.4f}  新 ={direct["candidate_dps"]:9.4f}  '
          f'Δ ={direct["delta"]:+8.4f}  Δ% ={direct["delta_pct"]:+7.4f}%')
    print(f'  服务值：旧 ={svc.current_dps:9.4f}  新 ={svc.candidate_dps:9.4f}  '
          f'Δ ={svc.delta:+8.4f}  Δ% ={svc.delta_pct:+7.4f}%')
    errs = [_rel_pct(svc.current_dps, direct['current_dps']),
            _rel_pct(svc.candidate_dps, direct['candidate_dps']),
            _rel_pct(svc.delta_pct, direct['delta_pct'])]
    rep.add(max(errs) < TOL_PCT, 'engine-ok（服务值 ↔ 直算值）',
            f'最大相对误差 {max(errs):.4f}%')
    anchor_errs = [_rel_pct(svc.current_dps, ANCHORS['current_dps']),
                   _rel_pct(svc.candidate_dps, ANCHORS['candidate_dps']),
                   _rel_pct(svc.delta_pct, ANCHORS['delta_pct'])]
    rep.add(max(anchor_errs) < TOL_PCT, '锚点（服务值 ↔ 197.9/226.3/+14.32%）',
            f'最大相对误差 {max(anchor_errs):.4f}%')
    _dps_meter_formula_check(rep)


# DPS 计显示值锚点（2026-10-10 活体实测 PID 12620：与游戏画面「23M」同源，随内存链冻结）
_METER_ANCHOR = {'total': 28114469480.0, 'start_time': 35484.5314386267,
                 'last_tick': 36710.330834729306, 'dps': 22934519.0}


def _dps_meter_formula_check(rep: Report):
    """DPS 计复算公式（hww() 同式）对照活体实测锚点：纯函数，headless 可验。"""
    from .core.dps_meter import meter_dps

    a = _METER_ANCHOR
    got = meter_dps(a['total'], a['start_time'], a['last_tick'])
    rep.add(_rel_pct(got, a['dps']) < TOL_PCT, 'DPS 计复算公式（hww 同式 ↔ 活体 23M 锚点）',
            f'{got:.0f}（期望 {a["dps"]:.0f}，误差 {_rel_pct(got, a["dps"]):.4f}%）')


def _set_cand_affix(profile, stat, value):
    """把候选武器上某属性的词条值设为 value；不存在则追加。"""
    for row in profile.weapon_candidate.affixes:
        if int(row[0]) == int(stat):
            row[2] = float(value)
            return
    profile.weapon_candidate.affixes.append([int(stat), 0, float(value)])


def _name_resolution_checks(rep: Report):
    """T9：导入态下装备名查不到必须显式告警（手工态不告警）——防传奇特效静默丢失。

    缺陷背景：`item_internal_name` 查不到时原样返回（回落而非报错），于是「名字不对」与
    「这件本就没有传奇特效」在下游无法区分，特效会静默消失且 Δ 照常变化。本检查把
    「导入模式下必须告警」与「手工名字不打扰」两侧都固化下来（含 GUI 输入框的同源判定）。
    """
    from deskrawl_calc import GameData

    from .core import calc_service
    from .core.profile import CharacterProfile

    gd = GameData()
    bad_name = '不存在的武器XYZ'
    imported = CharacterProfile.demo()
    imported.import_mode = 'beta'
    imported.weapon_candidate.name = bad_name
    imp_warns = calc_service.compare(imported, gd).warnings
    hit = any('未在游戏装备表命中' in w for w in imp_warns)

    manual = CharacterProfile.demo()
    manual.weapon_candidate.name = bad_name
    quiet = not any('未在游戏装备表命中' in w for w in calc_service.compare(manual, gd).warnings)

    # 正常可解析的名字不得告警（本地化表 → 内部名反查成功）
    ok_name = calc_service.name_known(gd, '苦痛锯齿巨剑')
    bad_resolves = not calc_service.name_known(gd, bad_name)
    rep.add(hit and quiet and ok_name and bad_resolves,
            '导入态装备名查不到 → 显式告警；手工名不打扰',
            f'导入告警={hit}；手工静默={quiet}；可解析名={ok_name}；不可解析名判定={bad_resolves}')
    if hit:
        print(f'    告警样例：{imp_warns[0]}')


def _equipment_checks(rep: Report):
    """T3：3 项输入敏感性的变化方向 + 候选暴伤符号反向验证。

    全部在 demo 的深拷贝上做，基线 profile 不被污染（等价于「改完再还原」）。
    """
    import copy

    from deskrawl_calc import GameData, StatType

    from .core import calc_service
    from .core.profile import CharacterProfile

    gd = GameData()
    base = CharacterProfile.demo()
    ref = calc_service.compare(base, gd)

    def pct_of(mutate):
        prof = copy.deepcopy(base)
        mutate(prof)
        return calc_service.compare(prof, gd).delta_pct

    print('  --- 输入敏感性（Δ% 变化方向须与手算一致）---')
    cases = [
        ('当前武器基础伤害 100→120', lambda p: setattr(p.weapon_current, 'base_damage', 120.0), 'down'),
        ('候选武器基础伤害 110→130', lambda p: setattr(p.weapon_candidate, 'base_damage', 130.0), 'up'),
        ('候选暴伤词条 +0.20→+0.40',
         lambda p: _set_cand_affix(p, StatType.CritDamage, 0.40), 'up'),
    ]
    for label, mutate, expect in cases:
        pct = pct_of(mutate)
        moved = 'up' if pct > ref.delta_pct else ('down' if pct < ref.delta_pct else 'flat')
        rep.add(moved == expect, f'敏感性：{label}',
                f'Δ% {ref.delta_pct:+.2f}% → {pct:+.2f}%（应 {expect}，实测 {moved}）')

    print('  --- 反向验证：候选武器暴伤词条符号改错 ---')
    neg = copy.deepcopy(base)
    _set_cand_affix(neg, StatType.CritDamage, -0.20)
    neg_res = calc_service.compare(neg, gd)
    rep.add(neg_res.candidate_dps < ref.candidate_dps and neg_res.delta_pct < ref.delta_pct,
            '暴伤 +0.20→-0.20：候选 DPS 与 Δ% 均反向下降',
            f'候选 DPS {ref.candidate_dps:.1f} → {neg_res.candidate_dps:.1f}；'
            f'Δ% {ref.delta_pct:+.2f}% → {neg_res.delta_pct:+.2f}%')


def _rank_checks(rep: Report):
    """T4：四类排序行数 + 3 个候选（宝石/符文/天赋各一）与引擎直算对拍。

    对拍走独立路径：把候选词条挂到当前武器上，用 compare_weapons 直算 Δ；
    排序接口走的是 DamageModel.dps，两条路径必须给出同一个 Δ。
    """
    from deskrawl_calc import GameData, Weapon, compare_weapons

    from .core import calc_service
    from .core.profile import KIND_LABELS, CharacterProfile

    gd = GameData()
    profile = CharacterProfile.demo()
    expected = {'gem': 36, 'rune': 199, 'talent': 186, 'runeset': 13}
    params = {'gem': (1, 2), 'rune': (3, 2), 'talent': (5, 2), 'runeset': (2, 2)}

    def manual(kind, name, level, category):
        w = profile.weapon_current.to_weapon()
        mods = calc_service.candidate_modifiers(gd, kind, name, level=level, category=category)
        w2 = Weapon(w.name, w.base_damage, w.base_speed,
                    list(w.modifiers) + list(mods), w.skill_multiplier)
        r = compare_weapons(profile.to_sheet(gd), w, w2, target=profile.to_target(),
                            damage_type=profile.damage_type)
        return r['delta'], r['candidate']['dps']

    print(f'  --- 排序：基线 DPS（当前构建不含候选）= '
          f'{calc_service.baseline_dps(profile, gd):.4f} ---')
    tables = {}
    for kind, exp in expected.items():
        level, category = params[kind]
        rows = calc_service.rank_candidates(profile, gd, kind, level=level, category=category)
        tables[kind] = rows
        data_n = len(calc_service.candidate_names(gd, kind))
        rep.add(len(rows) == exp == data_n, f'排序行数：{KIND_LABELS[kind]}',
                f'{len(rows)} 行（期望 {exp}，类别数据量 {data_n}）')

    print('  --- 3 候选 Δ 对拍（排序接口 vs 引擎 compare_weapons 直算）---')
    for kind in ('gem', 'rune', 'talent'):
        level, category = params[kind]
        top = max(tables[kind], key=lambda r: abs(r.delta))
        m_delta, m_dps = manual(kind, top.name, level, category)
        errs = [_rel_pct(top.delta, m_delta), _rel_pct(top.dps, m_dps)]
        rep.add(max(errs) < TOL_PCT, f'候选对拍：{KIND_LABELS[kind]} {top.name}',
                f'Δ {top.delta:+.4f} vs {m_delta:+.4f}，DPS {top.dps:.4f} vs {m_dps:.4f}'
                f'（最大相对误差 {max(errs):.4f}%）')


def _build_roundtrip(rep: Report):
    """T5：构建存/取 JSON 往返一致（含派生属性表逐项一致）。

    落盘用系统临时目录：data/ 是本任务边界上的只读区，自检不应把仓库工作区写脏
    （断言与检查名不变，仅换落盘位置）。
    """
    import os
    import tempfile

    from deskrawl_calc import GameData, StatType

    from .core import calc_service
    from .core.item_draft import ItemDraft
    from .core.profile import CharacterProfile, load_build, save_build

    gd = GameData()
    source = CharacterProfile.demo()
    # 空槽草稿（「切槽看一眼」留下的空壳）必须被序列化剔除：否则它随会话状态与构建存档落盘，
    # 下次载入就带着幻影条目回来。有内容的槽则必须原样保留（过滤不能误伤）。
    source.slot_current[9] = ItemDraft()
    source.slot_candidate[3] = ItemDraft(name='测试件', affixes=[[23, 0, 0.5]])
    d0 = source.to_dict()
    dropped_empty = '9' not in d0['slot_current'] and '3' in d0['slot_candidate']

    path = os.path.join(tempfile.gettempdir(), 'deskrawl_selftest_roundtrip.json')
    save_build(source, path)
    restored = load_build(path)

    same_dict = source.to_dict() == restored.to_dict()
    sheet_a, sheet_b = source.to_sheet(gd), restored.to_sheet(gd)
    finals = [abs(sheet_a.final(st) - sheet_b.final(st)) for st in StatType]
    same_sheet = max(finals) < 1e-12
    res_a, res_b = calc_service.compare(source, gd), calc_service.compare(restored, gd)
    same_dps = (abs(res_a.current_dps - res_b.current_dps) < 1e-9
                and abs(res_a.candidate_dps - res_b.candidate_dps) < 1e-9)

    rep.add(same_dict and same_sheet and same_dps and dropped_empty, '构建存取往返一致',
            f'{os.path.basename(path)}（系统临时目录）；JSON 等值={same_dict}，'
            f'属性表最大偏差={max(finals):.2e}，DPS 等值={same_dps}，'
            f'空槽草稿已剔除={dropped_empty}')




def _error_map_check(rep: Report):
    """T7：六类错误态 → 中文文案映射（假异常触发，不依赖活游戏与实际权限）。"""
    from .app import describe_import_error
    from .core.memory_import import MemoryImportError

    cases = [
        ('游戏未运行', MemoryImportError('未找到 Deskrawl.exe 进程——请先启动游戏并进入角色',
                                          'env', code='no_process'), ('未运行', '启动')),
        ('已运行未加载角色', MemoryImportError('GameManager/Inventory/Storage 单例未定位'
                                               '（角色未加载或版本漂移）', 'env', code='no_hero'),
         ('角色', '未加载')),
        ('权限不足', MemoryImportError('打开游戏进程失败：OpenProcess 被拒绝（err=5）',
                                       'env', code='denied'), ('管理员',)),
        ('32 位解释器', MemoryImportError('当前 Python 为 32 位', 'env', code='py32'),
         ('64 位',)),
        ('版本指纹不符', MemoryImportError('版本指纹不符：GameAssembly.dll 指纹不符',
                                           'version', code='fingerprint'), ('指纹', 'schema')),
        ('读取校验失败', MemoryImportError('双读一致性校验失败：连续读取内容不一致', 'data'),
         ('重试',)),
    ]
    ok_all, detail = True, []
    for label, exc, keys in cases:
        title, text = describe_import_error(exc)
        hit = all(k in title or k in text for k in keys)
        ok_all = ok_all and hit
        detail.append(f'{label}={"PASS" if hit else "FAIL"}')
    rep.add(ok_all, '错误映射 6 场景（假异常 → 中文文案）', '；'.join(detail))
    print(f'    弹窗文案示例：{describe_import_error(cases[0][1])[1].splitlines()[0]}')


def _session_state_checks(rep: Report):
    """T8：会话状态落盘服务层（往返一致 + 损坏/版本不符回落），临时目录，不碰真实状态。"""
    import tempfile

    from .core import session_state

    tmp = os.path.join(tempfile.mkdtemp(prefix='deskrawl_state_'), 'state.json')
    payload = {'version': session_state.STATE_VERSION,
               'window': {'geometry': 'QUJD', 'page': 2},
               'profile': {'name': '往返', 'level': 70}}
    saved = session_state.save_state(payload, path=tmp)
    roundtrip = saved == tmp and session_state.load_state(path=tmp) == payload
    no_tmp = not os.path.exists(tmp + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write('{ broken json')
    broken = session_state.load_state(path=tmp) == {}
    session_state.save_state(dict(payload, version=999), path=tmp)
    stale = session_state.load_state(path=tmp) == {}
    rep.add(roundtrip and no_tmp and broken and stale,
            '会话状态落盘（往返一致 + 原子写 + 损坏/版本不符回落）',
            f'往返={roundtrip}；无 .tmp 残留={no_tmp}；损坏文件回落={broken}；'
            f'版本不符回落={stale}；文件={tmp}')


def _format_checks(rep: Report):
    """数值显示口径：≤3 位小数、去尾零、无贡献层给 —。改格式函数必须同步改这里。"""
    from .core.format import NO_INFO, fmt_layer, fmt_qty

    cases = [(355.35, '355.35'), (1.299, '1.299'), (100.0, '100'), (0.0, '0'), (-0.0001, '0')]
    bad = [(v, fmt_qty(v), want) for v, want in cases if fmt_qty(v) != want]
    layers = (fmt_layer(1.0, identity=1) == NO_INFO, fmt_layer(0.0, identity=0) == NO_INFO,
              fmt_layer(0.75, identity=0) == '0.75')
    rep.add(not bad and all(layers), '数值显示口径（≤3 位小数 · 去尾零 · 无贡献层显示 —）',
            f'样本 {len(cases)} 个，失配 {len(bad)}；分层占位 {sum(layers)}/3')


def _table_model_checks(rep: Report):
    """表格模型层的纯逻辑断言（不需要 QApplication）：Δ% 三态阈值与显示格式。

    为什么单独测：渲染是否正确要看图，但「多大算中性、显示几位」是纯规则——把它钉在
    --selftest 里，改阈值时不必等到有人肉眼发现颜色不对。
    """
    from PySide6.QtCore import Qt

    from .core.skill_service import SkillRow
    from .widgets.compare_view import _FLAT_DELTA_PCT, _SkillModel

    def row(pct):
        return SkillRow(name='x', ability_name='旋风斩', level_req=10, current_dps=100.0,
                        candidate_dps=100.0 * (1 + pct / 100.0), delta=1.0, delta_pct=pct,
                        hits_per_sec=1.0, interval=1.0)

    model = _SkillModel()
    model.set_rows([row(0.0), row(_FLAT_DELTA_PCT * 0.5), row(-1.5), row(3.25)])
    trends = [model.trend(i) for i in range(model.rowCount())]
    texts = [model.data(model.index(i, 3), Qt.DisplayRole) for i in range(model.rowCount())]
    rep.add(trends == ['flat', 'flat', 'down', 'up'] and texts[3] == '+3.25%',
            '技能表模型：Δ% 三态阈值与格式（|Δ%|<0.005 归中性）',
            f'trend={trends}；Δ%={texts}')


def run_selftest() -> int:
    rep = Report()
    if not _print_kernel_selftest():
        print('内核自检未通过，终止。', file=sys.stderr)
        return 1
    _engine_ok(rep)
    _equipment_checks(rep)
    _name_resolution_checks(rep)
    _rank_checks(rep)
    _build_roundtrip(rep)
    # 夹具/面板口径检查已拆到 selftest_fixture（延迟导入：该模块反向引用本模块的 Report）
    from .selftest_effects import _health_condition_checks
    from .selftest_fixture import _legendary_effect_checks, _panel_checks, _snapshot_checks
    from .selftest_legendary import _legendary_checks
    from .selftest_skillmods import _talent_crit_checks, _talent_mod_checks
    _snapshot_checks(rep)
    _panel_checks(rep)
    _legendary_effect_checks(rep)
    _error_map_check(rep)
    _session_state_checks(rep)
    _format_checks(rep)
    _table_model_checks(rep)
    _legendary_checks(rep)
    _talent_mod_checks(rep)
    _talent_crit_checks(rep)
    _health_condition_checks(rep)
    print(f'\n自检结果：{"全部通过" if rep.ok() else "存在失败"}'
          f'（{rep.passed}/{len(rep.checks)}）')
    return 0 if rep.ok() else 1
