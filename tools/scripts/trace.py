import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import UnityPy, os, json, sys, struct
sys.path.insert(0, TOOLS)
import decode as D
from decode import Reader, decode_value, read_header, Decoder
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
fname = sys.argv[2] if len(sys.argv)>2 else None
pid = int(sys.argv[3]) if len(sys.argv)>3 else None
if fname is None:
    fname, pid = CACHE['objects'][cls][0]
raw = objs[(fname,pid)].get_raw_data()
dec = Decoder()
nm, off = read_header(raw)
r = Reader(raw, off)
print('CLASS', cls, fname, pid, 'name', nm, 'start', off, 'len', len(raw))

def walk(t, r, indent=0, depth=0):
    pad = '  '*indent
    e = D._elem_of(t)
    if e is not None:
        r.align(4); n = r.i32()
        print(f'{pad}{t}: count={n} @{r.o-4}')
        if n > 300 or n < 0: raise ValueError('bad count')
        for i in range(n):
            r.align(D.align_of(e))
            if depth < 8 and D._elem_of(e) is None and e not in D.PRIM and e not in D.FIXED and not D.is_unity_object(e) and e not in D.OBSC_SIZES and not (load_type(e) and load_type(e)[0]=='enum'):
                print(f'{pad}  [{i}] {e} @{r.o}')
                walk_struct(e, r, indent+2, depth+1)
            else:
                v = decode_value(dec, e, r, depth)
                print(f'{pad}  [{i}] = {v}')
        return
    if t in D.PRIM or t in D.FIXED or D.is_unity_object(t) or t in D.OBSC_SIZES:
        v = decode_value(dec, t, r, depth)
        print(f'{pad}{t} = {v} @{r.o}')
        return
    if load_type(t) and load_type(t)[0]=='enum':
        v = decode_value(dec, t, r, depth); print(f'{pad}{t}(enum) = {v} @{r.o}'); return
    print(f'{pad}{t} @{r.o}')
    walk_struct(t, r, indent+1, depth+1)

def walk_struct(t, r, indent=0, depth=0):
    for f in serialized_fields(t):
        print(f'{"  "*indent}.{f["name"]} : {f["type"]}')
        walk(f['type'], r, indent+1, depth)

try:
    walk_struct(cls, r, 0, 0)
except Exception as ex:
    print('ERROR at', r.o, repr(ex))
print('END', r.o, 'len', len(raw))
