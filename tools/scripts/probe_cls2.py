import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
# -*- coding: utf-8 -*-
"""调试：如何从对象解析出 C# 类名（用于定位 EquipmentEffect_* 等资产）。"""
import os, sys, collections
sys.path.insert(0, TOOLS)
import decode  # noqa (读 dump.cs)
import UnityPy

BASE = GAME_DATA
env = UnityPy.load(os.path.join(BASE, 'resources.assets'), os.path.join(BASE, 'sharedassets0.assets'),
                   os.path.join(BASE, 'globalgamemanagers.assets'), os.path.join(BASE, 'level0'))
files = {}
for fk, sf in env.files.items():
    files[os.path.basename(getattr(sf, 'name', str(fk)))] = sf

fname = 'resources.assets'
sf = files[fname]
print('ref_types', len(sf.ref_types or []), 'script_types', len(sf.script_types or []), 'externals', len(sf.externals or []))
o = sf.objects[4802]
print('obj4802 type attrs:', [a for a in dir(o.type) if not a.startswith('_')][:40])
for a in ('script_type_index', 'class_id', 'type_id', 'is_stripped'):
    try:
        print('  ', a, '=', getattr(o.type, a))
    except Exception as e:
        print('  ', a, 'ERR', e)
print('ref_types sample:', [ (getattr(r,'script_type_index',None)) for r in (sf.ref_types or [])[:10]])

# 用 script_types + MonoScript 反查类名
def build(sf):
    m = {}
    for i, st in enumerate(sf.script_types or []):
        try:
            fi = st.local_serialized_file_index
            pid = st.local_identifier_in_file
            tgt = sf if fi == 0 else files.get(os.path.basename(str(getattr(sf.externals[fi-1], 'path', ''))))
            ms = tgt.objects[pid].read()
            m[i] = getattr(ms, 'm_ClassName', None) or getattr(ms, 'm_Name', None)
        except Exception as e:
            m[i] = None
    return m

cm = build(sf)
print('script_types -> names sample:', dict(list(cm.items())[:15]))
print('obj4802 script_type_index =', getattr(o.type, 'script_type_index', None), '-> class', cm.get(getattr(o.type, 'script_type_index', -1)))

cnt = collections.Counter()
hit = 0
for pid, ob in sf.objects.items():
    sti = getattr(ob.type, 'script_type_index', None)
    c = cm.get(sti)
    if c:
        hit += 1
        cnt[c] += 1
print('objects with resolved class:', hit, '/', len(sf.objects))
for c, n in cnt.most_common(30):
    print(f'   {c:50} {n}')
