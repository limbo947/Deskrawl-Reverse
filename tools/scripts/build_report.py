import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
# -*- coding: utf-8 -*-
import json, os, glob, statistics as st

D = SO_DUMP
OUT = REPORT_DATA

def load(n):
    return json.load(open(os.path.join(D, n), encoding='utf-8'))

def val(x):
    """unwrap Obscured* / LeveledFloat{Base} to a plain number if possible."""
    if isinstance(x, (int, float)):
        return x
    if isinstance(x, dict):
        if 'value' in x and isinstance(x['value'], (int, float)):
            return x['value']
        if 'Base' in x:
            return val(x['Base'])
    return None

def num(vals):
    # 过滤阈值是防御性护栏：2026-10-10 前 decode.py 的 ACTk 公式写错时，
    # 会把 0 解成 1e-38 反常量、把整数解成 1e18 量级，这里兜底剔除以免再次污染报表。
    out = []
    for v in vals:
        if not isinstance(v, (int, float)):
            continue
        if isinstance(v, float) and v != v:  # NaN
            continue
        a = abs(v)
        if a > 1e9 or (0 < a < 1e-6):
            continue
        out.append(v)
    return out

def stat(vals):
    vals = num(vals)
    if not vals: return '—'
    med = st.median(vals)
    return f'{min(vals):g} ~ {max(vals):g}（中位 {med:g}, n={len(vals)}）'

RARITY = {0:'Common',1:'Uncommon',2:'Rare',3:'Legendary',4:'Divine',5:'Set'}

L = []
def w(s=''):
    L.append(s)

# ---------- overview ----------
files = sorted(glob.glob(os.path.join(D, '*.json')))
w('## 一、数据文件总览\n')
w('| 文件 | 记录数 | 主要用途 |')
w('|---|---:|---|')
USE = {
 'GameConfig':'全局数值配置（等级/成长/锻造/镶嵌/巅峰/离线）',
 'LootConfig':'掉落向量与稀有度权重',
 'ItemizationConfig':'装备词条池与宝石孔',
 'HealthPotionConfig':'血瓶档位效果',
 'HealingPotionUpgradeData':'血瓶升级配方',
 'HeroData':'职业英雄定义',
 'ItemData':'装备/材料物品库',
 'GemData':'宝石库',
 'RuneData':'符文库',
 'RuneSetData':'符文套装效果',
 'AbilityData':'技能定义',
 'StatusEffectData':'状态/Buff定义',
 'TalentData':'天赋树节点',
 'LifeSkillNodeData':'生活技能节点',
 'SlaveData':'宠物/随从',
 'Enemy':'敌人定义',
 'MapData':'地图关卡',
 'QuestData':'任务',
 'RecipeData':'合成配方',
 'FishingMapData':'钓鱼点',
 'TownData':'城镇',
 # 2026-10-10 新增的 4 个特效/系数资产文件（非「SO 实例」口径，见 docs/09 §B 说明）
 'AffixRollTable':'装备词条 Roll 系数表',
 'EquipmentEffects':'装备特效定义（按稀有度索引）',
 'LifeSkillEffects':'生活技能特效',
 'TalentEffects':'天赋特效',
}
tot = 0; main_tot = 0; n_aux = 0
AUX = {'AffixRollTable', 'EquipmentEffects', 'LifeSkillEffects', 'TalentEffects'}
for f in files:
    b = os.path.basename(f); n = len(json.load(open(f, encoding='utf-8')))
    tot += n
    if b[:-5] in AUX: n_aux += 1
    else: main_tot += n
    w(f'| `{b}` | {n} | {USE.get(b[:-5], "")} |')
w(f'| **合计** | **{tot}** | {len(files)} 个文件（{len(files)-n_aux} 个主数据 + {n_aux} 个特效/系数资产） |')
w()
w(f'> 第 07 篇引用的「1333 条 SO 实例」指 {len(files)-n_aux} 个主数据文件（实测 {main_tot} 条）；'
  f'另有 {n_aux} 个特效/系数资产文件（{tot - main_tot} 条）不计入该口径。')
