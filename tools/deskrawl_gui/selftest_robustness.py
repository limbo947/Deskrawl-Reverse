# -*- coding: utf-8 -*-
"""鲁棒性组自检：空候选判定 / RuneData 缓存 / 异常日志落盘。

从 selftest.py 拆出：主文件已 700+ 行，而这三组只依赖 core（不需要 QApplication），
与「数值锚点」职责不同；A1/D1/E1 三项改动的回归都落在这里。
"""
import json
import os
import sys
import tempfile
import threading


def _empty_candidate_checks(rep):
    """空候选必须被标记（A1）。

    空武器算出来恰好 0 DPS、空防具等于卸下当前件，两者都是把「还没填」当成一次换装；
    `candidate_empty` 是视图改判空态的唯一依据，漏判就会回到「−100%」那种假结论。
    """
    from deskrawl_calc import GameData

    from .core import calc_service as cs
    from .core.item_draft import ItemDraft
    from .core.profile import CharacterProfile, WeaponDraft

    gd = GameData()

    p_weapon = CharacterProfile.demo()
    p_weapon.weapon_candidate = WeaponDraft()
    p_weapon.compare_slot = 0
    r_weapon = cs.compare(p_weapon, gd)

    p_armor = CharacterProfile.demo()
    p_armor.compare_slot = 2
    p_armor.slot_current[2] = ItemDraft(name='测试胸甲', affixes=[[23, 0, 0.5]],
                                        equip_slot_type=3, item_level=70, rarity=3)
    p_armor.slot_candidate[2] = ItemDraft()
    r_armor = cs.compare(p_armor, gd)

    r_demo = cs.compare(CharacterProfile.demo(), gd)

    ok = (r_weapon.candidate_empty and abs(r_weapon.candidate_dps) < 1e-9
          and r_armor.candidate_empty and r_armor.delta_pct < 0
          and not r_demo.candidate_empty and r_demo.candidate_dps > 0)
    rep.add(ok, '空候选判定（武器槽 / 有当前件的防具槽判空；有内容候选不误判）',
            f'武器空候选 empty={r_weapon.candidate_empty} '
            f'cand={r_weapon.candidate_dps:.1f}；'
            f'胸甲空候选 empty={r_armor.candidate_empty} Δ%={r_armor.delta_pct:.2f}；'
            f'demo 候选 empty={r_demo.candidate_empty} cand={r_demo.candidate_dps:.1f}')


def _multi_compare_checks(rep):
    """A4 整套对比：空集 ≡ 基线、总 Δ 与逐槽边际口径自证、且总 Δ ≠ 各槽单算之和。

    第三条是本功能存在的理由：如果四处和相加相等，用户直接加也行；实测不等（乘区交互），
    这条断言把「不可相加」钉成事实而不是说法。
    """
    from deskrawl_calc import GameData, StatType

    from .core import calc_service as cs
    from .core import compare_multi as cm
    from .core.item_draft import ItemDraft
    from .core.profile import CharacterProfile

    gd = GameData()
    p = CharacterProfile.demo()
    zero_ok = abs(cm._dps_with(p, gd, []) - cs.baseline_dps(p, gd)) < 1e-9
    empty = cm.multi_compare(p, gd)

    p.slot_current[2] = ItemDraft(name='测试胸甲', affixes=[[int(StatType.DamagePhysical), 0, 0.5]])
    p.slot_candidate[2] = ItemDraft(name='候选胸甲',
                                    affixes=[[int(StatType.DamagePhysical), 0, 0.4],
                                             [int(StatType.CritDamage), 0, 0.3]])
    res = cm.multi_compare(p, gd)
    single = [cs.compare(p, gd, slot=s).delta for s in res.slots]
    nonadd_ok = abs(res.delta - sum(single)) > 1e-6
    marginals = [r.marginal for r in res.rows]
    order_ok = all(a >= b for a, b in zip(marginals, marginals[1:]))
    gate_ok = (res.slots == [0, 2] and 1 in res.skipped
               and abs(res.delta - (res.multi_dps - res.base_dps)) < 1e-9
               and order_ok and len(res.rows) == 2)
    rep.add(zero_ok and empty.slots == [0] and gate_ok and nonadd_ok,
            '整套对比（空集 ≡ 基线 · 空候选不参与 · 逐槽边际按幅值降序 · 总 Δ ≠ 各槽之和）',
            f'空集偏差={cm._dps_with(p, gd, []) - cs.baseline_dps(p, gd):.2e}；'
            f'参与槽={res.slots} 未填={len(res.skipped)}；'
            f'总 Δ={res.delta:+.2f} vs 各槽之和={sum(single):+.2f}（不等={nonadd_ok}）；'
            f'边际={[(r.label, round(r.marginal, 1)) for r in res.rows]}')


