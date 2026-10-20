# -*- coding: utf-8 -*-
"""按页拆出的交互检查段（E3）：角色 / 装备对比 / 装配中心各一段。

为什么要拆：这些断言原来挤在 selftest.py 的一个 224 行函数里（`_gui_behavior_checks`），
改一个控件要读整屏输出，且主文件持续膨胀。拆分按「页面」而非「控件」切分——每段只碰
本页的控件与信号链，失败时能立刻对应到一页。检查函数由调用方传入 check()，
与 --smoke 的 PASS/FAIL 输出格式一致。
"""


def compare_editor_checks(win, check):
    """装备对比页：词条下拉/类型列/删除撤销 + 参考技能卡归位。"""
    import copy

    from PySide6.QtCore import Qt

    from deskrawl_calc import StatType

    editor = win.compare_page.equipment_editor.candidate_editor

    # 1) 武器词条下拉 = 内核 StatType 全量中文名
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

    # 百分比属性：提示说明「按 % 显示、内部小数」，且输入框确实切到 % 单位（A8）
    pct_ok = (add_only_text() and '%' in t_item.toolTip()
              and '%' in v_spin.toolTip() and v_spin._percent is True)
    s_combo.setCurrentIndex(s_combo.findData(int(StatType.Strength)))
    num_ok = add_only_text() and '加法' in t_item.toolTip() and v_spin._percent is False
    check(pct_ok and num_ok, '词条类型为只读文本「加法」（无下拉；百分比属性切 % 单位）',
          f'物理伤害%：文本加法+%单位={pct_ok}；力量：仍为加法={num_ok}')
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
          and not hasattr(win.role_page.panel_editor, 'skill_combo'),
          '参考技能卡在对比页目标基础下方（唯一入口，写回 profile）',
          f'布局序号={te.layout().indexOf(sc)}（应 1）；写回={wrote_skill}；'
          f'还原={restored}；角色页无技能控件={not hasattr(win.role_page.panel_editor, "skill_combo")}')


def role_panel_checks(win, check):
    """角色页：面板改动 → 属性表实时刷新；职业主属性下拉写回 profile。"""
    from deskrawl_calc import StatType

    def stat_final(name):
        model = win.role_page.stat_table.model
        for r in range(model.rowCount()):
            if model.cell_text(r, 0) == name:
                return float(model.cell_text(r, 5))
        return None

    # 2) 面板改动 → 属性表实时刷新
    spin = win.role_page.panel_editor._base_spins[int(StatType.WeaponDamage)]
    before = stat_final('武器伤害')
    spin.setValue(37.0)
    after = stat_final('武器伤害')
    check(after is not None and abs(after - 37.0) < 1e-9, '面板改动 → 属性表实时刷新',
          f'武器伤害 最终值 {"（无该行）" if before is None else before} → {after}')
    spin.setValue(0.0)

    # 2b) 职业主属性下拉写回 profile（DPS 加成因子由 _snapshot_checks 用夹具覆盖）
    pc = win.role_page.panel_editor.primary_combo
    pc.setCurrentIndex(pc.findData(int(StatType.Strength)))
    wrote = win.profile.primary_stat == int(StatType.Strength)
    pc.setCurrentIndex(0)
    check(wrote and win.profile.primary_stat is None,
          '职业主属性下拉写回 profile（力量 → 未设置还原）',
          f'{pc.count()} 个选项；写回={wrote}')


def assembly_table_checks(win, check):
    """装配中心：搜索/加入/就地改参数/删除/排序/双击加入。

    删除类操作会弹模态确认框：全程短路为「确认」，否则非交互环境会挂死在等待点击上。
    """
    from PySide6.QtCore import Qt

    from .widgets import assembly_center as _ac_mod

    ac = win.assembly_center
    saved_confirm = _ac_mod.confirm_delete
    _ac_mod.confirm_delete = lambda *a, **k: True
    try:
        # 3) 搜索过滤 + 加入/删除
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

        def _delta_text(row):
            """Δ 列显示文本 → 数值：现在带涨跌箭头（▲/▼），解析前先剥掉它。

            箭头是给色弱用户的第二通道，不改变排序键（UserRole 仍是 float）；这里仍按
            「用户看到的顺序」断言，而不是绕过视图去读模型。
            """
            return float(str(model.index(row, 3).data(Qt.DisplayRole)).lstrip('▲▼ ').strip())

        table.sortByColumn(3, Qt.DescendingOrder)
        top_desc = _delta_text(0)
        low_desc = _delta_text(model.rowCount() - 1)
        table.sortByColumn(3, Qt.AscendingOrder)
        top_asc = _delta_text(0)
        check(top_desc > low_desc and abs(low_desc - top_asc) < 1e-6,
              'ΔDPS 按数值排序（非字符串）',
              f'降序 {top_desc:+.1f} … {low_desc:+.1f}；升序首行 {top_asc:+.1f}')

        # 5) 排序表双击 → 加入构建
        n0 = len(win.profile.assembled)
        table.doubleClicked.emit(ac.proxy.index(0, 0))
        n1 = len(win.profile.assembled)
        check(n1 == n0 + 1, '候选排序表双击加入构建', f'{n0} → {n1} 项')
        ac.assembled_list.setCurrentRow(n1 - 1)
        ac._remove_selected()
    finally:
        _ac_mod.confirm_delete = saved_confirm
