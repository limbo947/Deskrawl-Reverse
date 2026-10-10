## 一、数据文件总览

| 文件 | 记录数 | 主要用途 |
|---|---:|---|
| `AbilityData.json` | 124 | 技能定义 |
| `AffixRollTable.json` | 6 | 装备词条 Roll 系数表 |
| `Enemy.json` | 65 | 敌人定义 |
| `EquipmentEffects.json` | 92 | 装备特效定义（按稀有度索引） |
| `FishingMapData.json` | 3 | 钓鱼点 |
| `GameConfig.json` | 2 | 全局数值配置（等级/成长/锻造/镶嵌/巅峰/离线） |
| `GemData.json` | 36 | 宝石库 |
| `HealingPotionUpgradeData.json` | 1 | 血瓶升级配方 |
| `HealthPotionConfig.json` | 8 | 血瓶档位效果 |
| `HeroData.json` | 4 | 职业英雄定义 |
| `ItemData.json` | 338 | 装备/材料物品库 |
| `ItemizationConfig.json` | 1 | 装备词条池与宝石孔 |
| `LifeSkillEffects.json` | 36 | 生活技能特效 |
| `LifeSkillNodeData.json` | 85 | 生活技能节点 |
| `LootConfig.json` | 2 | 掉落向量与稀有度权重 |
| `MapData.json` | 76 | 地图关卡 |
| `QuestData.json` | 22 | 任务 |
| `RecipeData.json` | 51 | 合成配方 |
| `RuneData.json` | 151 | 符文库 |
| `RuneSetData.json` | 13 | 符文套装效果 |
| `SlaveData.json` | 67 | 宠物/随从 |
| `StatusEffectData.json` | 95 | 状态/Buff定义 |
| `TalentData.json` | 186 | 天赋树节点 |
| `TalentEffects.json` | 157 | 天赋特效 |
| `TownData.json` | 3 | 城镇 |
| **合计** | **1624** | 25 个文件（21 个主数据 + 4 个特效/系数资产） |

> 第 07 篇引用的「1333 条 SO 实例」指 21 个主数据文件（实测 1333 条）；另有 4 个特效/系数资产文件（291 条）不计入该口径。

## 二、装备/材料库（`ItemData.json`，338 条）

- **按 Type 分布**：Type 1=29, Type 2=87, Type 3=209, Type 7=13
- **按 Rarity 分布**：Common=49, Uncommon=86, Rare=114, Legendary=81, Divine=8
- **售价 SellPrice**：1 ~ 1e+07（中位 300, n=338）
- **掉落等级 MinDropLevel**：1 ~ 9999（中位 1, n=338）

## 三、宝石库（`GemData.json`，36 条）

- **按 Type 分布**：Type 6=36
- **按 Rarity 分布**：Common=36
- **售价 SellPrice**：2000 ~ 12000（中位 7000, n=36）
- **掉落等级 MinDropLevel**：30 ~ 999（中位 42.5, n=36）

## 四、符文库（`RuneData.json`，151 条）

- **按 Type 分布**：Type 5=151
- **按 Rarity 分布**：Uncommon=9, Rare=32, Legendary=32, Set=78
- **售价 SellPrice**：500 ~ 5000（中位 5000, n=151）
- **掉落等级 MinDropLevel**：1 ~ 35（中位 1, n=151）

## 五、全局配置 GameConfig（正式版）

| 常量 | 值 |
|---|---|
| 最大等级 MaxPlayerLevel | 70 |
| 离线时长上限(h) | 8 |
| 称号巅峰/级 ParagonPointsPerLevel | 1 |
| 装备最大强化等级 | 12 |
| 镶嵌材料数量/孔 | 100 |
| 镶嵌金币/物品等级 | 400 |
| 天赋洗点/点 | 8 |
| 精英血量× | 3 |
| 精英伤害× | 1.5 |
| 精英体型× | 1.1 |
| 精英怪等级0-30 血量成长 | 0.12 |
| 精英怪等级0-30 伤害成长 | 0.1 |
| 技能最大等级 | 10 |
| 技能升1级基础XP | 135 |
| 技能XP成长/级 | 1.5 |
| 符文最大等级 | 6 |
| 符文升1级基础XP | 450 |
| 符文XP成长/级 | 1.8 |
| 经验/基础血量 XpPerBaseHealth | 1 |
| 经验等级缩放 XpPerLevelScale | 0.1 |
| 低于此等级差无经验 | 6 |
| 离线每金币产出怪数 | 4 |

