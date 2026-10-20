# -*- coding: utf-8 -*-
"""只重导 `data/so_dump/TalentEffects.json`。

为什么单独一个脚本：`dump_all2.py` 会重写 21 个文件并依赖 `assets_cache.json`，而缓存偏旧会让
物品集缩水（AGENTS 有警告）。当只有 Effect 类受影响时（如 decode.py 的对齐修复），只碰这一个
文件、保持与 dump_all2 相同的遍历顺序与字段格式，diff 才看得清。
"""
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import UnityPy                                              # noqa: E402
import decode                                               # noqa: E402
from paths import GAME_DATA, SO_DUMP                         # noqa: E402

env = UnityPy.load(os.path.join(GAME_DATA, 'resources.assets'),
                   os.path.join(GAME_DATA, 'sharedassets0.assets'),
                   os.path.join(GAME_DATA, 'globalgamemanagers.assets'),
                   os.path.join(GAME_DATA, 'level0'))
files = {os.path.basename(getattr(sf, 'name', str(fk))): sf for fk, sf in env.files.items()}


def _ext_name(e):
    s = str(e)
    m = re.search(r'<FileIdentifier\((.*?)\)>', s)
    return m.group(1) if m else s.rstrip('>')


def obj_class(fn, o):
    """MonoBehaviour 类名：按 m_Script 的 PPTR 直接解（script_type_index 对 Effect 资产解不出）。"""
    sf = files.get(fn)
    if sf is None:
        return None
    try:
        raw = o.get_raw_data()
        fid = struct.unpack_from('<i', raw, 0x10)[0]
        pid = struct.unpack_from('<q', raw, 0x14)[0]
        if fid == 0:
            tf = fn
        elif 0 <= fid - 1 < len(sf.externals):
            tf = _ext_name(sf.externals[fid - 1])
        else:
            return None
        tgt = files.get(tf)
        if tgt is None or pid not in tgt.objects:
            return None
        ms = tgt.objects[pid].read()
        return getattr(ms, 'm_ClassName', None) or getattr(ms, 'm_Name', None)
    except Exception:
        return None


def main():
    rows = []
    for fn in ('resources.assets', 'sharedassets0.assets', 'globalgamemanagers.assets', 'level0'):
        sf = files.get(fn)
        if not sf:
            continue
        for o in sf.objects.values():
            c = obj_class(fn, o)
            if not c or not c.startswith('TalentEffect_'):
                continue
            try:
                nm, obj, refs, _end = decode.decode_object_ex(o.get_raw_data(), c)
            except Exception:
                continue
            rec = {'_name': nm, '_pathid': o.path_id, '_file': fn, '_class': c}
            if refs:
                rec['_managedRefs'] = refs
            rec.update(obj)
            rows.append(rec)
    out = os.path.join(SO_DUMP, 'TalentEffects.json')
    json.dump(rows, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
    print(f'重导完成：{len(rows)} 条 -> {out}')


if __name__ == '__main__':
    main()
