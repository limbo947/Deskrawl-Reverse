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

def run(cls):
    from collections import Counter
    tail = Counter(); err = 0; over = 0
    for fname,pid in CACHE['objects'].get(cls,[]):
        raw = objs[(fname,pid)].get_raw_data()
        try:
            nm,obj,end = decode_object(raw,cls)
            left = len(raw)-end
            if left < 0: over += 1
            tail[left]+=1
        except Exception as e:
            err += 1
    print(cls, 'errors', err, 'over', over, 'leftover distribution', dict(sorted(tail.items())[:10]))

run('StatusEffectData')
run('AbilityData')
print(json.dumps(decode_object(objs[('resources.assets',5245)].get_raw_data(),'StatusEffectData')[1], indent=1, default=str)[:1500])
