import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import sys, struct, json, bisect
from capstone import *
from capstone.x86 import *

PE_PATH = GAME_ASSEMBLY
VA_BASE = 0x180000000
_data = None
_sections = None

# method table
_meth = None
_meth_addr = None

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

def load_meth():
    global _meth, _meth_addr
    if _meth is None:
        j = json.load(open(SCRIPT_JSON, encoding='utf-8'))
        items = [(m['Address'], m['Name']) for m in j['ScriptMethod']]
        items.sort()
        _meth = items
        _meth_addr = [x[0] for x in items]

def meth_at(rva):
    load_meth()
    i = bisect.bisect_right(_meth_addr, rva) - 1
    if i >= 0:
        return _meth[i]
    return (None, None)

def rva2off(rva):
    load()
    for vaddr, vsize, rawoff, rawsize, name in _sections:
        if vaddr <= rva < vaddr + max(vsize, rawsize):
            return rawoff + (rva - vaddr)
    return rva

def read_bytes_va(va, n):
    off = rva2off(va - VA_BASE)
    return _data[off:off+n]

def read_cstr_va(va, n=64):
    b = read_bytes_va(va, n)
    z = b.find(b'\0')
    if z >= 0: b = b[:z]
    try:
        return b.decode('utf-8', errors='replace')
    except Exception:
        return None

def disasm(rva, size=0x400):
    load(); load_meth()
    off = rva2off(rva)
    code = _data[off:off+size]
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    for ins in md.disasm(code, VA_BASE + rva):
        extra = ''
        # rip-relative
        for op in ins.operands:
            if op.type == CS_OP_MEM and op.mem.base == X86_REG_RIP:
                target = ins.address + ins.size + op.mem.disp
                extra += f'  ; -> {target:#x}'
                try:
                    s = read_cstr_va(target, 40)
                    if s and s.isprintable() and len(s) >= 2:
                        extra += f' str="{s}"'
                except Exception:
                    pass
            if op.type == CS_OP_IMM and ins.mnemonic == 'call':
                pass
        if ins.mnemonic == 'call':
            for op in ins.operands:
                if op.type == CS_OP_IMM:
                    tgt = op.imm
                    sl = tgt - VA_BASE
                    if 0 <= sl < 0x8000000:
                        a, nm = meth_at(sl)
                        if nm and a == sl:
                            extra += f'  ; => {nm}'
        print(f"{ins.address:#x}: {ins.mnemonic:10s} {ins.op_str}{extra}")

if __name__ == '__main__':
    rva = int(sys.argv[1], 16)
    size = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x400
    disasm(rva, size)
