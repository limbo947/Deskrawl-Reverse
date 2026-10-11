# -*- coding: utf-8 -*-
"""从游戏资产导出 Unity Localization 的 CSV 本地化表 → data/loc/*.json（简中）。

背景：技能/物品等显示名不在 dump.cs/so_dump 里，而在 resources.assets 的 TextAsset
（Unity Localization 表，Key=AbilityData._name 等，多语言列）。GUI 只需简中一列，
导出成扁平 JSON 供 `deskrawl_gui.core.localization` 懒加载。

用法：python extract_localization.py                # 默认导出 Abilities
      python extract_localization.py Items UI       # 指定表名（TextAsset 名）

只读游戏文件；输出写到 <repo>/data/loc/<table小写>_zh.json。
"""
import csv
import io
import json
import os
import sys

import UnityPy

from paths import GAME_DIR, REPO

DATA_DIR = os.path.join(GAME_DIR, 'Deskrawl_Data')
OUT_DIR = os.path.join(REPO, 'data', 'loc')
SOURCE_ASSETS = ('resources.assets', 'globalgamemanagers.assets', 'sharedassets0.assets')


def find_text_asset(table: str) -> str:
    """在游戏资产里找名为 table 的 TextAsset，返回其 CSV 文本。"""
    for fname in SOURCE_ASSETS:
        env = UnityPy.load(os.path.join(DATA_DIR, fname))
        for obj in env.objects:
            if obj.type.name != 'TextAsset':
                continue
            data = obj.read()
            if getattr(data, 'm_Name', '') != table:
                continue
            script = data.m_Script
            if isinstance(script, bytes):
                script = script.decode('utf-8-sig', errors='replace')
            return script
    raise SystemExit(f'未找到 TextAsset「{table}」：确认表名与游戏文件存在')


def extract(table: str) -> dict:
    """解析 CSV → {Key: 简中}。简中缺失/重复时保留英文（回落显示，宁缺勿空）。

    表头去 BOM：部分 TextAsset（如 Equipments）的 m_Script 已是 str（未走 decode 分支），
    UTF-8 BOM 会附在首个列名上，不清掉则 DictReader 找不到 'Key' 列直接抛错。
    """
    text = find_text_asset(table).lstrip('\ufeff')
    rows = csv.DictReader(io.StringIO(text))
    out = {}
    for r in rows:
        zh = (r.get('Chinese (Simplified)') or '').strip()
        out[r['Key'].strip()] = zh or r['English'].strip()
    return out


def main(tables):
    os.makedirs(OUT_DIR, exist_ok=True)
    for table in tables:
        mapping = extract(table)
        path = os.path.join(OUT_DIR, f'{table.lower()}_zh.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, ensure_ascii=False, indent=1, sort_keys=True)
        print(f'{table}: {len(mapping)} 条 → {path}')


if __name__ == '__main__':
    main(sys.argv[1:] or ['Abilities'])
