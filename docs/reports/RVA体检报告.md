# RVA 体检报告（由 `tools/scripts/rva_audit.py` 自动生成，勿手改）

- 命令：`python rva_audit.py --check --falsify`
- 当期 GameAssembly.dll SHA-256：`f8221364be8101c60d76be3e031f2cd5be376a7fb6b9b73a7cfb45e2a52a9fab`
- 旧构建 dump.cs 来源：`git show 8660446:data/schema/dump.cs`
- 扫描：34 个文件 / 154 条地址字面量

## 0. 结论摘要

| 判定 | 条数 |
|---|---|
| 非地址（白名单/自动规则） | 43 |
| 仍有效（方法） | 65 |
| 仍有效（注释里的方法名已过期） | 1 |
| 仍有效（数据地址） | 9 |
| 已失效（已给出重算值） | 0 |
| 已失效（内联数据，只能改成方法级引用） | 0 |
| 已失效（重算候选不唯一） | 0 |
| 已失效（无法重算） | 0 |
| 已失效（数据地址已迁移） | 0 |
| 无法判定（人工确认） | 0 |
| 历史对照（有意保留的旧地址） | 7 |
| 弃用探针（理由已写入文档） | 29 |
| **合计** | **154** |

## 1. 已失效与重算值（写回源码前需人工复核）

| 文件:行 | 注释 | 旧址 | 判定 | 重算值 | 依据 |
|---|---|---|---|---|---|

## 2. 仍有效但注释需更新（地址对、名字过期）

| 文件:行 | 注释名 | 当期名 |
|---|---|---|
| `tools/deskrawl_gui/core/memory_import.py:424` | SumStatBonus | 注释名 SumStatBonus → 当期名 bha；StatusEffectController::bha(StatType a, double b) { }) Slot=None |

## 3. 白名单：判为非地址（每条必须写明理由）

