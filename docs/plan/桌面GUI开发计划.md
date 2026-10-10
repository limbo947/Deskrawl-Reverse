# Deskrawl 桌面 GUI 开发计划（v1）

## 1. Summary

把 `tools/deskrawl_calc/` 计算内核接到 PySide6 桌面界面，交付三大核心模块：
**① 角色面板手动录入**（含巅峰/技能选择）→ **② 新旧装备对比**（DPS 增减 + 乘区分解）→
**③ 宝石/符文/天赋候选排序**（数据层全量候选，按 DPS 增量排序）。

v1 明确不做：存档解析导入、运行时读内存、打包安装程序（全部留作后续模块，架构上预留接口）。

## 2. Current State Analysis（Phase 1 侦察结论）

| 资产 | 状态 | 对 GUI 的意义 |
|---|---|---|
| `tools/deskrawl_calc/engine.py` | `StatSheet`/`Modifier`/`Target`/`DamageModel`/`Weapon`/`compare_weapons`，纯 stdlib | 直接作为后端，**零修改复用** |
| `tools/deskrawl_calc/gamedata.py` | `GameData`：gems/runes/talents/runesets/ability_scaling/affix_range 全可下拉装配 | 候选排序与词条区间提示的数据源 |
| `tools/deskrawl_calc/stattype.py` | 70 项 StatType + 中文名 `STAT_NAMES` | 所有下拉框/表格列的显示名 |
| `data/so_dump/` | 25 个 JSON（2.5MB），1333 条 0 残留 | `GameData` 自动定位，无需配置 |
| `data/save_decrypted.json` | 联机角色装备栏为空 | 确认 v1 只能手动录入面板 |
| GUI 代码 / requirements.txt | 均无 | 从零开始，依赖只有 PySide6 |

**已验证的内机对接点**：`cli.demo()` 展示了完整链路（手写 StatSheet + GameData 装配 + compare_weapons），GUI 把这条链路的所有手写输入变成界面控件即可。

**性能评估**：候选排序 = 对每候选做一次 `DamageModel.dps()`， talent/gem 各约 100-300 项，单次计算微秒级 → 全量排序 < 50ms，v1 同步计算即可保持流畅，无需线程（`calc_service` 预留线程化接口）。

## 3. Proposed Changes

### 3.0 架构总览

```
tools/deskrawl_gui/                  ← 新包（与 deskrawl_calc 平级，仅依赖 PySide6 + deskrawl_calc）
├─ __init__.py
├─ __main__.py                       python -m deskrawl_gui 入口
├─ app.py                            QApplication + 主题 + 主窗口组装（<150 行）
├─ core/
│  ├─ __init__.py
│  ├─ profile.py                     CharacterProfile：UI 唯一事实源；to_sheet()/to_json()/from_json()
│  └─ calc_service.py                同步计算服务：compare()/rank_candidates()/stat_rows()；预留 moveToThread
├─ widgets/
│  ├─ __init__.py
│  ├─ panel_editor.py                面板编辑（基础属性/巅峰/技能选择）
│  ├─ equipment_editor.py            双武器编辑（当前 vs 候选）：基础伤害/攻速/倍率/词条行
│  ├─ compare_view.py                对比结果 + 乘区 A-D 分解条
│  ├─ assembly_browser.py            宝石/符文/天赋/套装 搜索+加入构建
│  ├─ candidate_rank_view.py         候选排序结果表（QSortFilterProxyModel 排序）
│  ├─ stat_table.py                  属性明细表（70 项三层聚合分解）
│  └─ target_editor.py               目标设置（等级/护甲/10 项条件/减伤）
└─ resources/style.qss               暗色主题
requirements-gui.txt                 新增：PySide6>=6.6
```

设计原则：**GUI 包不 import `tools/scripts/` 下任何东西**（那些依赖 UnityPy/capstone），保证 GUI 环境只需 `pip install PySide6`；`deskrawl_calc` 一行不改。

### 3.1 `core/profile.py` —— 构建档案模型（约 200 行）

