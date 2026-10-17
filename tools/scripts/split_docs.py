import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
# -*- coding: utf-8 -*-
"""将单一大文档按主题拆分为多篇，放入桌面新文件夹。"""
import os, re, io

SRC = GAME_SODOC
OUT = r'C:\Users\<user>\Desktop\Deskrawl-数值设计文档'

lines = open(SRC, encoding='utf-8').read().split('\n')


def find(pred, start=0):
    for i in range(start, len(lines)):
        if pred(lines[i]):
            return i
    raise SystemExit('not found')


def rng(a, b):
    """1-based inclusive line range -> text (stripped of leading/trailing blank)"""
    seg = lines[a - 1:b]
    while seg and not seg[0].strip():
        seg.pop(0)
    while seg and not seg[-1].strip():
        seg.pop()
    return '\n'.join(seg)


# 定位各章节起止（1-based）
L = {}
L['title_hdr'] = (1, 15)
L['toc'] = (16, 32)
L['s1'] = (33, 91)
L['s2'] = (92, 231)
L['s3'] = (232, 320)
L['s4'] = (321, 377)
L['s5'] = (378, 462)
L['s6'] = (463, 759)
L['s7'] = (760, 845)
L['s8'] = (846, 911)
L['s8a'] = (912, 1332)
L['s9'] = (1333, 1379)
L['s10'] = (1380, 1394)
L['appA'] = (1395, 1424)

# §8A 内部切分点：8A.6 标题行
i_8a6 = find(lambda l: l.startswith('### 8A.6'), L['s8a'][0] - 1) + 1
L['s8a_head'] = (L['s8a'][0], i_8a6 - 1)
L['s8a_body'] = (i_8a6, L['s8a'][1])

DOCS = [
    ('01-总体架构与SO清单.md', '总体架构与 SO 清单',
     '游戏数值分层架构、资产文件分布、146 个数值类实例规模，以及按域分组的 ScriptableObject 清单与功能说明。',
     ['s1', 's2']),
    ('02-属性系统与枚举.md', '属性系统与枚举字典',
     'StatType 全部 70 项属性（含分类/封顶/说明）、3 张硬编码属性分组表，以及 40+ 个枚举的完整取值。',
     ['s3', 's4']),
    ('03-核心数据结构.md', '核心数据结构',
     'StatModifier / LeveledStatModifier / LeveledFloat / TokenSpec / GemBonus / RuneAttribute 等最小数值单元，及 Obscured* 反作弊类型的内存布局。',
     ['s5']),
    ('04-伤害计算与属性关联.md', '伤害计算与属性关联',
     '属性三层聚合模型、伤害 13 步完整链路、bkn/bko/暴击/减伤/易伤各乘区公式，以及乘区拓扑图、属性依赖表与 SO 引用图。',
     ['s6', 's7']),
    ('05-配置字段说明.md', '配置字段说明（GameConfig）',
     'GameConfig 全字段 schema：全局引用、强化打孔、精英 Boss、成长曲线四组字段的类型与含义。',
     ['s8']),
    ('06-实测数值-全局与成长曲线.md', '实测数值：全局配置与成长曲线',
     '两套 GameConfig 对比、敌人成长分段、经验/技能/符文/Paragon/挂机曲线、强化成功率、精英与难度档位、Paragon 属性池。',
     ['s8a_head']),
    ('07-实测数值-内容数据.md', '实测数值：内容数据',
     '装备词条池与宝石孔位、掉落向量、药水档位、宝石、符文与套装、天赋、技能、地图与敌人的全部实测数值。',
     ['s8a_body']),
    ('08-常量设计要点与待办.md', '硬编码常量、设计要点与待办',
     '代码内硬编码常量（含 RVA/VA 地址）、10 条数值设计要点、未决问题清单与已解码数据文件索引。',
     ['s9', 's10', 'appA']),
]

os.makedirs(OUT, exist_ok=True)

