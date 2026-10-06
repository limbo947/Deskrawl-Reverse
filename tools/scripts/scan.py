import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import sys, struct
sys.path.insert(0, TOOLS)
import disasm
from capstone import *
from capstone.x86 import *

def scan(start_rva, end_rva, needle):
    data = disasm.load()
    off = disasm.rva2off(start_rva)
    size = end_rva - start_rva
    code = data[off:off+size]
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = False
    for ins in md.disasm(code, disasm.VA_BASE + start_rva):
        s = f"{ins.mnemonic} {ins.op_str}"
        if needle in s:
            print(f"{ins.address:#x}: {s}")

if __name__ == '__main__':
    a = int(sys.argv[1], 16); b = int(sys.argv[2], 16); n = sys.argv[3]
    scan(a, b, n)
