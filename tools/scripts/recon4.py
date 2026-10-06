import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import UnityPy, os
BASE = GAME_DATA
env = UnityPy.load(os.path.join(BASE,'resources.assets'))
for fkey, sf in env.files.items():
    print('ver', sf.header.version, 'enable_tt', sf._enable_type_tree, 'nref', len(sf.ref_types or []))
    for i,t in enumerate((sf.ref_types or [])[:12]):
        print(i, t.__dict__)
    break
