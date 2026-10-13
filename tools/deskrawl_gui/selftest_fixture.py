# -*- coding: utf-8 -*-
"""内存导入夹具 / 游戏面板口径检查段（从 selftest.py 拆出）。

为什么拆：selftest.py 有效行已逼近 800 行上限（本轮新增武器镜像/只读检查后 751 行），
而这一段是连续且自洽的——全部由 fixtures/ 下的 α/β 快照驱动，不碰 demo 场景与内核直算。
入口仍是 `deskrawl_gui --selftest`：run_selftest 延迟导入本模块（避免与本文件互相 import），
断言顺序与拆分前逐条一致。
"""
import json
import os

from .selftest import Report, _rel_pct

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
    # 暴伤/暴击率/物理% 等少读，见 profile._panel_finals 的实测记录）
    prow = {int(r[0]): float(r[5]) for r in calc_service.build_panel(beta)['rows']
            if r[5] is not None}
    expect = {st: prow.get(st, v) for st, v in nsq.items()}
    bad = [st for st, v in sorted(expect.items()) if sheet.final(st) != v]
    rep.add(not bad, 'β 夹具 装配链 Final ≡ 口径期望（主属性=面板 451，其余逐键 ≡ nsq）',
            f'{len(expect)} 键逐位比对，失配 {len(bad)}；主属性 {stat_name(prof.primary_stat)} '
            f'= {sheet.final(prof.primary_stat):.0f}（面板 {float(prow[5]):.0f}）；'
            f'模式={prof.import_mode}，宝石 {len(prof.assembled)} 颗')

    # 主属性伤害加成（Player.CalcDamage@0x511060）：DPS 的攻击伤害 = (武器伤害 + 通用增伤) ×(1+Final/100)
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