- **What**：`CharacterProfile` dataclass：`name, level, base: Dict[int,float]`（力/敏/智等基础面板）、`paragon: Dict[int,int]`、`skill_name, skill_level`、`weapon_current/weapon_candidate: WeaponDraft`、`assembled: List[AssemblyItem]`（宝石/符文/天赋/套装条目，含等级/点数）、`target: TargetDraft`。
- **Why**：现在 `cli.demo()` 里这些全是手写局部变量，没有可序列化结构；GUI 所有面板编辑、保存/加载构建、计算入口都围绕这一个模型转，避免各 widget 各自为政。
- **How**：
  - `WeaponDraft`：`name, base_damage, base_speed, skill_multiplier, affixes: List[Modifier]`（直接复用内核 `Modifier`）。
  - `to_sheet(gd: GameData) -> StatSheet`：base → paragon_modifiers → talent/gem/rune/runeset modifiers → affixes，与 demo 装配顺序一致。
  - `to_target() -> Target`：由 TargetDraft 构造内核 `Target`。
  - `to_json()/from_json()`：存 `data/builds/*.json`（新增目录），实现构建保存/加载；JSON 用 StatType 的 int 键，版本号字段防漂移。

### 3.2 `core/calc_service.py` —— 计算服务（约 150 行）

- **What**：纯函数式服务，输入 `CharacterProfile` + `GameData`，输出视图数据：
  - `compare(profile, gd) -> CompareResult`（包装 `compare_weapons`，附两边 DamageBreakdown）
  - `rank_candidates(profile, gd, category, *, slot=None) -> List[CandidateRow]`：基线 DPS → 遍历该类别全部候选（宝石按 equip_category、符文按 1..max_lv、天赋按 1..max_points、套装按 1..件数）→ 各自增量 DPS。
  - `stat_rows(sheet) -> List[StatRow]`：非零属性的 Base/Flat/%Add/Π/Final 五行分解。
- **Why**：把"装配 + 计算"从 widget 抽离，widget 只负责渲染；将来改线程化/缓存只需动这一个文件。
- **How**：直接调内核 `DamageModel.dps()`；`CandidateRow` 含 name/dps/delta/delta_pct/mods 描述，颜色标记在 view 层做。

### 3.3 `widgets/` —— 界面模块（每文件目标 <400 行，超限即拆）

- **panel_editor.py**：等级/力/敏/智/武器伤害等基础值 SpinBox；巅峰点数表（`paragon_stats()` 驱动，每行 StatType 中文名 + 点数 SpinBox）；技能下拉（`AbilityData` 名称列表 + 等级 SpinBox，显示 `ability_attack_scaling` 倍率）。
- **equipment_editor.py**：两组对称编辑器（当前/候选武器）。词条行 = `QComboBox(STAT_NAMES 非空项)` + `QComboBox(Flat/%Add/%Mult)` + `QDoubleSpinBox` + 删除按钮；"添加词条"按钮；底部 `affix_range` 提示标签（选中词条属性后显示 Lv×稀有度区间）。
- **compare_view.py**：左右两列 DPS 大数字 + 增减百分比（绿涨红跌）+ `DamageBreakdown` 的 A-D 乘区水平分解条（QProgressBar 风格自定义 paint，纯 QSS 可实现则不用自定义绘制）。
- **assembly_browser.py**：左：类别 Tab（宝石/符文/天赋/套装）+ 搜索框 + `QListView`（名称 + 效果摘要，摘要来自对应 `*_modifiers` 的 `describe()`）；右："已装配"列表（含等级/点数 SpinBox、删除）。信号 → 主窗口刷新属性表。
- **candidate_rank_view.py**：`QTableView` + `QAbstractTableModel` + `QSortFilterProxyModel`，列：名称/期望 DPS/ΔDPS/Δ%；双击一行可将该候选加入装配。
- **stat_table.py**：70 行 × 6 列（属性/基础/Flat/%Add/Π/Final），只显示 Final≠0 的行，数据来自 `stat_rows()`。
- **target_editor.py**：等级/护甲/魔抗/全局减伤 SpinBox，HP 百分比 Slider，10 项条件伤害 CheckBox（对应 `Target.conditional_stats()` 的 10 项）。

