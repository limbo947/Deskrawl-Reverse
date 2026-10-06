import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import re, os

paths = [
    GAME_ASSEMBLY,
    GAME_METADATA,
]
# find candidate magic / crypto-related ascii strings
needles = [b'DDS2', b'DDS', b'save.json', b'AES', b'Rijndael', b'Rfc2898']

for p in paths:
    if not os.path.exists(p):
        print('MISSING', p); continue
    d = open(p, 'rb').read()
    print('===', p, 'size', len(d))
    for n in needles:
        idxs = []
        start = 0
        while True:
            i = d.find(n, start)
            if i < 0: break
            idxs.append(i)
            start = i + 1
            if len(idxs) > 12: break
        print(f'  {n!r}: {len(idxs)} hits', [hex(x) for x in idxs[:12]])
