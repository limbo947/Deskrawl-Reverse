import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import UnityPy, os, json, binascii

BASE = GAME_DATA
CACHE = json.load(open(ASSETS_CACHE))

env = UnityPy.load(os.path.join(BASE,'resources.assets'),
                   os.path.join(BASE,'sharedassets0.assets'),
                   os.path.join(BASE,'globalgamemanagers.assets'),
                   os.path.join(BASE,'level0'))

# map (fname,pathid) -> obj
objs = {}
for fkey, sf in env.files.items():
    fname = os.path.basename(getattr(sf,'name',str(fkey)))
    for obj in sf.objects.values():
        objs[(fname, obj.path_id)] = (sf, obj)

def get(cls, n=5):
    res = []
    lst = CACHE['objects'].get(cls, [])
    for fname, pid in lst[:n]:
        if (fname,pid) in objs:
            res.append(((fname,pid), objs[(fname,pid)]))
    return res

for cls in ['GameConfig','HeroData','RecipeData','RuneSetData']:
    print('==============', cls)
    for key, (sf, obj) in get(cls):
        raw = obj.get_raw_data()
        print(f'  {key} len={len(raw)} head={binascii.hexlify(raw[:64]).decode()}')
    # also list sizes of all instances
    sizes = {}
    for fname,pid in CACHE['objects'].get(cls,[]):
        if (fname,pid) in objs:
            raw = objs[(fname,pid)][1].get_raw_data()
            sizes.setdefault(len(raw),[]).append(pid)
    print('  size distribution:', {k:len(v) for k,v in sizes.items()})
