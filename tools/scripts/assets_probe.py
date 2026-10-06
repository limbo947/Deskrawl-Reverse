import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import os, struct, json, re, sys
from collections import Counter, defaultdict
import UnityPy

BASE = GAME_DATA
FILES = ['resources.assets', 'sharedassets0.assets', 'globalgamemanagers.assets', 'level0']
CACHE = ASSETS_CACHE


def ext_name(e):
    s = str(e)
    m = re.search(r'<FileIdentifier\((.*?)\)>', s)
    return m.group(1) if m else s.rstrip('>')


def read_pptr(raw, off):
    return struct.unpack_from('<i', raw, off)[0], struct.unpack_from('<q', raw, off + 4)[0]


def main():
    paths = [os.path.join(BASE, f) for f in FILES if os.path.exists(os.path.join(BASE, f))]
    env = UnityPy.load(*paths)

    script_map = {}
    for fkey, sf in env.files.items():
        fname = os.path.basename(getattr(sf, 'name', str(fkey)))
        for obj in sf.objects.values():
            if obj.type.name == 'MonoScript':
                try:
                    d = obj.read()
                    script_map[(fname, obj.path_id)] = (
                        d.m_ClassName, d.m_Namespace, d.m_AssemblyName)
                except Exception:
                    pass
    print('scripts:', len(script_map), flush=True)

    game_classes = set()
    objects = defaultdict(list)   # class -> [(file, path_id)]
    counts = Counter()
    for fkey, sf in env.files.items():
        fname = os.path.basename(getattr(sf, 'name', str(fkey)))
        exts = [ext_name(e) for e in sf.externals]
        for obj in sf.objects.values():
            if obj.type.name != 'MonoBehaviour':
                continue
            raw = obj.get_raw_data()
            try:
                fid, pid = read_pptr(raw, 16)
            except Exception:
                continue
            if fid == 0:
                tf = fname
            else:
                tf = exts[fid - 1] if 0 <= fid - 1 < len(exts) else '?'
            info = script_map.get((tf, pid))
            cls = info[0] if info else '?'
            counts[cls] += 1
            objects[cls].append((fname, obj.path_id))

    with open(CACHE, 'w', encoding='utf-8') as f:
        json.dump({'scripts': {f'{k[0]}|{k[1]}': v for k, v in script_map.items()},
                   'counts': counts.most_common(),
                   'objects': {k: v for k, v in objects.items()}},
                  f)
    print('--- top classes ---')
    for cls, n in counts.most_common(150):
        print(f'{n}\t{cls}')


if __name__ == '__main__':
    main()
