# -*- coding: utf-8 -*-
"""P0 spike：联机角色数据内存导入可行性验证（严格只读）。

对应《联机角色数据内存导入可行性调研》§8 Phase 0：
  定位 SaveSystem 静态单例 nfi -> SaveContainer nfn -> OnlineSlots[i].Data，打印摘要。

只读边界（硬约束，验收条款）：
  - 仅 OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ) + ReadProcessMemory
  - 不写目标内存、不注入、不创建远程线程、不挂起/恢复线程、不调试附加
  - 不访问游戏目录文件、不发送网络请求

定位链（全部来自 data/schema/dump.cs，当前构建）：
  1) 锚点方法 RVA（反汇编前 192B 扫 rip 相对加载 -> 元数据用法槽）：
       2026-10-16 补丁 1.0.3 后按「类+签名+Slot」在新 dump 重算（旧名→新名见 docs/08 §14）：
       SaveSystem.ehq(SaveContainer)       RVA 0x7C7350   （旧 egi 0x7BA6A0）
       SaveSystem.ehn(string)              RVA 0x7C6ED0   （旧 egf 0x7BA220）
       SaveSystem.ehl(CharacterMode)       RVA 0x7C6AB0   （旧 egd 0x7B9E00）
       SaveSystem.eih()                    RVA 0x7C8C80   （旧 egz 0x7BBFD0）
  2) 槽值 = Il2CppClass*(SaveSystem)，以类名 "SaveSystem" 自校验（name @ +0x10）
  3) static_fields：Il2CppClass 内偏移候选扫描，用「实例对象 klass 指针回指」自校验；
     nfi 位于 static_fields+0x0（dump.cs L390396 <nfi>k__BackingField // 0x0）
  4) nfn @ nfi+0x28（L390404），其 klass 名应为 "SaveContainer"

字段偏移：dump.cs L390070-390060 与 docs09 §C 全表（SaveContainer/SaveSlotRecord/
SaveData/SavedRegistryEntry/SavedStatModifier/SavedEquipSlot/SavedTalent/SavedParagonStat/
SavedAbility/SavedStash/SavedParagon）。

用法：python mem_probe.py            # 自动找 Deskrawl 进程
"""
import ctypes
import math
import struct
import sys
from ctypes import wintypes

# ---------------- WinAPI（只读句柄） ----------------
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010

k32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.OpenProcess.restype = wintypes.HANDLE
k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.ReadProcessMemory.restype = wintypes.BOOL
k32.CloseHandle.argtypes = [wintypes.HANDLE]
psapi.GetModuleBaseNameW.argtypes = [wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
psapi.EnumProcessModulesEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE),
                                       wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.DWORD]
psapi.GetModuleFileNameExW.argtypes = [wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]


def read_mem(h, addr, size):
    if not addr:
        return None
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t()
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got)):
        return None
    return buf.raw[:got.value]


def valid_ptr(p):
    return p is not None and 0x10000 <= p < 0x7FFFFFFEFFFF


def u64(h, addr):
    b = read_mem(h, addr, 8)
    return struct.unpack('<Q', b)[0] if b and len(b) == 8 else None


def u32(h, addr):
    b = read_mem(h, addr, 4)
    return struct.unpack('<I', b)[0] if b and len(b) == 4 else None


def i64(h, addr):
    b = read_mem(h, addr, 8)
    return struct.unpack('<q', b)[0] if b and len(b) == 8 else None


def i32(h, addr):
    b = read_mem(h, addr, 4)
    return struct.unpack('<i', b)[0] if b and len(b) == 4 else None


def f32(h, addr):
    b = read_mem(h, addr, 4)
    return struct.unpack('<f', b)[0] if b and len(b) == 4 else None


def cstr(h, addr, cap=64):
    """Il2CppClass.name：char*（ASCII）"""
    if not valid_ptr(addr):
        return None
    b = read_mem(h, addr, cap)
    if not b:
        return None
    return b.split(b'\x00', 1)[0].decode('ascii', 'replace')


def wstr(h, addr, cap=1024):
    """System.String：length int32 @+0x10，UTF-16LE chars @+0x14"""
    if not valid_ptr(addr):
        return None
    n = i32(h, addr + 0x10)
    if n is None or n < 0 or n > cap:
        return None
    if n == 0:
        return ''
    b = read_mem(h, addr + 0x14, n * 2)
    if not b or len(b) != n * 2:
        return None
    return b.decode('utf-16-le', 'replace')


