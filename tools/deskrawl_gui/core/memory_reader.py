# -*- coding: utf-8 -*-
"""只读内存访问基元：进程通道 / IL2CPP 对象模型 / ACTk 解码（三层）。

只读边界（硬约束，验收条款）：只允许 OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ,
即 0x0410) + ReadProcessMemory。禁止 WriteProcessMemory / CreateRemoteThread / SuspendThread /
DLL 注入 —— 本模块与整个导入链任何时候不得出现写操作。

与 tools/scripts/mem_probe.py 刻意保持「算法同源、代码独立」：诊断脚本面向人工排查（宽容、
带打印），本模块面向导入（严格、抛错），两者允许约百行重复、各自演进（GUI 包不依赖逆向脚本）。

分层理由：ProcessReader 只谈 WinAPI；Il2CppReader 只谈对象模型（字符串/数组/表）；ActkCodec
只谈解码算法。分层后每层的变更理由单一，反向验证可以只改 ActkCodec 一层。
"""
from __future__ import annotations

import ctypes
import struct
from ctypes import wintypes

# 只读句柄：PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
OPENPROCESS_READONLY = 0x0410

_k32 = ctypes.windll.kernel32
_psapi = ctypes.windll.psapi
_k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_k32.OpenProcess.restype = wintypes.HANDLE
_k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                   ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
_k32.ReadProcessMemory.restype = wintypes.BOOL
_k32.CloseHandle.argtypes = [wintypes.HANDLE]
_psapi.EnumProcessModulesEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE),
                                        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.DWORD]
_psapi.GetModuleBaseNameW.argtypes = [wintypes.HANDLE, wintypes.HMODULE,
                                      wintypes.LPWSTR, wintypes.DWORD]


def offset(value) -> int:
    """offsets.json 中的偏移既可写 int 也可写 "0x..." 字符串，统一入口减少调用点噪音。"""
    return int(value, 16) if isinstance(value, str) else int(value)


def valid_ptr(p) -> bool:
    """用户态 64 位地址粗筛；0/错误值（如读取失败返回的 None）一律视为无效。"""
    return p is not None and 0x10000 <= p < 0x7FFFFFFEFFFF


class MemoryReadError(Exception):
    """读取/结构层错误。导入层据此重试或终止（宁可红，不出脏）。"""


class ProcessReader:
    """只读进程通道：查找进程、取模块基址、读原始字节的唯一入口。"""

    def __init__(self, pid: int):
        self.pid = pid
        self.handle = _k32.OpenProcess(OPENPROCESS_READONLY, False, pid)
        if not self.handle:
            err = _k32.GetLastError()
            if err == 5:
                raise MemoryReadError('OpenProcess 被拒绝（err=5）：游戏可能以管理员运行，'
                                      '请以管理员身份重启本工具后重试')
            raise MemoryReadError(f'OpenProcess 失败 err={err}')

    def close(self):
        if self.handle:
            _k32.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def read(self, addr, size):
        """原始读取；失败返回 None（调用方决定容忍度）。"""
        if not addr:
            return None
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t()
        if not _k32.ReadProcessMemory(self.handle, ctypes.c_void_p(addr), buf, size,
                                      ctypes.byref(got)):
            return None
        return buf.raw[:got.value]

    def u32(self, addr):
        b = self.read(addr, 4)
        return struct.unpack('<I', b)[0] if b and len(b) == 4 else None

    def i32(self, addr):
        b = self.read(addr, 4)
        return struct.unpack('<i', b)[0] if b and len(b) == 4 else None

    def u64(self, addr):
        b = self.read(addr, 8)
        return struct.unpack('<Q', b)[0] if b and len(b) == 8 else None

    def f32(self, addr):
        b = self.read(addr, 4)
        return struct.unpack('<f', b)[0] if b and len(b) == 4 else None

    def module_base(self, mod_name):
        """枚举模块取基址；找不到返回 None（调用方报「结构漂移」而非猜测）。"""
        arr = (wintypes.HMODULE * 2048)()
        cb = wintypes.DWORD()
        if not _psapi.EnumProcessModulesEx(self.handle, arr, ctypes.sizeof(arr),
                                           ctypes.byref(cb), 3):
            return None
        nm = ctypes.create_unicode_buffer(260)
        for i in range(cb.value // ctypes.sizeof(wintypes.HMODULE)):
            _psapi.GetModuleBaseNameW(self.handle, arr[i], nm, 260)
            if nm.value == mod_name:
                return ctypes.cast(arr[i], ctypes.c_void_p).value or arr[i]
        return None

    @staticmethod
    def find_process(name):
        """Toolhelp 快照按文件名找 PID；只枚举进程，不触碰目标内存。"""
        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
                        ('th32ProcessID', wintypes.DWORD),
                        ('th32DefaultHeapID', ctypes.POINTER(ctypes.c_ulong)),
                        ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
                        ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', ctypes.c_long),
                        ('dwFlags', wintypes.DWORD), ('szExeFile', wintypes.WCHAR * 260)]

        snap = _k32.CreateToolhelp32Snapshot(0x2, 0)
        ent = PROCESSENTRY32W()
        ent.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        pid = None
        ok = _k32.Process32FirstW(snap, ctypes.byref(ent))
        while ok:
            if ent.szExeFile == name:
                pid = ent.th32ProcessID
                break
            ok = _k32.Process32NextW(snap, ctypes.byref(ent))
        _k32.CloseHandle(snap)
        return pid


