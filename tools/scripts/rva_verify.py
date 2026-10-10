# -*- coding: utf-8 -*-
"""体检的「证据复核」与「报告渲染」段（从 rva_audit.py 拆出，计划任务①的维护性收拾）。

拆分理由：rva_audit.py 的有效行已逼近 700 行上限，而判定链（扫描→分类→消歧）与
这里的复核/渲染是两条独立的关注点——前者改的是「怎么判」，后者改的是「拿什么证明它判得对」。
搬迁零改动，判定行为不变；`labels` / `red_set` 由调用方注入，避免两个模块互相 import。
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def verify_deprecations(cfg):
    """弃用理由必须真的写在文档里：配置说弃用、文档没写 = 用配置消灭红点，直接判错。"""
    out = []
    for e in cfg.get('deprecated', []):
        doc = os.path.join(REPO, e['doc'])
        ok, note = os.path.exists(doc), ''
        if ok:
            text = open(doc, encoding='utf-8', errors='replace').read()
            ok = e['marker'] in text
            note = f"文档 {e['doc']} 中{'已' if ok else '未'}出现标记 {e['marker']!r}"
        else:
            note = f'文档不存在：{e["doc"]}'
        out.append({'file': e['file'], 'doc': e['doc'], 'marker': e['marker'],
                    'ok': ok, 'note': note})
    return out


def verify_doc_sections(cfg, img):
    """复核 docs/08 §12.1 节表：VA / 文件偏移 / 原始大小三列逐项与 PE 头比对。"""
    rows = []
    for row in cfg.get('doc_sections', {}).get('rows', []):
        sec = next((s for s in img.sections if s['name'] == row['name']), None)
        ok = bool(sec) and (img.image_base + sec['rva'] == int(row['va'], 16)
                            and sec['raw'] == int(row['raw'], 16)
                            and sec['rawsize'] == int(row['rawsize'], 16))
        rows.append({'name': row['name'], 'ok': ok,
                     'doc': row, 'actual': None if not sec else
                     {'va': hex(img.image_base + sec['rva']), 'raw': hex(sec['raw']),
                      'rawsize': hex(sec['rawsize'])}})
    return rows


def _near(a, b):
    """常量比对要容忍 float32 往返误差（1.1 存成 float32 读回是 1.100000023…）。"""
    return a is not None and abs(a - b) <= max(1e-6, abs(b) * 1e-6)


def verify_doc_constants(cfg, img):
    """复核 docs/08 §12.2 常量新址：新址必须逐字节读回该值；旧址报告是否仍能读回同值。"""
    rows = []
    for row in cfg.get('doc_constants', {}).get('rows', []):
        value = row['value']
        new_hit, old_hit = img.f64(int(row['va_new'], 16)), img.f64(int(row['va_old'], 16))
        new_f32, old_f32 = img.f32(int(row['va_new'], 16)), img.f32(int(row['va_old'], 16))
        rows.append({
            'name': row['name'], 'value': value, 'va_old': row['va_old'],
            'va_new': row['va_new'], 'new_ok': _near(new_hit, value) or _near(new_f32, value),
            'new_read': f'double={new_hit!r} float32={new_f32!r}',
            'old_read': f'double={old_hit!r} float32={old_f32!r}',
            'old_still_matches': _near(old_hit, value) or _near(old_f32, value)})
    return rows


def _dig(obj, path):
    for part in path.split('.'):
        obj = obj[part]
    return obj


def _collect(node, chk):
    """按配置从 JSON 子树收集待检值：keys=='rva' 取子字典的 rva 字段，否则取短十六进制串。"""
    if isinstance(node, dict) and chk.get('keys') == 'rva':
        return [(k, v['rva']) for k, v in node.items()
                if isinstance(v, dict) and 'rva' in v]
    keep = chk.get('keep')
    if isinstance(node, list):
        return [(str(i), v) for i, v in enumerate(node)]
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            if keep and k not in keep:
                continue
            if isinstance(v, str) and v.startswith('0x') and len(v) <= 6:
                out.append((k, v))
    return out


def verify_offsets(cfg, new_idx, old_idx):
    """复核 memory_offsets.json：实例偏移是否仍是该类字段、方法锚点是否仍是方法起始。

    「仍是某个字段的偏移」是**按偏移值**比对而非按字段名——补丁会重命名字段
    （`nsq`→`nyx`），这正是要证明的那件事：偏移不变、只有名字变。
    """
    spec = cfg.get('offset_checks', {})
    if not spec:
        return []
    data = json.load(open(os.path.join(REPO, spec['json']), encoding='utf-8'))
    out = []
    for chk in spec['checks']:
        try:
            node = _dig(data, chk['path'])
        except (KeyError, TypeError):
            out.append({'path': chk['path'], 'mode': chk['mode'], 'ok': False,
                        'count': 0, 'note': '配置路径在 JSON 中不存在'})
            continue
        mode = chk['mode']
        if mode == 'const':
            expect = chk.get('expect', {})
            bad = [f'{k}={v}（声明 {expect[k]}）' for k, v in node.items()
                   if k in expect and str(v).lower() != str(expect[k]).lower()]
            out.append({'path': chk['path'], 'mode': mode, 'ok': not bad, 'count': len(expect),
                        'note': '结构尺寸与声明一致' if not bad else '与声明不符: ' + ', '.join(bad)})
            continue
        if mode == 'klass':
            ok = node in new_idx.by_klass
            note = f'类 {node} 仍存在' if ok else f'类 {node} 当期不存在'
            if not ok:
                cands, score = new_idx.find_klass_by_shape(
                    node, old_idx.class_sigs.get(node, set()))
                note += f'；按类形状匹配最接近：{cands[:3]}（命中 {score} 个签名）'
            out.append({'path': chk['path'], 'mode': mode, 'ok': ok, 'count': 1,
                        'note': note})
            continue
        # 下面是 field / rva：把「同名但形状不符」的类也一并警示——名字每版重生成，
        # 只在当期存在并不等于就是同一个类。

        items = _collect(node, chk)
        valid = (set(new_idx.fields.get(chk['klass'], {}).values())
                 if mode == 'field' else set())
        bad = []
        for k, v in items:
            iv = int(v, 16)
            hit = bool(new_idx.at(iv)) if mode == 'rva' else iv in valid
            if not hit:
                bad.append(f'{k}={v}')
        out.append({'path': chk['path'], 'mode': mode, 'ok': not bad, 'count': len(items),
                    'note': '全部命中' if not bad else '未命中: ' + ', '.join(bad)})
    return out


def verify_fingerprints(cfg):
    """体检顺带核对 memory_offsets.json 的指纹门禁是否与磁盘上的游戏文件一致。"""
    path = os.path.join(REPO, 'tools/deskrawl_gui/core/memory_offsets.json')
    fp = json.load(open(path, encoding='utf-8'))['fingerprints']
    out = []
    for key, target in (('game_assembly_sha256', paths.GAME_ASSEMBLY),
                        ('global_metadata_sha256', paths.GAME_METADATA)):
        h = hashlib.sha256()
        if os.path.exists(target):
            with open(target, 'rb') as f:
                for chunk in iter(lambda: f.read(1 << 20), b''):
                    h.update(chunk)
            actual = h.hexdigest()
        else:
            actual = '<文件不存在>'
        out.append({'key': key, 'declared': fp.get(key), 'actual': actual,
                    'ok': actual == fp.get(key)})
    return out


def render(payload, findings, cfg, args, bad, labels, red_set):
    """渲染 Markdown 报告。表格顺序固定，便于 diff 比对两次补丁的差异。"""
    L = []
    A = L.append
    sha = next((f['actual'] for f in payload['fingerprints']
                if f['key'] == 'game_assembly_sha256'), '?')
    A('# RVA 体检报告（由 `tools/scripts/rva_audit.py` 自动生成，勿手改）')
    A('')
    A(f"- 命令：`python rva_audit.py"
      + (' --check --falsify' if args.check and args.falsify else
         ' --check' if args.check else ' --falsify' if args.falsify else '') + '`')
    A(f'- 当期 GameAssembly.dll SHA-256：`{sha}`')
    A(f'- 旧构建 dump.cs 来源：`git show {args.base_ref}:data/schema/dump.cs`')
    A(f"- 扫描：{payload['summary']['files']} 个文件 / {payload['summary']['total']} 条地址字面量")
    A('')
    A('## 0. 结论摘要')
    A('')
    A('| 判定 | 条数 |')
    A('|---|---|')
    for s in labels:
        A(f'| {labels[s]} | {payload["summary"].get(s, 0)} |')
    A(f"| **合计** | **{payload['summary']['total']}** |")
    A('')
    A('## 1. 已失效与重算值（写回源码前需人工复核）')
    A('')
    A('| 文件:行 | 注释 | 旧址 | 判定 | 重算值 | 依据 |')
    A('|---|---|---|---|---|---|')
    for f in findings:
        if f.status in red_set:
            h = f.hit
            new = f'`{hex(f.new_addr)}`' if f.new_addr else '—'
            A(f'| `{h.file}:{h.line}` | {h.name or "—"} | `{h.token}` | {labels[f.status]} '
              f'| {new} | {f.evidence or f.detail} |')
    A('')
    A('## 2. 仍有效但注释需更新（地址对、名字过期）')
    A('')
    A('| 文件:行 | 注释名 | 当期名 |')
    A('|---|---|---|')
    for f in findings:
        if f.status == 'valid_renamed':
            A(f'| `{f.hit.file}:{f.hit.line}` | {f.hit.name} | {f.detail} |')
    A('')
    A('## 3. 白名单：判为非地址（每条必须写明理由）')
    A('')
    A('| 文件:行 | 字面量 | 理由 |')
    A('|---|---|---|')
    for f in findings:
        if f.status == 'literal':
            A(f'| `{f.hit.file}:{f.hit.line}` | `{f.hit.token}` | {f.detail} |')
    A('')
    A('## 4b. 历史对照（紧邻「旧/补丁前」标注，刻意保留的旧地址）')
    A('')
    A('| 文件:行 | 字面量 | 原判定 | 重算值 | 上下文 |')
    A('|---|---|---|---|---|')
    for f in findings:
        if f.status == 'historical':
            new = f'`{hex(f.new_addr)}`' if f.new_addr else '—'
            A(f'| `{f.hit.file}:{f.hit.line}` | `{f.hit.token}` '
              f'| {labels[f.extra.get("raw_status", "unknown")]} | {new} | `{f.hit.ctx[-28:]}` |')
    A('')
    A('## 4c. 弃用探针（不参与生产路径，理由与出处见文档；原判定与重算值仍保留）')
    A('')
    A('| 文件:行 | 字面量 | 原判定 | 重算值 | 文档 |')
    A('|---|---|---|---|---|')
    for f in findings:
        if f.status == 'deprecated':
            h = f.hit
            new = f'`{hex(f.new_addr)}`' if f.new_addr else '—'
            raw = labels[f.extra.get('raw_status', 'unknown')]
            A(f'| `{h.file}:{h.line}` | `{h.token}` | {raw} | {new} '
              f'| {f.extra.get("deprecated_doc", "")} |')
    A('')
    A('弃用理由（配置里声明，脚本已校验文档确实写了）：')
    A('')
    seen = {}
    for f in findings:
        if f.status == 'deprecated':
            seen.setdefault(f.hit.file, f.extra.get('deprecated_reason', ''))
    for k, v in sorted(seen.items()):
        A(f'- `{k}`：{v}')
    A('')
    A('## 5. 文档表格复核')
    A('')
    A('### 5.1 docs/08 §12.1 PE 节表')
    A('')
    A('| 节 | 文档 VA | 实测 VA | 文档 raw | 实测 raw | 结论 |')
    A('|---|---|---|---|---|---|')
    for r in payload['doc_sections']:
        a = r['actual'] or {}
        A(f"| `{r['name']}` | `{r['doc']['va']}` | `{a.get('va', '—')}` | `{r['doc']['raw']}` "
          f"| `{a.get('raw', '—')}` | {'✅' if r['ok'] else '❌'} |")
    A('')
    A('### 5.2 docs/08 §9.1+§12.2 常量新旧址（新址必须逐字节读回该值）')
    A('')
    A('| 常量 | 值 | 旧址读取 | 新址 | 新址读取 | 结论 |')
    A('|---|---|---|---|---|---|')
    for r in payload['doc_constants']:
        A(f"| {r['name']} | `{r['value']}` | `{r['old_read']}` | `{r['va_new']}` "
          f"| `{r['new_read']}` | {'✅' if r['new_ok'] else '❌'}"
          + ('（旧址仍读回同值，失效不彻底）' if r['old_still_matches'] else '') + ' |')
    A('')
    A('## 6. memory_offsets.json 复核（结构偏移与方法锚点）')
    A('')
    A('| 配置路径 | 模式 | 命中 | 说明 |')
    A('|---|---|---|---|')
    for o in payload['offsets']:
        A(f"| `{o['path']}` | {o['mode']} | {'✅' if o['ok'] else '❌'} | {o.get('note', '')} |")
    A('')
    A('### 6.1 版本指纹门禁')
    A('')
    A('| 键 | 声明值 | 实测值 | 结论 |')
    A('|---|---|---|---|')
    for f in payload['fingerprints']:
        A(f"| `{f['key']}` | `{str(f['declared'])[:16]}…` | `{f['actual'][:16]}…` "
          f"| {'✅' if f['ok'] else '❌'} |")
    A('')
    A('## 7. 可证伪演示（`--falsify`）')
    A('')
    if payload['falsify']:
        A('| 用例 | 期望 | 实测 | 结论 | 说明 |')
        A('|---|---|---|---|---|')
        for c in payload['falsify']:
            A(f"| `{c['token']}` | {c['expect']} | {c['got']} | {'✅' if c['ok'] else '❌'} "
              f"| {c['why']} |")
    else:
        A('> 未运行。用 `python rva_audit.py --falsify` 生成（故意把已知有效地址改错一位，必须报红）。')
    A('')
    return '\n'.join(L) + '\n'
