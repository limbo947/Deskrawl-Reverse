# -*- coding: utf-8 -*-
"""REA 常驻 broker 的调用前端（cli 版）。

存在理由：CodeBuddy 的工具调用有 30 分钟硬超时，而 62 MB IL2CPP 的 Ghidra 全量分析远超它，
`rea_broker.mjs` 因此常驻持有 MCP 会话；本脚本只做两件小事——把请求写进 `request.json`、
轮询 `response.json`，让一次反编译变成毫秒级文件往返。broker 必须已在后台运行（本脚本不启动它，
也不会重启它：重启会丢掉已完成的 Ghidra 分析）。

用法（示例里的 <VA> 是占位符，别写真地址——docstring 里的字面量会被 RVA 体检扫到，
真地址请放 aliases.json 或文档，让体检有据可查）：
    python rea_call.py procedure_pseudo_code procedure=<VA>
    python rea_call.py xrefs address=<VA> --json
"""
import argparse
import json
import os
import sys
import time

BROKER_DIR = os.environ.get('REA_BROKER_DIR') or os.path.join(
    os.environ.get('TEMP') or os.environ.get('TMP') or '/tmp', 'rea-broker')


def _read_json(path):
    try:
        with open(path, encoding='utf-8-sig') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _write_json(path, obj):
    # encoding 显式给 utf-8（不带 BOM）：broker 用 JSON.parse 读，BOM 会让它整批丢弃请求
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(obj, fh, ensure_ascii=False)


def call(tool, args, timeout=1800.0, poll=0.4):
    req_path = os.path.join(BROKER_DIR, 'request.json')
    res_path = os.path.join(BROKER_DIR, 'response.json')
    status = _read_json(os.path.join(BROKER_DIR, 'status.json')) or {}
    prev = _read_json(req_path) or {}
    seq = max(int(status.get('lastSeq') or 0), int(prev.get('seq') or 0)) + 1

    _write_json(req_path, {'seq': seq, 'tool': tool, 'args': args})
    deadline = time.time() + timeout
    while time.time() < deadline:
        res = _read_json(res_path)
        if res and res.get('seq') == seq:
            return res
        time.sleep(poll)
    raise SystemExit(f'超时 {timeout}s：broker 未在期限内写回 seq={seq}（检查 {BROKER_DIR}\\status.json）')


def _parse_args(tokens):
    """参数既支持 JSON 也支持 `k=v` 多段写法。

    为什么要两种：Windows 的 PowerShell/命令行转义会吃掉 `\\"`，把 JSON 变成非法串
    （实测：带转义的 JSON 到进程时引号已被剥掉）。`k=v` 不经过引号转义，跨 shell 稳定；
    地址一律写 VA（占位符 <VA> = 0x180000000 + RVA），字面量请留在 aliases.json/文档里受体检管辖。
    """
    if not tokens:
        return {}
    if len(tokens) == 1 and tokens[0].lstrip().startswith('{'):
        return json.loads(tokens[0])
    out = {}
    for tok in tokens:
        k, _, v = tok.partition('=')
        out[k] = v
    return out


def main():
    ap = argparse.ArgumentParser(description='向 REA broker 发一次工具调用')
    ap.add_argument('tool')
    ap.add_argument('args', nargs='*', default=[], help='JSON 参数，或 k=v 形式的多段参数')
    ap.add_argument('--raw', action='store_true', help='打印完整响应而非只取 MCP 文本')
    ap.add_argument('--full', action='store_true', help='连证据块一起打印（默认只打印 result）')
    ap.add_argument('--json', action='store_true', help='只打印 structuredContent.result（列表类结果更干净）')
    ap.add_argument('--brief', action='store_true', help='引用类结果只打印跨函数的那几列')
    ap.add_argument('--timeout', type=float, default=1800.0)
    ns = ap.parse_args()

    res = call(ns.tool, _parse_args(ns.args), timeout=ns.timeout)
    if ns.raw:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res.get('ok') else 1

    result = res.get('result') or {}
    if ns.brief and 'structuredContent' in result:
        # 引用类结果（procedure_references）原始 JSON 有几十行/条，只留「谁调了谁」这一列
        payload = result['structuredContent'].get('result') or {}
        refs = payload.get('references') if isinstance(payload, dict) else None
        for r in refs or []:
            srcp = r.get('source_procedure') or {}
            tgtp = r.get('target_procedure') or {}
            kind = (r.get('kind') or {}).get('type', '?')
            # 只要跨函数的引用（函数体内的跳转是同函数控制流，不是调用点）
            if srcp.get('address') == tgtp.get('address'):
                continue
            print(f'{srcp.get("address", "?"):12s} {kind:20s} -> {r.get("target_address")}')
        return 0 if res.get('ok') else 1
    if ns.json and 'structuredContent' in result:
        print(json.dumps(result['structuredContent'].get('result'), ensure_ascii=False, indent=2))
        return 0 if res.get('ok') else 1
    texts = [c.get('text', '') for c in result.get('content', []) or []]
    body = '\n'.join(texts) if texts else json.dumps(res.get('error'), ensure_ascii=False)
    # MCP 文本本身常是一层 JSON（含 result/evidence），默认只吐 result 字段，避免几十行证据噪声
    if not ns.full:
        try:
            inner = json.loads(body)
        except ValueError:
            inner = None
        if isinstance(inner, dict):
            body = inner.get('result', body)
            if not isinstance(body, str):
                body = json.dumps(body, ensure_ascii=False, indent=2)
    print(body)
    # ok=false 或 MCP 文本里带 error 对象都算失败，便于在脚本/CD 里判红
    return 0 if res.get('ok') and '"error"' not in body[:200] else 1


if __name__ == '__main__':
    sys.exit(main())
