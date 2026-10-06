import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import json, sys, bisect

_data = None
_rvas = None
_names = None

def load():
    global _data, _rvas, _names
    if _data is None:
        j = json.load(open(SCRIPT_JSON, encoding='utf-8'))
        items = [(m['Address'], m['Name'], m.get('Signature','')) for m in j['ScriptMethod']]
        items.sort()
        _data = items
        _rvas = [x[0] for x in items]

def find(rva):
    load()
    if isinstance(rva, str):
        rva = int(rva, 16)
    i = bisect.bisect_right(_rvas, rva) - 1
    if i >= 0:
        return _data[i]
    return None

if __name__ == '__main__':
    for a in sys.argv[1:]:
        r = find(a)
        print(a, '->', r[1] if r else '??', '|', r[2] if r else '')
