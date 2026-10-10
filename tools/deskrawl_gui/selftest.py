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
import sys

# demo 场景锚点（2026-10-07 实测，随内核一起冻结）
ANCHORS = {'current_dps': 197.9, 'candidate_dps': 226.3, 'delta_pct': 14.32}
TOL_PCT = 0.5


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
    # 导入项可用性必须与指纹自检结果一致（一致性断言，任何环境都可判定）
    import_state_ok = (import_action is not None and import_action.isEnabled() == win._fingerprint_ok)
    print(f'[smoke] 菜单：{menu_titles}')
    print(f'[smoke] 工具→内核自检：{"已就绪" if kernel_action and kernel_action.isEnabled() else "缺失"}；'
          f'数据导入{"已就绪（指纹通过）" if win._fingerprint_ok else "已禁用（指纹不符，中文提示已就位）"}，'
          f'可用性一致={import_state_ok}')
    ok, summary, _ = win._kernel_selftest_message()
    print(f'[smoke] 内核自检弹窗文案：{summary}（通过={ok}）')

    print('[smoke] 交互检查：')
    behavior_ok = _gui_behavior_checks(win)

    if count <= 0:
        print('[smoke] 失败：widget 计数为 0', file=sys.stderr)
        return 1
    if kernel_action is None or not kernel_action.isEnabled() or not import_state_ok or not ok:
        print('[smoke] 失败：菜单/自检弹窗校验未通过', file=sys.stderr)
        return 1
    if not behavior_ok:
        print('[smoke] 失败：交互检查未通过', file=sys.stderr)
        return 1
    return 0


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

    def check(cond, label, detail=''):
        results.append(bool(cond))
        print(f'  [{"PASS" if cond else "FAIL"}] {label}' + (f'：{detail}' if detail else ''))

    def stat_final(name):
        table = win.stat_table.table
        for r in range(table.rowCount()):
            if table.item(r, 0).text() == name:
                return float(table.item(r, 5).text())
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

    # 1b) 类型由属性自动决定且不可改：全部属性锁「加法」，百分比类属性附小数填写提示
    saved = copy.deepcopy(editor.draft.affixes)
    editor.affixes.append_row()
    r = editor.affixes.rowCount() - 1
    s_combo = editor.affixes.cellWidget(r, 0)
    t_combo = editor.affixes.cellWidget(r, 1)
    v_spin = editor.affixes.cellWidget(r, 2)

    def locked():
        return (not t_combo.isEnabled() and t_combo.count() == 1
                and int(t_combo.currentData()) == 0)

    pct_ok = locked() and '小数' in t_combo.toolTip() and '小数' in v_spin.toolTip()
    s_combo.setCurrentIndex(s_combo.findData(int(StatType.Strength)))
    num_ok = locked() and '加法' in t_combo.toolTip()
    check(pct_ok and num_ok, '词条类型自动决定且不可改（全部锁加法）',
          f'物理伤害%：锁加法+小数提示={pct_ok}；力量：锁加法={num_ok}')
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
    expected = {'gem': 36, 'rune': 151, 'talent': 186, 'runeset': 13}
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
    from .core.profile import CharacterProfile, load_build, save_build

    gd = GameData()
    source = CharacterProfile.demo()
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

    rep.add(same_dict and same_sheet and same_dps, '构建存取往返一致',
            f'{os.path.basename(path)}（系统临时目录）；JSON 等值={same_dict}，'
            f'属性表最大偏差={max(finals):.2e}，DPS 等值={same_dps}')


# --------------------------------------------------------------------------- #
# 内存导入夹具自检（任务书：β=memdump --json 原样输出；α=β 去掉 equipment 的变体）
# --------------------------------------------------------------------------- #
_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')

# 由「装备词条 + 孔位宝石」即可完全解释的键位（2026-10-08 对拍逐键核定，残差 0）。
# 它是反向验证的抓手：这些键位不依赖 nsq 就能独立复算，改坏夹具必须变红。
_DERIVED_EXACT_KEYS = (0, 4, 11, 13, 14, 15, 16, 17, 22, 23, 29, 31, 36, 38, 40, 42, 44, 51, 52, 53, 65)

# 孔位宝石加成组（与 core/profile._gem_category 同一实测锚定：武器 2 / 饰品 1 / 护甲 0）
_GEM_CAT = {1: 2, 7: 1, 8: 1}


