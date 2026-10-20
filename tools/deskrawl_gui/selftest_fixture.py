# -*- coding: utf-8 -*-
"""内存导入夹具 / 游戏面板口径检查段（从 selftest.py 拆出，二次拆至 717→约 210 行）。

为什么拆：单一 selftest.py 会因「一个场景一段断言」线性膨胀。本段的边界是「夹具本身」：
β/α 快照的装配链闭环、面板 23 行锚点、装备名本地化；装备链路的对称性/镜像/技能表在
selftest_equipment.py（E2 拆出，原属本文件）。入口仍是 `deskrawl_gui --selftest`，
断言顺序与拆分前逐条一致。
"""
from .selftest import Report, _rel_pct
# 装备链路/镜像/技能表检查段在同一次里被调用，故在此统一导入（单向依赖）
from .selftest_equipment import (_chain_audit_checks, _import_keep_checks,
                                 _like_current_pref_checks, _load_fixture,
                                 _nonweapon_mirror_checks, _skill_checks,
                                 _skill_freq_checks, _slot_checks,
                                 _weapon_mirror_checks)

# --------------------------------------------------------------------------- #
# 内存导入夹具自检（任务书：β=memdump --json 原样输出；α=β 去掉 equipment 的变体）
# --------------------------------------------------------------------------- #
# 由「装备词条 + 孔位宝石」即可完全解释的键位（2026-10-08 对拍逐键核定，残差 0）。
# 它是反向验证的抓手：这些键位不依赖 nsq 就能独立复算，改坏夹具必须变红。
_DERIVED_EXACT_KEYS = (0, 4, 11, 13, 14, 15, 16, 17, 22, 23, 29, 31, 36, 38, 40, 42, 44, 51, 52, 53, 65)

