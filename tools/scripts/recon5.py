import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import UnityPy, os
BASE = GAME_DATA
env = UnityPy.load(os.path.join(BASE,'resources.assets'),
                   os.path.join(BASE,'sharedassets0.assets'),
                   os.path.join(BASE,'globalgamemanagers.assets'))
for fkey, sf in env.files.items():
    name = os.path.basename(getattr(sf,'name',str(fkey)))
    rt = sf.ref_types or []
    print('FILE', name, 'ver', sf.header.version, 'enable_tt', sf._enable_type_tree, 'nref', len(rt),
          'nscripts', len(sf.script_types), 'nextern', len(sf.externals))
    # resolve MonoScripts from globalgamemanagers
    ggm = None
    for k2, s2 in env.files.items():
        if os.path.basename(getattr(s2,'name','')) == 'globalgamemanagers.assets':
            ggm = s2
    for i, t in enumerate(rt):
        sti = t.script_type_index
        cls = t.class_id
        msdesc = ''
        if sti is not None and sti >= 0 and sti < len(sf.script_types):
            lsoi = sf.script_types[sti]
            fi = lsoi.local_serialized_file_index
            pid = lsoi.local_identifier_in_file
            msdesc = f'fileIdx={fi} pid={pid}'
            target = None
            if fi == 0:
                target = sf
            elif fi - 1 < len(sf.externals):
                extname = getattr(sf.externals[fi-1],'path','')
                base = os.path.basename(str(extname))
                for k2, s2 in env.files.items():
                    if os.path.basename(getattr(s2,'name','')) == base:
                        target = s2
            if target is not None and pid in target.objects:
                try:
                    ms = target.objects[pid].read()
                    msdesc += f' -> {ms.m_Namespace}.{ms.m_ClassName} ({ms.m_AssemblyName})'
                except Exception as e:
                    msdesc += f' [err {e}]'
        print(f'  ref[{i}] class_id={cls} script_type_index={sti} {msdesc}')
