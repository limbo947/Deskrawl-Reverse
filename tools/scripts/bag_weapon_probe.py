# -*- coding: utf-8 -*-
"""临时探针：验证仓库/背包内未装备武器能否读到实例数据（Q1 可行性）。只读。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'deskrawl_gui'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from deskrawl_gui.core.memory_reader import ProcessReader, Il2CppReader, ActkCodec, valid_ptr
from deskrawl_gui.core.memory_import import Locator, SnapshotBuilder, load_offsets
from deskrawl_calc.stattype import STAT_NAMES

off = load_offsets()
pid = ProcessReader.find_process(off['process_name'])
print('pid =', pid)
pr = ProcessReader(pid)
with pr:
    il = Il2CppReader(pr, off['il2cpp'])
    builder = SnapshotBuilder(il, ActkCodec(pr), off, Locator(pr, il, off))
    builder.locate()
    payload = builder.read_pass()
    print(f'uid2gid 条数 = {len(builder.uid2gid)}')
    for where in ('inventory', 'storage'):
        rows = payload[where]
        weapons = []
        for it in rows:
            if not it['uid']:
                continue
            g = builder.uid2gid.get(it['uid'])
            if g is None:
                continue
            gio = off['generated_item']
            item_level = pr.i32(g + gio['item_level'])
            upg = pr.i32(g + gio['upgrade_level'])
            mods = builder._read_modifiers(pr.u64(g + gio['modifiers']))
            # 名称在 name_map 里查不到 ItemData 指针（_read_slots 已带 name）
            weapons.append((it['name'], where, item_level, upg, mods))
        print(f'[{where}] 有实例数据的物品 {len(weapons)} 件')
        for name, w, ilv, upg, mods in weapons:
            if upg or (name or '').lower().find('sword') >= 0 or (name or '').lower().find('staff') >= 0:
                txt = '; '.join(f'[{m[0]}:{STAT_NAMES.get(m[0], "?")} t{m[1]} v{m[2]}]' for m in mods)
                print(f'  {name} ilv={ilv} upg={upg} mods: {txt}')
