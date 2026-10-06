import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
"""Decode Deskrawl ScriptableObject assets to JSON using the reconstructed schema."""
import UnityPy, os, json, sys
sys.path.insert(0, TOOLS)
import decode
from decode import decode_object

BASE = GAME_DATA
CACHE = json.load(open(ASSETS_CACHE))
OUT = SO_DUMP
os.makedirs(OUT, exist_ok=True)

TARGETS = ['GameConfig', 'ItemizationConfig', 'LootConfig', 'HealthPotionConfig',
           'HealingPotionUpgradeData', 'HeroData', 'SlaveData', 'RecipeData',
           'RuneSetData', 'LifeSkillNodeData', 'Enemy', 'QuestData', 'MapData',
           'FishingMapData', 'TownData', 'GemData', 'RuneData', 'ItemData',
           'AbilityData', 'StatusEffectData', 'TalentData']

env = UnityPy.load(os.path.join(BASE,'resources.assets'), os.path.join(BASE,'sharedassets0.assets'),
                   os.path.join(BASE,'globalgamemanagers.assets'), os.path.join(BASE,'level0'))
objs = {}
for fk, sf in env.files.items():
    fn = os.path.basename(getattr(sf,'name',str(fk)))
    for o in sf.objects.values():
        objs[(fn,o.path_id)] = o

report = []
for cls in TARGETS:
    insts = CACHE['objects'].get(cls, [])
    out = []
    leftover_counts = {}
    err = 0
    for fname, pid in insts:
        if (fname,pid) not in objs:
            continue
        raw = objs[(fname,pid)].get_raw_data()
        try:
            name, obj, end = decode_object(raw, cls)
        except Exception as e:
            err += 1
            continue
        left = len(raw) - end
        leftover_counts[left] = leftover_counts.get(left, 0) + 1
        rec = {'_name': name, '_pathid': pid, '_file': fname}
        if left:
            rec['_trailing_managed_ref_table_bytes'] = left
        rec.update(obj)
        out.append(rec)
    with open(os.path.join(OUT, cls + '.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, default=str)
    report.append((cls, len(out), err, dict(sorted(leftover_counts.items()))))
    print(f'{cls:26} instances={len(out):4} errors={err} trailing={dict(sorted(leftover_counts.items()))}')

print('\nJSON written to', OUT)