# 孔位宝石加成组（与 core/profile._gem_category 同一实测锚定：武器 2 / 饰品 1 / 护甲 0）
_GEM_CAT = {1: 2, 7: 1, 8: 1}


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
    from .core.localization import equipment_display_name
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
    # 暴伤/暴击率/物理% 等少读，见 profile._panel_finals 的实测记录）。取 with_conversions=False：
    # 基座与 sheet 同层（换算由 `_apply_conversions` 显式后置），否则比的是两种口径
    prow = {int(r[0]): float(r[5])
            for r in calc_service.build_panel(beta, with_conversions=False)['rows']
            if r[5] is not None}
    expect = {st: prow.get(st, v) for st, v in nsq.items()}
    bad = [st for st, v in sorted(expect.items()) if sheet.final(st) != v]
    rep.add(not bad, 'β 夹具 装配链 Final ≡ 口径期望（主属性=面板 451，其余逐键 ≡ nsq）',
            f'{len(expect)} 键逐位比对，失配 {len(bad)}；主属性 {stat_name(prof.primary_stat)} '
            f'= {sheet.final(prof.primary_stat):.0f}（面板 {float(prow[5]):.0f}）；'
            f'模式={prof.import_mode}，宝石 {len(prof.assembled)} 颗')

    # 主属性伤害加成（Player.CalcDamage@0x518230）：DPS 的攻击伤害 = (武器伤害 + 通用增伤) ×(1+Final/100)
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
    upg_ok = (prof.weapon_current.name == equipment_display_name(gd, wrec['name'])
              and got != want_raw
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
    # F4（审计报告）实机复核锚：真实 β 包的非武器槽**携带实例数据**（memdump --json 实测
    # inventory 4 + storage 29 件 equip_slot_type∈[2,11] 且 modifiers≠null），故夹具已并入
    # 这批真实记录（storage 尾部，2026-10-12 采集）——非武器槽候选下拉据此可被真实填充。
    nw_bag = [rec for rec in bag if 2 <= int(rec.get('equip_slot_type') or 0) <= 11]
    rep.add(len(nw_bag) >= 1, 'β 夹具 非武器背包候选（F4 实机并入真实记录）',
            f'{len(nw_bag)} 件真实非武器记录（equip_slot_type∈[2,11]，带词条）')

    # 装备名简中化：导入链按 Equipments 表（Unity Localization）翻成游戏内显示名；
    # 锚定一个具体映射（LegendarySword1 → 苦痛锯齿巨剑），表被换/键失配时先红
    equip_names = [prof.weapon_current.name, *(d.name for d in prof.slot_current.values()),
                   *names]
    han = all(any('\u4e00' <= ch <= '\u9fff' for ch in n) for n in equip_names)
    sample = equipment_display_name(gd, 'LegendarySword1')
    rep.add(han and sample == '苦痛锯齿巨剑' and prof.weapon_current.name == sample,
            '装备名简中本地化（Equipments 表 → 与游戏内显示一致）',
            f'{len(equip_names)} 件装备名含中文={han}；LegendarySword1 → {sample}')

    # 装配件简中化：宝石/符文/套装在 Equipments 表，天赋**单独**一张 Talents 表（2026-10-17 导出，
    # 186/186 覆盖）。天赋若误挂 Equipments 会整体回落内部名，必须锚一个具体译文才会红。
    from .core.localization import assembly_display_name
    rune_zh = assembly_display_name(gd, 'rune', 'HunterSetRune1_1')
    talent_zh = assembly_display_name(gd, 'talent', 'HunterTalent19')
    rep.add(rune_zh == '设阱者的传承 I' and talent_zh != 'HunterTalent19',
            '装配件简中本地化（符文/套装走 Equipments 表，天赋走 Talents 表）',
            f'HunterSetRune1_1 → {rune_zh}；HunterTalent19 → {talent_zh}')

    # 符文「技能等级+N」：游戏侧 bonus = Levels + runeLevel // EveryN（cjb@0x18071B670 是 idiv 后 add）。
    # 必须锚 Levels=4 的 WarriorSetRune2_1：Levels=2 那档乘/加同值（2×2=2+2=4），抓不出乘法误实现。
    from types import SimpleNamespace

    from .core.skill_service import ability_level_bonuses
    one = SimpleNamespace(assembled=[
        SimpleNamespace(kind='rune', name='WarriorSetRune2_1', level=6)])
    two = SimpleNamespace(assembled=[
        SimpleNamespace(kind='rune', name='WarriorSetRune2_1', level=6),
        SimpleNamespace(kind='rune', name='WarriorSetRune2_2', level=6)])
    b1 = ability_level_bonuses(one, gd).get('WarriorHeavyAttack3', 0)
    b2 = ability_level_bonuses(two, gd).get('WarriorHeavyAttack3', 0)
    rep.add(b1 == 6 and b2 == 10,
            '符文技能等级：Levels + 等级/EveryN（6/6 时 _1→+6、_1+_2→+10）',
            f'WarriorSetRune2_1 → +{b1}；再加 _2 → +{b2}')

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

    # 武器区：真实武器用传奇词条替代「基础伤害/攻速/技能倍率」三行；手工自拟的名字回落三行
    # （这三项对游戏武器是既成事实，白字伤害走 WeaponDamage 词条，手填只会诱导错误录入）
    if weapon_bag:
        ce = eqb.current_editor
        spins = (ce.damage_spin, ce.speed_spin, ce.skill_spin)
        legend_txt = ce.legend_label.text()
        real_ok = (bool(legend_txt) and not ce.legend_label.isHidden()
                   and all(sp.isHidden() for sp in spins))
        saved_name = ce.draft.name
        ce.draft.name = '旧武器·双手剑'
        ce.reload()
        manual_ok = (not ce.legend_label.text() and ce.legend_label.isHidden()
                     and all(not sp.isHidden() for sp in spins))
        ce.draft.name = saved_name
        ce.reload()
        rep.add(real_ok and manual_ok,
                '武器区：传奇词条替代三行数值（手工名回落手工录入）',
                f'{saved_name} → 「{legend_txt}」，三行隐藏={real_ok}；手工名回落={manual_ok}')

    # 非武器槽同样带传奇词条行（护甲/饰品的传奇特效是它们的主要战力，不能只在武器上显示）
    from .core.legendary import legendary_lines as _legend_lines

    armor = next(((s, it) for s, it in (prof.slot_current or {}).items()
                  if _legend_lines(gd, it.name)), None)
    if armor:
        slot_id, armor_item = armor
        from .widgets.item_editor import ItemEditor

        armor_ed = ItemEditor('当前', armor_item,
                              legendary_fn=lambda n: _legend_lines(gd, n))
        armor_text = armor_ed.legend_label.text()
        rep.add(bool(armor_text) and not armor_ed.legend_label.isHidden(),
                '非武器槽也显示传奇词条（与武器同一行）',
                f'槽{slot_id} {armor_item.name} → 「{armor_text}」')

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

    # 当前件（游戏事实）固定只读：基线不可改脏，候选侧照常可编辑
    lock_ok = (eqc.current_editor.name_edit.isReadOnly()
               and not eqc.current_editor.add_btn.isEnabled()
               and not eqc.candidate_editor.name_edit.isReadOnly())
    rep.add(lock_ok, 'β 当前件只读（已固定）/ 候选可编辑',
            f'当前只读={eqc.current_editor.name_edit.isReadOnly()}，'
            f'标题「{eqc.current_editor.title()}」；'
            f'候选只读={eqc.candidate_editor.name_edit.isReadOnly()}')

    # 候选装备「与当前装备相同（强化/宝石）」：武器镜像 → 重算 → 取消复原（任意槽同款开关）
    _weapon_mirror_checks(rep, prof, gd)
    _nonweapon_mirror_checks(rep, prof, gd)
    # 开关选择跨槽记忆 + 导入保留用户口径（图二设置不随导入变化）
    _like_current_pref_checks(rep, prof, gd)
    _import_keep_checks(rep, prof, gd)
    _chain_audit_checks(rep, prof, gd)

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


def _legendary_effect_checks(rep: Report):
    """T9：传奇特效首批 A（条件暴击 / 标签暴伤）接线自检。

    链路：数据层 `item_effects`/`runeset_effects` 保真提取 → 内核 `effects` 语义 →
    `calc_service` 逐侧装配（条件暴击进暴击乘区）→ `skill_service` 按技能/标签过滤。
    反向抓手：目标状态开关必须驱动条件暴击；候选换「按标签暴伤」件时只抬命中该标签的技能行，
    其余行 Δ 逐位为 0（证明接线真实生效而非空转）。
    """
    import copy

    from deskrawl_calc import GameData

    from .core import calc_service, skill_service
    from .core.profile import CharacterProfile

    gd = GameData()
    beta = _load_fixture('snapshot_beta.json')

    # 1) 数据层：装备 → 全部传奇特效（保真 dict，含非属性类）；符文套装特效同源
    sw = [e['_class'] for e in gd.item_effects('LegendarySword1')]
    rs = gd.runeset_effects('WarriorSetRune3', 6)
    rep.add(any(c.endswith('ConditionalCritChance') for c in sw)
            and any(str(e.get('_class', '')).endswith('ConditionalCritDamage') for e in rs),
            '传奇特效 数据层（item_effects / runeset_effects 保真提取）',
            f'LegendarySword1 → {sw}；WarriorSetRune3(6) → {[e["_class"] for e in rs]}')

    # 2) 条件暴击门控端到端：当前武器 = LegendarySword1（易伤 → 额外 +30% 暴击率）
    p = CharacterProfile.from_snapshot(beta, gd)
    p.compare_slot = 0
    p.target.vulnerable = False
    r0 = calc_service.compare(p, gd)
    p.target.vulnerable = True
    r1 = calc_service.compare(p, gd)
    d_cur = r1.current_model.crit_chance() - r0.current_model.crit_chance()
    d_cand = r1.candidate_model.crit_chance() - r0.candidate_model.crit_chance()
    # BonusCritChance 原值是 float32（0.30000001192092896）→ 容差 1e-6
    rep.add(abs(d_cur - 0.30) < 1e-6 and abs(d_cand) < 1e-12 and r1.current_dps > r0.current_dps,
            '传奇特效·条件暴击（易伤门控 → 当前武器暴击率 +30%，候选列不动）',
            f'当前暴击率 {r0.current_model.crit_chance():.3f} → {r1.current_model.crit_chance():.3f}；'
            f'候选 Δ={d_cand:.2e}；当前 DPS {r0.current_dps:.1f} → {r1.current_dps:.1f}')

    # 3) 按标签暴伤：候选换 LegendaryPants1（3 条 AbilityTagCritDamage，含 Tag 8=火焰），
    #    词条/宝石与当前件逐位相同 → 只抬含 tag 8 的技能行（WarriorHeavyAttack1），其余行 Δ 逐位 0
    p2 = CharacterProfile.from_snapshot(beta, gd)
    p2.compare_slot = 3
    cand = copy.deepcopy(p2.slot_current[3])
    cand.name = 'LegendaryPants1'
    p2.slot_candidate[3] = cand
    res = calc_service.compare(p2, gd)
    rows = skill_service.skill_rows(p2, gd, res.current_sheet, res.candidate_sheet, res.target,
                                    cur_effects=res.current_effects,
                                    cand_effects=res.candidate_effects)
    by = {r.name: r for r in rows}
    hit = by['WarriorHeavyAttack1'].delta               # tags [1, 8] 含火焰(8)
    miss = by['WarriorBasicAttack'].delta               # tags [0, 7] 不含
    rep.add(hit > 0 and abs(miss) < 1e-9,
            '传奇特效·标签暴伤（候选 LegendaryPants1 → 只抬 WarriorHeavyAttack1 行）',
            f'WarriorHeavyAttack1 Δ={hit:+.3f}（应 >0）；WarriorBasicAttack Δ={miss:.2e}（应 0）')

    # 4) 条件伤害：候选换 LegendaryNeck7（Condition=Stunned、DamageType=物理、Ability=WarriorBasicAttack2、+1.5）
    #    → 目标开「眩晕」时只抬 WarriorBasicAttack2 行；关「眩晕」时各行 Δ 归零（门控 + Ability 过滤反证）
    p3 = CharacterProfile.from_snapshot(beta, gd)
    p3.compare_slot = 8
    cn = copy.deepcopy(p3.slot_current[8])
    cn.name = 'LegendaryNeck7'
    p3.slot_candidate[8] = cn

    def rows_of(p):
        r = calc_service.compare(p, gd)
        return skill_service.skill_rows(p, gd, r.current_sheet, r.candidate_sheet, r.target,
                                        cur_effects=r.current_effects,
                                        cand_effects=r.candidate_effects)

    p3.target.stunned = False
    d_off = {r.name: r.delta for r in rows_of(p3)}
    p3.target.stunned = True
    d_on = {r.name: r.delta for r in rows_of(p3)}
    hit = d_on['WarriorBasicAttack2']
    others = [v for k, v in d_on.items() if k != 'WarriorBasicAttack2']
    off_zero = all(abs(v) < 1e-9 for v in d_off.values())
    rep.add(off_zero and hit > 0 and all(abs(v) < 1e-9 for v in others),
            '传奇特效·条件伤害（颈链 Cleave → 只抬 WarriorBasicAttack2 行，眩晕门控）',
            f'非眩晕各行 Δ 全 0={off_zero}；眩晕 WarriorBasicAttack2 Δ={hit:+.3f}（应 >0），'
            f'其余行全 0={all(abs(v) < 1e-9 for v in others)}')

    # 5) 技能修正（AbilityModifier）：候选按 Tag 8 注入 Damage +0.6 → 只抬 WarriorHeavyAttack1
    from .core.profile import AssemblyItem

    p4 = CharacterProfile.from_snapshot(beta, gd)
    p4.compare_slot = 1
    p4.slot_candidate[1] = copy.deepcopy(p4.slot_current[1])   # 与当前件相同 → 排除属性差异
    r4 = calc_service.compare(p4, gd)
    am = {'_class': 'EquipmentEffect_AbilityModifier', 'Tag': 8, 'Ability': None,
          'Stat': 2, 'Modifier': 0.6}
    d_am = {r.name: r.delta for r in skill_service.skill_rows(
        p4, gd, r4.current_sheet, r4.candidate_sheet, r4.target,
        cur_effects=r4.current_effects, cand_effects=r4.candidate_effects + [am])}
    hit_am = d_am['WarriorHeavyAttack1']
    others_am = [v for k, v in d_am.items() if k != 'WarriorHeavyAttack1']
    rep.add(hit_am > 0 and all(abs(v) < 1e-9 for v in others_am),
            '传奇特效·技能修正（AbilityModifier Tag8 Damage+0.6 → 只抬 WarriorHeavyAttack1）',
            f'WarriorHeavyAttack1 Δ={hit_am:+.3f}（应 >0）；其余行全 0='
            f'{all(abs(v) < 1e-9 for v in others_am)}')

    # 6) 引导修改（AbilityChannelModifier，符文套装 WarriorSetRune2(4)）→ 旋风斩 hits/sec ×1.25
    p5 = CharacterProfile.from_snapshot(beta, gd)
    r5 = calc_service.compare(p5, gd)
    base_hits = {r.name: r.hits_per_sec for r in skill_service.skill_rows(
        p5, gd, r5.current_sheet, r5.candidate_sheet, r5.target,
        cur_effects=r5.current_effects, cand_effects=r5.candidate_effects)}
    p6 = copy.deepcopy(p5)
    p6.assembled = list(p6.assembled) + [AssemblyItem('runeset', 'WarriorSetRune2', 4)]
    r6 = calc_service.compare(p6, gd)
    up_hits = {r.name: r.hits_per_sec for r in skill_service.skill_rows(
        p6, gd, r6.current_sheet, r6.candidate_sheet, r6.target,
        cur_effects=r6.current_effects, cand_effects=r6.candidate_effects)}
    ww = 'WarriorHeavyAttack3'
    ratio = up_hits[ww] / base_hits[ww]
    other_same = abs(up_hits['WarriorBasicAttack'] - base_hits['WarriorBasicAttack']) < 1e-12
    rep.add(abs(ratio - 1.25) < 1e-9 and other_same,
            '传奇特效·引导修改（符文套装 WarriorSetRune2(4) → 旋风斩 hits/sec ×1.25）',
            f'旋风斩 {base_hits[ww]:.4f} → {up_hits[ww]:.4f}（×{ratio:.4f}）；'
            f'其它技能不变={other_same}')

    # 7) 属性换算（StatConversion）：候选换 LegendaryChestArmor6（闪避22 → 物理减伤51 ×0.5）
    #    → 候选侧属性表 51 增加「0.5×Final(闪避)」，当前侧不变（装配完成后显式后步）
    p7 = CharacterProfile.from_snapshot(beta, gd)
    p7.compare_slot = 2
    c6 = copy.deepcopy(p7.slot_current[2])
    c6.name = 'LegendaryChestArmor6'
    p7.slot_candidate[2] = c6
    r7 = calc_service.compare(p7, gd)
    d51 = r7.candidate_sheet.final(51) - r7.current_sheet.final(51)
    dodge = r7.current_sheet.final(22)
    rep.add(abs(d51 - 0.5 * dodge) < 1e-6,
            '传奇特效·属性换算（胸甲 ChestArmor6 → 闪避×0.5 加到物理减伤 51）',
            f'Δ物理减伤(51)={d51:.6f}（期望 0.5×闪避 {dodge:.6f}={0.5 * dodge:.6f}）')

    # 8) 对普通/精英伤害倍率（DivineHelmet3，B 面唯一「只差开关」的一条）：进独立乘数。
    #    纯函数管取值分支（普通/精英/无特效），技能行管接线：两侧同目标、无 DOT 的普攻应精确 ×1.4。
    from deskrawl_calc import Target as _Target
    from deskrawl_calc import effects as _fx

    helm = {'_class': 'EquipmentEffect_DivineHelmet3',
            'NormalEnemyMultiplier': 1.2, 'EliteEnemyMultiplier': 1.4}
    t_elite = _Target(level=70, elite=True)
    p.target.elite = True                     # 端到端走精英档（1.4），普通档由上面的纯函数验证
    r8 = calc_service.compare(p, gd)          # p 的 compare_slot=0，最省的一次装配
    plain = {r.name: r.current_dps for r in skill_service.skill_rows(
        p, gd, r8.current_sheet, r8.candidate_sheet, r8.target,
        cur_effects=r8.current_effects)}
    boosted = {r.name: r.current_dps for r in skill_service.skill_rows(
        p, gd, r8.current_sheet, r8.candidate_sheet, r8.target,
        cur_effects=r8.current_effects + [helm])}
    fn_ok = (abs(_fx.enemy_class_multiplier([helm], _Target(level=70)) - 1.2) < 1e-9
             and abs(_fx.enemy_class_multiplier([helm], t_elite) - 1.4) < 1e-9
             and _fx.enemy_class_multiplier([], t_elite) == 1.0)
    nm = 'WarriorBasicAttack'
    ratio8 = boosted[nm] / plain[nm] if plain[nm] else 0.0
    rep.add(fn_ok and abs(ratio8 - 1.4) < 1e-9,
            '传奇特效·普通/精英伤害倍率（DivineHelmet3：普通 ×1.2 / 精英 ×1.4 进独立乘数）',
            f'纯函数 普通={_fx.enemy_class_multiplier([helm], _Target(level=70)):.2f} / '
            f'精英={_fx.enemy_class_multiplier([helm], t_elite):.2f}；'
            f'技能行 {nm} ×{ratio8:.4f}（期望 ×1.4000）')
