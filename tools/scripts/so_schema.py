import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import re, sys, io
sys.path.insert(0, TOOLS)
from so_fields import _data, fields_of, is_serialized

OUT = r'C:\Users\<user>\tools\so_schema.md'

ENUM_RE = re.compile(
    r'(?:public|internal)\s+enum\s+(\w+)\s*(?::\s*(\w+))?\s*//\s*TypeDefIndex:\s*(\d+)\s*\{(.*?)\n\}', re.S)
CONST_RE = re.compile(r'public\s+const\s+(\w+)\s+(\w+)\s*=\s*(-?\w+);')

# all classes with TypeDefIndex
CLASS_RE = re.compile(
    r'(?:public|internal)\s+(?:sealed\s+|abstract\s+|partial\s+|static\s+)*class\s+(\w+)\s*:\s*([\w\.<>,\s]+?)\s*//\s*TypeDefIndex:\s*(\d+)')

GAME_ROOTS = {'ScriptableObject', 'AbilityEffect', 'StatusEffectBehavior', 'EquipmentEffectBehavior',
              'TalentEffectBehavior', 'LifeSkillNodeEffect', 'EquipmentEffectBehavior',
              'ItemData', 'Character'}


def main():
    # build hierarchy
    classes = {}
    for m in CLASS_RE.finditer(_data):
        classes[m.group(1)] = (m.group(2).strip(), int(m.group(3)))

    def descends(name, root, seen=None):
        seen = seen or set()
        if name in seen:
            return False
        seen.add(name)
        if name == root:
            return True
        base = classes.get(name, (None,))[0]
        if not base:
            return False
        base = base.split('<')[0].strip()
        return descends(base, root, seen)

    game_so = []
    for name, (base, idx) in classes.items():
        if idx < 5500 or idx > 6000:
            continue
        b = base.split('<')[0].strip()
        if b in ('ScriptableObject',) or descends(name, 'ScriptableObject'):
            game_so.append((idx, name, base))
        elif b in GAME_ROOTS:
            game_so.append((idx, name, base))
    game_so.sort()

    buf = io.StringIO()
    buf.write('# Deskrawl — ScriptableObject / 数值类 字段模式（由 dump.cs 提取）\n\n')

    # enums in game range
    buf.write('## 枚举\n\n')
    for m in ENUM_RE.finditer(_data):
        idx = int(m.group(3))
        if idx < 5480 or idx > 6120:
            continue
        name, underlying, body = m.group(1), m.group(2) or 'int', m.group(4)
        buf.write(f'### {name}  (TypeDefIndex {idx}, underlying: {underlying})\n')
        vals = CONST_RE.findall(body)
        for t, n, v in vals:
            buf.write(f'- {n} = {v}\n')
        buf.write('\n')

    buf.write('\n## 类字段（仅序列化字段，按声明顺序）\n\n')
    for idx, name, base in game_so:
        header, fs = fields_of(name)
        if fs is None:
            continue
        buf.write(f'### {name} : {base}   (TypeDefIndex {idx})\n')
        for f in fs:
            if not is_serialized(f):
                continue
            attrs = ','.join(f['attrs'])
            extra = f'  `[{attrs}]`' if attrs else ''
            buf.write(f"- `{f['name']}` : `{f['type']}`{extra}\n")
        buf.write('\n')

    open(OUT, 'w', encoding='utf-8').write(buf.getvalue())
    print('written', OUT, len(buf.getvalue()), 'chars')
    print('classes:', len(game_so))


if __name__ == '__main__':
    main()
