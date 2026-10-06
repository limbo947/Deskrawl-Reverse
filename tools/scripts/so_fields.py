import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import re, sys

DUMP = DUMP_CS
_data = open(DUMP, encoding='utf-8', errors='ignore').read()

CLS_RE = re.compile(
    r'((?:\[[^\]]*\]\s*\n\s*)*(?:public|internal)\s+(?:sealed\s+|abstract\s+|partial\s+|static\s+)*'
    r'(?:class|struct|enum|interface)\s+(\w+)\b[^\{]*?)\{(.*?)\n\}', re.S)


def find_body(name):
    m = re.search(r'(?:public|internal)\s+(?:sealed\s+|abstract\s+|partial\s+|static\s+|unsafe\s+)*'
                  r'(?:class|struct|enum)\s+' + re.escape(name) + r'(?!\.)\b[^\{]*\{', _data)
    if not m:
        return None, None
    header_start = _data.rfind('\n', 0, m.start()) + 1
    header = _data[header_start:m.end()]
    i = m.end() - 1
    depth = 0
    while i < len(_data):
        if _data[i] == '{':
            depth += 1
        elif _data[i] == '}':
            depth -= 1
            if depth == 0:
                break
        i += 1
    return header, _data[m.end():i]


FIELD_RE = re.compile(
    r'((?:\s*\[[^\]]*\]\s*\n)*)\s*((?:public|private|protected|internal)\s+'
    r'(?:static\s+|readonly\s+|const\s+|volatile\s+)*)([\w\.<>,\[\]\?]+)\s+(\w+)\s*;\s*//\s*(0x[0-9A-Fa-f]+)')


def fields_of(name):
    header, body = find_body(name)
    if body is None:
        return None, None
    out = []
    for m in FIELD_RE.finditer(body):
        attrs = [a.strip() for a in re.findall(r'\[([^\]]*)\]', m.group(1))]
        mods = m.group(2)
        if 'static' in mods or 'const' in mods:
            continue
        out.append({
            'attrs': attrs,
            'mods': mods.strip(),
            'type': m.group(3),
            'name': m.group(4),
            'off': m.group(5),
        })
    return header.strip().split('\n')[-1], out


def is_serialized(f):
    if 'HideInInspector' in ' '.join(f['attrs']):
        return False
    if 'CompilerGenerated' in ' '.join(f['attrs']):
        return False
    if f['mods'].startswith('public'):
        return True
    return any('SerializeField' in a for a in f['attrs'])


if __name__ == '__main__':
    for n in sys.argv[1:]:
        header, fs = fields_of(n)
        print('#### ' + n + '  ' + (header or ''))
        if fs is None:
            print('  NOT FOUND')
            continue
        for f in fs:
            mark = '' if is_serialized(f) else '   [non-serialized]'
            a = ','.join(f['attrs'])
            print(f"  {f['off']:>6}  {f['type']:<46} {f['name']:<38} {a}{mark}")
        print()
