#!/usr/bin/env python3
"""Check local Markdown links/anchors and method-index/router consistency."""
from collections import Counter
import json
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

directory_names = {
    'router': '01-router', 'methods': '02-methods', 'references': '03-references',
    'assets': '04-assets', 'tests': '05-tests'
}
numbered = {p.name for p in ROOT.iterdir() if p.is_dir() and re.match(r'^\d{2}-', p.name)}
required = set(directory_names.values()) - {'05-tests'}
if not required <= numbered or numbered - set(directory_names.values()):
    raise SystemExit(f'FAIL: numbered directory layout; missing={sorted(required - numbered)}, '
                     f'unexpected={sorted(numbered - set(directory_names.values()))}')

# Check plain-text paths as well as Markdown links, so commands/configuration cannot retain stale names.
path_names = re.compile(r'(?<![\w-])(\d{2}-(router|methods|references|assets|tests))(?![\w-])')
text_suffixes = {'.md', '.py', '.json', '.yml', '.yaml', '.html', '.ts', '.vue', '.css'}
for path in ROOT.rglob('*'):
    if not path.is_file() or path.suffix not in text_suffixes or any(
            part in {'node_modules', 'dist', '__pycache__', '.git', 'coverage', '.vite'}
            for part in path.relative_to(ROOT).parts):
        continue
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        for match in path_names.finditer(line):
            if match[1] != directory_names[match[2]]:
                errors.append(f'{path.relative_to(ROOT)}:{number}: stale directory reference {match[1]}')

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
            if not destination.is_relative_to(ROOT):
                errors.append(f'{prefix}: link escapes package: {raw}')
            elif not destination.exists():
                errors.append(f'{prefix}: missing {raw}')
            elif fragment and destination.suffix == '.md' and fragment not in anchors(destination):
                errors.append(f'{prefix}: missing heading {raw}')

skill = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
header = re.match(r'\A---\n(.*?)\n---\n', skill, re.DOTALL)
if not header or not re.search(r'^name: chart-design-advisor$', header[1], re.MULTILINE) or not re.search(r'^description: .+', header[1], re.MULTILINE):
    errors.append('SKILL.md: invalid or missing skill name/description frontmatter')
policy_file = ROOT / 'release.json'
if policy_file.is_file():
    policy = json.loads(policy_file.read_text(encoding='utf-8'))
    if f'版本：{policy["skill_version"]}。' not in skill:
        errors.append('SKILL.md: release policy version does not match entrypoint')

for package_path in ROOT.rglob('package.json'):
    if any(part in {'node_modules', 'dist'} for part in package_path.relative_to(ROOT).parts):
        continue
    package = json.loads(package_path.read_text(encoding='utf-8'))
    lock_path = package_path.with_name('package-lock.json')
    if lock_path.is_file():
        lock = json.loads(lock_path.read_text(encoding='utf-8'))['packages']['']
        for key in ('dependencies', 'devDependencies'):
            if lock.get(key, {}) != package.get(key, {}):
                errors.append(f'{package_path.relative_to(ROOT)}: lockfile {key} mismatch')
    for name, command in package.get('scripts', {}).items():
        for script in re.findall(r'(?:^|\s|&&)node\s+([\w./-]+\.(?:mjs|cjs|js))\b', command):
            if not (package_path.parent / script).is_file():
                errors.append(f'{package_path.relative_to(ROOT)}: script {name} points to missing {script}')

index = (ROOT / '02-methods/index.md').read_text(encoding='utf-8')
route = (ROOT / '01-router/route-map.md').read_text(encoding='utf-8')
for method_id in range(1, 14):
    key = f'{method_id:02d}'
    index_rows = re.findall(rf'^\| {key} \|[^\n]+$', index, re.MULTILINE)
    route_rows = re.findall(rf'^\| {key} \|[^\n]+$', route, re.MULTILINE)
    if len(index_rows) != 1 or len(route_rows) != 1:
        errors.append(f'Method {key}: expected one index row and one route row')
        continue
    state = index_rows[0].split('|')[3].strip()
    candidates = list((ROOT / '02-methods').glob(f'{key}-*.md'))
    named_card = ROOT / '02-methods' / f'method-{key}.md'
    if named_card.is_file():
        errors.append(f'Method {key}: short card filename must start with {key}-')
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
print('PASS: contained Markdown targets/headings, frontmatter, 13 routes and package script/lock references')
