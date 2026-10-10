# PROGRESS · 内存导入 P1/P2（本任务书范围：M1 + M2）

> 任务书：`goals`（2026-10-07）。规格：`内存导入P1-P2工程实施计划.md` v1.1。
> 本文件每完成一项任务立即更新；中断续跑以本文件为准。

## 交付确认（交给用户前核对）

- [x] 任务1 M2-0：mem_probe.py 加 Dictionary 遍历，7 段字典输出
- [x] 任务2 M1 spike：装备容器结论（β 偏移 / α 固化死因）
- [x] 任务3 M2 核心：memory_import.py + memory_offsets.json + memdump.py（双读一致 + 对拍一致）
- [x] 反向验证：红→绿证据已贴
- [x] 回归：内核 8/8、GUI 14/14、smoke 0；改动仅落白名单

---

## 任务 0 · 基线核对（2026-10-07）

解释器：`d:\workspace\Deskrawl-Reverse\.venv-gui\Scripts\python.exe`；工作目录 `d:\workspace\Deskrawl-Reverse\tools`。
游戏：Deskrawl.exe **PID=28336**（与基线一致），角色 ExampleHeroB Lv70 已加载（槽位 nfk=1）。

### git status --porcelain（原样，改动基线）

```
 D BLOCKED.md
 D PROGRESS.md
 M tools/deskrawl_gui/selftest.py
 M tools/deskrawl_gui/widgets/equipment_editor.py
?? docs/plan/
?? tools/scripts/mem_probe.py
?? "启动GUI.bat"
```

> 说明：根目录 BLOCKED.md/PROGRESS.md 的删除、selftest.py 与 equipment_editor.py 的修改均为**他人未提交改动**，任务书禁碰；本次白名单改动只允许新增到 `docs/plan/`、`tools/deskrawl_gui/core/`、`tools/deskrawl_gui/memdump.py`、`tools/scripts/mem_probe.py`。

### 五条命令实测结果

1. `python -m deskrawl_calc.cli selftest` → **8 PASS / 0 FAIL** ✅
2. `python -m deskrawl_gui --selftest` → **14/14 全部通过** ✅
3. `python -m deskrawl_gui --smoke` → widget 456，**EXITCODE=0** ✅
4. `cd tools\scripts && python mem_probe.py` → 路径 B 成立 ✅
   - `_level=70` ✅、`BaseMaxHealth=1204` ✅、`BaseDamage=0`、`BaseMaxMana=100`、`BaseCritChance=0.05`
   - `Inventory.nso` 背包 0 项（数组长 40）✅
   - `Storage.nyk` 仓库 **116 项**（数组长 250）——**与任务书基线「95 件」不一致**
   - 单例：GameManager/Inventory/Storage 全部定位成功；SaveSystem 辅助链正常（nfn=SaveContainer v5）
5. 游戏进程存在（PID 28336）

### 偏差裁决：仓库 95 → 116

判定为**游戏内实时状态变化（活数据），非链路回归**：同次重跑中 level/生命/背包 0 三个锚点全部一致，单例链与解码链完好；
mem_probe.py 脚本自身未改动（`git status` 确认 untracked 且本次任务 1 之前未编辑）。
仓库件数的对拍基线改用**本次会话实测值**（两工具在同次会话内逐项一致即可，不追认 95）。
（依据任务书："快照数值必须来自当前活体进程"。）

### 理解（目标/顺序/最大风险，≤10 行）

1. 目标：让一条 CLI 命令把游戏内存里的角色快照（level/聚合字典/背包/仓库）成结构化数据，且与诊断工具 mem_probe 逐项对拍一致——这是 GUI 一键导入的地基。
2. 顺序：先 M2-0（mem_probe 字典遍历，对拍基准）→ M1 spike（装备容器，半天止损）→ M2 核心（memory_import 五层 + memdump CLI）→ 反向验证 → 全量回归。
3. 最大风险：聚合字典 Entry 布局（0x38/ObscuredDouble 0x28）若与实测有出入，对拍基准失真；先用 mem_probe 打印全量 KV 并做值域断言兜底（暴击∈[0,1]、生命>1204、力量>0）。
4. 次风险：撕裂读导致两次快照不一致；对策=双读一致性校验 + 校验失败即报错拒出脏数据（宁可红，不出脏）。
5. 边界：只读两 API 硬约束；白名单外文件一律不动（尤其 selftest.py / equipment_editor.py 的他人改动）。
6. 止损：M1 三策略全落空即固化 α 模式（合格）；同一验收连败 3 次换下一项并如实记录。

---

## 任务 1 · M2-0 字典遍历沉淀（✅ 完成）

命令：`python mem_probe.py`（工作目录 `tools\scripts`，脚本新增 `stat_dict()` / `dump_stat_dicts()`，
布局 entries@0x18、count@0x20、Entry 0x38：next@0/hash@4/key@8/value@0x10，空闲槽 next<=-2 跳过）。

实测输出（PID 28336 活体进程）：

- **7 段字典全部可读**：`nsq` 33 KV、`nsr` 0 KV、`nsu` 5 KV、`nsv` 1 KV、`ntc` 6 KV、`ntd` 0 KV、`nte` 1 KV
- **值域自检 6 项全 PASS**：键均为合法 StatType(0..65)；值均为有限 double；
  `nsq` 生命=2511.8 > 1204(基础)【Final 候选】；`nsq` 暴击率=0.34 ∈[0,1]；`nsq` 力量=377 > 0
