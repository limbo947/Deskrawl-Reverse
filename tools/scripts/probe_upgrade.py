# -*- coding: utf-8 -*-
"""③-9 探针：定位「强化配方选择」的调用点。

为什么用探针而不是直接翻 dump.cs：强化链的方法名被混淆（`ccw`/`gcv`），
但类名与签名保留，靠 dump_index 按「类 + 归一化签名」定位比肉眼 grep 62 MB 可靠；
地址一律现查现用（不写死），因此不产生需要 RVA 体检登记的字面量。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import SO_DUMP          # noqa: E402
import dump_index as di            # noqa: E402


def main():
    idx = di.DumpIndex.load(os.path.join(os.path.dirname(__file__), '..', '..',
                                        'data', 'schema', 'dump.cs'))
    print('=== GameConfig 强化/配方相关字段 ===')
    for f, o in sorted(idx.fields.get('GameConfig', {}).items(), key=lambda z: z[1]):
        if any(s in f for s in ('Recipe', 'Upgrade', 'Success')):
            print(f'  0x{o:02X} {f}')

    print('=== GameConfig 强化相关方法 ===')
    for m in idx.by_klass.get('GameConfig', []):
        if any(s in m.sig for s in ('RecipeData', 'Recipe', 'Upgrade')):
            print(f'  rva=0x{m.rva:X} {m.name} {m.sig}')

    print('=== UpgradePanelUI 方法 ===')
    for m in idx.by_klass.get('UpgradePanelUI', []):
        print(f'  rva=0x{m.rva:X} slot={m.slot} {m.name} {m.sig}')

    print('=== RecipeData 实例（so_dump） ===')
    with open(os.path.join(SO_DUMP, 'RecipeData.json'), encoding='utf-8') as fh:
        for r in json.load(fh):
            ing = [(i.get('Item', {}).get('pathID'), i.get('Amount'))
                   for i in (r.get('Ingredients') or []) if isinstance(i.get('Item'), dict)]
            print(f"  {r['_name']:26s} pathID={r['_pathid']} gold={r.get('GoldCost')} "
                  f"out={r.get('OutputQuantity')} ing={ing}")


if __name__ == '__main__':
    main()
