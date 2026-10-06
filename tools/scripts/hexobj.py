import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import UnityPy, os, json, sys, struct
sys.path.insert(0, TOOLS)
from decode import read_header, decode_value, Reader
import schema
from schema import load_type, serialized_fields

BASE = GAME_DATA
env = UnityPy.load(os.path.join(BASE,'resources.assets'))
objs = {}
for fkey, sf in env.files.items():
    fname = os.path.basename(getattr(sf,'name',str(fkey)))
    for obj in sf.objects.values():
        objs[(fname, obj.path_id)] = (sf, obj)

key = ('resources.assets', int(sys.argv[1]) if len(sys.argv)>1 else 5244)
raw = objs[key][1].get_raw_data()
print('len', len(raw))
nm, off = read_header(raw); print('name', nm, 'hdr_end', off)
for i in range(0, min(len(raw), 160), 16):
    ch = raw[i:i+16]
    print(f'{i:4d}  ' + ' '.join(f'{b:02x}' for b in ch) + '  ' + ''.join(chr(b) if 32<=b<127 else '.' for b in ch))
print('--- schema fields SlaveData')
for f in serialized_fields('SlaveData'):
    print('   ', f['type'], f['name'])
