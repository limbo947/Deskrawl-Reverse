# -*- coding: utf-8 -*-
"""dump.cs 方法与字段索引：补丁后重锚定的公共基座（任务①与②共用）。

为什么独立成模块：GUPS 混淆器**每次构建都重新生成方法名**（类名部分保留），跨补丁只能按
「签名 + Slot」或「类形状」匹配。RVA 体检（rva_audit.py）与语义别名表（build_aliases.py）
都要这套匹配能力，放两份实现必然漂移，故抽成单一来源。

历史旧构建的 dump.cs 未入库（dumper 直接覆盖同名文件），只能从 git 取：
    git show <ref>:data/schema/dump.cs
本模块用 `open_dump_from_git(ref)` 流式读取，避免把 28 MB 产物再写进仓库。
"""
import re
import subprocess

RVA_RE = re.compile(
    r'^\s*//\s*RVA:\s*0x([0-9A-Fa-f]+)\s+Offset:\s*0x[0-9A-Fa-f]+'
    r'\s+VA:\s*0x([0-9A-Fa-f]+)(?:\s+Slot:\s*(\d+))?')
NS_RE = re.compile(r'^//\s*Namespace:\s*(.*?)\s*$')
TYPE_RE = re.compile(
    r'^(?:[a-z]+\s+)*(?:class|struct|interface|enum)\s+(.+?)\s*(?::\s|\{|//|$)')
TDINDEX_RE = re.compile(r'//\s*TypeDefIndex:\s*(\d+)')
# 字段名可能是编译器生成的 `<lxj>k__BackingField`，故名字用「非空白非分号」而非标识符——
# 按标识符写会漏掉全部自动属性后备字段，而它们正是内存偏移表引用最多的那批。
FIELD_RE = re.compile(
    r'^\s*(?:\[[^\]]*\]\s*)*(?:[^\s;]+\s+)+([^\s;]+)\s*;\s*//\s*0x([0-9A-Fa-f]+)\s*$')
