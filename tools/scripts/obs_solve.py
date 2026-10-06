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

def i64(r,o): return struct.unpack_from('<q',r,o)[0]
def u32(r,o): return struct.unpack_from('<I',r,o)[0]
def f32(r,o): return struct.unpack_from('<f',r,o)[0]

samples=[]
for fn,pid in CACHE['objects']['Enemy'][:12]:
    raw = objs[(fn,pid)].get_raw_data()
    nm,e = read_header(raw)
    samples.append((nm,raw,e))

def plausible(v): return 1 <= v <= 5_000_000

print('ObscuredLong candidates (BaseMaxHealth should be 1..5e6):')
for T in (20,24,28,32,36):
    for hp,hb,ho in ((4,8,8),(4,8,8),(8,8,8)):
        pass
    for (hp, kp) in ((4,12),(8,16),(4,13),(0,8),(4,8)):
        good=0; vals=[]
        for nm,raw,e in samples:
            h=i64(raw,e+hp); k=i64(raw,e+kp)
            v=h^k
            if plausible(v): good+=1
            vals.append(v)
        if good>=10:
            print(f'T={T} hiddenOff={hp} keyOff={kp} good={good} sample={vals[:3]}')

print('\nObscuredInt candidates (find class+field):')
# EquipmentEffect_AllStats? just sample ObscuredInt in Enemy? none. use any class with ObscuredInt
print('\nObscuredFloat layout probe (Enemy BaseMoveSpeed etc.) raw around offset:')
for nm,raw,e in samples[:2]:
    print(nm, [hex(u32(raw,e+i)) for i in range(0,72,4)])
