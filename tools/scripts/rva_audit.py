# -*- coding: utf-8 -*-
"""全仓地址体检：一条命令列出、分类并重算写死在仓库里的地址（计划任务①）。

为什么脚本「只报告、不写回」：地址自动写错会污染全仓且难回滚，故本脚本只产出
`docs/reports/RVA体检报告.md` + `data/schema/rva_audit.json`，写回由人工复核后单独提交。

每个地址字面量走同一条判定链（先到先得）：
  ① 配置白名单 / 自动非地址规则（ImageBase、微常量、超出映像的掩码）
  ② 当期 dump.cs 的方法起始 RVA            → 仍有效
  ③ 旧构建 dump.cs 同名方法（签名 + Slot，混淆类再按类形状匹配）→ 已失效 + 重算值
  ④ docs/08 §12.2 常量表（旧址/新址）        → 已失效 + 重算值，或仍有效
  ⑤ 旧 script.json 的字符串/元数据条目       → 已失效 + 重算值
  ⑥ 旧构建中「含有该地址的方法」             → 已失效（内联数据，只能改方法级引用）
  ⑦ 都判不了 → 人工确认（配置文件里登记的弃用探针除外，且弃用理由必须写在文档里）

为什么 `--check` 与 `--falsify` 必须同时存在：`--check` 是给回归用的门（红=有死地址未处理），
`--falsify` 用来证明这扇门不是「一律放行」——故意把已知有效地址改错一位，它必须报红。
"""
import argparse
import fnmatch
import hashlib
import json
import math
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402
import dump_index  # noqa: E402
import pe_file  # noqa: E402
import script_index  # noqa: E402
import rva_verify  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
CONFIG = os.path.join(HERE, 'rva_audit_config.json')
REPORT = os.path.join(REPO, 'docs', 'reports', 'RVA体检报告.md')
JSON_OUT = os.path.join(REPO, 'data', 'schema', 'rva_audit.json')
OLD_DUMP_REF = '8660446'  # 补丁前最后一次提交 dump.cs 的 ref；换补丁时用 --base-ref 覆盖
MIN_SHAPE = 3  # 类形状匹配的最低签名命中数：低于它不足以认定「同一个类」

LABEL = {
    'literal': '非地址（白名单/自动规则）',
    'valid': '仍有效（方法）',
    'valid_renamed': '仍有效（注释里的方法名已过期）',
    'data_valid': '仍有效（数据地址）',
    'stale_relocated': '已失效（已给出重算值）',
    'stale_inline': '已失效（内联数据，只能改成方法级引用）',
    'stale_ambiguous': '已失效（重算候选不唯一）',
    'stale_unresolved': '已失效（无法重算）',
    'data_stale': '已失效（数据地址已迁移）',
    'unknown': '无法判定（人工确认）',
    'historical': '历史对照（有意保留的旧地址）',
    'deprecated': '弃用探针（理由已写入文档）',
}
RED = ('stale_relocated', 'stale_inline', 'stale_ambiguous', 'stale_unresolved',
       'data_stale', 'unknown')
# 「旧 xxx」这类紧邻标注说明作者是**故意**保留旧地址做对照（旧→新映射的存档），
# 重写它反而毁掉下一次补丁要用的线索。仅对「本来会判失效」的地址生效。
HIST_RE = re.compile(r'旧|补丁前|已被|原(?:名|址)')
# 判定里的「名字」取词时容易捞到这些关键字，必须排除，否则会把 RVA/VA 当成方法名比对
NAME_STOP = {'rva', 'va', 'offset', 'fileoff', 'at', 'addr', 'address', 'id'}


class Hit:
    __slots__ = ('file', 'line', 'col', 'token', 'value', 'text', 'name', 'ctx')

    def __init__(self, file, line, col, token, value, text, name, ctx):
        self.file, self.line, self.col = file, line, col
        self.token, self.value, self.text = token, value, text
        self.name, self.ctx = name, ctx

    @property
    def key(self):
        return f'{self.file}:{self.line}:{self.token}'