DECL_NAME_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\s*(?:<[^>(]*>)?\s*\(')


class Method:
    """一条 dump.cs 方法记录。sig 是抹掉混淆名后的归一化签名（跨构建可比）。"""

    __slots__ = ('rva', 'va', 'name', 'klass', 'ns', 'tdindex', 'slot', 'decl', '_sig')

    def __init__(self, rva, va, name, klass, ns, tdindex, slot, decl):
        self.rva, self.va, self.name, self.klass = rva, va, name, klass
        self.ns, self.tdindex, self.slot, self.decl = ns, tdindex, slot, decl
        self._sig = _normalize(decl, name)

    @property
    def full(self):
        return f'{self.ns}.{self.klass}::{self.name}' if self.ns else f'{self.klass}::{self.name}'

    @property
    def sig(self):
        """归一化签名：把方法名替换为 <m>，折叠空白与混淆名差异（构造时算一次）。"""
        return self._sig

    def to_dict(self):
        return {'rva': hex(self.rva), 'va': hex(self.va), 'name': self.name,
                'klass': self.klass, 'ns': self.ns, 'slot': self.slot, 'sig': self.sig}


def _normalize(decl, name):
    """把声明里的方法名替换为 `<m>` 得到归一化签名：混淆名每版都变，只有类型部分可比。"""
    head = decl.split('(', 1)[0]
    idx = head.rfind(name) if name else -1
    if idx < 0:
        return re.sub(r'\s+', ' ', decl)
    return re.sub(r'\s+', ' ', decl[:idx] + '<m>' + decl[idx + len(name):])


def parse(lines):
    """解析 dump.cs 行流。返回 (methods, fields_by_klass)。

    用「单独成行的花括号」维护类作用域栈——Il2CppDumper 的输出里花括号必单独成行，
    方法体一律内联（`{ }`），所以这个方法可靠且不必写完整 C# 解析器。
    """
    methods, fields = [], {}
    stack, pending = [], None
    ns, tdindex = '', None
    cur_sig_line = None  # 已读到 RVA 注释、等待方法声明

    for line in lines:
        stripped = line.strip()
        if cur_sig_line is not None:
            if not stripped or stripped.startswith('//') or stripped.startswith('['):
                continue
            m = DECL_NAME_RE.search(stripped)
            name = m.group(1) if m else '<unknown>'
            klass, kns, ktd = stack[-1] if stack else ('', ns, None)
            rva, va, slot = cur_sig_line
            meth = Method(rva, va, name, klass, kns, ktd, slot, stripped)
            methods.append(meth)
            cur_sig_line = None
            continue

        m = RVA_RE.match(line)
        if m:
            rva = int(m.group(1), 16)
            va = int(m.group(2), 16)
            if rva != 0xFFFFFFFFFFFFFFFF and rva > 0 and rva != 0xFFFFFFFF:
                cur_sig_line = (rva, va, int(m.group(3)) if m.group(3) else None)
            else:
                cur_sig_line = None  # RVA: -1（抽象/未实现）无地址，不作锚点
            continue

        if stripped == '{':
            stack.append(pending if pending else ('', ns, None))
            pending = None
            continue
        if stripped == '}':
            if stack:
                stack.pop()
            continue

        m = NS_RE.match(line)
        if m:
            ns = m.group(1)
            continue

        m = TYPE_RE.match(line)
        if m:
            tdm = TDINDEX_RE.search(line)
            tdindex = int(tdm.group(1)) if tdm else None
            pending = (m.group(1).strip(), ns, tdindex)
            fields.setdefault(m.group(1).strip(), {})
            continue

        m = FIELD_RE.match(line)
        if m and stack:
            fields.setdefault(stack[-1][0], {})[m.group(1)] = int(m.group(2), 16)

    return methods, fields


class DumpIndex:
    """某一构建的 dump.cs 索引。"""

    def __init__(self, methods, fields, label=''):
        self.methods = methods
        self.fields = fields
        self.label = label
        self.by_rva = {}
        for m in methods:
            self.by_rva.setdefault(m.rva, []).append(m)
        self.by_klass = {}
        for m in methods:
            self.by_klass.setdefault(m.klass, []).append(m)
        self._by_ks = {}
        for m in methods:
            self._by_ks.setdefault((m.klass, m.sig, m.slot), []).append(m)
        self._sorted = sorted(m.rva for m in methods)
        self.class_sigs = {}
        for m in methods:
            self.class_sigs.setdefault(m.klass, set()).add(m.sig)

    def containing(self, rva, span=0x4000):
        """返回包含该 RVA 的方法（内联数据/跳转表注释用），超出 span 视为不属于任何方法。

        为什么要 span 上限：注释里的「跳转表 @ xxx」指的是方法**内部**的内联数据，
        若不加限就会被归到几万字节前的无关方法上，重锚定结论会误导。
        """
        import bisect
        i = bisect.bisect_right(self._sorted, rva) - 1
        if i < 0:
            return None
        start = self._sorted[i]
        if rva - start > span:
            return None
        return self.by_rva[start][0]

    @classmethod
    def load(cls, path, label=None):
        with open(path, encoding='utf-8', errors='replace') as f:
            methods, fields = parse(f)
        return cls(methods, fields, label or str(path))

    @classmethod
    def load_from_git(cls, ref, rel='data/schema/dump.cs', label=None):
        """从 git 取历史构建的 dump.cs 流式解析（不落盘，避免仓库里躺 28 MB）。"""
        proc = subprocess.Popen(
            ['git', 'show', f'{ref}:{rel}'],
            stdout=subprocess.PIPE, cwd=_repo_root(),
            text=True, encoding='utf-8', errors='replace')
        try:
            methods, fields = parse(proc.stdout)
        finally:
            proc.stdout.close()
            proc.wait()
        return cls(methods, fields, label or f'{ref}:{rel}')

    def at(self, rva):
        """RVA 落在哪个方法内（方法起始 RVA 精确匹配，或落在其地址区间视为未命中）。"""
        return self.by_rva.get(rva, [])

    def find(self, klass, sig=None, slot=None, name=None):
        """按类 + 归一化签名（+ Slot）匹配；name 仅作兜底提示，不作判据。"""
        if sig is not None:
            cands = self.by_klass.get(klass, [])
            hits = [m for m in cands if m.sig == sig]
            if slot is not None:
                narrowed = [m for m in hits if m.slot == slot]
                hits = narrowed or hits
            if hits:
                return hits
        if name is not None:
            return [m for m in self.by_klass.get(klass, []) if m.name == name]
        return []

    def match_any(self, sig, slot=None):
        """跨类按归一化签名匹配（用于混淆类改名后找同类方法的候选）。"""
        hits = [m for m in self.methods if m.sig == sig]
        if slot is not None:
            narrowed = [h for h in hits if h.slot == slot]
            hits = narrowed or hits
        return hits

    def klass_shape(self, klass, limit=None):
        """类形状指纹：归一化签名的集合（忽略方法名与类名，跨构建可比）。"""
        sigs = sorted(self.class_sigs.get(klass, ()))
        return tuple(sigs[:limit] if limit else sigs)

    def find_klass_by_shape(self, klass=None, shape=None):
        """按类形状找当期同类（混淆类改名后的重锚定主力）。

        返回 (候选类名列表, 命中签名数)。类形状是**交集计数**而非全等——补丁会增删方法，
        要求全等就永远匹配不上；得分相同且并列的候选一律返回，由调用方判「不唯一」。
        """
        want = set(shape if shape is not None else self.class_sigs.get(klass, ()))
        if not want:
            return [], 0
        best, best_score = [], 0
        for k, sigs in self.class_sigs.items():
            score = len(want & sigs)
            if score > best_score:
                best, best_score = [k], score
            elif score == best_score and score > 0:
                best.append(k)
        return best, best_score


def _repo_root():
    import os
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


if __name__ == '__main__':
    import sys
    idx = DumpIndex.load(sys.argv[1]) if len(sys.argv) > 1 else DumpIndex.load(
        __import__('os').path.join(_repo_root(), 'data', 'schema', 'dump.cs'))
    print(f'{idx.label}: methods={len(idx.methods)} classes={len(idx.by_klass)} '
          f'fields_classes={len(idx.fields)}')
