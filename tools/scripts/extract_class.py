import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import re, sys

DUMP = DUMP_CS
_data = None

def load():
    global _data
    if _data is None:
        _data = open(DUMP, encoding='utf-8', errors='ignore').read()
    return _data

def extract_class(name, data=None):
    data = data or load()
    pat = re.compile(r'((?:\[.*?\]\s*\n\s*)*(?:public|internal)\s+(?:static\s+|abstract\s+|sealed\s+|partial\s+)*\b(?:class|struct|enum|interface)\s+' + re.escape(name) + r'\b[^\{]*)\{', re.M)
    m = pat.search(data)
    if not m:
        return None
    start = m.start()
    i = m.end() - 1
    depth = 0
    while i < len(data):
        if data[i] == '{': depth += 1
        elif data[i] == '}':
            depth -= 1
            if depth == 0: break
        i += 1
    return data[start:i+1]

if __name__ == '__main__':
    data = load()
    for n in sys.argv[1:]:
        c = extract_class(n, data)
        print('='*30, n, '='*30)
        print(c if c else 'NOT FOUND')
        print()
