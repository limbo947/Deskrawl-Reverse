import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import struct, json, bisect

PE = GAME_ASSEMBLY
VA_BASE = 0x180000000
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

def off2va(off):
    for name, vaddr, vsize, rawoff, rawsize in secs:
        if rawoff <= off < rawoff + rawsize:
            return VA_BASE + vaddr + (off - rawoff)
    return None

def va2off(va):
    rva = va - VA_BASE
    for name, vaddr, vsize, rawoff, rawsize in secs:
        if vaddr <= rva < vaddr + max(vsize, rawsize):
            return rawoff + (rva - vaddr)
    return None

# method table for naming
j = json.load(open(SCRIPT_JSON, encoding='utf-8'))
meth = sorted((m['Address'], m['Name']) for m in j['ScriptMethod'])
maddr = [x[0] for x in meth]
def mname(rva):
    i = bisect.bisect_right(maddr, rva) - 1
    if i >= 0:
        return meth[i]
    return (None, None)

targets = {
    'password': 0x1839e44c8,
    'password|mac': 0x1839e44b0,
    'DDS1': 0x1839e4470,
    'DDS2': 0x1839e4478,
    'SaveFileWriter:': 0x1839e4408,
    '.tmp': 0x1839e4410,
}

# find .text section
texts = [s for s in secs if s[0] == '.text']
print('text sections:', [(s[0], hex(s[1]), hex(s[4])) for s in texts])

for label, tva in targets.items():
    hits = []
    for name, vaddr, vsize, rawoff, rawsize in texts:
        base = rawoff; end = rawoff + rawsize
        buf = data
        for i in range(base, end-6):
            b0 = buf[i]
            # lea r64, [rip+disp32] : 48/4C 8D <modrm with rim=101>
            if b0 in (0x48, 0x4C) and buf[i+1] == 0x8D and (buf[i+2] & 0xC7) == 0x05:
                disp = struct.unpack('<i', buf[i+3:i+7])[0]
                va = off2va(i)
                tgt = va + 7 + disp
                if tgt == tva:
                    hits.append(va)
            # mov r64, [rip+disp32] : 48/4C 8B ...
            elif b0 in (0x48, 0x4C) and buf[i+1] == 0x8B and (buf[i+2] & 0xC7) == 0x05:
                disp = struct.unpack('<i', buf[i+3:i+7])[0]
                va = off2va(i)
                tgt = va + 7 + disp
                if tgt == tva:
                    hits.append(va)
    print(f'\n{label} ({tva:#x}): {len(hits)} refs')
    for h in hits[:20]:
        rva = h - VA_BASE
        a, nm = mname(rva)
        print(f'  ref @ {h:#x} (rva {rva:#x})  in {nm} (+{rva-a:#x})' if a else f'  ref @ {h:#x}')
