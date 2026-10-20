# -*- coding: utf-8 -*-
"""打便携包 zip：用 zipfile 而不是 Compress-Archive —— 后者写非 ASCII 条目名时不置 UTF-8
标志，在非 Windows 解压器上会变乱码；zipfile 在名字含非 ASCII 时自动置位，跨平台稳。
"""
from __future__ import annotations

import os
import sys
import zipfile

# CI 的 stdout 是 cp1252（Windows runner 默认代码页）：直接 print 中文会
# UnicodeEncodeError —— v1.0.0 首次发布就挂在这里（PyInstaller 已成功、只差 zip 那一行）。
# 统一给两个流换成 UTF-8，本地（GBK）与 CI 走同一编码，不会再因终端语言不同而失败。
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, 'reconfigure'):
        _stream.reconfigure(encoding='utf-8', errors='replace')


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    zip_path, src_dir = argv[0], argv[1]
    base = os.path.dirname(os.path.abspath(src_dir))
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for dirpath, _dirs, files in os.walk(src_dir):
            for name in files:
                full = os.path.join(dirpath, name)
                z.write(full, os.path.relpath(full, base))   # 保留顶层文件夹，解压得到一个目录
    mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f'已打包 {zip_path}（{mb:.1f} MB）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
