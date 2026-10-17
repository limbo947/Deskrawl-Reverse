# -*- coding: utf-8 -*-
"""联机角色数据只读导入：定位 → 双读快照 → 校验（M2 核心，α/β 双模式）。

用途：游戏运行中把角色数据读成结构化快照——7 个聚合字典（面板 Final）、背包/仓库
（UID+名称）、装备 12 槽（β：逐件词条/强化/宝石）。成功标准 = 与 mem_probe 逐项一致 +
双读一致；全程只读（见 memory_reader 的硬约束）。

设计取舍：
- 自包含（仅 stdlib + memory_reader），不 import tools/scripts —— 继承 GUI 包不依赖逆向脚本的约束；
- 一切构建相关偏移集中在 memory_offsets.json，游戏更新后只改一处；
- 校验哲学「宁可红不出脏」：结构/键域/值域/双读任一失败即抛错，绝不把可疑数据当快照返回；
- α/β 模式是能力降级而非开关：装备容器或实例表不可用时自动降级 α 并给出 warnings。

拆分（2026-10-17）：原文件 749 有效行（已过 700 拆分行阈值），拆出两块**无共享状态**的部分——
错误态 `memory_errors`、定位基元 `memory_locate`、快照硬校验 `memory_validate`；本文件只留
「快照构建 + 双读编排」，即真正需要同时看到偏移表、解码器与进程的那一段。
"""
from __future__ import annotations

import struct
import time
from typing import List

from .memory_errors import MemoryImportError
from .memory_locate import Locator
from .memory_reader import (ActkCodec, Il2CppReader, MemoryReadError, ProcessReader,
                            valid_ptr)
from .memory_snapshot import (SnapshotResult, _fingerprints, _section_diff,
                              check_fingerprints, load_offsets)
from .memory_validate import validate_snapshot

# 定位基元与错误态已拆到 memory_locate / memory_errors，这里保留再导出：dps_meter、memdump、
# app、selftest 都从本模块取这两个名字，搬迁不该逼调用方改 import。
__all__ = ['MemoryImportError', 'Locator', 'SnapshotBuilder', 'SnapshotResult',
           'import_snapshot', 'load_offsets', 'check_fingerprints']