| 文件:行 | 字面量 | 理由 |
|---|---|---|
| `tools/deskrawl_calc/stattype.py:125` | `0x402010` | 封顶属性的**位掩码**（注释原文「掩码 0x402010 + 特判 37」），是 4 项封顶属性的位集，不是地址；与之配对的 0x4A9C30 才是代码地址 |
| `tools/deskrawl_gui/core/memory_reader.py:5` | `0x0410` | 四位以内的微常量（位掩码/计数/标志），不可能是地址 |
| `tools/deskrawl_gui/core/memory_reader.py:21` | `0x0410` | 四位以内的微常量（位掩码/计数/标志），不可能是地址 |
| `tools/deskrawl_gui/core/memory_reader.py:44` | `0x10000` | 用户态指针下限，出现在 `0x10000 <= p < 0x7FFFFFFEFFFF` 的范围比较里，是阈值不是地址 |
| `tools/deskrawl_gui/core/memory_reader.py:263` | `0xFFFFFFFF` | 值 0xFFFFFFFF 超出映像范围（max_rva=0x419d000），是掩码/哨兵而非地址 |
| `tools/deskrawl_gui/core/memory_reader.py:264` | `0x100000000` | 值 0x100000000 超出映像范围（max_rva=0x419d000），是掩码/哨兵而非地址 |
| `tools/deskrawl_gui/core/memory_reader.py:264` | `0x80000000` | 值 0x80000000 超出映像范围（max_rva=0x419d000），是掩码/哨兵而非地址 |
| `tools/deskrawl_gui/core/memory_reader.py:287` | `0xFFFFFFFF` | 值 0xFFFFFFFF 超出映像范围（max_rva=0x419d000），是掩码/哨兵而非地址 |
| `tools/deskrawl_gui/core/memory_reader.py:302` | `0xFF0000FF` | 值 0xFF0000FF 超出映像范围（max_rva=0x419d000），是掩码/哨兵而非地址 |
| `tools/scripts/decode.py:96` | `0xFF0000FF` | 值 0xFF0000FF 超出映像范围（max_rva=0x419d000），是掩码/哨兵而非地址 |
| `tools/scripts/decode.py:100` | `0xFFFFFFFF` | 值 0xFFFFFFFF 超出映像范围（max_rva=0x419d000），是掩码/哨兵而非地址 |
| `tools/scripts/decode.py:125` | `0xFFFFFFFF` | 值 0xFFFFFFFF 超出映像范围（max_rva=0x419d000），是掩码/哨兵而非地址 |
| `tools/scripts/decode.py:125` | `0xFFFFFFFF` | 值 0xFFFFFFFF 超出映像范围（max_rva=0x419d000），是掩码/哨兵而非地址 |
| `tools/scripts/decode.py:128` | `0xFFFFFFFF` | 值 0xFFFFFFFF 超出映像范围（max_rva=0x419d000），是掩码/哨兵而非地址 |
| `tools/scripts/disasm.py:11` | `0x180000000` | PE ImageBase 本身（节表换算基准），不是可寻址目标 |
| `tools/scripts/disasm2.py:9` | `0x180000000` | PE ImageBase 本身（节表换算基准），不是可寻址目标 |
| `tools/scripts/disasm2.py:95` | `0x8000000` | 值 0x8000000 超出映像范围（max_rva=0x419d000），是掩码/哨兵而非地址 |
| `tools/scripts/dump_index.py:91` | `0xFFFFFFFF` | 值 0xFFFFFFFF 超出映像范围（max_rva=0x419d000），是掩码/哨兵而非地址 |
| `tools/scripts/dump_index.py:147` | `0x4000` | `containing()` 判定「内联数据是否属于该方法的跨距阈值」，是搜索窗口宽度不是地址 |
| `tools/scripts/extract_rolltable.py:11` | `0x180000000` | PE ImageBase 本身（节表换算基准），不是可寻址目标 |
| `tools/scripts/mem_probe.py:37` | `0x0400` | 四位以内的微常量（位掩码/计数/标志），不可能是地址 |
| `tools/scripts/mem_probe.py:38` | `0x0010` | 四位以内的微常量（位掩码/计数/标志），不可能是地址 |
| `tools/scripts/mem_probe.py:65` | `0x10000` | 同上（内存链刻意自包含，与 memory_reader.py 是两份独立实现） |
| `tools/scripts/mem_probe.py:222` | `0xFFFFFFFF` | 值 0xFFFFFFFF 超出映像范围（max_rva=0x419d000），是掩码/哨兵而非地址 |
| `tools/scripts/mem_probe.py:223` | `0x100000000` | 值 0x100000000 超出映像范围（max_rva=0x419d000），是掩码/哨兵而非地址 |
| `tools/scripts/mem_probe.py:223` | `0x80000000` | 值 0x80000000 超出映像范围（max_rva=0x419d000），是掩码/哨兵而非地址 |
| `tools/scripts/mem_probe.py:235` | `0xFFFFFFFF` | 值 0xFFFFFFFF 超出映像范围（max_rva=0x419d000），是掩码/哨兵而非地址 |
| `tools/scripts/mem_probe.py:261` | `0xFF0000FF` | 值 0xFF0000FF 超出映像范围（max_rva=0x419d000），是掩码/哨兵而非地址 |
| `tools/scripts/mem_probe.py:558` | `0x0410` | 四位以内的微常量（位掩码/计数/标志），不可能是地址 |
| `tools/scripts/obs_solve3.py:42` | `0xffffffff` | 值 0xffffffff 超出映像范围（max_rva=0x419d000），是掩码/哨兵而非地址 |
| `tools/scripts/pe_file.py:8` | `0x180000000` | PE ImageBase 本身（节表换算基准），不是可寻址目标 |
| `tools/scripts/probe_dps_meter.py:34` | `0x0410` | 四位以内的微常量（位掩码/计数/标志），不可能是地址 |
| `tools/scripts/probe_paragon.py:41` | `0x0410` | 四位以内的微常量（位掩码/计数/标志），不可能是地址 |
| `tools/scripts/probe_paragon.py:45` | `0x180000000` | PE ImageBase 本身（节表换算基准），不是可寻址目标 |
| `tools/scripts/probe_player_statistics.py:28` | `0x0410` | 四位以内的微常量（位掩码/计数/标志），不可能是地址 |
| `tools/scripts/probe_runes.py:37` | `0x0410` | 四位以内的微常量（位掩码/计数/标志），不可能是地址 |
| `tools/scripts/probe_skill_levels.py:9` | `0x0410` | 四位以内的微常量（位掩码/计数/标志），不可能是地址 |
| `tools/scripts/probe_stat_labels.py:47` | `0x0410` | 四位以内的微常量（位掩码/计数/标志），不可能是地址 |
| `tools/scripts/probe_stat_labels.py:51` | `0x180000000` | PE ImageBase 本身（节表换算基准），不是可寻址目标 |
| `tools/scripts/rea_call.py:60` | `0x180000000` | PE ImageBase 本身（节表换算基准），不是可寻址目标 |
| `tools/scripts/read_const.py:6` | `0x180000000` | PE ImageBase 本身（节表换算基准），不是可寻址目标 |
| `tools/scripts/rva_audit.py:518` | `0x1000` | 本脚本的「微常量上限」判定阈值（低于它的字面量直接归入非地址），是规则参数不是地址 |
| `tools/scripts/xref.py:7` | `0x180000000` | PE ImageBase 本身（节表换算基准），不是可寻址目标 |

