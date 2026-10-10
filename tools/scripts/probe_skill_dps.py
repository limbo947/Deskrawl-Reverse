# -*- coding: utf-8 -*-
"""③-13 探针：量化「前摇/收招/站桩」对秒伤模型的影响。

为什么需要它：GUI 的秒伤模型（`deskrawl_gui/core/skill_service.py`）刻意忽略了
ChannelWindup/ChannelRecovery/StandingTime，此声明是否可接受取决于**实际数据量级**
——若这些字段在引导技能上非零且与 tick 同量级，忽略它们会系统性高估秒伤。
本探针只读 AbilityData，不改模型，先给量级再决定动不动代码。
"""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import SO_DUMP          # noqa: E402


def val(x):
    if isinstance(x, (int, float)):
        return x
    if isinstance(x, dict):
        if 'value' in x and isinstance(x['value'], (int, float)):
            return x['value']
        if 'Base' in x:
            return val(x['Base'])
    return None


def has_damage(rec):
    return any(e.get('__type__') == 'DamageEffect'
               for e in (rec.get('_managedRefs') or {}).get('__items__', []))


def main():
    with open(os.path.join(SO_DUMP, 'AbilityData.json'), encoding='utf-8') as fh:
        ab = json.load(fh)

    print('=== 字段取值分布（全部 124 条）===')
    for f in ('ChannelDuration', 'ChannelTickRate', 'ChannelWindup', 'ChannelRecovery',
              'StandingTime', 'CastOutOfCombat', 'IsStandingUponCasting'):
        c = Counter(val(r.get(f)) for r in ab)
        print(f'  {f:24s} {dict(sorted(c.items(), key=lambda z: (z[0] is None, z[0])))}')

    ch = [r for r in ab if (val(r.get('ChannelDuration')) or 0) > 0
          and (val(r.get('ChannelTickRate')) or 0) > 0 and has_damage(r)]
    print(f'\n=== 引导型伤害技能（{len(ch)} 个）：tick 间隔 vs 前摇+收招 ===')
    for r in ch:
        d = val(r['ChannelDuration'])
        t = val(r['ChannelTickRate'])
        w = val(r.get('ChannelWindup')) or 0.0
        rec = val(r.get('ChannelRecovery')) or 0.0
        st = val(r.get('StandingTime')) or 0.0
        cd = val(r.get('Cooldown')) or 0.0
        ticks = d / t if t else 0
        print(f"  {r['_name']:34s} dur={d:5.2f} tick={t:5.3f} ticks={ticks:5.1f} "
              f"windup={w:5.2f} recov={rec:5.2f} stand={st:4.2f} cd={cd:5.1f}")

    nd = [r for r in ab if has_damage(r)]
    print(f'\n=== 伤害技能总数 {len(nd)}；其中引导 {len(ch)}；'
          f'有前摇 {sum(1 for r in nd if (val(r.get("ChannelWindup")) or 0) > 0)}；'
          f'有收招 {sum(1 for r in nd if (val(r.get("ChannelRecovery")) or 0) > 0)}；'
          f'需站桩 {sum(1 for r in nd if r.get("IsStandingUponCasting"))}')


if __name__ == '__main__':
    main()
