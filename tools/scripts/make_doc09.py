import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
# -*- coding: utf-8 -*-
import io

BODY = open(REPORT_DATA, encoding='utf-8').read()
OUT = r'C:\Users\<user>\Desktop\Deskrawl-数值设计文档\09-存档解密与数据汇总报表.md'

DECRYPT_PY = r'''import hashlib, hmac, json

SAVE  = GAME_SAVE
PW    = b'desktop-diablo-save-v1-CHANGE-ME'
MACPW = b'desktop-diablo-save-v1-CHANGE-ME|mac'

def aes_cbc(key, iv, ct):
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    d = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    return d.update(ct) + d.finalize()

def unpad(b):
    n = b[-1] if b else 0
    return b[:-n] if 1 <= n <= 16 and b[-n:] == bytes([n]) * n else b

data  = open(SAVE, 'rb').read()
key   = hashlib.sha256(PW).digest()
mackey= hashlib.sha256(MACPW).digest()

assert data[:4] == b'DDS2'
mac, iv, ct = data[4:36], data[36:52], data[52:]
assert hmac.new(mackey, data[:4] + iv + ct, hashlib.sha256).digest() == mac   # MAC 校验

txt = unpad(aes_cbc(key, iv, ct)).decode('utf-8')
obj = json.loads(txt)                       # -> SaveContainer
print(list(obj.keys()))                     # ['Version','LocalSlots','OnlineSlots','LocalStash','DlcEntitlements']
'''

HEAD = f'''# 存档解密与实测数据汇总报表

> 📚 **Deskrawl 数值设计文档** ｜ [返回索引](00-索引.md)

> 本篇补齐第 08 篇遗留的两项待办：**(A) `Data/save.json`（DDS2）存档加解密算法**（指令级还原 + 字节级验证）、
> **(B) 附录 A 21 个 JSON（1333 条 SO 实例）的可读汇总报表**，以及 **(C) 已解密存档的结构说明（存档字段 ↔ `SaveData` 对照）**。

---

## A. DDS2 存档解密

### A.1 定位路径

存档写入调用链（`GameAssembly.dll`）：

```
SaveSystem.SerializeContainer(SaveContainer)  @ RVA 0x7BA6A0
   ├─ UnityEngine.JsonUtility.ToJson   @ RVA 0x182A04BD0
   ├─ SaveSystem.CompactJson(string)   @ RVA 0x7CEF20   ; JSON 压缩（去空白）
   └─ SaveWriter.WriteAsync @ RVA 0x4DF520 (异步写盘)
          ├─ je.jc.evc()               @ RVA 0x4DFD30
          └─ SaveCrypto.Encrypt(string) -> byte[]  @ RVA 0x7FA7C0   ; ★ 加密封装
```

真正的编解码类在补丁前叫 **`it`**（TypeDefIndex 6173，含静态字段 `nns`/`nnt` = magic 字节数组），
补丁后按「类形状匹配」重锚定为 **`jb`**；语义名与当期地址见 `data/schema/aliases.json`：

| 方法 | RVA | 作用 |
|---|---|---|
| `SaveCrypto.Sha256(string)` | `0x7FA3D0` | `SHA256(UTF8(s))` → 32 字节 |
| `SaveCrypto.FileKey()` | `0x7FA5D0` | 文件密钥 = `Sha256("desktop-diablo-save-v1-CHANGE-ME")` |
| `SaveCrypto.MacKey()` | `0x7FA630` | MAC 密钥 = `Sha256("desktop-diablo-save-v1-CHANGE-ME|mac")` |
| `SaveCrypto.Encrypt(string)` | `0x7FA7C0` | 加密：JSON 字符串 → 文件字节 |
| `SaveCrypto.Decrypt(byte[], out string, out bool)` | `0x7FB260` | 解密：文件字节 → JSON |
| `SaveCrypto.IsDds2(byte[])` | `0x7FA690` | 版本判定（前缀是否 `DDS2`） |
| `SaveCrypto.FixedTimeEquals(byte[], byte[])` | `0x7FA750` | 定长比较 |
| `SaveCrypto.StaticInit()` | `0x7FBB90` | 初始化 magic：`ASCII("DDS1")` / `ASCII("DDS2")` |

> 线索来源：`global-metadata.dat` 字符串 `SaveFileWriter: `、`DDS1`、`DDS2`、
> `desktop-diablo-save-v1-CHANGE-ME(|mac)`，经 metadata-usage 交叉定位到 `iw`/`it` 类。✅

### A.2 密钥派生 ✅

```
Key    = SHA256( UTF8("desktop-diablo-save-v1-CHANGE-ME") )        # AES-256 主密钥
MacKey = SHA256( UTF8("desktop-diablo-save-v1-CHANGE-ME|mac") )    # HMAC 独立密钥
```

即 **无盐 PBKDF**——密钥直接取自字符串 SHA-256，`|mac` 后缀仅用于 MAC 密钥的域隔离。

### A.3 文件格式（DDS2）✅

```
偏移   长度   字段
0x00    4     Magic   = "DDS2" (44 44 53 32)
0x04   32     MAC     = HMAC-SHA256( MacKey, Magic || IV || Ciphertext )
0x24   16     IV      = 随机生成，随文件保存
0x34   N      Ciphertext = AES-256-CBC( Key, IV, PKCS7(UTF8(json)) )
```

- 密文算法：`Aes.Create()` 默认 **CBC + PKCS7**，密钥 32 字节 → **AES-256-CBC**。
- MAC 覆盖 **magic + IV + 密文**（不含自身），校验通过即可确证明文未被篡改。
- 文件总长 = `52 + N`；`N` 为 16 的整数倍。

### A.4 验证结果 ✅

对实际存档 `d:\\steam\\steamapps\\common\\Deskrawl\\Data\\save.json`（**2676 字节**）：

- Magic = `DDS2`，密文 `N = 2624 = 16 × 164`；
- **重算 MAC 与文件中 MAC 完全一致** → 格式与密钥 100% 正确；
- 解密去填充后得 2623 字节合法 JSON，顶层结构：

```json
{{ "Version": 5, "LocalSlots": [...], "OnlineSlots": [...], "LocalStash": {{...}}, "DlcEntitlements": [...] }}
```

（示例账号 `ExampleHeroA` / `MonkHero`，`OnlineSlots[0].Data` 即 `SaveData`：Level、CurrentXP、BaseMaxHealth…）

### A.5 解密脚本（可直接复用）

```python
{DECRYPT_PY}```

> 依赖：`pycryptodome` 或 `cryptography`。`DDS1` 为旧格式（同一密钥、magic 不同），当前版本已弃用。

---

## B. 实测数据汇总报表

> 数据源：`data/so_dump/*.json`（25 文件：21 个主数据 1333 条 + 4 个特效/系数资产 291 条，字节级精确解码）。
> 数值单位与枚举含义详见第 02、07 篇；本报表由 `tools/scripts/build_report.py` 生成到 `report_data.md`，
> 2026-10-10 已随 `decode.py` 的 ACTk 公式修正重生成（旧版本节含错值，勿引用历史副本）。
> 表中 `n=` 为有效样本数；过滤阈值（剔除反常量与 1e18 量级）是防御性护栏，用于捕获解码回归。

'''