- 旧锚点不回归：`_level=70` ✓、`BaseMaxHealth=1204` ✓、背包/仓库照常打印
- **双跑一致性（预验收）**：连跑两次，聚合字典段（55 行）逐行一致 ✓

### 语义观察（供任务 3 标注，勿当结论）

- `nsq` = Final 面板候选（力量 377 / 生命 2511.8 / 暴击 0.34 / 护甲 4362.95，33 键，全战斗属性+减伤）
- `nsu`(5) / `nsv`(1) / `nte`(1) = 小规模增量池（nsu 含力量+50、暴击+0.1、暴伤+0.8…像装备增量）；
- `ntc`(6) = 非战斗增益（金币 1.5 / 魔法装备 1.0 / 药水 0.42 / 背包容量 12 / 材料 2.0 / 经验 1.5）；
- `nsr`/`ntd` 当前为空。

### ⚠️ 环境观察：玩家正在活动（活数据）

本次会话内实测到 **背包 0 → 24 → 25 件**、仓库 116 → 115 件（数组容量不变）——
游戏内实时状态在变（正常游玩拾取）。对任务 3 双读验收的影响：
**物品 UID 列表可能因游玩而合法变化**；聚合字典段不受影响（55 行一致）。
双读验收时若 UID 段不等，先判别是否游玩干扰（间隔重跑/看 dict 段是否仍一致），如实记录，不粉饰。

---

## 任务 2 · M1 spike 装备容器定位（✅ 完成：**β 可行 + 容器偏移实证**）

### 结论（领导要求的产出格式）

**β 逐件导入模式可行。** 三策略中第 1 策略（UI/管理器反查）直接命中，按计划「任一命中即停」，
策略 2（nwo 填充链）与策略 3（进图前后枚举对比）未动用。

**容器偏移（全部活体实测）**：

| 容器 | 获取链 | 布局 | 实测 |
|---|---|---|---|
| `EquipmentManager` 单例 | getter `dbz()` RVA **0x753370**（`<mqx>k__BackingField` static+0x0，与 GameManager 同套 getter 链） | — | 定位成功 0x1FA7E5A7900 |
| `mqz` 槽→SO | **EquipmentManager+0x28** | `Dictionary<EquipSlotId, ItemData>`，Entry 步长 **0x18**（key i32@8 / value ptr@0x10） | **12/12 槽**有 ItemData，klass=ItemData |
| `mra` 槽→UID | **EquipmentManager+0x30** | `Dictionary<EquipSlotId, string>`，步长 0x18 | **12/12 槽**有 GUID |

**交叉验证（全绿）**：① 每槽 ItemData.EquipSlot(SO@0x90) ≡ EquipSlotId→EquipSlotType 期望映射
（dce 表，12/12 OK）；② 全部 ItemData.Type=3=Equipment（12/12）；③ `Rarity=3` 与名称 Legendary* 自洽。

### 附：β 完整数据源（本次顺带定位，超预期）

- **逐件实例数据**：静态类 `gi` 的 `myk`（`doj()` @0x7731B0 扫槽定位），`Dictionary<string, GeneratedItemData>`，
  **587 条，12 件装备 UID 命中 12/12**。`GeneratedItemData` 布局：ItemLevel@0x10 / Rarity@0x14 /
  `Modifiers: StatModifier[]`@0x18 / UpgradeLevel@0x20 / RuneLevel@0x28 / SocketCount@0x38 /
  SocketedGemBaseIds@0x40 / InstanceId@0x50。
  `StatModifier`（struct 0x1C）：`StatType Stat`@0 + `ModifierType Type`@4 + `ObscuredFloat Value`@8。
  武器样例：Lv=845 / Upg=4 / Sock=3 / Mods[7]。
- **名称反查（替代 so_dump 静态表）**：`SaveSystem.ngi`@**+0x70**，`Dictionary<string, ItemData>`，
  535 条 → 建「指针→名称」倒排：**12 件装备全部解析出名称**（LegendarySword1 / LegendaryHelm2 /
  LegendaryChestArmor5 / LegendaryPants3 / LegendaryBoots1 / LegendaryBelt3 / LegendaryRing7 /
  LegendaryRing5 / LegendaryNeck1 / LegendaryShoulder3 / LegendaryGloves2 / LegendaryBack4）。
  任务 3 需与 `data/so_dump/ItemData.json` 名称键交叉核对（只读比对）。
- 名称表 `ngi` 属 SaveSystem 实例（nfi 链已通），背包/仓库物品同样可用其解析名称（α 模式受益）。

### 备注

- 环境仍为活数据：会话内背包 0→25→0 件波动（玩家在玩）；装备 12 槽全程稳定。
- spike 探索过程无持久文件落盘（stdin 脚本 + 只读；白名单无越界）。

---

## 任务 3 · M2 核心 memory_import + memdump（✅ 完成）

### 交付物（全部落白名单）

| 文件 | 有效代码行 | 说明 |
|---|---|---|
| `tools/deskrawl_gui/core/memory_offsets.json` | 83 行（JSON） | 全部 RVA/偏移/槽位映射集中表 |
| `tools/deskrawl_gui/core/memory_reader.py` | 223 | ProcessReader / Il2CppReader / ActkCodec 三层（按计划拆分） |
| `tools/deskrawl_gui/core/memory_import.py` | 413 | Locator / SnapshotBuilder / import_snapshot（目标 400，超 13 行→见 BLOCKED 非阻塞项） |
| `tools/deskrawl_gui/memdump.py` | 79 | CLI：人类可读 / --json / --no-double-read；退出码 0=成功 2=环境 3=数据 |