def _chain_audit_checks(rep: Report, prof, gd):
    """F12 回归网：装备伤害链路审计（docs/plan/装备伤害链路完整性审计.md）的断言落位。

    补齐审计发现的空白：全槽对称性、宝石加成组按槽位推导（F1 修复锚）、61/62 零消费口径固化、
    披风槽行为、传奇特效接线自证（F3）。手工候选的 equip_slot_type 与导入件不同——这是本组
    断言存在的理由：旧实现按草稿字段取宝石组，戒指/项链槽会静默错位（+5.44% 幻影收益），
    而此前零断言使其长期不可见。
    """
    import copy

    from deskrawl_calc import StatType

    from .core import calc_service, skill_service

    p = copy.deepcopy(prof)                      # 就地改候选，不污染后续检查
    p.weapon_candidate = copy.deepcopy(p.weapon_current)

    def rows_of(res):
        return skill_service.skill_rows(p, gd, res.current_sheet, res.candidate_sheet, res.target,
                                        level=p.skill_level)

    # 1) 全槽对称性：候选=当前件 → 主 DPS 与逐技能秒伤 Δ≡0（审计前只锚定槽 1/2/10）
    bad = []
    for slot in range(11):
        if slot == 0:
            p.weapon_candidate = copy.deepcopy(p.weapon_current)
        else:
            cur = p.slot_current.get(slot)
            if cur is None:
                continue
            p.slot_candidate[slot] = copy.deepcopy(cur)
        res = calc_service.compare(p, gd, slot=slot)
        if abs(res.delta) > 1e-9 or any(abs(r.delta) > 1e-9 for r in rows_of(res)):
            bad.append(slot)
    rep.add(not bad, '全槽对称性（槽 0..10 候选=当前件 → 主 DPS 与技能表 Δ≡0）',
            f'{11 - len(bad)}/11 槽通过' + (f'，失配槽 {bad}' if bad else ''))

    # 2) 宝石加成组按槽位推导：武器 2 / 戒指·项链 1 / 其余（含腰带）0
    got = {s: calc_service.gem_category_for_slot(s) for s in range(12)}
    want = {0: 2, 6: 1, 7: 1, 8: 1}
    rep.add(all(got[s] == want.get(s, 0) for s in range(12)),
            '宝石加成组按槽位推导（武器 2 / 戒指·项链 1 / 其余 0）',
            f'槽0={got[0]}，槽6/7/8={got[6]}/{got[7]}/{got[8]}，槽2={got[2]}，槽10={got[10]}')

    # 3) F1 修复锚：饰品槽手工候选（equip_slot_type=0）镜像宝石仍按饰品组
    ring = next((s for s in (6, 7, 8) if p.slot_current.get(s) and p.slot_current[s].gems), None)
    if ring is None:
        rep.add(False, '饰品槽宝石组（F1 修复锚）', '夹具无带宝石的饰品槽')
    else:
        cand = copy.deepcopy(p.slot_current[ring])
        cand.equip_slot_type = 0                 # 手工草稿默认值：旧实现据此取护甲组
        cand.gems = ['GemRuby6']                 # 护甲组=力量、饰品组=火焰减伤 → 错位会虚高 DPS
        # 名字保持当前件同名：传奇特效按名字反查（不可解析的名字会丢掉特效，Δ 被特效主导而
        # 掩盖宝石组这个变量）；本断言只回答「宝石组取对没有」。
        p.slot_candidate[ring] = cand
        r = calc_service.compare(p, gd, slot=ring)
        rows = rows_of(r)
        # 非空转自证：红宝石两组数值确实不同（否则本断言证明不了取组正确）
        distinct = gd.gem_modifiers('GemRuby6', 0) != gd.gem_modifiers('GemRuby6', 1)
        ok = distinct and abs(r.delta) < 1e-9 and not any(abs(x.delta) > 1e-9 for x in rows)
        rep.add(ok, f'饰品槽手工候选（槽 {ring}，equip_slot_type=0）宝石仍按饰品组',
                f'GemRuby6 两组数值不同={distinct}；Δ%={r.delta_pct:+.6f}；'
                f'技能行 Δ≡0={not any(abs(x.delta) > 1e-9 for x in rows)}')

    # 4) 技能类型标签池（33/34/61 同池加算）已接线；62（持续伤害）仍不建模
    #    指令级依据：Character.SkillTypeDamageMultiplier(Slot 16) 按 tag 0/1/2 累加 33/34/61；
    #    62 由 DamageOverTimeBehavior 的 DOT tick 公式消费，本工具未建模 DOT，故保持惰性。
    slot = 6 if p.slot_current.get(6) else next(iter(p.slot_current), None)
    if slot is None:
        rep.add(False, '技能类型标签池（33/34/61）', '夹具无非武器槽')
    else:
        def rows_with(extra):
            p.slot_candidate[slot] = copy.deepcopy(p.slot_current[slot])
            p.slot_candidate[slot].affixes = list(p.slot_current[slot].affixes) + extra
            res = calc_service.compare(p, gd, slot=slot)
            return res.candidate_dps, rows_of(res)

        base_dps, _ = rows_with([])
        # 61：只对带 Special(2) 标签的技能生效（Barbarian=WarriorSpecial3/4）
        dps61, rows61 = rows_with([[int(StatType.SpecialAbilityDamage), 0, 5.0]])
        special = {r.name for r in rows61 if 'Special' in r.name}
        others = [r for r in rows61 if 'Special' not in r.name]
        hit61 = [r for r in rows61 if abs(r.delta) > 1e-9]
        ok61 = (special and {r.name for r in hit61} == special
                and all(abs(r.delta) < 1e-9 for r in others))
        # 62：DOT 未建模 → 任何技能行都不变（主 DPS 也不变）
        dps62, rows62 = rows_with([[int(StatType.DamageOverTime), 0, 5.0]])
        ok62 = (abs(dps62 - base_dps) < 1e-9
                and not any(abs(r.delta) > 1e-9 for r in rows62))
        rep.add(ok61 and ok62,
                '技能类型池：61 命中 Special(2) 标签技能；62（持续伤害）未建模保持惰性',
                f'注入 61+5.0 → 命中 {sorted({r.name for r in hit61})}'
                f'（Special 技能={sorted(special)}）={ok61}；'
                f'注入 62+5.0 → 主 DPS 不变且技能行 Δ≡0={ok62}')

    # 5) 披风槽 11（按设计排除）行为固化：标签回落、无当前件 → 候选为空时 Δ≡0
    r11 = calc_service.compare(p, gd, slot=11)
    rep.add(r11.slot_label == '槽11' and abs(r11.delta) < 1e-9,
            '披风槽 11（按设计排除）行为固化：标签回落「槽11」、空候选 Δ≡0',
            f'label={r11.slot_label}，Δ%={r11.delta_pct:+.6f}')

    # 6) F3 传奇特效已接线：饰品槽 6（屠龙戒 pid 59854 → 攻击速度% +0.35）必须真的入池
    eff_slot = next((s for s in sorted(p.slot_current)
                     if calc_service._effect_mods(gd, p.slot_current[s].name)), None)
    if eff_slot is None:
        rep.add(False, 'F3 传奇特效接线（StatModifier 类入池）', '夹具无带可解析特效的槽')
    else:
        cur = p.slot_current[eff_slot]
        mods = calc_service._effect_mods(gd, cur.name)
        p.slot_candidate[eff_slot] = copy.deepcopy(cur)          # 候选=当前 → 两侧都含特效 → Δ≡0
        r_same = calc_service.compare(p, gd, slot=eff_slot)
        # 反向自证：把候选的特效名换成不可解析的名字 → 特效丢失 → Δ 显著为负（非空转）
        p.slot_candidate[eff_slot] = copy.deepcopy(cur)
        p.slot_candidate[eff_slot].name = '★不可解析名★'
        r_drop = calc_service.compare(p, gd, slot=eff_slot)
        p.slot_candidate[eff_slot] = copy.deepcopy(cur)
        rep.add(abs(r_same.delta) < 1e-9 and r_drop.delta < -1e-6,
                f'F3 传奇特效接线（槽 {eff_slot} {cur.name}：{len(mods)} 条特效词条入池）',
                f'特效={[str(m.describe()) for m in mods]}；候选同名 Δ≡0={abs(r_same.delta) < 1e-9}；'
                f'名字不可解析时 Δ%={r_drop.delta_pct:+.3f}（特效被丢掉，证明接线真实生效）')

    # 7) F7 强化缩放模型（2026-10-12 实机重定）：每级给 2 条词条各 +5%（从 idx0 顺序推进、
    #    末尾绕回）；7 词条时 L=4 的 2L=8 溢出 1 → idx0 吃两次（×1.10）。旧模型给 [20]/[21]
    #    单列 ×(1+0.0125L)/×(1+0.025L) 与「+4 全条 ×1.05 + [21] 单列 ×1.10」均源于漏了绕回。
    from .core.item_draft import apply_upgrade
    probe = [[21, 0, 1.0], [20, 0, 100.0], [4, 0, 1.0], [5, 0, 1.0], [6, 0, 1.0], [3, 0, 1.0], [12, 0, 1.0]]

    def _fac(lv, idx):
        out, _ = apply_upgrade(probe, lv)
        return round(out[idx][2], 6)

    ok_up = (_fac(1, 0) == 1.05 and _fac(2, 0) == 1.05 and _fac(3, 0) == 1.05
             and _fac(4, 0) == 1.10 and _fac(4, 1) == 105.0 and _fac(3, 6) == 1.0)
    rep.add(ok_up, 'F7 强化缩放（前 2L 槽位各 +5%、2L>n 绕回使早期词条吃两次）',
            f'7 词条：[21] L1/2/3={_fac(1, 0)}/{_fac(2, 0)}/{_fac(3, 0)}、L4={_fac(4, 0)}（×1.10）；'
            f'[20] L4={_fac(4, 1)}（=105）；idx6 L3={_fac(3, 6)}')


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