class Il2CppReader:
    """IL2CPP 对象模型读取：类名/字符串/数组/List/Dictionary。

    头偏移来自 offsets['il2cpp']（IL2CPP 运行时布局，跨构建稳定但集中管理便于审计）。
    Dictionary 遍历必须跳过空闲槽（CoreCLR 负链墓碑 next<=-2）：删除后旧值仍留在
    entries 数组里，不跳会读到残留脏值。
    """

    def __init__(self, pr: ProcessReader, il_offsets: dict):
        self.pr = pr
        self.o = {k: offset(v) for k, v in il_offsets.items()}

    def _need(self, value, what):
        if value is None:
            raise MemoryReadError(f'{what} 读取失败（地址不可读）')
        return value

    def cstr(self, addr, cap=64):
        """Il2CppClass.name 等 char*：定长读，截到首个 NUL。"""
        if not valid_ptr(addr):
            return None
        b = self.pr.read(addr, cap)
        if not b:
            return None
        return b.split(b'\x00', 1)[0].decode('ascii', 'replace')

    def wstr(self, addr, cap=256):
        """System.String：len int32@+0x10，UTF-16LE chars@+0x14。"""
        if not valid_ptr(addr):
            return None
        n = self.pr.i32(addr + self.o['string_len'])
        if n is None or n < 0 or n > cap:
            return None
        if n == 0:
            return ''
        b = self.pr.read(addr + self.o['string_data'], n * 2)
        if not b or len(b) != n * 2:
            return None
        return b.decode('utf-16-le', 'replace')

    def klass_name(self, obj):
        """对象 → klass 指针 → (类名, 命名空间)。name/namespace 是 char* 字段，需再解引用。"""
        k = self.pr.u64(obj) if valid_ptr(obj) else None
        if not valid_ptr(k):
            return None, None
        np_ = self.pr.u64(k + self.o['klass_name_ptr'])
        return (self.cstr(np_) if valid_ptr(np_) else None, None)

    def static_fields(self, klass):
        sf = self.pr.u64(klass + self.o['static_fields'])
        if not valid_ptr(sf):
            raise MemoryReadError('static_fields 指针不可读（Il2CppClass 布局漂移？）')
        return sf

    def array_items(self, arr):
        """IL2CPP 数组：len@+0x18，元素区 @+0x20。空数组（ptr 为 0 且无元素）返回 (0, 0)。"""
        if not valid_ptr(arr):
            return 0, 0
        n = self.pr.i32(arr + self.o['array_len'])
        if n is None or n < 0 or n > 1000000:
            raise MemoryReadError(f'数组长度异常：{n}')
        return arr + self.o['array_data'], n

    def list_items(self, lst):
        """List<T>：_items@+0x10、_size@+0x18；元素区在 _items 数组 @+0x20。"""
        if not valid_ptr(lst):
            return 0, 0
        items = self.pr.u64(lst + self.o['list_items'])
        size = self.pr.i32(lst + self.o['list_size'])
        if size is None or size < 0 or size > 1000000:
            raise MemoryReadError(f'List 长度异常：{size}')
        if size == 0:
            return 0, 0
        if not valid_ptr(items):
            raise MemoryReadError('List._items 为空但 size>0（撕裂读？）')
        return items + self.o['array_data'], size

    def dict_entries(self, d, step):
        """Dictionary 遍历核心：返回 (占用槽 entry 地址列表, 空闲槽数)。

        自校验：对象 klass 名必须以 Dictionary 开头、count 有界——任何一条不满足即抛错，
        避免把非字典对象当字典读出「像模像样的垃圾」。条目读取失败同样抛错（调用方重试）。
        """
        if not valid_ptr(d):
            raise MemoryReadError('字典指针为 null')
        nm, _ = self.klass_name(d)
        if not nm or not nm.startswith('Dictionary'):
            raise MemoryReadError(f'对象类名 {nm!r} 不是 Dictionary（结构漂移？）')
        count = self.pr.i32(d + self.o['dict_count'])
        if count is None or count < 0 or count > 4096:
            raise MemoryReadError(f'字典 count={count} 超出合理范围')
        if count == 0:
            return [], 0
        entries = self.pr.u64(d + self.o['dict_entries'])
        if not valid_ptr(entries):
            raise MemoryReadError('字典 entries 指针不可读')
        out, free = [], 0
        for i in range(count):
            e = entries + self.o['array_data'] + step * i
            nxt = self.pr.i32(e)
            if nxt is None:
                raise MemoryReadError(f'字典条目 {i} 读取失败（并发修改？）')
            if nxt < -1:
                free += 1
                continue
            out.append(e)
        return out, free

    def dict_entry_key_i32(self, entry):
        v = self.pr.i32(entry + self.o['entry_key'])
        if v is None:
            raise MemoryReadError('字典键读取失败')
        return v

    def dict_entry_key_str(self, entry):
        return self.wstr(self.pr.u64(entry + self.o['entry_key']))

    def dict_entry_value(self, entry):
        return self.pr.u64(entry + self.o['entry_value'])


