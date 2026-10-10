# -*- coding: utf-8 -*-
"""一次性探针：训练假人 DPS 计的内存定位链（只读）。

背景：TrainingDpsMeterUI 无静态类型引用，但 TrainingDummy.bmj（受击入口）尾调一个
静态事件/服务对象（用法槽 → Il2CppClass* → static_fields[+0x20] → 处理器对象）。
本探针沿这条链实测：枚举 bmj 用法槽的类名 → 展开 static+0x20 对象的字段 → 找到
klass=TrainingDpsMeterUI 的实例 → 读 [+0x50] 总伤害 / [+0x58] 开始时间（hww():
显示 DPS = 总伤害 / max(now-开始时间, 1.0)）。

验证锚：游戏画面 DPS 计「总伤害」肉眼可见（如 3.9B），读数必须一致。

用法：python probe_dps_meter.py
"""
import ctypes
import ctypes.wintypes as wintypes
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mem_probe import (cstr, find_process, f32, klass_name, module_base, read_mem,
                       scan_usage_slots, u32, u64, valid_ptr)

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
DUMMY_BMJ_RVA = 0x52B0B0      # dump.cs: TrainingDummy.bmj(long, bool) Slot 26
METER_KLASS = 'TrainingDpsMeterUI'
PROC = 'Deskrawl.exe'


def open_proc():
    pid = find_process(PROC)
    if not pid:
        raise SystemExit('未找到 Deskrawl.exe 进程（需在训练假人地图且 DPS 计可见）')
    h = k32.OpenProcess(0x0410, False, pid)   # 只读：QUERY_INFORMATION|VM_READ
    if not h:
        raise SystemExit(f'OpenProcess 失败 err={ctypes.get_last_error()}（管理员？）')
    return h, pid


def klass_of(h, klass_ptr):
    """Il2CppClass* → (namespace, name)。类指针直接 +0x10/+0x18 取名（比 klass_name 少一层解引用）。"""
    if not valid_ptr(klass_ptr):
        return None, None
    np_ = u64(h, klass_ptr + 0x10)
    sp_ = u64(h, klass_ptr + 0x18)
    return (cstr(h, sp_) if valid_ptr(sp_) else None,
            cstr(h, np_) if valid_ptr(np_) else None)


def main():
    h, pid = open_proc()
    base = module_base(h, 'GameAssembly.dll')
    print(f'pid={pid} base={base:#x}')

    # 1) bmj 用法槽 → 各槽的类名（找事件总线）
    print('\n== TrainingDummy.bmj 用法槽 ===')
    slots = scan_usage_slots(h, base, DUMMY_BMJ_RVA, span=256)
    cands = []
    for s in sorted(slots):
        v = u64(h, s)
        if not valid_ptr(v):
            continue
        ns, nm = klass_of(h, v)
        if nm:
            print(f'  slot {s:#x} → klass {ns}.{nm}')
            cands.append((s, v, ns, nm))

    # 2) 逐候选：static_fields → [+0x20] 处理器对象 → 深度 1-2 找 TrainingDpsMeterUI 实例
    for s, klass, ns, nm in cands:
        try:
            sf = u64(h, klass + 0xB8)
        except Exception:
            continue
        if not valid_ptr(sf):
            continue
        handler = u64(h, sf + 0x20)
        if not valid_ptr(handler):
            continue
        hns, hnm = klass_of(h, handler)
        print(f'\n== {ns}.{nm} static+0x20 → obj klass={hns}.{hnm} @ {handler:#x}')
        # 深度 1：处理器的实例字段（已知 +0x78 = System.Delegate[]）
        for off in range(0x0, 0x80, 8):
            p = u64(h, handler + off)
            if not (valid_ptr(p) and p != handler):
                continue
            ns2, nm2 = obj_klass(h, p)
            if nm2 and nm2 != hnm:
                print(f'  +{off:#04x} → {ns2}.{nm2} @ {p:#x}')
            if nm2 == METER_KLASS:
                dump_meter(h, p)
                return
            if nm2 == 'Delegate[]' or nm2 == 'MulticastDelegate[]':
                walk_delegates(h, p, tag=f'{hnm}+{off:#x}')
    print('\n未命中 TrainingDpsMeterUI：把上面输出交回分析。')


def obj_klass(h, obj):
    """对象指针 → (namespace, name)。"""
    k = u64(h, obj) if valid_ptr(obj) else None
    return klass_of(h, k) if valid_ptr(k) else (None, None)


def walk_delegates(h, arr, tag):
    """遍历委托数组（Il2CppArray: max_length@0x18, data@0x20），逐委托找 target=计量器。"""
    n = u32(h, arr + 0x18)
    print(f'\n== 委托数组 {tag} @ {arr:#x}，count={n}')
    for i in range(min(n, 32)):
        d = u64(h, arr + 0x20 + 8 * i)
        if not valid_ptr(d):
            continue
        dns, dnm = obj_klass(h, d)
        print(f'  [{i}] {dns}.{dnm} @ {d:#x}')
        for off in range(0x10, 0x60, 8):
            p = u64(h, d + off)
            if valid_ptr(p) and p != d and p != arr:
                ns2, nm2 = obj_klass(h, p)
                if nm2 and not nm2.startswith('System') and nm2 not in ('Delegate[]',):
                    print(f'       +{off:#04x} → {ns2}.{nm2} @ {p:#x}')
                if nm2 == METER_KLASS:
                    print(f'    *** 命中（委托 {i} +{off:#x}）***')
                    dump_meter(h, p)
                    raise SystemExit(0)


def dump_meter(h, p):
    """读计量器三字段（hww 口径：DPS = [+0x50] / max(now-[+0x58], 1.0)）。"""
    import struct
    raw50 = read_mem(h, p + 0x50, 8)
    raw58 = read_mem(h, p + 0x58, 8)
    raw60 = read_mem(h, p + 0x60, 8)
    pmk = struct.unpack('<d', raw50)[0] if raw50 else None
    pml = struct.unpack('<d', raw58)[0] if raw58 else None
    pmm = struct.unpack('<d', raw60)[0] if raw60 else None
    print(f'\n*** TrainingDpsMeterUI @ {p:#x}')
    print(f'  [+0x50] pmk 总伤害   = {pmk!r}')
    print(f'  [+0x58] pml 开始时间 = {pml!r}')
    print(f'  [+0x60] pmm          = {pmm!r}')
    print('  对照游戏 DPS 计「总伤害」应一致（如 3.9B）')


if __name__ == '__main__':
    main()