def _weapon_mirror_checks(rep: Report, prof, gd):
    """候选装备「与当前装备相同（强化/宝石）」：镜像当前件 + 按原始词条重算 + 取消复原。

    这是「同强化同宝石谁更强」的对照开关，三件事缺一都会让用户看到错的 Δ：
    宝石必须真的进数值（武器孔位宝石按侧计入）、强化等级必须按背包原始词条重算
    （折叠后的词条不可反推）、取消后必须回到背包原貌。
    """
    from deskrawl_calc import StatType

    from .core import calc_service
    from .core.item_draft import apply_upgrade
    from .widgets.equipment_editor import EquipmentEditor

    bag = getattr(prof, 'bag_items', None) or []
    idx = next((i for i, r in enumerate(bag) if int(r.get('equip_slot_type') or 0) == 1
                and r.get('modifiers')), None)
    if idx is None:
        rep.add(False, '候选武器复用当前强化/宝石', '夹具无带原始词条的背包武器')
        return

    eq = EquipmentEditor(prof, gd)
    eq.bag_combo.setCurrentIndex(eq.bag_combo.findData(idx))
    cand, cur = prof.weapon_candidate, prof.weapon_current
    own = [[list(a) for a in cand.affixes], int(cand.upgrade_level), list(cand.gems)]
    r_own = calc_service.compare(prof, gd)

    eq.candidate_editor.like_current.setChecked(True)      # 勾选：镜像当前件的 +N 与宝石
    mir_level = int(cand.upgrade_level)
    want_affixes, want_speed = apply_upgrade(cand.raw_modifiers, cur.upgrade_level)
    want = [[int(s), int(t), float(v)] for s, t, v in want_affixes]
    has_speed = any(int(s) == int(StatType.WeaponSpeed) for s, _t, _v in cand.raw_modifiers)
    mirror_ok = (int(cand.upgrade_level) == int(cur.upgrade_level)
                 and list(cand.gems) == list(cur.gems)
                 and [list(a) for a in cand.affixes] == want
                 and (not has_speed
                      or abs(float(cand.base_speed) - float(want_speed)) < 1e-9))
    r_mir = calc_service.compare(prof, gd)

    eq.candidate_editor.like_current.setChecked(False)     # 取消：回到背包原貌
    back_ok = ([list(a) for a in cand.affixes] == own[0] and int(cand.upgrade_level) == own[1]
               and list(cand.gems) == own[2])
    r_back = calc_service.compare(prof, gd)

    # 夹具上背包武器是「+0 无宝石」而当前武器是「+4 / 3 颗」：镜像后候选必须变高，且当前侧不动
    r_own_cur = r_own.current_dps
    dps_ok = (r_mir.candidate_dps > r_own.candidate_dps if (cur.gems and not own[2])
              else r_mir.candidate_dps >= r_own.candidate_dps)
    rep.add(mirror_ok and dps_ok and back_ok and r_back.candidate_dps == r_own.candidate_dps
            and r_mir.current_dps == r_own_cur,
            '候选武器「与当前装备相同」（镜像 +N/宝石 + 重算 + 取消复原）',
            f'当前 +{cur.upgrade_level}/{len(cur.gems)} 颗 → 镜像后候选 +{mir_level}；'
            f'候选 DPS {r_own.candidate_dps:.1f} → {r_mir.candidate_dps:.1f}'
            f'（当前侧 {r_own_cur:.1f} 不变={r_mir.current_dps == r_own_cur}）；'
            f'取消复原={back_ok}（DPS 回到 {r_back.candidate_dps:.1f}）')