def _build_library_checks(rep):
    """A6 构建库：目录扫描给出元信息、备注随文件往返、损坏文件不炸整库。

    用临时目录而非 data/builds：断言不该依赖（也不该污染）用户的真实构建。
    """
    from deskrawl_calc import GameData

    from .core.build_library import scan_builds, set_note
    from .core.profile import CharacterProfile, save_build

    gd = GameData()
    tmp = tempfile.mkdtemp(prefix='deskrawl_builds_')
    a = CharacterProfile.demo()
    a.name, a.note = '构建甲', '单手剑试验'
    save_build(a, os.path.join(tmp, 'a.json'))
    b = CharacterProfile.demo()
    b.name, b.level = '构建乙', 65
    save_build(b, os.path.join(tmp, 'b.json'))
    with open(os.path.join(tmp, 'broken.json'), 'w', encoding='utf-8') as f:
        f.write('{ 坏掉的 json')

    entries = scan_builds(gd, tmp)
    by_name = {e.name: e for e in entries}
    scan_ok = (len(entries) == 3 and by_name['构建甲'].note == '单手剑试验'
               and by_name['构建甲'].level == 70 and by_name['构建乙'].level == 65
               and all(e.dps and e.dps > 0 for e in entries if not e.error))
    broken_ok = sum(1 for e in entries if e.error) == 1

    set_note(os.path.join(tmp, 'b.json'), '双持试验')
    reloaded = {e.name: e for e in scan_builds(gd, tmp)}
    note_ok = reloaded['构建乙'].note == '双持试验'
    rep.add(scan_ok and broken_ok and note_ok,
            '构建库（元信息扫描 / 备注随文件往返 / 损坏文件单独标记不炸整库）',
            f'{len(entries)} 份（含 1 份损坏）；DPS 示例 '
            f'{by_name["构建甲"].dps:.1f}；备注往返={note_ok}')


def _theme_checks(rep):
    """A12 主题：色值表覆盖全部在用色值，浅色替换不残留暗色专属令牌。

    为什么用「残留扫描」而不是截图比对：截图会随 Qt 版本与 DPI 抖动，而「某个暗色值没被
    映射」是确定的失败——它在浅色主题下就是一块读不出来的暗底。

    恒等映射（主黄/涨绿/跌红/聚焦蓝）不算残留：它们是跨主题不变的语义令牌，浅色下本就
    该保持同一个值；只扫描「需要翻转」的那批暗色专属令牌，才不会因为品牌色而误报。
    """
    from .core import theme

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "style.qss")
    with open(path, encoding="utf-8") as f:
        qss = f.read()
    unknown = theme.unknown_colors(qss)
    light = theme.apply_theme(qss, "light")
    upper = light.upper()
    # 同一个色值可以既是暗色令牌、又是某个浅色令牌的目标（画布 #FFFFFF / 细边线 #EAECEF
    # 就同时扮演两个角色）。只有「不是任何浅色目标的暗色令牌」才算真的没被替换。
    produced = {v.upper() for v in theme.LIGHT_MAP.values()}
    leftover = [c for c in theme.theme_specific_tokens()
                if c in upper and c.upper() not in produced]
    shared = [c for c, v in theme.LIGHT_MAP.items() if c.upper() == v.upper()]
    dark_same = theme.apply_theme(qss, "dark") == qss
    white_kept = theme.CANVAS_LIGHT in upper      # 浅色画布确已铺上纯白
    rep.add(not unknown and not leftover and dark_same and white_kept,
            "主题令牌（色值表覆盖全部在用色值；浅色不残留暗色；暗色不动）",
            f"未登记色值={unknown or '无'}；浅色残留={leftover or '无'}；"
            f"暗色原样={dark_same}；浅色画布={white_kept}；恒等品牌令牌={len(shared)} 个")