### 3.4 `app.py` + `__main__.py` —— 主窗口组装

- `QMainWindow`：左侧 dock = 面板编辑；右侧 dock（Tab 化）= 目标设置 + 属性明细；中央 = `QTabWidget`（装备对比 / 候选排序 / 装配浏览器）。
- 工具栏：保存构建 / 加载构建 / 运行内核自检（调 `deskrawl_calc.cli.selftest()`，结果弹窗）。
- 任何 profile 变更 → 单一 `profileChanged` 信号 → 刷新右侧属性表与中央当前 Tab 的计算结果（同步 <50ms，无卡顿）。
- 主题：`resources/style.qss` 暗色，集中调色板（QSS 变量用占位符替换，避免散落硬编码）。
- 启动时 `GameData()` 一次性加载（2.5MB JSON，实测 <1s），显示启动等待提示（QSplashScreen 或状态栏）。

### 3.5 依赖与工程文件

- 新增 `requirements-gui.txt`：`PySide6>=6.6`。
- README §5「工具 UI」行状态改为 ✅ 并加 GUI 启动说明（编辑现有文件，不新建文档）。

## 4. Assumptions & Decisions

| 决策 | 结论 | 理由 |
|---|---|---|
| 框架 | **PySide6 (Qt6)** | 用户已选；LGPL 无版权问题；与 Python 内核零桥接 |
| 数据来源 v1 | **手动输入** | 用户已选；联机角色数据本就不在本地 |
| 功能范围 | **面板 + 装备对比 + 候选排序** | 用户已选 |
| 计算线程 | v1 同步，接口预留线程化 | 全量排序 <50ms，同步无卡顿，少写一半线程代码 |
| 内核改动 | **零改动** | 内核已有全部所需 API；GUI 只 additive |
| 语言 | 界面全中文 | 与项目文档/用户一致 |
| 运行方式 | `cd tools && python -m deskrawl_gui` | 源码运行；PyInstaller 打包留作后续 |
| 存档/内存导入 | v1 仅菜单占位（禁用态） | 架构上 `profile.from_save()` 预留，不实现 |
| 文件行数 | 每 widget 文件 <400 行 | 遵循项目 800 行硬上限并留余量 |

## 5. 开发顺序（里程碑）

1. **M1 骨架**：包结构 + `app.py` 主窗口 + dock/tab 布局 + QSS 主题（空面板先跑起来）。
2. **M2 档案与面板**：`profile.py` + `calc_service.py` + `panel_editor` + `stat_table`（输入→属性表实时刷新）。
3. **M3 装备对比**：`equipment_editor` + `compare_view`（复刻 cli.demo 场景，数值与 CLI 对拍）。
4. **M4 装配与排序**：`assembly_browser` + `candidate_rank_view`。
5. **M5 收尾**：构建保存/加载、自检菜单、README 更新、全量验证。

## 6. Verification

1. **内核回归**：`cd tools && python -m deskrawl_calc.cli selftest` —— 8 项断言仍全 PASS（内核未动）。
2. **启动冒烟**：`python -m deskrawl_gui` —— 主窗口正常渲染，无异常退出。
3. **CLI 对拍**：在 GUI 中复现 `cli.demo()` 的输入（同等基础/宝石/符文/天赋/双武器/目标）→ 对比 DPS 与 Δ%，误差 <0.5%（浮点截断容忍）。
4. **排序正确性**：候选排序基线 = 不添加候选的 DPS；任取 3 个候选手工 `add_mods` 后 `DamageModel.dps` 对拍。
5. **构建往返**：保存构建 JSON → 重新加载 → 属性表与保存前一致。
6. **行数检查**：新文件全部 `<=800` 有效行（目标 ≤400）。
7. **依赖隔离**：全新 venv 只装 `requirements-gui.txt` + 本仓库，GUI 可启动（证明未误 import scripts 的重依赖）。
