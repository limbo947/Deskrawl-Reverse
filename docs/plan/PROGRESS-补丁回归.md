# PROGRESS · 补丁后地址重锚定与回归固化

> 任务书：`补丁后地址重锚定与回归固化计划.md`（2026-10-10）。阻塞记录：`BLOCKED-补丁回归.md`（本任务无阻塞，未创建）。
> 体例沿用 `PROGRESS-P1P2.md`：每完成一项立即留实测输出，中断续跑以本文件为准。

## 交付确认

- [x] 任务① RVA 体检：`tools/scripts/rva_audit.py` 一条命令列出/分类/重算全仓地址 + `--check` + `--falsify`
- [x] 任务① 复核后写回：46 处陈旧地址注释全部更新（脚本只报告，写回由人工复核后单独执行）
- [x] 任务② 语义别名表：`data/schema/aliases.json`（37 条）+ `build_aliases.py --check` 通过
- [x] 任务③ 文档置信度：`文档置信度待核清单.md`，N = 16 = 已核 11 + 暂缓 5
- [x] 任务④ 补丁回归五步清单 `补丁回归清单.md` + `patch_regression.py` + 四处反向验证（红→绿）
- [x] 总验收：内核 10 PASS / GUI 32-32 / 两个 `--check` 退出码 0 / 实机 memdump 退出码 0

---

## 任务 0 · 基线核对与改动白名单（2026-10-10）

解释器：`.venv-gui\Scripts\python.exe`（GUI 侧）或系统 `python`（内核侧）；工作目录 `tools` 或 `tools\scripts`。
游戏：`Deskrawl.exe` **PID=12620**（运行中，实机验收可做）。

### 基线命令实测

| # | 命令 | 任务书预期 | **实测** | 判定 |
|---|---|---|---|---|
| 1 | `python -m deskrawl_calc.cli selftest` | 8 PASS / 0 FAIL | **10 PASS / 0 FAIL**，EXIT=0 | ⚠️ 任务书数字过期 |
| 2 | `..\.venv-gui\Scripts\python.exe -m deskrawl_gui --selftest` | 14/14 | **32/32 全部通过**，EXIT=0 | ⚠️ 任务书数字过期 |
| 3 | `..\.venv-gui\Scripts\python.exe -m deskrawl_gui.memdump` | 退出码 0 | **EXIT=0**；`[指纹] dicts=2bb88f501b552794 uids=dc78a95d77ff98cc`；`[校验] PASS：结构/键域/值域/双读一致性全部通过` | ✅ |
| 4 | REA broker：读 `%TEMP%\rea-broker\status.json` | 毫秒级返回 | `{"state":"ready","lastSeq":32}` | ✅（**全程未重启 broker**） |

**偏差裁决**：第 1、2 条数字与任务书不符，系任务书写于更早状态、其后自检项已扩充（内核 8→10、GUI 14→32），
非本次回归。本任务以实测值为基线。

### 任务书「现状实测」表的偏差（重要）

任务书 §3.1 用 `0x[0-9A-Fa-f]{5,6}` 扫描，该模式**漏掉 7–9 位 VA**（`0x18362A350`、`0x1839E44C8`…），
故其「15 个文件命中」不完整。本任务改用可配置宽度（默认 4–10 位）实测命中 **25 个文件 / 122 条**——
这不是新增失效项，而是原先根本没被扫描到。

### git status 基线

开工前已有大量他人未提交改动（`data/schema/*` 已换新构建、`tools/deskrawl_gui/*` 内存链、`docs/plan/` 整体未跟踪）。
本任务实际改动见文末「改动清单」，全部落在计划允许的范围内。

## 理解（目标/顺序/最大风险）

1. 目标：把「补丁后重锚定」变成可重复、可自检、失败会吭声的流程。
2. 顺序：① 扫描器 + dump 索引 → ② 别名表（复用索引）→ ③ 文档置信度 → ④ 串成清单。
3. 最大风险：误报（把掩码当失效地址）与**误判为有效**（把撞名的类当成同一个类，比找不到更危险）。
4. 对策：白名单须写明「为什么不是地址」；类名必须通过「类形状自证」；每个门禁都做反证演练。
5. 边界：只读（不改游戏目录、不写目标进程）；源码写回限定注释层。

---

## 任务① · RVA 体检与自动重算

