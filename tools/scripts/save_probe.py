import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import sys, os

P = GAME_SAVE
d = open(P, 'rb').read()
print('size =', len(d))
print('first 64 bytes hex :', d[:64].hex())
print('first 64 bytes repr:', d[:64])

# show a hexdump of first 256 bytes
def hexdump(b, base=0, n=256):
    for i in range(0, min(len(b), n), 16):
        chunk = b[i:i+16]
        hexs = ' '.join(f'{c:02x}' for c in chunk)
        asc = ''.join(chr(c) if 32 <= c < 127 else '.' for c in chunk)
        print(f'{base+i:08x}  {hexs:<47}  {asc}')

hexdump(d)
print('...')
print('last 32 bytes hex :', d[-32:].hex())

# byte histogram / entropy
from collections import Counter
c = Counter(d)
import math
ent = -sum((v/len(d))*math.log2(v/len(d)) for v in c.values())
print('entropy =', round(ent, 4), ' distinct bytes =', len(c))
