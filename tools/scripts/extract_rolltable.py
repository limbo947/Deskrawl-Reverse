import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
# -*- coding: utf-8 -*-
"""从 gg..cctor 提取"每级词条系数表" Dictionary<StatType,float>。"""
import struct
from capstone import *
from capstone.x86 import *

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
    vs, va, rs, ro = struct.unpack('<IIII', data[o+8:o+24])
    secs.append((va, max(vs, rs), ro))


def rva2off(rva):
    for va, vs, ro in secs:
        if va <= rva < va + vs:
            return ro + (rva - va)
    return None


def f32_at_va(va):
    o = rva2off(va - VA_BASE)
    return struct.unpack('<f', data[o:o+4])[0]


START, END = 0x787520, 0x788130          # RollTable.StaticInit（旧 gg..cctor）.. 下一方法（旧 gh.dnx → gi.dpj）
code = data[rva2off(START): rva2off(START) + (END - START)]
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

XMM_CONST = {}          # 记录 movss xmm6 / xmm7 的常量
key = None
val = None
pairs = []
for ins in md.disasm(code, VA_BASE + START):
    op = ins.op_str
    if ins.mnemonic == 'mov' and op.startswith('edx, '):
        v = op.split(', ')[1]
        if v[:1].isdigit() or v[:1] == '-':
            key = int(v, 0)
    elif ins.mnemonic == 'xor' and op.replace(' ', '') == 'edx,edx':
        key = 0
    elif ins.mnemonic in ('movss', 'movaps'):
        # movss xmm2, dword ptr [rip + X] / movaps xmm2, xmm6
        if op.startswith('xmm2, '):
            src = op.split(', ', 1)[1]
            if 'rip' in src:
                disp = int(src.split('+ ')[1].split(']')[0], 16)
                tgt = ins.address + ins.size + disp
                val = f32_at_va(tgt)
            elif src.startswith('xmm'):
                val = XMM_CONST.get(src)
        elif op.startswith(('xmm6, ', 'xmm7, ', 'xmm8, ')) and 'rip' in op:
            reg = op.split(', ')[0]
            disp = int(op.split('+ ')[1].split(']')[0], 16)
            XMM_CONST[reg] = f32_at_va(ins.address + ins.size + disp)
    elif ins.mnemonic == 'call' and key is not None and val is not None:
        pairs.append((key, val))
        key = None
        val = None
    if ins.mnemonic == 'ret' and len(pairs) > 5:
        break

import sys, json
sys.path.insert(0, TOOLS)
from deskrawl_calc.stattype import name as sname

print(f'提取到 {len(pairs)} 条系数：')
rows = []
for k, v in pairs:
    print(f'  StatType {k:>3}  {sname(k):<14} ×{v:.10g}')
    rows.append({'Stat': k, 'Name': sname(k), 'PerLevel': v})

out = {
    '_source': 'RollTable.StaticInit（旧 gg..cctor）@ RVA 0x787520 (Dictionary<StatType,float> mxt)',
    'formula': 'value = (1 + rarityMul) * (itemLevel * PerLevel[stat] (+5 if stat==20)) * rollFactor',
    'rollFactor': {'random': [0.85, 1.15], 'max': 1.15},
    'rarityMul': {'Common': 0.2, 'Uncommon': 0.4, 'Rare': 0.5, 'Legendary': 0.6, 'Divine': 0.0, 'RuneSet': 0.0},
    'min': 0.001,
    'entries': rows,
}
json.dump(out, open(os.path.join(SO_DUMP, 'AffixRollTable.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('\n写入 so_dump\\AffixRollTable.json')