def _rune_cache_checks(rep):
    """RuneData 只解析一次（D1）。

    用缓存计数而非计时：命中/miss 是确定性的，不会随机器抖动；而「每次都重解 333KB JSON」
    正是原先单次编辑 4.78ms 的来源。
    """
    from deskrawl_calc import GameData

    from .core import skill_service
    from .core.profile import CharacterProfile

    gd = GameData()
    p = CharacterProfile.demo()
    skill_service._rune_rows.cache_clear()
    skill_service.ability_level_bonuses(p, gd)
    miss1 = skill_service._rune_rows.cache_info().misses
    skill_service.ability_level_bonuses(p, gd)
    info = skill_service._rune_rows.cache_info()
    rows = len(skill_service._rune_rows(gd))
    ok = miss1 == 1 and info.misses == 1 and info.hits >= 1 and rows > 0
    rep.add(ok, 'RuneData 行缓存（首次读盘、其后命中；不重复解析 333KB JSON）',
            f'首次 miss={miss1}；两次后 misses={info.misses} hits={info.hits}；行数={rows}')


def _export_checks(rep):
    """表格导出（A2）：TSV 压平控制符、CSV 引号转义、落盘带 BOM 且行数正确。

    三张表都走同一套文本层，这里钉住规则本身；界面只负责把当前显示文本喂进来。
    """
    from .core import export

    headers = ['属性', '数值']
    rows = [['物理伤害', '12.5'], ['含\t制表符\n与换行', '含,逗号"引号']]
    tsv = export.rows_to_tsv(headers, rows)
    csv_text = export.rows_to_csv(headers, rows)
    tsv_ok = (tsv.splitlines()[0] == '属性\t数值'
              and tsv.splitlines()[1] == '物理伤害\t12.5'
              and '\t制表符' not in tsv and '换行' in tsv)

    tmp_dir = tempfile.mkdtemp(prefix='deskrawl_export_')
    path = os.path.join(tmp_dir, 'out.csv')
    n = export.write_csv(path, headers, rows)
    with open(path, 'rb') as f:
        raw = f.read()
    with open(path, encoding='utf-8-sig', newline='') as f:   # 保留 \r\n：默认会做通用换行转换
        written = f.read()
    file_ok = (n == 2 and raw.startswith(b'\xef\xbb\xbf')
               and written.count('\r\n') == 3 and '物理伤害' in written)
    csv_ok = '"含,逗号""引号"' in csv_text
    rep.add(tsv_ok and csv_ok and file_ok,
            '表格导出文本层（TSV 压平 \\t/\\n、CSV 引号转义、CSV 带 BOM 且行数正确）',
            f'TSV 首行={tsv.splitlines()[0]!r}；CSV 转义={csv_ok}；'
            f'文件行={written.count(chr(13) + chr(10))} BOM={raw[:3]!r}')