**升级所需击杀数（MobsToLevel）**：Lv1=2, Lv5=35, Lv15=900, Lv50=20000, 满级=50000

**强化成功率 UpgradeSuccessChances**（1→12 级）：1, 1, 1, 1, 0.75, 0.5, 0.4, 0.3, 0.2, 0.1, 1, 1

**难度档 DifficultyTiers**：

| 难度 | 敌人血量× | 敌人伤害× | 经验× | 掉落/地图级 | 金币/地图级 | 物品等级/地图级 | Boss材料× |
|---|---|---|---|---|---|---|---|
| 0 | 1 | 1 | 1 | 0 | 0 | 0 | 1 |
| 1 | 3.5 | 1.35 | 1.5 | 0.005 | 0.005 | 1 | 1.5 |
| 2 | 6 | 1.8 | 2 | 0.01 | 0.01 | 2 | 2 |

**巅峰属性 ParagonStats**（Stat / 每点收益 / 上限）：

| Stat | 类别 | 每点 | 上限 |
|---|---|---|---|
| 0 | 0 | 1 | 0 |
| 1 | 0 | 1 | 0 |
| 2 | 0 | 1 | 0 |
| 57 | 0 | 0.005 | 50 |
| 14 | 0 | 2 | 50 |
| 4 | 1 | 0.001 | 50 |
| 5 | 1 | 0.02 | 50 |
| 6 | 1 | 0.004 | 50 |
| 13 | 1 | 0.002 | 50 |
| 44 | 2 | 0.01 | 50 |
| 59 | 2 | 0.01 | 50 |
| 42 | 2 | 0.005 | 50 |
| 36 | 2 | 4 | 50 |
| 11 | 3 | 5 | 25 |
| 17 | 3 | 0.05 | 0 |

## 六、掉落配置 LootConfig（正式版）

| 敌人档 | 掷骰次数 | 金币× | 药水掉落 | 最小向量 | 最大向量 | 神圣率 | 宝石率 |
|---|---|---|---|---|---|---|---|
| 普通 | 1 | 2 | 0.3 | NoDrop 87.4 / C 9 / U 3 / R 0.6 / L 0 | NoDrop 95 / C 2.5 / U 1.75 / R 0.6 / L 0.15 | 0 | 0.01 |
| 精英 | 1 | 2 | 1 | NoDrop 0 / C 69.5 / U 23 / R 6.5 / L 1 | NoDrop 0 / C 47.5 / U 36 / R 15 / L 1.5 | 3e-06 | 0.06 |
| 小Boss | 2 | 4 | 1 | NoDrop 35.2 / C 33.8 / U 22.5 / R 7 / L 1.5 | NoDrop 10.6 / C 32.4 / U 35 / R 20 / L 2 | 1e-05 | 0.1 |
| Boss | 3 | 5 | 1 | NoDrop 0 / C 60 / U 30 / R 8 / L 2 | NoDrop 0 / C 38 / U 35 / R 24 / L 3 | 1e-05 | 0.12 |
| 神话Boss | 3 | 5 | 1 | NoDrop 0 / C 51.8 / U 30 / R 16.2 / L 2 | NoDrop 0 / C 24 / U 37.5 / R 35 / L 3.5 | 2e-05 | 0.12 |

- 随机装备向量：C 50 / U 32.5 / R 15.3 / L 2.2
- 符文掉落：几率 0.02，最低等级 40，权重 {'Common': 0.0, 'Uncommon': 54.5, 'Rare': 43.29999923706055, 'Legendary': 1.5, 'Divine': 0.0, 'Set': 0.699999988079071}
- 远古概率 AncientChance=0.1，黑雾概率 BlackMistChance=0.002
- 传奇最低等级 10，神圣/套装最低难度 2/2

## 七、物品化配置 ItemizationConfig

