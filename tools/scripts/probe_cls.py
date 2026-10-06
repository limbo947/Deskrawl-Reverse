import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import UnityPy, os, json, sys
sys.path.insert(0, TOOLS)
import schema
from schema import load_type, serialized_fields
CACHE = json.load(open(ASSETS_CACHE))
BASE = GAME_DATA
env = UnityPy.load(os.path.join(BASE,'resources.assets'), os.path.join(BASE,'sharedassets0.assets'),
                   os.path.join(BASE,'globalgamemanagers.assets'), os.path.join(BASE,'level0'))
objs = {}
for fk, sf in env.files.items():
    fn = os.path.basename(getattr(sf,'name',str(fk)))
    for o in sf.objects.values():
        objs[(fn,o.path_id)] = o

cls = sys.argv[1]
print('BASE CHAIN fields for', cls)
for f in serialized_fields(cls):
    print('   ', f['type'], f['name'], 'SR' if any('SerializeReference' in a for a in f['attrs']) else '')
for fn,pid in CACHE['objects'].get(cls,[])[:3]:
    raw = objs[(fn,pid)].get_raw_data()
    print('====', fn, pid, 'len', len(raw))
    for i in range(0,len(raw),16):
        ch=raw[i:i+16]
        print(f'{i:4d}  '+' '.join(f'{b:02x}' for b in ch)+'  '+''.join(chr(b) if 32<=b<127 else '.' for b in ch))