def _fingerprint_cache_checks(rep):
    """启动指纹缓存（D4）：命中时不再读文件，文件变更（mtime）后必须重算。

    用哈希调用次数而非计时断言：次数是确定性的，而缓存的意义正是把 60MB DLL 的哈希从
    每次启动一次降到「文件变了一次」。
    """
    from .core import memory_snapshot as ms

    tmp = tempfile.mkdtemp(prefix='deskrawl_fp_')
    blob = os.path.join(tmp, 'blob.bin')
    with open(blob, 'wb') as f:
        f.write(b'x' * (64 * 1024))
    cache = {}
    calls = {'n': 0}
    orig = ms.sha256_file

    def counted(path):
        calls['n'] += 1
        return orig(path)

    ms.sha256_file = counted
    try:
        d1 = ms.cached_sha256(blob, cache)      # 首次：读盘
        d2 = ms.cached_sha256(blob, cache)      # 命中缓存
        st = os.stat(blob)
        os.utime(blob, ns=(st.st_atime_ns, st.st_mtime_ns + 10 ** 9))
        d3 = ms.cached_sha256(blob, cache)      # mtime 变 → 重算
    finally:
        ms.sha256_file = orig

    js = os.path.join(tmp, 'rows.json')
    with open(js, 'w', encoding='utf-8') as f:
        json.dump([{'a': 1}, {'a': 2}], f)
    n1 = ms.cached_json_count(js, {})
    n2 = ms.cached_json_count(js, {})
    ok = (d1 == d2 == d3 and calls['n'] == 2 and n1 == n2 == 2)
    rep.add(ok, '启动指纹缓存（size/mtime 命中复用；文件变更后重算）',
            f'哈希调用 {calls["n"]} 次（期望 2：首算 + 变更后）；'
            f'mtime 变更触发重算={d3 == d1}；JSON 条目数 {n1}/{n2}')


def _heroes_checks(rep):
    """A10：职业清单由 HeroData.Class 派生（补丁新增职业不漏），已知职业用中文名。"""
    from deskrawl_calc import GameData

    from .core.heroes import hero_class_label, hero_class_options

    gd = GameData()
    opts = hero_class_options(gd)
    classes = [cls for cls, _label in opts]
    labels = dict(opts)
    ok = (classes == sorted(classes) and {1, 2, 4, 8} <= set(classes)
          and labels.get(1) == '野蛮人' and labels.get(2) == '法师'
          and labels.get(4) == '猎人' and labels.get(8) == '武僧'
          and hero_class_label(gd, None) == '未设职业'
          and hero_class_label(gd, 9999) == '未设职业')
    rep.add(ok, '职业清单由 HeroData 派生（四职业中文名 + 未知回落「未设职业」）',
            f'选项={opts}')


def _meter_cache_checks(rep):
    """D2：DPS 计定位缓存按 pid 隔离、可整体作废；复用 pid 前必须自证进程身份。"""
    from .core import dps_meter

    dps_meter._forget_meter()
    miss = dps_meter._cached_meter(1234)
    dps_meter._store_meter(1234, 0x7FF00000)
    hit = dps_meter._cached_meter(1234)
    other = dps_meter._cached_meter(5678)
    dps_meter._forget_meter()
    gone = dps_meter._cached_meter(1234)
    # pid 会被系统回收：只判「句柄能打开」会把别人的内存当游戏读，故复用必须比进程名
    same = dps_meter._same_image('Deskrawl.exe', 'deskrawl.EXE')
    diff = dps_meter._same_image('chrome.exe', 'Deskrawl.exe')
    empty = dps_meter._same_image('', 'Deskrawl.exe')
    ok = (miss == 0 and hit == 0x7FF00000 and other == 0 and gone == 0
          and same and not diff and not empty)
    rep.add(ok, 'DPS 计定位缓存（按 pid 命中；作废后重定位；pid 复用须自证进程名）',
            f'未命中={miss}；命中={hex(hit)}；换 pid={other}；作废后={gone}；'
            f'同名复用={same}；异名拒绝={not diff}；空名拒绝={not empty}')