def _nonweapon_mirror_checks(rep: Report, prof, gd):
    """非武器槽同步「与当前装备相同」：真实背包记录载入 → 勾选镜像 → 取消复原。

    与武器版共用开关逻辑，但走的是 ItemDraft（无武器三行）与 _add_item_mods 的宝石
    路径（加成组按对比槽位推导，见 calc_service.gem_category_for_slot）——故单独验证。
    数据来源（审计报告 F4，2026-10-12 实机复核）：真实 β 包的非武器背包条目**携带实例
    数据**——`memdump --json` 实测 inventory 4 + storage 29 件 equip_slot_type∈[2,11] 且
    modifiers≠null；旧夹具（2026-10-08）不含是因其采集早于放宽提交 3df9cb8，并非真实包
    如此。故夹具的 storage 已并入这批真实记录（尾部，uid 与当期快照一致），本检查改从
    真实记录载入，不再合成条目。
    选手套槽（装备槽 10 / EquipSlotType 9）：夹具中当前手套为 +1，镜像到当前强化等级后
    候选词条数值必然变化（+1 → 前 2 条 ×1.05），可作非空转自证。不再要求「镜像后候选 ≡
    当前件」——真实记录的 roll 与当前件不同，该等式只在合成同源记录时才成立。
    """
    import copy

    from .core import calc_service
    from .core.item_draft import apply_upgrade
    from .widgets.equipment_editor import EquipmentEditor

    cur = prof.slot_current.get(10)
    idx = next((i for i, r in enumerate(prof.bag_items)
                if int(r.get('equip_slot_type') or 0) == 9 and r.get('modifiers')), None)
    if cur is None or idx is None:
        rep.add(False, '非武器槽「与当前装备相同」', '夹具缺当前手套或可载入的真实非武器记录')
        return
    sel = prof.bag_items[idx]
    raw = [[int(s), int(t), float(v)] for s, t, v in sel['modifiers']]

    prof2 = copy.deepcopy(prof)
    eq = EquipmentEditor(prof2, gd)
    eq.slot_combo.setCurrentIndex(eq.slot_combo.findData(10))
    cb = getattr(eq.candidate_editor, 'like_current', None)
    if cb is None:
        rep.add(False, '非武器槽「与当前装备相同」', '非武器候选未提供开关')
        return
    eq.bag_combo.setCurrentIndex(eq.bag_combo.findData(idx))
    cand = prof2.slot_candidate[10]
    loaded_ok = bool(cand.affixes)
    own = [[list(a) for a in cand.affixes], int(cand.upgrade_level), list(cand.gems)]
    r_own = calc_service.compare(prof2, gd, slot=10)

    cb.setChecked(True)                                    # 勾选：镜像当前手套的 +1 与宝石
    mir_level = int(cand.upgrade_level)
    want, _s = apply_upgrade(raw, cur.upgrade_level)
    want = [[int(s), int(t), float(v)] for s, t, v in want]
    mirror_ok = (mir_level == int(cur.upgrade_level)
                 and [list(a) for a in cand.affixes] == want
                 and list(cand.gems) == list(cur.gems))
    changed = [list(a) for a in cand.affixes] != own[0]     # 非空转自证：镜像确实改了数值
    r_mir = calc_service.compare(prof2, gd, slot=10)

    cb.setChecked(False)                                   # 取消：回到背包原貌（+0）
    back_ok = ([list(a) for a in cand.affixes] == own[0]
               and int(cand.upgrade_level) == own[1] and list(cand.gems) == own[2])
    rep.add(loaded_ok and mirror_ok and changed and back_ok
            and r_mir.current_dps == r_own.current_dps,
            '非武器槽「与当前装备相同」同步（真实记录载入 → 镜像 +N/宝石 → 取消复原）',
            f'{sel["name"]}（真实记录 +{int(sel.get("upgrade_level") or 0)} 载入={loaded_ok}）'
            f'→ 镜像当前手套 +{cur.upgrade_level}（词条数值变化={changed}）；'
            f'候选 DPS {r_own.candidate_dps:.1f} → {r_mir.candidate_dps:.1f}'
            f'（当前侧不变={r_mir.current_dps == r_own.current_dps}）；复原={back_ok}')


