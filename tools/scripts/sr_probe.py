import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import UnityPy, os, json, sys, struct
sys.path.insert(0, TOOLS)
import decode
from decode import Reader, decode_value, decode_struct, read_header, Decoder
import schema
from schema import serialized_fields, load_type
CACHE = json.load(open(ASSETS_CACHE))
BASE = GAME_DATA
env = UnityPy.load(os.path.join(BASE,'resources.assets'), os.path.join(BASE,'sharedassets0.assets'),
                   os.path.join(BASE,'globalgamemanagers.assets'), os.path.join(BASE,'level0'))
objs = {}
for fk, sf in env.files.items():
    fn = os.path.basename(getattr(sf,'name',str(fk)))
    for o in sf.objects.values():
        objs[(fn,o.path_id)] = (sf,o)

# map refTypeIndex -> class name per file
def refnames(sf):
    out = {}
    for i,t in enumerate(sf.ref_types or []):
        sti = t.script_type_index
        name='?'
        if 0 <= sti < len(sf.script_types):
            l = sf.script_types[sti]
            fi = l.local_serialized_file_index
            pid = l.local_identifier_in_file
            tgt=None
            if fi==0: tgt=sf
            elif fi-1 < len(sf.externals):
                base=os.path.basename(str(getattr(sf.externals[fi-1],'path','')))
                for k2,s2 in env.files.items():
                    if os.path.basename(getattr(s2,'name',''))==base: tgt=s2
            if tgt is not None and pid in tgt.objects:
                try:
                    ms=tgt.objects[pid].read(); name=f'{ms.m_Namespace}.{ms.m_ClassName}'
                except Exception: name='<err>'
        out[i]=name
    return out

cls = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv)>2 else 3
shown=0
for fname,pid in CACHE['objects'][cls]:
    raw = objs[(fname,pid)][1].get_raw_data()
    nm,off = read_header(raw)
    r = Reader(raw, off)
    dec = Decoder()
    hit=False
    for f in serialized_fields(cls):
        if any('SerializeReference' in a for a in f['attrs']):
            r.align(4); cnt = r.i32()
            print(f'== {cls} {nm!r} {fname}/{pid} len={len(raw)} SR field {f["name"]} @{r.o-4} count={cnt}')
            sf = objs[(fname,pid)][0]
            print('   refnames:', refnames(sf))
            print('   next bytes:', raw[r.o:r.o+64].hex())
            hit=True
            break
        dec2 = decode_value(dec, f['type'], r, 0)
    if hit and cnt>0:
        shown+=1
        if shown>=n: break
