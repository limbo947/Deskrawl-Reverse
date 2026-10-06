import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
"""Reconstruct Unity serialization schemas from the IL2CPP dump."""
import re, os, sys, json

DUMP = DUMP_CS
_fields_cache = {}   # name -> [field dict]
_base_cache = {}     # name -> base name or None


def _find_first_decl(name):
    """Find the first top-level declaration of `name` (dot in nested names is skipped)."""
    m = re.search(r'(?:public|internal)\s+(?:sealed\s+|abstract\s+|partial\s+|static\s+|unsafe\s+)*'
                  r'(?:class|struct|enum)\s+' + re.escape(name) + r'(?!\.)\b[^\{]*\{', _data)
    return m


def _data_load():
    global _data
    if '_data' not in globals():
        _data = open(DUMP, encoding='utf-8', errors='ignore').read()
    return _data


_data = open(DUMP, encoding='utf-8', errors='ignore').read()

FIELD_RE = re.compile(
    r'((?:\s*\[[^\]]*\]\s*\n)*)\s*((?:public|private|protected|internal)\s+'
    r'(?:static\s+|readonly\s+|const\s+|volatile\s+|unsafe\s+)*)([\w\.<>,\[\]\?]+)\s+(\w+)\s*;\s*//\s*(0x[0-9A-Fa-f]+)')


def _split_decl(m):
    """From a match ending with '{', return (name, base_or_None, indent)."""
    text = m.group(0)
    nm = re.search(r'(?:class|struct|enum|interface)\s+([\w\.<>`]+)', text)
    name = nm.group(1) if nm else None
    head = text[:text.rfind('{')]
    head = re.sub(r'//.*', '', head)   # drop TypeDefIndex comment
    base = None
    if ':' in head:
        b = head.split(':', 1)[1].strip()
        base = b.split(',')[0].strip().split('<')[0].strip() or None
    return name, base


def _brace_body(pos):
    i = pos - 1
    depth = 0
    while i < len(_data):
        if _data[i] == '{':
            depth += 1
        elif _data[i] == '}':
            depth -= 1
            if depth == 0:
                return _data[pos:i], i
        i += 1
    return '', len(_data)


def load_type(name):
    """Parse a single type by name (first top-level decl). Returns (kind, base, [fields])."""
    if name in _fields_cache:
        return _fields_cache[name]
    m = _find_first_decl(name)
    if not m:
        _fields_cache[name] = None
        return None
    nm, base = _split_decl(m)
    body, _ = _brace_body(m.end())
    kind = 'enum' if re.search(r'enum\s+' + re.escape(name) + r'(?!\.)\b', m.group(0)) else 'class'
    fields = []
    if kind != 'enum':
        for fm in FIELD_RE.finditer(body):
            attrs = [a.strip() for a in re.findall(r'\[([^\]]*)\]', fm.group(1))]
            mods = fm.group(2)
            if 'static' in mods or 'const' in mods:
                continue
            fields.append({'attrs': attrs, 'mods': mods.strip(), 'type': fm.group(3),
                           'name': fm.group(4), 'off': fm.group(5)})
    _fields_cache[name] = (kind, base, fields)
    return _fields_cache[name]


def is_serialized(f):
    if 'static' in f['mods'] or 'const' in f['mods'] or 'readonly' in f['mods']:
        return False
    a = ' '.join(f['attrs'])
    # NOTE: [HideInInspector] does NOT stop serialisation; only [NonSerialized]/static/const do.
    if 'CompilerGenerated' in a or 'NonSerialized' in a:
        return False
    if f['mods'].startswith('public'):
        return True
    return any(('SerializeField' in x) or ('SerializeReference' in x) for x in f['attrs'])


UNITY_ROOTS = {'ScriptableObject', 'MonoBehaviour', 'Behaviour', 'Component', 'Object',
               'GameObject', 'Texture', 'Texture2D', 'AudioClip', 'Sprite', 'Material',
               'Renderer', 'Collider', 'MonoScript', 'RenderSettings'}


def is_unity_object(name):
    seen = set()
    cur = name
    while cur and cur not in seen:
        seen.add(cur)
        if cur in UNITY_ROOTS:
            return True
        r = load_type(cur)
        if r is None:
            return False
        cur = r[1]
    return False


def serialized_fields(name):
    """All serialized fields, base-class fields FIRST (Unity serializes the whole chain)."""
    chain = []
    cur = name
    seen = set()
    while cur and cur not in seen:
        seen.add(cur)
        r = load_type(cur)
        if r is None:
            break
        if cur not in UNITY_ROOTS:
            chain.append((cur, r[2]))
        cur = r[1]
    out = []
    for cname, flds in reversed(chain):
        for f in flds:
            if is_serialized(f):
                out.append(f)
    return out


if __name__ == '__main__':
    for n in sys.argv[1:]:
        r = load_type(n)
        if r is None:
            print(n, 'NOT FOUND'); continue
        print('####', n, 'kind=', r[0], 'base=', r[1], 'obj=', is_unity_object(n))
        for f in serialized_fields(n):
            print(f"   {f['off']:>6}  {f['type']:<42} {f['name']:<34} {'SR' if any('SerializeReference' in a for a in f['attrs']) else ''}")
