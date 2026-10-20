# -*- coding: utf-8 -*-
"""训练假人 DPS 计实测值（只读）：定位 TrainingDpsMeterUI 实例并读总伤害/当前每秒伤害。

定位链（2026-10-10 活体实测，PID 12620）：TrainingDummy.bmj（受击入口）用法槽 → 事件总线类
（混淆名每版会变，不校名只走链）→ static_fields[+0x20] → 处理器对象 → 委托数组字段 →
委托 target 中 klass==TrainingDpsMeterUI（非混淆名，跨补丁稳定）→ 实例。

显示值口径（hww() 反汇编）：当前每秒伤害 = pmk[+0x50] / max(pmm[+0x60] − pml[+0x58], 1.0)，
其中 pmm 是 UI 刷新（0.2s 节流）时缓存的时钟 now——因此无需另读游戏时钟。
总伤害为累计值，「重置」按钮清零并重置 pml。
"""
from __future__ import annotations

import contextlib
import math
import struct

from .memory_import import Locator, MemoryImportError
from .memory_reader import MemoryReadError, ProcessReader, valid_ptr
from .memory_snapshot import load_offsets

_METER_KLASS = 'TrainingDpsMeterUI'      # 非混淆类名：定位链的自校验终点
_HANDLER_SPAN = 0x100                    # 处理器对象字段扫描范围（实测 +0x78 处命中）
_MAX_DELEGATES = 32

# 已定位实例的缓存：每秒轮询时进程与地图都不变，没必要每次都重走
# 「全进程枚举 + 256 槽扫描 + 逐层解引用」这条链（离线态 5s 一次，同样浪费）。
_meter_cache = {'pid': 0, 'addr': 0}


def _cached_meter(pid: int) -> int:
    return _meter_cache['addr'] if _meter_cache['pid'] == int(pid) else 0


def _store_meter(pid: int, addr: int) -> None:
    _meter_cache['pid'] = int(pid)
    _meter_cache['addr'] = int(addr)


def _forget_meter() -> None:
    _meter_cache['pid'] = 0
    _meter_cache['addr'] = 0


def meter_dps(total: float, start_time: float, last_tick: float) -> float:
    """复算 DPS 计显示值（与 TrainingDpsMeterUI.hww() 逐式同源）。纯函数，供 selftest 锚点。"""
    return total / max(last_tick - start_time, 1.0)


def _cstr(pr, addr, cap=96) -> str:
    """读 NUL 结尾 C 串（ProcessReader 无 cstr 基元，这里本地实现最简版）。"""
    try:
        raw = pr.read(addr, cap)
    except MemoryReadError:
        return ''
    return raw.split(b'\x00', 1)[0].decode('utf-8', errors='replace')


def _klass_name(pr, klass_ptr) -> str:
    """Il2CppClass* → 类名（类指针 +0x10 直接取名；区别于实例指针需先解一层 klass）。"""
    try:
        name_ptr = pr.u64(klass_ptr + 0x10)
        return _cstr(pr, name_ptr) if valid_ptr(name_ptr) else ''
    except MemoryReadError:
        return ''


def _is_delegate_array(pr, ptr) -> bool:
    """委托数组判定：数组自身类名含 Delegate（如 System.Delegate[]）且长度合理。

    注意判的是数组 klass 而非元素——元素是 System.Action`1 等具体委托类型，类名不含 Delegate。
    """
    try:
        n = pr.u32(ptr + 0x18)
        if not (0 < n <= 64):
            return False
        arr_klass = pr.u64(ptr)
    except MemoryReadError:
        return False
    return valid_ptr(arr_klass) and 'Delegate' in _klass_name(pr, arr_klass)


def _find_meter_via_handler(pr, handler, moff) -> int | None:
    """处理器对象 → 委托数组字段 → 各委托的 target（偏移实测 +0x20）= 计量器实例。"""
    target_off = moff['delegate_target']
    for off in range(0x00, _HANDLER_SPAN, 8):
        try:
            p = pr.u64(handler + off)
        except MemoryReadError:
            continue
        if not (valid_ptr(p) and p != handler) or not _is_delegate_array(pr, p):
            continue
        try:
            n = pr.u32(p + 0x18)
        except MemoryReadError:
            continue
        for i in range(min(n, _MAX_DELEGATES)):
            try:
                d = pr.u64(p + 0x20 + 8 * i)
                target = pr.u64(d + target_off)
            except MemoryReadError:
                continue
            if valid_ptr(target) and _klass_name(pr, pr.u64(target)) == _METER_KLASS:
                return target
    return None


