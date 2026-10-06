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
objs = {}
for fkey, sf in env.files.items():
    fname = os.path.basename(getattr(sf,'name',str(fkey)))
    for obj in sf.objects.values():
        objs[(fname, obj.path_id)] = (sf, obj)

def dump(cls, n=3):
    print('==============', cls)
    lst = CACHE['objects'].get(cls, [])
    for fname, pid in lst[:n]:
        raw = objs[(fname,pid)][1].get_raw_data()
        print(f'  {fname}/{pid} len={len(raw)}')
        for i in range(0, len(raw), 16):
            chunk = raw[i:i+16]
            hx = ' '.join(f'{b:02x}' for b in chunk)
            asc = ''.join(chr(b) if 32<=b<127 else '.' for b in chunk)
            print(f'    {i:4d}  {hx:<48} {asc}')

dump('RecipeData', 2)
dump('RuneSetData', 1)
dump('HeroData', 1)
