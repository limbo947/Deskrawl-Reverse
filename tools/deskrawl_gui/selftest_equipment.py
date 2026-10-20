# -*- coding: utf-8 -*-
"""装备链路 / 镜像 / 技能表检查段（从 selftest_fixture.py 拆出）。

为什么拆：fixture 段有效行已到 717（棘轮规则要求 700 行即拆），而本段自洽——
全部围绕「一件装备怎么进数值、两侧怎么镜像、技能表怎么随换装动」，
与夹具的面板闭环/本地化断言不是同一件事。入口仍是 `deskrawl_gui --selftest`。
"""
import json
import os

from .selftest import Report, _rel_pct

# 夹具目录与读取器放这里（本模块被 fixture 段引用，方向单向，避免循环导入）
_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


def _load_fixture(name: str) -> dict:
    with open(os.path.join(_FIXTURES, name), encoding='utf-8') as f:
        return json.load(f)


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

    # 4) 技能类型标签池 33/34/61 同池加算；62（持续伤害）现由 DOT 段消费（只作用于施加 DOT 的技能）
    #    指令级依据：Character.SkillTypeDamageMultiplier(Slot 16) 按 tag 0/1/2 累加 33/34/61；
    #    62 由 DamageOverTimeBehavior 的 tick 公式消费（docs/04 §6.2.7），工具已建模 DOT 并折入技能秒伤。
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
        # 62：DOT 已建模 → 只作用于施加 DOT 的技能（Barbarian=Bleeding 于 WarriorBasicAttack3/HeavyAttack4）；
        #    「零消费保持惰性」旧口径作废——命中集合须恰为 DOT 技能，且注入 62 使其货币上升。
        dps62, rows62 = rows_with([[int(StatType.DamageOverTime), 0, 5.0]])
        dot_skills = {'WarriorBasicAttack3', 'WarriorHeavyAttack4'}
        hit62 = {r.name for r in rows62 if abs(r.delta) > 1e-9}
        proven = all(gd.ability_dot(n) for n in dot_skills)   # 自证：这俩确为 DOT 技能
        ok62 = (proven and abs(dps62 - base_dps) < 1e-9 and hit62 == dot_skills)
        rep.add(ok61 and ok62,
                '技能类型池：61 命中 Special(2) 标签技能；62 只命中施加 DOT 的技能',
                f'注入 61+5.0 → 命中 {sorted({r.name for r in hit61})}'
                f'（Special 技能={sorted(special)}）={ok61}；'
                f'注入 62+5.0 → 命中 {sorted(hit62)}（DOT 技能={sorted(dot_skills)}，自证={proven}）、'
                f'主 DPS 不变={abs(dps62 - base_dps) < 1e-9}')

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

    # 8) F8 防御：_negate 卸下不可逆词条（连乘 type 2）时会丢项使 Δ 失真——必须写显式告警而非
    #    静默跳过（type≠0 词条当前全仓不可达，这是防御性缺口；注入以证明告警真的会触发）。
    from deskrawl_calc import Modifier
    warns = []
    kept = calc_service._negate(
        [Modifier(int(StatType.DamagePhysical), 0, 3.0),
         Modifier(int(StatType.DamagePhysical), 2, 1.5)], warns, '测试件')
    rep.add(len(kept) == 1 and len(warns) == 1 and '连乘' in warns[0],
            'F8 防御：_negate 跳过 type 2 词条并写告警（不静默丢项）',
            f'保留 {len(kept)} 条（期望 1）、告警 {warns}')

    # 9) Δ 归因（边际影响）：逐条抽掉候选词条重算 → 有益词条为正、按幅值降序、只取前 3。
    #    断言「符号与排序」而非具体 DPS：口径稳定比某个数字重要（词条间有乘区交互，不做加总）
    p.weapon_candidate = copy.deepcopy(p.weapon_current)
    p.weapon_candidate.affixes = [[20, 0, 100.0], [4, 0, 5.0]]
    marg = calc_service.affix_marginals(p, gd)
    rep.add(len(marg) == 2 and marg[0][0] == 20 and marg[0][1] > marg[1][1] > 0,
            'Δ 归因：逐条移除的边际影响（正值=该条有益，按幅值降序、最多 3 条）',
            f'{[(s, round(d, 1)) for s, d, _v in marg]}')


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
    """「与当前装备相同」选择跨槽保持：记忆位为开时，新槽的**有内容候选**自动沿用镜像。

    记忆位是 profile.like_current_pref（随会话状态/构建持久化）。I3 后切槽不再自动拷贝当前件，
    所以「沿用镜像」必须先在目标槽显式播种（点「以当前件为起点」）——本检查据此两步走，
    顺带证明「空候选不会被误勾」（勾了只会得到有宝石没词条的半成品）。
    """
    import copy

    from .widgets.equipment_editor import EquipmentEditor

    prof2 = copy.deepcopy(prof)
    eq = EquipmentEditor(prof2, gd)                    # 默认槽 0 = 武器
    eq.candidate_editor.like_current.setChecked(True)  # 勾选 → 记忆位开
    pref_on = bool(prof2.like_current_pref)
    eq.slot_combo.setCurrentIndex(eq.slot_combo.findData(2))   # 换到胸甲（当前件带 1 颗宝石）
    empty_not_checked = not eq.candidate_editor.like_current.isChecked()   # 空候选不误勾
    eq._seed_candidate()                                       # 显式播种 → 候选有内容
    seeded_ok = bool(prof2.slot_candidate[2].affixes or prof2.slot_candidate[2].name)
    draft_flag = bool(prof2.slot_candidate[2].like_current)    # 快照：之后的取消会清零
    kept = eq.candidate_editor.like_current.isChecked() and draft_flag
    eq.candidate_editor.like_current.setChecked(False)         # 取消 → 记忆位关
    eq.slot_combo.setCurrentIndex(eq.slot_combo.findData(3))   # 换到裤子
    off_ok = (not eq.candidate_editor.like_current.isChecked()
              and not bool(prof2.like_current_pref))
    rep.add(pref_on and empty_not_checked and seeded_ok and kept and off_ok,
            '「与当前装备相同」跨槽保持（播种后沿用 / 取消后不再勾 / 空候选不误勾）',
            f'空候选不误勾={empty_not_checked}；播种成功={seeded_ok}；'
            f'换槽沿用={kept}（槽2 候选草稿 like_current={draft_flag}）；'
            f'取消后不勾={off_ok}；最终记忆位={prof2.like_current_pref}')


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

    # 天赋「按技能修正」的 2/5/6/0（2026-10-19 接入；旧白名单只收 8/9，导入角色等于丢整块天赋）。
    # 伤害项是纯乘数、冷却项只改频次 → 精确对拍；暴击两项受 0.85 封顶与目标影响，只断方向。
    from deskrawl_calc import StatType

    plain = 'WarriorSpecial3'                     # cd=10 / 非引导 / 无 DOT，乘区关系最干净
    pb = row_for(prof, plain)
    cd0 = min(0.80, max(0.0, calc_service.compare(prof, gd)
                        .current_sheet.final(StatType.CooldownReduction)))
    cd1 = min(0.80, max(0.0, cd0 + 0.3))

    def mod_row(mods):
        p = copy.deepcopy(prof)
        p.ability_mods = {plain: mods}
        return row_for(p, plain)

    r_dmg, r_cc, r_cd, r_cool = (mod_row({2: 0.5}), mod_row({5: 0.1}),
                                 mod_row({6: 0.2}), mod_row({0: 0.3}))
    mods_ok = (_rel_pct(r_dmg.current_dps, pb.current_dps * 1.5) < 1e-6
               and r_cc.current_dps > pb.current_dps and r_cd.current_dps > pb.current_dps
               and _rel_pct(r_cool.hits_per_sec,
                            pb.hits_per_sec * (1.0 - cd0) / (1.0 - cd1)) < 1e-9)
    rep.add(mods_ok, '天赋按技能修正 2/5/6/0 落入乘区（伤害×1.5 · 暴击上升 · 逐技能冷却改频次）',
            f'{plain}：伤害 {pb.current_dps:.1f}→{r_dmg.current_dps:.1f}（期望 ×1.5）；'
            f'暴击率/暴伤 {r_cc.current_dps:.1f}/{r_cd.current_dps:.1f}（应均 >{pb.current_dps:.1f}）；'
            f'冷却+30% 命中 {pb.hits_per_sec:.4f}→{r_cool.hits_per_sec:.4f}'
            f'（期望 ×{(1 - cd0) / (1 - cd1):.4f}）')
