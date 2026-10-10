# -*- coding: utf-8 -*-
"""③-17 探针：Back 9 件装备的战力来源到底在哪。

旧结论「固定属性/特效传奇」已被 ③-10 否证（ItemData 无数值载荷、EquipmentEffects 不关联）。
本探针做剩下两件事：① ItemData 的字段清单里是否有 Back 专属字段（外观槽假设的直接证据）；
② 全量 so_dump 里**有没有任何资产引用这 9 件的 pathID**（若零引用且自身无载荷，
则「纯外观、零战力」就是数据侧的定论，不必再猜外部关联键）。
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import SO_DUMP          # noqa: E402
import dump_index as di            # noqa: E402


def main():
    with open(os.path.join(SO_DUMP, 'ItemData.json'), encoding='utf-8') as fh:
        items = json.load(fh)
    backs = [r for r in items if r.get('EquipSlot') == 11]
    print(f'=== Back 装备 {len(backs)} 件：全部非零/非空字段 ===')
    for r in backs:
        payload = {k: v for k, v in r.items()
                   if k not in ('_name', '_pathid', '_file', '_managedRefs')
                   and v not in (None, 0, 0.0, '', [], False)}
        print(f"  {r['_name']:32s} pathID={r['_pathid']} -> {payload}")

    print('\n=== ItemData 字段清单（dump.cs）===')
    idx = di.DumpIndex.load(os.path.join(os.path.dirname(__file__), '..', '..',
                                        'data', 'schema', 'dump.cs'))
    for f, o in sorted(idx.fields.get('ItemData', {}).items(), key=lambda z: z[1]):
        print(f"  0x{o:03X} {f}{'   <-- Back 专属' if 'Back' in f else ''}")

    print('\n=== 全量 so_dump 交叉引用这 9 件的 pathID ===')
    pids = {r['_pathid'] for r in backs}
    names = {r['_name'] for r in backs}
    hits = 0
    for path in sorted(glob.glob(os.path.join(SO_DUMP, '*.json'))):
        base = os.path.basename(path)
        if base == 'ItemData.json':
            continue
        with open(path, encoding='utf-8') as fh:
            txt = fh.read()
        for pid in sorted(pids):
            # "pathID": N 的引用形态与导出器一致；按词边界匹配避免 6038 命中 60388
            if f'"{pid}"' in txt or f': {pid},' in txt or f': {pid}}}' in txt:
                print(f'  {base}: 引用 pathID {pid}')
                hits += 1
        for nm in names:
            if nm in txt:
                print(f'  {base}: 提及名字 {nm}')
                hits += 1
    if not hits:
        print('  （零引用——没有任何资产按 pathID 或名字关联 Back 件）')


if __name__ == '__main__':
    main()