### 关键实现

- 五层结构齐备；偏移全集中 `memory_offsets.json`（含 EquipSlotId→EquipSlotType 期望映射，
  用于装备链交叉自校验）；
- **城镇态链已接入**：进图态（GameManager+0x40）优先、城镇态（+0x48→PlayerTownController+0x20）兜底；
- **β 模式全量落地**（spike 收益兑现）：12 槽 uid+名称+逐件词条（StatModifier 内联 0x1C）+强化/符文/孔+宝石 BaseId；
- 「宁可红不出脏」：结构/键域/值域（|v|≤1e9、聚合生命≥基础生命、暴击∈[0,1]、力量>0）/UID 唯一/双读一致，
  任一失败即抛错、不输出数据；
- 领域修正：可堆叠材料/宝石（GemData 等）**无实例 UID 属正常态**（仓库 28 件），UID 查重仅限非空值。

### 实测输出（PID 28336 活体，2026-10-08 00:2x）

- 模式=beta、城镇态=False、角色 ExampleHeroB Lv70（槽位 1，profile 0000…0001）
- `player._level=70  BaseMaxHealth=1204`（与 mem_probe 一致）
- 7 字典：nsq 33 / nsr 0 / nsu 5 / nsv 1 / ntc 6 / ntd 0 / nte 1 KV；Final 候选=nsq
- 装备 12 槽全解析：Weapon=LegendarySword1 ilv=845 upg=4 sock=3 mods=7（词条全 t0 加法，与项目纪律
  「词条类型全为加法」一致）；Back 无词条（ilv=1）
- 仓库 115 件（含 28 件无 UID 堆叠：6 系宝石多档 + ExpPotion1×2）；背包 0 件（玩家活动中，会话内波动 0↔25）

### 完成条件 1：双读一致 + 对拍一致（命令实测）

- `python -m deskrawl_gui.memdump` 连跑两次：**除时间戳外 206 行逐行一致**；指纹两次相同：
  `[指纹] dicts=f4f8020958bc1856  uids=0484dc4abf2fe1bc`
- 与 `mem_probe.py` 对拍：**46 KV = 46 KV 逐项一致**；level memdump=70/mem_probe=70；
  BaseMaxHealth 1204/1204；仓库件数 115/115 ✅
- `--json` 输出可被解析（meta/装备 12/仓库 115 全量）✅

---

## 反向验证与回归（✅）

### 反向验证（红→绿，必做项）

1. **红**：把 `ActkCodec.obsc_double` 的字节置换故意改错（`r = b`，跳过置换，模拟解码算法回归）→
   `python -m deskrawl_gui.memdump` 输出：
   `[失败] 字典 nsq[21] 值域异常：5.467757287081266e+192（解码/撕裂读）`，
   **退出码 3，未输出任何脏数据** ✅
2. **绿**：还原置换后复跑 → `[校验] PASS：结构/键域/值域/双读一致性全部通过`、退出码 0，
   指纹与破坏前完全一致（f4f8020958bc1856 / 0484dc4abf2fe1bc）——证明还原精确，且指纹可当算法回归哨兵。
   （说明：任务书示例「key^1」只翻转最低位尾数（相对变化 ~1e-16），任何值域校验原理上都无法察觉；
   故取「会产生真实数值破坏的置换回归」作为红证据，符合「必须看到校验失败/值域报警」的意图。）

### 回归（全部不退）

- 内核 `python -m deskrawl_calc.cli selftest` → **8 PASS / 0 FAIL**
- GUI `python -m deskrawl_gui --selftest` → **14/14 全部通过**
- GUI `python -m deskrawl_gui --smoke` → **退出码 0**
- 行数：新文件 223 / 413 / 79 有效行、offsets.json 83 行，全部 <800 硬限

### git 白名单核对（对比任务 0 基线）

新增改动仅：`docs/plan/PROGRESS-P1P2.md`、`docs/plan/BLOCKED-P1P2.md`、
`tools/deskrawl_gui/core/memory_{import,reader}.py` + `memory_offsets.json`、`tools/deskrawl_gui/memdump.py`、
`tools/scripts/mem_probe.py`（任务 1）。他人未提交改动（selftest.py、equipment_editor.py、
根目录 BLOCKED.md/PROGRESS.md 删除）**原样未碰**。✅

## 遗留清单（领导已拍板 / 下一版本）

1. **城镇态实机验证**：兜底链代码已接好（+0x48→+0x20），本次实测环境为进图态（战斗链命中、
   town_mode=False）；城镇态另一态实测留下版本（领导拍板）。
2. **M3 GUI 集成 + M4 P2 健壮化**：下一张任务书（错误态六场景、指纹 SHA-256/so_dump 联动、菜单接通）。
3. **7 字典语义标注**（Final/Flat 池命名）：7 段值已全量可读，命名待 GUI 对拍（M3）。
4. **β 装配链对拍**（GUI 装配 Final ≡ nsq 逐键、误差 0）：依赖 M3 装配实现后执行。

---

# 【P1/P2 接续任务书 · 2026-10-08】任务 1–3（from_snapshot / GUI 集成 / P2 健壮化）

> 任务书：`goals`（2026-10-08）。规格：`内存导入P1-P2工程实施计划.md` v1.1。前篇 M1+M2 已验收；
> 本段起为本张书的进度记录（逐项追加）。