def _load_fixture(name: str) -> dict:
    with open(os.path.join(_FIXTURES, name), encoding='utf-8') as f:
        return json.load(f)


def _derived_flat(payload: dict, gd) -> dict:
    """从夹具「装备词条 + 孔位宝石静态加成」独立复算各键位合计（刻意不读 nsq 面板）。"""
    out = {}
    for rec in payload.get('equipment') or []:
        for s, _t, v in (rec.get('modifiers') or []):
            out[int(s)] = out.get(int(s), 0.0) + float(v)
        cat = _GEM_CAT.get(int(rec.get('equip_slot_type', 0)), 0)
        for gname in (rec.get('socketed_gems') or []):
            for m in gd.gem_modifiers(str(gname), cat):
                out[int(m.stat)] = out.get(int(m.stat), 0.0) + float(m.value)
    return out


def _snapshot_checks(rep: Report):
    """T6：内存导入夹具自检（headless，不依赖活游戏）。

    检查分工：装配链对拍验证「面板闭环（误差 0）」；装备派生对拍用不依赖 nsq 的独立复算
    验证 β 分解真实落地（反向验证「改坏夹具必须变红」的抓手）；α 侧覆盖候选排序与 UI
    的「近似」标注、装备对比降级。残差键位的成因记录见 PROGRESS（非阻塞）。
    """
    import copy

    from deskrawl_calc import GameData, stat_name

    from .core import calc_service
    from .core.profile import CharacterProfile

    gd = GameData()
    beta = _load_fixture('snapshot_beta.json')
    nsq = {int(k): float(v) for k, v in beta['player']['base'].items()}
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from .widgets.assembly_center import AssemblyCenter
    from .widgets.equipment_editor import EquipmentEditor

    # 本函数的 UI 检查要先于 α 段构造控件，QApplication 必须最先就位（QWidget 硬前置）
    app = QApplication.instance() or QApplication(['deskrawl_gui', '--selftest'])

    prof = CharacterProfile.from_snapshot(beta, gd)
    sheet = prof.to_sheet(gd)
    sheet.add_mods(prof.weapon_current.to_weapon().modifiers)
    # 期望 = 面板行 final（基座已改用 build_panel 面板口径：nsq 只是平坦层，用它比对会让
    # 暴伤/暴击率/物理% 等少读，见 profile._panel_finals 的实测记录）
    prow = {int(r[0]): float(r[5]) for r in calc_service.build_panel(beta)['rows']
            if r[5] is not None}
    expect = {st: prow.get(st, v) for st, v in nsq.items()}
    bad = [st for st, v in sorted(expect.items()) if sheet.final(st) != v]
    rep.add(not bad, 'β 夹具 装配链 Final ≡ 口径期望（主属性=面板 451，其余逐键 ≡ nsq）',
            f'{len(expect)} 键逐位比对，失配 {len(bad)}；主属性 {stat_name(prof.primary_stat)} '
            f'= {sheet.final(prof.primary_stat):.0f}（面板 {float(prow[5]):.0f}）；'
            f'模式={prof.import_mode}，宝石 {len(prof.assembled)} 颗')

    # 主属性伤害加成（Player.CalcDamage@0x50E400）：DPS 的攻击伤害 = (武器伤害 + 通用增伤) ×(1+Final/100)
    fac = calc_service.compare(prof, gd).current_model.primary_stat_multiplier()
    rep.add(abs(fac - 5.51) < 1e-9, 'β 主属性伤害加成 = ×5.510（力量 451，游戏 tooltip 同源）',
            f'主属性={stat_name(prof.primary_stat)}；因子 ×{fac:.4f}')
    prof_up = copy.deepcopy(prof)
    prof_up.weapon_current.affixes = list(prof_up.weapon_current.affixes) + [[0, 0, 100.0]]
    d0 = calc_service.baseline_dps(prof, gd)
    d1 = calc_service.baseline_dps(prof_up, gd)
    rep.add(_rel_pct(d1 / d0, 6.51 / 5.51) < 1e-6,
            '力量词条 +100 → DPS 按 ×(1+力量/100) 等比上升（451→551）',
            f'DPS {d0:.2f} → {d1:.2f}（比值 {d1 / d0:.6f}，期望 {6.51 / 5.51:.6f}）')

    wrec = next(r for r in beta['equipment'] if int(r['slot']) == 0)
    want_raw = [[int(s), int(t), float(v)] for s, t, v in wrec['modifiers']]
    got = [[int(s), int(t), float(v)] for s, t, v in prof.weapon_current.affixes]
    by = {int(s): float(v) for s, _t, v in got}
    upg = int(wrec.get('upgrade_level') or 0)
    upg_ok = (prof.weapon_current.name == wrec['name'] and got != want_raw
              and by.get(20) == nsq[20] and by.get(21) == nsq[21]
              and prof.weapon_current.upgrade_level == upg
              and prof.weapon_current.gems == [str(g) for g in (wrec.get('socketed_gems') or [])])
    rep.add(upg_ok, 'β 夹具 武器词条=强化后口径（nsq 单源覆写 + 模型折算 + 宝石元数据）',
            f'{prof.weapon_current.name} +{upg}：{len(got)} 条（原值 {len(want_raw)} 条）；'
            f'武器伤害={by.get(20):.4f}（面板 {nsq[20]:.4f}）、攻速={by.get(21):.4f}；'
            f'宝石 {len(prof.weapon_current.gems)} 颗')

    bag = prof.bag_items
    bag_ok = bool(bag) and all(
        isinstance(rec.get('affixes'), list) and rec.get('source') in ('背包', '仓库')
        for rec in bag)
    names = [rec['name'] for rec in bag]
    rep.add(bag_ok, 'β 夹具 背包/仓库装备候选（bag_items）',
            f'{len(bag)} 件：{names[:4]}{"…" if len(names) > 4 else ""}')

    # 候选下拉行为：武器槽下拉只列武器 → 选中第一件武器即整件载入候选草稿（引用不变）
    weapon_bag = [r for r in bag if int(r.get('equip_slot_type') or 0) == 1]
    if weapon_bag:
        eqb = EquipmentEditor(prof, gd)
        eqb.bag_combo.setCurrentIndex(1)
        d = prof.weapon_candidate
        sel = weapon_bag[0]
        loaded = (d.name == sel['name'] and d.base_damage == 0.0
                  and [list(a) for a in d.affixes] == [list(a) for a in sel['affixes']]
                  and d.upgrade_level == sel['upgrade_level'] and d.gems == sel['gems'])
        # 元信息行显隐必须与内容一致：有强化或宝石才显示（仓库 +0 无宝石武器 → 隐藏）
        want_meta = bool(sel.get('upgrade_level') or sel.get('gems'))
        meta_ok = (not eqb.candidate_editor.meta_label.isHidden()) == want_meta
        rep.add(loaded and meta_ok,
                '候选下拉载入背包装备（整件载入 + 元信息行显隐一致）',
                f'候选={d.name}（{len(d.affixes)} 条词条，强化 +{d.upgrade_level}，'
                f'宝石 {len(d.gems)}）；元信息行显示={want_meta}')

    # 非武器槽对比：候选=当前件 → Δ=0；给候选加词条 → DPS 上升（方向 + 基线一致性）
    _slot_checks(rep, prof, gd)

    # 技能秒伤对比：职业（Barbarian=1）的伤害技能逐行，当前↔候选与引擎直算口径一致
    _skill_checks(rep, prof, gd)

    # 技能频次：引导按 tick 计命中；ChannelSpeed/StrikeCount 天赋放大命中次数
    _skill_freq_checks(rep, prof, gd)

    # 武器卡片元信息：强化 +N 与镶嵌宝石只读展示（β 当前武器 = +4 / 3 颗）
    eqc = EquipmentEditor(prof, gd)
    meta = eqc.current_editor.meta_label.text()
    rep.add('强化 +4' in meta and 'GemDiamond5' in meta,
            '武器卡片元信息行（强化 +N / 镶嵌宝石）',
            f'文本：{meta[:60]}…')

    derived = _derived_flat(beta, gd)
    exact_bad = [st for st in _DERIVED_EXACT_KEYS if nsq[st] != derived.get(st, 0.0)]
    floor_bad = [st for st in nsq if nsq[st] < derived.get(st, 0.0)]
    rep.add(not exact_bad and not floor_bad, 'β 夹具 装备派生对拍（独立复算，不读 nsq）',
            f'可完全派生 {len(_DERIVED_EXACT_KEYS)} 键逐位相等={not exact_bad}；'
            f'{len(nsq)} 键派生下限全成立={not floor_bad}'
            f'（其余 {len(nsq) - len(_DERIVED_EXACT_KEYS)} 键残差并入 base，成因见 PROGRESS）')

    alpha = _load_fixture('snapshot_alpha.json')
    prof_a = CharacterProfile.from_snapshot(alpha, gd)
    rows = calc_service.rank_candidates(prof_a, gd, 'gem', level=1, category=2)
    base_dps = calc_service.baseline_dps(prof_a, gd)

    view = AssemblyCenter(prof_a, gd)
    ti = next(i for i in range(view.kind_combo.count())
              if view.kind_combo.itemData(i) == 'talent')
    view.kind_combo.setCurrentIndex(ti)     # 天赋池含百分比加算词条，用于验证「近似」标注
    marked = any('近似' in (view.model.data(view.model.index(r, 1), Qt.DisplayRole) or '')
                 for r in range(view.model.rowCount()))
    hint_ok = '近似' in view.hint.text()
    eq = EquipmentEditor(prof_a, gd)
    current_off = not eq.current_editor.isEnabled()
    rep.add(prof_a.import_mode == 'alpha' and len(rows) > 0 and base_dps > 0
            and marked and hint_ok and current_off and ('降级' in eq.alpha_banner.text()),
            'α 夹具 候选排序 + 近似标注 + 对比降级',
            f'宝石候选 {len(rows)} 条；基线 DPS={base_dps:.1f}；行「近似」标注={marked}；'
            f'视图提示={hint_ok}；当前武器禁用={current_off}')
    assert app is not None


