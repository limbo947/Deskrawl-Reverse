# -*- coding: utf-8 -*-
"""一次性探针：RuneManager 符文槽布局实测（只读）。

RuneManager（dump.cs）：单例 getter ebx() RVA 0x7B97E0；字段 RuneData[] nje@0x30（6 槽）、
string[] njf@0x38、Dictionary<RuneSetData,int> njg@0x40。
本探针打印槽内 RuneData 的类名/名称、njf 字符串（疑似实例 UID）、套装字典条目，
用于确认「符文名 + 符文等级」的读取链。
"""
import ctypes
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mem_probe import (cstr, find_process, find_singleton, klass_name, module_base,
                       read_mem, u32, u64, valid_ptr, wstr)

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
GETTER_RVA = 0x7B97E0          # RuneManager.ebx()


def dump_list(h, ptr, label, limit=12):
    """Il2Cpp 数组/List 逐元素：打印指针与元素类名。"""
    if not valid_ptr(ptr):
        print(f'  {label}: 无效指针')
        return
    n = u32(h, ptr + 0x18)
    data = ptr + 0x20
    print(f'  {label}: len={n}')
    for i in range(min(n or 0, limit)):
        e = u64(h, data + 8 * i)
        nm = klass_name(h, e)[1] if valid_ptr(e) else None
        print(f'    [{i}] {e:#x} klass={nm}')


def main():
    pid = find_process('Deskrawl.exe')
    h = k32.OpenProcess(0x0410, False, pid)
    if not h:
        raise SystemExit('OpenProcess 失败')
    base = module_base(h, 'GameAssembly.dll')
    rm = find_singleton(h, base, GETTER_RVA, 'RuneManager')
    print('RuneManager 实例:', hex(rm) if valid_ptr(rm) else None)
    if not valid_ptr(rm):
        raise SystemExit('未定位 RuneManager（角色未加载？）')
    for off, label in ((0x30, 'RuneData[] nje'), (0x38, 'string[] njf')):
        ptr = u64(h, rm + off)
        print(f'\n+{off:#x} {label} = {hex(ptr) if valid_ptr(ptr) else None}')
        if not valid_ptr(ptr):
            continue
        n = u32(h, ptr + 0x18)
        print(f'  len = {n}')
        for i in range(min(n or 0, 8)):
            e = u64(h, ptr + 0x20 + 8 * i)
            if not valid_ptr(e):
                print(f'    [{i}] 空')
                continue
            ns, nm = klass_name(h, e)
            s = wstr(h, e, cap=64)
            print(f'    [{i}] {e:#x} klass={ns}.{nm}' + (f' str={s!r}' if s else ''))
    d = u64(h, rm + 0x40)
    print(f'\n+0x40 套装字典 = {hex(d) if valid_ptr(d) else None}')
    if valid_ptr(d):
        cnt = u32(h, d + 0x20)
        print('  count =', cnt)


if __name__ == '__main__':
    main()
