import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import json, os, glob

D = SO_DUMP
files = sorted(glob.glob(os.path.join(D, '*.json')))
print('files:', len(files))
for f in files:
    try:
        j = json.load(open(f, encoding='utf-8'))
    except Exception as e:
        print(os.path.basename(f), 'ERR', e); continue
    n = len(j) if isinstance(j, list) else 1
    sample = j[0] if isinstance(j, list) and j else j
    keys = list(sample.keys()) if isinstance(sample, dict) else type(sample).__name__
    print(f'\n=== {os.path.basename(f)}  records={n}')
    print('   keys:', keys)
    print('   sample:', json.dumps(sample, ensure_ascii=False)[:400])
