import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import UnityPy, os, json, sys, binascii
sys.path.insert(0, TOOLS)
import decode
from decode import decode_object, Reader
import schema
from schema import load_type

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


def validate(cls, limit=None, verbose=False):
    lst = CACHE['objects'].get(cls, [])
    if limit:
        lst = lst[:limit]
    ok = bad = err = 0
    sizes = {}
    firstbad = None
    for fname, pid in lst:
        if (fname,pid) not in objs:
            continue
        raw = objs[(fname,pid)][1].get_raw_data()
        sizes[len(raw)] = sizes.get(len(raw),0)+1
        try:
            name, obj, end = decode_object(raw, cls)
            pad = raw[end:]
            if end == len(raw) or (len(pad) <= 3 and pad == b'\x00' * len(pad)):
                ok += 1
            else:
                bad += 1
                if firstbad is None:
                    firstbad = (fname,pid,len(raw),end,obj)
        except Exception as e:
            err += 1
            if firstbad is None:
                firstbad = (fname,pid,len(raw),'ERR',str(e))
    print(f'{cls}: n={len(lst)} exact_ok={ok} size_mismatch={bad} errors={err} sizes={sizes}')
    if firstbad and verbose:
        fname,pid,ln,end,obj = firstbad
        print('   first problem:', fname, pid, 'len',ln,'end',end)
        if isinstance(obj,dict):
            print('   ', json.dumps(obj, default=str)[:1200])
        else:
            print('   ', obj)
    return ok, bad, err


if __name__ == '__main__':
    for cls in sys.argv[1:]:
        validate(cls, verbose=True)
