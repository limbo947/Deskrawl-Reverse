import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import sys, os
from collections import Counter
import UnityPy

BASE = GAME_DATA

def script_name(obj, env):
    try:
        tt = obj.serialized_type
        st = tt
        return None
    except Exception:
        return None

def main(fname):
    p = os.path.join(BASE, fname)
    env = UnityPy.load(p)
    print('=== ', fname, ' files:', len(env.files))
    for sf in env.files.values():
        try:
            print('  file:', getattr(sf, 'name', '?'), 'types:', len(getattr(sf, 'types', [])))
        except Exception as e:
            print('  err', e)
    cnt = Counter()
    for obj in env.objects:
        cnt[obj.type.name] += 1
    print(cnt.most_common(20))
    # inspect one MonoBehaviour
    for obj in env.objects:
        if obj.type.name == 'MonoBehaviour':
            try:
                d = obj.read()
                print('m_Name:', getattr(d, 'm_Name', None))
                print('serialized_type:', obj.serialized_type)
                st = obj.serialized_type
                if st is not None:
                    print('  script_type_index:', st.script_type_index)
                    nodes = getattr(st, 'nodes', None)
                    print('  nodes:', len(nodes) if nodes else nodes)
                    if nodes:
                        for n in nodes[:25]:
                            print('    ', n.level, n.type, n.name)
                break
            except Exception as e:
                print('read err', type(e).__name__, e)
                break

if __name__ == '__main__':
    main(sys.argv[1])