### 新增的公共基座（① ② 共用，避免两份实现漂移）

| 文件 | 有效行 | 职责 |
|---|---|---|
| `tools/scripts/dump_index.py` | 171 | `dump.cs` 方法与字段索引；归一化签名（抹掉混淆名）；类形状指纹 |
| `tools/scripts/pe_file.py` | 66 | PE 只读：节表、VA↔文件偏移、位模式搜索 |
| `tools/scripts/script_index.py` | 71 | `script.json` 流式索引：字符串字面量/元数据条目「地址↔语义」双向表 |
| `tools/scripts/rva_audit.py` | 693 | 扫描 → 分类 → 判定 → 报告 + `--check` + `--falsify`（**接近 700 行阈值，下次加逻辑应先拆出证据复核段**） |

### 判定链（先到先得）

```
白名单/自动非地址规则 → 当期 dump 方法起始 → 旧构建同名方法（签名+Slot → 类形状 → 跨类唯一）
→ 嵌套类重锚定 → docs/08 §12.2 常量表（字节校验）→ 旧 script.json 字面量对搬
→ 旧构建「含该地址的方法」（内联数据）→ 人工确认
消歧三级：同签名组按序 → 类内区间 → 整类位移（证据列写明用了哪一级）
```

### 关键发现（过程中修掉的三个坑，都已写进回归清单）

1. **类名撞车**：新构建里存在同名类 `iw`，但签名交集 0/5 —— 真身是 `je`（`gg`→`gh`、`gi`→`gj` 同理）。
   加「类形状自证（交集 ≥60%）」守卫后，`extract_rolltable.py` 与 `make_doc09.py` 的重算值才正确
   （守卫前 `iw.esm` 被错误重锚定到当期 `iw` 类）。
2. **签名+Slot 也不唯一**：`Player.fat`、`ObscuredLong.kas`、`it.esc/esd` 各有两个同签名候选；
   三级消歧后唯一化，其中 4 条依据较弱，已在别名表里显式标注。
3. **多类共享同一 RVA**：`0x452340` 同时是 `ObscuredLong.kas` 与 `ObscuredDateTime.jtj`；注释里的名字是唯一线索。

### 结果（`python rva_audit.py --check --falsify`，退出码 0）

```
扫描 25 个文件 / 122 条地址字面量
    29  非地址（白名单/自动规则）
    56  仍有效（方法）
     1  仍有效（数据地址）
     7  历史对照（有意保留的旧地址）
    29  弃用探针（理由已写入文档）
✓ 无「已失效/待确认」条目
```

写回前为：44 条已失效（含重算值）+ 2 条内联数据 + 4 条历史对照 —— 全部处理完毕。

### 写回明细（人工复核后逐文件小步执行，仅动注释）

| 文件 | 处数 | 形式 |
|---|---|---|
| `tools/deskrawl_calc/cli.py` / `engine.py` / `stattype.py` | 7 | 语义名@当期地址（`Player.CalcDamage@0x50E400` 等） |
| `tools/deskrawl_gui/core/{calc_service,memory_import,memory_reader,profile}.py` | 8 | 同上（含 ACTk 解码四处） |
| `tools/deskrawl_gui/{app.py,selftest.py,widgets/item_editor.py,widgets/panel_editor.py}` | 5 | 同上 |
| `tools/scripts/mem_probe.py` | 3 | 同上 |
| `tools/scripts/make_doc09.py` | 13 | 存档链 RVA 表 → 语义名 + 当期地址 |
| `tools/scripts/extract_rolltable.py` | 3 | `START/END` 新址 + `_source` 语义名 |
| 内联数据两处（`stattype.py`） | 2 | 改为「跳转表在 `Character.ApplyDamage@0x67E320` 内」——**不写假地址** |
| 常量旧址（`engine.py`） | 1 | 新址 + 保留旧址作对照（触发「历史对照」分类） |

命名约定（已写进回归清单）：**代码注释引用语义名**（`aliases.json` 的键）+ 当期地址；
紧邻「旧/补丁前」标注的地址视为**刻意保留的对照记录**，不重写。

### 可证伪演示（`--falsify`，报告 §7）