w()

# ---------- item-like ----------
def item_stats(fname, title):
    j = load(fname)
    w(f'## {title}（`{fname}`，{len(j)} 条）\n')
    from collections import Counter
    tc = Counter(val(x.get('Type')) for x in j)
    rc = Counter(val(x.get('Rarity')) for x in j)
    w('- **按 Type 分布**：' + ', '.join(f'Type {int(k)}={v}' for k,v in sorted(tc.items(), key=lambda z:(z[0] is None, z[0]))))
    w('- **按 Rarity 分布**：' + ', '.join(f'{RARITY.get(int(k), int(k))}={v}' for k,v in sorted(rc.items(), key=lambda z:(z[0] is None, z[0]))))
    w('- **售价 SellPrice**：' + stat([x.get('SellPrice') for x in j]))
    w('- **掉落等级 MinDropLevel**：' + stat([x.get('MinDropLevel') for x in j]))
    w()

item_stats('ItemData.json', '二、装备/材料库')
item_stats('GemData.json', '三、宝石库')
item_stats('RuneData.json', '四、符文库')

# ---------- GameConfig ----------
gc = [x for x in load('GameConfig.json') if x['_name'] == 'GameConfig'][0]
w('## 五、全局配置 GameConfig（正式版）\n')
rows = [
 ('最大等级 MaxPlayerLevel', gc['MaxPlayerLevel']),
 ('离线时长上限(h)', gc['OfflineTimeCapHours']),
 ('称号巅峰/级 ParagonPointsPerLevel', gc['ParagonPointsPerLevel']),
 ('装备最大强化等级', gc['MaxEquipmentUpgradeLevel']),
 ('镶嵌材料数量/孔', gc['SocketMaterialAmount']),
 ('镶嵌金币/物品等级', gc['SocketGoldPerItemLevel']),
 ('天赋洗点/点', gc['TalentRefundCostPerPointSpent']),
 ('精英血量×', gc['EliteHealthMultiplier']),
 ('精英伤害×', gc['EliteDamageMultiplier']),
 ('精英体型×', gc['EliteScaleMultiplier']),
 ('精英怪等级0-30 血量成长', gc['EnemyHealthGrowthPerLevel0To30']),
 ('精英怪等级0-30 伤害成长', gc['EnemyDamageGrowthPerLevel0To30']),
 ('技能最大等级', gc['MaxAbilityLevel']),
 ('技能升1级基础XP', gc['AbilityBaseXPToLevel']),
 ('技能XP成长/级', gc['AbilityXPGrowthPerLevel']),
 ('符文最大等级', gc['MaxRuneLevel']),
 ('符文升1级基础XP', gc['RuneBaseXPToLevel']),
 ('符文XP成长/级', gc['RuneXPGrowthPerLevel']),
 ('经验/基础血量 XpPerBaseHealth', gc['XpPerBaseHealth']),
 ('经验等级缩放 XpPerLevelScale', gc['XpPerLevelScale']),
 ('低于此等级差无经验', gc['XpZeroUnderLevel']),
 ('离线每金币产出怪数', gc['OfflineMobsPerGoldRoll']),
]
w('| 常量 | 值 |')
w('|---|---|')
for k,v in rows: w(f'| {k} | {v:g} |')
w()
w('**升级所需击杀数（MobsToLevel）**：Lv1=%d, Lv5=%d, Lv15=%d, Lv50=%d, 满级=%d\n' % (
    gc['MobsToLevelAtLevel1'], gc['MobsToLevelAtLevel5'], gc['MobsToLevelAtLevel15'],
    gc['MobsToLevelAtLevel50'], gc['MobsToLevelAtMaxLevel']))
