import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
"""Unity binary serializer reconstruction driven by the IL2CPP dump schema."""
import os, sys, struct, json
sys.path.insert(0, TOOLS)
import schema
from schema import load_type, serialized_fields, is_unity_object, is_serialized

PRIM = {'bool': 1, 'byte': 1, 'sbyte': 1, 'char': 2, 'short': 2, 'ushort': 2,
        'int': 4, 'uint': 4, 'float': 4, 'long': 8, 'ulong': 8, 'double': 8}
FIXED = {'Vector2': 8, 'Vector3': 12, 'Vector4': 16, 'Vector2Int': 8, 'Vector3Int': 12,
         'Color': 16, 'Color32': 4, 'Quaternion': 16, 'Rect': 16, 'RectInt': 16,
         'Bounds': 24, 'LayerMask': 4, 'Matrix4x4': 64}

# alignment policy for 8-byte primitives (toggled empirically)
ALIGN8 = False

# ACTk Obscured* serialized sizes (empirically measured; IL2CPP memory size differs).
# Layout: int hash, int32 hiddenValue, key..., then raw tail kept verbatim.
OBSC_SIZES = {'ObscuredFloat': 28, 'ObscuredInt': 12, 'ObscuredLong': 20, 'ObscuredBool': 12}


class Reader:
    def __init__(self, data, off=0):
        self.d = data
        self.o = off

    def align(self, n):
        if n > 1:
            self.o = (self.o + n - 1) & ~(n - 1)

    def i32(self):
        v = struct.unpack_from('<i', self.d, self.o)[0]; self.o += 4; return v

    def u32(self):
        v = struct.unpack_from('<I', self.d, self.o)[0]; self.o += 4; return v

    def i64(self):
        v = struct.unpack_from('<q', self.d, self.o)[0]; self.o += 8; return v

    def f32(self):
        v = struct.unpack_from('<f', self.d, self.o)[0]; self.o += 4; return v

    def f64(self):
        v = struct.unpack_from('<d', self.d, self.o)[0]; self.o += 8; return v

    def raw(self, n):
        v = self.d[self.o:self.o+n]; self.o += n; return v


def _elem_of(t):
    if t.endswith('[]'):
        return t[:-2]
    if t.startswith('List<') and t.endswith('>'):
        return t[5:-1]
    return None


def prim_size(t):
    return PRIM.get(t)


def align_of(t):
    if t in PRIM:
        n = PRIM[t]
        if n == 8:
            return 8 if ALIGN8 else 4
        # Unity pads sub-4 primitive fields (bool/byte/short) up to 4 bytes.
        return 4
    if t == 'string' or _elem_of(t) is not None:
        return 4
    if t in ('LayerMask',):
        return 4
    if t in FIXED:
        return 4
    if is_unity_object(t):
        return 4
    r = load_type(t)
    if r is None:
        return 4
    if r[0] == 'enum':
        return 4
    # inline struct: alignment = max field alignment (4 typical)
    return 4


class Decoder:
    def __init__(self):
        self.file = None


def decode_obscured(t, r):
    """ACTk Obscured* : [hash:i32][cipher...][raw tail]. Value = cipher XOR key."""
    size = OBSC_SIZES[t]
    start = r.o
    h = r.i32()
    if t == 'ObscuredLong':
        a = r.i64(); b = r.i64(); tail = r.raw(max(0, size - 20))
        return {'__type__': t, 'hash': h, 'hiddenValue': a, 'cryptoKey': b,
                'value': a ^ b, '__tail__': tail.hex()}
    a = r.i32(); b = r.i32(); tail = r.raw(max(0, size - 12))
    if t == 'ObscuredFloat':
        x = struct.unpack('<I', struct.pack('<i', a ^ b))[0]
        val = struct.unpack('<f', struct.pack('<I', x))[0]
    else:
        val = a ^ b
    return {'__type__': t, 'hash': h, 'hiddenValue': a, 'cryptoKey': b,
            'value': val, '__tail__': tail.hex()}


def decode_fixed(t, b):
    """Unity maths structs -> numeric arrays (more useful than raw hex)."""
    F = struct.unpack
    if t in ('Vector2', 'Vector2Int'):
        return list(F('<2f' if t == 'Vector2' else '<2i', b))
    if t in ('Vector3', 'Vector3Int'):
        return list(F('<3f' if t == 'Vector3' else '<3i', b))
    if t in ('Vector4', 'Quaternion', 'Color', 'Rect'):
        return list(F('<4f', b))
    if t == 'Color32':
        return list(b)
    if t == 'Bounds':
        return list(F('<6f', b))
    if t == 'Matrix4x4':
        return list(F('<16f', b))
    if t == 'LayerMask':
        return F('<i', b)[0]
    return {'__hex__': b.hex()}


