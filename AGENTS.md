
## 项目性质

对单机挂机 ARPG **Deskrawl**（Unity 6000.3.6f1 / IL2CPP / GUPS.Obfuscator 混淆）的**只读**数值逆向仓库。已还原完整伤害公式、1333 条静态数值（SO 实例）、装备词条生成规则与存档加解密，并产出两个可运行工具：数值计算内核 `deskrawl_calc` 与桌面 GUI `deskrawl_gui`。逆向工作已闭环，当前主要开发方向是 GUI 与角色数据接入。**任何情况下不得修改游戏安装目录内的文件**。

补丁后的地址重锚定已流程化（2026-10-10）：一条命令体检全仓地址（`tools/scripts/rva_audit.py`）、一张语义别名表隔离每版都变的混淆名（`data/schema/aliases.json`）、一份五步回归清单（`docs/plan/补丁回归清单.md`）+ 串行入口 `patch_regression.py`。游戏一更新，照清单走即可。

环境：Windows 10，PowerShell（pwsh 优先）。Python 3.10+。无 lint/构建配置，纯 Python 仓库。

## 常用命令

### 计算内核（无第三方依赖，系统 Python 即可）

```powershell
cd D:\workspace\Deskrawl-Reverse\tools
python -m deskrawl_calc.cli selftest   # 10 项公式断言自检；CI 友好，非 0 退出码=失败
python -m deskrawl_calc.cli            # 自检 + 「换武器 DPS 对比」示例
```

没有 pytest 等测试框架——`selftest` 就是全部自动化测试，且为单一整体，无法只跑其中一项；修改 `engine.py`/`gamedata.py` 后必须运行它。

### 桌面 GUI（独立 venv，只依赖 PySide6 + deskrawl_calc）

```powershell
cd D:\workspace\Deskrawl-Reverse
python -m venv .venv-gui
.\.venv-gui\Scripts\python.exe -m pip install -r requirements-gui.txt
cd tools
..\.venv-gui\Scripts\python.exe -m deskrawl_gui              # 启动主窗口
..\.venv-gui\Scripts\python.exe -m deskrawl_gui --selftest   # 内核 10 项 + GUI 服务层/面板锚点对拍，共 32 项
..\.venv-gui\Scripts\python.exe -m deskrawl_gui --smoke      # 无显示环境骨架冒烟（建窗口即退）
```

根目录 `启动GUI.bat` 双击可用：首跑自动建 venv 装依赖，参数透传（如 `启动GUI.bat --selftest`）。`--selftest` 不建 QApplication，headless 可跑；其 DPS 锚点（`selftest.py` 的 `ANCHORS`）与内核一起冻结，改动公式需同步更新锚点。

### 内存快照 CLI（需游戏运行中，64 位 Python，可能需管理员权限）

```powershell
cd D:\workspace\Deskrawl-Reverse\tools
..\.venv-gui\Scripts\python.exe -m deskrawl_gui.memdump            # 人类可读输出
..\.venv-gui\Scripts\python.exe -m deskrawl_gui.memdump --json     # 结构化快照
```

退出码：0 成功 / 2 环境错误 / 3 数据校验失败。默认双读一致性校验，`--no-double-read` 可关（仅诊断用）。

### 地址体检与语义别名（补丁后必跑；系统 Python 即可，无第三方依赖）

```powershell
cd d:\workspace\Deskrawl-Reverse\tools\scripts
python rva_audit.py --check --falsify     # 全仓地址体检：退出码 0 = 无失效/待确认；--falsify 是自证用例
python rva_audit.py --docs                # 额外扫 docs/**/*.md（文档侧重锚定工单）
python build_aliases.py --check           # 语义别名表校验（真读当期 dump.cs 比对签名+Slot）
python build_aliases.py --write           # 补丁后刷新 current，旧值压入 history
python patch_regression.py --live         # 指纹 → 体检 → 别名 → 自检 →（游戏运行中）实机
```