def _like_current_pref_checks(rep: Report, prof, gd):
    """「与当前装备相同」选择跨槽保持：勾选后换槽仍自动勾选，取消后不再自动勾。

    记忆位是 profile.like_current_pref（随会话状态/构建持久化）；自动勾选只在本槽当前件
    有可镜像的强化/宝石时发生——手工空卡不误勾，也不会给「候选=当前件拷贝」贴上镜像标签。
    """
    import copy

    from .widgets.equipment_editor import EquipmentEditor

    prof2 = copy.deepcopy(prof)
    eq = EquipmentEditor(prof2, gd)                    # 默认槽 0 = 武器
    eq.candidate_editor.like_current.setChecked(True)  # 勾选 → 记忆位开
    pref_on = bool(prof2.like_current_pref)
    eq.slot_combo.setCurrentIndex(eq.slot_combo.findData(2))   # 换到胸甲（当前件带 1 颗宝石）
    draft_flag = bool(prof2.slot_candidate[2].like_current)    # 快照：之后的取消会清零
    kept = eq.candidate_editor.like_current.isChecked() and draft_flag
    eq.candidate_editor.like_current.setChecked(False)         # 取消 → 记忆位关
    eq.slot_combo.setCurrentIndex(eq.slot_combo.findData(3))   # 换到裤子
    off_ok = (not eq.candidate_editor.like_current.isChecked()
              and not bool(prof2.like_current_pref))
    rep.add(pref_on and kept and off_ok,
            '「与当前装备相同」选择跨槽保持（勾选记忆 / 取消记忆）',
            f'勾选后换槽仍勾选={kept}（槽2 候选草稿 like_current={draft_flag}）；'
            f'取消后换槽不勾={off_ok}；最终记忆位={prof2.like_current_pref}')