PART_C = r'''
---

## C. 已解密存档结构说明（存档字段 ↔ `SaveData` 对照）

> 数据来源：A 部分解密得到的 `save_decrypted.json`（本机），字段定义来自 `dump.cs` 的
> `SaveContainer` / `SaveSlotRecord` / `SaveData` / `SavedStash` 等类（TypeDefIndex 6099–6135）。
> 序列化由 **`UnityEngine.JsonUtility`** 完成：**JSON 键 = C# 字段名，顺序 = 字段声明顺序**，
> 无缩进（写入前经 `SaveSystem.egk` 去除空白）。✅

### C.1 结构总览

```
SaveContainer
├─ Version : int                      存档格式版本（当前 = 5）
├─ LocalSlots   : List<SaveSlotRecord> 本地(离线)模式槽位（本机为空）
├─ OnlineSlots  : List<SaveSlotRecord> 联机模式槽位（本机 2 条）
├─ LocalStash   : SavedStash           跨角色共享仓库（金币/材料/生活技能/巅峰）
└─ DlcEntitlements : List<LocalDlcEntitlement>

SaveSlotRecord
├─ Mode       : CharacterMode         0 = Local, 1 = Online
├─ ProfileId  : string                账号/存档唯一 ID
├─ PlayerName : string                槽位显示名
├─ Level      : int                   槽位显示等级（≠ Data.Level）
├─ HeroName   : string                职业资源名（如 MonkHero）
└─ Data       : SaveData              该槽位的全部角色数据

SaveData                    SavedStash
├─ 角色数值…                 ├─ Slots / Registry / Gold
├─ InventorySlots…           ├─ Materials / LifeSkills
├─ 进度集合…                 ├─ UnlockedSlaves
└─ 统计…                     └─ Paragon : SavedParagon
```

### C.2 顶层容器 `SaveContainer`（TypeDefIndex 6118）

| JSON 键 | 类型 | 偏移 | 说明 | 本机样本 |
|---|---|---|---|---|
| `Version` | int | 0x10 | 存档格式版本 | `5` |
| `LocalSlots` | `List<SaveSlotRecord>` | 0x18 | 本地模式槽位 | `[]` |
| `OnlineSlots` | `List<SaveSlotRecord>` | 0x20 | 联机模式槽位 | 2 条 |
| `LocalStash` | `SavedStash` | 0x28 | 跨角色共享仓库 | 见 C.5 |
| `DlcEntitlements` | `List<LocalDlcEntitlement>` | 0x30 | 已购 DLC/权益 | `[]` |

### C.3 槽位记录 `SaveSlotRecord`（TypeDefIndex 6116）

| JSON 键 | 类型 | 偏移 | 说明 |
|---|---|---|---|
| `Mode` | `CharacterMode` | 0x10 | `0 = Local`, `1 = Online` |
| `ProfileId` | string | 0x18 | 32 位十六进制账号 ID |
| `PlayerName` | string | 0x20 | 槽位显示名（本机 `ExampleHeroA` / `ExampleHeroB`） |
| `Level` | int | 0x28 | 槽位等级（本机 `6` / `70`） |
| `HeroName` | string | 0x30 | 职业资源名（本机 `MonkHero` / `BarbarianHero`） |
| `Data` | `SaveData` | 0x38 | 角色完整数据（见 C.4） |

> ⚠️ 注意：`SaveSlotRecord.Level/PlayerName` 与 `Data.Level/Data.PlayerName` 是**两组独立字段**。
> 本机样本中槽位层有值、`Data` 层为默认值（`Level=1`、`PlayerName=""`），说明槽位列表是**摘要索引**，真实数据在 `Data`。

### C.4 角色数据 `SaveData`（TypeDefIndex 6099，共 49 字段）

| JSON 键 | 类型 | 偏移 | 说明 | 本机样本 |
|---|---|---|---|---|
| `Level` | int | 0x10 | 角色等级 | `1` |
| `CurrentXP` | long | 0x18 | 当前经验 | `0` |
| `BaseMaxHealth` | long | 0x20 | 基础最大生命 | `100` |
| `BaseDamage` | long | 0x28 | 基础伤害 | `10` |
| `CurrentHP` | long | 0x30 | 当前生命（**-1 = 未持久化/进图时满血**） | `-1` |
| `BaseMaxMana` | long | 0x38 | 基础最大法力 | `100` |
| `CurrentMana` | long | 0x40 | 当前法力（-1 同上） | `-1` |
| `BasePrimaryStat` | float | 0x48 | 基础主属性 | `10` |
| `InventorySlots` | `List<SavedSlot>` | 0x50 | 背包槽 | `[]` |
| `EquipmentSlots` | `List<SavedEquipSlot>` | 0x58 | 已装备槽 | `[]` |
| `CarriageSlots` | `List<SavedSlot>` | 0x60 | 马车(随行)槽 | `[]` |
| `ItemRegistryEntries` | `List<SavedRegistryEntry>` | 0x68 | 物品实例注册表（词条/强化/镶嵌） | `[]` |
| `ActiveMapName` | string | 0x70 | 当前地图 | `""` |
| `ActiveArea` | string | 0x78 | 当前区域 | `Town` |
| `ActiveTownName` | string | 0x80 | 当前城镇 | `""` |
| `ActiveSlave` | string | 0x88 | 当前出战随从 | `""` |
| `ClaimedDlc` | `List<string>` | 0x90 | 已领取 DLC 奖励 | `[]` |
| `TalentOutstandingPoints` | int | 0x98 | 未分配天赋点 | `0` |
| `AllocatedTalents` | `List<SavedTalent>` | 0xA0 | 已点天赋 | `[]` |
| `ParagonStats` | `List<SavedParagonStat>` | 0xA8 | 巅峰属性分配 | `[]` |
| `CarriageRarityActions` | `List<SavedRarityAction>` | 0xB0 | 马车按稀有度的自动处理规则 | `[]` |
| `CarriageFilterReins` | bool | 0xB8 | 马车筛选：缰绳 | `true` |
| `CarriageCollectChests` | bool | 0xB9 | 马车自动拾取宝箱 | `true` |
| `CarriageCollectResourceNodes` | bool | 0xBA | 马车自动采集资源点 | `true` |
| `HealthPotionAutoUseThreshold` | float | 0xBC | 自动喝药阈值（**-1 = 关闭**） | `-1` |
| `ConsumableSlots` | `List<string>` | 0xC0 | 快捷消耗品 | `[]` |
| `RuneSlots` | `List<SavedSlot>` | 0xC8 | 符文槽 | `[]` |
| `RunesTabOpened` | bool | 0xD0 | 符文页是否解锁 | `false` |
| `LearnedAbilities` | `List<SavedAbility>` | 0xD8 | 已学技能（含等级/XP） | `[]` |
| `EquippedBasicAttack` | string | 0xE0 | 普攻技能 | `""` |
| `EquippedStrongAttack` | string | 0xE8 | 重击技能 | `""` |
| `EquippedSpecial1` | string | 0xF0 | 特殊技 1 | `""` |
| `EquippedSpecial2` | string | 0xF8 | 特殊技 2 | `""` |
| `SelectedHero` | string | 0x100 | 已选职业 | `""` |
| `PlayerName` | string | 0x108 | 角色名（与槽位名独立） | `""` |
| `UnlockedObjects` | `List<string>` | 0x110 | 已解锁对象/功能 | `[]` |
| `CompletedQuests` | `List<string>` | 0x118 | 已完成任务 | `[]` |
| `VisitedMaps` | `List<string>` | 0x120 | 已访问地图 | `[]` |
| `CompletedMaps` | `List<string>` | 0x128 | 已通关地图 | `[]` |
| `SeenStories` | `List<string>` | 0x130 | 已观看剧情 | `[]` |
| `MythicBestTimes` | `List<SavedMythicBest>` | 0x138 | 神话最佳用时 | `[]` |
| `WorldDifficulty` | string | 0x140 | 当前难度 | `""` |
| `HighestDifficulty` | string | 0x148 | 最高已解锁难度 | `""` |
| `ClearedDifficulty` | string | 0x150 | 已通关难度 | `""` |
| `PotionUpgradeLevel` | int | 0x158 | 血瓶升级档位 | `0` |
| `ActiveBuffs` | `List<SavedActiveBuff>` | 0x160 | 跨会话保留的 Buff | `[]` |
| `TotalGameTime` | double | 0x168 | 累计游戏时长 | `0` |
| `TotalEarnedGold` | long | 0x170 | 累计获得金币 | `0` |
| `TotalEarnedExp` | long | 0x178 | 累计获得经验 | `0` |
| `TotalDeaths` | int | 0x180 | 累计死亡次数 | `0` |
| `LootCountsByRarity` | int[] | 0x188 | 各稀有度掉落计数 | `[]` |
| `LastSessionEndUnix` | long | 0x190 | 上次会话结束时间戳 | `0` |

### C.5 共享仓库 `SavedStash`（6117）与 `SavedParagon`（6113）

**`SavedStash`**（`LocalStash`）

| JSON 键 | 类型 | 偏移 | 说明 |
|---|---|---|---|
| `Slots` | `List<SavedSlot>` | 0x10 | 仓库格 |
| `Registry` | `List<SavedRegistryEntry>` | 0x18 | 仓库物品注册表 |
| `Gold` | long | 0x20 | 共享金币（本机 `0`） |
| `Materials` | `List<SavedMaterial>` | 0x28 | 材料 |
| `LifeSkills` | `List<SavedLifeSkill>` | 0x30 | 生活技能等级 |
| `UnlockedSlaves` | `List<string>` | 0x38 | 已解锁随从 |
| `Paragon` | `SavedParagon` | 0x40 | 巅峰状态 |

**`SavedParagon`**：`Unlocked : bool` / `Level : int` / `XP : long`（本机 `false / 0 / 0`）

### C.6 物品与装备保存结构

| 类（TypeDefIndex） | 字段（JSON 键 : 类型） |
|---|---|
| `SavedSlot` (6109) | `Idx:int`, `ItemName:string`, `Count:int`, `ItemUid:string`, `Locked:bool` |
| `SavedEquipSlot` (6110) | `SlotId:string`, `ItemName:string`, `ItemUid:string` |
| `SavedStatModifier` (6103) | `Stat:string`, `Type:string`, `Value:float` ← 单条词条（Stat 名 + 类型 + 数值） |
| `SavedRegistryEntry` (6104) | `Uid`, `ItemLevel:int`, `Rarity:string`, `Modifiers:List<SavedStatModifier>`, `UpgradeLevel:int`, `UpgradeAttempts:int`, `IsAncient:bool`, `Locked:bool`, `RuneLevel:int`, `RuneXP:long`, `SocketCount:int`, `SocketedGemBaseIds:List<string>`, `InstanceId:string`, `ChestContents:List<SavedChestContent>`, `ChestGold:int`, `SourceMapMinEnemyLevel:int`, `SourceIsMythic:bool`, `IsBlackMist:bool`, `BlackMistReveal:SavedBlackMistReveal`, `Bound:bool` |
| `SavedChestContent` (6105) | `BaseItemId:string`, `ItemLevel:int`, `Rarity:string`, `Modifiers:List<SavedStatModifier>`, `IsAncient:bool`, `IsBlackMist:bool`, `InstanceId:string`, `SocketCount:int` |
| `SavedBlackMistReveal` (6106) | `Slots:List<SavedBlackMistRevealSlot>`, `Finalized:bool` |
| `SavedBlackMistRevealSlot` (6107) | `ChoiceA:SavedStatModifier`, `ChoiceB:SavedStatModifier`, `Revealed:bool`, `Selected:int` |
| `SavedMaterial` (6102) | `MaterialAssetName:string`, `Count:int` |

> `SavedRegistryEntry` 是存档里**最重的数值单元**：一件装备的全部词条（`Modifiers`）、强化（`UpgradeLevel/Attempts`）、
> 镶嵌（`SocketCount/SocketedGemBaseIds`）、来源（`SourceMapMinEnemyLevel/SourceIsMythic/IsBlackMist`）与绑定状态都在此。

### C.7 其余记录类

| 类（TypeDefIndex） | 字段 |
|---|---|
| `SavedTalent` (6111) | `TalentName:string`, `Points:int` |
| `SavedParagonStat` (6114) | `Stat:string`, `Points:int` |
| `SavedRarityAction` (6108) | `Rarity:string`, `Action:string` |
| `SavedAbility` (6115) | `AbilityName:string`, `Level:int`, `XP:long` |
| `SavedLifeSkill` (6112) | `NodeName:string`, `Level:int` |
| `SavedMythicBest` (6100) | `Id:string`, `Seconds:float` |
| `SavedActiveBuff` (6101) | `EffectAssetName:string`, `RemainingDuration:float`, `Stacks:int`, `BuffCategory:BuffCategory` |
| `LocalDlcEntitlement` (6135) | `SteamId:string`, `AppId:uint`, `SharedRewardsClaimed:bool` |

### C.8 枚举与序列化约定

- **`CharacterMode`**：`Local = 0`，`Online = 1`（`SaveContainer` 用两个列表区分两种模式的槽位）。
- **JSON 键即字段名**：`JsonUtility` 按字段名序列化，字段声明顺序 = JSON 顺序（与上表偏移递增一致）。
- **默认值填充**：所有字段始终写出（空集合 = `[]`，无值字符串 = `""`，未用 = `0`）。
- **哨兵值**：`CurrentHP/CurrentMana = -1`（表示未保存、加载时按满值处理）；
  `HealthPotionAutoUseThreshold = -1`（自动喝药关闭）。
- **两套名字**：槽位层（`SaveSlotRecord.PlayerName/Level/HeroName`）与角色层（`SaveData.PlayerName/Level`）独立，勿混淆。

### C.9 本机样本解读

| # | Mode | ProfileId | PlayerName | Level | HeroName | Data 状态 |
|---|---|---|---|---|---|---|
| 0 | 1 | `00000000000000000000000000000002` | ExampleHeroA | 6 | MonkHero | 初始数据（Lv1，背包全空） |
| 1 | 1 | `00000000000000000000000000000001` | ExampleHeroB | 70 | BarbarianHero | 初始数据（Lv1，背包全空） |

`LocalSlots` 为空、`LocalStash` 全空、`DlcEntitlements` 为空 → 该账号仅有 2 个联机槽位的“新建”记录。

---
'''

FOOT = '''*文档结束。A 部分为指令级还原 + 字节级验证（✅）；B 部分由脚本 `report_data.md` 自动生成；C 部分字段定义取自 `dump.cs`，样本值取自本机解密存档。*
'''

DOC = HEAD + BODY + PART_C + '\n' + FOOT

with io.open(OUT, 'w', encoding='utf-8') as f:
    f.write(DOC)
print('written ->', OUT, 'chars', len(DOC))
