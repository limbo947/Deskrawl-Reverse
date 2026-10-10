# -*- coding: utf-8 -*-
"""③-13 探针：实机定位 Player+0x230（当前构建字段名 nza）的「逐技能等级」容器结构。

为什么先探针再动导入链：GUI 秒伤目前全表共用 profile.skill_level 单一等级，而
「接入逐技能等级」的复核条件指向 Player+0x230——旧构建叫 nst，补丁后改名 nza，
且**容器类型不明**（Dictionary<AbilityData,int> 还是 List<T>）。按猜的布局直接写进
memory_import 违背「宁可红不出脏」：结构必须实机自证（类名 + 键类型 + 值域三重）。

只读约束：仅 OpenProcess(0x0410) + ReadProcessMemory（全部经 mem_probe 的基元）。
用法：python probe_skill_levels.py   （需游戏运行中且已进图）
"""
import ctypes
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mem_probe as mp

PLAYER_ABILITY_LEVELS = 0x230   # Player.nza（旧 nst）：逐技能等级容器（待证）
HERO_ABILITIES = 0x50           # HeroData.abilities：List<AbilityData>（已入 offsets 表）


def _klass(h, p):
    """对象类名；读不出返回 None（调用方据此决定是否继续解引用）。"""
    if not mp.valid_ptr(p):
        return None
    kn, _ = mp.klass_name(h, p)
    return kn


def dump_list(h, lst, limit=40):
    first, n = mp.list_of(h, lst)
    print(f'    List count={n}')
    for i in range(min(n or 0, limit)):
        e = mp.elem(h, first, i)
        kn = _klass(h, e)
        if kn is None:
            print(f'      [{i}] <不可读> 0x{e:X}')
            continue
        # 元素是类实例时连字段区前几个 4/8 字节一起打，便于认出「Ability 指针 + 等级 int」
        i32s = [mp.i32(h, e + o) for o in (0x8, 0xC, 0x10, 0x14, 0x18, 0x1C, 0x20)]
        print(f'      [{i}] 0x{e:X} klass={kn!r} i32[8..0x20]={[v for v in i32s]}')


def dump_dict(h, d, key_of=None):
    """Dictionary 探查：Entry 步长按键值类型对齐推算（AbilityData*,int → 0x18）。

    为什么要试多个步长：IL2CPP 的 Entry 布局是 {next,hash,key,value}，步长由 V 的
    对齐决定；stat_dict 只覆盖 <enum,ObscuredDouble>（0x38），这里的 V 若是 int 则 0x18。
    键类型自证（klass_name == AbilityData）通过才认，不通过就换步长，避免读到脏值。
    """
    nm = _klass(h, d) or ''
    if not nm.startswith('Dictionary'):
        return False
    count = mp.i32(h, d + 0x20)
    entries = mp.u64(h, d + 0x18)
    print(f'    {nm} count={count} entries=0x{entries or 0:X}')
    if not mp.valid_ptr(entries) or not count or count <= 0 or count > 4096:
        return True
    for stride in (0x18, 0x20, 0x28, 0x38):
        e0 = entries + 0x20 + stride * 0
        key = mp.u64(h, e0 + 8)
        if _klass(h, key) == 'AbilityData' or key_of and key_of(h, key):
            print(f'    （stride=0x{stride:X}：key=AbilityData* 自证通过）')
            free = 0
            for i in range(min(count, 40)):
                e = entries + 0x20 + stride * i
                nxt = mp.i32(h, e)
                if nxt is None or nxt < -1:
                    free += 1
                    continue
                k = mp.u64(h, e + 8)
                v = mp.i32(h, e + 0x10)
                print(f'      [{i}] key=0x{k:X} klass={_klass(h, k)!r} value={v}')
            if free:
                print(f'      （空闲墓碑 {free} 条已跳过）')
            return True
        print(f'    （stride=0x{stride:X} 键类型不符：{_klass(h, key)!r}，换下一个）')
    return True


def main():
    pid = mp.find_process('Deskrawl.exe')
    if not pid:
        print('未找到 Deskrawl.exe —— 请先启动游戏并进入角色。')
        return 2
    h = ctypes.windll.kernel32.OpenProcess(
        mp.PROCESS_QUERY_INFORMATION | mp.PROCESS_VM_READ, False, pid)
    if not h:
        print(f'OpenProcess 失败 err={ctypes.windll.kernel32.GetLastError()}')
        return 2
    try:
        base = mp.module_base(h, 'GameAssembly.dll')
        if not base:
            print('未找到 GameAssembly.dll')
            return 2
        found = {want: mp.find_singleton(h, base, rva, want)
                 for _, rva, want in mp.SINGLETON_GETTERS}
        gm = found.get('GameManager')
        player = None
        if mp.valid_ptr(gm):
            pcc = mp.u64(h, gm + 0x40)       # GameManager.PlayerCombatController @0x40
            if mp.valid_ptr(pcc):
                player = mp.u64(h, pcc + 0x20)  # PlayerCombatController.Player @0x20
        if not mp.valid_ptr(player):
            print('Player 不可达（未进图？）')
            return 3
        print(f'Player @0x{player:X}')

        c = mp.u64(h, player + PLAYER_ABILITY_LEVELS)
        kn = _klass(h, c)
        print(f'[Player+0x{PLAYER_ABILITY_LEVELS:X}] = 0x{c:X} klass={kn!r}')
        if kn and kn.startswith('List'):
            dump_list(h, c)
        elif kn and kn.startswith('Dictionary'):
            dump_dict(h, c)
        elif kn:
            # 兜底：非容器就打前 0x40 字节原始值，供人工判型（不猜结构）
            raw = mp.read_mem(h, c, 0x40)
            print(f'    非容器（原始字节）：{raw.hex() if raw else "<不可读>"}')
        else:
            print('    容器为空（未学任何技能等级？）')

        # 对照：英雄技能表（键集合应与之对应，便于把 AbilityData* 映射回技能名）
        hd = mp.u64(h, gm + 0x38)          # GameManager.HeroData @0x38
        if mp.valid_ptr(hd):
            kn_h = _klass(h, hd)
            ab = mp.u64(h, hd + HERO_ABILITIES)
            n = mp.i32(h, ab + 0x18) if mp.valid_ptr(ab) else None
            print(f'[HeroData({kn_h!r}).abilities @0x{HERO_ABILITIES:X}] count={n}')
            if n:
                first, _ = mp.list_of(h, ab)
                for i in range(min(n, 20)):
                    a = mp.elem(h, first, i)
                    nm_p = mp.u64(h, a + 0x18) if mp.valid_ptr(a) else 0
                    nm = mp.wstr(h, nm_p) if mp.valid_ptr(nm_p) else None
                    print(f'      [{i}] 0x{a:X} AbilityName={nm!r}')
        return 0
    finally:
        ctypes.windll.kernel32.CloseHandle(h)


if __name__ == '__main__':
    sys.exit(main())
