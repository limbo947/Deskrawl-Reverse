import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import UnityPy, os, json, sys, struct
sys.path.insert(0, TOOLS)
from decode import read_header
CACHE = json.load(open(ASSETS_CACHE))
BASE = GAME_DATA
env = UnityPy.load(os.path.join(BASE,'sharedassets0.assets'))
objs = {}
for fk, sf in env.files.items():
    fn = os.path.basename(getattr(sf,'name',str(fk)))
    for o in sf.objects.values():
        objs[(fn,o.path_id)] = o
samples=[]
for fn,pid in CACHE['objects']['Enemy'][:40]:
    raw = objs[(fn,pid)].get_raw_data()
    nm,e = read_header(raw)
    samples.append((nm,raw,e))
def i32(r,o): return struct.unpack_from('<i',r,o)[0]
def i64(r,o): return struct.unpack_from('<q',r,o)[0]

# _level is the first field, ObscuredInt total 12 => try int xor pairs inside e..e+12
print('== ObscuredInt _level (expect 1..100) int pairs within first 12 bytes')
for ho in range(0,13,4):
    for ko in range(0,13,4):
        if ho==ko: continue
        good=sum(1 for nm,raw,e in samples if 1 <= (i32(raw,e+ho)^i32(raw,e+ko)) <= 100)
        if good>len(samples)*0.7: print('   ho',ho,'ko',ko,'good',good)
print('   raw first 12 bytes as ints (3 samples):')
for nm,raw,e in samples[:3]:
    print('   ', nm, [i32(raw,e+i) for i in range(0,12,4)])
# BaseMaxHealth is second field (ObscuredLong 20 bytes) starting at e+12
print('== ObscuredLong BaseMaxHealth (expect 1..1e7) long pairs within e+12..e+32')
for ho in range(12,33,4):
    for ko in range(12,33,4):
        if ho==ko: continue
        good=sum(1 for nm,raw,e in samples if 1 <= (i64(raw,e+ho)^i64(raw,e+ko)) <= 10000000)
        if good>len(samples)*0.7: print('   ho',ho,'ko',ko,'good',good)
print('   raw ints e+12..e+36 (2 samples):')
for nm,raw,e in samples[:2]:
    print('   ', nm, [hex(i32(raw,e+i)&0xffffffff) for i in range(12,40,4)])