## 任务 0 · 基线核对（2026-10-08）

解释器：`d:\workspace\Deskrawl-Reverse\.venv-gui\Scripts\python.exe`；工作目录 `d:\workspace\Deskrawl-Reverse\tools`。
游戏：Deskrawl.exe **PID=28336**（与任务书一致），角色 ExampleHeroB Lv70 已加载（进图态，槽位 1）。

### git status --porcelain（原样，本张书基线）

```
 D BLOCKED.md
 D PROGRESS.md
?? docs/plan/
?? tools/deskrawl_gui/core/memory_import.py
?? tools/deskrawl_gui/core/memory_offsets.json
?? tools/deskrawl_gui/core/memory_reader.py
?? tools/deskrawl_gui/memdump.py
?? tools/scripts/mem_probe.py
?? "启动GUI.bat"
```

> 说明：与任务书「GUI v1 遗留改动已入库（b7e0039）、selftest.py 与 equipment_editor.py 工作区干净」一致
> （两者本次不在 git status 中 = 已提交）。根目录 BLOCKED.md/PROGRESS.md 的删除为他人未提交改动，按禁碰处理。
> 本张书白名单改动只允许落在 `tools/deskrawl_gui/{core 点名文件,app.py,selftest.py,memdump.py,fixtures/,widgets 点名文件}` 与 `docs/plan/`。

### 五条命令实测结果（2026-10-08 00:5x）

1. `python -m deskrawl_calc.cli selftest` → **8 PASS / 0 FAIL** ✅
2. `python -m deskrawl_gui --selftest` → **14/14 全部通过** ✅
3. `python -m deskrawl_gui --smoke` → widget 456，**EXITCODE=0** ✅（菜单=['文件','工具','存档']，存档禁用占位=True）
4. `python -m deskrawl_gui.memdump --json` → 退出码 0、可解析；mode=beta、装备 12 槽、仓库 115、背包 0；
   已**原样存入** `tools/deskrawl_gui/fixtures/snapshot_beta.json`（22020 字节；meta.time=2026-10-08 00:52:57；PID=28336）
5. 游戏进程存在（PID 28336）；GameAssembly.dll SHA-256 前缀 `25067EBA0B1B294C`（与任务书基线一致）

### 理解（目标/顺序/最大风险，≤10 行）

1. 目标：GUI 一键把活体快照映射成 CharacterProfile（β 逐件 / α 聚合），装配链 Final ≡ 内存 nsq（误差 0），
   六类错误态中文报错不崩溃，并加指纹等 P2 健壮化。
2. 顺序：任务 1 先做（GUI 只是壳，映射错全错）→ 任务 2 GUI → 任务 3 健壮化 → 两处反向验证（红→绿）→ 全量回归。
3. 最大风险：**nsq 含快照外来源**（天赋/巅峰/强化/传奇特效）——逐键对拍必须区分「可完全派生键位」与「残差键位」，
   残差并入 base 保面板闭环；自检必须保留**不依赖 nsq 的装备派生对拍**，作为反向验证「真会响」的抓手。
4. 次风险：浮点顺序——base 残差必须按内核同序（assembled → weapon）反解，否则链式复算非逐位相等；
   已实测：33/33 键逐位相等（用内核 StatSheet 同序复算，0 失配）。
5. 边界：只读两 API（OpenProcess 0x0410 + ReadProcessMemory）；不新增依赖/流程；老 14 项自检一名不动、断言不松。

### 任务 1 设计决策（先落纸，防实现漂移）

**映射（β）**：武器槽 → `weapon_current`（词条原样三元组；`base_damage=0`——游戏白字伤害在 WeaponDamage(20)
词条里，避免与 `final(20)` 双计；`base_speed=nsq[21]`——武器速度面板值）；孔位宝石 → `assembled`
（GemData 静态加成与游戏实测三键逐位一致：物理伤害% +0.95 / 生命% +0.24 / 物理减伤 +0.17）；其余装备词条
与全部残差并入 `base`。**α**：`base = nsq 全量`，无装备/武器。

**残差实证（本夹具逐键核定）**：
- 可完全派生键位 21 个（装备词条 + 宝石静态加成恰好等于 nsq，无残差）：
  `0,4,11,13,14,15,16,17,22,23,29,31,36,38,40,42,44,51,52,53,65`
- 残差键位 12 个：`3(+2.35) 5(+0.0886) 6(+0.008) 7(+34.8) 8(+68.95) 9(+25.9) 12(+4.65) 20(+14.15)
  21(+0.113) 32(+0.3027) 45(+0.7777) 57(+0.15)`。其中 3/5/6/7/8/9/12/20 与「已强化装备的**部分**词条 ×5%
  （武器速度 ×10%）」的形态逐位吻合（如 20: 283×0.05=14.15、21: 1.13×0.1=0.113、8: (774+605)×0.05=68.95）；
  32/45/57 未能定因（天赋/传奇特效/强化公式未在快照内）——**非阻塞**，已记 BLOCKED-P1P2.md。
  快照内其余字典池（nsu/nsv/ntc/nte）与残差无对应（已逐键比对），「用字典池找平」不成立，改用「残差并入 base」。

---

## 任务 1 · from_snapshot + 夹具（✅ 完成）

- 交付：`core/profile.py` 新增 `from_snapshot(payload, gd)` 与字段 `import_mode/import_time`（存档往返保留语义；
  widget 侧据此做 α 降级）。