w('**强化成功率 UpgradeSuccessChances**（1→12 级）：' + ', '.join(f'{v:g}' for v in gc['UpgradeSuccessChances']) + '\n')
w('**难度档 DifficultyTiers**：\n')
w('| 难度 | 敌人血量× | 敌人伤害× | 经验× | 掉落/地图级 | 金币/地图级 | 物品等级/地图级 | Boss材料× |')
w('|---|---|---|---|---|---|---|---|')
for d in gc['DifficultyTiers']:
    w(f"| {d['Difficulty']} | {d['EnemyHealthMultiplier']:g} | {d['EnemyDamageMultiplier']:g} | {d['ExpMultiplier']:g} | "
      f"{d['LootBonusPerMapLevel']:g} | {d['GoldBonusPerMapLevel']:g} | {d['ItemLevelsPerMapLevel']} | {d['BossMaterialMultiplier']:g} |")
w()
w('**巅峰属性 ParagonStats**（Stat / 每点收益 / 上限）：\n')
w('| Stat | 类别 | 每点 | 上限 |')
w('|---|---|---|---|')
for p in gc['ParagonStats']:
    w(f"| {p['Stat']} | {p['Category']} | {p['ValuePerPoint']:g} | {p['MaxPoints']} |")
w()

# ---------- LootConfig ----------
w('## 六、掉落配置 LootConfig（正式版）\n')
lc = [x for x in load('LootConfig.json') if x['_name'] == 'LootConfig'][0]
def vector(v):
    parts = []
    for k, s in (('NoDrop','NoDrop'),('Common','C'),('Uncommon','U'),('Rare','R'),('Legendary','L')):
        if k in v:
            parts.append(f'{s} {v[k]:g}')
    return ' / '.join(parts)
w('| 敌人档 | 掷骰次数 | 金币× | 药水掉落 | 最小向量 | 最大向量 | 神圣率 | 宝石率 |')
w('|---|---|---|---|---|---|---|---|')
for key, label in [('NormalDropSettings','普通'),('EliteDropSettings','精英'),('MiniBossDropSettings','小Boss'),('BossDropSettings','Boss'),('MythicBossDropSettings','神话Boss')]:
    s = lc[key]
    w(f"| {label} | {s['RollAttempts']} | {s['GoldMultiplier']:g} | {s['PotionChargeDropChance']:g} | {vector(s['MinLootVector'])} | {vector(s['MaxLootVector'])} | {s['DivineChance']:g} | {s['GemDropChance']:g} |")
w()
w(f"- 随机装备向量：{vector(lc['RandomEquipmentLootVector'])}")
w(f"- 符文掉落：几率 {lc['RuneDrops']['DropChance']:g}，最低等级 {lc['RuneDrops']['MinDropLevel']}，权重 {lc['RuneDrops']['RarityWeights']}")
w(f"- 远古概率 AncientChance={lc['AncientChance']:g}，黑雾概率 BlackMistChance={lc['BlackMistChance']:g}")
w(f"- 传奇最低等级 {lc['MinLegendaryLevel']}，神圣/套装最低难度 {lc['MinDivineDifficulty']}/{lc['MinSetDifficulty']}")
w()

# ---------- Itemization ----------
w('## 七、物品化配置 ItemizationConfig\n')
ic = load('ItemizationConfig.json')[0]
w('| 槽位 Slot | 主词条池(数) | 副词条池(数) | 宝石孔上限 |')
w('|---|---:|---:|---:|')
sock = {g['Slot']: g['MaxSockets'] for g in ic['GemSocketsBySlot']}
for p in ic['SlotPools']:
    w(f"| {p['Slot']} | {len(p['Primary'])} | {len(p['Secondary'])} | {sock.get(p['Slot'], '-')} |")
w(f"\n镶嵌开放等级 MinLevelForSockets = {ic['MinLevelForSockets']}")
w("\n各槽位主词条池 Stat 编号：\n")
for p in ic['SlotPools']:
    if p['Primary']:
        w(f"- Slot {p['Slot']}：`{p['Primary']}`")
w()

# ---------- potions ----------
w('## 八、治疗药水\n')
hp = load('HealthPotionConfig.json')
w('| 名称 | 立即治疗 | 持续回血(%最大HP) | 持续时间(s) | 冷却(s) |')
w('|---|---|---|---|---|')
for p in hp:
    w(f"| {p['_name']} | {val(p['InstantHealAmount']):g} | {val(p['HotMaxHPFraction']):g} | {val(p['HotDuration']):g} | {val(p['Cooldown']):g} |")
