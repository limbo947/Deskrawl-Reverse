# -*- coding: utf-8 -*-
"""一次性探针：PlayerStatistics 单例字段语义实测（只读）。

动机：训练假人 DPS 计只在假人图存在；若 PlayerStatistics 的计数器是「玩家造成伤害累计」，
则 GUI 在任何战斗场景都能做差分 → 实战滚动 DPS。
字段（dump.cs）：odx double@0x28 / ody long@0x30 / odz long@0x38 / oea int@0x40；
单例 getter fmx() RVA 0x51C840。语义待本探针对照游戏「统计」面板确认。

用法：python probe_player_statistics.py [间隔秒]   # 默认采样 2 次、隔 3s
"""
import ctypes
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mem_probe import find_process, find_singleton, module_base, u32, u64, valid_ptr

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
GETTER_RVA = 0x51C840       # PlayerStatistics.fmx()
KLASS = 'PlayerStatistics'


def open_proc():
    pid = find_process('Deskrawl.exe')
    if not pid:
        raise SystemExit('未找到 Deskrawl.exe 进程')
    h = k32.OpenProcess(0x0410, False, pid)
    if not h:
        raise SystemExit(f'OpenProcess 失败 err={ctypes.get_last_error()}')
    return h, pid


def sample(h, base):
    inst = find_singleton(h, base, GETTER_RVA, KLASS)
    if not valid_ptr(inst):
        return None
    import struct
    def d(off):
        raw = read8(h, inst + off)
        return struct.unpack('<d', raw)[0] if raw else None
    def i(off):
        raw = read8(h, inst + off)
        return struct.unpack('<q', raw)[0] if raw else None
    return {'addr': inst, 'odx': d(0x28), 'ody': i(0x30), 'odz': i(0x38), 'oea': u32(h, inst + 0x40)}


def read8(h, addr):
    buf = ctypes.create_string_buffer(8)
    got = ctypes.c_size_t()
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, 8, ctypes.byref(got))
    return buf.raw if ok and got.value == 8 else None


def main():
    gap = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
    h, pid = open_proc()
    base = module_base(h, 'GameAssembly.dll')
    print(f'pid={pid} base={base:#x}')
    s1 = sample(h, base)
    print('采样1:', s1)
    time.sleep(gap)
    s2 = sample(h, base)
    print('采样2:', s2)
    if s1 and s2:
        print(f'\n差分（{gap}s）：Δodx={s2["odx"] - s1["odx"]:+.1f}  '
              f'Δody={s2["ody"] - s1["ody"]:+}  Δodz={s2["odz"] - s1["odz"]:+}  '
              f'Δoea={s2["oea"] - s1["oea"]:+}')
        print('对照：打一会怪再看本输出；若 Δodx/Δody 与你造成的伤害量级一致即为伤害累计。')


if __name__ == '__main__':
    main()
