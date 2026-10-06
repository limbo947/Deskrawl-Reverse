import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import UnityPy, os, json, sys, struct
sys.path.insert(0, TOOLS)
from decode import read_header
CACHE = json.load(open(ASSETS_CACHE))
BASE = GAME_DATA
env = UnityPy.load(os.path.join(BASE,'sharedassets0.assets'), os.path.join(BASE,'resources.assets'))
objs = {}
for fk, sf in env.files.items():
    fn = os.path.basename(getattr(sf,'name',str(fk)))
    for o in sf.objects.values():
        objs[(fn,o.path_id)] = o
samples=[]
for fn,pid in CACHE['objects']['Enemy'][:20]:
    raw = objs[(fn,pid)].get_raw_data()
    nm,e = read_header(raw)
    samples.append((nm,raw,e))

def i64(r,o): return struct.unpack_from('<q',r,o)[0]
def u32(r,o): return struct.unpack_from('<i',r,o)[0]

def plaus(v): return 1 <= v <= 20_000_000
print('=== long xor pairs')
best=[]
for ho in range(0,36,4):
    for ko in range(0,36,4):
        if ho==ko: continue
        good=0
        for nm,raw,e in samples:
            v = i64(raw,e+ho) ^ i64(raw,e+ko)
            if plaus(v): good+=1
        if good>=len(samples)*0.6:
            best.append((good,ho,ko))
for b in sorted(best, reverse=True)[:10]: print(b)
print('=== int xor pairs (value = int(h^key))')
best=[]
for ho in range(0,32,4):
    for ko in range(0,32,4):
        if ho==ko: continue
        good=0
        for nm,raw,e in samples:
            v = u32(raw,e+ho) ^ u32(raw,e+ko)
            if 1 <= v <= 20_000_000: good+=1
        if good>=len(samples)*0.6:
            best.append((good,ho,ko))
for b in sorted(best, reverse=True)[:10]: print(b)
print('=== raw values list for first 3 samples')
for nm,raw,e in samples[:3]:
    print(repr(nm), [i64(raw,e+i) for i in range(0,32,4)])
