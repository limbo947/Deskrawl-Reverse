# -*- coding: utf-8 -*-
"""表格导出的文本层：行 → TSV / CSV（纯函数，Qt-free）。

为什么单独成文件：属性明细、候选排序、技能对比三张表与「复制结论」共用同一套转义规则；
写在各 widget 里迟早各写一遍，而单元格内的制表符/引号一旦漏转，粘进表格就会错列。
"""
from __future__ import annotations

import csv
import io
from typing import Iterable, Sequence

# TSV 没有标准转义：单元格里的 \t/\r/\n 只能压成空格，否则一行会被读成多列/多行
_TSV_FLATTEN = str.maketrans({'\t': ' ', '\r': ' ', '\n': ' '})


def _tsv_cell(value) -> str:
    return str('' if value is None else value).translate(_TSV_FLATTEN)


def rows_to_tsv(headers: Sequence, rows: Iterable[Sequence]) -> str:
    """制表符分隔文本（表头 + 行），可直接粘进 Excel/飞书/群聊。"""
    lines = ['\t'.join(_tsv_cell(h) for h in headers)]
    lines.extend('\t'.join(_tsv_cell(c) for c in row) for row in rows)
    return '\n'.join(lines)


def rows_to_csv(headers: Sequence, rows: Iterable[Sequence]) -> str:
    """CSV 文本（RFC 4180：含逗号/引号/换行时自动加引号）。"""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator='\r\n')
    writer.writerow([str(h) for h in headers])
    writer.writerows([[str(c) for c in row] for row in rows])
    return buf.getvalue()


def write_csv(path: str, headers: Sequence, rows: Iterable[Sequence]) -> int:
    """写 CSV 文件并返回行数（不含表头）。

    为什么用 utf-8-sig：Excel 双击打开无 BOM 的 UTF-8 CSV 会把中文读成乱码，而「导出后用
    Excel 看」正是这条功能的默认用途。
    """
    rows = [list(r) for r in rows]
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        f.write(rows_to_csv(headers, rows))
    return len(rows)
