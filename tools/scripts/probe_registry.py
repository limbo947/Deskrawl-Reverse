import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
# -*- coding: utf-8 -*-
"""验证托管引用段(ManagedReference)的解析：
   [int32 A][int32 N] 之后，每条 = [u64 hash][string typeName][string ns][string asm][payload]
"""
import os, json, sys
sys.path.insert(0, TOOLS)
import decode
from decode import Reader, decode_value, decode_struct, read_header, Decoder
from schema import serialized_fields, load_type
import UnityPy

BASE = GAME_DATA
env = UnityPy.load(os.path.join(BASE, 'resources.assets'))
objs = {}
for fk, sf in env.files.items():
    for o in sf.objects.values():
        objs[(os.path.basename(str(getattr(sf, 'name', ''))), o.path_id)] = o


def fields_end(raw, cls):
    dec = Decoder()
    name, off = read_header(raw)
    r = Reader(raw, off)
    for f in serialized_fields(cls):
        if any('SerializeReference' in a for a in f['attrs']):
            r.align(4); cnt = r.i32()
            for _ in range(max(0, cnt)):
                r.align(4); r.raw(8)
            continue
        decode_value(dec, f['type'], r, 0)
    return name, r.o


def parse_registry(raw, start, end):
    r = Reader(raw, start)
    A = r.i32(); N = r.i32()
    out = [{'__hdr__': (A, N)}]
    for i in range(N):
        r.align(4)
        h = r.raw(8)
        tn = decode_value(None, 'string', r)
        ns = decode_value(None, 'string', r)
        asm = decode_value(None, 'string', r)
        rec = {'hash': h.hex(), 'type': tn, 'ns': ns, 'asm': asm, 'start': r.o}
        try:
            rec['fields'] = decode_struct(Decoder(), tn, r)
            rec['ok'] = True
        except Exception as e:
            rec['err'] = f'{type(e).__name__}: {e}'
            rec['ok'] = False
        rec['end'] = r.o
        out.append(rec)
    out.append({'__final_end__': r.o, '__end__': end})
    return out


for TARGET in (sys.argv[1:] or ['FireElementalMeteor', 'EnemyBasicAttackLongerRange']):
    rows = json.load(open(os.path.join(SO_DUMP, 'AbilityData.json'), encoding='utf-8'))
    rec = next((r for r in rows if r['_name'] == TARGET), None)
    if not rec:
        print('not found', TARGET); continue
    raw = objs[(rec['_file'], rec['_pathid'])].get_raw_data()
    nm, fe = fields_end(raw, 'AbilityData')
    print(f'\n===== {TARGET} ({nm}) len={len(raw)} fields_end={fe:#x} tail={len(raw)-fe} =====')
    reg = parse_registry(raw, fe, len(raw))
    for e in reg:
        if '__hdr__' in e:
            print('  header A,N =', e['__hdr__']); continue
        if '__final_end__' in e:
            print('  final_end =', hex(e['__final_end__']), 'file_end =', hex(e['__end__'])); continue
        print(f"  [{e['type']}] @{e['start']:#x}..{e['end']:#x} ok={e['ok']} ns={e['ns']!r} asm={e['asm']!r}")
        if e['ok']:
            print('      ', json.dumps(e['fields'], ensure_ascii=False, default=str)[:600])
        else:
            print('      ERR', e.get('err'))