def annotate(text, start, idx=0):
    """从地址字面量**左侧**取语义线索：`bjr@0x...` → bjr，`kah() @0x...` → kah。

    返回 (名字, 上下文)。名字只用于报告比对，绝不作为判定依据——混淆名每版都变。
    `idx` 是该字面量在本行内的序号，用于 `START, END = 0x.., 0x..` 这种成对赋值。
    """
    pre = text[:start].rstrip()
    ctx = pre[-48:]
    # `A, B = 0x1, 0x2`：第二个字面量的左侧还挂着第一个地址，先剥掉才能认出名字
    pre = re.sub(r'0x[0-9A-Fa-f]+\s*[,、]\s*$', '', pre).rstrip()
    m = re.match(r'^(.+?)\s*=\s*$', pre)
    if m and ',' in m.group(1):
        parts = [p.strip() for p in m.group(1).split(',')]
        if idx < len(parts):
            cand = re.search(r'([A-Za-z_][A-Za-z0-9_]*)$', parts[idx])
            if cand and not cand.group(1).isupper():
                return cand.group(1), ctx
    for _ in range(3):
        stripped = re.sub(r'(?i)\b(rva|va|offset|fileoff|at|addr)\b\s*$', '', pre).rstrip()
        if stripped != pre:
            pre = stripped
            continue
        if pre[-1:] in '@=(,:.、，':
            pre = pre[:-1].rstrip()
            continue
        break
    pre = re.sub(r'\([^()]*\)\s*$', '', pre).rstrip()
    pre = pre.rstrip('`|）】〕,;')
    m = re.search(r'([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)$', pre)
    name = m.group(1) if m else None
    if name and (name.lower() in NAME_STOP or name.isdigit() or name.startswith('0x')
                 or name.isupper()):
        name = None  # 全大写多为常量/变量名（START/END/RVA），不是方法名
    return name, ctx


def scan_hits(cfg, with_docs=False):
    """扫描配置指定根目录，返回按 (文件, 行, 列) 排序的字面量命中。

    文档默认不扫：计划 §3.1 的扫描面是 `tools/**/*.py`，而文档里几百个旧 RVA
    属另一条工作线（重写 §12 类章节）。`--docs` 打开后走同一条判定链，
    产出「文档重锚定工单」——数字可见，但不因此把默认门禁变红。
    """
    sc = cfg['scan']
    pat = re.compile(r'(?<![0-9A-Za-z_])0x([0-9A-Fa-f]{%d,%d})\b'
                     % (sc.get('min_digits', 4), sc.get('max_digits', 10)))
    roots = list(sc['roots'])
    suffixes = list(sc['suffixes'])
    if with_docs:
        roots.append('docs')
        suffixes.append('.md')
    excl = sc.get('exclude_globs', [])
    files = []
    for root in roots:
        base = os.path.join(REPO, root)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d != '__pycache__']
            for fn in filenames:
                if not any(fn.endswith(s) for s in suffixes):
                    continue
                rel = os.path.relpath(os.path.join(dirpath, fn), REPO).replace('\\', '/')
                # 机器产出的报告按设计就含大量地址（它们是地址的陈列柜），扫它只会制造噪声
                if any(fnmatch.fnmatch(rel, g) for g in excl):
                    continue
                files.append(os.path.join(dirpath, fn))
    hits = []
    for path in sorted(files):
        rel = os.path.relpath(path, REPO).replace('\\', '/')
        with open(path, encoding='utf-8', errors='replace') as f:
            for lineno, text in enumerate(f, 1):
                for n, m in enumerate(pat.finditer(text)):
                    start = m.start()
                    name, ctx = annotate(text, start, n)
                    hits.append(Hit(rel, lineno, start, m.group(0), int(m.group(1), 16),
                                    text.rstrip('\n'), name, ctx))
    hits.sort(key=lambda h: (h.file, h.line, h.col))
    return hits


