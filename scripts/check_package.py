#!/usr/bin/env python3
"""Check local Markdown links/anchors and method-index/router consistency."""
from collections import Counter
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import unquote

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
errors = []
links = re.compile(r'\[[^\]]+\]\(([^)]+)\)')

def anchors(path):
    found, counts, in_code = set(), Counter(), False
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.lstrip().startswith(('```', '~~~')):
            in_code = not in_code
        if in_code:
            continue
        match = re.match(r'^#{1,6}\s+(.+?)\s*#*$', line)
        if not match:
            continue
        value = match.group(1).strip().lower()
        value = ''.join(c for c in value if c in '-_' or not unicodedata.category(c).startswith(('P', 'S')))
        value = re.sub(r'\s', '-', value)
        slug = value if counts[value] == 0 else f'{value}-{counts[value]}'
        counts[value] += 1
        found.add(slug)
    return found

if not (ROOT / 'SKILL.md').is_file():
    raise SystemExit(f'FAIL: no SKILL.md at {ROOT}')

for document in ROOT.rglob('*.md'):
    if any(part in {'node_modules', 'dist'} for part in document.relative_to(ROOT).parts):
        continue
    for number, line in enumerate(document.read_text(encoding='utf-8').splitlines(), 1):
        for raw in links.findall(line):
            raw = raw.strip().strip('<>')
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', raw):
                continue
            target, _, fragment = unquote(raw).partition('#')
            destination = (document.parent / target).resolve() if target else document
            prefix = f'{document.relative_to(ROOT)}:{number}'
            if not destination.exists():
                errors.append(f'{prefix}: missing {raw}')
            elif fragment and destination.suffix == '.md' and fragment not in anchors(destination):
                errors.append(f'{prefix}: missing heading {raw}')

index = (ROOT / '03-methods/index.md').read_text(encoding='utf-8')
route = (ROOT / '02-router/route-map.md').read_text(encoding='utf-8')
for method_id in range(1, 14):
    key = f'{method_id:02d}'
    index_rows = re.findall(rf'^\| {key} \|[^\n]+$', index, re.MULTILINE)
    route_rows = re.findall(rf'^\| {key} \|[^\n]+$', route, re.MULTILINE)
    if len(index_rows) != 1 or len(route_rows) != 1:
        errors.append(f'Method {key}: expected one index row and one route row')
        continue
    state = index_rows[0].split('|')[3].strip()
    candidates = list((ROOT / '03-methods').glob(f'{key}-*.md'))
    named_card = ROOT / '03-methods' / f'method-{key}.md'
    if named_card.is_file():
        candidates.append(named_card)
    if state not in ('已编写', '待实现'):
        errors.append(f'Method {key}: unknown state {state}')
    elif state == '已编写':
        if len(candidates) != 1:
            errors.append(f'Method {key}: expected one short card, found {len(candidates)}')
        elif candidates[0].name not in index_rows[0] or candidates[0].name not in route_rows[0]:
            errors.append(f'Method {key}: short card missing from index or router')
    elif candidates:
        errors.append(f'Method {key}: pending state conflicts with existing short card')

for message in errors:
    print(message)
if errors:
    raise SystemExit(f'FAIL: {len(errors)} issue(s)')
print('PASS: Markdown targets/headings and 13 method-index/router entries')