def _locate_meter(pr, loc: Locator, moff) -> int | None:
    """锚点 RVA 用法槽 → 候选类 → static_fields[+handler_field] → 处理器 → 计量器实例。"""
    for slot in loc.scan_usage_slots(moff['anchor_rva'], span=256):
        try:
            klass = pr.u64(slot)
        except MemoryReadError:
            continue
        if not valid_ptr(klass):
            continue
        try:
            sf = loc.il.static_fields(klass)
            handler = pr.u64(sf + moff['handler_field'])
        except MemoryReadError:
            continue
        if not valid_ptr(handler):
            continue
        meter = _find_meter_via_handler(pr, handler, moff)
        if meter:
            return meter
    return None


def _same_image(cached: str, want: str) -> bool:
    """能否复用上次的 pid：可执行文件名必须一致。

    pid 会被系统回收：只判「句柄能打开」就可能读到一个毫不相干的进程，而这正是
    「宁可红不出脏」要挡的那类错。取不到名称（''）一律不复用。
    """
    return bool(cached) and str(cached).lower() == str(want).lower()


@contextlib.contextmanager
def _process(off):
    """只读进程通道：优先复用上次的 pid，省掉每秒一次的 Toolhelp 全进程枚举。

    复用失败（游戏已退/pid 被回收/权限变化）→ 退回一次全枚举并给出标准错误码；
    稳态开销因此只剩 OpenProcess + 名称核对 + 24 字节读取。
    """
    name = str(off['process_name'])
    cached = int(_meter_cache['pid'] or 0)
    if cached:
        try:
            pr = ProcessReader(cached)
        except MemoryReadError:
            pr = None
        if pr is not None and _same_image(pr.image_name(), name):
            try:
                yield pr
            finally:
                pr.close()
            return
        if pr is not None:
            pr.close()
        _forget_meter()
    pid = ProcessReader.find_process(name)
    if not pid:
        raise MemoryImportError('未找到 Deskrawl.exe 进程（游戏未运行）', 'env', code='no_process')
    with ProcessReader(pid) as pr:
        yield pr


def read_dps_meter(off=None) -> dict:
    """读一次 DPS 计：{'total','dps','start_time','last_tick'}（单位与游戏一致）。

    全程只读（OpenProcess VM_READ）；定位链以类名自校验收尾，读数值做
    有限性/时序校验（宁可抛错不出脏数据）。游戏未运行抛 no_process；
    不在假人图/链路失配抛 data。
    """
    off = off or load_offsets()
    moff = off.get('dps_meter') or {}
    if not moff.get('anchor_rva'):
        raise MemoryImportError('偏移表缺少 dps_meter 节（需更新 memory_offsets.json）', 'data')
    with _process(off) as pr:
        pid = pr.pid
        meter = _cached_meter(pid)
        # 缓存的实例指针还要能读到 klass 才算有效：切图/重启后它可能已失效（读不到或变 0）
        if not meter or not valid_ptr(pr.u64(meter)):
            _forget_meter()
            meter = _locate_meter(pr, Locator(pr, _StaticFieldsOnly(
                pr, off['il2cpp']['static_fields']), off), moff)
            if not meter:
                raise MemoryImportError(
                    '未定位到 DPS 计（需在训练假人地图且累计过伤害；游戏更新后需重算 anchor_rva）', 'data')
            _store_meter(pid, meter)
        raw = pr.read(meter + moff['total'], 24)   # total/start/last 三个 double 连续
        if not raw or len(raw) != 24:
            # pr.read 失败返回 None（不抛异常）：不显式判就会在校验之外变成 TypeError，
            # 线程兜底只能报「data + 异常类名」，排障时看不出是「指针失效」还是「校验不过」
            _forget_meter()                        # 指针失效：下次重新定位
            raise MemoryImportError('DPS 计字段不可读（指针可能已失效，下次轮询重定位）', 'data')
        total, start_time, last_tick = struct.unpack('<3d', raw)
    if (not all(map(math.isfinite, (total, start_time, last_tick)))
            or total < 0 or start_time < 0 or last_tick < start_time):
        _forget_meter()
        raise MemoryImportError('DPS 计读数未通过值域/时序校验（游戏状态变化？稍后重试）', 'data')
    return {'total': total, 'start_time': start_time, 'last_tick': last_tick,
            'dps': meter_dps(total, start_time, last_tick)}


class _StaticFieldsOnly:
    """最小 il2cpp 适配：dps_meter 链路只用到 static_fields 这一个基元。

    不复用 memory_import.Il2CppReader 的动机：那套构造要读一堆运行时字段，
    这里只需要 klass+0xB8，独立小适配反而让链路依赖一目了然。
    """

    def __init__(self, pr, static_fields_off: int):
        self._pr = pr
        self._sf = static_fields_off

    def static_fields(self, klass):
        v = self._pr.u64(klass + self._sf)
        if not valid_ptr(v):
            raise MemoryReadError('static_fields 不可读')
        return v
