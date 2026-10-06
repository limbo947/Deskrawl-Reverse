import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import json, os, sys, math, collections
sys.path.insert(0, TOOLS)
import decode, schema
from schema import serialized_fields, load_type

OUT = SO_DUMP
def load(c): return json.load(open(os.path.join(OUT, c + '.json'), encoding='utf-8'))

def walk(o, path=''):
    if isinstance(o, dict):
        if '__type__' in o and 'value' in o:
            yield path, o['value']; return
        for k, v in o.items():
            yield from walk(v, f'{path}.{k}' if path else k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, f'{path}[{i}]')

print('=== [Range(0,1)] fields, expect all in [0,1] ===')
checks = [('ItemData', ['ChestCommonChance','ChestUncommonChance','ChestRareChance','ChestLegendaryChance','ChestDivineChance','ChestGemChance']),
          ('MapData', ['EliteChance','MythicBand1HealthMultiplierPerTier','MusicVolume','MusicVolume2']),
          ('GameConfig', ['UpgradeSuccessChances'])]
for cls, names in checks:
    data = load(cls)
    for nm in names:
        vals = []
        for r in data:
            v = r.get(nm)
            if v is None: continue
            if isinstance(v, list): vals += [x for x in v if isinstance(x,(int,float))]
            elif isinstance(v,(int,float)): vals.append(v)
        if not vals: print(f'  {cls}.{nm}: (no data)'); continue
        bad = [x for x in vals if not (-1e-6 <= x <= 1.0000001)]
        print(f'  {cls}.{nm}: n={len(vals)} range=[{min(vals):.4g},{max(vals):.4g}] out_of_range={len(bad)}')

print('\n=== integer plausibility ===')
for cls, nm, lo, hi in [('AbilityData','LevelRequirement',1,70), ('ItemData','SellPrice',0,100000),
                        ('ItemData','MaxStackSize',1,10000), ('GameConfig','MaxPlayerLevel',1,200),
                        ('TalentData','MaxPoints',1,100), ('TalentData','LevelRequirement',1,70)]:
    data = load(cls); vals=[r[nm] for r in data if isinstance(r.get(nm),int)]
    bad=[v for v in vals if not (lo<=v<=hi)]
    print(f'  {cls}.{nm}: n={len(vals)} range=[{min(vals)},{max(vals)}] out_of_expected={len(bad)} {bad[:6]}')

print('\n=== garbage / validity scan ===')
for c in sorted(os.listdir(OUT)):
    data = json.load(open(os.path.join(OUT,c), encoding='utf-8'))
    reps = 0; nan = 0
    for r in data:
        for p,v in walk(r):
            if isinstance(v,str) and '\ufffd' in v: reps += 1
            if isinstance(v,float) and (math.isnan(v) or math.isinf(v)): nan += 1
    print(f'  {c[:-5]:26} records={len(data):4} invalid_utf8_strings={reps} nan_inf={nan}')

print('\n=== GameConfig (all fields, both instances) ===')
gc = load('GameConfig')
for r in gc:
    print(f'--- _name={r["_name"]!r} _pathid={r["_pathid"]} _file={r["_file"]}')
    for k, v in r.items():
        if k.startswith('_'): continue
        print(f'    {k} = {json.dumps(v, ensure_ascii=False, default=str)}')

print('\n=== HeroData (all 4 instances, all fields) ===')
for r in load('HeroData'):
    print(f'--- _name={r["_name"]!r} _pathid={r["_pathid"]}')
    for k, v in r.items():
        if k.startswith('_'): continue
        print(f'    {k} = {json.dumps(v, ensure_ascii=False, default=str)}')