- `rva_audit.py` **只报告、不写回**（地址自动写错会污染全仓）；写回由人工复核后单独提交。
- 判定链：白名单/自动非地址规则 → 当期 `dump.cs` 方法起始 → 旧构建同名方法（签名+Slot → **类形状自证** → 跨类唯一）→ 嵌套类 → `docs/08 §12.2` 常量表字节校验 → 旧 `script.json` 字面量对搬 → 内联数据 → 人工确认。**同名类不算证据**：混淆类名每版重生成，实测新构建有同名 `iw` 但签名交集 0/5，真身是 `je`（`gg`→`gh`、`gi`→`gj` 同理）。
- 报告落 `docs/reports/RVA体检报告.md`（+ `-文档.md`），机读结果落 `data/schema/rva_audit*.json`；`rva_verify.py` 是复核与渲染段（从 `rva_audit.py` 拆出）。
- 文件分区（`rva_audit_config.json`）：`literal`/`data_refs` 每条必须写明理由；弃用探针的理由**必须真的写在文档里**（脚本会打开文档校验标记），文档侧历史证词用 `doc_policy` 或文档内 `<!-- rva-audit:historical 理由 -->` 标记——都不许用来「消灭红点」。
- **写地址的习惯**：注释与文档引用**语义名**（`aliases.json` 的键）而非当期混淆名；紧邻「旧/补丁前」标注的地址是刻意保留的对照，不要「顺手修正」。

### 逆向脚本（tools/scripts/，重依赖，仅重建数据时需要）

依赖 `UnityPy`、`capstone`；存档解密另需 `cryptography` 或 `pycryptodome`（两者任一，`decrypt_save.py` 自动回落）。游戏目录由环境变量 `DESKRAWL_GAME` 定位（默认 `d:\steam\steamapps\common\Deskrawl`），换机器只需设它。所有脚本从 `paths.py` 取路径，仓库可整体移动。典型用法：`python decrypt_save.py`（解密存档→`data/save_decrypted.json`）、`python read_save.py`、`python dump_all2.py`（重导 SO）。重新生成 `data/schema/`：用 `tools/thirdparty/Il2CppDumper` 对 `GameAssembly.dll` + `global-metadata.dat` 导出，只保留 `dump.cs`/`script.json`/`stringliteral.json` 三个文件。

## 高层架构

### 三层单向依赖：内核 → GUI →（断）→ 逆向脚本

```
tools/deskrawl_calc/   纯 Python 计算内核（零依赖，可独立作库）
tools/deskrawl_gui/    PySide6 桌面 UI（只 import deskrawl_calc）
tools/scripts/         逆向脚本（UnityPy/capstone，面向游戏文件）
```

**硬约束：GUI 包不得 import `tools/scripts`**（包括内存导入链也刻意自包含，只用 stdlib）。`core/memory_reader.py` 与 `scripts/mem_probe.py` 是「算法同源、代码独立」的两份实现，允许约百行重复——诊断脚本宽容带打印，导入通道严格抛错。改其中一份时另一份不自动同步。

### deskrawl_calc：公式 + 数据两层

- `stattype.py`：`StatType` IntEnum（70 项属性）+ 分组表 `CORE`/`ALL_ELEMENTS`/`CONDITIONAL_DAMAGE`。**枚举值是稀疏 ID，游戏存档/配置按 ID 引用，禁止重排或改值**；三张分组表来自 `ItemizationConfig` 元数据（SHA-256 自校验过的硬结论），不是推断。
- `engine.py`：公式实现，模块 docstring 把每条公式映射到 `docs/04` 的章节号（✅=指令级证据，🔶=推断且已做成可覆盖参数）。核心模型：
  - 三层聚合 `Final = (Base + ΣFlat) × (1 + ΣPercentAdd) × Π(1 + PercentMult)`（`StatSheet` 持有 base/flat/add/mult 四个字典）。
  - 伤害乘区：乘区 A（元素% 与全伤害% **同池加算**）× 乘区 B（暴伤，独立）× 乘区 C（10 项条件伤害同池）× 易伤 1.3 × 命中浮动 × 减伤层（护甲曲线 `resist/(resist+50×max(1,level))` 等，乘法）。暴击率/闪避/CDR/蓝耗缩减封顶 0.85。真正独立的乘区只有 4 个。
  - `unwrap()` 兼容 dump 里的 `Obscured*`（`{'value': x}`）与 `LeveledFloat`（`{Base, PerLevel}`，公式 `Base + (level-1)×PerLevel`）嵌套结构——处理 so_dump 数据时必须经过它，不能直接当 float 用。
- `gamedata.py`：`GameData` 加载 `data/so_dump/*.json`（懒加载+缓存，按 `_name` 索引），产出可直接入 `StatSheet` 的 `Modifier`：宝石（按镶嵌部位 0/1/2 区分加成组）、符文、天赋、传奇特效（by pathID）、巅峰、技能倍率、词条 Roll 区间。数据目录自动定位 `../../data/so_dump`，回落到旧绝对路径。
- `cli.py`：10 项 selftest 断言的数值都取自 docs/04 的可对照证据，是「公式实现 == 逆向证据」的回归网。

