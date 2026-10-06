import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import sys, struct
from capstone import *
from capstone.x86 import *

PE_PATH = GAME_ASSEMBLY
_data = None
_sections = None
VA_BASE = 0x180000000

def load():
    global _data, _sections
    if _data is None:
        _data = open(PE_PATH, 'rb').read()
        pe_off = struct.unpack('<I', _data[0x3c:0x40])[0]
        num_sections = struct.unpack('<H', _data[pe_off+6:pe_off+8])[0]
        opt_size = struct.unpack('<H', _data[pe_off+20:pe_off+22])[0]
        sec_off = pe_off + 24 + opt_size
        _sections = []
        for i in range(num_sections):
            o = sec_off + i*40
            name = _data[o:o+8].rstrip(b'\0').decode(errors='ignore')
            vsize, vaddr, rawsize, rawoff = struct.unpack('<IIII', _data[o+8:o+24])
            _sections.append((vaddr, vsize, rawoff, rawsize, name))
    return _data

def rva2off(rva):
    load()
    for vaddr, vsize, rawoff, rawsize, name in _sections:
        if vaddr <= rva < vaddr + max(vsize, rawsize):
            return rawoff + (rva - vaddr)
    return rva  # fallback (header)

def read_double_at_va(va):
    off = rva2off(va - VA_BASE)
    return struct.unpack('<d', _data[off:off+8])[0]

def read_float_at_va(va):
    off = rva2off(va - VA_BASE)
    return struct.unpack('<f', _data[off:off+4])[0]

def disasm(rva, size=0x400):
    load()
    off = rva2off(rva)
    code = _data[off:off+size]
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    for ins in md.disasm(code, VA_BASE + rva):
        extra = ''
        # resolve rip-relative memory operands
        for op in ins.operands:
            if op.type == CS_OP_MEM and op.mem.base == X86_REG_RIP:
                target = ins.address + ins.size + op.mem.disp
                extra = f'  ; -> {target:#x}'
                try:
                    if ins.mnemonic in ('movsd','movaps','comisd'):
                        extra += f'  double={read_double_at_va(target)}'
                    elif ins.mnemonic in ('movss','comiss','addss','mulss','subss'):
                        extra += f'  float={read_float_at_va(target)}'
                except Exception:
                    pass
        print(f"{ins.address:#x}: {ins.mnemonic:10s} {ins.op_str}{extra}")

if __name__ == '__main__':
    rva = int(sys.argv[1], 16)
    size = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x400
    disasm(rva, size)
