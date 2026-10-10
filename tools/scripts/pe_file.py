# -*- coding: utf-8 -*-
"""PE 只读工具：节表解析、VA↔文件偏移换算、位模式搜索。

为什么单独成文件：常量重锚定（`docs/08 §12.6` 方法 1）要按**精确位模式**在整映像里搜索，
而「扫描源码地址 → 换算 → 读字节」这条链在体检(①)、别名表(②)、回归脚本(④)里都要用；
仓库里已有的 `read_const.py`/`chk.py`/`xref.py` 各写了一份，重复且各自带打印，故抽公共实现。

约定：VA 一律含 ImageBase（`0x180000000`）；对外只暴露 `sections`、`va2off`、`read`、
`find_pattern`，不暴露原始文件句柄，避免调用方随手写文件。
"""
import struct


class PEImage:
    """只读的 PE 映像视图（惰性读盘，只提供读操作）。"""

    def __init__(self, path):
        self.path = str(path)
        with open(self.path, 'rb') as f:
            self.data = f.read()
        d = self.data
        pe = struct.unpack('<I', d[0x3C:0x40])[0]
        nsec = struct.unpack('<H', d[pe + 6:pe + 8])[0]
        optsz = struct.unpack('<H', d[pe + 20:pe + 22])[0]
        self.image_base = struct.unpack('<Q', d[pe + 24 + 24:pe + 24 + 32])[0]
        so = pe + 24 + optsz
        self.sections = []
        for i in range(nsec):
            o = so + i * 40
            name = d[o:o + 8].rstrip(b'\0').decode('latin1')
            vsize, vaddr, rawsize, rawoff = struct.unpack('<IIII', d[o + 8:o + 24])
            self.sections.append({'name': name, 'rva': vaddr, 'vsize': vsize,
                                  'raw': rawoff, 'rawsize': rawsize})
        self.max_rva = max(s['rva'] + max(s['vsize'], s['rawsize']) for s in self.sections)

    def section_of(self, rva):
        for s in self.sections:
            if s['rva'] <= rva < s['rva'] + max(s['vsize'], s['rawsize']):
                return s
        return None

    def va2off(self, va):
        rva = va - self.image_base
        s = self.section_of(rva)
        if not s or rva - s['rva'] >= s['rawsize']:
            return None
        return s['raw'] + (rva - s['rva'])

    def read(self, va, n):
        o = self.va2off(va)
        return None if o is None else self.data[o:o + n]

    def f64(self, va):
        b = self.read(va, 8)
        return None if b is None or len(b) < 8 else struct.unpack('<d', b)[0]

    def f32(self, va):
        b = self.read(va, 4)
        return None if b is None or len(b) < 4 else struct.unpack('<f', b)[0]

    def find_pattern(self, pattern, section_names=None, limit=64):
        """全映像按位模式搜索，返回命中的 VA 列表（只遍历可读节）。"""
        hits = []
        for s in self.sections:
            if section_names and s['name'] not in section_names:
                continue
            start, end = s['raw'], s['raw'] + s['rawsize']
            i = self.data.find(pattern, start, end)
            while i >= 0 and len(hits) < limit:
                hits.append(self.image_base + s['rva'] + (i - s['raw']))
                i = self.data.find(pattern, i + 1, end)
        return hits

    def find_double(self, value, **kw):
        return self.find_pattern(struct.pack('<d', value), **kw)

    def find_float(self, value, **kw):
        return self.find_pattern(struct.pack('<f', value), **kw)

    def find_ascii(self, text, **kw):
        return self.find_pattern(text.encode('utf-8'), **kw)


def load():
    """按仓库约定加载当前 `GameAssembly.dll`（路径来自 paths.py）。"""
    import paths
    return PEImage(paths.GAME_ASSEMBLY)


if __name__ == '__main__':
    img = load()
    print(f'{img.path}  image_base={img.image_base:#x}  max_rva={img.max_rva:#x}')
    for s in img.sections:
        print(f"  {s['name']:10s} rva={s['rva']:#x} vsize={s['vsize']:#x} "
              f"raw={s['raw']:#x} rawsize={s['rawsize']:#x}")