### deskrawl_gui：profile 为唯一事实源，服务层纯函数

- `core/profile.py`：`CharacterProfile`（可 JSON 序列化，存 `data/builds/*.json`）是面板编辑、构建存取、计算的唯一事实源。装配顺序与 `cli.demo()` 刻意保持一致，使 GUI 复算能与内核直算对拍。装备槽→宝石部位的映射（`_GEM_CATEGORY_BY_EQUIP_TYPE`）是内存面板实测锚定的，勿按直觉改。
- `core/calc_service.py`：全部纯函数（输入 profile/GameData，输出视图 dataclass），widget 不做计算。将来要把排序挪线程只改这一个文件。
- `app.py`：只做主窗口装配（左 dock 面板 / 中央三 Tab / 右 dock 目标+属性明细）与信号中转；编辑逻辑下沉 `widgets/`。导入错误统一走 `MemoryImportError.code` → 中文文案映射（`_IMPORT_ERROR_TEXTS`），新错误态应加 code 而非拼消息子串。
- `__main__.py` 三模式互斥：`--selftest`（纯数值，不建 QApplication）、`--smoke`（建窗即退）、默认 GUI。

### 内存导入链（GUI 内，联机角色只读导入）

`memory_reader.py`（WinAPI 基元）→ `memory_import.py`（定位+快照+校验）→ `memory_snapshot.py`（偏移表/指纹/版本校验），偏移集中在 `core/memory_offsets.json`。

- **只读硬约束（验收条款）**：只允许 `OpenProcess(0x0410)` + `ReadProcessMemory`；禁止 WriteProcessMemory/CreateRemoteThread/SuspendThread/DLL 注入，整条导入链任何时候不得出现写操作。
- **校验哲学「宁可红不出脏」**：结构/键域/值域/双读一致性任一失败即抛错，绝不返回可疑数据；定位链全部以类名自校验收尾。
- 游戏更新后只需改 `memory_offsets.json`；版本指纹（`check_fingerprints`）同时校验偏移与 so_dump 静态数据，失配即拒绝导入。
- α/β 是能力降级而非开关：装备容器不可用时自动降级 α（聚合字典）并给 warnings，β 提供逐件词条。
- 背景：联机角色数据在服务器不在本地，所以走运行时读内存；本地模式存档才有完整角色数据（`read_save.py` 可解析）。

### tools/scripts：逆向脚本与地址工具链（75 个 .py）

公共基座：`paths.py`（统一路径，所有脚本 `from paths import *`）、`schema.py`（从 `data/schema/dump.cs` 用正则重建 Unity 序列化 schema：字段、偏移、继承）、`decode.py`（schema 驱动的 Unity 二进制反序列化器，含 ACTk `Obscured*` 序列化尺寸与 `[SerializeReference]` 托管引用段布局——主数据流只存 count+8B 键，真实对象在字段区之后的托管段）。其上：`dump_all2.py`/`dump_effects.py`（批量导出 SO/特效→`data/so_dump/`）、`decrypt_save.py`/`read_save.py`（DDS2 存档 AES-256-CBC + HMAC-SHA256，密钥 `SHA256("desktop-diablo-save-v1-CHANGE-ME")`）、`disasm.py`/`disasm2.py`/`xref.py`（capstone 反汇编 `GameAssembly.dll`，VA 基址 0x180000000，RVA↔文件偏移换算）、`extract_rolltable.py`（词条系数表）。

**地址工具链的四个基座**（被 `rva_audit.py`/`build_aliases.py` 复用，改一处两边都受益）：`dump_index.py`（`dump.cs` 方法与字段索引 + **归一化签名**——抹掉混淆名只留类型/参数/返回类型，以及类形状指纹）、`pe_file.py`（PE 只读：节表、VA↔偏移、位模式搜索，用来做常量字节校验）、`script_index.py`（`script.json` 流式索引，「地址↔语义」双向表，用于字面量/元数据对搬）、`rva_verify.py`（体检的证据复核与报告渲染段）。`rea_broker.mjs` 是绕开工具超时的常驻 REA 通道（**开工期间不要重启**，Ghidra 的 81 分钟分析会重来），调用前端是 `rea_call.py`（`python rea_call.py <tool> k=v …`，写 `%TEMP%\rea-broker\request.json` 轮询 `response.json`）——**REA 入参必须用 VA**（0x180000000+RVA，传 RVA 报 "No procedure exists"），且参数用 `k=v` 而非 JSON（PowerShell 转义会剥引号）。

