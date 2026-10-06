import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import UnityPy, os, json, sys, struct
sys.path.insert(0, TOOLS)
from decode import read_header
CACHE = json.load(open(ASSETS_CACHE))
BASE = GAME_DATA
env = UnityPy.load(os.path.join(BASE,'resources.assets'), os.path.join(BASE,'sharedassets0.assets'),
                   os.path.join(BASE,'globalgamemanagers.assets'), os.path.join(BASE,'level0'))
objs = {}
for fk, sf in env.files.items():
    fn = os.path.basename(getattr(sf,'name',str(fk)))
    for o in sf.objects.values():
        objs[(fn,o.path_id)] = o
def u32(r,o): return struct.unpack_from('<i',r,o)[0]
def f32(r,o): return struct.unpack_from('<f',r,o)[0]
def okfloat(v): return v == 0.0 or (1e-4 < v <= 1.0001)

data = []
for fn,pid in CACHE['objects']['MapData']:
    raw = objs[(fn,pid)].get_raw_data()
    nm,e = read_header(raw)
    data.append((nm,raw,e))
print('total', len(data))
for shift in (0,4,8,12):
    for E in (20,24,28,32,36):
        good=0; bad=0; ex=[]
        for nm,raw,e in data:
            o = e+28+shift
            if o+4 > len(raw): bad+=1; continue
            c = u32(raw,o)
            if c<0 or c>50: bad+=1; continue
            o2 = o+4+c*E
            if o2+12 > len(raw): bad+=1; continue
            me=u32(raw,o2); el=f32(raw,o2+4); pc=u32(raw,o2+8)
            if 0<=me<1000 and okfloat(el) and 0<=pc<200: good+=1
            else:
                bad+=1
                if len(ex)<4: ex.append((nm,c,me,el,pc))
        if good > 0.7*len(data):
            print(f'shift={shift} E={E} good={good} bad={bad} ex={ex}')
