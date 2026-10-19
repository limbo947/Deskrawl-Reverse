# AGENTS.md — AI 代理操作规范

> 本文面向 AI 代理：提供项目上下文、硬约束、编码约定与执行指引，使代理能基于本文独立完成常规开发任务。
> 面向人类参与者的项目概览与快速上手见 [README.md](README.md)；深层逆向证据见 `docs/`（入口 `docs/00-索引.md`）。

## 目录

- [项目性质](#项目性质)
- [仓库地图](#仓库地图)
- [常用命令](#常用命令)
- [高层架构](#高层架构)
- [编码约定](#编码约定)
- [开发流程与交工检查](#开发流程与交工检查)
- [常见问题处理指引](#常见问题处理指引)
- [Agent skills](#agent-skills)

## 项目性质

对单机挂机 ARPG **Deskrawl**（Unity 6000.3.6f1 / IL2CPP / GUPS.Obfuscator 混淆）的**只读**数值逆向仓库。已还原完整伤害公式、1333 条静态数值（SO 实例）、装备词条生成规则与存档加解密，并产出可运行工具：数值计算内核 `deskrawl_calc`、桌面 GUI `deskrawl_gui`（后者内含内存快照 CLI `memdump` 与联机角色只读导入链）。逆向工作已闭环，当前主要开发方向是 GUI 与角色数据接入。**任何情况下不得修改游戏安装目录内的文件**。

补丁后的地址重锚定已流程化（2026-10-10）：一条命令体检全仓地址（`tools/scripts/rva_audit.py`）、一张语义别名表隔离每版都变的混淆名（`data/schema/aliases.json`，43 条）、一份五步回归清单（`docs/plan/补丁回归清单.md`）+ 串行入口 `patch_regression.py`。游戏一更新，照清单走即可（见[常见问题处理指引](#常见问题处理指引)）。

环境：Windows 10，PowerShell（pwsh 优先）。Python 3.10+。无 lint/构建配置，纯 Python 仓库。

## 仓库地图

```
tools/deskrawl_calc/     纯 Python 计算内核（零依赖，可独立作库）
  stattype.py            StatType IntEnum（67 项，稀疏 ID 0–66，1.0.3 新增 FinalDamageReduction=66）
  engine.py              公式实现（三层聚合 + 伤害乘区 + 装备对比）
  gamedata.py            GameData：so_dump 加载 + Modifier 产出
  effects.py             传奇特效消费逻辑
  cli.py                 selftest（26 项断言）+ demo
tools/deskrawl_gui/      PySide6 桌面 UI（只 import deskrawl_calc）
  app.py                 主窗口装配（SidebarNav + 三页：角色/装备对比/装配中心）
  __main__.py            三模式：默认 GUI / --selftest / --smoke
  memdump.py             内存快照 CLI
  selftest.py            GUI 自检 68 项（内核 26 项为通过门槛；拆出 selftest_legendary.py 文案组、
                         selftest_skillmods.py 天赋按技能修正组）
  core/                  服务层纯函数 + 内存导入链：
    profile.py           CharacterProfile（唯一事实源，可 JSON 序列化）
    calc_service.py      全部纯函数（widget 不做计算）
    skill_service.py / glossary.py / localization.py / legendary.py / session_state.py
    dps_meter.py / assembly_meta.py / item_draft.py
    memory_reader.py     WinAPI 只读基元
    memory_locate.py     进程/类定位
    memory_import.py     快照编排 + preserved_import
    memory_validate.py   结构/键域/值域校验
    memory_snapshot.py   偏移表/指纹/版本校验（读 core/memory_offsets.json）
    memory_errors.py     MemoryImportError → 中文文案映射
  widgets/               UI 组件（15 个模块）
  resources/             暗色主题 QSS 等
tools/scripts/           逆向脚本（86 个 .py；UnityPy/capstone，面向游戏文件）
tools/thirdparty/        第三方工具（Il2CppDumper；自行下载，不入库）
packaging/               便携版打包（launcher / deskrawl.spec / build_portable.ps1 / make_zip.py）
data/                    事实源数据（so_dump 25 JSON / loc 3 表 / builds / schema）
                         注：schema 的 dump.cs·script.json·stringliteral.json 与 builds 个人
                         构建不入库，须本地生成；仓库只带 schema/aliases.json 与 rva_audit*.json
docs/                    机制与实测文档（00-索引 + 01–09）+ plan/ + reports/ + agents/
```

## 常用命令

### 计算内核（无第三方依赖，系统 Python 即可）

```powershell
cd D:\workspace\Deskrawl-Reverse\tools
python -m deskrawl_calc.cli selftest   # 26 项公式断言自检；CI 友好，非 0 退出码=失败
python -m deskrawl_calc.cli            # 自检 + 「换武器 DPS 对比」示例
```

没有 pytest 等测试框架——`selftest` 就是全部自动化测试，且为单一整体，无法只跑其中一项；修改 `engine.py`/`gamedata.py`/`effects.py` 后必须运行它。

### 桌面 GUI（独立 venv，只依赖 PySide6 + deskrawl_calc）

```powershell
cd D:\workspace\Deskrawl-Reverse
python -m venv .venv-gui
.\.venv-gui\Scripts\python.exe -m pip install -r requirements-gui.txt
cd tools
..\.venv-gui\Scripts\python.exe -m deskrawl_gui              # 启动主窗口
..\.venv-gui\Scripts\python.exe -m deskrawl_gui --selftest   # 内核 26 项（门槛）+ GUI 68 项对拍
..\.venv-gui\Scripts\python.exe -m deskrawl_gui --smoke      # 无显示环境骨架冒烟（建窗即退）
```

根目录 `启动GUI.bat` 双击可用：首跑自动建 venv 装依赖，参数透传（如 `启动GUI.bat --selftest`）。`--selftest` 不建 QApplication，headless 可跑；其 DPS 锚点（`selftest.py` 的 `ANCHORS`）与内核一起冻结，改动公式需同步更新锚点。

### 便携版打包（PyInstaller one-folder；仅构建期需要）

```powershell
cd D:\workspace\Deskrawl-Reverse
.\packaging\build_portable.ps1        # 装依赖 → 构建 → 白名单拷 data/ → 打 zip + SHA256
.\packaging\build_portable.ps1 -NoInstall -ExeName DeskrawlTool -Version v0.1.0   # CI 形态
```

- 产物 `dist\<ExeName>\`（exe + `_internal\` + `data\`）与 `dist\<ExeName>-<ver>-win64.zip`；`dist/`、`build/` 已 gitignore，不入库。
- **路径同构是硬约束**：仓库六处数据定位都是 `__file__` 相对跳转（`gamedata`/`session_state`/`profile`/`memory_snapshot`/`app`/`localization`）。frozen 下「与代码同级的小资源」必须镜像到 `_internal/<pkg>/…` 原位（spec 的 `datas`），`data/` 必须拷到 **exe 同级**（不走 datas）。**不得**设 `--contents-directory "."`，否则六处跳转一起错开一层。
- 单个 exe 分派四入口：无参=GUI（windowed，无黑框）、`--selftest`/`--smoke`（启动器按需接回控制台，三级阶梯：继承句柄 → AttachConsole → AllocConsole）、`memdump …`。
- spec 的体积过滤**必须按 `PySide6/` 前缀**（translations/qml/resources 合计约 186 MB）；若用 `\resources\` 之类子串匹配，会连自己的 `deskrawl_gui/resources/style.qss` 一起删掉，GUI 启动即抛 FileNotFoundError。
- 只读安装兜底：启动器探测 exe 同级不可写时，把 `DESKRAWL_DATA_DIR` 指向 `%LOCALAPPDATA%\Deskrawl\data`。`core/data_dir.py` 是「可写数据根」的单一事实源（`session_state.STATE_PATH` / `profile.BUILDS_DIR` 都经它），改数据根只改这一处。
- 改完必验：`exe --selftest`（期望 68/68）与 `--smoke` 退出码 0；`.github/workflows/build-portable.yml` 已把这两步作为 Release 门禁，本地构建后也应手动跑一遍。
- **排障开关**：`DESKRAWL_DEBUG_STREAMS=1` 让启动器打印实际走的分支与句柄判定（排查冻结态「没有输出」用）；`DESKRAWL_NO_PAUSE=1` 关掉自建控制台的退出暂停（自动化用）。注意 `pwsh` **不会等待** GUI 子系统 exe，本地验收必须用 `Start-Process -Wait -PassThru` 才拿得到退出码与输出。

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
- 判定链：白名单/自动非地址规则 → 当期 `dump.cs` 方法起始 → 旧构建同名方法（签名+Slot → **类形状自证** → 跨类唯一）→ 嵌套类 → 内联数据（含该地址的方法）→ `docs/08 §12.2` 常量表字节校验 → **当期 `script.json` 的字符串/元数据槽（须与 `data_refs` 的 `expect` 登记名一致）** → 旧 `script.json` 按内容/名字对搬 → 人工确认。**同名类不算证据**：混淆类名每版重生成，实测新构建有同名 `iw` 但签名交集 0/5，真身是 `je`（`gg`→`gh`、`gi`→`gj` 同理）。`.data` 元数据槽只有**当期**表能证明「还在原位」（两版 RVA 空间高度重叠，同一 RVA 在旧表里常是别的条目，按旧表判必然误报迁移）；`script.json` 的 `Address` 列是槽的 **RVA**，两张表都按 RVA 过滤——曾按 VA 过滤导致两表全空、这两条规则静默失效。
- 报告落 `docs/reports/RVA体检报告.md`（+ `-文档.md`），机读结果落 `data/schema/rva_audit*.json`；`rva_verify.py` 是复核与渲染段（从 `rva_audit.py` 拆出）。
- 文件分区（`rva_audit_config.json`）：`literal`/`data_refs` 每条必须写明理由；弃用探针的理由**必须真的写在文档里**（脚本会打开文档校验标记），文档侧历史证词用 `doc_policy` 或文档内 `<!-- rva-audit:historical 理由 -->` 标记——都不许用来「消灭红点」。
- 报告第 8 段是两项**自校验**（补丁后的第一声警铃）：① `data_refs` 每条必须带锚点——`expect`（当期 `script.json` 的条目名/字面量，判定链 ⑥ 会核对）或显式 `anchor: "none"`（当期无锚点可查，理由写在 `reason` 里），缺锚点直接判错，防「登记即有效」静默降级；② `doc_fingerprints`：`docs/08 §12` 记录的构建 SHA 必须等于磁盘实测（双向：文档要记、值要对），给 `*Registration` 这类无锚点导出指针一个「补丁后先红」的锚。
- **写地址的习惯**：注释与文档引用**语义名**（`aliases.json` 的键）而非当期混淆名；紧邻「旧/补丁前」标注的地址是刻意保留的对照，不要「顺手修正」。

### 逆向脚本（tools/scripts/，重依赖，仅重建数据时需要）

依赖 `UnityPy`、`capstone`；存档解密另需 `cryptography` 或 `pycryptodome`（两者任一，`decrypt_save.py` 自动回落）。游戏目录由环境变量 `DESKRAWL_GAME` 定位（默认 `d:\steam\steamapps\common\Deskrawl`），换机器只需设它。所有脚本从 `paths.py` 取路径，仓库可整体移动。典型用法：`python decrypt_save.py`（解密存档→`data/save_decrypted.json`）、`python read_save.py`、`python dump_all2.py`（重导 SO）。重新生成 `data/schema/`：用 `tools/thirdparty/Il2CppDumper` 对 `GameAssembly.dll` + `global-metadata.dat` 导出，只保留 `dump.cs`/`script.json`/`stringliteral.json` 三个文件。**该工具与这三个产物都不入库**——首次使用需自行下载工具并生成，否则地址工具链（`rva_audit.py`/`build_aliases.py`）与 `schema.py` 无输入；计算内核与 GUI 不受影响。详见 README「准备 schema 与第三方工具」。

## 高层架构

### 三层单向依赖：内核 → GUI →（断）→ 逆向脚本

```
deskrawl_calc   纯 Python 计算内核（零依赖，可独立作库）
     ↓ 只读依赖
deskrawl_gui    PySide6 桌面 UI（只 import deskrawl_calc）
     ✗（刻意断开）
tools/scripts   逆向脚本（UnityPy/capstone，面向游戏文件）
```

**硬约束：GUI 包不得 import `tools/scripts`**（包括内存导入链也刻意自包含，只用 stdlib）。`core/memory_reader.py` 与 `scripts/mem_probe.py` 是「算法同源、代码独立」的两份实现，允许约百行重复——诊断脚本宽容带打印，导入通道严格抛错。改其中一份时另一份不自动同步。

### deskrawl_calc：公式 + 数据两层

- `stattype.py`：`StatType` IntEnum（67 项属性，稀疏 ID 0–66）+ 分组表 `CORE`/`ALL_ELEMENTS`/`CONDITIONAL_DAMAGE` 与封顶组 `CAPPED_085`/`CAPPED_080`/`CAPPED_090`。**枚举值是稀疏 ID，游戏存档/配置按 ID 引用，禁止重排或改值**；分组表来自 `ItemizationConfig` 元数据（SHA-256 自校验过的硬结论），不是推断。
- `engine.py`：公式实现，模块 docstring 把每条公式映射到 `docs/04` 的章节号（✅=指令级证据，🔶=推断且已做成可覆盖参数）。核心模型：
  - 三层聚合 `Final = (Base + ΣFlat) × (1 + ΣPercentAdd) × Π(1 + PercentMult)`（`StatSheet` 持有 base/flat/add/mult 四个字典）。
  - 伤害乘区：乘区 A（元素% 与全伤害% **同池加算**）× 乘区 B（暴伤，独立）× 乘区 C（10 项条件伤害同池）× 易伤 1.3 × 命中浮动 × 减伤层（护甲曲线 `resist/(resist+50×max(1,level))` 等，乘法）。封顶（1.0.2b 实证）：暴击率/闪避/蓝耗缩减 0.85，CDR 0.80，减伤类 0.90。真正独立的乘区只有 4 个。
  - DOT tick 完整形态：`round(实例倍率 × 条件池 × max(1,叠层) × 1.0 × 暴击)`；62 号属性与元素乘区同池，标签乘区 33/34/61 不参与 DOT。
  - 1.0.3 新增 `FinalDamageReduction(66)`：受击方绝对减伤 `max(0, 伤害×减伤层 − Final(66))`，不进攻击方 DPS 倍率。
  - `unwrap()` 兼容 dump 里的 `Obscured*`（`{'value': x}`）与 `LeveledFloat`（`{Base, PerLevel}`，公式 `Base + (level-1)×PerLevel`）嵌套结构——处理 so_dump 数据时必须经过它，不能直接当 float 用。
- `gamedata.py`：`GameData` 加载 `data/so_dump/*.json`（懒加载+缓存，按 `_name` 索引），产出可直接入 `StatSheet` 的 `Modifier`：宝石（按镶嵌部位 0/1/2 区分加成组）、符文、天赋、传奇特效（by pathID）、巅峰、技能倍率、词条 Roll 区间。数据目录自动定位 `../../data/so_dump`（仓库自定位，无绝对路径回落）。
- `effects.py`：传奇特效消费逻辑（条件暴击/暴伤、标签暴伤、条件伤害、技能修正、引导修改、属性换算等，A 类 32 条已建模）。
- `cli.py`：26 项 selftest 断言的数值都取自 docs/04 的可对照证据，是「公式实现 == 逆向证据」的回归网。

### deskrawl_gui：profile 为唯一事实源，服务层纯函数

- `core/profile.py`：`CharacterProfile`（可 JSON 序列化，存 `data/builds/*.json`）是面板编辑、构建存取、计算的唯一事实源。装配顺序与 `cli.demo()` 刻意保持一致，使 GUI 复算能与内核直算对拍。装备槽→宝石部位的映射（`_GEM_CATEGORY_BY_EQUIP_TYPE`）是内存面板实测锚定的，勿按直觉改。
- `core/calc_service.py`：全部纯函数（输入 profile/GameData，输出视图 dataclass），widget 不做计算。将来要把排序挪线程只改这一个文件。
- `app.py`：只做主窗口装配（侧边导航 `SidebarNav` + 三页堆栈：角色 / 装备对比 / 装配中心）与信号中转；编辑逻辑下沉 `widgets/`。导入错误统一走 `MemoryImportError.code` → 中文文案映射（`_IMPORT_ERROR_TEXTS`），新错误态应加 code 而非拼消息子串。会话持久化：关闭时把窗口几何/当前页 + 完整 profile 落盘 `data/session_state.json`（gitignore 排除，原子写），启动自动恢复；`MainWindow(persist_state=False)` 为默认（测试/冒烟不碰用户状态），仅生产入口 `run_gui` 显式开启。内存导入走 `preserved_import`：只换角色数据，保留用户口径（图二目标/参考技能/伤害类型/开关记忆）——不能退回裸 `from_snapshot`（selftest 会红）。
- 对比页的取向：**当前件（游戏事实）只读**（`ItemEditor.set_locked`，导入态自动生效）——基线可改就等于对比失效；参考技能卡（`widgets/skill_card.py`）挂在目标基础卡片下方（换装预测/循环系数的基线口径）；候选**任意槽**可勾「与当前装备相同（强化/宝石）」，按背包原始词条 `raw_modifiers` 重算，**选择跨槽保持**（`profile.like_current_pref` 记忆位，换槽/载入背包件自动沿用，随会话持久化）——武器孔位宝石**按侧计入** `compare(slot=0)`（先按槽卸下装配链里的当前武器宝石，再并入各自武器词条），非武器槽走「先卸下当前件再按侧装回」（`_slot_sheets`）。装备名经 `core/localization.py` 按游戏 Equipments 本地化表（`data/loc/equipments_zh.json`）在导入时翻成简中。
- `__main__.py` 三模式互斥：`--selftest`（纯数值，不建 QApplication）、`--smoke`（建窗即退）、默认 GUI。

### 内存导入链（GUI 内，联机角色只读导入）

`memory_reader.py`（WinAPI 基元）→ `memory_locate.py`（定位）→ `memory_import.py`（快照编排）→ `memory_validate.py`（校验）→ `memory_snapshot.py`（偏移表/指纹/版本校验），偏移集中在 `core/memory_offsets.json`。

- **只读硬约束（验收条款）**：只允许 `OpenProcess(0x0410)` + `ReadProcessMemory`；禁止 WriteProcessMemory/CreateRemoteThread/SuspendThread/DLL 注入，整条导入链任何时候不得出现写操作。
- **校验哲学「宁可红不出脏」**：结构/键域/值域/双读一致性任一失败即抛错，绝不返回可疑数据；定位链全部以类名自校验收尾。
- 游戏更新后只需改 `memory_offsets.json`；版本指纹（`check_fingerprints`）同时校验偏移与 so_dump 静态数据，失配即拒绝导入。
- α/β 是能力降级而非开关：装备容器不可用时自动降级 α（聚合字典）并给 warnings，β 提供逐件词条。
- 背景：联机角色数据在服务器不在本地，所以走运行时读内存；本地模式存档才有完整角色数据（`read_save.py` 可解析）。

### tools/scripts：逆向脚本与地址工具链（86 个 .py）

公共基座：`paths.py`（统一路径，所有脚本 `from paths import *`）、`schema.py`（从 `data/schema/dump.cs` 用正则重建 Unity 序列化 schema：字段、偏移、继承）、`decode.py`（schema 驱动的 Unity 二进制反序列化器，含 ACTk `Obscured*` 序列化尺寸与 `[SerializeReference]` 托管引用段布局——主数据流只存 count+8B 键，真实对象在字段区之后的托管段）。其上：`dump_all2.py`/`dump_effects.py`（批量导出 SO/特效→`data/so_dump/`）、`decrypt_save.py`/`read_save.py`（DDS2 存档 AES-256-CBC + HMAC-SHA256，密钥 `SHA256("desktop-diablo-save-v1-CHANGE-ME")`）、`disasm.py`/`disasm2.py`/`xref.py`（capstone 反汇编 `GameAssembly.dll`，VA 基址 0x180000000，RVA↔文件偏移换算）、`extract_rolltable.py`（词条系数表）、`extract_localization.py`（简中表导出）。

**地址工具链的四个基座**（被 `rva_audit.py`/`build_aliases.py` 复用，改一处两边都受益）：`dump_index.py`（`dump.cs` 方法与字段索引 + **归一化签名**——抹掉混淆名只留类型/参数/返回类型，以及类形状指纹）、`pe_file.py`（PE 只读：节表、VA↔偏移、位模式搜索，用来做常量字节校验）、`script_index.py`（`script.json` 流式索引，「地址↔语义」双向表，用于字面量/元数据对搬）、`rva_verify.py`（体检的证据复核与报告渲染段）。`rea_broker.mjs` 是绕开工具超时的常驻 REA 通道（**开工期间不要重启**，Ghidra 的 81 分钟分析会重来），调用前端是 `rea_call.py`（`python rea_call.py <tool> k=v …`，写 `%TEMP%\rea-broker\request.json` 轮询 `response.json`）——**REA 入参必须用 VA**（0x180000000+RVA，传 RVA 报 "No procedure exists"），且参数用 `k=v` 而非 JSON（PowerShell 转义会剥引号）。

其余多为一次性探针（probe/scan/exp_*），新探针仿照现有写法即可，不必追求复用它们——其中 6 个已在 `docs/plan/补丁回归清单.md` 登记为**弃用探针**（不随补丁重锚定，理由必须写在文档里，否则体检判红）。

> ⚠️ **重导 so_dump 前先重建资产缓存**：`dump_all2.py` 依赖 `tools/scripts/assets_cache.json`，该缓存偏旧时
> 只会认到 251/338 件物品——直接重跑会把 `data/so_dump/` 覆盖成更小的数据集（2026-10-10 实测后已回滚）。
> 重导流程：重建缓存 → 跑 `dump_all2.py` → `git diff --numstat data/so_dump/` 逐文件核对，只许看到数值行变化。

### data/ 与 docs/

- `data/so_dump/`：25 个 JSON、1333 条 SO 实例（字节级精确，0 残留），是全部静态数值的事实源。JSON 里 `_name`/`_pathID`/`_managedRefs` 是导出器附加的元字段。
- `data/loc/`：Unity Localization 表导出的简中映射（`abilities_zh.json` 技能名、`equipments_zh.json` 装备/宝石/符文/套装名、`talents_zh.json` 天赋名、`ui_zh.json` 界面词；`extract_localization.py <表名>` 导出，GUI 显示名用，缺表/未覆盖回落内部名）。注意**天赋不在 Equipments 表**（实测 186/186 全缺），须单独导 Talents 表。补丁更新游戏后本地化表若变，需重跑导出。
- `data/schema/`：Il2CppDumper(v39) 产物 `dump.cs`/`script.json`/`stringliteral.json` —— **这三者不入库**（约 121 MB，含游戏逆向产物），首次使用由各人本地生成（见 README「准备 schema 与第三方工具」，工具在 `tools/thirdparty/` 亦不入库）。仓库随附的只有 `aliases.json`（**语义别名表**，43 条：伤害链/面板口径/ACTk 解码器/存档加解密链/Roll 表）与 `rva_audit*.json`（体检机读结果）；涉及地址工具链的任务若无 `dump.cs`，先自行生成再动手。
- 注意存在**两套同名 GameConfig**：`MaxPlayerLevel` 35（Beta，resources.assets）与 70（正式，sharedassets0.assets），查配置时先确认哪套（`dump.cs` 里只有一个 `GameConfig` 类）。
- `docs/00-索引.md` 是文档入口（含分类地图与按需阅读路径）；docs/01–05 是**机制与结构篇**（架构/属性/数据结构/公式/配置字段）、06–09 是**实测与工具篇**（成长曲线/内容数值/常量与地址/存档），编号即阅读顺序；docs/08 §11 存硬结论、§12 存补丁后重锚定结果；docs/plan/ 存**现行**计划/清单/进度档，已完结的历史证词移入 `docs/plan/archive/`（**地址不随补丁回改**）；docs/reports/ 存**脚本产出的报告**（勿手改，重跑命令见 `docs/plan/补丁回归清单.md`）。文档置信度标注：✅ 指令/字节级证据、🔶 高置信推断（**当前正文已无在用条目**）、⚠️ 待确认（「暂缓」条目必须写明复核条件）——引用数值时沿用此标注，不要把 🔶 或暂缓写成定论。

## 编码约定

- 函数级注释解释「为什么」（动机与权衡），不复述「做什么」，1–3 行。
- 单文件有效代码（不含空行/注释）≤800 行；已超限文件只降不升（修改前先实测行数作基准）。接近上限时拆文件——`memory_snapshot.py`/`memory_locate.py`/`memory_validate.py` 就是从 `memory_import.py` 拆出的范例，拆分理由写在被拆文件 docstring 里。
- 新功能优先复用现有模块（引擎的 `unwrap`/`leveled_value`、GUI 的 `calc_service` 纯函数、脚本的 `paths`/`schema`/`decode`/`dump_index`/`pe_file`/`script_index` 基座）。
- GUI 会话持久化默认仅生产入口启用，selftest/smoke 等自动化路径显式关闭（`persist_state=False`），避免污染用户状态。
- **ACTk `Obscured*` 的取值公式按类型分家，别写成统一形式**（`decode.py` 曾因此错了 3124 个值）：
  整型 = `(hidden − key) XOR key`（写入侧 `key + (value XOR key)`）；浮点 = `float_bits(ACTkByte4.Shuffle(hidden) XOR key)`。
  判据是「数值是否圆整」：错公式会把闪避 0 解成 1e-38 反常量、把符文 Base 20 解成 11.35。指令级依据见
  `aliases.json` 的 `Actk.ObscuredLong.Decrypt`（`sub`+`xor` 对 `xor`+`lea`）。

## 开发流程与交工检查

1. **改代码先跑相关自检**：动 `engine.py`/`gamedata.py`/`effects.py` → `deskrawl_calc.cli selftest`；动 GUI → `deskrawl_gui --selftest`（68 项）。selftest 是整体，不可只跑子集；断言数值来自 docs/04 证据，改公式必须同步更新 GUI 的 `ANCHORS`。
2. **涉及地址的改动**（补丁后重锚定、新增反汇编结论）交工前跑三件事：`rva_audit.py --check --falsify`、`build_aliases.py --check`、`deskrawl_gui --selftest`；`--check` 的严格性靠「改错一位必须报红」的 `--falsify` 自证，不许靠白名单消红。
3. **新错误态/新 UI 样式**：导入错误加 `MemoryImportError` code 而非拼消息子串；QSS 规则必须与控件 objectName 绑定（selftest 有双向对账断言，死钩子会红）。
4. **提交**：只提交相关文件；`data/session_state.json`、`*.tmp`、`.venv-gui/`、`__pycache__/` 不入库（gitignore 已配）。Windows 下多行提交信息用 `git commit -F` 读文件，避免 PowerShell 转义问题。
5. **新建探针/文档**：探针放 `tools/scripts/` 仿照现有写法；issues/specs 按 [Agent skills](#agent-skills) 的 issue-tracker 约定放 `.scratch/<feature>/`；文档置信度用 ✅/🔶/⚠️ 标注。

## 常见问题处理指引

### 游戏更新（补丁）后地址失效

照 `docs/plan/补丁回归清单.md` 走五步，或一条命令串行：

```powershell
cd d:\workspace\Deskrawl-Reverse\tools\scripts
python patch_regression.py --live      # 指纹 → 体检 → 别名 → 自检 →（游戏运行中）实机
```

要点：体检报告红了先读判定链结论再动手改；语义别名用 `build_aliases.py --write` 刷新（旧值自动压入 history）；偏移改动集中在 `core/memory_offsets.json`；两版混淆类名同名不算证据（见[常用命令·地址体检](#地址体检与语义别名补丁后必跑系统-python-即可无第三方依赖)）。

### 内存导入失败（GUI 数据导入报错）

按 `MemoryImportError.code` 对照 `_IMPORT_ERROR_TEXTS`（六类错误态，app.py）排查：
`no_process` → 先启动游戏并进入角色；`no_hero` → 停留在主菜单/加载中，进入角色后重试；
`denied` → 以管理员身份运行；`py32` → 换 64 位 Python；`fingerprint` → 游戏更新后偏移未重锚定，
走补丁回归流程；`data`（默认回落）→ 读取/校验失败（宁可红不出脏），先跑
`memdump --no-double-read` 诊断。版本指纹同时校验偏移与 so_dump，失配即拒绝导入是刻意设计，不要绕过。

### 重导 so_dump 数据量变小

`assets_cache.json` 过期所致（只认到 251/338 件物品）。先重建资产缓存再跑 `dump_all2.py`，并用 `git diff --numstat data/so_dump/` 逐文件核对，只许看到数值行变化（详见[高层架构·tools/scripts](#toolsscripts逆向脚本与地址工具链86-个-py)的警告块）。

### selftest 构造 QWidget 崩溃（0xC0000409）

selftest 里构造任何 QWidget 前必须先建 QApplication；piped 输出要加 `-u` 才能定位真实崩溃点。

### `.data` 元数据槽按旧表判迁移误报

只有当期 `script.json` 能证明槽还在原位；两版 RVA 空间高度重叠，按旧表判必然误报。`script.json` 的 `Address` 列是 RVA，过滤必须按 RVA 而非 VA（曾因此两表全空、规则静默失效）。

## Agent skills

### Issue tracker

Issues 与 specs 以本地 markdown 文件存放于 `.scratch/<feature>/`。详见 `docs/agents/issue-tracker.md`。

### Domain docs

Single-context 布局：仓库根 `GLOSSARY.md` + `docs/adr/`。详见 `docs/agents/domain.md`。注意：这两个文件目前尚未创建，属预期状态——由 `/domain-modeling` 等 skill 在术语/decision 实际被解决时懒创建；缺失时静默继续，不要预先创建，也不要标记缺失。
