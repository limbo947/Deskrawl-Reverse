import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
# -*- coding: utf-8 -*-
"""解密并结构化输出 Deskrawl 存档（只读）。用法: python read_save.py [save.json 路径]"""
import hashlib, hmac, json, sys

SAVE  = sys.argv[1] if len(sys.argv) > 1 else GAME_SAVE
PW    = b'desktop-diablo-save-v1-CHANGE-ME'
MACPW = b'desktop-diablo-save-v1-CHANGE-ME|mac'

def aes_cbc(key, iv, ct):
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        d = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        return d.update(ct) + d.finalize()
    except Exception:
        from Crypto.Cipher import AES
        return AES.new(key, AES.MODE_CBC, iv).decrypt(ct)

def unpad(b):
    n = b[-1] if b else 0
    return b[:-n] if 1 <= n <= 16 and b[-n:] == bytes([n]) * n else b

def load(path):
    data = open(path, 'rb').read()
    key, mackey = hashlib.sha256(PW).digest(), hashlib.sha256(MACPW).digest()
    assert data[:4] == b'DDS2', '不是 DDS2 存档'
    mac, iv, ct = data[4:36], data[36:52], data[52:]
    assert hmac.new(mackey, data[:4] + iv + ct, hashlib.sha256).digest() == mac, 'MAC 校验失败'
    return json.loads(unpad(aes_cbc(key, iv, ct)).decode('utf-8'))

MODE = {0: 'Local', 1: 'Online'}

def reg_index(data):
    return {e['Uid']: e for e in data.get('ItemRegistryEntries', [])}

def show_entry(e):
    bits = [f"iLv{e.get('ItemLevel')}", e.get('Rarity') or '?']
    if e.get('IsAncient'): bits.append('远古')
    if e.get('IsBlackMist'): bits.append('黑雾')
    if e.get('UpgradeLevel'): bits.append(f"+{e['UpgradeLevel']}({e.get('UpgradeAttempts')}试)")
    if e.get('RuneLevel'): bits.append(f"符文Lv{e['RuneLevel']}")
    if e.get('SocketCount'): bits.append(f"孔{e['SocketCount']}")
    mods = ', '.join(f"{m.get('Stat')}+{m.get('Value')}({m.get('Type')})" for m in e.get('Modifiers', []))
    s = f"    - [{e.get('Uid')}] {' '.join(bits)}"
    if mods: s += f"\n        词条: {mods}"
    return s

def show_slots(title, slots, reg):
    print(f"  {title}: {len(slots)} 件")
    for sl in slots:
        uid = sl.get('ItemUid')
        head = f"    * 槽{sl.get('Idx')} {sl.get('ItemName')} x{sl.get('Count', 1)}" + (" [锁]" if sl.get('Locked') else "")
        print(head)
        if uid and uid in reg: print(show_entry(reg[uid]))

def show_char(rec):
    d = rec.get('Data') or {}
    print(f"  角色: Lv{d.get('Level')} XP={d.get('CurrentXP')} HP={d.get('CurrentHP')}/{d.get('BaseMaxHealth')} "
          f"MP={d.get('CurrentMana')}/{d.get('BaseMaxMana')} 主属性={d.get('BasePrimaryStat')} 伤害={d.get('BaseDamage')}")
    print(f"  进度: 地图='{d.get('ActiveMapName')}' 区域='{d.get('ActiveArea')}' 难度='{d.get('WorldDifficulty')}' 血瓶档={d.get('PotionUpgradeLevel')}")
    reg = reg_index(d)
    show_slots('装备 EquipmentSlots', d.get('EquipmentSlots', []), reg)
    show_slots('背包 InventorySlots', d.get('InventorySlots', []), reg)
    show_slots('马车 CarriageSlots', d.get('CarriageSlots', []), reg)
    show_slots('符文 RuneSlots', d.get('RuneSlots', []), reg)
    print(f"  物品注册表: {len(reg)} 条")
    for e in reg.values(): print(show_entry(e))
    print(f"  天赋: {[(t.get('TalentName'), t.get('Points')) for t in d.get('AllocatedTalents', [])]} 未分配点={d.get('TalentOutstandingPoints')}")
    print(f"  技能: {[(a.get('AbilityName'), a.get('Level')) for a in d.get('LearnedAbilities', [])]}")
    print(f"  巅峰属性: {[(p.get('Stat'), p.get('Points')) for p in d.get('ParagonStats', [])]}")
    print(f"  已完成任务={len(d.get('CompletedQuests', []))} 已访问地图={len(d.get('VisitedMaps', []))} "
          f"累计金币={d.get('TotalEarnedGold')} 累计经验={d.get('TotalEarnedExp')} 死亡={d.get('TotalDeaths')}")

def show_stash(rec):
    st = rec.get('LocalStash') or {}
    print(f"  仓库: 金币={st.get('Gold')} 材料={len(st.get('Materials', []))} 生活技能={len(st.get('LifeSkills', []))} "
          f"未解锁随从={len(st.get('UnlockedSlaves', []))} 巅峰={st.get('Paragon')}")
    reg = {e['Uid']: e for e in st.get('Registry', [])}
    show_slots('仓库格 Slots', st.get('Slots', []), reg)
    print(f"  仓库注册表: {len(reg)} 条")
    for m in st.get('Materials', []): print(f"    - 材料 {m.get('MaterialAssetName')} x{m.get('Count')}")

def main():
    obj = load(SAVE)
    print(f"存档: {SAVE}")
    print(f"Version={obj.get('Version')}  LocalSlots={len(obj.get('LocalSlots', []))}  "
          f"OnlineSlots={len(obj.get('OnlineSlots', []))}  DlcEntitlements={len(obj.get('DlcEntitlements', []))}")
    for label, slots in (('LocalSlots', obj.get('LocalSlots', [])), ('OnlineSlots', obj.get('OnlineSlots', []))):
        for i, rec in enumerate(slots):
            print(f"\n=== {label}[{i}]  Mode={MODE.get(rec.get('Mode'), rec.get('Mode'))} "
                  f"ProfileId={rec.get('ProfileId')} 名={rec.get('PlayerName')} 等级={rec.get('Level')} 职业={rec.get('HeroName')} ===")
            show_char(rec)
    print("\n=== LocalStash ===")
    show_stash(obj)

if __name__ == '__main__':
    main()