NAV_HEAD = ('> 📚 **Deskrawl 数值设计文档** ｜ [返回索引](00-索引.md)\n')


def nav_footer(idx):
    prev_l = DOCS[idx - 1][0] if idx > 0 else None
    next_l = DOCS[idx + 1][0] if idx + 1 < len(DOCS) else None
    parts = ['[返回索引](00-索引.md)']
    if prev_l:
        parts.insert(0, f'← [{DOCS[idx-1][1]}]({prev_l})')
    if next_l:
        parts.append(f'[{DOCS[idx+1][1]}]({next_l}) →')
    return '---\n\n' + ' ｜ '.join(parts) + '\n'


written = []
for idx, (fname, title, desc, keys) in enumerate(DOCS):
    buf = io.StringIO()
    buf.write(f'# {title}\n\n')
    buf.write(NAV_HEAD)
    buf.write('\n> ' + desc + '\n\n---\n\n')
    for k in keys:
        buf.write(rng(*L[k]))
        buf.write('\n\n---\n\n')
    buf.write(nav_footer(idx))
    text = buf.getvalue().replace('\n\n\n\n', '\n\n')
    with open(os.path.join(OUT, fname), 'w', encoding='utf-8') as f:
        f.write(text)
    written.append((fname, text.count('\n') + 1, len(text)))

# ── 索引 ──
ibuf = io.StringIO()
ibuf.write('# Deskrawl 数值设计文档 · 索引\n\n')
ibuf.write(rng(*L['title_hdr']).split('\n', 1)[1].strip() + '\n\n')
ibuf.write('---\n\n## 文档导航\n\n')
ibuf.write('| # | 文档 | 内容摘要 | 行数 |\n|---|---|---|---|\n')
for i, (fname, title, desc, _) in enumerate(DOCS, 1):
    n = dict((w[0], w[1]) for w in written)[fname]
    ibuf.write(f'| {i:02d} | [{title}]({fname}) | {desc} | {n} |\n')

ibuf.write('\n---\n\n## 调研方法与置信度\n\n')
ibuf.write("""
本文档集是对游戏客户端 `Deskrawl`（Unity 6000.3.6f1 / IL2CPP / GUPS.Obfuscator 混淆）的
**只读静态逆向调研结果**，未修改任何游戏文件。

**证据来源**

| 类型 | 来源 |
|---|---|
| 指令级证据 | `GameAssembly.dll` 反汇编（capstone，逐条读取指令与浮点常量） |
| 符号与结构 | Il2CppDumper（v39 分支）还原的 `dump.cs`：类、字段、偏移、TypeDefIndex |
| 元数据 | `Deskrawl_Data/il2cpp_data/Metadata/global-metadata.dat`（metadata v39） |
| 实测数值 | 自建反序列化器导出的 **1333 条 SO 实例**（字节级精确，0 错误）→ `data/so_dump/*.json` |

**置信度标注**

- ✅ 指令级证据或字节级解码验证
- 🔶 基于代码结构与命名的高置信度推断
- ⚠️ 待确认项

> **阅读建议**：先看本篇索引 → 01（架构与 SO 清单）建立全局认知 → 04（伤害计算与属性关联）
> 理解数值骨架 → 06/07（实测数值）查具体配置。
""")

index_text = ibuf.getvalue()
with open(os.path.join(OUT, '00-索引.md'), 'w', encoding='utf-8') as f:
    f.write(index_text)

print('输出目录:', OUT)
total = 0
for fname, n, sz in written:
    total += n
    print(f'  {fname:<40} {n:>5} 行  {sz/1024:>6.1f} KB')
print(f'  00-索引.md{"":<31} {index_text.count(chr(10))+1:>5} 行  {len(index_text)/1024:>6.1f} KB')
print(f'合计 {len(written)+1} 个文件，正文 {total} 行')
print('原文:', len(lines), '行 -> 保留在游戏目录（未删除）')