## 4a. 仍有效（数据地址：常量新址 / 当期 script.json 槽 / 登记的数据指针）

| 文件:行 | 字面量 | 依据 |
|---|---|---|
| `tools/deskrawl_calc/engine.py:152` | `0x18364FAD0` | 常量「护甲分母」= 50.0（double） |
| `tools/scripts/probe_paragon.py:17` | `0x183A2A4D8` | 当期 元数据槽：hh_TypeInfo（与登记名一致）（当期 script.json 按 RVA 命中 + data_refs 登记名核对） |
| `tools/scripts/probe_stat_labels.py:13` | `0x183A2D670` | 当期 元数据槽：ItemRarity_var（与登记名一致）（当期 script.json 按 RVA 命中 + data_refs 登记名核对） |
| `tools/scripts/probe_stat_labels.py:13` | `0x183A2FB50` | 当期 元数据槽：Method$UnityEngine.Object.Instantiate<StatRowUI>()（与登记名一致）（当期 script.json 按 RVA 命中 + data_refs 登记名核对） |
| `tools/scripts/probe_stat_labels.py:13` | `0x183A2FB48` | 当期 元数据槽：StatRowUI[]_TypeInfo（与登记名一致）（当期 script.json 按 RVA 命中 + data_refs 登记名核对） |
| `tools/scripts/probe_stat_labels.py:14` | `0x183A37E40` | 当期 元数据槽：ItemRarity[]_TypeInfo（与登记名一致）（当期 script.json 按 RVA 命中 + data_refs 登记名核对） |
| `tools/scripts/probe_stat_labels.py:14` | `0x183A1F3E8` | 当期 元数据槽：UnityEngine.Object_TypeInfo（与登记名一致）（当期 script.json 按 RVA 命中 + data_refs 登记名核对） |
| `tools/scripts/probe_stat_labels.py:14` | `0x183A25F98` | 当期 元数据槽：GameManager_TypeInfo（与登记名一致）（当期 script.json 按 RVA 命中 + data_refs 登记名核对） |
| `tools/scripts/probe_stat_labels.py:15` | `0x183A2D6C8` | 当期 元数据槽：PlayerStatistics_TypeInfo（与登记名一致）（当期 script.json 按 RVA 命中 + data_refs 登记名核对） |

## 4b. 历史对照（紧邻「旧/补丁前」标注，刻意保留的旧地址）

| 文件:行 | 字面量 | 原判定 | 重算值 | 上下文 |
|---|---|---|---|---|
| `tools/deskrawl_calc/cli.py:65` | `0x509D80` | 已失效（已给出重算值） | `0x180511060` | `CalcDamage@0x511060，补丁前 bjr@` |
| `tools/deskrawl_calc/engine.py:152` | `0x18363F120` | 已失效（已给出重算值） | `0x18364fad0` | `el))。常量 50 @ 0x18364FAD0（补丁前` |
| `tools/deskrawl_calc/stattype.py:106` | `0x6F6360` | 已失效（已给出重算值） | `0x18070a3f0` | `nit @ 0x70A3F0，补丁前 ..cctor @` |
| `tools/scripts/mem_probe.py:15` | `0x7A4360` | 已失效（已给出重算值） | `0x1807ba6a0` | `       RVA 0x7BA6A0   （旧 eed` |
| `tools/scripts/mem_probe.py:16` | `0x7A3EE0` | 已失效（已给出重算值） | `0x1807ba220` | `       RVA 0x7BA220   （旧 eea` |
| `tools/scripts/mem_probe.py:17` | `0x7A3AC0` | 已失效（已给出重算值） | `0x1807b9e00` | `       RVA 0x7B9E00   （旧 edy` |
| `tools/scripts/mem_probe.py:18` | `0x7A5C60` | 已失效（已给出重算值） | `0x1807bbfd0` | `       RVA 0x7BBFD0   （旧 eeu` |

