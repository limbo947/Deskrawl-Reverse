import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import hashlib, hmac, sys, json

SAVE = GAME_SAVE
PW  = b'desktop-diablo-save-v1-CHANGE-ME'
MACPW = b'desktop-diablo-save-v1-CHANGE-ME|mac'

def aes_cbc_decrypt(key, iv, ct):
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        return dec.update(ct) + dec.finalize()
    except Exception:
        from Crypto.Cipher import AES
        return AES.new(key, AES.MODE_CBC, iv).decrypt(ct)

def unpad(b):
    if not b: return b
    n = b[-1]
    if 1 <= n <= 16 and b[-n:] == bytes([n]) * n:
        return b[:-n]
    return b

data = open(SAVE, 'rb').read()
print('size', len(data), 'magic', data[:4])

key = hashlib.sha256(PW).digest()
mackey = hashlib.sha256(MACPW).digest()

if data[:4] == b'DDS2':
    mac = data[4:36]
    iv = data[36:52]
    ct = data[52:]
    calc = hmac.new(mackey, data[:4] + iv + ct, hashlib.sha256).digest()
    print('MAC match:', calc == mac)
    pt = aes_cbc_decrypt(key, iv, ct)
else:  # DDS1
    iv = data[4:20]
    ct = data[20:]
    pt = aes_cbc_decrypt(key, iv, ct)

pt = unpad(pt)
print('plaintext bytes', len(pt))
txt = pt.decode('utf-8', errors='replace')
print('--- head ---')
print(txt[:600])
try:
    obj = json.loads(txt)
    print('--- valid JSON, top-level keys:', list(obj.keys()))
except Exception as e:
    print('json parse failed:', e)

open(SAVE_DECRYPTED, 'w', encoding='utf-8').write(txt)
print('written ->', SAVE_DECRYPTED)
