import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import UnityPy, os, json, sys
sys.path.insert(0, TOOLS)
import decode
from decode import decode_object, Reader
BASE = GAME_DATA
env = UnityPy.load(os.path.join(BASE,'resources.assets'), os.path.join(BASE,'sharedassets0.assets'),
                   os.path.join(BASE,'globalgamemanagers.assets'), os.path.join(BASE,'level0'))
objs = {}
for fk, sf in env.files.items():
    fn = os.path.basename(getattr(sf,'name',str(fk)))
    for o in sf.objects.values():
        objs[(fn,o.path_id)] = o
cls = sys.argv[1]; fname = sys.argv[2]; pid = int(sys.argv[3])
raw = objs[(fname,pid)].get_raw_data()
try:
    nm, obj, end = decode_object(raw, cls)
    print('name', nm, 'end', end, 'len', len(raw))
    print(json.dumps(obj, indent=1, default=str)[:4000])
except Exception as e:
    print('ERR', repr(e))