def _import_keep_checks(rep: Report, prof, gd):
    """导入保留用户口径设置：目标（图二）/参考技能/伤害类型/开关记忆不随导入重置。

    走产线同一函数（app.preserved_import）——若有人改回 replace_with(from_snapshot(...))
    的裸路径，这条会立刻变红。
    """
    import copy

    from deskrawl_calc import DamageType

    from .app import preserved_import
    from .core.profile import TargetDraft

    beta = _load_fixture('snapshot_beta.json')
    before = copy.deepcopy(prof)
    before.target = TargetDraft(level=65, hp_fraction=0.5, elite=True, vulnerable=True,
                                distant=True)
    before.skill_name = 'WarriorHeavyAttack3'
    before.skill_level = 10
    before.damage_type = int(DamageType.Fire)          # 非默认（Physical=0），证明确实保留
    before.like_current_pref = True

    newp = preserved_import(before, beta, gd)
    ok = (newp.import_mode == 'beta'
          and newp.target.level == 65 and abs(float(newp.target.hp_fraction) - 0.5) < 1e-9
          and newp.target.elite and newp.target.vulnerable and newp.target.distant
          and newp.skill_name == 'WarriorHeavyAttack3' and int(newp.skill_level) == 10
          and int(newp.damage_type) == int(DamageType.Fire)
          and bool(newp.like_current_pref))
    rep.add(ok, '导入保留用户口径（图二目标/参考技能/伤害类型/开关记忆）',
            f'目标 Lv{newp.target.level}/血{float(newp.target.hp_fraction):.0%}/精英={newp.target.elite}；'
            f'技能 {newp.skill_name} Lv{newp.skill_level}；伤害类型={DamageType(int(newp.damage_type)).name}；'
            f'开关记忆={bool(newp.like_current_pref)}；模式={newp.import_mode}')


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
