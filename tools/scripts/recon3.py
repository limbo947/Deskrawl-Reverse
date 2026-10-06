import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import UnityPy, os, json, binascii

BASE = GAME_DATA
env = UnityPy.load(os.path.join(BASE,'resources.assets'))
for fkey, sf in env.files.items():
    print('FILE', fkey, type(sf).__name__, getattr(sf,'name',None))
    rt = getattr(sf, 'ref_types', None)
    print('  ref_types:', None if rt is None else len(rt))
    if rt:
        for i, t in enumerate(rt[:12]):
            print('   ', i, 'cls=', getattr(t,'m_ClassName',None), 'ns=', getattr(t,'m_NameSpace',None),
                  'asm=', getattr(t,'m_AssemblyName',None), 'script_type_index=', getattr(t,'m_ScriptTypeIndex',None),
                  'node=', getattr(t,'node',None) is not None and len(t.node.m_Children) if getattr(t,'node',None) else None)