class Finding:
    def __init__(self, hit, status, detail, new_addr=None, evidence='', extra=None):
        self.hit, self.status, self.detail = hit, status, detail
        self.new_addr, self.evidence = new_addr, evidence
        self.extra = extra or {}

    def to_dict(self):
        return {'file': self.hit.file, 'line': self.hit.line, 'token': self.hit.token,
                'value': hex(self.hit.value), 'annotation': self.hit.name,
                'context': self.hit.ctx, 'status': self.status, 'label': LABEL[self.status],
                'detail': self.detail, 'new_addr': hex(self.new_addr) if self.new_addr else None,
                'evidence': self.evidence, **self.extra}


class Auditor:
    """把「一个地址字面量」判成「仍有效 / 已失效+重算值 / 人工确认」。"""

    def __init__(self, cfg, old_idx, new_idx, img, old_scripts, new_scripts, aliases=None):
        self.cfg, self.old, self.new, self.img = cfg, old_idx, new_idx, img
        self.old_scripts, self.new_scripts = old_scripts, new_scripts
        self.aliases = (aliases or {}).get('aliases', {})
        self.lit = {}
        for e in cfg.get('literal', []):
            for tok in ([e['token']] if 'token' in e else []) + list(e.get('tokens', [])):
                self.lit[f"{e['file']}:{tok}"] = e['reason']
        self.deprecated = {e['file']: e for e in cfg.get('deprecated', [])}
        self.refs = {}
        for e in cfg.get('data_refs', []):
            for tok in ([e['token']] if 'token' in e else []) + list(e.get('tokens', [])):
                self.refs[f"{e['file']}:{tok}"] = e['reason']
        pol = cfg.get('doc_policy', {})
        self.hist_docs = {e['file']: e['reason'] for e in pol.get('historical_docs', [])}
        self.mark_begin = pol.get('marker_begin', 'rva-audit:historical')
        self.mark_end = pol.get('marker_end', '/rva-audit:historical')
        self._regions = {}
        self.consts = {}
        for row in cfg.get('doc_constants', {}).get('rows', []):
            for k in ('va_old', 'va_new'):
                self.consts[int(row[k], 16)] = (k, row)
        self._shape_cache = {}
        self._anchor_cache = {}

    # ---- 混淆类改名后的类形状匹配（缓存，避免每次遍历 7000 个类） ----
    def _shape(self, klass):
        if klass not in self._shape_cache:
            classes, score = self.new.find_klass_by_shape(
                klass, self.old.class_sigs.get(klass, set()))
            self._shape_cache[klass] = classes if score >= MIN_SHAPE else []
        return self._shape_cache[klass]

    def _class_order(self, klass):
        """按可信度排候选类，并识别「撞名」。

        为什么必须自证：混淆名**每版重新生成**，同一个名字（如 `iw`）在新构建里可能
        是完全不相干的另一个类（实测 `iw` 同名类签名交集 0/5，真身是 `je`）。若不做这层
        校验，同签名匹配会落到错误的类上——那比找不到更危险。
        """
        own = self.old.class_sigs.get(klass, set())
        order, note = [], ''
        if klass in self.new.by_klass:
            inter = len(own & self.new.class_sigs[klass])
            need = max(MIN_SHAPE, int(len(own) * 0.6))
            if inter >= need or (len(own) <= 2 and inter >= 1):
                order.append(klass)
            else:
                note = f'{klass} 同名类形状自证不足（签名交集 {inter}/{len(own)}），判为撞名'
        for k in self._shape(klass):
            if k not in order:
                order.append(k)
        return order, note

    def _unique_relocate(self, om):
        """只按「类 + 归一化签名 + Slot」判定，不做顺序消歧（顺序消歧需要它作锚点）。"""
        order, note = self._class_order(om.klass)
        for klass in order:
            cands = self.new.find(klass, om.sig, om.slot)
            if cands:
                why = ('同类同签名 + Slot' if klass == om.klass
                       else f'类形状匹配（{om.klass} → {klass}）')
                return cands, f'{note}；{why}' if note else why
        if '.' in om.klass:
            # 嵌套类在 dump 里写作 A.B；重命名后外层与外层、内层与内层各自改名，
            # 故先把外层定位到当期类，再在它的嵌套类里按签名找。
            outer, inner = om.klass.rsplit('.', 1)
            for outer_new in [outer] + self._shape(outer):
                for k in self.new.by_klass:
                    if not k.startswith(outer_new + '.'):
                        continue
                    cands = self.new.find(k, om.sig, om.slot)
                    if len(cands) == 1:
                        return cands, f'嵌套类重锚定（{om.klass} → {k}）'
            cands = self.new.find(inner, om.sig, om.slot)
            if len(cands) == 1:
                return cands, f'嵌套类名退化匹配（{om.klass} → {inner}）'
        any_c = self.new.match_any(om.sig, om.slot)
        if len(any_c) == 1:
            return any_c, '跨类唯一同签名候选'
        return [], note

    def _anchors(self, klass):
        """类内「可唯一定位」的兄弟方法，用作消歧标尺：(旧序, 新 RVA)。"""
        if klass not in self._anchor_cache:
            sibs = sorted(self.old.by_klass.get(klass, []), key=lambda m: m.rva)
            anchors = []
            for j, m in enumerate(sibs):
                c, _ = self._unique_relocate(m)
                if len(c) == 1:
                    anchors.append((j, c[0].rva))
            self._anchor_cache[klass] = (sibs, anchors)
        return self._anchor_cache[klass]

    def _group_pick(self, om, cands):
        """同签名组按序对齐：组内旧方法数 == 新候选数时，第 k 个对第 k 个。

        依据是同一编译单元内方法顺序稳定。补丁**新增**方法会让两边数量不等，
        此时本规则主动放弃（不猜）。
        """
        sibs = [m for m in self.old.by_klass.get(om.klass, [])
                if m.sig == om.sig and m.slot == om.slot]
        if not sibs or len(sibs) != len(cands) or om not in sibs:
            return None
        sibs.sort(key=lambda m: m.rva)
        pair = sorted(cands, key=lambda c: c.rva)[sibs.index(om)]
        return (pair, f'同签名组按序对齐（旧 {len(sibs)} 个 ↔ 新 {len(cands)} 个，组内顺序视为一致）')

    def _interval_pick(self, om, cands):
        """区间消歧：取夹在「最近可定位前驱/后继」新区间内的候选。"""
        sibs, anchors = self._anchors(om.klass)
        i = next((j for j, m in enumerate(sibs) if m is om), None)
        if i is None or not anchors:
            return None
        prev = max((a for a in anchors if a[0] < i), default=None, key=lambda a: a[0])
        nxt = min((a for a in anchors if a[0] > i), default=None, key=lambda a: a[0])
        if prev is None and nxt is None:
            return None
        ok = [c for c in cands
              if (prev is None or c.rva > prev[1]) and (nxt is None or c.rva < nxt[1])]
        if len(ok) == 1:
            return ok[0], '类内区间消歧（前驱/后继已唯一定位）'
        return None

    def _delta_pick(self, om, cands):
        """整类位移消歧：类内多数锚点的 (旧 RVA − 新 RVA) 若一致，即按该位移预测新址。

        实测补丁后的重排多是「整段搬移 + 局部增删」，所以多数位移是强信号；
        少数派锚点占比过高（<60%）说明这个类在补丁里被大改，此时不猜。
        """
        sibs, anchors = self._anchors(om.klass)
        if len(anchors) < 4:
            return None
        hist = {}
        for j, new_rva in anchors:
            delta = sibs[j].rva - new_rva
            hist[delta] = hist.get(delta, 0) + 1
        delta, cnt = max(hist.items(), key=lambda kv: kv[1])
        if cnt < max(4, int(len(anchors) * 0.6)):
            return None
        pred = om.rva - delta
        near = [c for c in cands if abs(c.rva - pred) <= 0x40]
        if len(near) == 1:
            return (near[0], f'整类位移 {hex(delta)}（{cnt}/{len(anchors)} 个锚点一致），'
                            f'候选落在预测址 {hex(pred)} ±0x40 内')
        return None

    def relocate(self, om):
        cands, why = self._unique_relocate(om)
        if len(cands) == 1:
            return cands, why
        if len(cands) > 1:
            for picker in (self._group_pick, self._interval_pick, self._delta_pick):
                got = picker(om, cands)
                if got:
                    return [got[0]], got[1]
        return cands, why

    def _doc_regions(self, path):
        """解析文档里的历史证词区块：`<!-- rva-audit:historical 理由 -->` … `<!-- /rva-audit:historical -->`。

        为什么标记写在文档里而不是配置里：行号会随文档编辑漂移，标记跟着内容走，
        且理由落在使用处，评审不必跳文件。只对「本来会判失效」的地址生效——
        区块内的当期地址依旧照常判「仍有效」，不会被整片掩盖。
        """
        if path in self._regions:
            return self._regions[path]
        regions, start, reason = [], None, ''
        try:
            with open(os.path.join(REPO, path), encoding='utf-8', errors='replace') as fh:
                for lineno, text in enumerate(fh, 1):
                    if self.mark_begin in text and self.mark_end not in text:
                        start, reason = lineno, text.split(self.mark_begin, 1)[1].strip(' \t->-')
                    elif self.mark_end in text and start:
                        regions.append((start, lineno, reason))
                        start, reason = None, ''
        except OSError:
            pass
        self._regions[path] = regions
        return regions

    def _doc_history(self, hit):
        """该命中是否落在「已声明的历史证词」里（整篇登记或区块标记），返回理由。"""
        if not hit.file.endswith('.md'):
            return None
        if hit.file in self.hist_docs:
            return self.hist_docs[hit.file]
        for s, e, reason in self._doc_regions(hit.file):
            if s <= hit.line <= e:
                return reason or '（标记未写理由）'
        return None

    def _alias_ok(self, name, m):
        """注释写的是语义别名：只要该别名指的就是当期这个方法，就不算「注释名过期」。"""
        entry = self.aliases.get(name)
        return bool(entry) and entry['current']['rva'] == hex(m.rva)

    def method_audit(self, hit, rva):
        here = self.new.at(rva)
        if here:
            m = here[0]
            status = 'valid'
            detail = f'{m.klass}::{m.name}({m.sig.split("<m>", 1)[-1].lstrip("( ")}) Slot={m.slot}'
            if hit.name and hit.name != m.name:
                if self._alias_ok(hit.name, m):
                    return Finding(hit, 'valid', f'语义别名 {hit.name} → 当期 {m.klass}::{m.name}',
                                   extra={'method': m.full, 'alias': hit.name})
                if hit.name.rsplit('.', 1)[-1] != m.name:
                    status = 'valid_renamed'
                    detail = f'注释名 {hit.name} → 当期名 {m.name}；{detail}'
            return Finding(hit, status, detail, extra={'method': m.full, 'slot': m.slot})
        olds = self.old.at(rva)
        if olds:
            # 同一 RVA 可能被多个类共享（泛型实例/继承会把同一份代码挂在两个类名下），
            # 此时注释里的名字是唯一线索，优先取与注释名同名者作证据。
            om = olds[0]
            if hit.name and len(olds) > 1:
                leaf = hit.name.rsplit('.', 1)[-1]
                om = next((m for m in olds if m.name == leaf), om)
            cands, why = self.relocate(om)
            if len(cands) == 1:
                nm = cands[0]
                return Finding(hit, 'stale_relocated',
                               f'旧 {om.klass}::{om.name} → 新 {nm.klass}::{nm.name}（{why}）',
                               new_addr=nm.va, evidence=f'dump.cs 签名+Slot 匹配（{why}）',
                               extra={'old_method': f'{om.klass}::{om.name}',
                                      'new_method': nm.full, 'new_name': nm.name,
                                      'new_rva': hex(nm.rva), 'new_va': hex(nm.va)})
            if len(cands) > 1:
                return Finding(hit, 'stale_ambiguous',
                               f'旧 {om.klass}::{om.name} 在当期有 {len(cands)} 个同签名候选',
                               evidence='dump.cs 签名匹配',
                               extra={'candidates': [c.va for c in cands]})
            return Finding(hit, 'stale_unresolved', f'旧 {om.klass}::{om.name} 在当期找不到对应方法')
        om = self.old.containing(rva)
        sec = self.img.section_of(rva)
        if om and sec and sec['name'] in ('.text', 'il2cpp'):
            cands, why = self.relocate(om)
            tail = (f'所属方法已迁移到 {hex(cands[0].va)}（{why}）'
                    if len(cands) == 1 else '所属方法在当期未定位')
            return Finding(hit, 'stale_inline',
                           f'落在方法 {om.klass}::{om.name} 内部（内联数据或地址笔误）；{tail}',
                           new_addr=cands[0].va if len(cands) == 1 else None)
        return None

    def data_audit(self, hit, rva):
        va = self.img.image_base + rva
        if va in self.consts:
            which, row = self.consts[va]
            if which == 'va_new':
                got = self.read_const(va, row['value'])
                if got:
                    return Finding(hit, 'data_valid', f"常量「{row['name']}」= {row['value']}（{got}）",
                                   extra={'const': row['name']})
                return Finding(hit, 'data_stale',
                               f"地址落在常量「{row['name']}」新址上，但读回的字节 ≠ {row['value']}",
                               evidence='docs/08 §12.2')
            return Finding(hit, 'stale_relocated',
                           f"常量「{row['name']}」旧簇地址 → 新址 {row['va_new']}",
                           new_addr=int(row['va_new'], 16),
                           evidence='docs/08 §12.2 新址表（字节校验通过）')
        entry = self.old_scripts.by_addr.get(va)
        if entry:
            kind, value = entry
            if kind == 'string':
                found = self.new_scripts.find(value)
                if len(found) == 1:
                    return Finding(hit, 'data_stale', f'字符串字面量 {value!r} 已迁移',
                                   new_addr=self.img.image_base + found[0],
                                   evidence='新旧 script.json 按字面量内容对搬')
                if len(found) > 1:
                    return Finding(hit, 'stale_ambiguous', f'字面量 {value!r} 当期有 {len(found)} 处',
                                   extra={'candidates': [hex(self.img.image_base + a) for a in found]})
                return Finding(hit, 'stale_unresolved', f'字面量 {value!r} 当期 script.json 中已不存在')
            if kind == 'metadata':
                found = self.new_scripts.names.get(value, [])
                if len(found) == 1:
                    return Finding(hit, 'data_stale', f'元数据条目 {value} 已迁移',
                                   new_addr=self.img.image_base + found[0],
                                   evidence='新旧 script.json 按条目名对搬')
                return Finding(hit, 'unknown', f'旧构建此处是元数据条目 {value}，当期未唯一定位')
        return None

    def read_const(self, va, value):
        """按声明值反查存储形式。用容差而非 == ：float32 存不下精确的 1.1
        （读回 1.100000023841858），逐位相等会把「float32 存的就是它」误判成失效。"""
        f64, f32 = self.img.f64(va), self.img.f32(va)
        for label, got in (('double', f64), ('float32', f32)):
            if got is not None and math.isclose(got, value, rel_tol=1e-6, abs_tol=1e-9):
                return label
        return None

    def audit(self, hit):
        reason = self.lit.get(f'{hit.file}:{hit.token}')
        if reason:
            return Finding(hit, 'literal', reason)
        ref = self.refs.get(f'{hit.file}:{hit.token}')
        if ref:
            return Finding(hit, 'data_valid', f'已登记的数据指针：{ref}',
                           evidence='rva_audit_config.json:data_refs')
        v = hit.value
        if v == self.img.image_base:
            return Finding(hit, 'literal', 'PE ImageBase 本身（节表换算基准），不是可寻址目标')
        if v < 0x1000:
            return Finding(hit, 'literal', '四位以内的微常量（位掩码/计数/标志），不可能是地址')
        rva = v - self.img.image_base if v >= self.img.image_base else v
        if rva >= self.img.max_rva:
            return Finding(hit, 'literal',
                           f'值 {hit.token} 超出映像范围（max_rva={hex(self.img.max_rva)}），'
                           '是掩码/哨兵而非地址')
        f = self.method_audit(hit, rva) or self.data_audit(hit, rva)
        if f is None:
            sec = self.img.section_of(rva)
            where = f"{sec['name']} 节" if sec else '任何节之外'
            f = Finding(hit, 'unknown', f'落在 {where}（{hex(rva)}），既非方法起始也非已知数据条目')
        if f.status in RED:
            why = self._doc_history(hit)
            if why:
                f.extra['raw_status'] = f.status
                f.status = 'historical'
                f.detail = f'文档已声明为历史证词（{why}）；原判定：{f.detail}'
        if f.status in RED and HIST_RE.search(hit.ctx[-16:]):
            f.extra['raw_status'] = f.status
            f.status = 'historical'
            f.detail = f'紧邻的「旧/补丁前」标注表明是刻意保留的对照记录；原判定：{f.detail}'
        if f.status in RED and hit.file in self.deprecated:
            dep = self.deprecated[hit.file]
            f.extra['deprecated_reason'] = dep['reason']
            f.extra['deprecated_doc'] = dep['doc']
            f.extra['raw_status'] = f.status
            f.status = 'deprecated'
            f.detail = f'原判定（仅供参考，该文件不在生产路径上）：{f.detail}'
        return f


