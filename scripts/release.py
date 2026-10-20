#!/usr/bin/env python3
"""Build, verify and promote immutable skill ZIPs using an explicit file inventory."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
IGNORED_DIRS = {'.git', 'node_modules', 'dist', 'coverage', '__pycache__', '.vite'}
ACCEPTANCE_IDS = {'HD-PLAN', 'ANOMALY', 'COMPACT', 'SEMI-BOX', 'HOSTED', 'HTML'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def safe_path(value):
    require(isinstance(value, str) and value and '\\' not in value, f'unsafe path: {value!r}')
    path = PurePosixPath(value)
    require(not path.is_absolute() and '..' not in path.parts and str(path) == value,
            f'unsafe path: {value}')
    return value


def inventory(root):
    found = set()
    for path in root.rglob('*'):
        relative = path.relative_to(root)
        if any(part in IGNORED_DIRS for part in relative.parts):
            continue
        if path.name == '.DS_Store' or path.suffix in {'.pyc', '.pyo', '.tsbuildinfo'}:
            continue
        require(not path.is_symlink(), f'symlink is not a distributable source file: {relative}')
        if path.is_file():
            found.add(relative.as_posix())
    return found


def validate_policy(policy):
    require(policy['schema_version'] == 1, 'unsupported release policy schema')
    require(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', policy['skill_name']), 'invalid skill name')
    require(re.fullmatch(r'\d+\.\d+\.\d+', policy['skill_version']), 'invalid skill version')
    require(re.fullmatch(r'r[1-9]\d*', policy['distribution_revision']), 'invalid distribution revision')
    runtime, maintenance = policy['runtime_files'], policy['maintenance_only_files']
    for paths in (runtime, maintenance):
        require(isinstance(paths, list) and len(paths) == len(set(paths)), 'duplicate inventory entry')
        for path in paths:
            safe_path(path)
    require(not set(runtime) & set(maintenance), 'runtime/maintenance inventories overlap')
    require(set(policy['required_runtime_files']) <= set(runtime), 'required runtime file excluded')
    require('release.json' in maintenance and 'scripts/check_package.py' in maintenance,
            'maintenance package must include release policy and package checker')
    require(not any(p.startswith(('05-tests/', '.github/', '.githooks/')) or
                    p in {'AGENTS.md', 'CONTRIBUTING.md', 'CHANGELOG.md', 'VALIDATION.md', 'release.json'}
                    for p in runtime), 'maintenance material in runtime inventory')
    cases = policy['acceptance_cases']
    require(cases and len({c['id'] for c in cases}) == len(cases), 'invalid acceptance cases')
    require({c['id'] for c in cases} == ACCEPTANCE_IDS, 'schema 1 requires all six acceptance cases')


def validate_tree(root):
    checker = root / 'scripts/check_package.py'
    subprocess.run([sys.executable, str(checker), str(root)], check=True)
    prototype = root / '06-assets/semiconductor-four-box-vue'
    subprocess.run([sys.executable, str(root / 'scripts/check_prototype.py'), str(prototype)], check=True)


def zip_bytes(files, name):
    import io
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path, content in sorted(files.items()):
            info = zipfile.ZipInfo(f'{name}/{path}', date_time=(2020, 1, 1, 0, 0, 0))
            info.create_system = 3
            mode = 0o100755 if path == '.githooks/pre-push' else 0o100644
            info.external_attr = (mode << 16)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content, compresslevel=9)
    return output.getvalue()


def unpack_bytes(path, name):
    files = {}
    with zipfile.ZipFile(path) as archive:
        require(archive.testzip() is None, f'corrupt ZIP: {path.name}')
        for info in archive.infolist():
            require(not info.is_dir(), 'unexpected directory ZIP entry')
            full = safe_path(info.filename)
            require(full.startswith(name + '/'), 'incorrect skill root in ZIP')
            relative = full[len(name) + 1:]
            safe_path(relative)
            require(relative not in files, f'duplicate ZIP entry: {relative}')
            require((info.external_attr >> 16) & 0o170000 != 0o120000, 'symlink ZIP entry')
            files[relative] = archive.read(info)
    return files


def write_tree(root, files):
    for name, content in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def build(root, output):
    policy = read_json(root / 'release.json')
    validate_policy(policy)
    paths = set(policy['runtime_files'] + policy['maintenance_only_files'])
    actual = inventory(root)
    require(paths == actual,
            f'inventory mismatch; unclassified={sorted(actual - paths)}; missing={sorted(paths - actual)}')
    require(not output.exists(), 'output already exists; use a new directory and never overwrite tested ZIPs')
    require(not output.is_relative_to(root), 'release output must be outside the source tree')
    files = {path: (root / path).read_bytes() for path in sorted(paths)}
    with tempfile.TemporaryDirectory(prefix='skill-release-check-') as temp:
        stage = Path(temp)
        write_tree(stage / 'source', files)
        validate_tree(stage / 'source')
        runtime = {p: files[p] for p in policy['runtime_files']}
        write_tree(stage / 'runtime', runtime)
        # The checker stays outside the runtime package, but validates its extracted files.
        subprocess.run([sys.executable, str(stage / 'source/scripts/check_package.py'),
                        str(stage / 'runtime')], check=True)
    name = policy['skill_name']
    prefix = f"{name}-v{policy['skill_version']}-{policy['distribution_revision']}"
    record = {
        'schema_version': 1, 'skill_name': name, 'skill_version': policy['skill_version'],
        'distribution_revision': policy['distribution_revision'],
        'source_inventory_sha256': sha(json_bytes({p: sha(b) for p, b in files.items()})),
        'files': {p: {'sha256': sha(b), 'bytes': len(b)} for p, b in files.items()},
        'artifacts': {}, 'validation_scope': 'static checks only; internal Agent acceptance required'
    }
    artifacts = {}
    for kind, selected in [('maintainer', files), ('runtime', runtime)]:
        filename = f'{prefix}-{kind}.zip'
        data = zip_bytes(selected, name)
        artifacts[filename] = data
        record['artifacts'][kind] = {'filename': filename, 'sha256': sha(data),
                                     'file_count': len(selected), 'bytes': len(data)}
    artifacts['release-record.json'] = json_bytes(record)
    acceptance = {
        'schema_version': 1, 'runtime_sha256': record['artifacts']['runtime']['sha256'],
        'decision': 'UNVERIFIED', 'reviewer': '', 'tested_at': '',
        'environment': '', 'cases': [dict(c, status='UNVERIFIED', evidence=[]) for c in policy['acceptance_cases']]
    }
    artifacts['acceptance-template.json'] = json_bytes(acceptance)
    artifacts['SHA256SUMS'] = ''.join(f'{sha(data)}  {p}\n' for p, data in sorted(artifacts.items())).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.skill-release-', dir=output.parent) as temp:
        stage = Path(temp) / 'bundle'
        stage.mkdir()
        write_tree(stage, artifacts)
        verify(stage)
        stage.rename(output)
    return record


def verify(bundle):
    record = read_json(bundle / 'release-record.json')
    require(record['schema_version'] == 1, 'unsupported record schema')
    name = record['skill_name']
    require(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name), 'invalid record skill name')
    expected_artifacts = {'release-record.json', 'acceptance-template.json'}
    for kind in ('maintainer', 'runtime'):
        filename = safe_path(record['artifacts'][kind]['filename'])
        require('/' not in filename, 'ZIP must be directly inside bundle')
        expected_artifacts.add(filename)
    checksum_entries = {}
    for line in (bundle / 'SHA256SUMS').read_text().splitlines():
        digest, path = line.split('  ', 1)
        require(path not in checksum_entries, 'duplicate checksum path')
        checksum_entries[safe_path(path)] = digest
    require(set(checksum_entries) == expected_artifacts, 'incomplete checksum list')
    for path, digest in checksum_entries.items():
        require(sha((bundle / path).read_bytes()) == digest, f'bundle checksum mismatch: {path}')
    archives = {}
    for kind in ('maintainer', 'runtime'):
        artifact = record['artifacts'][kind]
        path = bundle / artifact['filename']
        require(sha(path.read_bytes()) == artifact['sha256'], f'ZIP hash mismatch: {kind}')
        require(path.stat().st_size == artifact['bytes'], f'ZIP size mismatch: {kind}')
        archives[kind] = unpack_bytes(path, name)
        require(len(archives[kind]) == artifact['file_count'], f'file count mismatch: {kind}')
    source = archives['maintainer']
    policy = json.loads(source['release.json'])
    validate_policy(policy)
    require((name, record['skill_version'], record['distribution_revision']) ==
            (policy['skill_name'], policy['skill_version'], policy['distribution_revision']), 'record/policy identity mismatch')
    require(set(source) == set(policy['runtime_files'] + policy['maintenance_only_files']), 'source ZIP inventory mismatch')
    require(set(archives['runtime']) == set(policy['runtime_files']), 'runtime ZIP inventory mismatch')
    require(set(record['files']) == set(source), 'per-file record inventory mismatch')
    for path, data in source.items():
        require(record['files'][path] == {'bytes': len(data), 'sha256': sha(data)}, f'file hash mismatch: {path}')
    for path, data in archives['runtime'].items():
        require(data == source[path], f'runtime/maintainer content drift: {path}')
    require(sha(json_bytes({p: sha(b) for p, b in source.items()})) == record['source_inventory_sha256'], 'source digest mismatch')
    with tempfile.TemporaryDirectory(prefix='skill-verify-') as temp:
        stage = Path(temp)
        write_tree(stage / 'maintainer', source)
        write_tree(stage / 'runtime', archives['runtime'])
        validate_tree(stage / 'maintainer')
        subprocess.run([sys.executable, str(stage / 'maintainer/scripts/check_package.py'),
                        str(stage / 'runtime')], check=True)
    return record, policy


def promote(bundle, acceptance_path, output):
    record, policy = verify(bundle)
    acceptance_bytes = acceptance_path.read_bytes()
    acceptance = json.loads(acceptance_bytes)
    artifact = record['artifacts']['runtime']
    require(acceptance.get('schema_version') == 1, 'unsupported acceptance schema')
    require(acceptance.get('runtime_sha256') == artifact['sha256'], 'acceptance belongs to a different ZIP')
    require(acceptance.get('decision') == 'ACCEPTED', 'internal Agent acceptance is not complete')
    require(all(isinstance(acceptance.get(k), str) and acceptance[k].strip()
                for k in ('reviewer', 'tested_at', 'environment')), 'reviewer/date/environment required')
    cases = acceptance['cases']
    require(len(cases) == len(policy['acceptance_cases']) and
            {c['id'] for c in cases} == {c['id'] for c in policy['acceptance_cases']}, 'acceptance case coverage mismatch')
    evidence_files = {}
    for case in cases:
        require(case['status'] == 'PASS' and case['evidence'], f'case not passed with evidence: {case["id"]}')
        for evidence in case['evidence']:
            relative = safe_path(evidence['path'])
            require(relative.startswith('evidence/'), 'evidence files must be inside evidence/')
            path = acceptance_path.parent / relative
            require(path.is_file() and path.stat().st_size > 0, f'missing evidence: {relative}')
            data = path.read_bytes()
            require(sha(data) == evidence['sha256'], f'evidence hash mismatch: {relative}')
            evidence_files[relative] = data
    require(not output.exists() and not output.is_relative_to(bundle), 'use a new promotion directory outside bundle')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.skill-promote-', dir=output.parent) as temp:
        stage = Path(temp) / 'published'
        stage.mkdir()
        data = (bundle / artifact['filename']).read_bytes()
        require(sha(data) == artifact['sha256'], 'ZIP changed during promotion')
        promoted = {artifact['filename']: data, 'acceptance.json': acceptance_bytes, **evidence_files}
        write_tree(stage, promoted)
        (stage / 'SHA256SUMS').write_text(''.join(f'{sha(content)}  {name}\n'
                                               for name, content in sorted(promoted.items())))
        stage.rename(output)
    return artifact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    builder = sub.add_parser('build')
    builder.add_argument('--source', type=Path, default=ROOT)
    builder.add_argument('--out', type=Path, required=True)
    verifier = sub.add_parser('verify')
    verifier.add_argument('--bundle', type=Path, required=True)
    promoter = sub.add_parser('promote')
    promoter.add_argument('--bundle', type=Path, required=True)
    promoter.add_argument('--acceptance', type=Path, required=True)
    promoter.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'build':
            record = build(args.source.resolve(), args.out.resolve())
            print('PASS: immutable candidate bundle built; internal Agent acceptance UNVERIFIED')
            print(json.dumps(record['artifacts'], ensure_ascii=False, indent=2))
        elif args.command == 'verify':
            record, _ = verify(args.bundle.resolve())
            print(f"PASS: bundle checksums, inventories, shared runtime bytes and static checks ({record['skill_version']})")
        else:
            artifact = promote(args.bundle.resolve(), args.acceptance.resolve(), args.out.resolve())
            print(f"PASS: copied accepted ZIP unchanged; SHA256 {artifact['sha256']}")
    except (ValueError, KeyError, TypeError, OSError, zipfile.BadZipFile, subprocess.CalledProcessError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
