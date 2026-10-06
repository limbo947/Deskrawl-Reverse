import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import json, os

D = SO_DUMP
for name in ('GameConfig.json', 'LootConfig.json', 'ItemizationConfig.json', 'HealingPotionUpgradeData.json'):
    j = json.load(open(os.path.join(D, name), encoding='utf-8'))
    print('='*90)
    print(name, len(j))
    print(json.dumps(j, ensure_ascii=False, indent=1)[:12000])
