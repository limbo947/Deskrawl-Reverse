# Deskrawl 数值逆向 · 项目进度

> **一句话**：对单机/挂机暗黑类游戏 **Deskrawl: Idle ARPG**（Unity 6000.3.6f1 / IL2CPP / 混淆）做的
> **只读**数值逆向 —— 已还原完整伤害公式、全部静态数值数据、装备词条生成规则与存档加解密，
> 并据此做了一个「装备/技能/宝石 数值对比」计算内核（UI 待做）。
>
> **状态**：数据与公式层已完成，工具内核可运行；剩余 4 项零星待确认。
> **最近更新**：2026-10-07（回填 MythicBand2 实测值并销项）

---

## 1. 目录结构

```
Deskrawl-Reverse/
├─ README.md                  ← 本文（进度总览）
├─ docs/                      ← 数值设计文档集（10 篇 Markdown）
│   ├─ 00-索引.md             ← 从这里开始读
│   ├─ 01-总体架构与SO清单.md
│   ├─ 02-属性系统与枚举.md
│   ├─ 03-核心数据结构.md
│   ├─ 04-伤害计算与属性关联.md      ← 核心：公式
│   ├─ 05-配置字段说明.md
│   ├─ 06-实测数值-全局与成长曲线.md
│   ├─ 07-实测数值-内容数据.md
│   ├─ 08-常量设计要点与待办.md      ← 常量/待办/§11 补充结论
│   └─ 09-存档解密与数据汇总报表.md   ← 存档解密 + 数据报表 + 存档结构
├─ tools/
│   ├─ deskrawl_calc/         ← ★ 计算内核（Python 包：公式 + 数据层）
│   │   ├─ stattype.py        StatType 枚举与分组表
│   │   ├─ engine.py          三层聚合 + 13 步伤害链路 + 装备对比
│   │   ├─ gamedata.py        数据层（自动装配宝石/符文/天赋/特效/词条 Roll）
│   │   └─ cli.py             自检 + 换武器对比示例
│   ├─ scripts/               ← 逆向脚本（65 个 .py + paths.py + assets_cache.json）
│   │   ├─ paths.py                 统一路径解析（仓库可任意移动）
│   │   ├─ schema.py / decode.py    Unity 二进制反序列化器（依 dump.cs 重建 schema）
│   │   ├─ dump_all2.py / dump_effects.py  SO 与特效批量导出
│   │   ├─ decrypt_save.py / read_save.py  存档解密与解析
│   │   ├─ disasm.py / disasm2.py / xref.py  反汇编与交叉引用
│   │   └─ extract_rolltable.py     词条系数表提取
│   └─ thirdparty/            ← 第三方工具（重新生成 schema 用）
│       ├─ Il2CppDumper/ · Il2CppDumper-v39/ · Il2CppDumper.zip · ttg/
└─ data/
    ├─ so_dump/               ← ★ 25 个 JSON（全部静态数值实测数据）
    ├─ save_decrypted.json    已解密的存档（本机账号）
    └─ schema/                dump.cs / script.json / stringliteral.json（IL2CPP 还原产物）
```

---

## 2. 快速开始

```powershell
cd D:\workspace\Deskrawl-Reverse\tools
python -m deskrawl_calc.cli            # 运行 8 项公式自检 + 换武器对比示例
python -m deskrawl_calc.cli selftest   # 只跑自检（CI 友好，非 0 退出码表示失败）
```

作为库使用：