| 槽位 Slot | 主词条池(数) | 副词条池(数) | 宝石孔上限 |
|---|---:|---:|---:|
| 1 | 26 | 3 | 3 |
| 2 | 12 | 5 | 1 |
| 3 | 15 | 5 | 2 |
| 4 | 12 | 5 | 2 |
| 5 | 11 | 5 | 0 |
| 6 | 11 | 4 | 0 |
| 7 | 16 | 5 | 1 |
| 8 | 23 | 4 | 1 |
| 9 | 12 | 5 | 0 |
| 10 | 12 | 2 | 0 |
| 11 | 0 | 0 | 0 |

镶嵌开放等级 MinLevelForSockets = 30

各槽位主词条池 Stat 编号：

- Slot 1：`[0, 1, 2, 3, 5, 6, 33, 34, 61, 23, 24, 25, 26, 27, 28, 29, 30, 31, 43, 32, 45, 58, 46, 62, 63, 40]`
- Slot 2：`[0, 1, 2, 7, 14, 13, 8, 9, 22, 44, 54, 55]`
- Slot 3：`[0, 1, 2, 7, 8, 9, 22, 39, 44, 42, 61, 29, 30, 51, 53]`
- Slot 4：`[0, 1, 2, 7, 8, 9, 22, 39, 44, 42, 49, 51]`
- Slot 5：`[0, 1, 2, 7, 8, 9, 22, 37, 53, 52, 60]`
- Slot 6：`[0, 1, 2, 7, 22, 9, 37, 38, 13, 6, 39]`
- Slot 7：`[0, 1, 2, 4, 5, 6, 14, 9, 40, 23, 24, 25, 26, 27, 28, 65]`
- Slot 8：`[0, 1, 2, 4, 5, 6, 13, 9, 33, 34, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 40, 44, 65]`
- Slot 9：`[0, 1, 2, 13, 37, 14, 4, 3, 5, 6, 60, 9]`
- Slot 10：`[0, 1, 2, 7, 8, 9, 22, 13, 49, 52, 60, 39]`

## 八、治疗药水

| 名称 | 立即治疗 | 持续回血(%最大HP) | 持续时间(s) | 冷却(s) |
|---|---|---|---|---|
| HpPotion1 | 25 | 0.3 | 3 | 5 |
| HpPotion2 | 75 | 0.3 | 3 | 5 |
| HpPotion3 | 150 | 0.35 | 3 | 5 |
| HpPotion4 | 300 | 0.35 | 3 | 5 |
| HpPotion5 | 600 | 0.4 | 3 | 5 |
| HpPotion6 | 1000 | 0.4 | 3 | 5 |
| HpPotion7 | 1500 | 0.45 | 3 | 5 |
| HpPotion8 | 2000 | 0.45 | 3 | 5 |

| 档位 | 需求等级 | 金币 | 材料 |
|---|---|---|---|
| 1 | 1 | 0 | — |
| 2 | 5 | 100 | pathID 60044×10, pathID 60045×5 |
| 3 | 15 | 500 | pathID 60044×20, pathID 60045×10 |
| 4 | 25 | 3000 | pathID 60045×50, pathID 60046×30 |
| 5 | 35 | 25000 | pathID 60046×65, pathID 60047×40 |
| 6 | 45 | 80000 | pathID 60047×40, pathID 60048×30 |
| 7 | 55 | 150000 | pathID 60049×35, pathID 60051×50 |
| 8 | 65 | 300000 | pathID 60050×60, pathID 60052×45 |

## 九、技能 AbilityData（124 条）

- 法力消耗 ManaCost：0 ~ 85（中位 0, n=124）
- 冷却 Cooldown：0 ~ 99999（中位 5.5, n=124）
- 施法距离 Range：1 ~ 30（中位 6, n=124）
- 需求等级 LevelRequirement：1 ~ 50（中位 1, n=124）
- Targeting 分布：{0: 66, 1: 16, 2: 3, 3: 10, 4: 11, 5: 6, 7: 8, 8: 1, 9: 2, 10: 1}
- Affinity 分布：{0: 109, 1: 15}

## 十、状态效果 StatusEffectData（95 条）