其余多为一次性探针（probe/scan/exp_*），新探针仿照现有写法即可，不必追求复用它们——其中 6 个已在 `docs/plan/补丁回归清单.md` 登记为**弃用探针**（不随补丁重锚定，理由必须写在文档里，否则体检判红）。

> ⚠️ **重导 so_dump 前先重建资产缓存**：`dump_all2.py` 依赖 `tools/scripts/assets_cache.json`，该缓存偏旧时
> 只会认到 251/338 件物品——直接重跑会把 `data/so_dump/` 覆盖成更小的数据集（2026-10-10 实测后已回滚）。
> 重导流程：重建缓存 → 跑 `dump_all2.py` → `git diff --numstat data/so_dump/` 逐文件核对，只许看到数值行变化。

### data/ 与 docs/

- `data/so_dump/`：25 个 JSON、1333 条 SO 实例（字节级精确，0 残留），是全部静态数值的事实源。JSON 里 `_name`/`_pathID`/`_managedRefs` 是导出器附加的元字段。
- `data/schema/`：Il2CppDumper(v39) 产物 `dump.cs`/`script.json`/`stringliteral.json`，是 schema.py 与反汇编符号的输入；外加 `aliases.json`（**语义别名表**，37 条：伤害链/面板口径/ACTk 解码器/存档加解密链/Roll 表）与 `rva_audit*.json`（体检机读结果）。
- 注意存在**两套同名 GameConfig**：`MaxPlayerLevel` 35（Beta，resources.assets）与 70（正式，sharedassets0.assets），查配置时先确认哪套（`dump.cs` 里只有一个 `GameConfig` 类）。
- `docs/00-索引.md` 是文档入口（含分类地图与按需阅读路径）；docs/01–05 是**机制与结构篇**（架构/属性/数据结构/公式/配置字段）、06–09 是**实测与工具篇**（成长曲线/内容数值/常量与地址/存档），编号即阅读顺序；docs/08 §11 存硬结论、§12 存补丁后重锚定结果；docs/plan/ 存**现行**计划/清单/进度档，已完结的历史证词移入 `docs/plan/archive/`（**地址不随补丁回改**）；docs/reports/ 存**脚本产出的报告**（勿手改，重跑命令见 `docs/plan/补丁回归清单.md`）。文档置信度标注：✅ 指令/字节级证据、🔶 高置信推断（**当前正文已无在用条目**）、⚠️ 待确认（「暂缓」条目必须写明复核条件）——引用数值时沿用此标注，不要把 🔶 或暂缓写成定论。

### 编码约定

- 函数级注释解释「为什么」（动机与权衡），不复述「做什么」，1–3 行。
- 单文件有效代码（不含空行/注释）≤800 行；已超限文件只降不升（修改前先实测行数作基准）。接近上限时拆文件——`memory_snapshot.py` 就是从 `memory_import.py` 拆出的范例，拆分理由写在被拆文件 docstring 里。
- 新功能优先复用现有模块（引擎的 `unwrap`/`leveled_value`、GUI 的 `calc_service` 纯函数、脚本的 `paths`/`schema`/`decode`/`dump_index`/`pe_file`/`script_index` 基座）。
- 涉及地址的改动（补丁后重锚定、新增反汇编结论）交工前跑三件事：`rva_audit.py --check --falsify`、`build_aliases.py --check`、`deskrawl_gui --selftest`；`--check` 的严格性靠「改错一位必须报红」的 `--falsify` 自证，不许靠白名单消红。
- **ACTk `Obscured*` 的取值公式按类型分家，别写成统一形式**（`decode.py` 曾因此错了 3124 个值）：
  整型 = `(hidden − key) XOR key`（写入侧 `key + (value XOR key)`）；浮点 = `float_bits(ACTkByte4.Shuffle(hidden) XOR key)`。
  判据是「数值是否圆整」：错公式会把闪避 0 解成 1e-38 反常量、把符文 Base 20 解成 11.35。指令级依据见
  `aliases.json` 的 `Actk.ObscuredLong.Decrypt`（`sub`+`xor` 对 `xor`+`lea`）。
