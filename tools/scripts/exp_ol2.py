import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import UnityPy, os, json, sys
sys.path.insert(0, TOOLS)
import decode
from decode import decode_object
CACHE = json.load(open(ASSETS_CACHE))
BASE = GAME_DATA
env = UnityPy.load(os.path.join(BASE,'resources.assets'), os.path.join(BASE,'sharedassets0.assets'),
                   os.path.join(BASE,'globalgamemanagers.assets'), os.path.join(BASE,'level0'))
objs = {}
for fk, sf in env.files.items():
    fn = os.path.basename(getattr(sf,'name',str(fk)))
    for o in sf.objects.values():
        objs[(fn,o.path_id)] = o
def validate(cls):
    ok=bad=err=0
    for fname,pid in CACHE['objects'].get(cls,[]):
        raw = objs[(fname,pid)].get_raw_data()
        try:
            nm,obj,end = decode_object(raw,cls)
            pad=raw[end:]
            if end==len(raw) or (len(pad)<=3 and pad==b'\x00'*len(pad)): ok+=1
            else: bad+=1
        except Exception: err+=1
    return ok,bad,err
print('baseline non-enemy sanity:')
for c in ['GameConfig','ItemData','HeroData','MapData','SlaveData','RuneSetData']:
    print(' ', c, validate(c))
best=[]
for OI in (12,16,20,24,28):
    for OL in (20,24,28,32,36,40):
        decode.OBSC_SIZES['ObscuredInt']=OI
        decode.OBSC_SIZES['ObscuredLong']=OL
        r = validate('Enemy')
        if r[0] > 0: print(f'OI={OI} OL={OL} -> {r}')
        best.append((r[0],OI,OL))
print('top:', sorted(best, reverse=True)[:6])
