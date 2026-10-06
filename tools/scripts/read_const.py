import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import struct
PE = GAME_ASSEMBLY
VA = 0x180000000
d = open(PE, 'rb').read()
pe = struct.unpack('<I', d[0x3c:0x40])[0]
ns = struct.unpack('<H', d[pe+6:pe+8])[0]
osz = struct.unpack('<H', d[pe+20:pe+22])[0]
so = pe + 24 + osz
secs = []
for i in range(ns):
    o = so+i*40
    n = d[o:o+8].rstrip(b'\0').decode('latin1')
    vs, va, rs, ro = struct.unpack('<IIII', d[o+8:o+24])
    secs.append((va, max(vs, rs), ro, n))
def off(rva):
    for va, vs, ro, n in secs:
        if va <= rva < va+vs:
            return ro + (rva-va)
    raise KeyError(hex(rva))
def f32(va):
    o = off(va-VA); return struct.unpack('<f', d[o:o+4])[0]
def f64(va):
    o = off(va-VA); return struct.unpack('<d', d[o:o+8])[0]

for va, label in [
    (0x18362a1a0, 'roll_high / default(1.0?)'),
    (0x18362a0e0, 'roll_low'),
    (0x183629f64, 'rarity0 mult'),
    (0x183629ff8, 'rarity1 mult'),
    (0x18362a028, 'rarity2 mult'),
    (0x18362a050, 'rarity3 mult'),
    (0x18362a160, 'const (1.0?)'),
    (0x18362a658, 'round scale'),
    (0x183629e40, 'min value'),
    (0x18362a3c0, 'WeaponDamage additive'),
]:
    try:
        print(f'{va:#x}  f32={f32(va):<22g} f64={f64(va):g}   {label}')
    except Exception as e:
        print(va, 'ERR', e)
