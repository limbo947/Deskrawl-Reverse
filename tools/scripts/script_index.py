# -*- coding: utf-8 -*-
"""script.json 索引：字符串字面量 / 元数据条目的「地址 ↔ 语义」双向表。

为什么需要它：`docs/08 §12.6` 的重锚定方法只覆盖「常量按位模式搜」与「方法按签名+Slot 匹配」，
而 `.data` 里的字符串字面量地址（`xref.py` / `chk.py` 用的那批）两者都覆盖不到——
它们的地址由 metadata 决定，补丁后既不是方法也不是常量，只能按**字面量内容**在
新旧 script.json 之间对搬。script.json 有 95 MB，故只做流式单遍解析并支持按需过滤。

历史构建同样只能走 git：`git show <ref>:data/schema/script.json`。
"""
import json
import re
import subprocess

ADDR_RE = re.compile(r'^\s*"Address":\s*(\d+),?\s*$')
STR_RE = re.compile(r'^\s*"Value":\s*("(?:[^"\\]|\\.)*"),?\s*$')
NAME_RE = re.compile(r'^\s*"Name":\s*("(?:[^"\\]|\\.)*"),?\s*$')


def _lines_from_git(ref, rel):
    proc = subprocess.Popen(['git', 'show', f'{ref}:{rel}'], stdout=subprocess.PIPE,
                            cwd=_repo_root(), text=True, encoding='utf-8', errors='replace')
    try:
        for line in proc.stdout:
            yield line
    finally:
        proc.stdout.close()
        proc.wait()


def _repo_root():
    import os
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ScriptIndex:
    """`by_addr`: 地址 → ('string', 值) 或 ('metadata', 名字)；`strings`: 值 → [地址]。"""

    def __init__(self, label=''):
        self.label = label
        self.by_addr = {}
        self.strings = {}
        self.names = {}  # 元数据条目名 → [地址]（ScriptMetadata / ScriptMetadataMethod）

    @classmethod
    def parse(cls, lines, label='', want_values=None, want_addrs=None):
        idx = cls(label)
        addr = None
        for line in lines:
            m = ADDR_RE.match(line)
            if m:
                addr = int(m.group(1))
                continue
            if addr is None:
                continue
            m = STR_RE.match(line)
            if m:
                value = json.loads(m.group(1))
                if want_addrs is None or addr in want_addrs:
                    idx.by_addr[addr] = ('string', value)
                if want_values is None or value in want_values:
                    idx.strings.setdefault(value, []).append(addr)
                addr = None
                continue
            m = NAME_RE.match(line)
            if m:
                name = json.loads(m.group(1))
                if want_values is None or name in want_values:
                    idx.names.setdefault(name, []).append(addr)
                if want_addrs is None or addr in want_addrs:
                    idx.by_addr[addr] = ('metadata', name)
            addr = None
        return idx

    @classmethod
    def load(cls, path, **kw):
        with open(path, encoding='utf-8', errors='replace') as f:
            return cls.parse(f, label=str(path), **kw)

    @classmethod
    def load_from_git(cls, ref, rel='data/schema/script.json', **kw):
        return cls.parse(_lines_from_git(ref, rel), label=f'{ref}:{rel}', **kw)

    def find(self, value, exact=True):
        """按字面量内容找当期地址；非精确模式用于「SaveFileWriter:」这类带尾空格的坑。"""
        if exact:
            return list(self.strings.get(value, []))
        return [a for v, addrs in self.strings.items() if value in v for a in addrs]


if __name__ == '__main__':
    import sys
    import paths
    idx = ScriptIndex.load(paths.SCRIPT_JSON)
    print(f'{idx.label}: string_entries={len(idx.by_addr)} distinct={len(idx.strings)}')
    for probe in ('DDS1', 'DDS2'):
        print(f'  {probe!r} -> {[hex(a) for a in idx.find(probe)]}')
