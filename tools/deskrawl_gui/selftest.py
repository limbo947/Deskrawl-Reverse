# -*- coding: utf-8 -*-
"""命令行自检。

--smoke    ：实例化主窗口并统计 widget 数，验证骨架在无显示环境下可跑通。
--selftest ：内核公式自检 + GUI 服务层与引擎直算对拍（逐项补齐）。

对拍原则：GUI 侧（CharacterProfile → calc_service）与引擎侧（直接构造 StatSheet/Weapon）
走两条独立路径，比对期望 DPS 与 Δ%，误差阈值 <0.5%。
"""
import contextlib
import io
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
    archive_menu = next((a.menu() for a in win.menuBar().actions() if a.text() == '存档'), None)
    archive_disabled = archive_menu is not None and not any(
        a.isEnabled() for a in archive_menu.actions())
    print(f'[smoke] 菜单：{menu_titles}')
    print(f'[smoke] 工具→内核自检：{"已就绪" if kernel_action and kernel_action.isEnabled() else "缺失"}；'
          f'存档菜单禁用占位：{archive_disabled}')
    ok, summary, _ = win._kernel_selftest_message()
    print(f'[smoke] 内核自检弹窗文案：{summary}（通过={ok}）')

    print('[smoke] 交互检查：')
    behavior_ok = _gui_behavior_checks(win)

    if count <= 0:
        print('[smoke] 失败：widget 计数为 0', file=sys.stderr)
        return 1
    if kernel_action is None or not kernel_action.isEnabled() or not archive_disabled or not ok:
        print('[smoke] 失败：菜单/自检弹窗校验未通过', file=sys.stderr)
        return 1
    if not behavior_ok:
        print('[smoke] 失败：交互检查未通过', file=sys.stderr)
        return 1
    return 0


def _gui_behavior_checks(win) -> bool:
    """在已建好的主窗口上跑一遍关键交互（真实控件 + 真实信号链），headless 可验证。

    覆盖任务书里的交互要求：词条下拉用内核全量中文名、面板改动→属性表实时刷新、
    装配浏览器搜索与加入构建、排序表按数值排序、双击加入构建。
    检查完逐个还原，避免污染 demo 构建。
    """
    import copy

    from PySide6.QtCore import Qt

    from deskrawl_calc import StatType

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

    # 3) 装配浏览器：搜索过滤 + 加入/删除
    browser = win.assembly_browser
    listing = browser._lists['gem']
    browser._searches['gem'].setText('GemAmethyst')
    hidden = sum(1 for i in range(listing.count()) if listing.item(i).isHidden())
    check(0 < hidden < listing.count(), '装配浏览器搜索过滤生效',
          f'{listing.count()} 项中隐藏 {hidden} 项')
    browser._searches['gem'].setText('')
    n0 = len(win.profile.assembled)
    listing.setCurrentRow(0)
    browser._add_selected('gem')
    n1 = len(win.profile.assembled)
    check(n1 == n0 + 1, '装配浏览器「加入构建」生效', f'{n0} → {n1} 项')
    browser.assembled_list.setCurrentRow(n1 - 1)
    browser._remove_selected()
    check(len(win.profile.assembled) == n0, '装配浏览器「删除选中」生效',
          f'回到 {len(win.profile.assembled)} 项')

    # 4) 排序表：四列均可排序，且 ΔDPS 按数值而非字符串排
    table = win.candidate_rank_view.table
    model = table.model()
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
    table.doubleClicked.emit(win.candidate_rank_view.proxy.index(0, 0))
    n1 = len(win.profile.assembled)
    check(n1 == n0 + 1, '候选排序表双击加入构建', f'{n0} → {n1} 项')
    win.assembly_browser.assembled_list.setCurrentRow(n1 - 1)
    win.assembly_browser._remove_selected()

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
    """T5：构建存/取 JSON 往返一致（含派生属性表逐项一致）。"""
    import os

    from deskrawl_calc import GameData, StatType

    from .core import calc_service
    from .core.profile import BUILDS_DIR, CharacterProfile, load_build, save_build

    gd = GameData()
    source = CharacterProfile.demo()
    path = os.path.join(BUILDS_DIR, 'demo-hunter.json')
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
            f'{os.path.relpath(path)}；JSON 等值={same_dict}，属性表最大偏差={max(finals):.2e}，'
            f'DPS 等值={same_dps}')


def run_selftest() -> int:
    rep = Report()
    if not _print_kernel_selftest():
        print('内核自检未通过，终止。', file=sys.stderr)
        return 1
    _engine_ok(rep)
    _equipment_checks(rep)
    _rank_checks(rep)
    _build_roundtrip(rep)
    print(f'\n自检结果：{"全部通过" if rep.ok() else "存在失败"}'
          f'（{rep.passed}/{len(rep.checks)}）')
    return 0 if rep.ok() else 1