| 用例 | 期望 | 实测 | 结论 |
|---|---|---|---|
| `0x18067BD01`（真实有效的 `Character.bkn` 末位 +1） | 判红 | `stale_inline` | ✅ |
| `0x18050E401`（`Player.bkn` 覆写 +1） | 判红 | `stale_inline` | ✅ |
| `0x7B6671`（SaveSystem 锚点 +1，RVA 形式） | 判红 | `stale_inline` | ✅ |
| `0x18363F021`（常量 0.85 新址 +1） | 判红 | `unknown` | ✅ |
| `0x18067BD00`（真值对照） | 判绿 | `valid` | ✅ |

### 附带产出：文档侧缺口量化（`--docs`，默认不扫、不进默认门禁）

```
python rva_audit.py --docs   → 37 个文件 / 525 条字面量
   126 仍有效 · 20 数据地址仍有效 · 88 非地址 · 160 已失效(含重算值) · 12 内联 · 2 数据迁移 · 78 无法判定
```

报告：`docs/plan/RVA体检报告-文档.md`；JSON：`data/schema/rva_audit_docs.json`。
**252 条待处理**已作为工单交给任务③清单（条目 ③-8）。

---

## 任务② · 语义别名表

`data/schema/aliases.json`：**37 条**，覆盖伤害链（Character/Player 各槽位）、面板口径、ACTk 四个解码器、
存档读写与加解密链、词条 Roll 表。每条含 `说明 / slot / signature / 锚定依据 / current{klass,name,rva,va} / history[]`。

`python build_aliases.py --check` → 退出码 0：

```
别名 37 条：核对 37 条，问题 0 条
  ! 4 条靠「组内序位」消歧（签名+Slot 不足以唯一，依据较弱）：Player.ConditionalModValue,
    Actk.ObscuredLong.Decrypt, SaveCrypto.FileKey, SaveCrypto.MacKey
```

- `--check` **真读当期 `dump.cs`** 逐条比对（类 + 归一化签名 + Slot），并回验 `history` 是否存在于旧构建；
- 别名条目**只增不减**：`--write` 只刷新 `current` 并把上一版压入 `history`；
- 4 条弱依据（`current.ordinal`）在输出里单独列出，不混同强依据。

---

## 任务③ · 文档置信度

产出：`docs/plan/文档置信度待核清单.md`。**N = 16 = 已核 11 + 暂缓 5**。

**与任务书前提不符的事实（已记录）**：文档正文**已无 `🔶` 在用条目**（全量扫描只命中 3 处图例本身），
历史 🔶 在更早工作里已升级。故清单范围扩到 `⚠️` 与「很可能/推断」句——即任务书的真实意图。
`docs/00-索引.md` 图例已加注。

本轮**新增取证**：

| 条目 | 手段 | 结论 |
|---|---|---|
| `docs/04 §6.2.6` 坚韧度 UI 口径 | REA 反编译 `FUN_180567b20`（= `EquipmentUI.gdy`） | ⚠️→✅，含 `max(1,level)` 钳位与 `50.0` 常量原文 |
| `docs/06 8A.1` 两套 GameConfig | `dump.cs` 单类 + `so_dump` 两条实例字段 | ⚠️→✅ |
| `docs/07 8A.6` MaxStackSize 99 类别 | 338 条交叉统计 + `ItemType` 枚举 | **更正**：99 = Commodity 11 + Consumable 4（不含材料） |
| `docs/08 §12.3` / `docs/04 §6.2` 的 `fgl`→`fji` | 新旧 dump 签名比对 | **更正**：应为 `fgp(PlayerCondition,float)`；两处文档已同步 |
| `docs/08 §9.1` 的 `0x498340` 位置标注 | RVA 归属查询 | **更正**：非方法起始，是 `DamageEffect.tc`(→`tp`) 的内联段 |

暂缓 5 条（③-8 文档 64+ 旧 RVA、③-9 特殊强化、③-10 Back 特效、③-11 敌人 ObscuredLong、③-13 技能秒伤估算）
均在清单里写明**复核所需条件**，可直接当工单用。

---

## 任务④ · 补丁回归流程固化

