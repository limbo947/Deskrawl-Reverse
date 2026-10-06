import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import UnityPy, os, json, sys, itertools
sys.path.insert(0, TOOLS)
import decode
from decode import decode_object, FIELDS_OVERRIDE, mkfields
CACHE = json.load(open(ASSETS_CACHE))
BASE = GAME_DATA
env = UnityPy.load(os.path.join(BASE,'resources.assets'), os.path.join(BASE,'sharedassets0.assets'),
                   os.path.join(BASE,'globalgamemanagers.assets'), os.path.join(BASE,'level0'))
objs = {}
for fk, sf in env.files.items():
    fn = os.path.basename(getattr(sf,'name',str(fk)))
    for o in sf.objects.values():
        objs[(fn,o.path_id)] = o

E_CANDS = {
 'E20': [('GameObject','EnemyPrefab'),('int','Count'),('int','Row')],
 'E24f': [('GameObject','EnemyPrefab'),('int','Count'),('int','Row'),('float','X')],
 'E28l': [('GameObject','EnemyPrefab'),('int','Count'),('int','Row'),('long','PlannedXP')],
 'E48': [('GameObject','EnemyPrefab'),('int','Count'),('int','Row'),('long','PlannedXP'),('long','PlannedBaseHealth'),('long','PlannedBaseDamage'),('bool','PlannedIsBoss')],
}
C_CANDS = {
 'C_dump': [('EnemySpawnEntry[]','Enemies'),('float','Weight'),('GameObject','BossPrefab')],
 'C_noBoss': [('EnemySpawnEntry[]','Enemies'),('float','Weight')],
 'C_enemiesOnly': [('EnemySpawnEntry[]','Enemies')],
}

def validate(cls):
    ok=bad=err=0
    for fname,pid in CACHE['objects'].get(cls,[]):
        raw = objs[(fname,pid)].get_raw_data()
        try:
            nm,obj,end = decode_object(raw,cls)
            pad=raw[end:]
            if end==len(raw) or (len(pad)<=3 and pad==b'\x00'*len(pad)): ok+=1
            else: bad+=1
        except Exception: err+=1
    return ok,bad,err

for en,ef in E_CANDS.items():
    for cn,cf in C_CANDS.items():
        FIELDS_OVERRIDE['EnemySpawnEntry'] = mkfields(ef)
        FIELDS_OVERRIDE['EncounterData'] = mkfields(cf)
        ok,bad,err = validate('MapData')
        print(f'{en:6} {cn:14} ok={ok} bad={bad} err={err}')
