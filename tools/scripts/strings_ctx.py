import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
P = GAME_METADATA
d = open(P, 'rb').read()

def show(center, before=48, after=160):
    a = max(0, center-before); b = center+after
    seg = d[a:b]
    # split on NUL and print printable runs
    print(f'--- around {center:#x} ---')
    print(repr(seg))

for off in (0x36f10, 0xbfe9b, 0xc0b56, 0x90167, 0x61685b):
    show(off)
