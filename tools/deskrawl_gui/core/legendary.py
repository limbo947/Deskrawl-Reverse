# -*- coding: utf-8 -*-
"""传奇词条文案：装备名 → 游戏内原文（Equipments 表里的 `*.Desc` 描述）。

为什么单独成文件：文案有三层来源（整件 Desc / 特效 Desc / 特效类模板）且要按令牌填值，
塞进 localization（只管名字）或 item_editor（只管摆放）都会让那一处变成杂物间。

数据锚点（2026-10-19 实测，67 件带 `EquipmentEffects` 的装备）：整件 Desc 57 件、
特效级 Desc 4 件、`EquipmentEffect.<类>` 模板 4 件、其余 2 件靠「特效名前缀」匹配
（文案键是 `LegendaryNeck4_Retaliation.Desc`，特效名只有 `LegendaryNeck4`）。

令牌跨特效取值：一条描述常常覆盖同一件装备的多个子特效（`LegendaryGloves8` 的
`{damage}` 来自兄弟特效 `_Damage`），所以填值用的是「整件所有特效 + 其引用的状态记录」
合成出来的池子，而不是单个特效。

解析不到文案时返回空表而不是造一句话：调用方据此回落到手工录入，不拿占位文字冒充事实。
填不上的令牌原样保留花括号——看得见缺口比编一个数好。
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from typing import List

from deskrawl_calc.effects import unmodeled_classes

from .localization import ability_display_name, equipments_text, item_internal_name

# 未计入提示的固定文案：与「传奇词条」行同处显示，措辞必须一眼看懂是 DPS 口径缺口
_UNMODELED_NOTE = '（未计入 DPS）'

_TOKEN = re.compile(r'\{([0-9A-Za-z_]+)\}')

# 位置参数模板（{0}/{1}）没有字段名可推断，只能按类登记取值字段（实测仅这几条在用）
_POS_ARGS = {
    'EquipmentEffect.AllStats': ('Bonus',),
    'EquipmentEffect.AllAbilityLevels': ('Levels',),
    'EquipmentEffect.AbilityLevel': ('Levels',),
}

# 模板里的令牌与字段名对不上、后缀也匹配不到的，只能逐个登记（(类键, 令牌) → 字段）
_FIELD_ALIAS = {
    ('EquipmentEffect.DivineHelmet3', 'damage'): 'NormalEnemyMultiplier',
    ('EquipmentEffect.DivineHelmet3', 'elitedamage'): 'EliteEnemyMultiplier',
}


def legendary_lines(gd, display_name: str) -> List[str]:
    """装备名（简中显示名或内部名）→ 传奇词条原文行；无文案/名字不识别返回 []。

    含 B/C 面未接线特效的装备，末行缀「（未计入 DPS）」——静默缺失比不建模更误导。
    """
    internal = item_internal_name(gd, str(display_name or ''))
    if not internal or internal not in gd.items():
        return []
    table = equipments_text(gd)
    effects = list(gd.item_effects(internal))
    pool = _pool(gd, effects)
    whole = table.get(f'{internal}.Desc')
    if whole:
        lines = [_fill(str(whole), pool, '')]
    else:
        lines = []
        for eff in effects:
            line = _effect_text(table, eff, pool)
            if line:
                lines.append(line)
        if not lines:
            pref = _prefix_desc(table, internal)
            lines = [_fill(pref, pool, '')] if pref else []
    return _mark_unmodeled(lines, effects)


def _mark_unmodeled(lines: List[str], effs: list) -> List[str]:
    """末行缀「（未计入 DPS）」：只针对 B/C 面（数值型但口径没算），D 类触发不标。"""
    if lines and unmodeled_classes(effs):
        lines[-1] = lines[-1] + _UNMODELED_NOTE
    return lines


def _pool(gd, effects: list) -> list:
    """取值池 = 全部特效 + 它们引用的外部记录（`{duration}` 在 StatusEffectData、
    `{ability}` 在 AbilityData）。

    引用在这里就地展开成「同形字段」而不是另开文字通道：技能名以 `{SummoningAbility: 名}`
    的形状入池，`_text_field` 就能像数值字段一样按名字找到它（`{ability}` 由后缀命中）。
    """
    pool = list(effects)
    index = _status_index(getattr(gd, 'dir', ''))
    for eff in effects:
        for key, val in (eff or {}).items():
            if not isinstance(val, dict) or not val.get('pathID'):
                continue
            pid = int(val['pathID'])
            if 'ability' in key.lower():
                name = _ability_name(gd, pid)
                if name:
                    pool.append({key: name})
            elif 'Status' in key:
                rec = index.get(pid)
                if rec:
                    pool.append(rec)
    return pool


def _ability_name(gd, path_id: int) -> str:
    """技能引用 pathID → 简中名。`_name` 是混淆名（`MonkSpecial4`），必须过本地化表。"""
    try:
        name = gd.ability_name_by_pathid().get(int(path_id))
    except (AttributeError, OSError, ValueError, TypeError):
        return ''
    return ability_display_name(gd, name) if name else ''


@lru_cache(maxsize=4)
def _status_index(dir_key: str) -> dict:
    """StatusEffectData 的 pathID → 记录（GUI 侧自读，与 ability_level_bonuses 读 RuneData 同款）。"""
    if not dir_key:
        return {}
    try:
        with open(os.path.join(dir_key, 'StatusEffectData.json'), encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return {int(r.get('_pathid') or 0): r for r in data if isinstance(r, dict)}


def _prefix_desc(table: dict, stem: str) -> str:
    """`<stem>_…Desc` 前缀匹配（多段特效共用一段描述的那种）。"""
    if not stem:
        return ''
    for key, text in table.items():
        if key.startswith(f'{stem}_') and key.endswith('.Desc'):
            return str(text)
    return ''


def _class_key(cls: str) -> str:
    """`EquipmentEffect_AllStats` → 模板键 `EquipmentEffect.AllStats`。"""
    cls = str(cls or '')
    return 'EquipmentEffect.' + cls.split('EquipmentEffect_', 1)[-1]


def _effect_text(table: dict, eff: dict, pool: list) -> str:
    name = str(eff.get('_name') or '')
    cls_key = _class_key(eff.get('_class'))
    text = table.get(f'{name}.Desc') or _prefix_desc(table, name)
    if text:
        return _fill(str(text), pool, cls_key)
    tpl = table.get(cls_key)
    if tpl:
        return _fill(str(tpl), pool, cls_key)
    return ''


def _fill(text: str, pool: list, cls_key: str) -> str:
    """把 `{name}` / `{0}` 换成池子里的字段值。

    取值优先级：令牌声明（`XxxToken{Name,Format}`，含嵌套在托管引用里的，如 AttackScaling
    → `{damage}` 的 `0.#%`）> 同名字段 > 该类登记的别名 > 后缀匹配 > 前缀匹配。
    数值全都不中时才试文字字段（技能名等），避免「伤害」被填成一个名字。
    都对不上就原样保留：宁可露出 `{x}` 也不编一个数。
    """
    if '{' not in text:
        return text
    tokens = _token_values(pool)
    pos = _POS_ARGS.get(cls_key, ())

    def repl(m):
        key = m.group(1)
        if key.isdigit():
            idx = int(key)
            if idx < len(pos):
                hit = _field(pool, pos[idx], cls_key)
                if hit:
                    # 模板写成「+{0}%」时值本身是比例（0.3），放大成 30 再拼百分号
                    scale = 100.0 if text[m.end():m.end() + 1] == '%' else 1.0
                    return _fmt(hit[1] * scale, '0.#')
            return m.group(0)
        tok = tokens.get(key.lower())
        if tok:
            return _fmt(tok[0], tok[1])
        hit = _field(pool, key, cls_key)
        if hit:
            fname, val = hit
            # `*Multiplier` 是倍率，文案说的却是「提高多少」→ 1.2 读作 20%
            if fname.lower().endswith('multiplier'):
                return f'{(val - 1.0) * 100:g}%'
            return _fmt(val, '', key)
        word = _text_field(pool, key)
        return word or m.group(0)

    return _TOKEN.sub(repl, text)


def _token_values(pool: list) -> dict:
    """递归收集 `{Name:…, Format:…}` 令牌 → {小写名: (值, 格式)}；值与令牌是同节点兄弟。"""
    out = {}

    def walk(node):
        if isinstance(node, dict):
            for key, val in node.items():
                if key.endswith('Token') and isinstance(val, dict) and val.get('Name'):
                    src = node.get(key[:-5])
                    if src is not None:
                        out[str(val['Name']).lower()] = (_unwrap(src),
                                                         str(val.get('Format') or ''))
                walk(val)
        elif isinstance(node, list):
            for val in node:
                walk(val)

    walk(pool)
    return out


def _field(pool: list, name: str, cls_key: str = ''):
    """按字段名取数值 → (字段名, 值)；精确 → 别名 → 后缀 → 前缀，四档依次放宽。"""
    want = str(name).replace('_', '').lower()
    pairs = []
    for eff in pool:
        for key, val in (eff or {}).items():
            if key.startswith('_') or isinstance(val, (dict, list, bool)) or val is None:
                continue
            num = _unwrap(val)
            if isinstance(num, (int, float)):
                pairs.append((key, float(num)))

    for k, v in pairs:
        if k.replace('_', '').lower() == want:
            return k, v
    alias = _FIELD_ALIAS.get((cls_key, str(name).lower()))
    if alias:
        for k, v in pairs:
            if k == alias:
                return k, v
    for match in (lambda k: k.lower().endswith(want), lambda k: k.lower().startswith(want)):
        hits = [(k, v) for k, v in pairs if match(k)]
        if hits:
            return min(hits, key=lambda kv: len(kv[0]))       # 最短的那个最贴近令牌名
    return None


def _text_field(pool: list, name: str):
    """按字段名取文字值（技能名等）；匹配顺序与 `_field` 同构，但不参与数值格式化。

    `{ability}` 与字段 `SummoningAbility` 词形不同，靠后缀档命中——这是 `_pool` 把技能引用
    以 `{原名: 简中名}` 入池换来的；不额外登记别名，加了新引用字段便自动可用。
    """
    want = str(name).replace('_', '').lower()
    pairs = [(key, val) for eff in pool for key, val in (eff or {}).items()
             if not key.startswith('_') and isinstance(val, str) and val]
    for k, v in pairs:
        if k.replace('_', '').lower() == want:
            return v
    for match in (lambda k: k.lower().endswith(want), lambda k: k.lower().startswith(want)):
        hits = [(k, v) for k, v in pairs if match(k)]
        if hits:
            return min(hits, key=lambda kv: len(kv[0]))[1]
    return None


def _unwrap(val):
    """`LeveledFloat{Base,PerLevel}` / `Obscured*{value}` → 基础数值（与内核 unwrap 同语义）。"""
    if isinstance(val, dict):
        if 'Base' in val:
            return _unwrap(val['Base'])
        if 'value' in val:
            return val['value']
    return val


def _fmt(val, fmt: str, name: str = '') -> str:
    """按令牌格式渲染：`0.#%` 这类 C# 定点格式；无格式时按令牌名判断要不要折算百分数。

    无格式的比例推断是刻意的：没有令牌声明的模板（`有{chance}几率`）里 0.2 读作「0.2」
    会与游戏内文案差一个量级，而这类字段在本数据里基本都是概率/系数。但时长与层数不是
    比例（`每{cooldown}秒` 的 0.2 就该读作 0.2 秒），按令牌名排除掉。
    """
    try:
        num = float(val)
    except (TypeError, ValueError):
        return str(val)
    fmt = str(fmt or '')
    percent = fmt.endswith('%')
    if percent:
        num *= 100.0
    sharp = fmt.count('#')
    if sharp:
        text = f'{num:.{sharp}f}'.rstrip('0').rstrip('.')
    elif fmt:
        text = f'{num:.0f}'
    elif 0.0 < num < 1.0 and not _is_plain_number(name):
        return f'{num * 100:g}%'
    else:
        text = f'{num:g}'
    return f'{text}%' if percent else text


# 这些令牌是「时长/层数/次数」，无格式时不能按比例换算（否则 0.2 秒读成 20%）
_PLAIN_TOKENS = ('cooldown', 'duration', 'seconds', 'time', 'interval', 'delay',
                 'level', 'levels', 'stack', 'stacks', 'hits', 'count', 'amount')


def _is_plain_number(name: str) -> bool:
    low = str(name or '').lower()
    return any(tok in low for tok in _PLAIN_TOKENS)
