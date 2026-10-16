# -*- coding: utf-8 -*-
"""一次性探针：读 StatisticsUI.hnk/hnm 引用的元数据槽内容（只读）——确认统计行标签。"""
import ctypes
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mem_probe import find_process, module_base, read_mem, u64, valid_ptr

k32 = ctypes.WinDLL('kernel32', use_last_error=True)

SLOTS = {
    'hnk#1': 0x183A64B90, 'hnk#2': 0x183A66578, 'hnk#3': 0x183A66570,
    'hnk#4': 0x183A6E7C8, 'hnk#5': 0x183A58008, 'hnm#clock': 0x183A5D560,
    'hnm#row_a': 0x183A64BE8,
}


def wstr(h, addr, cap=256):
    """il2cpp System.String：长度@0x10，字符@0x14（UTF-16）。"""
    raw = read_mem(h, addr + 0x10, 4)
    if not raw:
        return None
    n = int.from_bytes(raw, 'little')
    if not (0 < n < cap):
        return f'<len={n}>'
    body = read_mem(h, addr + 0x14, n * 2)
    return body.decode('utf-16-le', errors='replace') if body else None


def probe_slot(h, label, addr):
    v = u64(h, addr)
    if not valid_ptr(v):
        print(f'{label} {addr:#x} → 非指针/不可读')
        return
    k = u64(h, v)
    kn = None
    if valid_ptr(k):
        np_ = u64(h, k + 0x10)
        raw = read_mem(h, np_, 48) if valid_ptr(np_) else None
        kn = raw.split(b'\x00', 1)[0].decode('utf-8', 'replace') if raw else None
    text = wstr(h, v) if kn == 'String' else None
    print(f'{label} {addr:#x} → obj klass={kn}' + (f' text={text!r}' if text else ''))


def main():
    h = k32.OpenProcess(0x0410, False, find_process('Deskrawl.exe'))
    if not h:
        raise SystemExit('OpenProcess 失败')
    base = module_base(h, 'GameAssembly.dll')
    va_base = 0x180000000
    for label, va in SLOTS.items():
        probe_slot(h, label, base + (va - va_base))


if __name__ == '__main__':
    main()
