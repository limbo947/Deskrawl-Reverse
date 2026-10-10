# -*- coding: utf-8 -*-
"""一次性探针：巅峰状态容器（静态类 static_fields[+0x40]）实测（只读）。

dyt(StatType) 反汇编：klass(usage slot) → static_fields[+0x40] → 按 StatType 查点数。
本探针 dump 该对象的类名与字段，确认容器类型与条目布局。
"""
import ctypes
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mem_probe import (find_process, module_base, read_mem, u32, u64, valid_ptr)

k32 = ctypes.WinDLL('kernel32', use_last_error=True)

# dzg/dyt 共用的状态类 usage slot（VA → 运行时重定位）
STATE_SLOT_VA = 0x183A1BF88


def klass_name_of_obj(h, obj):
    k = u64(h, obj) if valid_ptr(obj) else None
    if not valid_ptr(k):
        return None
    np_ = u64(h, k + 0x10)
    raw = read_mem(h, np_, 64) if valid_ptr(np_) else None
    return raw.split(b'\x00', 1)[0].decode('utf-8', 'replace') if raw else None


def wstr(h, addr, cap=64):
    raw = read_mem(h, addr + 0x10, 4)
    if not raw:
        return None
    n = int.from_bytes(raw, 'little')
    if not (0 < n < cap):
        return None
    body = read_mem(h, addr + 0x14, n * 2)
    return body.decode('utf-16-le', errors='replace') if body else None


def main():
    h = k32.OpenProcess(0x0410, False, find_process('Deskrawl.exe'))
    if not h:
        raise SystemExit('OpenProcess 失败')
    base = module_base(h, 'GameAssembly.dll')
    slot = base + (STATE_SLOT_VA - 0x180000000)
    klass = u64(h, slot)
    if not valid_ptr(klass):
        raise SystemExit('状态类槽不可读')
    print(f'状态类 @ {klass:#x} name={klass_name_of_obj(h, klass)}')
    sf = u64(h, klass + 0xB8)
    print(f'static_fields @ {sf:#x}')
    for off in range(0x0, 0x80, 8):
        p = u64(h, sf + off)
        if not valid_ptr(p):
            continue
        nm = klass_name_of_obj(h, p)
        print(f'  static+{off:#04x} → {p:#x} klass={nm}')
        if nm == 'Dictionary`2':
            from mem_probe import list_of
            entries_ptr = u64(h, p + 0x18)      # Dictionary.entries 引用
            count = int.from_bytes(read_mem(h, p + 0x20, 4) or b'\0\0\0\0', 'little')
            print(f'    Dictionary count={count} entries@{entries_ptr:#x}')
            # il2cpp Dictionary: buckets@0x10? entries@0x18, count@0x20, 步长见实测
            for i in range(min(count, 80)):
                ent = entries_ptr + 0x20 + i * 0x18      # 假设 stride 0x18（hash/key/value）
                key = u32(h, ent + 0x8)
                val = u32(h, ent + 0x10)
                if key or val:
                    print(f'    [{i}] key(stat)={key} value(points)={val}')
        elif nm and 'Paragon' in str(nm):
            for o2 in range(0x10, 0x60, 8):
                q = u64(h, p + o2)
                if valid_ptr(q):
                    print(f'    +{o2:#04x} → {q:#x} klass={klass_name_of_obj(h, q)}')


if __name__ == '__main__':
    main()