```python
from deskrawl_calc import GameData, StatSheet, Modifier, Weapon, Target, compare_weapons, StatType

gd = GameData()                                    # 自动定位 ..\..\data\so_dump
sheet = StatSheet()
sheet.add_mods(gd.gem_modifiers('GemAmethyst3', equip_category=2))   # 宝石
sheet.add_mods(gd.rune_modifiers('HunterSetRune1_4', rune_level=3))  # 符文
sheet.add_mods(gd.talent_modifiers('HunterTalent19', points=5))      # 天赋
sheet.add_mods(gd.equipment_effect_modifiers(4796))                  # 传奇特效（by pathID）
sheet.add_mods(gd.paragon_modifiers({4: 50}))                        # 巅峰

print(gd.ability_attack_scaling('FireElementalMeteor', 10))          # 技能倍率
print(gd.affix_range(4, 70, 3))                                      # 暴击率 Lv70 传奇 的 Roll 区间

r = compare_weapons(sheet, old_weapon, new_weapon,
                    target=Target(level=70, elite=True, vulnerable=True))
print(f'{r["delta_pct"]:+.2f}%')
```

> 依赖：Python 3.10+；存档解密额外需要 `cryptography` 或 `pycryptodome`。
> 逆向脚本（`tools/scripts/`）额外需要 `UnityPy`、`capstone`。

---

## 3. 已完成成果

### 3.1 数值公式（✅ 指令级证据）

```
Final(stat) = (Base + ΣFlat) × (1 + ΣPercentAdd) × Π(1 + PercentMult)      ← 三层聚合

伤害 = 攻强 × [1 + 元素% + 全伤害%]        ← 乘区A（同池加算）
            × (1 + 暴伤)                  ← 乘区B（暴击时，独立）
            × (1 + Σ10项条件伤害)          ← 乘区C（同池加算）
            × 1.3 × Random(0.9,1.1)        ← 易伤固定 + 命中浮动（均独立）
            × Π(1 − 护甲曲线/元素减伤/全局减伤)  ← 减伤层（乘法）
```

- **同池加算陷阱**：`物理伤害%` 与 `全伤害加成%` 是**同一个池**；条件伤害 10 项同池。
- **真正独立的乘区只有 4 个**：暴击、条件伤害池、易伤 1.3、命中浮动。
- 封顶：暴击率 / 闪避 / 冷却缩减 / 法力消耗缩减 均 `≤ 0.85`。

### 3.2 静态数据（✅ 字节级解码，0 错误）

| 内容 | 规模 | 文件 |
|---|---|---|
| ScriptableObject 实例（21 类） | **1333 条** | `data/so_dump/*.json` |
| 技能效果（`DamageEffect` 等） | 124 / 124 | `AbilityData.json` 的 `_managedRefs` |
| 状态行为 | 88 / 95 | `StatusEffectData.json` |
| 装备传奇特效 | 92 | `EquipmentEffects.json` |
| 天赋特效 / 生活技能特效 | 157 / 36 | `TalentEffects.json` / `LifeSkillEffects.json` |
| 词条每级系数表 | 55 项 | `AffixRollTable.json` |

### 3.3 关键突破

| 突破 | 说明 |
|---|---|
| **技能伤害倍率** | `DamageEffect.AttackScaling`：`Base + (lv−1)×PerLevel`（例：陨石 `4.2196 + 0.06115×(lv−1)`） |
| **装备词条 Roll** | `值 = (1+稀有度系数) × 等级 × 每级系数[属性] × Random(0.85,1.15)`；稀有度系数 `+.2/.4/.5/.6` |
| **`[SerializeReference]` 载荷** | 布局：主数据流只存 `count + 8B 键`；真实对象在**字段区之后**的托管引用段（类型名**明文**） |
| **传奇特效** | `EquipmentEffect_*` 是独立 SO 资产，按 `m_Script` 反查类名后可直接解码 |
| **存档 `DDS2`** | `AES-256-CBC + HMAC-SHA256`，密钥 `SHA256("desktop-diablo-save-v1-CHANGE-ME")`；已解密并校验 MAC |

> 详细证据与 RVA 地址见 `docs/08-常量设计要点与待办.md` §11 与 `docs/04`。

### 3.4 工具内核

`tools/deskrawl_calc/`：`cli.py` 的 **8 项自检全部通过**（三层聚合 / 乘区 A / 暴伤 / 封顶 / 护甲曲线 /
条件池 / 易伤 1.3），并附带「换武器 → DPS 增减」示例。

