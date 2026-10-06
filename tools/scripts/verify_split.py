import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403
import re, glob, os

os.chdir(r'C:\Users\<user>\Desktop\Deskrawl-数值设计文档')
orig = open(GAME_SODOC, encoding='utf-8').read()
files = sorted(glob.glob('*.md'))
split = ''.join(open(f, encoding='utf-8').read() for f in files)


def norm(t):
    return re.sub(r'\s+', '', t)


def strip_headings(t):
    """去掉所有 markdown 标题行与导航/分隔符，只留正文"""
    out = []
    for l in t.split('\n'):
        if l.lstrip().startswith('#'):
            continue
        if l.startswith('> 📚'):
            continue
        if set(l.strip()) <= set('-'):
            continue
        out.append(l)
    return '\n'.join(out)


ns = norm(strip_headings(split))
lines = orig.split('\n')
idx = [i for i, l in enumerate(lines) if l.startswith('## ')]
idx.append(len(lines))

bad = 0
for k in range(len(idx) - 1):
    seg = '\n'.join(lines[idx[k]:idx[k + 1]])
    body = norm(strip_headings(seg))
    if body and body not in ns:
        bad += 1
        print('MISSING SEGMENT:', lines[idx[k]][:70])

print('二级章节数:', len(idx) - 1, ' 缺失:', bad)

sub_idx = [i for i, l in enumerate(lines) if l.startswith('### ')]
sub_idx.append(len(lines))
sub_bad = 0
for k in range(len(sub_idx) - 1):
    seg = '\n'.join(lines[sub_idx[k]:sub_idx[k + 1]])
    body = norm(strip_headings(seg))
    if body and body not in ns:
        sub_bad += 1
        print('  MISSING SUB:', lines[sub_idx[k]][:70])
print('三级子段数:', len(sub_idx) - 1, ' 缺失:', sub_bad)

print('\n--- 文件清单 ---')
tot = 0
for f in files:
    n = len(open(f, encoding='utf-8').read().splitlines())
    tot += n
    print(f'{f:<42} {n:>4} 行  {os.path.getsize(f)/1024:>6.1f} KB')
print(f'{"合计":<42} {tot:>4} 行')
