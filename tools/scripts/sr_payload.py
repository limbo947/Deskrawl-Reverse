import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
# -*- coding: utf-8 -*-
"""解码 [SerializeReference] 载荷：主数据流只存 count + 8B 键，真实字段附在对象尾部。
用 AbilityEffect 的 16 个子类做"长度精确匹配"来反推每个元素的类型，并建立 键→类型 映射。
"""
import UnityPy, os, json, sys, collections
sys.path.insert(0, TOOLS)
import decode
from decode import Reader, decode_value, decode_struct, read_header, Decoder
from schema import serialized_fields

CACHE = json.load(open(ASSETS_CACHE))
BASE = GAME_DATA
env = UnityPy.load(os.path.join(BASE, 'resources.assets'), os.path.join(BASE, 'sharedassets0.assets'),
                   os.path.join(BASE, 'globalgamemanagers.assets'), os.path.join(BASE, 'level0'))
objs = {}
for fk, sf in env.files.items():
    fn = os.path.basename(getattr(sf, 'name', str(fk)))
    for o in sf.objects.values():
        objs[(fn, o.path_id)] = o

ABILITY_EFFECTS = ['ApplyStatusEffectEffect', 'DamageEffect', 'DashEffect', 'EveryNthCastEffect',
                   'GainManaEffect', 'HealEffect', 'KnockbackEffect', 'PullEffect', 'ReviveAllEffect',
                   'SpawnBeamEffect', 'SpawnGroundZoneEffect', 'SpawnParticleAoEEffect',
                   'SpawnProjectileEffect', 'SpawnTransientCharacterEffect', 'StaggeredStrikesEffect',
                   'StatScaledDamageEffect']


def sr_info(raw, cls):
    """返回 (name, sr_field_name, count, keys[bytes], sr_offset, end_offset)。"""
    dec = Decoder()
    name, off = read_header(raw)
    r = Reader(raw, off)
    for f in serialized_fields(cls):
        if any('SerializeReference' in a for a in f['attrs']):
            r.align(4)
            pos = r.o
            cnt = r.i32()
            keys = []
            for _ in range(max(0, cnt)):
                r.align(4)
                keys.append(r.raw(8))
            return name, f['name'], cnt, keys, pos, r.o
        decode_value(dec, f['type'], r, 0)
    return name, None, 0, [], 0, r.o


def try_seq(raw, start, end, n, cands):
    """从 start 起用 cands 里的类型依次解码 n 个元素，要求恰好吃到 end。返回 [(cls, obj, endoff)]。"""
    def rec(off, k):
        if k == n:
            return [] if off == end else None
        for c in cands:
            r = Reader(raw, off)
            try:
                obj = decode_struct(Decoder(), c, r)
            except Exception:
                continue
            if r.o > end or r.o <= off:
                continue
            tail = rec(r.o, k + 1)
            if tail is not None:
                return [(c, obj, r.o)] + tail
        return None
    return rec(start, 0)


def main():
    rows = CACHE['objects'].get('AbilityData', [])
    key2cls = collections.defaultdict(collections.Counter)
    sample = {}
    done = 0
    for fname, pid in rows:
        raw = objs[(fname, pid)].get_raw_data()
        try:
            name, srf, cnt, keys, srpos, srend = sr_info(raw, 'AbilityData')
        except Exception:
            continue
        if srf is None or cnt <= 0:
            continue
        tail_start = srend            # 主数据流到此结束（后面的字段？此处 SR 是末字段则=尾部起点）
        # 先按"其余字段在 SR 之后"重新计算真正尾部：解完整对象
        try:
            _, _, end = decode.decode_object(raw, 'AbilityData')
        except Exception:
            end = srend
        payload = raw[end:]
        if not payload:
            continue
        seq = try_seq(raw, end, len(raw), cnt, ABILITY_EFFECTS)
        if seq:
            for k, (c, obj, _) in zip(keys, seq):
                key2cls[k.hex()][c] += 1
                sample.setdefault((k.hex(), c), obj)
            done += 1
    print(f'可精确解出的 AbilityData：{done} / {sum(1 for f,p in rows if p)}')
    print('\n=== 键(8B hex) → 类型 映射 ===')
    for k, c in sorted(key2cls.items()):
        print(f'  {k}  ->  {dict(c)}')
    print('\n=== 样例效果 ===')
    for (k, c), obj in list(sample.items())[:8]:
        print(f'  [{c}] {json.dumps(obj, ensure_ascii=False, default=str)[:400]}')


if __name__ == '__main__':
    main()