def run_falsify(cfg, auditor):
    """证伪：把已知有效地址改错一位，判定链必须报「已失效」；真值必须仍判有效。"""
    cases = cfg.get('falsify', {}).get('cases', [])
    results = []
    for i, case in enumerate(cases, 1):
        h = Hit('<falsify>', i, 0, case['token'], int(case['token'], 16), case['token'], None, '')
        f = auditor.audit(h)
        want_red = case['expect'] == 'stale'
        got_red = f.status in RED
        results.append({'token': case['token'], 'why': case['why'],
                        'expect': case['expect'], 'got': f.status,
                        'ok': got_red == want_red, 'detail': f.detail})
    return results


def build_arg_parser():
    p = argparse.ArgumentParser(description='全仓地址体检（只报告，不写回源码）')
    p.add_argument('--check', action='store_true', help='存在「已失效/无法判定」条目时退出码非 0')
    p.add_argument('--falsify', action='store_true', help='跑证伪用例（改错一位必须报红）')
    p.add_argument('--docs', action='store_true',
                   help='同时扫描 docs/**/*.md（产出文档重锚定工单，默认不扫）')
    p.add_argument('--base-ref', default=OLD_DUMP_REF, help='旧构建 dump.cs 所在的 git ref')
    p.add_argument('--report', default=REPORT, help='Markdown 报告输出路径')
    p.add_argument('--json', dest='json_out', default=JSON_OUT, help='机器可读输出路径')
    p.add_argument('--no-write', action='store_true', help='只打印摘要，不落盘（调试用）')
    return p


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    cfg = json.load(open(CONFIG, encoding='utf-8'))
    hits = scan_hits(cfg, with_docs=args.docs)
    img = pe_file.load()
    new_idx = dump_index.DumpIndex.load(paths.DUMP_CS)
    old_idx = dump_index.DumpIndex.load_from_git(args.base_ref)
    # script.json 只按需要的地址/字面量过滤加载：文件 95 MB，全量建表毫无必要
    want_addrs = {img.image_base + (h.value - img.image_base if h.value >= img.image_base
                                    else h.value) for h in hits}
    old_scripts = script_index.ScriptIndex.load_from_git(
        args.base_ref, want_addrs=want_addrs)
    want_values = {v for k, v in old_scripts.by_addr.values() if k == 'string'}
    want_values |= {v for k, v in old_scripts.by_addr.values() if k == 'metadata'}
    new_scripts = script_index.ScriptIndex.load(
        paths.SCRIPT_JSON, want_values=want_values)

    alias_path = os.path.join(REPO, 'data', 'schema', 'aliases.json')
    aliases = json.load(open(alias_path, encoding='utf-8')) if os.path.exists(alias_path) else {}
    auditor = Auditor(cfg, old_idx, new_idx, img, old_scripts, new_scripts, aliases)
    findings = [auditor.audit(h) for h in hits]
    doc_secs = rva_verify.verify_doc_sections(cfg, img)
    doc_consts = rva_verify.verify_doc_constants(cfg, img)
    deps = rva_verify.verify_deprecations(cfg)
    offsets = rva_verify.verify_offsets(cfg, new_idx, old_idx)
    fps = rva_verify.verify_fingerprints(cfg)
    falsify = run_falsify(cfg, auditor) if args.falsify else []

    summary = {s: sum(1 for f in findings if f.status == s) for s in LABEL}
    summary['total'] = len(findings)
    summary['files'] = len({f.hit.file for f in findings})
    red = [f for f in findings if f.status in RED]
    bad = {
        'doc_sections': [r for r in doc_secs if not r['ok']],
        'doc_constants': [r for r in doc_consts if not r['new_ok']],
        'deprecations': [d for d in deps if not d['ok']],
        'offsets': [o for o in offsets if not o['ok']],
        'fingerprints': [f for f in fps if not f['ok']],
        'falsify': [c for c in falsify if not c['ok']],
    }

    payload = {'build': {'game_assembly_sha256': dict(
        (f['key'], f['actual']) for f in fps if f['key'] == 'game_assembly_sha256')},
        'old_dump_ref': args.base_ref, 'summary': summary,
        'findings': [f.to_dict() for f in findings],
        'doc_sections': doc_secs, 'doc_constants': doc_consts,
        'deprecations': deps, 'offsets': offsets, 'fingerprints': fps,
        'falsify': falsify, 'red': [f.hit.key for f in red]}
    if not args.no_write:
        os.makedirs(os.path.dirname(args.json_out), exist_ok=True)
        json.dump(payload, open(args.json_out, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        open(args.report, 'w', encoding='utf-8').write(
            rva_verify.render(payload, findings, cfg, args, bad, LABEL, RED))

    print(f"扫描 {summary['files']} 个文件 / {summary['total']} 条地址字面量")
    for s in LABEL:
        if summary.get(s):
            print(f'  {summary[s]:4d}  {LABEL[s]}')
    for name, items in bad.items():
        if items:
            print(f'  ✗ {name}: {len(items)} 项异常 -> {json.dumps(items[0], ensure_ascii=False)[:160]}')
    if red:
        print(f'✗ {len(red)} 条已失效/待确认（明细见报告）：')
        for f in red[:15]:
            print(f'    {f.hit.file}:{f.hit.line}  {f.hit.token}  {f.detail[:90]}')
        if len(red) > 15:
            print(f'    ...（另 {len(red) - 15} 条）')
    else:
        print('✓ 无「已失效/待确认」条目')

    # 报告模式（无 --check）恒为 0：计划 §3.1 要求「一条命令列出」先能跑通、能贴进文档；
    # 门禁职责交给 --check，避免把「已有死地址待写回」这类正常状态变成 CI 红灯。
    failure = bool(red) or any(bad[k] for k in ('doc_sections', 'doc_constants',
                                                'deprecations', 'offsets', 'falsify'))
    return 1 if (args.check and failure) else 0


if __name__ == '__main__':
    sys.exit(main())