## 4c. 弃用探针（不参与生产路径，理由与出处见文档；原判定与重算值仍保留）

| 文件:行 | 字面量 | 原判定 | 重算值 | 文档 |
|---|---|---|---|---|
| `tools/scripts/chk.py:26` | `0x39E4408` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |
| `tools/scripts/chk.py:26` | `0x39E4410` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |
| `tools/scripts/chk.py:26` | `0x39E4470` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |
| `tools/scripts/chk.py:26` | `0x39E4478` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |
| `tools/scripts/chk.py:26` | `0x39E44B0` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |
| `tools/scripts/chk.py:26` | `0x39E44C8` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |
| `tools/scripts/meta_range.py:6` | `0x39E43C0` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |
| `tools/scripts/meta_range.py:6` | `0x39E44E0` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |
| `tools/scripts/read_const.py:29` | `0x18362a1a0` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |
| `tools/scripts/read_const.py:30` | `0x18362a0e0` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |
| `tools/scripts/read_const.py:31` | `0x183629f64` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |
| `tools/scripts/read_const.py:32` | `0x183629ff8` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |
| `tools/scripts/read_const.py:33` | `0x18362a028` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |
| `tools/scripts/read_const.py:34` | `0x18362a050` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |
| `tools/scripts/read_const.py:35` | `0x18362a160` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |
| `tools/scripts/read_const.py:36` | `0x18362a658` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |
| `tools/scripts/read_const.py:37` | `0x183629e40` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |
| `tools/scripts/read_const.py:38` | `0x18362a3c0` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |
| `tools/scripts/strings_ctx.py:14` | `0x36f10` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |
| `tools/scripts/strings_ctx.py:14` | `0xbfe9b` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |
| `tools/scripts/strings_ctx.py:14` | `0xc0b56` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |
| `tools/scripts/strings_ctx.py:14` | `0x90167` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |
| `tools/scripts/strings_ctx.py:14` | `0x61685b` | 已失效（内联数据，只能改成方法级引用） | `0x180628b80` | docs/plan/补丁回归清单.md |
| `tools/scripts/xref.py:45` | `0x1839e44c8` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |
| `tools/scripts/xref.py:46` | `0x1839e44b0` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |
| `tools/scripts/xref.py:47` | `0x1839e4470` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |
| `tools/scripts/xref.py:48` | `0x1839e4478` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |
| `tools/scripts/xref.py:49` | `0x1839e4408` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |
| `tools/scripts/xref.py:50` | `0x1839e4410` | 无法判定（人工确认） | — | docs/plan/补丁回归清单.md |

弃用理由（配置里声明，脚本已校验文档确实写了）：

- `tools/scripts/chk.py`：一次性 PE 查看器：RVA 列表是取样（.data 里 SaveFileWriter/DDS1/DDS2 那批），不是锚点；且其功能已被 pe_file.py（节表/换算/读字节）覆盖。补丁后取样地址语义已变，重锚定无价值。
- `tools/scripts/meta_range.py`：一次性范围取样（[0x39E43C0,0x39E44E0] 打印 ScriptString），功能已被 script_index.py 完整覆盖；范围边界是取样窗口而非锚点。
- `tools/scripts/read_const.py`：一次性常量探针：目标常量在旧常量簇 0x18362A***，标签本身带问号（'roll_high / default(1.0?)'），且原始输入（补丁前 GameAssembly.dll）已被游戏更新覆盖，不可复原。其任务已由 extract_rolltable.py + docs/08 §11.3 的 55 项系数表 + §12.2 新址表承接。
- `tools/scripts/strings_ctx.py`：探针输入是 global-metadata.dat 的文件偏移，补丁后该文件被覆盖（同版本 v39、内容不同），旧偏移不可复原；当时的结论（SerializeReference 托管段布局）已固化进 decode.py 与 docs/08 §11.1。
- `tools/scripts/xref.py`：一次性 xref 探针：6 个目标地址是手搓的，与补丁前 script.json 的字面量表并不一致（'password' 项 0x39E44C8 vs 表内 0x39F1AD0），本身就不可信；字符串地址的权威来源已改为 script_index.py + script.json。