def _slot_checks(rep: Report, prof, gd):
    """非武器槽对比自检：候选=当前件 → Δ=0；给候选加词条 → DPS 上升。

    验证「卸下当前件 → 两侧分别装回」的对称路径：当前侧必须恒等于基线，只有候选产生 Δ。
    """
    import copy

    from deskrawl_calc import StatType

    from .core import calc_service

    slot = next((s for s in sorted(prof.slot_current) if prof.slot_current[s].affixes), None)
    if slot is None:
        rep.add(False, '非武器槽对比（β 夹具）', '夹具无带词条的非武器槽')
        return
    prof2 = copy.deepcopy(prof)
    prof2.slot_candidate[slot] = copy.deepcopy(prof2.slot_current[slot])
    r_same = calc_service.compare(prof2, gd, slot=slot)
    same_ok = abs(r_same.delta) < 1e-9 and abs(r_same.delta_pct) < 1e-9
    prof2.slot_candidate[slot].affixes = (list(prof2.slot_candidate[slot].affixes)
                                          + [[int(StatType.DamagePhysical), 0, 0.5]])
    r_up = calc_service.compare(prof2, gd, slot=slot)
    rep.add(same_ok and r_up.delta > 0 and r_up.current_dps == r_same.current_dps,
            f'非武器槽对比（槽 {slot}：候选取当前件 → Δ=0；加词条 → 上升）',
            f'Δ0={r_same.delta_pct:+.3f}%（{r_same.current_dps:.1f} DPS）；'
            f'加 +0.5 物理伤害% 后 Δ={r_up.delta_pct:+.3f}%，'
            f'当前侧不变={r_up.current_dps == r_same.current_dps}')


