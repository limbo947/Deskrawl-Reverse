import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import json, collections, os

D = SO_DUMP
def load(n): return json.load(open(os.path.join(D, n + '.json'), encoding='utf-8'))

STAT = {0:'Strength',1:'Dexterity',2:'Intelligence',3:'Damage',4:'CritChance',5:'CritDamage',6:'AttackSpeed',
7:'MaxHealth',8:'Armor',9:'MagicResist',10:'MoveSpeed',11:'LifeOnHit',12:'LifeOnKill',13:'CooldownReduction',
14:'MaxMana',15:'GoldFind',16:'MagicFind',17:'HpPotionFind',18:'Capacity',19:'MaterialFind',20:'WeaponDamage',
21:'WeaponSpeed',22:'Dodge',23:'DamagePhysical',24:'DamageFire',25:'DamageCold',26:'DamageLightning',
27:'DamagePoison',28:'DamageArcane',29:'DamageVsHealthy',30:'DamageVsInjured',31:'DamageVsSlowed',
32:'DamageVsElite',33:'BasicAttackDamage',34:'StrongAttackDamage',35:'ManaOnKill',36:'LifeRegen',
37:'ManaCostReduction',38:'PotionCharges',39:'Thorns',40:'VulnerableDamage',41:'XPGain',42:'MaxHealthPercent',
43:'DamageVsImmobilized',44:'ArmorPercent',45:'DamageVsBleeding',46:'DamageVsPoisoned',47:'ManaRegen',
48:'ThornsDamagePercent',49:'PoisonDamageReduction',50:'GemSlots',51:'PhysicalDamageReduction',
52:'FireDamageReduction',53:'ColdDamageReduction',54:'LightningDamageReduction',55:'ArcaneDamageReduction',
56:'HealingReceivedBonus',57:'MoveSpeedPercent',58:'DamageVsDistant',59:'MagicResistPercent',
60:'CritDamageReduction',61:'SpecialAbilityDamage',62:'DamageOverTime',63:'DamageVsBurned',
64:'DamageReduction',65:'DamagePercent'}
SLOT = {0:'None',1:'Weapon',2:'Helm',3:'Chest',4:'Pants',5:'Boots',6:'Belt',7:'Ring',8:'Necklace',9:'Gloves',
10:'Shoulder',11:'Back'}
MT = {0:'Flat',1:'PctAdd',2:'PctMult'}
RAR = {0:'Common',1:'Uncommon',2:'Rare',3:'Legendary',4:'Divine',5:'RuneSet'}

print('### ItemizationConfig.SlotPools（装备词条池）')
ic = load('ItemizationConfig')[0]
for p in ic['SlotPools']:
    prim = ','.join(STAT.get(s, str(s)) for s in p['Primary'])
    sec = ','.join(STAT.get(s, str(s)) for s in p['Secondary'])
    print(f"- {SLOT.get(p['Slot'],p['Slot'])}: Primary[{len(p['Primary'])}] = {prim}")
    print(f"    Secondary[{len(p['Secondary'])}] = {sec}")
print('GemSockets:', [(SLOT.get(x['Slot'],x['Slot']), x['MaxSockets']) for x in ic['GemSocketsBySlot']], 'MinLevelForSockets=', ic['MinLevelForSockets'])

print('\n### GameConfig.ParagonStats（Paragon 属性池）')
gc = [o for o in load('GameConfig') if not o['IsDemo']][0]
for p in gc['ParagonStats']:
    print(f"- {STAT.get(p['Stat'],p['Stat'])} cat={p['Category']} perPoint={p['ValuePerPoint']:.4f} max={p['MaxPoints']}")

print('\n### GameConfig.DifficultyTiers')
for t in gc['DifficultyTiers']:
    print(f"- diff={t['Difficulty']} HPx{t['EnemyHealthMultiplier']} DMGx{t['EnemyDamageMultiplier']} "
          f"loot/map={t['LootBonusPerMapLevel']} gold/map={t['GoldBonusPerMapLevel']} expx{t['ExpMultiplier']} "
          f"ilvl/map={t['ItemLevelsPerMapLevel']} bossMat={t['BossMaterialMultiplier']}")

print('\n### HealingPotionUpgradeData.Tiers')
for t in load('HealingPotionUpgradeData')[0]['Tiers']:
    print(f"- lvl>={t['RequiredLevel']} gold={t['GoldCost']} mats={[(m['Item']['pathID'], m['Amount']) for m in t['MaterialCosts']]} potion={t['Config']['pathID']}")