class SnapshotBuilder:
    """快照读取与校验：定位一次、读取多遍；双读一致性由 import_snapshot 编排比较。"""

    def __init__(self, il, codec, off, loc):
        self.il = il
        self.pr = il.pr
        self.codec = codec
        self.off = off
        self.loc = loc
        self.warnings: List[str] = []
        self.gm = self.inv = self.sto = self.em = self.nfi = None
        self.name_map = {}        # ItemData 指针 → SO 名称（SaveSystem.ngi 倒排）
        self.uid2gid = {}         # ItemUid → GeneratedItemData*（gi.myk）
        self.slot_expect = {int(k): v for k, v in off['equip_slot_id_to_type'].items()}

    def _warn(self, msg):
        """多遍读取会重复触发同一警告；去重保证 warnings 干净可读。"""
        if msg not in self.warnings:
            self.warnings.append(msg)

    def locate(self):
        """定位锚点与索引：必需项（GM/背包/仓库）失败=硬错误；增强项失败=降级警告。"""
        g = self.off['singleton_getters']
        self.gm = self.loc.find_singleton(g['GameManager']['rva'], g['GameManager']['klass'])
        self.inv = self.loc.find_singleton(g['Inventory']['rva'], g['Inventory']['klass'])
        self.sto = self.loc.find_singleton(g['Storage']['rva'], g['Storage']['klass'])
        if not (self.gm and self.inv and self.sto):
            raise MemoryImportError('GameManager/Inventory/Storage 单例未定位'
                                    '（角色未加载或版本漂移；请进入角色后重试）', 'env',
                                    code='no_hero')
        self.nfi = self.loc.find_save_system()
        if self.nfi:
            self._build_name_map()
        else:
            self._warn('SaveSystem 链未定位：角色摘要与物品名称将缺失')
        eq = self.off['singleton_getters']['EquipmentManager']
        self.em = self.loc.find_singleton(eq['rva'], eq['klass'])
        if self.em:
            self._build_gid_map()
        else:
            self._warn('EquipmentManager 未定位：降级 α 模式（无装备明细）')

    def _build_name_map(self):
        """ngi: Dictionary<string, ItemData>（535 条缓存）→ {SO指针: 名称}。
        SO 托管名恒空，这个倒排是运行时官方的名称来源（替代 so_dump 静态表）。"""
        ngi = self.pr.u64(self.nfi + self.off['save_system']['item_name_cache'])
        try:
            entries, _ = self.il.dict_entries(ngi, self.off['entry_steps']['ptr'])
        except MemoryReadError as e:
            self._warn(f'物品名称索引不可用：{e}')
            return
        for e in entries:
            nm = self.il.dict_entry_key_str(e)
            p = self.il.dict_entry_value(e)
            if nm and valid_ptr(p):
                self.name_map[p] = nm

    def _build_gid_map(self):
        """gi.myk: Dictionary<uid, GeneratedItemData> → uid→实例数据（β 词条/强化来源）。"""
        gi = self.off['generated_items']
        kls = self.loc.find_static_klass(gi['scan_rvas'], gi['klass'])
        if not kls:
            self._warn('gi 静态类未定位：装备实例数据不可用，降级 α 模式')
            return
        try:
            myk = self.pr.u64(self.il.static_fields(kls) + gi['items'])
            entries, _ = self.il.dict_entries(myk, self.off['entry_steps']['ptr'])
        except MemoryReadError as e:
            self._warn(f'装备实例字典不可用：{e}；降级 α 模式')
            return
        for e in entries:
            u = self.il.dict_entry_key_str(e)
            p = self.il.dict_entry_value(e)
            if u and valid_ptr(p):
                self.uid2gid[u] = p

    def _find_player(self):
        """进图态优先（GameManager+0x40 → PlayerCombatController+0x20），
        城镇态兜底（+0x48 → PlayerTownController+0x20）；两者皆空=角色未加载。"""
        gm_off = self.off['game_manager']
        c_off = self.off['controller']['player']
        want = self.off['player']['klass']
        for field_off, town in ((gm_off['combat_controller'], False),
                                (gm_off['town_controller'], True)):
            ctrl = self.pr.u64(self.gm + field_off)
            if not valid_ptr(ctrl):
                continue
            player = self.pr.u64(ctrl + c_off)
            if not valid_ptr(player):
                continue
            nm, _ = self.il.klass_name(player)
            if nm != want:
                raise MemoryReadError(f'Player 链类名不符：{nm!r}（应为 {want!r}）')
            return player, town
        raise MemoryImportError('GameManager 控制器未持有 Player（角色未加载/在主菜单）',
                                'env', code='no_hero')

    def _read_stat_dict(self, d, label):
        """Dictionary<StatType, ObscuredDouble>：键 i32@+8，值 ObscuredDouble@+0x10（0x28）。"""
        entries, _free = self.il.dict_entries(d, self.off['entry_steps']['stat_double'])
        kv = {}
        for e in entries:
            key = self.il.dict_entry_key_i32(e)
            val = self.codec.obsc_double(e + self.il.o['entry_value'])
            if val is None:
                raise MemoryReadError(f'字典 {label} 值解码失败')
            kv[key] = val
        return kv

    def _read_plain_double_dict(self, d, label):
        """Dictionary<StatType, double>：键 i32@+8，值**普通 double**@+0x10，步长 0x18。

        为什么单独一份：StatusEffectController 的 flat/pct/mult 三个增益层是明文 double
        （dump.cs 两版均为 `double`），与面板字典（ObscuredDouble，步长 0x38）不同。照
        ObscuredDouble 解会在 buff 层非空时解出 nan（活体 buff 一旦存在即暴露）。
        """
        entries, _free = self.il.dict_entries(d, self.off['entry_steps']['stat_plain_double'])
        kv = {}
        for e in entries:
            key = self.il.dict_entry_key_i32(e)
            raw = self.pr.read(e + self.il.o['entry_value'], 8)
            if raw is None:
                raise MemoryReadError(f'字典 {label} 值读取失败')
            kv[key] = struct.unpack('<d', raw)[0]
        return kv

    def _read_slots(self, arr):
        """InventorySlot[]（引用数组）：Item@0x10 / Count@0x18 / ItemUid@0x20；空槽跳过。

        领域事实：可堆叠材料/宝石（GemData 等）没有实例 UID（uidp=0x0 或空串），
        这是正常态而非结构错误——空 UID 条目不参与实例级追踪（对拍时按 '' 计入列表）。
        扩展（2026-10-08）：条目附带 EquipSlot 类型（ItemData+0x90）；武器（类型 1）且
        UID 在实例表时进一步附带逐件实例数据（词条/强化/宝石）——仓库/背包候选武器的
        数据源，与装备槽同构（探针实证：仓库 87 件全部可读，详见 PROGRESS）。
        """
        first, n = self.il.array_items(arr)
        iso = self.off['inventory_slot']
        out = []
        for i in range(n):
            s = self.pr.u64(first + 8 * i)
            if not valid_ptr(s):
                continue
            item = self.pr.u64(s + iso['item'])
            uidp = self.pr.u64(s + iso['uid'])
            cnt = self.pr.i32(s + iso['count'])
            if uidp is None or cnt is None:
                raise MemoryReadError('InventorySlot 字段读取失败（并发修改？）')
            uid = self.il.wstr(uidp) if uidp else ''
            if uid is None:
                raise MemoryReadError('InventorySlot.ItemUid 读取失败')
            if not uid and not valid_ptr(item):
                continue
            rec = {'uid': uid, 'count': cnt, 'name': self.name_map.get(item)}
            if valid_ptr(item):
                rec['equip_slot_type'] = self.pr.i32(item + self.off['item_data']['equip_slot'])
                # 装备候选（任意槽，类型 1..11）：UID 命中实例表才附逐件词条
                # （α 降级时 uid2gid 为空，条目保持精简，由 from_snapshot 汇总告警）
                est = int(rec['equip_slot_type'] or 0)
                if 1 <= est <= 11 and uid and uid in self.uid2gid:
                    inst = self._read_instance(uid)
                    if inst:
                        rec.update(inst)
            out.append(rec)
        return out

    def _read_modifiers(self, arr):
        """StatModifier[]（struct 0x1C 内联）：Stat@0 / ModifierType@4 / ObscuredFloat@8。"""
        first, n = self.il.array_items(arr)
        o = self.off['stat_modifier']
        out = []
        for i in range(n):
            e = first + o['size'] * i
            val = self.codec.obsc_float(e + o['value'])
            out.append([self.pr.i32(e + o['stat']), self.pr.i32(e + o['type']), val])
        return out

    def _read_str_array(self, arr):
        first, n = self.il.array_items(arr)
        return [self.il.wstr(self.pr.u64(first + 8 * i)) for i in range(n)]

    def _read_runes(self) -> list:
        """符文槽：RuneManager（单例）6 槽 → [{'name','uid','level'}]。

        为什么单独读：符文不在装备链里（RuneManager 直接持有 RuneData[] + 实例 UID 数组），
        而它是「技能等级+N」的唯一来源（旋风斩 2×6/6 符文 = +8 级 → tooltip 185%），
        也带自身属性。定位失败只告警（降级为无符文，技能等级按基础值算）。
        """
        ro = self.off.get('rune_manager') or {}
        if not ro:
            return []
        rm = self.loc.find_singleton(ro['getter_rva'], ro['klass'])
        if not valid_ptr(rm):
            self._warn('RuneManager 未定位：符文槽未计入（技能等级加成缺失）')
            return []
        fn, nn = self.il.array_items(self.pr.u64(rm + ro['runes']))
        fu, nu = self.il.array_items(self.pr.u64(rm + ro['uids']))
        out = []
        for i in range(min(nn, nu, int(ro.get('max_slots') or 6))):
            rdata = self.pr.u64(fn + 8 * i)
            uidp = self.pr.u64(fu + 8 * i)
            uid = self.il.wstr(uidp) if valid_ptr(uidp) else ''
            name = self.name_map.get(rdata) if valid_ptr(rdata) else None
            if not name:
                if valid_ptr(rdata):
                    self._warn(f'符文槽 {i} 名称未在名称索引命中（UID {uid}），未计入')
                continue
            level = 0
            if uid and uid in self.uid2gid:
                inst = self._read_instance(uid)
                if inst:
                    level = int(inst.get('rune_level') or 0)
            out.append({'name': str(name), 'uid': uid or '', 'level': level})
        return out

    def _read_instance(self, uid):
        """按 UID 读 GeneratedItemData 逐件实例数据（词条/强化/宝石），与装备槽同构。

        UID 不在实例表返回 None（调用方决定降级语义）；类名自校验，漂移即抛错。
        """
        g = self.uid2gid.get(uid)
        if not valid_ptr(g):
            return None
        gnm, _ = self.il.klass_name(g)
        if gnm != self.off['generated_item_klass']:
            raise MemoryReadError(f'UID {uid} 实例对象类名 {gnm!r} 不符')
        gio = self.off['generated_item']
        return {'item_level': self.pr.i32(g + gio['item_level']),
                'rarity': self.pr.i32(g + gio['rarity']),
                'upgrade_level': self.pr.i32(g + gio['upgrade_level']),
                'rune_level': self.pr.i32(g + gio['rune_level']),
                'socket_count': self.pr.i32(g + gio['socket_count']),
                'modifiers': self._read_modifiers(self.pr.u64(g + gio['modifiers'])),
                'socketed_gems': self._read_str_array(self.pr.u64(g + gio['socketed_gems']))}

    def _read_equipment(self):
        """β：mqz 槽→ItemData + mra 槽→uid + myk 逐件实例数据（词条/强化/宝石）。

        ItemData.EquipSlot 必须与槽位期望映射一致（dce 表）——这是区分「真装备链」
        与「碰巧读到的数组」的关键交叉校验，不符即抛错。
        """
        if not self.em or not self.uid2gid:
            return None
        eo = self.off['equipment_manager']
        qz, _ = self.il.dict_entries(self.pr.u64(self.em + eo['slot_item']),
                                     self.off['entry_steps']['ptr'])
        ra, _ = self.il.dict_entries(self.pr.u64(self.em + eo['slot_uid']),
                                     self.off['entry_steps']['ptr'])
        item_by_slot = {self.il.dict_entry_key_i32(e): self.il.dict_entry_value(e) for e in qz}
        uid_by_slot = {self.il.dict_entry_key_i32(e):
                       self.il.wstr(self.il.dict_entry_value(e)) for e in ra}
        slots = []
        for slot in sorted(set(item_by_slot) | set(uid_by_slot)):
            item, uid = item_by_slot.get(slot), uid_by_slot.get(slot)
            if not valid_ptr(item):
                raise MemoryReadError(f'装备槽 {slot} 的 ItemData 指针无效')
            if not uid:
                raise MemoryReadError(f'装备槽 {slot} 的 UID 为空')
            nm_item, _ = self.il.klass_name(item)
            if nm_item != self.off['item_data']['klass']:
                raise MemoryReadError(f'装备槽 {slot} 对象类名 {nm_item!r} 非 ItemData')
            eq_type = self.pr.i32(item + self.off['item_data']['equip_slot'])
            expect = self.slot_expect.get(slot)
            if expect is not None and eq_type != expect:
                raise MemoryReadError(f'装备槽 {slot} EquipSlot={eq_type} != 期望 {expect}'
                                      '（装备链偏移漂移？）')
            rec = {'slot': slot, 'uid': uid, 'name': self.name_map.get(item),
                   'item_type': self.pr.i32(item + self.off['item_data']['type']),
                   'equip_slot_type': eq_type, 'modifiers': None, 'socketed_gems': None}
            inst = self._read_instance(uid)
            if inst:
                rec.update(inst)
            else:
                self._warn(f'装备 UID {uid} 不在实例表（刚装备未注册？），该件无词条明细')
            slots.append(rec)
        return slots

    def _read_conditionals(self, player):
        """nuf/nug 条件属性表（Player.ConditionalModValue@0x503C70 的输入；布局见 memory_offsets.json 注释）。

        值字段是内联 double（非 Obscured）；ability/status 指针非空表示该条带技能/状态门控，
        导出为 1（面板复算侧不猜门控状态，跳过并告警）。"""
        cm = self.off['player']['conditional_mods']
        stride = cm['tuple_stride']
        out = {'nuf': [], 'nug': []}
        for label in ('nuf', 'nug'):
            lst = self.pr.u64(player + cm[label])
            if not valid_ptr(lst):
                continue
            first, n = self.il.list_items(lst)
            for i in range(n):
                b = self.pr.read(first + stride * i, stride)
                if b is None:
                    raise MemoryReadError(f'{label} 条件属性表条目不可读')
                cond, = struct.unpack_from('<i', b, 0)
                if label == 'nuf':
                    radius, = struct.unpack_from('<f', b, 4)
                    stat, mtype = struct.unpack_from('<ii', b, 8)
                    value, = struct.unpack_from('<d', b, 16)
                    gated, = struct.unpack_from('<q', b, 24)
                    out['nuf'].append([cond, radius, stat, mtype, value, 1 if gated else 0])
                else:
                    status, = struct.unpack_from('<q', b, 8)
                    stat, mtype = struct.unpack_from('<ii', b, 16)
                    value, = struct.unpack_from('<d', b, 24)
                    out['nug'].append([cond, 1 if status else 0, stat, mtype, value])
        return out

    def _read_status_mods(self, player):
        """StatusEffectController 三字典（StatusEffectController.SumStatBonus@0x4DB980 的 g1/g2/g3 层）。空表=无增益。"""
        sc = self.off['player']['status_controller']
        ctrl = self.pr.u64(player + sc['ptr'])
        out = {}
        for label in ('flat', 'pct', 'mult'):
            d = self.pr.u64(ctrl + sc[label]) if valid_ptr(ctrl) else 0
            out[label] = self._read_plain_double_dict(d, f'status.{label}') if valid_ptr(d) else {}
        return out

    def _read_primary_stat(self):
        """GameManager+0x38 → HeroData+0x2C（PrimaryStat 0=力量/1=敏捷/2=智力），类名自校验。"""
        hero = self.pr.u64(self.gm + self.off['game_manager']['hero_data']) if self.gm else 0
        if not valid_ptr(hero):
            self._warn('HeroData 未定位：主属性加项（BasePrimaryStat）未导出，面板复算缺该加项')
            return None
        nm, _ = self.il.klass_name(hero)
        if nm != self.off['hero_data']['klass']:
            self._warn(f'HeroData 类名不符（{nm!r}）：主属性未导出')
            return None
        v = self.pr.i32(hero + self.off['hero_data']['primary_stat'])
        if v not in (0, 1, 2):
            self._warn(f'HeroData.PrimaryStat 值域异常（{v}）：主属性未导出')
            return None
        return v

    def _read_hero_class(self):
        """GameManager+0x38 → HeroData+0x30（HeroClass 枚举 1/2/4/8），类名自校验。

        职业决定了结果区列出哪些伤害技能（HeroData.Abilities）；读不到只降级技能表，不影响数值。
        """
        hero = self.pr.u64(self.gm + self.off['game_manager']['hero_data']) if self.gm else 0
        if not valid_ptr(hero):
            return None
        nm, _ = self.il.klass_name(hero)
        if nm != self.off['hero_data']['klass']:
            return None
        v = self.pr.i32(hero + self.off['hero_data']['class'])
        if v not in (1, 2, 4, 8):
            self._warn(f'HeroData.Class 值域异常（{v}）：技能表不可用')
            return None
        return v

    def _read_hero_abilities(self):
        """HeroData+0x50 → List<AbilityData*>（顺序与 so_dump HeroData.Abilities 一致，活体实证）。

        用途：运行时 AbilityData* → 技能名（按技能修正按指针存储）。失败只告警，数值导入不受影响。
        """
        hero = self.pr.u64(self.gm + self.off['game_manager']['hero_data']) if self.gm else 0
        if not valid_ptr(hero):
            return []
        try:
            first, n = self.il.list_items(self.pr.u64(hero + self.off['hero_data']['abilities']))
        except MemoryReadError as e:
            self._warn(f'HeroData.Abilities 不可用：{e}')
            return []
        out = []
        for i in range(n):
            p = self.pr.u64(first + 8 * i)
            if not valid_ptr(p):
                continue
            nm, _ = self.il.klass_name(p)
            if nm != self.off['ability_klass']:
                self._warn(f'技能 {i} 类名 {nm!r} 非 AbilityData：技能表可能不完整')
                continue
            out.append(p)
        return out

    def _read_talent_ability_mods(self, player):
        """按角色已点天赋读「按技能修正」（TalentEffect_AbilityModifier），只取频次相关项。

        链路：Player+0x248 Dictionary<TalentData*,int>（点数）→ TalentData+0x48 Effects[]
        → 元素对象 TalentEffect_AbilityModifier（Stat/Ability/Modifier）。只收 ChannelSpeed(8) /
        StrikeCount(9) 这两类会改变「每秒命中次数」的修正；Damage/Crit 等进已有属性链更合适，暂不在此叠加。
        值 = 点数×Base + PerLevel×点数×(点数-1)/2（每级累加；死神之刃 10/10→+100% 与 tooltip 实证）。
        失败只告警：技能频次降级为「无天赋加成」。返回 [stat, ability_ptr, value] 列表。
        """
        te = self.off['talent_effect_ability_modifier']
        wanted = set(int(v) for v in self.off['ability_mod_stat'].values())
        out = []
        d = self.pr.u64(player + self.off['player']['talents'])
        try:
            entries, _ = self.il.dict_entries(d, self.off['entry_steps']['ptr'])
        except MemoryReadError as e:
            self._warn(f'天赋表不可用：{e}')
            return out
        for e in entries:
            tptr = self.pr.u64(e + self.il.o['entry_key'])
            pts = self.pr.i32(e + self.il.o['entry_value'])
            if not valid_ptr(tptr) or pts is None or pts <= 0:
                continue
            try:
                first, n = self.il.array_items(self.pr.u64(tptr + self.off['talent_data']['effects']))
            except MemoryReadError:
                continue
            for i in range(n):
                obj = self.pr.u64(first + 8 * i)
                if not valid_ptr(obj):
                    continue
                nm, _ = self.il.klass_name(obj)
                if nm != te['klass']:
                    continue
                stat = self.pr.i32(obj + te['stat'])
                if stat not in wanted:
                    continue
                ability = self.pr.u64(obj + te['ability'])
                if not valid_ptr(ability):
                    continue
                base = self.codec.obsc_float(obj + te['modifier'])
                per = self.codec.obsc_float(obj + te['modifier'] + te['per_level_stride'])
                if base is None or per is None:
                    continue
                val = pts * float(base) + float(per) * pts * (pts - 1) / 2.0
                out.append([int(stat), ability, val])
        return out

    def _read_paragon(self) -> dict:
        """读巅峰点数分配：静态管理器（混淆类，dump.cs hh）static_fields[+0x40] 的
        Dictionary<StatType,int>。

        定位（2026-10-10 活体实测，dyt(StatType) 反汇编）：扫 dyt/dzg 用法槽 → 候选类 →
        static_fields[+0x40] 须为合法字典（count≤80、全键在 stat_key_range、点数 (0,999]），
        形状+值域双校验替代类名校验（类名每版混淆）。容器不可用只告警不阻断：
        巅峰对面板是增量信息，base 已含其贡献，读不到就维持旧口径。
        """
        po = self.off.get('paragon') or {}
        if not po.get('anchor_rvas'):
            return {}
        klo, khi = self.off['stat_key_range']
        seen = set()
        for rva in po['anchor_rvas']:
            for slot in self.loc.scan_usage_slots(rva, span=256):
                try:
                    klass = self.pr.u64(slot)
                except MemoryReadError:
                    continue
                if not valid_ptr(klass) or klass in seen:
                    continue
                seen.add(klass)
                try:
                    sf = self.il.static_fields(klass)
                    d = self.pr.u64(sf + po['static_dict'])
                    entries = self.pr.u64(d + po['entries']) if valid_ptr(d) else None
                    count = self.pr.i32(d + po['count']) if valid_ptr(d) else None
                except MemoryReadError:
                    continue
                if not valid_ptr(entries) or count is None or not 0 <= count <= 80:
                    continue
                out, ok = {}, True
                for i in range(count):
                    ent = entries + po['data'] + i * po['stride']
                    try:
                        stat = self.pr.i32(ent + po['key'])
                        pts = self.pr.i32(ent + po['value'])
                    except MemoryReadError:
                        ok = False
                        break
                    if not (klo <= stat <= khi and 0 < pts <= 999):
                        ok = False
                        break
                    out[int(stat)] = int(pts)
                if ok:
                    return out
        self._warn('巅峰容器未定位（结构漂移？读数维持不含巅峰的旧口径）')
        return {}

    def _read_hero(self):
        """SaveSystem：nfk 槽位索引 → SaveContainer.OnlineSlots[nfk] 摘要。
        快照带槽位摘要（名字/等级/profile），防切角色后用过期快照静默错配构建。"""
        if not self.nfi:
            return None
        ss = self.off['save_system']
        idx = self.pr.i32(self.nfi + ss['field_slot_index'])
        nfn = self.pr.u64(self.nfi + ss['container'])
        if not valid_ptr(nfn) or idx is None:
            return None
        first, n = self.il.list_items(self.pr.u64(nfn + self.off['container']['online_slots']))
        if not 0 <= idx < n:
            return None
        rec = self.pr.u64(first + 8 * idx)
        if not valid_ptr(rec):
            return None
        co = self.off['container']
        return {'name': self.il.wstr(self.pr.u64(rec + co['rec_name'])),
                'summary_level': self.pr.i32(rec + co['rec_summary_level']),
                'profile': self.il.wstr(self.pr.u64(rec + co['rec_profile'])),
                'slot_index': idx}

    def read_pass(self) -> dict:
        """完整读取一遍。结构性失败抛 MemoryReadError（供重试）；值域问题留给 validate。"""
        player, town = self._find_player()
        po = self.off['player']
        lvl = self.codec.obsc_int(player + po['level'])
        if lvl is None:
            raise MemoryReadError('player._level 读取失败')
        hp_raw = self.pr.read(player + po['current_health'], 8)
        if hp_raw is None:
            raise MemoryReadError('player.CurrentHealth 读取失败')
        fields = {
            'BaseMaxHealth': self.codec.obsc_long(player + po['base_max_health']),
            'BaseDamage': self.codec.obsc_long(player + po['base_damage']),
            'BaseMoveSpeed': self.codec.obsc_float(player + po['base_move_speed']),
            'BaseCritChance': self.codec.obsc_float(player + po['base_crit_chance']),
            'BaseCritDamage': self.codec.obsc_float(player + po['base_crit_damage']),
            'BaseAttackSpeed': self.codec.obsc_float(player + po['base_attack_speed']),
            'BaseDodgeChance': self.codec.obsc_float(player + po['base_dodge_chance']),
            'BaseMaxMana': self.codec.obsc_long(player + po['base_max_mana']),
            'CurrentHealth': struct.unpack('<q', hp_raw)[0],
            'CurrentXP': self.codec.obsc_long(player + po['current_xp']),
            'BasePrimaryStat': self.codec.obsc_float(player + po['base_primary_stat']),
            'BaseLifeOnHit': self.codec.obsc_float(player + po['base_life_on_hit']),
            'BaseLifeOnKill': self.codec.obsc_float(player + po['base_life_on_kill']),
            'BaseCooldownReduction': self.codec.obsc_float(player + po['base_cooldown_reduction']),
        }
        dicts = {label: self._read_stat_dict(self.pr.u64(player + offv), label)
                 for label, offv in po['stat_dicts'].items()}
        return {
            'level': lvl, 'fields': fields, 'dicts': dicts, 'town': town,
            'conditionals': self._read_conditionals(player),
            'status_mods': self._read_status_mods(player),
            'primary_stat': self._read_primary_stat(),
            'hero_class': self._read_hero_class(),
            'hero_abilities': self._read_hero_abilities(),
            'talent_ability_mods': self._read_talent_ability_mods(player),
            'paragon': self._read_paragon(),
            'runes': self._read_runes(),
            'inventory': self._read_slots(self.pr.u64(self.inv + self.off['inventory']['slots'])),
            'storage': self._read_slots(self.pr.u64(self.sto + self.off['storage']['slots'])),
            'equipment': self._read_equipment(),
            'hero': self._read_hero(),
        }

    def validate(self, payload):
        """硬校验委托 memory_validate.validate_snapshot（校验是纯 payload 函数，已拆出）。

        保留这层方法只为让调用方读起来仍是「builder 的一次遍读 → 校验」；校验本体不依赖
        builder 的任何状态，单独放在 memory_validate.py 便于直接用构造的 payload 单测。
        """
        validate_snapshot(payload, self.off)


