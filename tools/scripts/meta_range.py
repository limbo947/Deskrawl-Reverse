import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import json
j = json.load(open(SCRIPT_JSON, encoding='utf-8'))
lo, hi = 0x39E43C0, 0x39E44E0
print('--- ScriptMetadata in range ---')
for e in j['ScriptMetadata']:
    a = e['Address']
    if lo <= a <= hi:
        print(f"  {a:#x}  {e['Name']}  ({e['Signature']})")
print('--- ScriptString in range ---')
for e in j['ScriptString']:
    a = e['Address']
    if lo <= a <= hi:
        print(f"  {a:#x}  {e['Value']!r}")
print('--- ScriptMetadataMethod in range ---')
for e in j['ScriptMetadataMethod']:
    a = e['Address']
    if lo <= a <= hi:
        print(f"  {a:#x}  {e['Name']}  methodAddr={e['MethodAddress']:#x}")
