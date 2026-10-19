# -*- coding: utf-8 -*-
"""天赋「按技能修正」的解析侧自检（纯数据，不需要 QApplication / 实机）。

为什么单独一组：2026-10-19 起 `TalentEffect_AbilityModifier` 不只有指针型（按技能），
还有 Tag 型（按 AbilityTag 展开），而 `memory_validate` 的行格式随之变成 3/4 元两种。
这两处都能用合成数据证伪，不必连游戏；实机只用来对拍面板数值。

`rep` 是 selftest.Report 的鸭子类型实例（不 import 以免与主模块循环引用）。
"""
from __future__ import annotations


def _talent_mod_checks(rep) -> None:
    """Tag 型展开到同类技能 + 指针型按名字落位 + 校验接受两种行格式。"""
    from deskrawl_calc import GameData

    from .core.memory_validate import _talent_mod_row_ok
    from .core.profile import _talent_ability_mods

    gd = GameData()
    names = gd.abilities_for_class(1)                     # Barbarian
    ptrs = [0x100000 + i for i in range(len(names))]      # 假指针：只验证「第 i 个 ↔ 第 i 个名字」
    strong = [sk['name'] for sk in gd.damage_skills(1) if 1 in (sk.get('tags') or [])]
    other = 'WarriorSpecial3'                             # tags=[2,7]：不含 StrongAttack
    out = _talent_ability_mods(ptrs, [[8, ptrs[1], 0.5], [2, 0, 0.3, 1]], 1, gd)

    ptr_ok = out.get(names[1], {}).get(8) == 0.5
    tag_ok = bool(strong) and all(out.get(n, {}).get(2) == 0.3 for n in strong)
    neg_ok = not (out.get(other) or {}).get(2)             # 反向：未命中 tag 的技能不受影响
    row_ok = (_talent_mod_row_ok([2, 0x100000, 0.5]) and _talent_mod_row_ok([2, 0, 0.5, 1])
              and not _talent_mod_row_ok([2, 0, 0.5])       # 指针 0 的 3 元组是脏数据
              and not _talent_mod_row_ok([2, 0, 0.5, 9999])  # Tag=None 不构成目标
              and not _talent_mod_row_ok([2, 0, float('nan'), 1]))
    rep.add(ptr_ok and tag_ok and neg_ok and row_ok,
            '天赋技能修正：指针型按技能落位 / Tag 型展开到同类技能（校验收 3·4 元组）',
            f'指针型 {names[1]}=0.5；Tag=1 展开 {len(strong)} 个技能={tag_ok}；'
            f'未命中技能不受影响={neg_ok}；行格式校验={row_ok}')