def _stat_metadata_checks(rep):
    """E6：两套属性元数据（输入单位 / 面板显示格式）各自单一来源，且语义不可互换。

    为什么值得一条断言：这两套表要是有第三份副本，新增属性就会漏改其中一处——表现是
    「面板显示成 3000%」这种不报错的错数。断言锁住三件事：集合只含真实属性、判定函数与
    集合一致、calc_service 里不再有第二份字面量。
    """
    from deskrawl_calc import StatType
    from deskrawl_calc.stattype import (FRACTIONAL_STATS, PERCENT_DISPLAY_STATS,
                                        is_fractional, is_percent_display)

    from .core import calc_service

    ids = {int(s) for s in StatType}
    subset_ok = FRACTIONAL_STATS <= ids and PERCENT_DISPLAY_STATS <= ids
    consistent = all(is_fractional(s) == (int(s) in FRACTIONAL_STATS)
                     and is_percent_display(s) == (int(s) in PERCENT_DISPLAY_STATS)
                     for s in ids)
    # 语义区分（两套表没有被合并成一套的证据）：
    #   · 显示成 % 的属性必然按小数存 → 显示集是输入集的真子集；
    #   · 材料获取(19) 按小数输入但面板显示数值 → 反方向不成立；
    #   · 武器速度(21) 两套都不在（面板单独按一位小数处理）、最大生命(7) 按千分位。
    distinct = (PERCENT_DISPLAY_STATS < FRACTIONAL_STATS
                and is_fractional(StatType.MaterialFind)
                and not is_percent_display(StatType.MaterialFind)
                and is_percent_display(StatType.CritChance)
                and not is_fractional(StatType.WeaponSpeed)
                and not is_percent_display(StatType.WeaponSpeed)
                and not is_percent_display(StatType.MaxHealth))
    single_source = not hasattr(calc_service, '_PCT_DISPLAY')
    # 面板格式化真的走内核判定：暴击率 0.25 → "25%"，最大生命 3000 → "3,000"
    panel = calc_service.build_panel({'player': {'stat_dicts': {'nsq': {'4': 0.25, '7': 3000}},
                                                 'fields': {'CurrentHealth': 3000}},
                                      'meta': {}})
    texts = {int(r[0]): r[6] for r in panel['rows']}
    fmt_ok = (texts.get(int(StatType.CritChance)) == '25%'
              and ',' in texts.get(int(StatType.MaxHealth), ''))
    ok = subset_ok and consistent and distinct and single_source and fmt_ok
    rep.add(ok, '属性元数据分层（输入单位 vs 面板显示格式，各自单一来源）',
            f'集合是真实属性={subset_ok}；判定与集合一致={consistent}；语义区分={distinct}；'
            f'calc_service 无第二份表={single_source}；'
            f'面板格式={texts.get(int(StatType.CritChance))}/'
            f'{texts.get(int(StatType.MaxHealth))}')


def _logging_checks(rep):
    """异常落盘（E1）：excepthook 写入文件，且自检路径不触发 GUI 提示、不留全局 hook。"""
    from .core import logging_setup

    tmp = os.path.join(tempfile.mkdtemp(prefix='deskrawl_log_'), 'app-test.log')
    old_ex, old_th = sys.excepthook, threading.excepthook
    path = body = ''
    installed = False
    try:
        path = logging_setup.install(path=tmp)          # 不传 notify：无 GUI 环境下只落盘
        installed = sys.excepthook is logging_setup._hook
        try:
            raise RuntimeError('自检注入的异常')
        except RuntimeError:
            sys.excepthook(*sys.exc_info())
        with open(tmp, encoding='utf-8') as f:
            body = f.read()
    finally:
        logging_setup.uninstall()
        sys.excepthook, threading.excepthook = old_ex, old_th
    ok = (installed and path == tmp and 'Traceback' in body
          and '自检注入的异常' in body and sys.excepthook is old_ex)
    rep.add(ok, '异常日志（hook 落盘 traceback；卸载后还原 hook）',
            f'安装={installed}；路径一致={path == tmp}；'
            f'文件 {len(body)} 字符；还原={sys.excepthook is old_ex}')
