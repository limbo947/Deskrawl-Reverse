# -*- coding: utf-8 -*-
"""定位基元：锚点 RVA → 用法槽 → Il2CppClass → static_fields → 实例/静态区。

自 memory_import.py 拆出（原文件 749 有效行，已过 700 拆分行阈值）。拆出理由：定位链是
「只读硬约束」里最独立的一段——它只依赖 ProcessReader/Il2CppReader + 偏移表，与快照构建
（SnapshotBuilder）没有任何共享状态，且被 DPS 计定位链（dps_meter）单独复用。
"""
from __future__ import annotations

import struct

from .memory_errors import MemoryImportError
from .memory_reader import MemoryReadError, valid_ptr

# rip 相对寻址前缀：REX(48/4C) + OP(8B=mov / 8D=lea) + ModRM(mod=00, rm=101)
_RIP_PREFIXES = {b'\x48\x8b', b'\x48\x8d', b'\x4c\x8b', b'\x4c\x8d'}
_RIP_MODRMS = {0x05, 0x0D, 0x15, 0x1D, 0x2D, 0x35, 0x3D}  # 0x25(rsp) 排除


class Locator:
    """锚点定位：静态 getter 用法槽 → Il2CppClass → static_fields → 实例/静态区。

    全部链以类名自校验收尾：偏移漂移时宁可拒绝导入，也不返回「碰巧读到」的数据。
    """

    def __init__(self, pr, il, off):
        self.pr = pr
        self.il = il
        self.off = off
        self.base = pr.module_base(off['module'])
        if not self.base:
            raise MemoryImportError(f'未找到模块 {off["module"]}（游戏进程异常？）', 'env')

    def scan_usage_slots(self, rva, span=192):
        """扫方法前 span 字节的 rip 相对目标（元数据用法槽）。getter 桩很短，
        192B 覆盖 class-init 判空分支；span=256 用于静态类方法。"""
        code = self.pr.read(self.base + rva, span)
        if not code:
            raise MemoryImportError(f'方法 RVA 0x{rva:X} 不可读（版本更新？需重出偏移表）', 'env')
        slots = set()
        for i in range(len(code) - 7):
            if code[i:i + 2] in _RIP_PREFIXES and code[i + 2] in _RIP_MODRMS:
                disp = struct.unpack('<i', code[i + 3:i + 7])[0]
                slots.add(self.base + rva + i + 7 + disp)
        return slots

    def find_singleton(self, getter_rva, klass):
        """单例 getter 链：槽值=Il2CppClass* → static_fields(+0xB8) → 实例(+0x0)。"""
        for slot in self.scan_usage_slots(getter_rva):
            v = self.pr.u64(slot)
            if not valid_ptr(v):
                continue
            try:
                inst = self.pr.u64(self.il.static_fields(v))
            except MemoryReadError:
                continue
            if not valid_ptr(inst):
                continue
            nm, _ = self.il.klass_name(inst)
            if nm == klass:
                return inst
        return None

    def find_static_klass(self, method_rvas, klass):
        """静态类（无实例）：扫若干方法的用法槽取 Il2CppClass*（类名自校验）。"""
        for rva in method_rvas:
            for slot in self.scan_usage_slots(rva, span=256):
                v = self.pr.u64(slot)
                if not valid_ptr(v):
                    continue
                np_ = self.pr.u64(v + self.il.o['klass_name_ptr'])
                if self.il.cstr(np_) == klass:
                    return v
        return None

    def find_save_system(self):
        """SaveSystem 静态单例（nfi）：多锚点扫槽取类名命中者的 static_fields[0]。"""
        for rva in self.off['save_system']['anchor_rvas']:
            for slot in self.scan_usage_slots(rva):
                v = self.pr.u64(slot)
                if not valid_ptr(v):
                    continue
                np_ = self.pr.u64(v + self.il.o['klass_name_ptr'])
                if self.il.cstr(np_) == self.off['save_system']['klass']:
                    try:
                        return self.pr.u64(self.il.static_fields(v))
                    except MemoryReadError:
                        continue
        return None
