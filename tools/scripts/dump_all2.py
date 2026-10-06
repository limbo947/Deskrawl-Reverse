import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
# -*- coding: utf-8 -*-
"""重新导出 so_dump（含 [SerializeReference] 托管引用载荷），并导出各类 *Effect 资产。

- 21 个原文件: 追加 `_managedRefs`（技能效果/状态行为的具体数值）
- 新增 EquipmentEffects.json / TalentEffects.json / LifeSkillEffects.json / StatusBehaviors.json
"""
import UnityPy, os, json, sys, collections
sys.path.insert(0, TOOLS)
import decode
from decode import decode_object, decode_object_ex

BASE = GAME_DATA
CACHE = json.load(open(ASSETS_CACHE))
OUT = SO_DUMP
os.makedirs(OUT, exist_ok=True)

TARGETS = ['GameConfig', 'ItemizationConfig', 'LootConfig', 'HealthPotionConfig',
           'HealingPotionUpgradeData', 'HeroData', 'SlaveData', 'RecipeData',
           'RuneSetData', 'LifeSkillNodeData', 'Enemy', 'QuestData', 'MapData',
           'FishingMapData', 'TownData', 'GemData', 'RuneData', 'ItemData',
           'AbilityData', 'StatusEffectData', 'TalentData']

env = UnityPy.load(os.path.join(BASE, 'resources.assets'), os.path.join(BASE, 'sharedassets0.assets'),
                   os.path.join(BASE, 'globalgamemanagers.assets'), os.path.join(BASE, 'level0'))
files = {}
objs = {}
for fk, sf in env.files.items():
    fn = os.path.basename(getattr(sf, 'name', str(fk)))
    files[fn] = sf
    for o in sf.objects.values():
        objs[(fn, o.path_id)] = o


def build_class_map(sf):
    """scriptTypeIndex -> 类名（经 MonoScript）。"""
    m = {}
    try:
        sts = sf.script_types or []
        for i, st in enumerate(sts):
            name = None
            try:
                fi = st.local_serialized_file_index
                pid = st.local_identifier_in_file
                tgt = sf if fi == 0 else files.get(os.path.basename(str(getattr(sf.externals[fi - 1], 'path', ''))))
                if tgt is not None and pid in tgt.objects:
                    ms = tgt.objects[pid].read()
                    name = getattr(ms, 'm_ClassName', None) or getattr(ms, 'm_Name', None)
            except Exception:
                name = None
            m[i] = name
    except Exception:
        pass
    return m


clsmap = {fn: build_class_map(sf) for fn, sf in files.items()}


def obj_class(fn, o):
    try:
        sti = o.type.script_type_index
    except Exception:
        return None
    return clsmap.get(fn, {}).get(sti)


# ---------- 1) 重新导出 21 个文件（含托管引用） ----------
print('=== 重新导出（含 _managedRefs） ===')
for cls in TARGETS:
    out, err, noleft, leftover = [], 0, 0, collections.Counter()
    for fname, pid in CACHE['objects'].get(cls, []):
        if (fname, pid) not in objs:
            continue
        raw = objs[(fname, pid)].get_raw_data()
        try:
            name, obj, refs, end = decode_object_ex(raw, cls)
        except Exception:
            err += 1
            continue
        rec = {'_name': name, '_pathid': pid, '_file': fname}
        if refs:
            rec['_managedRefs'] = refs
        left = len(raw) - end
        if 0 < left <= 3 and not any(raw[end:]):
            left = 0  # Unity 对象尾部 4 字节对齐零填充，不算残留
        if left:
            rec['_trailing_bytes'] = left
            leftover[left] += 1
        else:
            noleft += 1
        rec.update(obj)
        out.append(rec)
    json.dump(out, open(os.path.join(OUT, cls + '.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1, default=str)
    print(f'{cls:24} n={len(out):4} err={err:2} clean={noleft:4} leftover={dict(leftover)}')

# ---------- 2) 导出 *Effect 资产 ----------
print('\n=== 导出 Effect 资产 ===')
PREFIXES = {'EquipmentEffect_': 'EquipmentEffects', 'TalentEffect': 'TalentEffects',
            'LifeSkillEffect_': 'LifeSkillEffects', 'StatusEffectBehavior': 'StatusBehaviors'}
buckets = collections.defaultdict(list)
seen = 0
for fn in ('resources.assets', 'sharedassets0.assets', 'globalgamemanagers.assets', 'level0'):
    sf = files.get(fn)
    if not sf:
        continue
    for o in sf.objects.values():
        c = obj_class(fn, o)
        if not c:
            continue
        for pre, key in PREFIXES.items():
            if c.startswith(pre):
                raw = o.get_raw_data()
                try:
                    nm, obj, refs, end = decode_object_ex(raw, c)
                except Exception:
                    continue
                rec = {'_name': nm, '_pathid': o.path_id, '_file': fn, '_class': c}
                if refs:
                    rec['_managedRefs'] = refs
                rec.update(obj)
                buckets[key].append(rec)
                seen += 1
                break
for key, rows in buckets.items():
    json.dump(rows, open(os.path.join(OUT, key + '.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1, default=str)
    print(f'{key:20} {len(rows)}')
print('\n完成 ->', OUT)
