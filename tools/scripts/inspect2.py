import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import json, os
D = SO_DUMP
def load(n): return json.load(open(os.path.join(D, n), encoding='utf-8'))

def show(fname, fields, want_nonempty=None, k=3):
    j = load(fname)
    print('='*100)
    print(fname, len(j))
    shown = 0
    for x in j:
        if want_nonempty and not any(x.get(f) for f in want_nonempty):
            continue
        sub = {f: x.get(f) for f in fields}
        print('  _name=', x.get('_name'))
        print('   ', json.dumps(sub, ensure_ascii=False)[:900])
        shown += 1
        if shown >= k: break
    if shown == 0:
        print('   (没有非空样本) 首条:', json.dumps({f: j[0].get(f) for f in fields}, ensure_ascii=False)[:600])

show('ItemData.json', ['Type','Rarity','FixedStats','EquipmentEffects','AbilityLevels','Effect'], ['FixedStats','EquipmentEffects','AbilityLevels'])
show('GemData.json', ['Type','Rarity','Effect','FixedStats','ArmorBonuses','AccessoryBonuses','WeaponBonuses','BuffEffect'], ['ArmorBonuses','FixedStats','WeaponBonuses'])
show('RuneData.json', ['Type','Rarity','Attributes','Effects','Set'], ['Attributes','Effects'])
show('TalentData.json', ['MaxPoints','StatModifiers','Effects'], ['StatModifiers'])
show('RuneSetData.json', ['Bonuses'], ['Bonuses'], 2)
show('StatusEffectData.json', ['Duration','Behaviors','MaxStacks'], ['Behaviors'], 2)
show('AbilityData.json', ['ManaCost','Cooldown','Effects'], ['Effects'], 2)
show('LifeSkillNodeData.json', ['MaxLevel','Effects'], ['Effects'], 2)