w()
tiers = load('HealingPotionUpgradeData.json')[0]['Tiers']
w('| 档位 | 需求等级 | 金币 | 材料 |')
w('|---|---|---|---|')
for i,t in enumerate(tiers,1):
    mats = ', '.join(f"pathID {m['Item']['pathID']}×{m['Amount']}" for m in t['MaterialCosts']) or '—'
    w(f"| {i} | {t['RequiredLevel']} | {t['GoldCost']} | {mats} |")
w()

# ---------- abilities ----------
ab = load('AbilityData.json')
w(f'## 九、技能 AbilityData（{len(ab)} 条）\n')
w('- 法力消耗 ManaCost：' + (stat([val(x.get('ManaCost')) for x in ab]) or '—'))
w('- 冷却 Cooldown：' + (stat([val(x.get('Cooldown')) for x in ab]) or '—'))
w('- 施法距离 Range：' + (stat([val(x.get('Range')) for x in ab]) or '—'))
w('- 需求等级 LevelRequirement：' + (stat([val(x.get('LevelRequirement')) for x in ab]) or '—'))
from collections import Counter
w('- Targeting 分布：' + str(dict(sorted(Counter(int(val(x['Targeting'])) for x in ab if val(x['Targeting']) is not None).items()))))
w('- Affinity 分布：' + str(dict(sorted(Counter(int(val(x['Affinity'])) for x in ab if val(x['Affinity']) is not None).items()))))
w()

# ---------- statuses ----------
se = load('StatusEffectData.json')
w(f'## 十、状态效果 StatusEffectData（{len(se)} 条）\n')
w('- 持续时间 Duration：' + (stat([val(x.get('Duration')) for x in se]) or '—'))
stack = sum(1 for x in se if x.get('Stackable'))
w(f'- 可叠加 {stack} 条；最大层数分布：' + str(dict(sorted(Counter(int(val(x['MaxStacks'])) for x in se if val(x['MaxStacks']) is not None).items()))))
w('- Tick 间隔 TickRate：' + (stat([val(x.get('TickRate')) for x in se]) or '—'))
w()

# ---------- talents ----------
ta = load('TalentData.json')
w(f'## 十一、天赋 TalentData（{len(ta)} 条）\n')
w('- MaxPoints 分布：' + str(dict(sorted(Counter(int(val(x['MaxPoints'])) for x in ta if val(x['MaxPoints']) is not None).items()))))
w('- 需求等级 LevelRequirement：' + (stat([val(x.get('LevelRequirement')) for x in ta]) or '—'))
w(f"- 带 StatModifiers 的节点：{sum(1 for x in ta if x.get('StatModifiers'))}；带 Effects 的节点：{sum(1 for x in ta if x.get('Effects'))}")
w()

# ---------- life skills ----------
ls = load('LifeSkillNodeData.json')
w(f'## 十二、生活技能 LifeSkillNodeData（{len(ls)} 条）\n')
w('- MaxLevel 分布：' + str(dict(sorted(Counter(int(val(x['MaxLevel'])) for x in ls if val(x['MaxLevel']) is not None).items()))))
w(f"- Notable 节点：{sum(1 for x in ls if x.get('IsNotable'))}；有前置 Prerequisite：{sum(1 for x in ls if x.get('Prerequisite'))}")
gold = [g for x in ls for g in x.get('GoldCosts', [])]
w('- 金币成本：' + (stat(gold) or '—'))
w()

# ---------- rune sets ----------
rs = load('RuneSetData.json')
w(f'## 十三、符文套装 RuneSetData（{len(rs)} 个）\n')
w('| 套装 | 档位(需求件数) |')
w('|---|---|')
for s in rs:
    w(f"| {s['_name']} | {', '.join(str(b['RequiredCount']) for b in s['Bonuses'])} |")
w()

