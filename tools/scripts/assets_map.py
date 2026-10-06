import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import os, sys, struct
from collections import Counter
import UnityPy

BASE = GAME_DATA
FILES = ['resources.assets', 'sharedassets0.assets', 'globalgamemanagers.assets', 'level0']


def read_pptr(raw, off):
    return struct.unpack_from('<i', raw, off)[0], struct.unpack_from('<q', raw, off + 4)[0]


def read_string(raw, off):
    n = struct.unpack_from('<i', raw, off)[0]
    off += 4
    if n < 0 or n > 512 or off + n > len(raw):
        raise ValueError('bad string len %d at %d' % (n, off))
    s = raw[off:off + n].decode('utf-8', 'replace')
    off = (off + n + 3) & ~3
    return s, off


def parse_monoscript(raw):
    off = 16 + 12   # m_GameObject(12) m_Enabled(1)+pad(3) m_Script(12)
    cls, off = read_string(raw, off)
    ns, off = read_string(raw, off)
    asm, off = read_string(raw, off)
    return cls, ns, asm


def main():
    paths = [os.path.join(BASE, f) for f in FILES if os.path.exists(os.path.join(BASE, f))]
    env = UnityPy.load(*paths)

    fname_by_obj = {}
    for fkey, sf in env.files.items():
        for obj in sf.objects.values():
            fname_by_obj[obj.path_id] = os.path.basename(getattr(sf, 'name', str(fkey)))
    # note: UnityPy env.objects iterates all; use sf.objects for per-file

    # per-file externals
    for fkey, sf in env.files.items():
        print('FILE', os.path.basename(getattr(sf, 'name', str(fkey))),
              'externals:', [os.path.basename(str(e)) for e in sf.externals], flush=True)

    script_map = {}
    per_file_mono = Counter()
    for fkey, sf in env.files.items():
        fname = os.path.basename(getattr(sf, 'name', str(fkey)))
        for obj in sf.objects.values():
            if obj.type.name == 'MonoScript':
                per_file_mono[fname] += 1
                try:
                    cls, ns, asm = parse_monoscript(obj.get_raw_data())
                    script_map[(fname, obj.path_id)] = (cls, ns, asm)
                except Exception as e:
                    pass
    print('MonoScript per file:', per_file_mono)
    print('parsed scripts:', len(script_map))

    def resolve(fname, sf, fid_file, path_id):
        if fid_file == 0:
            return fname, path_id
        ext = sf.externals[fid_file - 1]
        return os.path.basename(str(ext)), path_id

    mb_by_class = Counter()
    mb_per_file = Counter()
    unresolved = 0
    for fkey, sf in env.files.items():
        fname = os.path.basename(getattr(sf, 'name', str(fkey)))
        for obj in sf.objects.values():
            if obj.type.name != 'MonoBehaviour':
                continue
            mb_per_file[fname] += 1
            raw = obj.get_raw_data()
            try:
                fid_file, path_id = read_pptr(raw, 16)
            except Exception:
                continue
            tf, tp = resolve(fname, sf, fid_file, path_id)
            info = script_map.get((tf, tp))
            if info is None:
                unresolved += 1
                mb_by_class['?' + tf] += 1
            else:
                mb_by_class[info[0]] += 1

    print('MonoBehaviour per file:', mb_per_file, 'unresolved:', unresolved)
    print('--- counts by class ---')
    for cls, n in mb_by_class.most_common(120):
        print(f'{n}\t{cls}')


if __name__ == '__main__':
    main()