## 5. 文档表格复核

### 5.1 docs/08 §12.1 PE 节表

| 节 | 文档 VA | 实测 VA | 文档 raw | 实测 raw | 结论 |
|---|---|---|---|---|---|
| `.text` | `0x180001000` | `0x180001000` | `0x400` | `0x400` | ✅ |
| `il2cpp` | `0x180424000` | `0x180424000` | `0x422600` | `0x422600` | ✅ |
| `.rdata` | `0x182E63000` | `0x182e63000` | `0x2E61400` | `0x2e61400` | ✅ |
| `.data` | `0x18394C000` | `0x18394c000` | `0x3949800` | `0x3949800` | ✅ |

### 5.2 docs/08 §9.1+§12.2 常量新旧址（新址必须逐字节读回该值）

| 常量 | 值 | 旧址读取 | 新址 | 新址读取 | 结论 |
|---|---|---|---|---|---|
| 命中浮动上界 | `1.1` | `double=6.947929595477165e+78 float32=7.037368913005485e+22` | `0x18364F914` | `double=0.015234442414657679 float32=1.100000023841858` | ✅ |
| 受伤阈值 | `0.3` | `double=9.092174261023591e-307 float32=1.0899477145401121e+27` | `0x18364F728` | `double=4.800414192374092e-07 float32=0.30000001192092896` | ✅ |
| 健康阈值 | `0.8` | `double=5.624386911297039e+160 float32=-4744619770249216.0` | `0x18364F83C` | `double=5.246966156e-315 float32=0.800000011920929` | ✅ |
| 属性数值封顶 | `0.85` | `double=5.006413625294587e+223 float32=2.7368118089614256e+20` | `0x18364F860` | `double=0.0017968753794775695 float32=0.8500000238418579` | ✅ |
| 命中浮动下界 | `0.9` | `double=148713325446.85452 float32=-1.3242666332582207e-18` | `0x18364F87C` | `double=0.0030184672170435077 float32=0.8999999761581421` | ✅ |
| 易伤乘区 | `1.3` | `double=1.1368968342350022e+243 float32=3.072731204561519e+32` | `0x18364F938` | `double=0.07500000289874151 float32=1.2999999523162842` | ✅ |
| 护甲分母 | `50.0` | `double=3.3707750381021294e-307 float32=8.94658864418333e-39` | `0x18364FAD0` | `double=50.0 float32=0.0` | ✅ |
| 主属性分母 | `100.0` | `double=9.940868632040414e+247 float32=2.1129645031192029e-19` | `0x18364FAE8` | `double=100.0 float32=0.0` | ✅ |

## 6. memory_offsets.json 复核（结构偏移与方法锚点）

| 配置路径 | 模式 | 命中 | 说明 |
|---|---|---|---|
| `player` | field | ✅ | 全部命中 |
| `player` | field | ✅ | 全部命中 |
| `player.stat_dicts` | field | ✅ | 全部命中 |
| `player.conditional_mods` | field | ✅ | 全部命中 |
| `player.status_controller` | field | ✅ | 全部命中 |
| `player.status_controller` | field | ✅ | 全部命中 |
| `hero_data` | field | ✅ | 全部命中 |
| `inventory_slot` | field | ✅ | 全部命中 |
| `item_data` | field | ✅ | 全部命中 |
| `generated_item` | field | ✅ | 全部命中 |
| `talent_effect_ability_modifier` | field | ✅ | 全部命中 |
| `player.conditional_mods` | const | ✅ | 结构尺寸与声明一致 |
| `talent_effect_ability_modifier` | const | ✅ | 结构尺寸与声明一致 |
| `singleton_getters` | rva | ✅ | 全部命中 |
| `save_system.anchor_rvas` | rva | ✅ | 全部命中 |
| `generated_items.scan_rvas` | rva | ✅ | 全部命中 |
| `generated_items.klass` | klass | ✅ | 类 gj 仍存在 |
| `hero_data.klass` | klass | ✅ | 类 HeroData 仍存在 |
| `item_data.klass` | klass | ✅ | 类 ItemData 仍存在 |
| `generated_item_klass` | klass | ✅ | 类 GeneratedItemData 仍存在 |

