import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import json
j = json.load(open(SCRIPT_JSON, encoding='utf-8'))
print('keys:', list(j.keys()))
for k in j.keys():
    v = j[k]
    print(k, type(v).__name__, (len(v) if hasattr(v,'__len__') else ''))
    if isinstance(v, list) and v:
        print('   sample:', json.dumps(v[0], ensure_ascii=False)[:200])