def _skill_checks(rep: Report, prof, gd):
    """技能秒伤对比自检：逐行非空且 >0，并用引擎直算校验 skill_scaling 合成口径。

    独立路径：手写 (BaseDamage + scaling×(F20+F3))×主属性因子，须与 DamageModel.attack_damage() 逐位一致。
    """
    import copy

    from deskrawl_calc import DamageModel, StatType

    from .core import calc_service, skill_service

    res = calc_service.compare(prof, gd)
    rows = skill_service.skill_rows(prof, gd, res.current_sheet, res.candidate_sheet, res.target)
    # 主力技能选择：显式指定参考技能 → 精确命中该行（循环系数/候选预测的基线口径）
    prof_m = copy.deepcopy(prof)
    prof_m.skill_name = rows[0].name
    picked = skill_service.pick_main_row(rows, prof_m)
    top = max(rows, key=lambda r: r.current_dps)
    pick_ok = picked is not None and picked.name == rows[0].name \
        and skill_service.pick_main_row(rows, prof).name == top.name
    skills = gd.damage_skills(prof.hero_class, prof.skill_level)
    ok = (prof.hero_class == 1 and len(rows) == len(skills) == 10
          and all(r.current_dps > 0 for r in rows))
    sk = next(s for s in skills if s['name'] == 'WarriorHeavyAttack3')   # Whirlwind
    e = sk['effects'][0]
    w = prof.weapon_current.to_weapon()
    sheet = res.current_sheet
    model = DamageModel(sheet, e['damage_type'], weapon_damage=w.base_damage,
                        primary_stat=prof.primary_stat, skill_scaling=e['scaling'])
    f20, f3 = sheet.final(StatType.WeaponDamage), sheet.final(StatType.Damage)
    ps_fac = 1.0 + sheet.final(int(prof.primary_stat)) / 100.0
    manual = (w.base_damage + e['scaling'] * (f20 + f3)) * ps_fac
    eng_ok = abs(model.attack_damage() - manual) < 1e-9
    # 候选侧用候选武器：把候选白字基础伤害上调，主力行候选列必抬、当前列不动
    # （旧版两侧共用 weapon_current，候选换武器的白字/攻速会被漏掉——「预测不动」的根因之一）
    prof_w = copy.deepcopy(prof)
    prof_w.weapon_candidate.base_damage = float(prof_w.weapon_candidate.base_damage) + 100.0
    res_w = calc_service.compare(prof_w, gd)
    rows_w = skill_service.skill_rows(prof_w, gd, res_w.current_sheet, res_w.candidate_sheet,
                                      res_w.target)
    ww_base = next(r for r in rows if r.name == 'WarriorHeavyAttack3')
    ww_up = next(r for r in rows_w if r.name == 'WarriorHeavyAttack3')
    cand_weapon_ok = (ww_up.candidate_dps > ww_base.candidate_dps
                      and ww_up.current_dps == ww_base.current_dps)
    rep.add(ok and eng_ok and pick_ok and cand_weapon_ok,
            f'技能秒伤对比（{len(rows)} 项，Barbarian；skill_scaling 合成口径）',
            f'行数={len(rows)}（期望 {len(skills)}）；示例 {rows[0].ability_name} '
            f'{rows[0].current_dps:.1f} 秒伤；Whirlwind 倍率={e["scaling"]:.3f}，'
            f'攻击伤害 引擎={model.attack_damage():.4f} vs 手算={manual:.4f}，一致={eng_ok}；'
            f'主力技能选择={pick_ok}；候选武器参与（白字+100→候选列 {ww_base.candidate_dps:.0f}'
            f'→{ww_up.candidate_dps:.0f}，当前列不变）={cand_weapon_ok}')