def _s32(x):
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x >= 0x80000000 else x


def _s64(x):
    x &= 0xFFFFFFFFFFFFFFFF
    return x - 0x10000000000000000 if x >= 0x8000000000000000 else x


class ActkCodec:
    """ACTk (CodeStage Anti-Cheat Toolkit) Obscured* 解码。

    算法来自反汇编实证（调研报告 §3.3，各函数签名见注释）；密钥随每个结构体内嵌，
    无需全局密钥。hash 字段只做反篡改校验，读取时忽略（只读不触发检测器）。
    """

    def __init__(self, pr: ProcessReader):
        self.pr = pr

    def obsc_int(self, addr):     # (hidden - key) ^ key；Actk.ObscuredInt.Decrypt @0x4548A0
        hidden = self.pr.u32(addr + 4)
        key = self.pr.u32(addr + 8)
        if hidden is None or key is None:
            return None
        return _s32(((hidden - key) & 0xFFFFFFFF) ^ key)

    def obsc_long(self, addr):    # (hidden - key) ^ key；Actk.ObscuredLong.Decrypt @0x451340
        hidden = self.pr.u64(addr + 8)
        key = self.pr.u64(addr + 0x10)
        if hidden is None or key is None:
            return None
        return _s64(((hidden - key) & 0xFFFFFFFFFFFFFFFF) ^ key)

    def obsc_float(self, addr):   # bswap12(hidden) ^ key（字节 1<->2 互换）；Actk.ObscuredFloat.Decrypt @0x453810
        hidden = self.pr.u32(addr + 4)
        key = self.pr.u32(addr + 8)
        if hidden is None or key is None:
            return None
        b1, b2 = (hidden >> 8) & 0xFF, (hidden >> 16) & 0xFF
        swapped = (hidden & 0xFF0000FF) | (b1 << 16) | (b2 << 8)
        return struct.unpack('<f', struct.pack('<I', swapped ^ key))[0]

    def obsc_double(self, addr):  # 字节置换（swap01 + 4->5->7->4 三循环）后 ^ key；Actk.ObscuredDouble.Decrypt @0x452B70
        hidden = self.pr.u64(addr + 8)
        key = self.pr.u64(addr + 0x10)
        if hidden is None or key is None:
            return None
        b = struct.pack('<Q', hidden)
        r = bytes([b[1], b[0], b[2], b[3], b[7], b[4], b[6], b[5]])
        bits = struct.unpack('<Q', r)[0] ^ key
        return struct.unpack('<d', struct.pack('<Q', bits))[0]