print('\n### ItemData 分布 (n=%d)' % len(load('ItemData')))
it = load('ItemData')
c = collections.Counter((o['Type'], o['Rarity']) for o in it)
for k, v in sorted(c.items()): print(f"  Type={k[0]} Rarity={RAR.get(k[1],k[1])}: {v}")
sp = [o['SellPrice'] for o in it if o['SellPrice']]
print('  SellPrice: min=%d max=%d distinct=%d' % (min(sp), max(sp), len(set(sp))))
ms = [o['MaxStackSize'] for o in it]
print('  MaxStackSize 取值:', sorted(set(ms)))
print('  EquipSlot 分布:', collections.Counter(SLOT.get(o['EquipSlot'],o['EquipSlot']) for o in it if o['EquipSlot']).most_common())
fx = sum(1 for o in it if any(o.get('FixedStats') or []))
print('  含 FixedStats 的物品数:', fx)

print('\n### GemData (n=%d)' % len(load('GemData')))
for o in load('GemData'):
    for s in (o.get('FixedStats') or []):
        v = s['Value']
        if isinstance(v, dict): v = v.get('_plain', v)
        print(f"  {o['_name'][:34]:<34} {STAT.get(s['Stat'],s['Stat']):<22} {MT.get(s['Type'],s['Type']):<7} {v}")

print('\n### RuneData 分布 (n=%d)' % len(load('RuneData')))
rd = load('RuneData')
print('  Stat 分布:', collections.Counter(STAT.get(o['Stat'], o['Stat']) for o in rd).most_common())
print('  Modifier 分布:', collections.Counter(MT.get(o['Modifier'], o['Modifier']) for o in rd).most_common())
bases = []
for o in rd:
    v = o.get('Value')
    if isinstance(v, dict):
        b = v.get('Base'); pl = v.get('PerLevel')
        if isinstance(b, dict): b = b.get('_plain', b)
        if isinstance(pl, dict): pl = pl.get('_plain', pl)
        bases.append((b, pl))
print('  示例 Value(Base,PerLevel):', bases[:12])
print('  Rarity 分布:', collections.Counter(RAR.get(o['Rarity'], o['Rarity']) for o in rd).most_common())

print('\n### TalentData (n=%d)' % len(load('TalentData')))
td = load('TalentData')
print('  MaxPoints:', collections.Counter(o['MaxPoints'] for o in td).most_common())
lr = [o['LevelRequirement'] for o in td]
print('  LevelRequirement: min=%d max=%d' % (min(lr), max(lr)))
print('  含 StatModifiers 节点:', sum(1 for o in td if o.get('StatModifiers')))
print('  含 Effects 节点:', sum(1 for o in td if o.get('Effects')))

print('\n### AbilityData (n=%d)' % len(load('AbilityData')))
ab = load('AbilityData')
print('  LevelRequirement:', collections.Counter(o['LevelRequirement'] for o in ab).most_common(12))
print('  Targeting:', collections.Counter(o['Targeting'] for o in ab).most_common())
print('  TargetCount 取值:', sorted(set(o['TargetCount'] for o in ab)))
mg = [o['ManaGain'] for o in ab]
print('  ManaGain 非零数量:', sum(1 for x in mg if x), 'max=', max(mg))
cds = []
for o in ab:
    cd = o.get('Cooldown'); 
    if isinstance(cd, dict):
        b = cd.get('Base')
        if isinstance(b, dict): b = b.get('_plain')
        if b: cds.append(b)
print('  Cooldown.Base 非零数量:', len(cds), 'range=', (min(cds), max(cds)) if cds else None)
print('  含 Effects 数:', sum(1 for o in ab if o.get('Effects')))

print('\n### MapData (n=%d)' % len(load('MapData')))
md = load('MapData')
print('  MapType:', collections.Counter(o['MapType'] for o in md).most_common())
print('  EnemyMinLevel range:', min(o['EnemyMinLevel'] for o in md), max(o['EnemyMinLevel'] for o in md))
print('  EnemyMaxLevel range:', min(o['EnemyMaxLevel'] for o in md), max(o['EnemyMaxLevel'] for o in md))
print('  EliteChance 取值:', sorted(set(round(o['EliteChance'],3) for o in md)))
print('  MaxEncounters 取值:', sorted(set(o['MaxEncounters'] for o in md)))

print('\n### Enemy (n=%d)' % len(load('Enemy')))
en = load('Enemy')
print('  MythicSize:', collections.Counter(o['MythicSize'] for o in en).most_common())
print('  Abilities 数分布:', collections.Counter(len(o.get('Abilities') or []) for o in en).most_common())
print('  DropsLoot=True:', sum(1 for o in en if o['DropsLoot']))

print('\n### RuneSetData (n=%d)' % len(load('RuneSetData')))
for o in load('RuneSetData'):
    mods = o.get('Modifiers') or []
    txt = ','.join(f"{STAT.get(m['Stat'],m['Stat'])}:{MT.get(m['Type'],m['Type'])}" for m in mods)
    print(f"  {o['_name'][:30]:<30} need={o['RequiredCount']} mods=[{txt}]")