def _skill_freq_checks(rep: Report, prof, gd):
    """技能频次模型：引导按 tick 计命中；通道速度/附加斩击天赋按真值放大命中次数。

    用 β 夹具验证两处真值（与游戏 tooltip 对齐）：
    · 旋风斩（ChannelTickRate=0.32）：无天赋 1/tick 命中/秒；ChannelSpeed +1.0（死神之刃 10/10）→ 翻倍；
    · Rending Onslaught（StaggeredStrikesEffect.TargetCount=3）：基础 3 击；StrikeCount +1（屠夫韵律 1/3）
      → 命中次数 ×4/3（而非 ×2）。
    """
    import copy

    from .core import calc_service, skill_service

    skills = {s['name']: s for s in gd.damage_skills(prof.hero_class, prof.skill_level)}

    def row_for(p, name):
        res = calc_service.compare(p, gd)
        rows = skill_service.skill_rows(p, gd, res.current_sheet, res.candidate_sheet, res.target)
        return next(r for r in rows if r.name == name)

    ww = 'WarriorHeavyAttack3'
    tick = skills[ww]['tick_rate']
    base = row_for(prof, ww)
    tick_ok = abs(base.hits_per_sec - 1.0 / tick) < 1e-9
    p_cs = copy.deepcopy(prof)
    p_cs.ability_mods = {ww: {8: 1.0}}
    cs = row_for(p_cs, ww)
    cs_ok = (abs(cs.hits_per_sec - 2.0 / tick) < 1e-9
             and _rel_pct(cs.current_dps, base.current_dps * 2.0) < 1e-6)

    ro = 'WarriorHeavyAttack4'                            # Rending Onslaught（裂血连击）
    ro_strikes = skills[ro]['strikes']
    ro_base = row_for(prof, ro)
    p_ro = copy.deepcopy(prof)
    p_ro.ability_mods = {ro: {9: 1.0}}                    # 屠夫韵律 +1 次
    ro_up = row_for(p_ro, ro)
    ro_ok = ro_strikes == 3 and _rel_pct(ro_up.hits_per_sec, ro_base.hits_per_sec * 4.0 / 3.0) < 1e-6
    rep.add(tick_ok and cs_ok and ro_ok,
            '技能频次（引导按 tick · 通道速度/附加斩击天赋）',
            f'旋风斩 {base.hits_per_sec:.3f} 命中/秒（tick={tick}）→ 通道速度+100% {cs.hits_per_sec:.3f}；'
            f'裂血连击 基础 {ro_strikes} 击 {ro_base.hits_per_sec:.3f} → +1 次 {ro_up.hits_per_sec:.3f}'
            f'（×{ro_up.hits_per_sec / ro_base.hits_per_sec:.4f}，期望 ×1.3333）')


