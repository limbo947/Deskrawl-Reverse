# -*- coding: utf-8 -*-
"""统一路径解析。所有逆向脚本从这里取路径，整个 `scripts/` 目录可随仓库任意移动。

仓库结构约定：
    <repo>/docs            文档
    <repo>/tools/scripts   本目录
    <repo>/data/so_dump    导出的 SO JSON
    <repo>/data/schema     dump.cs / script.json / stringliteral.json

游戏安装目录可用环境变量 `DESKRAWL_GAME` 覆盖（默认按本机 Steam 路径）。
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))          # <repo>/tools/scripts
TOOLS = os.path.dirname(HERE)                              # <repo>/tools
REPO = os.path.dirname(TOOLS)                              # <repo>
DATA = os.path.join(REPO, 'data')
DOCS = os.path.join(REPO, 'docs')
SO_DUMP = os.path.join(DATA, 'so_dump')
SCHEMA = os.path.join(DATA, 'schema')
DUMP_CS = os.path.join(SCHEMA, 'dump.cs')
SCRIPT_JSON = os.path.join(SCHEMA, 'script.json')
STRINGLITERAL_JSON = os.path.join(SCHEMA, 'stringliteral.json')

ASSETS_CACHE = os.path.join(HERE, 'assets_cache.json')
REPORT_DATA = os.path.join(HERE, 'report_data.md')
SO_SCHEMA_MD = os.path.join(HERE, 'so_schema.md')
SAVE_DECRYPTED = os.path.join(DATA, 'save_decrypted.json')

# ---- 游戏安装目录（只读；若换机器/换盘，设 DESKRAWL_GAME 即可） ----
GAME_DIR = os.environ.get('DESKRAWL_GAME', r'd:\steam\steamapps\common\Deskrawl')
GAME_ASSEMBLY = os.path.join(GAME_DIR, 'GameAssembly.dll')
GAME_DATA = os.path.join(GAME_DIR, 'Deskrawl_Data')
GAME_SAVE = os.path.join(GAME_DIR, 'Data', 'save.json')
GAME_METADATA = os.path.join(GAME_DATA, 'il2cpp_data', 'Metadata', 'global-metadata.dat')
GAME_SODOC = os.path.join(GAME_DIR, 'Deskrawl_ScriptableObject_数值设计文档.md')

# 输出目录（若不存在则创建）
def ensure(p):
    os.makedirs(p, exist_ok=True)
    return p