def klass_name(h, obj):
    """对象 -> klass 指针 -> 类名。注意 name/namespace 是 char* 指针字段，需先解引用。"""
    k = u64(h, obj) if valid_ptr(obj) else None
    if not valid_ptr(k):
        return None, None
    np = u64(h, k + 0x10)
    sp = u64(h, k + 0x18)
    return (cstr(h, np) if valid_ptr(np) else None,
            cstr(h, sp) if valid_ptr(sp) else None)


def find_process(name):
    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
                    ('th32ProcessID', wintypes.DWORD),
                    ('th32DefaultHeapID', ctypes.POINTER(ctypes.c_ulong)),
                    ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
                    ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', ctypes.c_long),
                    ('dwFlags', wintypes.DWORD), ('szExeFile', wintypes.WCHAR * 260)]
    TH32CS_SNAPPROCESS = 0x2
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    ent = PROCESSENTRY32W(); ent.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    pid = None
    ok = k32.Process32FirstW(snap, ctypes.byref(ent))
    while ok:
        if ent.szExeFile == name:
            pid = ent.th32ProcessID
            break
        ok = k32.Process32NextW(snap, ctypes.byref(ent))
    k32.CloseHandle(snap)
    return pid


def module_base(h, mod_name):
    arr = (wintypes.HMODULE * 2048)()
    cb = wintypes.DWORD()
    if not psapi.EnumProcessModulesEx(h, arr, ctypes.sizeof(arr), ctypes.byref(cb), 3):
        return None
    nm = ctypes.create_unicode_buffer(260)
    for i in range(cb.value // ctypes.sizeof(wintypes.HMODULE)):
        psapi.GetModuleBaseNameW(h, arr[i], nm, 260)
        if nm.value == mod_name:
            return ctypes.cast(arr[i], ctypes.c_void_p).value or arr[i]
    return None


# ---------------- 锚点扫描 ----------------
# rip 相对寻址前缀：REX(48/4C) + OP(8B=mov / 8D=lea) + ModRM(mod=00, rm=101)
RIP_PREFIXES = {b'\x48\x8b', b'\x48\x8d', b'\x4c\x8b', b'\x4c\x8d'}
RIP_MODRMS = {0x05, 0x0D, 0x15, 0x1D, 0x2D, 0x35, 0x3D}  # 0x25(rsp) 排除

ANCHORS = [  # (说明, RVA) —— 2026-10-16 1.0.3 补丁后重算（类+签名+Slot 匹配；旧名为 1.0.2b 版）
    ('SaveSystem.ehq(SaveContainer)   旧 egi', 0x7C7350),
    ('SaveSystem.ehn(string)          旧 egf', 0x7C6ED0),
    ('SaveSystem.ehl(CharacterMode)   旧 egd', 0x7C6AB0),
    ('SaveSystem.eih()                旧 egz', 0x7C8C80),
]

# 路径 B：运行时单例静态 getter（无参返回单例实例）
SINGLETON_GETTERS = [
    # (说明, getter RVA, 期望返回类型类名) —— 2026-10-16 1.0.3 补丁后重算
    ('GameManager.dlo()   旧 dkg', 0x77D960, 'GameManager'),
    ('Inventory.fdi()     旧 fbq', 0x4FD1D0, 'Inventory'),
    ('Storage.frm()       旧 fpi', 0x52B390, 'Storage'),
]


def scan_usage_slots(h, base, rva, span=192):
    """扫锚点方法前 span 字节，返回 rip 相对目标（元数据用法槽）地址集合。"""
    code = read_mem(h, base + rva, span)
    slots = set()
    if not code:
        return slots
    for i in range(len(code) - 7):
        if code[i:i + 2] in RIP_PREFIXES and code[i + 2] in RIP_MODRMS:
            disp = struct.unpack('<i', code[i + 3:i + 7])[0]
            slots.add(base + rva + i + 7 + disp)
    return slots


def list_of(h, list_ptr):
    """IL2CPP List<T>：_items@0x10（数组引用），_size@0x18；数组元素区 @0x20。
    返回 (元素首地址, 数量)；空/无效 -> (0, 0)。"""
    if not valid_ptr(list_ptr):
        return 0, 0
    items = u64(h, list_ptr + 0x10)
    size = i32(h, list_ptr + 0x18)
    if not valid_ptr(items) or size is None or size < 0 or size > 100000:
        return 0, 0
    return items + 0x20, size


def elem(h, first, i):
    return u64(h, first + 8 * i)


# ---------------- ACTk (CodeStage Anti-Cheat Toolkit) 解码 ----------------
# 算法经反汇编实证（GameAssembly 当前构建）：
#   ObscuredInt/Long 读取 = (hiddenValue - currentCryptoKey) XOR currentCryptoKey
#     （encrypt 为 key + (value ^ key)； Actk.ObscuredInt.Decrypt@0x459960 / Actk.ObscuredLong.Decrypt@0x456400）
#   ObscuredFloat 读取 = bswap12(hiddenValue) XOR currentCryptoKey（Actk.ObscuredFloat.Decrypt@0x4588D0，
#     加密 jyh = bswap12(bits ^ key)，b16<->b24 字节互换）
# 布局：dump.cs L657166-657470；hash 字段为 FNV 校验（反篡改），读取时忽略
def _s32(x):
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x >= 0x80000000 else x


def _s64(x):
    x &= 0xFFFFFFFFFFFFFFFF
    return x - 0x10000000000000000 if x >= 0x8000000000000000 else x


def obsc_int(h, addr):     # 16B: hash@0 hidden(i32)@4 key(i32)@8 fake@0xC
    hidden, key = u32(h, addr + 4), u32(h, addr + 8)
    if hidden is None or key is None:
        return None
    return _s32(((hidden - key) & 0xFFFFFFFF) ^ key)


def obsc_long(h, addr):    # 32B: hash@0 hidden(i64)@8 key(i64)@0x10 fake@0x18
    hidden, key = u64(h, addr + 8), u64(h, addr + 0x10)
    if hidden is None or key is None:
        return None
    return _s64(((hidden - key) & 0xFFFFFFFFFFFFFFFF) ^ key)


def obsc_double(h, addr):  # 40B: hash@0 hidden@8 key@0x10 fake@0x18 oldByte8@0x20
    hidden, key = u64(h, addr + 8), u64(h, addr + 0x10)
    if hidden is None or key is None:
        return None
    b = struct.pack('<Q', hidden)
    # 字节置换（Actk.ObscuredDouble.Decrypt@0x457C30 反汇编实证）：swap(0,1) + 三循环 4->5->7->4
    r = bytes([b[1], b[0], b[2], b[3], b[7], b[4], b[6], b[5]])
    bits = struct.unpack('<Q', r)[0] ^ key
    return struct.unpack('<d', struct.pack('<Q', bits))[0]


def obsc_float(h, addr):   # 16B+4: hash@0 hidden(i32)@4 key(i32)@8 fake@0xC old@0x10
    hidden, key = u32(h, addr + 4), u32(h, addr + 8)
    if hidden is None or key is None:
        return None
    b1, b2 = (hidden >> 8) & 0xFF, (hidden >> 16) & 0xFF
    swapped = (hidden & 0xFF0000FF) | (b1 << 16) | (b2 << 8)
    return struct.unpack('<f', struct.pack('<I', swapped ^ key))[0]


# ---------------- M2-0：IL2CPP Dictionary<StatType, ObscuredDouble> 遍历 ----------------
# StatType 全表（dump.cs；1.0.3 起稀疏 ID 0..66）；名称表镜像 deskrawl_calc.stattype.STAT_NAMES
STAT_NAMES = {
    0: '力量', 1: '敏捷', 2: '智力', 3: '通用增伤', 4: '暴击率', 5: '暴击伤害', 6: '攻击速度%',
    7: '最大生命', 8: '护甲', 9: '魔抗', 10: '移动速度', 11: '击中回血', 12: '击杀回血',
    13: '冷却缩减', 14: '最大法力', 15: '金币获取', 16: '魔法装备获取', 17: '药水掉落',
    18: '背包容量', 19: '材料获取', 20: '武器伤害', 21: '武器速度', 22: '闪避', 23: '物理伤害%',
    24: '火焰伤害%', 25: '冰霜伤害%', 26: '闪电伤害%', 27: '毒素伤害%', 28: '奥术伤害%',
    29: '对健康敌人', 30: '对受伤敌人', 31: '对减速敌人', 32: '对精英', 33: '普攻伤害',
    34: '强力攻击伤害', 35: '击杀回蓝', 36: '生命回复', 37: '法力消耗缩减', 38: '药水充能',
    39: '荆棘', 40: '对易伤敌人', 41: '经验获取', 42: '最大生命%', 43: '对定身敌人', 44: '护甲%',
    45: '对流血的敌人', 46: '对中毒的敌人', 47: '法力回复', 48: '荆棘伤害%', 49: '毒素减伤',
    50: '宝石孔位', 51: '物理减伤', 52: '火焰减伤', 53: '冰霜减伤', 54: '闪电减伤', 55: '奥术减伤',
    56: '受治疗效果加成', 57: '移动速度%', 58: '对远处敌人', 59: '魔抗%', 60: '暴击伤害减免',
    61: '特殊技能加成伤害', 62: '持续伤害', 63: '对灼烧的敌人', 64: '全局减伤', 65: '全伤害加成%',
    66: '最终减伤',
}

DICT_SLOTS = [  # Player 的 7 个聚合字典（dump.cs L394237-394251），语义（Final/池）待对拍标注
    ('nsq', 0x218), ('nsr', 0x220), ('nsu', 0x238), ('nsv', 0x240),
    ('ntc', 0x278), ('ntd', 0x280), ('nte', 0x288),
]


def stat_dict(h, dict_ptr):
    """遍历 Dictionary<StatType, ObscuredDouble>（P1 spike 实测布局）。
    entries@0x18（数组元素区 @+0x20）、count@0x20；Entry 步长 0x38：next@0 hash@4 key@8
    value(ObscuredDouble 0x28)@0x10。空闲槽（CoreCLR 负链墓碑 next<=-2）必须跳过：
    删除后的旧值仍留在 entries 数组，不跳会读到残留脏值。返回 (kv, 空闲数, 错误或 None)。"""
    if not valid_ptr(dict_ptr):
        return [], 0, 'null'
    nm, _ = klass_name(h, dict_ptr)
    if not nm or not nm.startswith('Dictionary'):
        return [], 0, f'klass={nm!r}（应为 Dictionary`2）'
    count = i32(h, dict_ptr + 0x20)
    if count is None or count < 0 or count > 4096:
        return [], 0, f'count={count}'
    if count == 0:
        return [], 0, None
    entries = u64(h, dict_ptr + 0x18)
    if not valid_ptr(entries):
        return [], 0, f'entries=0x{entries or 0:X}'
    kv, free = [], 0
    for i in range(count):
        e = entries + 0x20 + 0x38 * i
        nxt = i32(h, e)
        if nxt is None:
            return kv, free, f'条目 {i} 读取失败'
        if nxt < -1:
            free += 1
            continue
        key, val = i32(h, e + 8), obsc_double(h, e + 0x10)
        if key is None or val is None:
            return kv, free, f'条目 {i} 解码失败'
        kv.append((key, val))
    return kv, free, None


def dump_stat_dicts(h, player):
    """M2-0：打印 7 个聚合字典全量 KV + 值域自检（任务 3 对拍基准）。"""
    print('    [聚合字典 ×7] Dictionary<StatType, ObscuredDouble> 全量 KV（ACTk 解码）')
    found, failed = {}, []
    for label, off in DICT_SLOTS:
        d = u64(h, player + off)
        kv, free, err = stat_dict(h, d)
        if err:
            failed.append(f'{label}@{off:#x}:{err}')
            print(f'      [{label} @+0x{off:X}] 读取失败: {err}')
            continue
        found[label] = dict(kv)
        tail = f'，跳过空闲槽 {free}' if free else ''
        print(f'      [{label} @+0x{off:X}] {len(kv)} KV{tail}   ptr=0x{d:X}')
        for key, val in sorted(kv):
            print(f'        {key:>3} {STAT_NAMES.get(key, f"Stat{key}"):<14} = {val}')
    # 值域自检（任务验收：7 段可读、键=合法 StatType、暴击率∈[0,1]、生命>1204、力量>0）
    checks = [('7 段字典全部可读', not failed)]
    all_kv = [(lb, k, v) for lb, kv in found.items() for k, v in kv.items()]
    bad_keys = sorted({k for _, k, _ in all_kv if not 0 <= k <= 66})
    bad_vals = [(lb, k) for lb, k, v in all_kv if not math.isfinite(v)]
    checks.append(('键均为合法 StatType(0..66)', not bad_keys))
    checks.append(('值均为有限 double', not bad_vals))
    if bad_keys:
        checks.append((f'非法键清单 {bad_keys}', False))
    if bad_vals:
        checks.append((f'非法值清单 {bad_vals}', False))
    # Final 候选 = 生命键值最大的字典（面板值含基础 1204 + 装备聚合，应最大）
    hp_cands = [(lb, kv[7]) for lb, kv in found.items() if kv.get(7) is not None]
    if hp_cands:
        fin_lb, fin_hp = max(hp_cands, key=lambda t: t[1])
        checks.append((f'生命最大字典 {fin_lb}={fin_hp} > 1204(基础) [Final 候选]', fin_hp > 1204))
        crit = found[fin_lb].get(4)
        if crit is not None:
            checks.append((f'[{fin_lb}] 暴击率={crit} ∈ [0,1]', 0.0 <= crit <= 1.0))
        strv = found[fin_lb].get(0)
        if strv is not None:
            checks.append((f'[{fin_lb}] 力量={strv} > 0', strv > 0))
    print('      [值域自检]')
    for name, ok in checks:
        print(f'        [{"PASS" if ok else "FAIL"}] {name}')
    if failed:
        print(f'      !! 失败字典: {"; ".join(failed)}')
    return not failed and all(ok for _, ok in checks)


def find_singleton(h, base, getter_rva, want):
    """静态 getter -> 元数据槽 -> Il2CppClass -> static_fields(0xB8) -> 实例(0x0)。
    用实例 klass 名 == want 自校验。"""
    for slot in scan_usage_slots(h, base, getter_rva):
        v = u64(h, slot)
        if not valid_ptr(v):
            continue
        sf = u64(h, v + 0xB8)
        if not valid_ptr(sf):
            continue
        inst = u64(h, sf)  # 静态字段 @0x0 = <XXX>k__BackingField
        if not valid_ptr(inst):
            continue
        nm, _ = klass_name(h, inst)
        if nm == want:
            return inst
    return None


def dump_inventory_slots(h, arr_ptr, label, limit=10):
    """InventorySlot[]：Item(ItemData*)@0x10 Count(i32)@0x18 ItemUid(string)@0x20"""
    if not valid_ptr(arr_ptr):
        print(f'    {label}: <null>')
        return
    n = i32(h, arr_ptr + 0x18)
    if n is None or n < 0:
        print(f'    {label}: <invalid>')
        return
    items = []
    first = arr_ptr + 0x20
    for i in range(n):
        s = elem(h, first, i)
        if not valid_ptr(s):
            continue
        cnt = i32(h, s + 0x18)
        uid = wstr(h, u64(h, s + 0x20))
        item = u64(h, s + 0x10)
        # ItemData : ScriptableObject -> UnityEngine.Object：m_CachedPtr@0x10, m_Name(string)@0x18
        iname = wstr(h, u64(h, item + 0x18)) if valid_ptr(item) else None
        if item or cnt or uid:
            items.append(f'{iname or "?"}x{cnt or 1} uid={uid or "-"}')
    print(f'    {label}: {len(items)} 项（数组长度 {n}）')
    for it in items[:limit]:
        print(f'      - {it}')


def dump_path_b(h, base):
    """路径 B：运行时对象实时数据（全部 ACTk 解码）。"""
    print('\n[6] 路径 B：运行时单例实时数据（ACTk XOR 解码）')
    # 复用 SINGLETON_GETTERS：RVA 只在一处维护，避免补丁后两处不一致
    found = {klass: find_singleton(h, base, rva, klass) for _, rva, klass in SINGLETON_GETTERS}
    gm, inv, sto = found.get('GameManager'), found.get('Inventory'), found.get('Storage')
    print(f'    单例：GameManager={"0x%X" % gm if gm else None} '
          f'Inventory={"0x%X" % inv if inv else None} Storage={"0x%X" % sto if sto else None}')

    player = None
    if valid_ptr(gm):
        pcc = u64(h, gm + 0x40)  # GameManager.PlayerCombatController @0x40
        if valid_ptr(pcc):
            player = u64(h, pcc + 0x20)  # PlayerCombatController.Player @0x20
    if valid_ptr(player):
        lvl = obsc_int(h, player + 0x20)        # Character._level
        hpmax = obsc_long(h, player + 0x30)     # Character.BaseMaxHealth
        dmg = obsc_long(h, player + 0x50)       # Character.BaseDamage
        crit = obsc_float(h, player + 0x84)     # Character.BaseCritChance
        mana = obsc_long(h, player + 0xD8)      # Character.BaseMaxMana
        xp = obsc_long(h, player + 0x180)       # Player.CurrentXP
        pstat = obsc_float(h, player + 0x1A0)   # Player.BasePrimaryStat
        loh = obsc_float(h, player + 0x1B4)     # Player.BaseLifeOnHit
        print(f'    Player @0x{player:X}:')
        print(f'      _level={lvl}  BaseMaxHealth={hpmax}  BaseDamage={dmg}  BaseMaxMana={mana}')
        print(f'      BasePrimaryStat={pstat:.2f}  BaseCritChance={crit}  BaseLifeOnHit={loh}  CurrentXP={xp}')
        dump_stat_dicts(h, player)
    else:
        print('    Player 实例不可达（未进图？GameManager.PlayerCombatController.Player 为空）')

    if valid_ptr(inv):
        dump_inventory_slots(h, u64(h, inv + 0x38), 'Inventory.nso（背包）')
    if valid_ptr(sto):
        dump_inventory_slots(h, u64(h, sto + 0x30), 'Storage.nyk（仓库）')
    return valid_ptr(player) or valid_ptr(inv) or valid_ptr(sto)


# ---------------- 各结构打印 ----------------
def dump_modifier_list(h, lst, limit=8):
    first, n = list_of(h, lst)
    out = []
    for i in range(min(n, limit)):
        m = elem(h, first, i)
        if not valid_ptr(m):
            continue
        stat = wstr(h, u64(h, m + 0x10))
        typ = wstr(h, u64(h, m + 0x18))
        val = f32(h, m + 0x20)
        out.append(f'{stat} {typ} {val}')
    return out, n


def dump_registry_entry(h, e, reg):
    uid = wstr(h, u64(h, e + 0x10)) or ''
    ilv = i32(h, e + 0x18)
    rar = wstr(h, u64(h, e + 0x20))
    mods, nmod = dump_modifier_list(h, u64(h, e + 0x28))
    upg = i32(h, e + 0x30)
    rlv = i32(h, e + 0x3C)
    sock = i32(h, e + 0x48)
    print(f'      - {uid[:16]:<16} Lv{ilv:<3} {rar:<10} +{upg} rune{rlv} sock{sock} mods[{nmod}]: '
          + ('; '.join(mods) if mods else '-'))
    reg[uid] = True


def dump_slot(h, rec, idx):
    mode = i32(h, rec + 0x10)
    profile = wstr(h, u64(h, rec + 0x18))
    name = wstr(h, u64(h, rec + 0x20))
    lvl = i32(h, rec + 0x28)
    hero = wstr(h, u64(h, rec + 0x30))
    data = u64(h, rec + 0x38)
    print(f'  [{idx}] Mode={mode} name={name!r} summaryLevel={lvl} hero={hero!r} profile={profile!r}')
    if not valid_ptr(data):
        print('      Data = <null>')
        return
    kn, _ = klass_name(h, data)
    d_lvl = i32(h, data + 0x10)
    d_xp = i64(h, data + 0x18)
    d_hp = i64(h, data + 0x20)
    d_dmg = i64(h, data + 0x28)
    d_pstat = f32(h, data + 0x48)
    _, n_inv = list_of(h, u64(h, data + 0x50))
    _, n_eq = list_of(h, u64(h, data + 0x58))
    _, n_reg = list_of(h, u64(h, data + 0x68))
    _, n_tal = list_of(h, u64(h, data + 0xA0))
    _, n_par = list_of(h, u64(h, data + 0xA8))
    _, n_ab = list_of(h, u64(h, data + 0xD8))
    sel_hero = wstr(h, u64(h, data + 0x100))
    pname = wstr(h, u64(h, data + 0x108))
    print(f'      Data(klass={kn}) Level={d_lvl} XP={d_xp} BaseMaxHP={d_hp} BaseDmg={d_dmg} '
          f'BasePrimary={d_pstat:.1f}')
    print(f'      counts: inv={n_inv} equip={n_eq} registry={n_reg} talents={n_tal} '
          f'paragon={n_par} abilities={n_ab} | SelectedHero={sel_hero!r} PlayerName={pname!r}')

    reg = {}
    ef, en = list_of(h, u64(h, data + 0x58))
    for i in range(min(en, 12)):
        s = elem(h, ef, i)
        if not valid_ptr(s):
            continue
        sid = wstr(h, u64(h, s + 0x10))
        iname = wstr(h, u64(h, s + 0x18))
        iuid = wstr(h, u64(h, s + 0x20))
        print(f'      equip slot {sid!r}: {iname!r} uid={iuid!r}')
    rf, rn = list_of(h, u64(h, data + 0x68))
    for i in range(min(rn, 12)):
        e = elem(h, rf, i)
        if valid_ptr(e):
            dump_registry_entry(h, e, reg)
    tf, tn = list_of(h, u64(h, data + 0xA0))
    tot = 0
    shown = 0
    for i in range(tn):
        t = elem(h, tf, i)
        if not valid_ptr(t):
            continue
        tn_name = wstr(h, u64(h, t + 0x10))
        pts = i32(h, t + 0x18)
        tot += pts
        if shown < 10:
            print(f'      talent {tn_name!r} x{pts}')
            shown += 1
    pf, pn = list_of(h, u64(h, data + 0xA8))
    par = []
    for i in range(min(pn, 20)):
        p = elem(h, pf, i)
        if valid_ptr(p):
            par.append(f'{wstr(h, u64(h, p + 0x10))}={i32(h, p + 0x18)}')
    if par:
        print(f'      paragon: {", ".join(par)}')
    af, an = list_of(h, u64(h, data + 0xD8))
    ab = []
    for i in range(min(an, 10)):
        a = elem(h, af, i)
        if valid_ptr(a):
            ab.append(f'{wstr(h, u64(h, a + 0x10))} Lv{i32(h, a + 0x18)}')
    if ab:
        print(f'      abilities: {", ".join(ab)}')
    return d_lvl, n_eq, n_reg, n_tal, tot


def main():
    print('=== Deskrawl 联机角色数据内存导入 P0 spike（严格只读） ===')
    print('只读 API：OpenProcess(0x0410) / ReadProcessMemory；不写、不注入、不建远程线程\n')

    pid = find_process('Deskrawl.exe')
    if not pid:
        print('未找到 Deskrawl.exe 进程 —— 请先启动游戏并进入角色。')
        return 2
    print(f'进程: Deskrawl.exe PID={pid}')
    h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        print(f'OpenProcess 失败 err={k32.GetLastError()}')
        return 2
    print('OpenProcess(QUERY_INFORMATION|VM_READ) 成功（只读句柄）')

    base = module_base(h, 'GameAssembly.dll')
    if not base:
        print('未找到 GameAssembly.dll 模块')
        k32.CloseHandle(h)
        return 2
    print(f'GameAssembly.dll base = 0x{base:X}')

    # ---- 1) 扫描锚点 -> 元数据用法槽 -> 验证 SaveSystem 类 ----
    klass = None
    slot_hits = {}
    all_names = {}
    for label, rva in ANCHORS:
        for slot in scan_usage_slots(h, base, rva):
            v = u64(h, slot)
            if not valid_ptr(v):
                continue
            # 槽值即 Il2CppClass*：name@+0x10 是 char* 指针，先解引用
            np = u64(h, v + 0x10)
            nm = cstr(h, np) if valid_ptr(np) else None
            all_names.setdefault(nm, set()).add(slot)
            if nm == 'SaveSystem':
                slot_hits[slot] = label
                klass = v
    print(f'\n[1] 元数据槽扫描：发现类名 {sorted(str(k) for k in all_names if k)}')
    if klass is None:
        print('  !! 未从锚点定位到 SaveSystem 类（需扩展锚点/扫描窗口）')
        k32.CloseHandle(h)
        return 3
    for s, lb in slot_hits.items():
        print(f'  SaveSystem klass = 0x{klass:X}  (槽 0x{s:X} <- {lb})')

    # ---- 2) static_fields 候选偏移自校验 -> nfi ----
    nfi = None
    sf_off = None
    for off in (0xB8, 0xB0, 0xC0, 0xC8, 0xA8):
        sf = u64(h, klass + off)
        if not valid_ptr(sf):
            continue
        cand = u64(h, sf)  # static field @0x0 = <nfi>k__BackingField
        if valid_ptr(cand) and u64(h, cand) == klass:  # 实例 klass 回指自校验
            nfi, sf_off = cand, off
            break
    if nfi is None:
        print('  !! static_fields 定位失败（Il2CppClass 布局漂移？）')
        k32.CloseHandle(h)
        return 3
    print(f'[2] static_fields @ klass+0x{sf_off:X} -> nfi = 0x{nfi:X}（klass 回指校验通过）')
    kn, _ = klass_name(h, nfi)
    print(f'    nfi.klass = {kn!r}（应为 SaveSystem）')

    # ---- 3) nfn 容器 ----
    mode = i32(h, nfi + 0x20)     # nfj : CharacterMode
    slot_idx = i32(h, nfi + 0x24)  # nfk : int
    nfn = u64(h, nfi + 0x28)
    print(f'[3] 当前模式 nfj={mode} 槽位 nfk={slot_idx}')
    if not valid_ptr(nfn):
        print('  !! nfn 为空 —— 游戏尚未加载任何存档容器？请进入/登录角色后重试。')
        k32.CloseHandle(h)
        return 3
    kn, _ = klass_name(h, nfn)
    ver = i32(h, nfn + 0x10)
    print(f'    nfn = 0x{nfn:X} klass={kn!r} Version={ver}（应为 SaveContainer / 5）')

    # ---- 4) 遍历 OnlineSlots ----
    print('[4] SaveContainer 内容：')
    lf, ln = list_of(h, u64(h, nfn + 0x18))
    print(f'    LocalSlots: {ln} 条')
    verdict = 'A_EMPTY'
    of, on = list_of(h, u64(h, nfn + 0x20))
    print(f'    OnlineSlots: {on} 条')
    for i in range(on):
        rec = elem(h, of, i)
        if valid_ptr(rec):
            r = dump_slot(h, rec, i)
            if r:
                d_lvl, n_eq, n_reg, n_tal, tal_pts = r
                kn_rec = i32(h, rec + 0x10)
                if kn_rec == 1 and (d_lvl > 1 or n_eq or n_reg or n_tal or tal_pts):
                    verdict = 'A_LIVE'
            print()

    # ---- 5) LocalStash ----
    stash = u64(h, nfn + 0x28)
    if valid_ptr(stash):
        gold = i64(h, stash + 0x20)
        _, s_slots = list_of(h, u64(h, stash + 0x10))
        _, s_reg = list_of(h, u64(h, stash + 0x18))
        pg = u64(h, stash + 0x40)
        print(f'[5] LocalStash: gold={gold} slots={s_slots} registry={s_reg} '
              + (f'paragon(unlocked={bool(u32(h, pg + 0x10))}, lv={i32(h, pg + 0x14)}, '
                 f'xp={i64(h, pg + 0x18)})' if valid_ptr(pg) else 'paragon=<null>'))

    # ---- 6) 路径 B：运行时单例实时数据 ----
    b_ok = dump_path_b(h, base)

    print('\n=== 结论 ===')
    if verdict == 'A_LIVE':
        print('路径 A 成立：nfn.OnlineSlots[i].Data 在客户端内存中持有联机角色完整数据（实时快照）。')
        print('下一步（P1）：GUI core/memory_import.py 封装本链路 -> CharacterProfile.from_save()。')
    else:
        print('路径 A 不成立：OnlineSlots[i].Data 在内存中为 null（完整数据仅在云端保存时临时装配，'
              'JsonUtility 把 null 写成默认对象，解释了本地存档的"空 Data"）。')
        if b_ok:
            print('路径 B 成立：运行时单例（Player/Inventory/Storage）持有实时角色数据，ACTk 可解码。')
            print('下一步（P1）：GUI 封装路径 B -> CharacterProfile（属性聚合字典 + 背包/仓库物品）。')
        else:
            print('路径 B 暂不可达：单例未创建（可能停留在主菜单）。请进入角色后重跑本脚本。')
    k32.CloseHandle(h)
    return 0


if __name__ == '__main__':
    sys.exit(main())
