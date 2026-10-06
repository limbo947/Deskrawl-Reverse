import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import sys, struct
sys.path.insert(0, TOOLS)
import disasm
from find_method import find

def find_callers(target_rva):
    data = disasm.load()
    target_va = disasm.VA_BASE + target_rva
    results = []
    for vaddr, vsize, rawoff, rawsize, name in disasm._sections:
        if name != '.text':
            continue
        sec = data[rawoff:rawoff+rawsize]
        i = 0
        while True:
            i = sec.find(b'\xe8', i)
            if i < 0:
                break
            if i + 5 <= rawsize:
                rel = struct.unpack('<i', sec[i+1:i+5])[0]
                src_va = disasm.VA_BASE + vaddr + i
                dest = src_va + 5 + rel
                if dest == target_va:
                    results.append(src_va - VA_BASE)
            i += 1
    return results

if __name__ == '__main__':
    for t in sys.argv[1:]:
        t_rva = int(t, 16)
        callers = find_callers(t_rva)
        print(f'=== callers of {t} ({find(t_rva)}) ===')
        for c in callers:
            m = find(c)
            print(f'  {c:#x}  in  {m[1] if m else "??"}')