def decode_value(dec, t, r, depth=0):
    if depth > 16:
        raise ValueError('depth limit')
    if t in OBSC_SIZES:
        return decode_obscured(t, r)
    # arrays / lists
    e = _elem_of(t)
    if e is not None:
        r.align(4)
        n = r.i32()
        if n < 0 or n > 5_000_000:
            raise ValueError(f'bad array count {n} for {t}')
        out = []
        ea = align_of(e)
        for _ in range(n):
            r.align(ea)
            out.append(decode_value(dec, e, r, depth+1))
        return out
    if t == 'string':
        r.align(4)
        n = r.i32()
        if n < 0 or n > 5_000_000:
            raise ValueError(f'bad string len {n}')
        b = r.raw(n); r.align(4)
        return b.decode('utf-8', 'replace')
    if t in PRIM:
        r.align(align_of(t))
        if t == 'bool':
            return r.raw(1)[0] != 0
        if t == 'byte':
            return r.raw(1)[0]
        if t == 'sbyte':
            return struct.unpack('<b', r.raw(1))[0]
        if t == 'char':
            return struct.unpack('<H', r.raw(2))[0]
        if t == 'short':
            return struct.unpack('<h', r.raw(2))[0]
        if t == 'ushort':
            return struct.unpack('<H', r.raw(2))[0]
        if t in ('int', 'uint'):
            return r.i32()
        if t == 'float':
            return r.f32()
        if t in ('long', 'ulong'):
            r.align(8 if ALIGN8 else 4)
            return r.i64()
        if t == 'double':
            r.align(8 if ALIGN8 else 4)
            return r.f64()
    if t in FIXED:
        r.align(4)
        return decode_fixed(t, r.raw(FIXED[t]))
    if is_unity_object(t):
        r.align(4)
        fid = r.i32(); pid = r.i64()
        return {'fileID': fid, 'pathID': pid} if (fid or pid) else None
    rt = load_type(t)
    if rt is None:
        raise ValueError(f'unknown type {t}')
    if rt[0] == 'enum':
        r.align(4)
        return r.i32()
    return decode_struct(dec, t, r, depth+1)


def _decode_fields(dec, fields, r, depth, out):
    i = 0
    while i < len(fields):
        f = fields[i]
        fname = f['name']
        if any('SerializeReference' in a for a in f['attrs']):
            out[fname] = decode_sr(dec, f, r)
            i += 1
            continue
        out[fname] = decode_value(dec, f['type'], r, depth)
        i += 1
    return True


def decode_struct(dec, t, r, depth=0):
    fields = FIELDS_OVERRIDE.get(t) or serialized_fields(t)
    out = {}
    _decode_fields(dec, fields, r, depth, out)
    return out


FIELDS_OVERRIDE = {}


def mkfields(spec):
    return [{'type': t, 'name': n, 'attrs': [], 'mods': '', 'off': ''} for t, n in spec]


# The shipping build does not serialise the runtime-only "Planned*" preview values of
# EnemySpawnEntry nor EncounterData.BossPrefab (empirically all 76 MapData match only
# when they are omitted).
FIELDS_OVERRIDE['EnemySpawnEntry'] = mkfields([
    ('GameObject', 'EnemyPrefab'), ('int', 'Count'), ('int', 'Row')])
FIELDS_OVERRIDE['EncounterData'] = mkfields([
    ('EnemySpawnEntry[]', 'Enemies'), ('float', 'Weight')])




def decode_sr(dec, f, r):
    """[SerializeReference] list. The main data stream stores only the 4-byte count and an
    8-byte managed-reference key per element; the real payloads live in a managed-reference
    section appended AFTER the object's normal fields (see decode_managed_section)."""
    r.align(4)
    n = r.i32()
    if n == 0:
        return []
    if n < 0 or n > 100000:
        raise ValueError(f'bad SR count {n}')
    out = []
    for _ in range(n):
        r.align(4)
        hdr = r.raw(8)
        out.append({'__managed_ref_hash__': hdr.hex()})
    return out


def decode_managed_section(dec, r, end):
    """Managed-reference section appended after the object's fields (only when SR count>0):

        [int32 A][int32 N]
        repeat N times:
            [u64 typeHash][string typeName][string namespace][string assemblyName]
            [payload = serialised fields of typeName]

    Type names are stored in plaintext, so the concrete managed type is exact.
    """
    r.align(4)
    a = r.i32()
    n = r.i32()
    if n < 0 or n > 100000:
        raise ValueError(f'bad managed count {n}')
    items = []
    for _ in range(n):
        r.align(4)
        h = r.raw(8)
        tn = decode_value(None, 'string', r)
        ns = decode_value(None, 'string', r)
        asm = decode_value(None, 'string', r)
        rec = {'__hash__': h.hex(), '__type__': tn, '__asm__': asm}
        if ns:
            rec['__ns__'] = ns
        if load_type(tn) is None:
            rec['__error__'] = f'unknown managed type {tn!r}'
        else:
            rec.update(decode_struct(dec, tn, r))
        rec['__end__'] = r.o
        items.append(rec)
    return {'__header__': [a, n], '__items__': items}


def decode_object_ex(raw, cls):
    """Like decode_object but also parses the trailing managed-reference section.

    Returns (name, obj, managed_refs_or_None, end_offset).
    """
    dec = Decoder()
    name, off = read_header(raw)
    r = Reader(raw, off)
    obj = {}
    has_sr = False
    for f in serialized_fields(cls):
        if any('SerializeReference' in a for a in f['attrs']):
            v = decode_sr(dec, f, r)
            obj[f['name']] = v
            if v:
                has_sr = True
        else:
            obj[f['name']] = decode_value(dec, f['type'], r, 0)
    refs = None
    if has_sr and r.o < len(raw):
        try:
            save = r.o
            refs = decode_managed_section(dec, r, len(raw))
        except Exception:
            r.o = save
            refs = None
    return name, obj, refs, r.o


def read_header(raw):
    """MonoBehaviour/ScriptableObject prologue -> (name, offset_after_name)."""
    r = Reader(raw)
    r.o = 12          # m_GameObject PPtr
    r.o += 4          # m_Enabled + 3 pad
    r.o += 12         # m_Script PPtr
    name = decode_value(None, 'string', r)
    return name, r.o


def decode_object(raw, cls):
    dec = Decoder()
    name, off = read_header(raw)
    r = Reader(raw, off)
    obj = decode_struct(dec, cls, r)
    return name, obj, r.o

