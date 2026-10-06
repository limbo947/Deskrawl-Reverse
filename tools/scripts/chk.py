import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import struct
PE = GAME_ASSEMBLY
data = open(PE, 'rb').read()
pe = struct.unpack('<I', data[0x3c:0x40])[0]
nsec = struct.unpack('<H', data[pe+6:pe+8])[0]
optsz = struct.unpack('<H', data[pe+20:pe+22])[0]
so = pe + 24 + optsz
secs = []
for i in range(nsec):
    o = so + i*40
    name = data[o:o+8].rstrip(b'\0').decode(errors='ignore')
    vsize, vaddr, rawsize, rawoff = struct.unpack('<IIII', data[o+8:o+24])
    secs.append((name, vaddr, vsize, rawoff, rawsize))
for name, vaddr, vsize, rawoff, rawsize in secs:
    print(f'{name:10s} vaddr={vaddr:#x} vsize={vsize:#x} rawoff={rawoff:#x} rawsize={rawsize:#x}')

def rva2off(rva):
    for name, vaddr, vsize, rawoff, rawsize in secs:
        if vaddr <= rva < vaddr + max(vsize, rawsize):
            return rawoff + (rva - vaddr)
    return None

for rva in (0x39E4408, 0x39E4410, 0x39E4470, 0x39E4478, 0x39E44B0, 0x39E44C8):
    o = rva2off(rva)
    print(hex(rva), '-> fileoff', hex(o) if o else None, repr(data[o:o+48]) if o else '')
