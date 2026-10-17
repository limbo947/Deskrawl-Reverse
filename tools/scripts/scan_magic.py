import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import os, sys

_HOME = os.path.expanduser('~')
ROOTS = [
    GAME_DIR,
    os.environ.get('DESKRAWL_STEAM_USERDATA', ''),   # Steam userdata 目录因人而异，需自行设
    os.path.join(_HOME, 'AppData', 'LocalLow', 'First Day Games', 'Deskrawl'),
    os.path.join(_HOME, 'Documents'),
    os.path.join(_HOME, 'Saved Games'),
]
SKIP_DIR = {'Unity', 'node_modules', '.git', 'Temp', 'Cache', 'cache'}
MAX = 40 * 1024 * 1024
found = []
scanned = 0
for root in ROOTS:
    if not os.path.isdir(root):
        continue
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIR and not d.startswith('.')]
        for fn in fns:
            p = os.path.join(dp, fn)
            try:
                if os.path.getsize(p) > MAX or os.path.getsize(p) < 8:
                    continue
                with open(p, 'rb') as f:
                    head = f.read(8)
                scanned += 1
                if head[:4] == b'DDS2' or head[:4] == b'DDS1':
                    found.append((p, head[:4], os.path.getsize(p)))
            except Exception:
                pass
print('scanned files:', scanned)
print('--- DDS1/DDS2 magic hits ---')
for p, m, s in found:
    print(f'  {m.decode()}  {s:>8}  {p}')
if not found:
    print('  (none)')
