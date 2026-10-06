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
MT={0:'Flat',1:'PctAdd',2:'PctMult'}
RAR={0:'Common',1:'Uncommon',2:'Rare',3:'Legendary',4:'Divine',5:'RuneSet'}
def sn(x): return STAT.get(x, str(x))

print('### GemData（36 个宝石，按槽位类别给不同加成）')
for o in load('GemData'):
    parts=[]
    for key,label in [('ArmorBonuses','护甲类'),('AccessoryBonuses','饰品类'),('WeaponBonuses','武器类')]:
        for b in (o.get(key) or []):
            parts.append(f"{label}:{sn(b['Stat'])}:{MT.get(b['Modifier'],b['Modifier'])}:{b['Value']:.4g}")
    print(f"  {o['_name'][:22]:<22} R={RAR.get(o['Rarity'],o['Rarity']):<9} lvl={o['MinDropLevel']}-{o['MaxDropLevel']:<4} price={o['SellPrice']:<7} stack={o['MaxStackSize']} | " + '; '.join(parts))

print('\n### RuneData（151 个符文，共 21 个套装）')
rd=load('RuneData')
print('  套装(Set) 引用数:', collections.Counter((o.get('Set') or {}).get('pathID') for o in rd).most_common(25))
print('  AllowDuplicateEquip=True:', sum(1 for o in rd if o.get('AllowDuplicateEquip')))
at=collections.Counter()
for o in rd:
    for a in (o.get('Attributes') or []):
        at[(sn(a['Stat']), MT.get(a['Modifier'],a['Modifier']))]+=1
print('  属性分布:', at.most_common(30))
samples=[]
for o in rd:
    for a in (o.get('Attributes') or []):
        v=a['Value']
        if isinstance(v,dict):
            b=v.get('Base'); pl=v.get('PerLevel')
            def flat(x):
                if isinstance(x,dict): return x.get('_plain', x.get('value', x))
                return x
            samples.append((o['_name'][:24], sn(a['Stat']), MT.get(a['Modifier'],a['Modifier']), flat(b), flat(pl)))
print('  Value(Base,PerLevel) 样例:')
for s in samples[:18]: print('   ', s)
print('  含 Effects 的符文:', sum(1 for o in rd if o.get('Effects')))

print('\n### TalentData（186）')
td=load('TalentData')
print('  MaxPoints:', collections.Counter(o['MaxPoints'] for o in td).most_common())
lr=[o['LevelRequirement'] for o in td]; print('  LevelRequirement: %d..%d'%(min(lr),max(lr)))
print('  含 StatModifiers:', sum(1 for o in td if o.get('StatModifiers')), ' 含 Effects:', sum(1 for o in td if o.get('Effects')))
print('  前置链数量(有 Prerequisite):', sum(1 for o in td if o.get('Prerequisite')))
eg=collections.Counter(o.get('ExclusiveGroup') for o in td if o.get('ExclusiveGroup'))
print('  互斥组数:', len(eg), eg.most_common(5))

print('\n### AbilityData（124）')
ab=load('AbilityData')
print('  LevelRequirement 分布:', collections.Counter(o['LevelRequirement'] for o in ab).most_common())
print('  Targeting 分布:', collections.Counter(o['Targeting'] for o in ab).most_common())
print('  TargetCount:', sorted(set(o['TargetCount'] for o in ab)))
print('  AoERadius 取值数:', len(set(o['AoERadius'] for o in ab)), ' 非零:', sum(1 for o in ab if o['AoERadius']))
print('  含 Effects:', sum(1 for o in ab if o.get('Effects')), ' 含 ChannelDuration:', sum(1 for o in ab if o.get('ChannelDuration')))
print('  含 Tags 数:', collections.Counter(len(o.get('Tags') or []) for o in ab).most_common(8))

print('\n### MapData（76）')
md=load('MapData')
print('  MapType:', collections.Counter(o['MapType'] for o in md).most_common())
print('  EliteChance:', sorted(set(round(o['EliteChance'],3) for o in md)))
print('  MaxEncounters:', sorted(set(o['MaxEncounters'] for o in md)))
print('  IsMiniBoss=True:', sum(1 for o in md if o['IsMiniBoss']))
myth=[o for o in md if o['MapType']==1]
print('  神话地图数:', len(myth))
for o in myth[:4]:
    print(f"    {o['_name'][:26]:<26} HP={o['MythicBaseHP']} DMG={o['MythicBaseDamage']} BossHP={o['MythicBossBaseHP']} BossDMG={o['MythicBossBaseDamage']} band1End={o['MythicBand1EndTier']} b1HPx={o['MythicBand1HealthMultiplierPerTier']} b2HPx={o['MythicBand2HealthMultiplierPerTier']}")

print('\n### Enemy（65）')
en=load('Enemy')
print('  MythicSize:', collections.Counter(o['MythicSize'] for o in en).most_common())
print('  DropsLoot:', sum(1 for o in en if o['DropsLoot']), ' 有 Phases:', sum(1 for o in en if o.get('Phases')), ' 有 SpecialDrops:', sum(1 for o in en if o.get('SpecialDrops')))
print('  Abilities 数:', collections.Counter(len(o.get('Abilities') or []) for o in en).most_common())

print('\n### RuneSetData（13）')
for o in load('RuneSetData'):
    mods=o.get('Modifiers') or []
    txt=','.join(f"{sn(m['Stat'])}/{MT.get(m['Type'],m['Type'])}" for m in mods)
    print(f"  {o['_name'][:26]:<26} need={o['RequiredCount']} mods[{len(mods)}]={txt} effects={len(o.get('Effects') or [])} skills={len(o.get('AbilityLevels') or [])}")

print('\n### LifeSkillNodeData（85）')
ls=load('LifeSkillNodeData')
print('  MaxLevel:', collections.Counter(o['MaxLevel'] for o in ls).most_common())
print('  GoldCosts 样例:', [ (o['_name'][:18], o['GoldCosts'][:4]) for o in ls[:5]])
print('  IsNotable=True:', sum(1 for o in ls if o['IsNotable']), ' 有前置:', sum(1 for o in ls if o.get('Prerequisite')))

print('\n### SlaveData（67）')
sd=load('SlaveData')
print('  Species:', collections.Counter(o['Species'] for o in sd).most_common())
print('  Rarity:', collections.Counter(RAR.get(o['Rarity'],o['Rarity']) for o in sd).most_common())
print('  Capacity:', sorted(set(o['Capacity'] for o in sd)))
print('  Abilities 数:', collections.Counter(len(o.get('Abilities') or []) for o in sd).most_common(8))

print('\n### RecipeData（51）')
rc=load('RecipeData')
print('  GoldCost:', sorted(set(o['GoldCost'] for o in rc))[:20])
print('  OutputQuantity:', collections.Counter(o['OutputQuantity'] for o in rc).most_common())