def import_snapshot(double_read=True) -> SnapshotResult:
    """导入入口：定位 → 双读快照 → 校验。失败抛 MemoryImportError。

    双读动机：值域内的并发修改（如力量 360→361）单遍校验查不出，两次读取逐值比较才
    拦得住；连续 3 次不一致说明游戏状态确实在动，宁可报错让用户择时再导（城镇/菜单）。
    """
    if struct.calcsize('P') != 8:
        raise MemoryImportError('当前 Python 为 32 位，无法读取 64 位游戏进程；'
                                '请使用 64 位解释器', 'env', code='py32')
    off = load_offsets()
    # 指纹先行：游戏更新后偏移/静态数据都可能失效，先拒绝再动手，避免「读得动但读错」
    problems = check_fingerprints(off)
    if problems:
        raise MemoryImportError('版本指纹不符：' + '；'.join(problems) +
                                '。请重新导出 schema/so_dump 并更新 memory_offsets.json 后重试',
                                'version', code='fingerprint')
    pid = ProcessReader.find_process(off['process_name'])
    if not pid:
        raise MemoryImportError(f'未找到 {off["process_name"]} 进程——请先启动游戏并进入角色',
                                'env', code='no_process')
    try:
        pr = ProcessReader(pid)
    except MemoryReadError as e:
        raise MemoryImportError(f'打开游戏进程失败：{e}', 'env',
                                code=('denied' if 'err=5' in str(e) else '')) from e
    with pr:
        il = Il2CppReader(pr, off['il2cpp'])
        builder = SnapshotBuilder(il, ActkCodec(pr), off, Locator(pr, il, off))
        builder.locate()
        prev, last_diff = None, []
        attempts = 3 if double_read else 1
        for attempt in range(attempts):
            try:
                cur = builder.read_pass()
            except MemoryReadError as e:
                last_diff = [f'读取异常：{e}']
                if attempt == attempts - 1:
                    raise MemoryImportError(f'读取连续失败：{e}')
                continue
            builder.validate(cur)
            if prev is None:
                prev = cur
                if not double_read:
                    break
                continue
            diff = _section_diff(prev, cur)
            if not diff:
                prev = cur
                break
            last_diff, prev = diff, cur
        else:
            raise MemoryImportError('双读一致性校验失败：连续读取内容不一致'
                                    f'（段：{", ".join(last_diff)}）——'
                                    '游戏状态正在变化，请稍后重试（城镇/菜单中更稳定）')
        payload = prev
    mode = 'beta' if (builder.uid2gid and payload['equipment']) else 'alpha'
    meta = {
        'time': time.strftime('%Y-%m-%d %H:%M:%S'),
        'pid': pid, 'mode': mode, 'town_mode': payload['town'],
        'final_dict': payload['final_dict'], 'hero': payload['hero'],
        'warnings': list(builder.warnings), 'fingerprints': _fingerprints(payload),
    }
    result = {
        'meta': meta,
        'player': {
            'level': payload['level'], 'fields': payload['fields'],
            'town_mode': payload['town'], 'final_dict': payload['final_dict'],
            'base': payload['dicts'][payload['final_dict']],
            'stat_dicts': payload['dicts'],
            'conditionals': payload['conditionals'], 'status_mods': payload['status_mods'],
            'primary_stat': payload['primary_stat'], 'hero_class': payload['hero_class'],
            'hero_abilities': payload['hero_abilities'],
            'talent_ability_mods': payload['talent_ability_mods'],
            'paragon': payload['paragon'],
            'runes': payload['runes'],
        },
        'inventory': payload['inventory'],
        'storage': payload['storage'],
        'equipment': payload['equipment'],
    }
    return SnapshotResult(time=meta['time'], pid=pid, mode=mode, town_mode=payload['town'],
                          warnings=meta['warnings'], payload=result)