- 夹具：`fixtures/snapshot_beta.json`（memdump --json 原样，22020 字节）+ `fixtures/snapshot_alpha.json`
  （β 夹具去 equipment、meta.mode=alpha 的变体）。
- β 实测（夹具）：装配链 **33/33 键逐位 ≡ nsq**；武器 7 条词条原样进 `weapon_current`（base_speed=1.2430）；
  宝石 7 颗进 `assembled`（静态 GemData 加成与面板三键逐位一致）。
- selftest 新增 3 项（headless 跑夹具）：`β 夹具 装配链 Final ≡ nsq（逐键误差 0）`、
  `β 夹具 武器词条逐条一致`、`β 夹具 装备派生对拍（独立复算，不读 nsq）`。

### 反向验证①（红→绿，必做项）

1. **红**：把夹具 `player.base["0"]`（力量）377 → 378 → `--selftest`：
   `[FAIL] β 夹具 装备派生对拍…可完全派生 21 键逐位相等=False`，**退出码 1（18/19）**。
2. **绿**：用字节级备份还原（还原后 sha256=`8b1ad07935494791cc485994c684bf37f53aca6b17c5073725174f5ead29323f`）
   → **19/19、退出码 0**。
3. 说明（如实）：装配链检查属「无损闭环」性质（base 吸收残差），对夹具改值天然免疫；真正会响的是
   派生对拍——这正是保留它、并把「可完全派生键位」冻结成夹具级常量的原因（防自检空转）。

## 任务 2 · GUI 集成（✅ 完成）

- 菜单：删除「存档」禁用占位 → 新增「数据导入」→「从运行中的游戏导入（只读）…」（app.py）。
- 流程：导入前探活（find_process）→ 主线程同步 + WaitCursor（**实测 0.342s**，未引入线程/异步）→
  节流 ≥1s（实测连点第二次被拦「导入过于频繁」）→ 成功走 `profile.from_snapshot()` → reload/刷新链 →
  状态栏**常驻**「快照：2026-10-08 01:18:27（β 逐件）」→ 结果对话框（时间/模式/件数/告警）。
- 六类错误态：`MemoryImportError.code`（no_process/no_hero/denied/py32/fingerprint/回落到 data）→
  `describe_import_error()` 中文弹窗；selftest 新增 `错误映射 6 场景（假异常 → 中文文案）` 全 PASS。
- α 降级：equipment_editor 顶部横幅 +「当前武器」编辑器禁用（对比语义=基线 vs 基线+候选词条）；
  候选排序视图 hint 与**行级「（近似）」标注**（selftest α 项实测 行标注=True/提示=True/禁用=True）。
- smoke 菜单断言已同步新结构：菜单=['文件','工具','数据导入']、导入项可用性一致=True、退出码 0。

## 任务 3 · P2 健壮化（✅ 完成）

- `memory_offsets.json` 写入指纹：GameAssembly.dll sha256 `25067eba0b1b294c…`（前缀与任务书一致）、
  global-metadata.dat sha256 `c1bebda9…`、so_dump/ItemData.json **338 条**；游戏目录可由 `DESKRAWL_GAME` 覆盖。
- 导入时校验（memdump 与 GUI 同一链路）：失配即拒绝——`kind='version'` → memdump 退出码 2、GUI 中文弹窗；
  启动时 `MainWindow` 即校验一次并设置菜单可用性（失配时菜单文案含「版本指纹不符，已禁用」+ tooltip 原因）。
- 新文件 `core/memory_snapshot.py`（80 有效行，自 memory_import 拆出偏移表加载/SnapshotResult/指纹与版本校验）；
  `memory_import.py` 463 → **393 有效行**，满足「要加代码先拆」的行数纪律。

### 反向验证②（红→绿，必做项）

1. **红**：offsets 里 GameAssembly sha256 首位 `2`→`3` → memdump：
   `[失败] 版本指纹不符：GameAssembly.dll 指纹不符（游戏已更新？）。请重新导出 schema/so_dump…`
   **退出码 2**；GUI：启动自检 problems=1、菜单禁用；强行放开后再导入同样被拒（中文弹窗）并重新禁用。
2. **绿**：还原备份 → memdump **退出码 0**、JSON 可解析（mode=beta、装备 12、仓库 115）；GUI 菜单恢复可用。

## 回归（2026-10-08 01:2x，全部实测）

| 项 | 结果 |
|---|---|
| 内核 `deskrawl_calc.cli selftest` | 8 PASS / 0 FAIL（退出码 0） |
| GUI `--selftest` | **19/19 全部通过**（老 14 项原样、名称未改；新增 5 项） |
| GUI `--smoke` | 退出码 0（widget 458；菜单断言新结构） |
| `memdump --json` | 退出码 0（活体 PID 28336：mode=beta、装备 12、仓库 115、背包 0） |
| 活体端到端（GUI 导入流程脚本实测） | 导入 0.342s；profile=ExampleHeroB·内存导入/mode=beta/宝石 7/词条 7；属性表 33 行；**活体 33 键闭环 0 失配** |
| 只读审计 | 全局 grep 无 `WriteProcessMemory/CreateRemoteThread/SuspendThread/…` 调用（唯一命中为 memory_reader 文档中的禁止声明） |
| 行数（有效行） | profile 210 / memory_snapshot 80 / memory_import 393 / memory_reader 223 / app 207 / selftest 401 / memdump 79 / equipment_editor 191 / candidate_rank_view 134（全部 <800） |
| git 基线对比 | 改动只落白名单（M：app.py、core/profile.py、selftest.py、widgets 两个点名文件；??：core 新文件、fixtures/、docs/plan/） |

