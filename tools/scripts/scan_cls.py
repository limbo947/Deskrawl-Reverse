import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import UnityPy, os, json, sys, struct
sys.path.insert(0, TOOLS)
from decode import read_header, Reader
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
show = int(sys.argv[2]) if len(sys.argv)>2 else 2
rows = []
for fn,pid in CACHE['objects'].get(cls,[]):
    raw = objs[(fn,pid)].get_raw_data()
    nm,end = read_header(raw)
    r = Reader(raw,end)
    r.o += 12  # Prerequisite
    mt = r.i32(); mn = r.i32(); mx = r.i32()
    b1 = raw[r.o]; b2 = raw[r.o+1]; r.o += 2
    r.align(4)
    cnt = r.i32()
    rows.append((cnt, nm, fn, pid, len(raw), end))
rows.sort()
for cnt,nm,fn,pid,ln,end in rows[:12]:
    print(f'count={cnt} {nm!r} {fn}/{pid} len={ln} eoff={end+32}')
print('--- dump first few with count 0')
n=0
for cnt,nm,fn,pid,ln,end in rows:
    if cnt==0 and n<show:
        raw = objs[(fn,pid)].get_raw_data()
        o = end+32
        print(f'==== {nm!r} {fn}/{pid} len={ln}')
        for i in range(o, min(ln,o+96), 16):
            ch=raw[i:i+16]
            print(f'{i:4d}  '+' '.join(f'{b:02x}' for b in ch)+'  '+''.join(chr(b) if 32<=b<127 else '.' for b in ch))
        n+=1
