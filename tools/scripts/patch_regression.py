# -*- coding: utf-8 -*-
"""补丁回归串行入口：把清单里的 ①–④ 步跑一遍并出一份报告（计划任务④）。

为什么是「串行调用」而不是把逻辑并进来：每步的判定逻辑已经躺在各自脚本里（体检、别名、自检），
再实现一遍必然漂移；本脚本只负责**顺序、环境、证据留档与结论汇总**，
并在任一必需步骤失败时给出「下一步做什么」，而不是假装成功。

用法：
    python patch_regression.py                 # 静态四步（指纹/体检/别名/自检）
    python patch_regression.py --live          # 追加实机验证（游戏需运行中）
    python patch_regression.py --docs          # 体检额外覆盖 docs/**/*.md（产出文档工单）
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
TOOLS = os.path.join(REPO, 'tools')
GUI_PY = os.path.join(REPO, '.venv-gui', 'Scripts', 'python.exe')
REPORT = os.path.join(REPO, 'docs', 'reports', '补丁回归报告.md')
FP_CODE = ('import json,rva_audit as R;'
           'print(json.dumps(R.rva_verify.verify_fingerprints('
           'json.load(open(R.CONFIG,encoding="utf-8"))),ensure_ascii=False))')


def run(name, argv, cwd=HERE, required=True, timeout=1800):
    """跑一步，返回结果字典。输出只留尾部若干行——报告要的是判据不是刷屏。"""
    t0 = time.time()
    try:
        p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=timeout)
        code, out = p.returncode, (p.stdout or '') + (p.stderr or '')
    except FileNotFoundError as e:
        code, out = 127, f'解释器/命令不存在：{e}'
    except subprocess.TimeoutExpired:
        code, out = 124, f'超时（>{timeout}s）'
    tail = '\n'.join(out.strip().splitlines()[-12:])
    return {'name': name, 'argv': ' '.join(argv), 'code': code, 'sec': round(time.time() - t0, 1),
            'ok': code == 0, 'required': required, 'tail': tail}


def main(argv=None):
    ap = argparse.ArgumentParser(description='补丁回归：指纹 → 体检 → 别名 → 自检（→ 实机）')
    ap.add_argument('--live', action='store_true', help='追加实机验证（memdump，需游戏运行中）')
    ap.add_argument('--docs', action='store_true', help='体检额外扫描 docs/**/*.md')
    ap.add_argument('--report', default=REPORT)
    args = ap.parse_args(argv)

    steps = []

    # ① 指纹：判断补丁是否发生。失配**不是失败**，而是「该走回归流程了」的信号，故 required=False；
    # 但「读不出指纹」必须是失败——否则解析失败会被当成「未检测到补丁」，把最该报警的情况静音。
    fp_raw = run('① 指纹核对（memory_offsets vs 磁盘）', [sys.executable, '-c', FP_CODE])
    try:
        fps = json.loads(fp_raw['tail'].strip().splitlines()[-1])
    except Exception:
        fps = []
    patched = any(not f.get('ok') for f in fps)
    fp_raw['ok'] = bool(fps) and not patched
    fp_raw['required'] = not fps
    steps.append(fp_raw)

    # ② RVA 体检（代码侧必跑；文档侧可选）
    audit = [sys.executable, 'rva_audit.py', '--check', '--falsify']
    if args.docs:
        audit += ['--docs', '--report', os.path.join(REPO, 'docs', 'reports', 'RVA体检报告-文档.md')]
    steps.append(run('② RVA 体检（--check --falsify）', audit))

    # ③ 语义别名表校验
    steps.append(run('③ 语义别名表（build_aliases --check）', [sys.executable, 'build_aliases.py', '--check']))

    # ④ 自检：内核 + GUI（GUI 用独立 venv 解释器）
    steps.append(run('④a 内核自检', [sys.executable, '-m', 'deskrawl_calc.cli', 'selftest'], cwd=TOOLS))
    if os.path.exists(GUI_PY):
        steps.append(run('④b GUI 自检', [GUI_PY, '-m', 'deskrawl_gui', '--selftest'], cwd=TOOLS))
    else:
        steps.append({'name': '④b GUI 自检', 'argv': GUI_PY, 'code': 127, 'sec': 0, 'ok': False,
                      'required': False, 'tail': f'未找到 venv 解释器：{GUI_PY}（跳过）'})

    # ⑤ 实机（可选）
    if args.live:
        steps.append(run('⑤ 实机导入（memdump）', [GUI_PY, '-m', 'deskrawl_gui.memdump'], cwd=TOOLS))

    failed = [s for s in steps if s['required'] and not s['ok']]
    verdict = ('✅ 指纹一致（未检测到补丁）' if fps and not patched else
               '⚠️ 指纹失配 → 说明发生了补丁，需按清单走完 1–5 步' if patched else
               '❌ 指纹无法读取（解析失败）——先修好这一步，别把「读不出来」当「没补丁」')
    lines = ['# 补丁回归报告（由 `tools/scripts/patch_regression.py` 生成）', '',
             f'- 运行时间：{time.strftime("%Y-%m-%d %H:%M:%S")}',
             f'- 模式：{"实机" if args.live else "静态"}{" + 文档扫描" if args.docs else ""}',
             f'- **补丁判定**：{verdict}',
             '', '## 步骤结果', '', '| 步骤 | 命令 | 退出码 | 耗时(s) | 结论 |', '|---|---|---|---|---|']
    for s in steps:
        lines.append(f"| {s['name']} | `{s['argv']}` | {s['code']} | {s['sec']} "
                     f"| {'✅' if s['ok'] else ('⚠️ 跳过' if not s['required'] else '❌')} |")
    lines += ['', '## 指纹明细', '', '| 键 | 声明 | 实测 | 一致 |', '|---|---|---|---|']
    for f in fps:
        lines.append(f"| `{f['key']}` | `{str(f['declared'])[:20]}…` | `{f['actual'][:20]}…` "
                     f"| {'✅' if f['ok'] else '❌'} |")
    lines += ['', '## 各步尾部输出', '']
    for s in steps:
        lines += [f"### {s['name']}", '', '```', s['tail'], '```', '']
    lines += ['## 结论与下一步', '']
    if failed:
        lines.append('❌ 必需步骤失败：' + ', '.join(s['name'] for s in failed))
        lines.append('')
        lines.append('排查顺序：① 若指纹失配 → 先做清单第 1 步（重导 `data/schema/`）；'
                     '② 再 `rva_audit.py --check` 看死地址清单并逐条写回；'
                     '③ 别名表签名的变化需人工改 `signature`/`slot`。')
    else:
        lines.append('✅ 必需步骤全部通过。' + ('若补丁判定为「发生了补丁」，还需完成清单第 5 步（文档与别名刷新）并做实机验证。'
                                          if patched else ''))
    with open(args.report, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')

    for s in steps:
        print(f"[{'ok' if s['ok'] else 'FAIL'}] {s['name']}（{s['code']}，{s['sec']}s）")
    print(f'补丁判定：{"指纹失配（发生了补丁）" if patched else "指纹一致"}')
    print(f'报告：{args.report}')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