> `data/builds/demo-hunter.json` 曾被既有往返检查写脏；已按 HEAD 逐字节还原（`git diff` 为空、状态干净），
> 并把该检查的落盘位置改为系统临时目录——守住 data/ 只读边界，断言与检查名未动。
> （诊断期间仅执行只读 git 查询 `git show`/`git diff`；另执行过一次 `git update-index --refresh`
> 仅为刷新 stat 缓存，未改动任何内容、索引条目或历史，status 输出不变。）

## 请领导操作（城镇态实机验收步骤，1 步）

1. 游戏内把角色切到**城镇场景**（停留在城镇 UI，不要在战斗中）。
2. GUI 菜单「数据导入」→「从运行中的游戏导入（只读）…」→ 应弹「导入成功」：
   快照时间 / 模式=β 逐件 / 装备·仓库·背包件数 / 告警条数；状态栏右下出现常驻「快照：…（β 逐件）」。
3. 抽查：左 dock 等级=70；「属性明细」的数值应为游戏面板口径（武器词条在「装备对比」页可见）。
   若失败：会收到中文报错弹窗（写明原因），属可复现证据，请截图回传。

---

# 【续修 · 2026-10-08 上午】属性明细 ↔ 游戏面板口径对齐（用户实机反馈）

## 问题（用户截图对照）
属性明细与游戏「属性」页对不上：力量 377 vs 451、护甲 4,363 vs 12,529、最大生命 2,512 vs 5,592、
暴击 34% vs 49%、暴伤 275% vs 505%、物伤 212% vs 287%、火冰电毒奥五行缺失（游戏 75%）。左 dock 与计算链无异常。

## 根因（反汇编定案，全部活体实证；RVA 均可复现）
属性明细当时显示 nsq（内存聚合字典）**减武器词条**——而游戏属性页显示的是 `Player.bjd(StatType)@0x4F5E10`
的复合结果。nsq 本身已含装备/宝石/强化/nwo（此前逐键闭环），面板在其上还有分层：

1. **基础字段层**（`Char.bje@0x67FDE0` / `Player.bje@0x4F64F0` 逐分支）：BaseMaxHealth→生命、
   BaseCritChance→暴击、**BaseCritDamage(实测 1.5)→暴伤**、BaseDamage→伤害、BaseMoveSpeed/AttackSpeed/
   Dodge/Mana/LifeOnHit/LifeOnKill/CDR→对应属性；BasePrimaryStat 归到主属性（`fak@0x4F3760` 链：
   GameManager+0x38→HeroData+0x2C，实测 0=力量，与面板 451=377+50+14+10 吻合）。
2. **平坦字典层**：nsq+nsu+ntc+nte+nsr 求和（nsu 实测 {力量+50, 暴击+0.1, 暴伤+0.8, 对易伤+0.8, 金币+0.4}）。
3. **百分比加算层**：nsv+ntd（实测 nsv={护甲:+0.40}）→ 护甲最终 ×1.4（12528.79→12,529 实证）。
4. **特殊%区**：生命/护甲/魔抗/移速再 ×(1+对应%属性)（bjd 尾部 cmp esi,7/8/9/10 → 42/44/59/57 分支）；
   生命 (2511.8+1204)×1.505=5592.28→5,592 实证。
5. **far**（`Player.far@0x4F6620`）：护甲 += bjd(力量)、魔抗 += bjd(智力)（魔抗 2659.9+0→2,660 实证）。
6. **条件表**（`Player.fat@0x4F6720`，求值 `fgp@0x506060`）：nuf@0x358 / nug@0x360（ValueTuple 内联 0x20 步长）；
   None(-1) 恒真、**Healthy=血比例>0.8**、Injured<0.3；实测 nuf 含 物理+5元素各 +0.75（满血生效 → 287% 与 75%×5）
   与 移速%+0.5（带技能门控）。血比例 = 当前血[lss@0x118]/面板生命。
7. **状态增益层**（`StatusEffectController.bgh@0x4D5E10`）：g3×(v+g1)×(1+g2)，三字典（+0x38/0x40/0x48）实测为空。
8. **封顶**（`Char.bjc@0x67FC80` 尾跳 0x4A9C30）：4/13/22/37 封顶 0.85。

**附带定因**：此前 BLOCKED 的「残差 32/45/57」之谜关闭——它们不是残差，而是 `Player.nwo`（List<StatModifier>@0x518）
运行时词条（实测 对精英+0.225、对流+0.7、移速+0.15），叠加装备强化 ×5%/×10% 后与 nsq 逐位相等。

## 实现（白名单内）
- `memory_offsets.json`：基础字段全量、CurrentHealth(0x118)、conditional_mods、status_controller、hero_data；
  语义注释更正（旧注释「nsu/nsv 与面板无加和关系」被本次反汇编证伪，已改写）。
- `memory_import.py`：read_pass 增 fields/conditionals/status_mods/primary_stat（含类名/值域自校验），
  validate 增 4 段校验；导入成功对话框新增「属性明细：游戏面板口径…」与面板复算说明行。
- `calc_service.build_panel`：按上述 1–8 全量复算 + 面板行序（游戏「属性」页 23 行打头）与显示格式
  （千分位 / 百分比去尾零 / 攻速一位小数）。