---

## 4. 数据来源与置信度

| 类型 | 来源 |
|---|---|
| 指令级证据 | `GameAssembly.dll` 反汇编（capstone） |
| 符号与结构 | Il2CppDumper(v39) 还原的 `data/schema/dump.cs` |
| 元数据 | `Deskrawl_Data/il2cpp_data/Metadata/global-metadata.dat`（metadata v39） |
| 实测数值 | 自建反序列化器导出的 **1333 条 SO 实例** |

标注约定：`✅` 有指令级/字节级证据 · `🔶` 高置信推断 · `⚠️` 待确认。

---

## 5. 未完成 / 已知缺口

| 项 | 状态 | 说明 |
|---|---|---|
| `bkl` / `bgm` 等虚接口实现 | ⚠️ | 基类默认返回 0，实际由敌人/玩家子类覆写 |
| `ItemizationConfig` 三张属性表的逐项值 | 🔶 | 长度与成员已交叉验证，`.rdata` 源表未逐项读取 |
| `MythicBand2*` 分段阈值 | ✅ 已销项 | `MythicDungeon` 全字段已补读并归档（07 篇 §8A.13）：`Band1EndTier=50`、HP 倍率 1.16/1.17、DMG 倍率 1.03/1.025、Gold/Exp 每 tier +0.02/+0.015 |
| `AbilityData.te()` 中「倍率 × 攻强」合成顺序 | 🔶 | 待逐指令复核 |
| 7 条 `StatusEffectData` 托管段 | ⚠️ | 多出 8 字节，个别行为类型未对齐 |
| **角色运行时数据** | ⬜ | 联机模式角色数据**不在本地**（服务器托管）；仅本地(Local)模式存档含完整角色数据 |
| 工具 UI | ⬜ | 已定方案：桌面 GUI，UI 后置 |

---

## 6. 路径与自包含性

`tools/scripts/paths.py` 统一解析所有路径，**整个仓库可任意移动**：

| 符号 | 指向 |
|---|---|
| `REPO` / `DATA` / `DOCS` | 仓库根 / `data` / `docs` |
| `SO_DUMP` / `SCHEMA` | `data\so_dump` / `data\schema` |
| `DUMP_CS` / `SCRIPT_JSON` / `STRINGLITERAL_JSON` | `data\schema\` 下的三个文件 |
| `ASSETS_CACHE` / `REPORT_DATA` / `SO_SCHEMA_MD` | `tools\scripts\` 下的中间产物 |
| `GAME_DIR` / `GAME_ASSEMBLY` / `GAME_DATA` / `GAME_SAVE` / `GAME_METADATA` | 游戏安装目录（**只读**） |

- 换机器/换盘只需设环境变量 `DESKRAWL_GAME`（默认 `d:\steam\steamapps\common\Deskrawl`）。
- **65 个脚本已全部改为从 `paths` 取路径**，无写死绝对路径；已验证可独立运行
  （`schema` 加载、`find_method`、`verify2`、`extract_rolltable`、`decrypt_save`、`read_save`）。
- 唯一外部依赖：**游戏本体**（反汇编/资产解析需要 `GameAssembly.dll` 与 `Deskrawl_Data`）。

**重新生成 `data/schema/`**：用 Il2CppDumper 对 `GameAssembly.dll` + `global-metadata.dat` 重新导出即可
（只需要其中的 `dump.cs` / `script.json` / `stringliteral.json` 三个文件）。

---

## 7. 建议的下一步

1. **补完最后 4 项**（`bkl/bgm`、`ItemizationConfig` 三表、`te()` 合成顺序、7 条状态行为）→ 文档中 `⚠️/🔶` 清零。
2. **桌面 GUI**：把 `deskrawl_calc` 接到界面（角色面板输入 + 新旧装备对比 + 宝石/技能候选排序）。
3. **角色数据接入**（三选一）：本地模式存档解析 / 运行时读内存（可读联机角色）/ 手动输入面板。