# ---------- maps ----------
mp = load('MapData.json')
w(f'## 十四、地图 MapData（{len(mp)} 张）\n')
w('- 敌人等级区间 EnemyMinLevel~MaxLevel：' + stat([val(x.get('EnemyMinLevel')) for x in mp]))
w('- MapType 分布：' + str(dict(sorted(Counter(int(val(x['MapType'])) for x in mp if val(x['MapType']) is not None).items()))))
w('- 精英率 EliteChance：' + (stat([val(x.get('EliteChance')) for x in mp]) or '—'))
w('- 最大遭遇数 MaxEncounters：' + (stat([val(x.get('MaxEncounters')) for x in mp]) or '—'))
d0 = next(x for x in mp if val(x.get('MythicBand1EndTier')) and x['_name'] and x['_name'] != 'LockedMap')
w(f"\n**神话(Mythic)参数样例（取自地图 `{d0['_name']}`）**：\n")
w('| 字段 | 值 |')
w('|---|---|')
for k in ['MythicBaseHP','MythicBaseDamage','MythicBossBaseHP','MythicBossBaseDamage','MythicBand1EndTier',
          'MythicBand1HealthMultiplierPerTier','MythicBand1DamageMultiplierPerTier',
          'MythicBand2HealthMultiplierPerTier','MythicBand2DamageMultiplierPerTier',
          'MythicGoldBonusPerTier','MythicExpBonusPerTier']:
    v = val(d0.get(k))
    if v is not None: w(f"| {k} | {v:g} |")
w()

# ---------- enemies ----------
en = load('Enemy.json')
w(f'## 十五、敌人 Enemy（{len(en)} 条）\n')
# ObscuredLong 的取值公式已于 2026-10-10 修正（(hidden-key) XOR key），故这里直接给值，不再打 ⚠️
w('- BaseMaxHealth：' + stat([val(x.get('BaseMaxHealth')) for x in en]))
w('- BaseDamage：' + stat([val(x.get('BaseDamage')) for x in en]))
w('- BaseMoveSpeed：' + stat([val(x.get('BaseMoveSpeed')) for x in en]))
w('- 暴击率 BaseCritChance：' + (stat([val(x.get('BaseCritChance')) for x in en]) or '—'))
w('- 闪避 BaseDodgeChance：' + (stat([val(x.get('BaseDodgeChance')) for x in en]) or '—'))
w('- MythicSize 分布：' + str(dict(sorted(Counter(int(val(x['MythicSize'])) for x in en if val(x['MythicSize']) is not None).items()))))
w(f"- EncounterType 分布：{dict(sorted(Counter(int(val(x['EncounterType'])) for x in en if val(x['EncounterType']) is not None).items()))}")
w()

# ---------- slaves ----------
sl = load('SlaveData.json')
w(f'## 十六、随从 SlaveData（{len(sl)} 条）\n')
w('- Rarity 分布：' + str(dict(sorted(Counter(int(val(x['Rarity'])) for x in sl if val(x['Rarity']) is not None).items()))))
w('- Capacity：' + stat([val(x.get('Capacity')) for x in sl]))
w('- Species 分布：' + str(dict(sorted(Counter(int(val(x['Species'])) for x in sl if val(x['Species']) is not None).items()))))
w()

# ---------- misc ----------
w('## 十七、其他数据\n')
qa = load('QuestData.json'); rc = load('RecipeData.json')
w(f"- 任务 QuestData：{len(qa)} 条")
w(f"- 配方 RecipeData：{len(rc)} 条；输出数量分布 {dict(sorted(Counter(int(val(x['OutputQuantity'])) for x in rc if val(x['OutputQuantity']) is not None).items()))}")
hm = load('HeroData.json')
w('- 英雄 HeroData：' + ', '.join(f"{h['HeroName']}(主属性{val(h['PrimaryStat'])}, 职业{val(h['Class'])})" for h in hm))
w(f"- 钓鱼点 FishingMapData：{len(load('FishingMapData.json'))}；城镇 TownData：{len(load('TownData.json'))}")

open(OUT, 'w', encoding='utf-8').write('\n'.join(L))
print('report body written to', OUT, 'lines', len(L))