- `stat_table.set_panel_view` + `app._refresh_all` + `profile.panel`：导入的构建显示面板口径（导入时冻结，
  hint 注明「编辑左侧面板不改变本表」）；手工构建退回计算口径；α 同口径（复算只依赖字典/基础字段/条件表）。
- 夹具再生：`fixtures/snapshot_beta.json` / `snapshot_alpha.json`（2026-10-08 09:21 活体，新格式含上述字段）。

## 验证（2026-10-08 上午，全部实测）
- **活体端到端**（生产链路 import_snapshot→build_panel）：**23/23 行显示文本与游戏截图逐字一致**
  （451 / 94 / 1.7 / 35.7% / 49% / 505% / 287% / 75%×5 / 256.8% / 119.2% / 233.3% / 185.8% / 233.3% /
  54.3% / 5,592 / 50.5% / 12,529 / 85.9% / 2,660）。
- **GUI 实机**（驱动 `MainWindow._import_from_game` 生产路径，弹窗捕获）：表格抽查 12 项全对；
  弹窗/hint/左 dock/装备对比均正常；分解列可读（护甲 [4813.95,0,0.4,1.859,12,529]）。
- **GUI --selftest：24/24**（原 19 项一项未少、名称未改；新增 5 项：23 行锚点、条件表落位、反向敏感、
  α 一致性、手工构建门禁）。
- **反向验证③（红→绿）**：夹具 nuf 物伤 +0.75→0.0（单字段）→ 自检 **24/24→20/24**
  （4 项面板检查变红，实测锚点失配 `[(23,'212%','287%')]`）→ 还原（sha256 一致）→ **24/24 回绿**。
- **GUI --smoke**：退出码 0（widget 458，与续修前一致）。

## 已知边界（透明记录，已写入面板复算说明）
- 敌情类条件（2 附近无敌 / 3 脱战 / 4 单敌交战 / 5 被包围）无法从单次快照静态判定 → 不计入并在弹窗列出；
  本构建实测仅影响 nug「单敌交战」+0.35 攻速条目（城镇中本就未生效，与面板一致）。
- 带技能/状态门控的条目（实测 nuf 移速%+0.5）跳过并列出。
- 面板口径按导入时点冻结（含血比例条件）；此后游戏内状态变化不影响该表，重新导入即刷新。

## 2026-10-08 下午：强化口径修复 + 背包/仓库候选武器（第三轮反馈）

### 反馈与结论
1. 「当前武器属性显示的是强化前数值」→ 已修复：weapon_current 词条按强化模型折算为
   强化后口径（=游戏 tooltip 数字）；[20]武器伤害/[21]武器速度用 nsq 单源精确值覆写
   （仅武器持有这两键，逐位=面板），其余词条按模型折算，残差反解吸收原值差，33 键闭环
   仍逐位相等（selftest 实证）。
2. 「没有显示宝石信息」→ 已修复：WeaponDraft 增加 upgrade_level/gems 元数据（JSON 往返
   保留），武器卡片新增只读元信息行「强化 +N（…）；镶嵌宝石：…」，无内容时隐藏。
3. 「仓库/背包未装备武器能否自动进候选」→ 可行并已实现：uid2gid（gi.myk）本来就收录全部
   生成物（探针实测仓库 115 件可读）；_read_slots 扩展 equip_slot_type，武器且 UID 命中
   实例表时附全量实例数据；from_snapshot 冻结为 profile.bag_weapons；装备对比页候选侧
   新增「从背包/仓库导入」下拉，选择即整把载入（可再手工微调）。α 降级时无实例数据，
   bag_weapons 为空（真实 α 中 equip_slot_type 仍可读，仅词条不可得）。

### 强化缩放模型（本轮逆向主产出，apply_upgrade / offsets 注释同源）
- 与活体 nsq 逐位对拍实证：+1 护甲三件（靴/手套/腰带，15 词条）→ 仅 modifiers 数组前
  2 条 ×1.05，其余原值；+4 武器（7 词条）→ 全部 ×1.05（2L=8≥7）。
- WeaponDamage(20) ×(1+0.0125L)、WeaponSpeed(21) ×(1+0.025L)（+4 → ×1.05/×1.10 逐位
  闭合；21 号走「前 2L」应为 ×1.05，实测 ×1.10 → 单列成键）。
- 反汇编定位：EquipmentTooltipUI.hof/hog（tooltip 侧「[+N]」括号 = 强化后-强化前），
  核心缩放函数未逐指令定案，模型以数值对拍钉死（证据链充分：22 词条 0 例外）。
- 边界：L∈{2,3} 与「前 2L」在词条数>8 时无实证，按现有证据外推（BLOCKED 记录）；
  当前武器的 20/21 不依赖外推（nsq 覆写）。

### Q3「力量词条改动 DPS 不变」——属游戏公式本征行为，非 bug
- 面板复算（bjd 反汇编）已实证：力量→护甲、智力→魔抗（far 依赖），伤害乘区 A-D 均不含
  主属性。故改主属性词条 DPS 恒不变（改护甲/生命可见）。已在词条数值框加 tooltip 说明
  （_TIP_PRIMARY_STAT），用户改完不再疑惑。

### 自检与回归
- GUI --selftest：**27/27**（新增 3 项：强化后口径+宝石元数据、bag_weapons、候选下拉
  载入+元信息行显隐；武器卡片元信息行并入 UI 检查）。
