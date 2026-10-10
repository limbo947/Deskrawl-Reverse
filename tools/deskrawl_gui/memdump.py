# -*- coding: utf-8 -*-
"""内存快照 CLI：`python -m deskrawl_gui.memdump [--json] [--no-double-read]`。

定位=验收/对拍工具：与 tools/scripts/mem_probe.py 输出逐项对照（level/生命/仓库件数/
7 字典 KV），并打印字典段与物品 UID 段的逐值指纹，供「连跑两次逐值相等」的验收比较。
默认双读一致性校验（宁可红不出脏）。退出码：0 成功；2 环境错误；3 数据/校验失败。
"""
from __future__ import annotations

import argparse
import json
import sys

from deskrawl_calc.stattype import STAT_NAMES

from .core.memory_import import MemoryImportError, import_snapshot, load_offsets

_OFF = load_offsets()
_SLOT_NAMES = {int(k): v for k, v in _OFF['equip_slot_names'].items()}


def _print_human(res, double_read=True) -> None:
    p, meta = res.payload, res.payload['meta']
    player = p['player']
    hero = meta.get('hero') or {}
    print('=== Deskrawl 内存快照 memdump（严格只读）===')
    print(f"时间={res.time}  PID={res.pid}  模式={res.mode}（{'β 逐件' if res.mode == 'beta' else 'α 聚合'}）"
          f"  城镇态={res.town_mode}")
    print(f"角色: {hero.get('name')}  摘要等级={hero.get('summary_level')}  "
          f"槽位={hero.get('slot_index')}  profile={hero.get('profile')}")
    f = player['fields']
    print(f"player._level={player['level']}  BaseMaxHealth={f['BaseMaxHealth']}  "
          f"BaseDamage={f['BaseDamage']}  BaseMaxMana={f['BaseMaxMana']}")
    pstat = f['BasePrimaryStat']
    print(f"BasePrimaryStat={pstat if pstat is None else round(pstat, 2)}  "
          f"BaseCritChance={f['BaseCritChance']}  BaseLifeOnHit={f['BaseLifeOnHit']}  "
          f"CurrentXP={f['CurrentXP']}")
    print(f"[聚合字典 ×7]（Final 候选={player['final_dict']}；KV 全量，与 mem_probe 对拍）")
    for label in _OFF['player']['stat_dicts']:
        kv = player['stat_dicts'].get(label, {})
        tag = ' ← Final' if label == player['final_dict'] else ''
        print(f'  [{label}] {len(kv)} KV{tag}')
        for key in sorted(kv):
            print(f'    {key:>3} {STAT_NAMES.get(key, f"Stat{key}")} = {kv[key]}')
    if p['equipment'] is None:
        print('[装备] 未导入（α 模式：装备容器不可用）')
    else:
        print(f"[装备 {len(p['equipment'])} 槽]（β：逐件词条/强化）")
        for rec in p['equipment']:
            mods = rec.get('modifiers')
            gems = rec.get('socketed_gems') or []
            detail = (f"ilv={rec.get('item_level')} rarity={rec.get('rarity')} "
                      f"upg={rec.get('upgrade_level')} rune={rec.get('rune_level')} "
                      f"sock={rec.get('socket_count')} mods={len(mods) if mods is not None else '?'} "
                      f"gems={len(gems)}")
            print(f"  slot {rec['slot']:>2} {_SLOT_NAMES.get(rec['slot'], '?'):<8} "
                  f"uid={rec['uid']} name={rec['name']} {detail}")
            if mods:
                txt = '; '.join(f"[{m[0]}:{STAT_NAMES.get(m[0], '?')} t{m[1]} v{m[2]}]" for m in mods)
                print(f"      mods: {txt}")
            if gems:
                print(f"      gems: {', '.join(str(g) for g in gems)}")
    for label, cn in (('inventory', '背包'), ('storage', '仓库')):
        items = p[label]
        print(f'[{cn}] {len(items)} 件（UID 全量列表）')
        for it in items:
            print(f"  {it['uid']}  x{it['count']}  {it['name'] or '?'}")
    fp = meta['fingerprints']
    print(f"[指纹] dicts={fp['dicts']}  uids={fp['uids']}  （连跑两次应逐值相等）")
    note = ('结构/键域/值域/双读一致性全部通过' if double_read
            else '结构/键域/值域通过（--no-double-read 未启用双读）')
    print(f'[校验] PASS：{note}')
    for w in res.warnings:
        print(f'[告警] {w}')


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog='python -m deskrawl_gui.memdump',
                                 description='Deskrawl 联机角色内存快照（严格只读）')
    ap.add_argument('--json', action='store_true', help='输出机器可比的 JSON（供逐值对拍）')
    ap.add_argument('--no-double-read', action='store_true', help='跳过双读一致性校验（仅调试）')
    args = ap.parse_args(argv)
    try:
        res = import_snapshot(double_read=not args.no_double_read)
    except MemoryImportError as e:
        print(f'[失败] {e}', file=sys.stderr)
        return 2 if e.kind in ('env', 'version') else 3
    if args.json:
        print(json.dumps(res.payload, ensure_ascii=False, indent=1))
    else:
        _print_human(res, double_read=not args.no_double_read)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())