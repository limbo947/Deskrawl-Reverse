import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import UnityPy, os, json, sys
sys.path.insert(0, TOOLS)
import decode
from decode import Reader, decode_value, _decode_fields, read_header, Decoder
from schema import serialized_fields
BASE = GAME_DATA
env = UnityPy.load(os.path.join(BASE,'resources.assets'))
objs = {}
for fk, sf in env.files.items():
    for o in sf.objects.values():
        objs[(os.path.basename(str(getattr(sf,'name',''))),o.path_id)] = o
fname, pid = 'resources.assets', int(sys.argv[1])
raw = objs[(fname,pid)].get_raw_data()
dec = Decoder()
nm, off = read_header(raw)
fields = serialized_fields('StatusEffectData')
r = Reader(raw, off)
out = {}
i=0
while i < len(fields):
    f = fields[i]
    if any('SerializeReference' in a for a in f['attrs']):
        r.align(4); pos=r.o; n=r.i32()
        print('SR field', f['name'], 'count', n, 'payload starts', r.o)
        break
    out[f['name']] = decode_value(dec, f['type'], r, 0)
    print('field', f['name'], '=', out[f['name']], '@', r.o)
    i+=1
start=r.o
total=len(raw)
print('remaining fields:', [f['name'] for f in fields[i+1:]])
for L in range(0, total-start+1, 4):
    r2 = Reader(raw, start+L)
    cand={}
    try:
        if _decode_fields(dec, fields[i+1:], r2, 0, cand):
            print('  L=',L,'end',r2.o,'total',total, 'OK' if r2.o==total or raw[r2.o:]==b'\x00'*(total-r2.o) else '', json.dumps(cand,default=str)[:200])
    except Exception as e:
        pass