- 夹具重导：snapshot_beta.json 从活体游戏重新导出（双读通过，仓库 115/装备 12/候选
  武器 2 把）；snapshot_alpha.json = β 去 equipment + 剥离实例字段（保留 equip_slot_type，
  与真实 α 读取态同构）。
- UI 检查注意：selftest 中 QWidget 构造前必须先建 QApplication（实测否则 0xC0000409
  静默崩），已在 _snapshot_checks 顶部就位。
- --smoke 退出码 0。

---

# 【第四轮 · 2026-10-09】主属性伤害加成修正（用户实机反馈：游戏内说明「力量会提升伤害」）

## 反馈与定案
- 用户上传游戏内**力量**词条说明截图：「提升力量系职业的伤害。当前提升 **451%** 伤害。
  同时提供 **451** 点护甲。」——直接推翻上一轮 Q3 结论（「主属性不进伤害乘区」）。
- **反汇编复核（本轮逐指令重读）**：
  - `Player.bjr@0x509D80` = `trunc((BaseDamage + scaling × (trunc(Final(20)) + Final(3))) × (1 + Final(主属性)/100))`；
    常量 `1.0`@0x18362A270、`100.0`@0x18362A370 在 PE 中实测读出（1.0 / 100.0）。
  - `Player.fak@0x4F3760` = `GameManager+0x38([+0xB8] 单例链) → HeroData+0x2C`——返回**英雄职业主属性**
    （Barbarian=0=力量）；文档 04/08 旧注「按武器选择」为误记，已更正。
  - tooltip 的「当前提升 451%」= Final(力量)=451 代入本式（×5.51）——451/451% 逐位自洽。
- **上一轮为何漏判**：只核对了乘区 A–D（bkn/bko/暴击/易伤）是否含主属性，而主属性乘子位于
  bjr 的**攻击伤害合成**内（与武器伤害/Damage(3) 同一步），不属任何「乘区」。属分析口径遗漏，非游戏行为。

## 实现（既有文件内，未新增模块）
- `deskrawl_calc/engine.py`：`DamageModel` 新增 `primary_stat`（None=不启用）与
  `primary_stat_multiplier()`；`attack_damage()` = (武器伤害 + Final(20) + **Final(3)**) × (1+Final(主属性)/100)。
  连带修复：此前**通用增伤(3) 从未进入 DPS**（武器/角色的 +Damage 词条对 DPS 完全不可见；
  夹具武器实测带 [3]=+49.35 词条）。
- `core/profile.py`：新增 `primary_stat` 字段（JSON 往返）；`from_snapshot` 取 `player.primary_stat`，
  并新增 `_align_primary_stat`（α/β 两路径）把该键位 base **对准面板口径**——面板值
  451 = nsq 377 + nsu 50 + nte 14 + BasePrimaryStat 10；对齐后 DPS 因子与游戏 tooltip 逐位一致，
  编辑仍按游戏本征斜率 +1%/点（对齐在导入时冻结，与属性明细面板口径同一约定）。
- `core/calc_service.py`：`compare` / `_dps_with` 传入 `primary_stat`（排序基线与候选增量同源）。
- GUI：左栏「职业主属性」下拉（未设置/力量/敏捷/智力，写回 profile）；词条数值框 tooltip 纠错
  （旧文案「改动主属性词条不会改变 DPS」已删）；对比页新增「攻击伤害主属性加成 力量 ×5.530」；
  导入成功弹窗新增主属性行（含 ×因子与「当前提升 N% 伤害」）。

## 验证（2026-10-09，全部实测）
- **活体端到端**（00:23:44 快照，PID 9868，β）：主属性=力量；面板行 453 → sheet.final=453.0000
  → 因子 **×5.530000** = 游戏 tooltip「当前提升 453% 伤害」；攻击伤害 (297.15+94.35)×5.53=2165.0
  （游戏截断式 2164，差 0.05% 见边界）。
- **夹具数值**：β base[0] 对齐到 451（`_align_primary_stat`）；因子 ×5.5100；武器 [3] 词条 49.35
  去除 → 当前 DPS 92009→80411（**-12.61%**，此前该词条 0 影响）；候选 +100 力量 → 候选 DPS
  7043.6→8321.9；α 同样对齐 451；构建 JSON 往返含 primary_stat（dict 等值）。
- **GUI --selftest：29/29**（原 27 项名称未改；β 装配链闭环检查改为「主属性键=面板 451、
  其余逐键 ≡ nsq」33 键 0 失配；新增 2 项：因子 ×5.510、力量 +100 → DPS 比值 1.181488（期望同值））。
- **内核自检：10 PASS**（新增 bjr 主属性断言：力量 451 → ×5.51；未设 → ×1.0）；demo 锚点
  197.9479 / 226.3011 / +14.3236% **未变**（手工构建默认 primary=None，不受影响）。
- **GUI --smoke**：退出码 0；widget 555（左栏新增下拉 +9）；交互检查 10/10（新增「职业主属性
  下拉写回 profile」）。

## 本轮已知边界（已同步 BLOCKED）
- 计算口径 DPS 的**非主属性键位**仍为 nsq 原始聚合（面板复合层不入计算链）——如活体暴击率
  计算口径 0.246 vs 面板 ~0.30；DPS 绝对值与游戏仍有系统偏差。本次只把「伤害公式里的主属性」
  按键位对准面板（= 用户反馈所指的乘子）。
- 未复刻 `trunc(Final(20))`（bjr 逐指令为截断）：浮点口径差 ≤0.05%（活体 2165.0 vs 2164），
  对武器对比结论无影响。
