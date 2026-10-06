import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import UnityPy, os, sys
sys.path.insert(0, TOOLS)
from decode import read_header
BASE = GAME_DATA
env = UnityPy.load(os.path.join(BASE,'sharedassets0.assets'))
fn = sys.argv[1] if len(sys.argv)>1 else 'sharedassets0.assets'
pid = int(sys.argv[2]) if len(sys.argv)>2 else 60934
n = int(sys.argv[3]) if len(sys.argv)>3 else 200
for fk,sf in env.files.items():
    if pid in sf.objects:
        raw = sf.objects[pid].get_raw_data()
        nm,e = read_header(raw)
        print('name',repr(nm),'hdr_end',e,'len',len(raw))
        for i in range(e, min(len(raw), e+n), 16):
            ch=raw[i:i+16]
            print(f'{i:4d}  '+' '.join(f'{b:02x}' for b in ch)+'  '+''.join(chr(b) if 32<=b<127 else '.' for b in ch))
        break
