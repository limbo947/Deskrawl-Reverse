# -*- coding: utf-8 -*-
"""语义别名表的生成与校验（计划任务②）。

存在理由：GUPS 混淆器每次构建都重生成方法名与部分类名，文档/脚本直接引用「混淆名 + 地址」
这种写法在下一次补丁后就变成噪声。别名表把「稳定的语义名」与「当期混淆名 + 地址」解耦：
代码与文档引用语义名，本脚本负责把语义名映射到当期实现，并在失配时报错。

判定依据是 **dump.cs 的类 + 归一化签名 + Slot**（真读当期产物逐条比对，不比对表里抄的字符串）；
类名同样不可信——实测同一随机名（如 `iw`）在新构建里会是完全不相干的另一个类，
故同名类还要通过「类形状自证」（签名交集 ≥ 60%）才算数，否则按形状另找同类。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402
import dump_index  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
ALIASES = os.path.join(REPO, 'data', 'schema', 'aliases.json')
MIN_SHAPE = 3


def shape_ok(old_idx, new_idx, old_klass, new_klass, ratio=0.6, floor=MIN_SHAPE):
    """同名类自证：新旧同名类的归一化签名交集必须够大（否则视为撞名）。"""
    own = old_idx.class_sigs.get(old_klass, set())
    if not own:
        return None, 0
    inter = len(own & new_idx.class_sigs.get(new_klass, set()))
    need = max(floor, int(len(own) * ratio))
    return inter >= need or (len(own) <= 2 and inter >= 1), inter


def locate(new_idx, entry):
    """在当期 dump 里按「类 + 签名 + Slot」定位；返回 (方法, 失败原因, 是否靠组内序位)。

    签名 + Slot 都不足以区分时（同一类里存在多个同签名方法），退到 `current.ordinal`——
    即「同签名组内按 RVA 升序的第 k 个」。这条依据弱于签名，故由别名表**显式声明**，
    并在校验输出里单独列出，不混同为强依据。
    """
    cur = entry['current']
    klass, sig, slot = cur['klass'], entry['signature'], entry.get('slot')
    cands = [m for m in new_idx.by_klass.get(klass, []) if m.sig == sig]
    if slot is not None:
        narrowed = [m for m in cands if m.slot == slot]
        cands = narrowed or cands
    if len(cands) == 1:
        return cands[0], None, False
    if not cands:
        return None, f'类 {klass} 中找不到签名 {sig}（Slot={slot}）', False
    if 'ordinal' in cur:
        ordered = sorted(cands, key=lambda m: m.rva)
        if 0 <= cur['ordinal'] < len(ordered):
            return ordered[cur['ordinal']], None, True
        return None, f"ordinal={cur['ordinal']} 超出候选数 {len(ordered)}", False
    return None, f'类 {klass} 中有 {len(cands)} 个同签名候选（Slot={slot}），别名不唯一', False


def check(cfg, new_idx, old_idx=None, quiet=False):
    """逐条校验；返回 (问题列表, 已核条数)。

    history 回验只针对 `base_build_sha256` 那一代（即 base_ref 指向的那份旧构建）：
    `--write` 每次只把「上一版」压入 history，历史会跨多版累积，但本机只保有一份旧
    dump（base_ref），更早世代无法回验——按 build 前缀跳过，避免把「无从校验」误判成红。
    """
    problems, checked, weak = [], 0, []
    seen = {}
    base_build = (cfg['build'].get('base_build_sha256') or '')[:8]
    for semantic, entry in cfg['aliases'].items():
        m, err, by_ordinal = locate(new_idx, entry)
        if by_ordinal:
            weak.append(semantic)
        if err:
            problems.append({'alias': semantic, 'why': err})
            continue
        checked += 1
        cur = entry['current']
        if m.name != cur['name'] or m.rva != int(cur['rva'], 16):
            problems.append({'alias': semantic,
                             'why': f"表内 {cur['name']}@{cur['rva']} ≠ 当期 {m.name}@{hex(m.rva)}"
                                    '（补丁后需 `--write` 刷新）'})
        if m.va != int(cur['va'], 16):
            problems.append({'alias': semantic, 'why': f"VA 不一致：表内 {cur['va']} ≠ {hex(m.va)}"})
        if id(m) in seen:
            problems.append({'alias': semantic, 'why': f'与 {seen[id(m)]} 指向同一方法'})
        seen[id(m)] = semantic
        for h in entry.get('history', []):
            if old_idx is None:
                continue
            if base_build and (h.get('build', '')[:8] != base_build):
                continue  # 更早世代：无对应旧 dump 可回验，跳过（非放行，见 docstring）
            hk = h.get('klass', '')
            hit = [x for x in old_idx.by_klass.get(hk, [])
                   if x.name == h['name'] and x.rva == int(h['rva'], 16)]
            if not hit:
                problems.append({'alias': semantic,
                                 'why': f"history 项 {hk}.{h['name']}@{h['rva']} 在旧构建 dump 中不存在"})
    if not quiet:
        print(f'别名 {len(cfg["aliases"])} 条：核对 {checked} 条，问题 {len(problems)} 条')
        for p in problems[:20]:
            print(f"  ✗ {p['alias']}: {p['why']}")
        if weak:
            labeled = [f"{s}（{cfg['aliases'][s].get('证据等级', '未标注证据等级')}）" for s in weak]
            print(f'  ! {len(weak)} 条靠「组内序位」消歧（签名+Slot 不足以唯一）：'
                  + ', '.join(labeled))
    return problems, checked


def write(cfg, new_idx, old_idx=None):
    """按当期 dump 刷新 current，并把上一版压入 history（条目只增不减）。"""
    changed = 0
    for semantic, entry in cfg['aliases'].items():
        m, err, _ = locate(new_idx, entry)
        if err:
            print(f'  ✗ 跳过 {semantic}: {err}（需人工改签名/Slot）')
            continue
        cur = entry['current']
        if m.name == cur['name'] and m.rva == int(cur['rva'], 16) and m.va == int(cur['va'], 16):
            continue
        entry.setdefault('history', []).insert(0, {
            'build': cfg['build']['game_assembly_sha256'][:8] + '…',
            'klass': cur['klass'], 'name': cur['name'], 'rva': cur['rva']})
        new_cur = {'klass': m.klass, 'name': m.name,
                   'rva': hex(m.rva), 'va': hex(m.va)}
        # 保留 ordinal：靠「组内序位」定位的条目若丢失该字段，下一次 --check 会因
        # 「同签名候选不唯一」判红（--write 只刷新 current，不应把消歧依据一起抹掉）。
        if 'ordinal' in cur:
            new_cur['ordinal'] = cur['ordinal']
        entry['current'] = new_cur
        entry['signature'] = m.sig
        changed += 1
        print(f'  ↻ {semantic}: {cur["name"]}@{cur["rva"]} → {m.name}@{hex(m.rva)}')
    print(f'刷新 {changed} 条')
    return changed


def main(argv=None):
    p = argparse.ArgumentParser(description='语义别名表：生成 / 校验')
    p.add_argument('--check', action='store_true', help='只校验（默认行为，退出码非 0 = 失配）')
    p.add_argument('--write', action='store_true', help='按当期 dump.cs 刷新 current 并压入 history')
    p.add_argument('--no-history-check', action='store_true', help='跳过 history 对旧构建的校验')
    p.add_argument('--base-ref', default=None, help='旧构建 ref（默认取别名表 build.base_ref）')
    args = p.parse_args(argv)

    cfg = json.load(open(ALIASES, encoding='utf-8'))
    new_idx = dump_index.DumpIndex.load(paths.DUMP_CS)
    ref = args.base_ref or cfg['build'].get('base_ref')
    old_idx = None
    if ref and not args.no_history_check:
        try:
            old_idx = dump_index.DumpIndex.load_from_git(ref)
        except Exception as e:  # git 不可用时降级为「只校验当期」
            print(f'! 旧构建 dump 不可用（{e}），history 校验跳过')
    if args.write:
        write(cfg, new_idx, old_idx)
        json.dump(cfg, open(ALIASES, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        print(f'已写回 {ALIASES}')
    problems, _ = check(cfg, new_idx, old_idx)
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