### 6.1 版本指纹门禁

| 键 | 声明值 | 实测值 | 结论 |
|---|---|---|---|
| `game_assembly_sha256` | `f8221364be8101c6…` | `f8221364be8101c6…` | ✅ |
| `global_metadata_sha256` | `f5cf7ba1bbd13cb0…` | `f5cf7ba1bbd13cb0…` | ✅ |

## 7. 可证伪演示（`--falsify`）

| 用例 | 期望 | 实测 | 结论 | 说明 |
|---|---|---|---|---|
| `0x18067FCE1` | stale | stale_inline | ✅ | 真实有效地址 0x18067FCE0（当期 Character.bkm=CalcDamage）末位 +1，必须判失效 |
| `0x180511061` | stale | stale_inline | ✅ | Player.bkm 覆写 0x180511060 末位 +1 |
| `0x7BA6A1` | stale | stale_inline | ✅ | SaveSystem 锚点 0x7BA6A0 末位 +1（RVA 形式） |
| `0x18364F861` | stale | unknown | ✅ | 常量 0.85 新址 0x18364F860 末位 +1（数据地址） |
| `0x183A2A4D9` | stale | unknown | ✅ | 当期元数据槽 hh_TypeInfo 0x183A2A4D8 末位 +1：当期表查不到该 RVA，必须落回人工确认（证明 ⑥ 不是「.data 一律放行」） |
| `0x18067FCE0` | valid | valid | ✅ | 真值对照：同一地址必须判有效（证明不是「一律判红」） |

## 8. 配置与文档锚点自校验

### 8.1 `data_refs` 逐条锚点（没有可核对锚点的必须显式声明 `anchor: none`）

| 文件 | 字面量 | 锚点 | 结论 | 说明 |
|---|---|---|---|---|
| `tools/scripts/probe_paragon.py` | `0x183A2A4D8` | 名字核对 | ✅ | expect=hh_TypeInfo |
| `tools/scripts/probe_stat_labels.py` | `0x183A2D670` | 名字核对 | ✅ | expect=ItemRarity_var |
| `tools/scripts/probe_stat_labels.py` | `0x183A2FB50` | 名字核对 | ✅ | expect=Method$UnityEngine.Object.Instantiate<StatRowUI>() |
| `tools/scripts/probe_stat_labels.py` | `0x183A2FB48` | 名字核对 | ✅ | expect=StatRowUI[]_TypeInfo |
| `tools/scripts/probe_stat_labels.py` | `0x183A37E40` | 名字核对 | ✅ | expect=ItemRarity[]_TypeInfo |
| `tools/scripts/probe_stat_labels.py` | `0x183A1F3E8` | 名字核对 | ✅ | expect=UnityEngine.Object_TypeInfo |
| `tools/scripts/probe_stat_labels.py` | `0x183A25F98` | 名字核对 | ✅ | expect=GameManager_TypeInfo |
| `tools/scripts/probe_stat_labels.py` | `0x183A2D6C8` | 名字核对 | ✅ | expect=PlayerStatistics_TypeInfo |
| `docs/08-常量设计要点与待办.md` | `0x182EE3580` `0x18349CCB0` | 显式无锚点 | ✅ | 已声明当期无锚点可查（原因写在 reason 里） |
| `docs/08-常量设计要点与待办.md` | `0x18364F9D0` `0x18364F9C8` `0x18364F9D8` `0x18364FE38` | 显式无锚点 | ✅ | 已声明当期无锚点可查（原因写在 reason 里） |

### 8.2 文档记录的构建指纹（文档 ↔ 磁盘 双向核对）

| 键 | 文档 | 文档记录值 | 磁盘实测 | 结论 |
|---|---|---|---|---|
| `game_assembly_sha256` | `docs/08-常量设计要点与待办.md` | `f8221364be8101c6…` | `f8221364be8101c6…` | ✅ 与磁盘一致；文档已记录 |

