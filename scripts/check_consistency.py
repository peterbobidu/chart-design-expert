#!/usr/bin/env python3
"""Check registered documentation contradictions; emit a full Markdown review inventory.

These checks cover known, scoped regressions, not general natural-language correctness.
The inventory flags claims for a maintainer to compare against their authority documents.
"""
import argparse
import json
from pathlib import Path
import re

IGNORE = {'.git', 'node_modules', 'dist', 'coverage', '__pycache__', '.vite'}
AUTHORITY = {
    'Tooltip': '03-references/chart-spec/components/tooltip.md',
    'HD legend': '03-references/chart-spec/common/legend.md',
    'HD layout': '03-references/chart-spec/common/layout.md',
    'HD parallel': '03-references/chart-spec/charts/parallel.md',
    'delivery': '03-references/prototype/hosted-project.md',
    'handoff': '03-references/prototype/handoff.md',
    'method state': '02-methods/index.md',
}
CLAIMS = re.compile(r'未定义|尚未覆盖|暂无|待实现|未提供|默认|必须|不强制|继承|版本|尚未验证|未发布')


def documents(root):
    return sorted(p for p in root.rglob('*.md')
                  if not any(part in IGNORE for part in p.relative_to(root).parts))


def check(root):
    errors = []
    for label, relative in AUTHORITY.items():
        if not (root / relative).is_file():
            errors.append(f'{relative}: missing authority for {label}')
    for path in documents(root):
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding='utf-8')
        active = relative in {'SKILL.md', 'README.md'} or relative.startswith(
            ('01-router/', '02-methods/', '03-references/'))
        in_gap = False
        in_code = False
        for number, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith(('```', '~~~')):
                in_code = not in_code
                continue
            if in_code:
                continue
            if re.match(r'^#{1,6}\s', line):
                in_gap = bool(re.search(r'尚未覆盖|当前缺口|尚未定义', line))
            prefix = f'{relative}:{number}'
            if active:
                # Whole-topic claims, not legitimate unknown subproperties such as font weight.
                if re.search(r'(?:Tooltip|Hover)\s*(?:视觉参数|样式)?\s*(?:等)?\s*(?:尚未覆盖|暂无定义|未定义)', line, re.I):
                    errors.append(f'{prefix}: obsolete whole-Tooltip gap; consult {AUTHORITY["Tooltip"]}')
                elif in_gap and re.search(r'Tooltip视觉参数(?:和|与|及|[、；;。]|$)', line, re.I):
                    errors.append(f'{prefix}: Tooltip visuals listed as uncovered; consult {AUTHORITY["Tooltip"]}')
                if re.search(r'Mini专项规范未接入', line):
                    errors.append(f'{prefix}: unscoped Mini gap; HD layout already includes partial guidance')
            if relative == '03-references/chart-spec/hd.md' and '平行坐标' in line and '暂无专项' in line:
                errors.append(f'{prefix}: obsolete HD parallel gap; consult {AUTHORITY["HD parallel"]}')
            if relative == '03-references/methods/05/detail.md' and re.search(
                    r'线宽、轴间距、目标标记及图形高亮等未定义', line):
                errors.append(f'{prefix}: unscoped parallel focus style gap; HD focus is now defined')
            # Active regression instructions may retain old inputs, but must not pin the next run to an obsolete version.
            if relative.startswith('05-tests/') and re.search(r'下一次运行使用[^。\n]*v\d+\.\d+\.\d+', line):
                errors.append(f'{prefix}: next regression run pinned to a historical version')
            # Detect the observed historical-result claim, not legitimate task inputs or quotations.
            if relative.startswith('05-tests/') and re.search(
                    r'(?:已由用户|用户已|用户在当前对话已)[^。！？\n]*当前对话[^。！？\n]*确认|用户在当前对话已确认', line):
                if not (line.lstrip().startswith(('>', '输入', '原文', '历史原文')) or
                        re.search(r'历史(?:记录|原文)|引用原文', line)):
                    errors.append(f'{prefix}: historical confirmation depends on current conversation')
        if relative.startswith('05-tests/') and re.search(r'^# Router Cases[^\n]*v\d+\.\d+\.\d+', text):
            errors.append(f'{relative}: active router suite title implies a frozen historical version')
        if relative == '05-tests/chart-spec-cases.md':
            for number, line in enumerate(text.splitlines(), 1):
                if '| CS-Vue-01 |' in line and '既有' not in line:
                    errors.append(f'{relative}:{number}: default Vue expectation omits existing-host path')
        if relative == '05-tests/echarts-capability-cases.md':
            for number, line in enumerate(text.splitlines(), 1):
                if '工程有外部补充实现' in line and 'README可访问交接说明' in line:
                    errors.append(f'{relative}:{number}: unqualified README requirement conflicts with hosted handoff')
    index = root / AUTHORITY['method state']
    if index.is_file():
        text = index.read_text(encoding='utf-8')
        summary = re.search(r'已编写\s*(\d+)\s*张[、，,]\s*待实现\s*(\d+)\s*张', text)
        if summary:
            written = len(re.findall(r'^\| \d{2} \|[^\n]*\| 已编写 \|', text, re.M))
            pending = len(re.findall(r'^\| \d{2} \|[^\n]*\| 待实现 \|', text, re.M))
            if tuple(map(int, summary.groups())) != (written, pending):
                errors.append(f'{AUTHORITY["method state"]}: method count summary disagrees with state rows')
    return errors


def inventory(root):
    result = []
    for path in documents(root):
        text = path.read_text(encoding='utf-8')
        relative = path.relative_to(root).as_posix()
        kind = ('history' if relative in {'CHANGELOG.md', 'VALIDATION.md'} else
                'template' if path.name == '_template.md' else
                'maintenance' if relative.startswith(('05-tests/', '.github/')) or relative in
                {'AGENTS.md', 'CONTRIBUTING.md', 'RELEASING.md'} else 'runtime')
        result.append({'path': relative, 'kind': kind, 'lines': len(text.splitlines()),
                       'review_claims': [{'line': n, 'text': line} for n, line in
                                         enumerate(text.splitlines(), 1) if CLAIMS.search(line)]})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', nargs='?', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--inventory', type=Path, help='Write review inventory outside the package source')
    args = parser.parse_args()
    root = args.root.resolve()
    if args.inventory:
        target = args.inventory.resolve()
        if target.is_relative_to(root):
            parser.error('review inventory must be outside the source tree')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({'authorities': AUTHORITY, 'documents': inventory(root)},
                                     ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    errors = check(root)
    for error in errors:
        print(error)
    print(('FAIL' if errors else 'PASS') + f': registered consistency rules; {len(documents(root))} Markdown files scanned; semantic review still required')
    raise SystemExit(bool(errors))