# 游戏面板口径锚点：2026-10-08 用户实机「属性」页截图逐行转写（文本须逐字一致）
_PANEL_ANCHORS = {
    0: '451', 3: '94', 21: '1.7', 6: '35.7%', 4: '49%', 5: '505%', 23: '287%',
    24: '75%', 25: '75%', 26: '75%', 27: '75%', 28: '75%',
    29: '256.8%', 31: '119.2%', 45: '233.3%', 32: '185.8%', 40: '233.3%', 65: '54.3%',
    7: '5,592', 42: '50.5%', 8: '12,529', 44: '85.9%', 9: '2,660',
}


def _panel_checks(rep: Report):
    """T8：游戏面板口径复算自检（23 行锚点 + 条件表落位 + 反向敏感 + α 一致性）。

    row = [stat, flat, cond, pct, mult, final, text]；锚点比对用 text（面板显示值）。
    反向敏感用「条件值归零必变红」保证锚点检查不是空转（等价于对夹具做算法级破坏）。
    """
    import copy

    from .core import calc_service
    from .core.profile import CharacterProfile

    beta = _load_fixture('snapshot_beta.json')
    panel = calc_service.build_panel(beta)
    by = {r[0]: r for r in panel['rows']}
    bad = [(st, (by[st][6] if st in by else '<缺失>'), want)
           for st, want in _PANEL_ANCHORS.items() if st not in by or by[st][6] != want]
    rep.add(not bad, '面板口径 23 行锚点（↔ 游戏「属性」页截图）',
            f'{len(_PANEL_ANCHORS)} 行文本逐字比对，失配 {len(bad)}'
            + (f'：{bad[:3]}' if bad else '；例：力量 451、护甲 12,529、生命 5,592'))

    r23 = by.get(23, [0] * 7)
    rep.add(abs(r23[2] - 0.75) < 1e-9 and abs(r23[1] - 2.12) < 1e-6 and r23[6] == '287%',
            '条件表落位（Healthy：物伤 = 平坦 2.12 + 条件 +0.75）',
            f'平坦={r23[1]:.4g} 条件={r23[2]:.4g} 最终={r23[6]}；'
            f'血比例={panel["hp_frac"]:.6f}')

    broken = copy.deepcopy(beta)
    for row in broken['player']['conditionals']['nuf']:
        if int(row[2]) == 23:
            row[4] = 0.0
    b2 = {r[0]: r for r in calc_service.build_panel(broken)['rows']}
    rep.add(b2[23][6] == '212%' and r23[6] == '287%',
            '反向敏感：条件值归零 → 物伤 287% → 212%',
            f'完好={r23[6]}，归零={b2[23][6]}')

    alpha = _load_fixture('snapshot_alpha.json')
    pa = calc_service.build_panel(alpha)
    same = pa['rows'] == panel['rows']
    rep.add(same, 'α 夹具 面板口径与 β 逐行一致',
            f'α {len(pa["rows"])} 行 / β {len(panel["rows"])} 行，逐项相等={same}')

    rep.add(CharacterProfile.demo().panel is None, '手工构建无面板数据（属性明细退回计算口径）',
            'demo().panel is None')


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


def run_selftest() -> int:
    rep = Report()
    if not _print_kernel_selftest():
        print('内核自检未通过，终止。', file=sys.stderr)
        return 1
    _engine_ok(rep)
    _equipment_checks(rep)
    _rank_checks(rep)
    _build_roundtrip(rep)
    _snapshot_checks(rep)
    _panel_checks(rep)
    _error_map_check(rep)
    print(f'\n自检结果：{"全部通过" if rep.ok() else "存在失败"}'
          f'（{rep.passed}/{len(rep.checks)}）')
    return 0 if rep.ok() else 1
