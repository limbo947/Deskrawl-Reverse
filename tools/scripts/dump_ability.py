import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
# -*- coding: utf-8 -*-
"""打印 AbilityData 每个字段的起止偏移 + 尾部（SR 载荷与类型注册表）完整 hexdump。"""
import os, json, sys, struct
sys.path.insert(0, TOOLS)
import decode
from decode import Reader, decode_value, decode_struct, read_header, Decoder
from schema import serialized_fields
import UnityPy

BASE = GAME_DATA
env = UnityPy.load(os.path.join(BASE, 'resources.assets'))
objs = {}
for fk, sf in env.files.items():
    for o in sf.objects.values():
        objs[(os.path.basename(str(getattr(sf, 'name', ''))), o.path_id)] = o

rows = json.load(open(os.path.join(SO_DUMP, 'AbilityData.json'), encoding='utf-8'))
TARGET = sys.argv[1] if len(sys.argv) > 1 else 'FireElementalMeteor'
rec = next(r for r in rows if r['_name'] == TARGET)
raw = objs[(rec['_file'], rec['_pathid'])].get_raw_data()
print('==', TARGET, rec['_file'], rec['_pathid'], 'len', len(raw))


def hexdump(b, base=0, n=1 << 20):
    for i in range(0, min(len(b), n), 16):
        ch = b[i:i+16]
        print(f'{base+i:04x}  ' + ' '.join(f'{c:02x}' for c in ch).ljust(47) + '  ' +
              ''.join(chr(c) if 32 <= c < 127 else '.' for c in ch))


dec = Decoder()
name, off = read_header(raw)
r = Reader(raw, off)
print('--- fields ---')
sr_end = None
for f in serialized_fields('AbilityData'):
    s = r.o
    if any('SerializeReference' in a for a in f['attrs']):
        r.align(4); cnt = r.i32()
        keys = [r.raw(8) for _ in range(max(0, cnt))]
        print(f'{s:04x}->{r.o:04x}  SR {f["name"]} count={cnt} keys={[k.hex() for k in keys]}')
        sr_end = r.o
        continue
    v = decode_value(dec, f['type'], r, 0)
    sv = json.dumps(v, default=str)
    print(f'{s:04x}->{r.o:04x}  {f["type"]:<22} {f["name"]:<28} {sv[:60]}')
print('fields end =', hex(r.o), 'len =', hex(len(raw)), 'leftover =', len(raw) - r.o)
print('--- tail (from fields end) ---')
hexdump(raw[r.o:], r.o)