- 持续时间 Duration：0 ~ 86400（中位 5, n=94）
- 可叠加 19 条；最大层数分布：{1: 73, 2: 1, 5: 5, 10: 3, 20: 3, 25: 1, 50: 1, 100: 7, 2147483647: 1}
- Tick 间隔 TickRate：0 ~ 2（中位 0, n=95）

## 十一、天赋 TalentData（186 条）

- MaxPoints 分布：{1: 63, 2: 1, 3: 2, 5: 25, 6: 29, 8: 44, 10: 22}
- 需求等级 LevelRequirement：0 ~ 100（中位 20, n=186）
- 带 StatModifiers 的节点：38；带 Effects 的节点：135

## 十二、生活技能 LifeSkillNodeData（85 条）

- MaxLevel 分布：{1: 85}
- Notable 节点：31；有前置 Prerequisite：84
- 金币成本：50 ~ 150000（中位 8000, n=85）

## 十三、符文套装 RuneSetData（13 个）

| 套装 | 档位(需求件数) |
|---|---|
| HunterSetRune1 | 2, 4, 6 |
| HunterSetRune2 | 2, 4, 6 |
| HunterSetRune3 | 2, 4, 6 |
| MonkSetRune1 | 2, 4, 6 |
| MonkSetRune2 | 2, 4, 6 |
| MonkSetRune3 | 2, 4, 6 |
| SorcererSetRune1 | 2, 4, 6 |
| SorcererSetRune2 | 2, 4, 6 |
| SorcererSetRune3 | 2, 4, 6 |
| WarriorSetRune1 | 2, 4, 6 |
| WarriorSetRune2 | 2, 4, 6 |
| WarriorSetRune3 | 2, 4, 6 |
| WarriorSetRune4 | 2, 4, 6 |

## 十四、地图 MapData（76 张）

- 敌人等级区间 EnemyMinLevel~MaxLevel：1 ~ 70（中位 40, n=76）
- MapType 分布：{0: 71, 1: 1, 2: 1, 3: 3}
- 精英率 EliteChance：0 ~ 0.05（中位 0, n=76）
- 最大遭遇数 MaxEncounters：1 ~ 12（中位 10, n=76）

**神话(Mythic)参数样例（取自地图 `Beach1`）**：

| 字段 | 值 |
|---|---|
| MythicBaseHP | 70 |
| MythicBaseDamage | 7 |
| MythicBossBaseHP | 5000 |
| MythicBossBaseDamage | 22 |
| MythicBand1EndTier | 70 |
| MythicBand1HealthMultiplierPerTier | 1.17 |
| MythicBand1DamageMultiplierPerTier | 1.0718 |
| MythicBand2HealthMultiplierPerTier | 1.17 |
| MythicBand2DamageMultiplierPerTier | 1.0234 |
| MythicGoldBonusPerTier | 0.05 |
| MythicExpBonusPerTier | 0.05 |

## 十五、敌人 Enemy（65 条）

- BaseMaxHealth：15 ~ 1.2e+07（中位 300, n=65）
- BaseDamage：1 ~ 50（中位 15, n=65）
- BaseMoveSpeed：0.8 ~ 3（中位 1.6, n=65）
- 暴击率 BaseCritChance：0 ~ 0.2（中位 0.1, n=65）
- 闪避 BaseDodgeChance：0 ~ 0.3（中位 0, n=65）
- MythicSize 分布：{1: 8, 2: 27, 3: 30}
- EncounterType 分布：{0: 65}

## 十六、随从 SlaveData（67 条）

- Rarity 分布：{0: 1, 1: 27, 2: 16, 3: 23}
- Capacity：15 ~ 35（中位 25, n=67）
- Species 分布：{0: 9, 1: 29, 2: 5, 3: 10, 4: 7, 5: 7}

## 十七、其他数据

- 任务 QuestData：22 条
- 配方 RecipeData：51 条；输出数量分布 {1: 51}
- 英雄 HeroData：Barbarian(主属性0, 职业1), Hunter(主属性1, 职业4), Sorcerer(主属性2, 职业2), Monk(主属性1, 职业8)
- 钓鱼点 FishingMapData：3；城镇 TownData：3