产出：
- `docs/plan/补丁回归清单.md`：**五步**（0 归档旧构建 → 1 重导 schema → 2 RVA 重算 → 3 指纹 → 4 实机 → 5 文档与别名），
  每步含命令/判据/**本轮实测的常见坑**，并列出**弃用探针**（`read_const.py`、`chk.py`、`xref.py`、
  `meta_range.py`、`strings_ctx.py`、`obs_solve3.py`）及其承接者。
- `tools/scripts/patch_regression.py`（91 有效行）：串 ①–④（`--live` 追加实机、`--docs` 追加文档扫描），
  输出 `docs/plan/补丁回归报告.md`。

### 四处反向验证（原文，红→绿）

```
=== 验证1a 指纹改错一位 -> memdump 必须报指纹不符且退出码非 0 ===
[失败] 版本指纹不符：GameAssembly.dll 指纹不符（游戏已更新？）。请重新导出 schema/so_dump 并更新 memory_offsets.json 后重试
EXIT=2
=== 验证1b 恢复原值 -> memdump 必须退出码 0 ===
[指纹] dicts=2bb88f501b552794  uids=dc78a95d77ff98cc  （连跑两次应逐值相等）
[校验] PASS：结构/键域/值域/双读一致性全部通过
EXIT=0

=== 验证2a engine.py 常量新址末位 +1 -> rva_audit --check 必须非 0 ===
✗ 1 条已失效/待确认（明细见报告）：
    tools/deskrawl_calc/engine.py:149  0x18363F121  落在 .rdata 节（0x363f121），既非方法起始也非已知数据条目
EXIT=1
=== 验证2b 改回 -> 必须 0 ===
✓ 无「已失效/待确认」条目
EXIT=0

=== 验证3a aliases.json 当期 rva 改错 -> build_aliases --check 必须非 0 ===
别名 37 条：核对 37 条，问题 1 条
  ✗ Player.CalcDamage: 表内 bkn@0x50e401 ≠ 当期 bkn@0x50e400（补丁后需 `--write` 刷新）
EXIT=1
=== 验证3b 改回 -> 必须 0 ===
EXIT=0

=== 验证4a 文档里抹掉 chk.py 的弃用理由 -> rva_audit --check 必须非 0 ===
  ✗ deprecations: 1 项异常 -> {"file": "tools/scripts/chk.py", "ok": false,
     "note": "文档 docs/plan/补丁回归清单.md 中未出现标记 'chk.py'"}
EXIT=1
=== 验证4b 改回 -> 必须 0 ===
✓ 无「已失效/待确认」条目
EXIT=0
```

验证 4 专门针对「拿配置消灭红点」：弃用理由必须**真的写在文档里**，否则门禁照红。

### 一键回归实测

```
python patch_regression.py --live
[ok] ① 指纹核对（memory_offsets vs 磁盘）（0，0.2s）
[ok] ② RVA 体检（--check --falsify）（0，12.0s）
[ok] ③ 语义别名表（build_aliases --check）（0，5.6s）
[ok] ④a 内核自检（0，0.2s）
[ok] ④b GUI 自检（0，0.7s）
[ok] ⑤ 实机导入（memdump）（0，0.4s）
补丁判定：指纹一致
REG_EXIT=0
```

> 注：`--live` 的 memdump 与 GUI 自检在**同一进程树内串行执行**，输出尾部已贴进 `补丁回归报告.md`。

---

## 总验收（命令与退出码）

| 命令 | 退出码 | 结论 |
|---|---|---|
| `python -m deskrawl_calc.cli selftest` | 0 | 10 PASS / 0 FAIL |
| `..\.venv-gui\Scripts\python.exe -m deskrawl_gui --selftest` | 0 | 32/32 |
| `python rva_audit.py --check --falsify` | 0 | 无失效/待确认；5/5 证伪用例通过 |
| `python build_aliases.py --check` | 0 | 37 条全对（含 4 条弱依据提示） |
| `..\.venv-gui\Scripts\python.exe -m deskrawl_gui.memdump` | 0 | 指纹+双读校验通过 |
| `python patch_regression.py --live` | 0 | 五步全 ok |

---

## 改动清单（白名单核对）

**新增（仓库）**：`tools/scripts/{dump_index,script_index,pe_file,rva_audit,build_aliases,patch_regression}.py`、
`tools/scripts/rva_audit_config.json`、`data/schema/{aliases.json,rva_audit.json,rva_audit_docs.json}`、
`docs/plan/{RVA体检报告.md,RVA体检报告-文档.md,文档置信度待核清单.md,补丁回归清单.md,补丁回归报告.md,PROGRESS-补丁回归.md}`

**修改（注释/文档层）**：`tools/deskrawl_calc/{cli,engine,stattype}.py`、
`tools/deskrawl_gui/{app,selftest}.py`、`tools/deskrawl_gui/core/{calc_service,memory_import,memory_reader,profile}.py`、
`tools/deskrawl_gui/widgets/{item_editor,panel_editor}.py`、`tools/scripts/{mem_probe,make_doc09,extract_rolltable}.py`、
`docs/{00-索引,04-伤害计算与属性关联,06-实测数值-全局与成长曲线,07-实测数值-内容数据,08-常量设计要点与待办,09-存档解密与数据汇总报表}.md`

**未改**：游戏安装目录（只读约束）；`.codebuddy/`；既有逆向脚本的执行逻辑（只动注释/字符串常量）。

## 第二轮（同日）：遗留 1–4 处理 + 文档结构优化 + AGENTS.md

### 遗留 1 · 文档侧 252 条：从「只有数字」到「逐条有处置」

新增**文档分区机制**（都只对「本来会判失效」的地址生效，区块里的当期地址照常判有效）：

| 类别 | 机制 | 落点 |
|---|---|---|
| 机器产物 | `scan.exclude_globs: ["docs/reports/*"]` | 报告按设计就是地址陈列柜，扫它只会自噪声 |
| 历史证词（整篇） | `doc_policy.historical_docs`（每条写理由） | `docs/04`（补丁前反汇编证据）、`docs/plan/PROGRESS-P1P2.md`/`BLOCKED-P1P2.md`/`PROGRESS-补丁回归.md`/`内存导入P1-P2工程实施计划.md`/`联机角色数据内存导入可行性调研.md` |
| 证据区块（文档内标记） | `<!-- rva-audit:historical 理由 -->` … `<!-- /rva-audit:historical -->` | `docs/08` §9.1+§10、§11.2–§11.5、§12.1–§12.3 三块 |
| 当期指引必须写当期地址 | 就地重锚定 | `docs/09` 存档链 14 处、`docs/02` 2 处、`docs/03`/`docs/07` 各 1 处 |
| 偏移/尺寸/差值/数据指针 | `literal` / `data_refs` 登记（每条写理由） | `docs/08` §12.1 与 §12.2 的偏移列、§12.5 的 dumper 指针、`0x4A08`（差值）、`0x1000`（类位移量） |

```
python rva_audit.py --docs --check    # EXIT=0
扫描 39 个文件 / 414 条地址字面量
    62 非地址 · 137 仍有效（方法） · 13 仍有效（数据地址）
   173 历史对照（有意保留的旧地址） · 29 弃用探针 · 0 待处理
```

顺带修掉两个**误判**（都属「宁可红不出脏」的反面）：
1. `data_audit` 用 `==` 比 float32 常量，`1.1` 读回 `1.100000023841858` 被判失效 → 改容差比对（`read_const` 同修）；
2. `--docs` 把机器产物也扫进来，制造 65 条自我噪声 → 排除 `docs/reports/*`。

### 遗留 2 · `rva_audit.py` 拆分（棘轮回归）

零改动切片把「证据复核 + 报告渲染」搬到新文件 `rva_verify.py`：

| 文件 | 有效行 | 职责 |
|---|---|---|
| `rva_audit.py` | **499**（原 693） | 扫描 / 分类 / 消歧 / 门禁 / CLI |
| `rva_verify.py` | 254 | `verify_doc_sections`/`_doc_constants`/`_offsets`/`_fingerprints`/`_deprecations` + `render`（`labels`/`red_set` 由调用方注入，避免循环 import） |

搬迁后两个门禁与全量回归逐条复跑通过（行为等价的证据）。

### 遗留 3 · 4 条弱依据别名的 REA 复核

| 别名 | 结论 | 证据等级 |
|---|---|---|
| `Player.ConditionalModValue` | **`fdm` 实证**：`FUN_1804fac90` 访问 `Player +0x358/+0x360`（= `nuf`/`nug` 条件属性表），同签名兄弟 `fdn` 两个偏移都不访问 | 指令级 |
| `SaveCrypto.FileKey` / `MacKey` | 两函数体同为 `return Sha256(cached-string)`（仅缓存串字段差 8 字节）；内部分配由组内序位 + 类整体位移两规则一致给出 | 两规则一致 + 反编译证实形状 |
| `Actk.ObscuredLong.Decrypt` | **三重一致**：组序 + 类位移 −0x1000 + 同址条目序（`0x451340` 同时登记 `kfj`/`ObscuredDateTime.jxz`，与旧 `0x452340` 的 `[jtj, kas]` 同序）。REA 在该地址返回「No procedure exists」（dump 把它登记为共享泛型条目）→ 无指令级证据 | 多规则一致 |

证据等级已写进 `aliases.json` 每条（`证据等级`/`证据` 字段），`build_aliases.py --check` 的弱依据提示也随之带上等级，不再把「已被反编译证实」与「仅靠序位」混为一谈。

### 遗留 4 · 任务书过期数字更正

`补丁后地址重锚定与回归固化计划.md`：§2.3 基线改为 10 PASS / 32-32（附更正说明）；§3.1 补上「`{5,6}` 宽度漏掉 7–9 位 VA」的更正与实测命中数（25 文件 / 122 条）；§3.1 产出路径改指 `docs/reports/`。

### 文档结构优化（本轮顺带）

```
docs/
  00-索引.md … 09-*.md     参考文档（新增「目录结构」章节，说明谁写哪一层）
  plan/                    计划 / 调研 / 进度档 / 阻塞档 / 清单　（人的文档，当时状态的证词）
  reports/                 脚本产物：RVA体检报告.md、RVA体检报告-文档.md、补丁回归报告.md（勿手改）
```

同步更新的引用点：`rva_audit.py`（`REPORT`）、`patch_regression.py`（报告路径 ×2）、`docs/plan/补丁回归清单.md`（命令）、`文档置信度待核清单.md`、`PROGRESS-补丁回归.md`、`docs/00-索引.md`。

### AGENTS.md 更新

新增「地址体检与语义别名」命令段（含判定链与撞名教训）；修正过期数字（内核 8→10 项、GUI 14→32 项）；补上四基座（`dump_index`/`pe_file`/`script_index`/`rva_verify`）、`aliases.json`/`rva_audit*.json`、`docs/reports/`、以及「注释引用语义名、旧地址标注不手改」的约定与三条交工门禁。

### 第二轮总验收

| 命令 | 退出码 | 结论 |
|---|---|---|
| `python rva_audit.py --check --falsify` | 0 | 代码侧 0 待处理 |
| `python rva_audit.py --docs --check --falsify` | 0 | 文档侧 0 待处理（173 条历史对照已登记理由） |
| `python build_aliases.py --check` | 0 | 37 条全对，4 条弱依据带证据等级 |
| `python -m deskrawl_calc.cli selftest` | 0 | 10 PASS |
| `python -m deskrawl_gui --selftest` | 0 | 32/32 |
| `python -m deskrawl_gui.memdump` | 0 | 指纹 + 双读校验通过 |
| `python patch_regression.py --live --docs` | 0 | 六步全 ok |

顺带修掉 `patch_regression.py` 的一个**假绿**：指纹读取解析失败时原会显示「✅ 指纹一致」，现改为「❌ 无法读取」并计入失败——「读不出来」不等于「没补丁」。

## 第三轮（同日）：剩余工作 — 数据解码缺陷修复

### 起点：③-11 的「解码不可靠」其实是公式错误

`docs/09` 长期挂着一句「敌人数值 ⚠️ ObscuredLong 解码不可靠」。本轮先怀疑是字段布局，结果根因在
**`tools/scripts/decode.py` 的两处公式错误**：

| 类型 | 旧（错） | 正确 | 症状 |
|---|---|---|---|
| `ObscuredInt`/`ObscuredLong` | `hidden XOR key` | `(hidden − key) XOR key` | 敌人 HP 解出 ±9e18、`_level` 解出 2 亿 |
| `ObscuredFloat` | `float_bits(hidden XOR key)` | `float_bits(ACTkByte4.Shuffle(hidden) XOR key)` | 闪避 0 解成 1.5e-38 反常量；符文 Base 20 解成 11.35 |

判定依据（三重独立一致）：① `capstone` 反汇编新构建 `0x180451340 = sub rcx,rdx; xor rcx,rdx`（解密）
与 `0x180451330 = xor rcx,rdx; lea rax,[rdx+rcx]`（加密）——写入侧就是 `key + (value XOR key)`；
② `memory_reader.py`/`mem_probe.py` 的运行时实现同一公式（且面板对拍已实证）；③ **数值是否圆整**：
修正后符文 Base/PerLevel 变成 20/3、0.3/0.015、500/20，天赋 0.04/2，敌人 HP 250/300/350/6400，
攻速 0.4~1.5，暴伤 1.5/2，闪避取值 {0×53, 0.15×9, 0.2×2, 0.3×1} —— 全部是设计级圆整数。

### 修复动作

1. `decode.py` 两处公式改正（注释里写清依据与「错公式的症状」）；
2. 重算 `data/so_dump/` 全部受影响取值：**11 个文件、3124 个值**，逐行替换保证 diff 只有数值
   （`git diff --numstat` 每文件均为 `N/N`）；
3. `docs/09 §十五` 敌人 ⚠️ → ✅（并记下修正后的全字段量级）；
4. `docs/07` 顶部加 ⚠️ 说明受影响小节；`§8A.10` 符文样例表按修正值重写，并把由错值推出的
   「套装后期发力/传奇即插即用」结论**降级为待核**（不同属性不可横向比较）；
5. `aliases.json` 的 `Actk.ObscuredLong.Decrypt` 证据升级为**指令级（字节反汇编）**——顺带把第二轮
   剩下那条无指令级证据的弱依据别名补齐；
6. `AGENTS.md` 增加「ACTk `Obscured*` 取值公式按类型分家」的约定与判据（数值是否圆整）。

### 回归

| 命令 | 结果 |
|---|---|
| `python -m deskrawl_calc.cli selftest` | 10 PASS（数据换了值也未动） |
| `python -m deskrawl_gui --selftest` | **32/32 通过** —— 冻结夹具走内存/锚点，不吃 SO 浮点，故不受影响（这点必须验，验过了） |
| 其余门禁 | `rva_audit --check --falsify`（代码侧 + `--docs`）、`build_aliases --check`、`memdump`、`patch_regression --live --docs` 全 0 |

### 顺带查清的另外两条

- **③-10 Back 装备**：9 件在 `ItemData` 里**没有任何数值载荷**（`FixedStats`/`EquipmentEffects`/`Effect`/`BuffEffect` 全空），
  `EquipmentEffects.json` 92 条资产也不关联 Back → 旧结论「固定属性/特效传奇」两半都不成立，已就地否证并更正。
- **③-9 强化配方**：4 条按稀有度索引（Common 60388 / Rare 60391 / Legendary 60390 / Divine 60389），
  `UpgradeRecipeSpecial`(60392) 是额外的第 5 条、唯一带 2,000,000 金币与专属耗材 → 与「存在独立特殊强化通路」相容，但等级分支仍缺代码证据（保留暂缓）。

## 第四轮（同日）：③-18 文档浮点表复核与汇总报表同步

### 复核方法与结论：列出的「受影响小节」其实都不受影响

按修正后的 `data/so_dump/*.json` 逐表重算，与 `docs/07` 正文逐项比对：

| 小节 | 复核项 | 结果 |
|---|---|---|
| §8A.10 符文池统计 | 151 符文 / 73 不归套装且可重复装 / 78 归 13 套×6 件 / `Effects` 数 0 / `Modifier` 全 Flat | 一致 |
| §8A.10 属性分布 Top | 32 种属性 135 次逐项 | **两处错**（见下） |
| §8A.11 天赋 | MaxPoints 分布 / LevelRequirement / StatModifiers 38 / Effects 135 / 互斥组 3 组（16/14/12）/ `Prerequisite` 0 | 一致 |
| §8A.12 技能 | LevelRequirement 分布 / Targeting 分布 / TargetCount{1,3} / AoERadius 12 种 19 非零 / Effects 124 / ChannelDuration 7 / Tags 57·50·16·1 | 一致 |
| §8A.13 地图与敌人 | MapType/EliteChance/MaxEncounters/MiniBoss；Enemy 的 MythicSize 30·27·8 / DropsLoot 65 / Phases 2 / SpecialDrops 63 / Abilities 44·19·2 | 一致 |
| §8A.14 其他 | SlaveData 67（Species/Rarity/Capacity/Abilities）；ItemData 338（Type×Rarity / SellPrice 59 种 / MaxStackSize 四档 / EquipSlot / FixedStats 6） | 一致 |

**说明**：这些表是**计数型**（枚举/长度统计），本就不经过浮点解码，所以上一轮「§8A.11/§8A.12 写着旧值」的判断其实不成立——
第三轮把「§8A.10 也受影响」推广成了「一处不对、处处可疑」，本轮逐一核实后收敛为下面的具体账。

### 实际改动的三处

1. **`docs/07 §8A.10` 属性分布表两处错**：漏了计数为 2 的 `Armor`（旧稿 19 行只有 19 项 >1，
   使「其余条件伤害各 1」承担了 12 项）；且计数 1 的 12 项里有 5 项（DamageLightning /
   CooldownReduction / StrongAttackDamage / MagicResist / ManaRegen）**不是条件伤害**。已补 `Armor` 行、
   列出 12 项清单、注明「合计 32 种 / 135 次」。
2. **`docs/09 §B` 是汇总报表的陈旧镜像**（第三轮修了数据却没重生成报表）：§九 技能 ManaCost/Cooldown/Range、
   §十 Duration、§十五 三条敌人行（BaseMoveSpeed/BaseCritChance/BaseDodgeChance）仍是**旧公式的值**，
   且与同节上方第三轮新写的正确值**同页自相矛盾**（例：`BaseMoveSpeed 0.534302~5.30969` vs `0.8~3`）。
   已按重生成的 `report_data.md` 同步；§一 文件总览也从「21 文件/1333」更正为「25 文件/1624
   （21 主数据 1333 + 4 特效/系数资产 291）」。
3. **生成器陈旧点**：`build_report.py` 仍把 `BaseMaxHealth`/`BaseDamage` 标成「ObscuredLong 解码不可靠」、
   `num()` 的护栏注释挂在旧 bug 上、合计行硬编码「21 个文件」；`make_doc09.py` 的 HEAD 仍写 Desktop 数据源路径
   与「带 ⚠️ 者未可靠解码」。三处已改为「值照常输出 + 护栏仅作回归探针」并补上 AUX 文件的用途标签。

### 顺带更正：§8A.13「唯一神话地图」措辞

`MythicDungeon` 是 76 张地图里**唯一 `MapType=Mythic`** 的一张（此说无误），但神话参数是**两档**：
MythicDungeon 独一档（BaseHP 30 / BaseDamage 2 / BossDMG 30 / Band1End 50 / 金×0.02 / XP×0.015），
其余 75 张共用另一档（70 / 7 / 22 / 70 / 0.05 / 0.05）。旧稿把这一张的参数当成全局神话曲线，已补注。

### 回归

| 命令 | 结果 |
|---|---|
| `python build_report.py` | 重生成 `report_data.md`（247 行），§一 25 文件 / 1624 条 |
| `python -m deskrawl_calc.cli selftest` | 10 PASS |
| `python -m deskrawl_gui --selftest` | 32/32 |
| `python rva_audit.py --check --falsify` / `--docs` | 退出码 0 |
| `python build_aliases.py --check` | 退出码 0 |

## 遗留与建议

1. `docs/` 地址已全部有处置（0 待处理）；**文档正文的方法名仍是旧名**（如 docs/08 §11 摘录里的 `bjr`），
   后续可择机改引 `aliases.json` 的语义名——属文档改写工作量，不在本轮。
2. **③-18 已完成（第四轮）**：`§8A.11`～`§8A.14` 逐项复核**无差异**（计数型表格不吃浮点解码），
   实际修的是 `§8A.10` 属性分布表、`docs/09 §B` 陈旧镜像与两处生成器陈旧点；
   清单统计已从「已核 15 + 暂缓 4」收敛为「已核 16 + 暂缓 3」。
3. ③-9（强化等级→配方分支）、③-13（技能秒伤模型）、③-17（Back 战力来源）三条暂缓仍挂在清单里。
4. 数据生成链有隐患：`tools/scripts/assets_cache.json` 偏旧（`dump_all2.py` 靠它只认到 251/338 件物品），
   **直接重跑 `dump_all2.py` 会把 so_dump 覆盖成更小的数据集**（本轮实测后已 `git checkout` 回滚，未留痕）。
   下次要重导数据，先重建资产缓存并逐文件 `git diff` 核对；`decode.py` 已修，重导会得到与本次一致的值。
5. 定期（每次补丁后）跑 `python patch_regression.py --live --docs` 即可；把 `--falsify` 当自证，别让白名单替代证据。
