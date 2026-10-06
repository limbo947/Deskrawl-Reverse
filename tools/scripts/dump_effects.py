import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
# -*- coding: utf-8 -*-
"""按 m_Script PPtr 解析对象类名，导出 EquipmentEffect_* / TalentEffect* / LifeSkillEffect_* / StatusEffectBehavior 资产。"""
import os, sys, json, struct, collections
sys.path.insert(0, TOOLS)
import decode
from decode import decode_object_ex
import UnityPy

BASE = GAME_DATA
OUT = SO_DUMP
env = UnityPy.load(os.path.join(BASE, 'resources.assets'), os.path.join(BASE, 'sharedassets0.assets'),
                   os.path.join(BASE, 'globalgamemanagers.assets'), os.path.join(BASE, 'level0'))
files, objs = {}, {}
for fk, sf in env.files.items():
    fn = os.path.basename(getattr(sf, 'name', str(fk)))
    files[fn] = sf
    for o in sf.objects.values():
        objs[(fn, o.path_id)] = o

_ext_names = {}
for fn, sf in files.items():
    _ext_names[fn] = [os.path.basename(str(getattr(e, 'path', ''))) for e in (sf.externals or [])]

_cls_cache = {}


def class_of(fn, pid):
    key = (fn, pid)
    if key in _cls_cache:
        return _cls_cache[key]
    name = None
    try:
        raw = objs[key].get_raw_data()
        fid = struct.unpack_from('<i', raw, 16)[0]
        spid = struct.unpack_from('<q', raw, 20)[0]
        tfn = fn if fid == 0 else _ext_names[fn][fid - 1]
        ms = objs[(tfn, spid)].read()
        name = getattr(ms, 'm_ClassName', None) or getattr(ms, 'm_Name', None)
    except Exception:
        name = None
    _cls_cache[key] = name
    return name


PREFIXES = {'EquipmentEffect_': 'EquipmentEffects', 'TalentEffect': 'TalentEffects',
            'LifeSkillEffect_': 'LifeSkillEffects', 'StatusEffectBehavior': 'StatusBehaviors'}
buckets = collections.defaultdict(list)
cls_count = collections.Counter()
for fn in files:
    for pid in list(files[fn].objects.keys()):
        c = class_of(fn, pid)
        if not c:
            continue
        for pre, key in PREFIXES.items():
            if c.startswith(pre):
                cls_count[c] += 1
                raw = objs[(fn, pid)].get_raw_data()
                try:
                    nm, obj, refs, end = decode_object_ex(raw, c)
                except Exception as e:
                    break
                rec = {'_name': nm, '_pathid': pid, '_file': fn, '_class': c}
                if refs:
                    rec['_managedRefs'] = refs
                rec.update(obj)
                buckets[key].append(rec)
                break

for key, rows in buckets.items():
    if rows:
        json.dump(rows, open(os.path.join(OUT, key + '.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1, default=str)
    print(f'{key:20} {len(rows)}')
print('\n各类计数:')
for c, n in cls_count.most_common(60):
    print(f'   {c:52} {n}')
