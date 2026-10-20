"""Exercise release failures and exact-byte promotion, using temporary source/bundle copies."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('skill_release', ROOT / 'scripts/release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scratch = tempfile.TemporaryDirectory(prefix='release-tests-')
        cls.base = Path(cls.scratch.name)
        cls.policy = release.read_json(ROOT / 'release.json')
        cls.source_files = {p: (ROOT / p).read_bytes() for p in
                            cls.policy['runtime_files'] + cls.policy['maintenance_only_files']}
        cls.source = cls.base / 'baseline-source'
        release.write_tree(cls.source, cls.source_files)
        cls.bundle = cls.base / 'baseline-bundle'
        with contextlib.redirect_stdout(io.StringIO()):
            release.build(cls.source, cls.bundle)

    @classmethod
    def tearDownClass(cls):
        cls.scratch.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=self.base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def source_copy(self):
        destination = self.root / 'source'
        shutil.copytree(self.source, destination)
        return destination

    def bundle_copy(self):
        destination = self.root / 'bundle'
        shutil.copytree(self.bundle, destination)
        return destination

    def acceptance(self, bundle):
        template = release.read_json(bundle / 'acceptance-template.json')
        template.update(decision='ACCEPTED', reviewer='automated fixture only',
                        tested_at='2026-10-20', environment='temporary unit-test fixture')
        evidence = bundle / 'evidence/fixture-evidence.txt'
        evidence.parent.mkdir(exist_ok=True)
        evidence.write_text('Synthetic fixture; not evidence of internal Agent validation.\n')
        for case in template['cases']:
            case.update(status='PASS', evidence=[{'path': 'evidence/fixture-evidence.txt',
                                                 'sha256': release.sha(evidence.read_bytes())}])
        path = bundle / 'acceptance.json'
        path.write_bytes(release.json_bytes(template))
        return path

    def assert_build_fails(self, root, pattern):
        with self.assertRaisesRegex((ValueError, subprocess.CalledProcessError), pattern):
            release.build(root, self.root / 'out')

    def test_unclassified_new_file_is_rejected(self):
        root = self.source_copy()
        (root / '04-references/new-rule.md').write_text('New rule')
        self.assert_build_fails(root, 'unclassified=.*new-rule')

    def test_missing_classified_file_is_rejected(self):
        root = self.source_copy()
        (root / '04-references/data-semantics.md').unlink()
        self.assert_build_fails(root, 'missing=.*data-semantics')

    def test_symlink_source_is_rejected(self):
        root = self.source_copy()
        target = root / 'README.md'
        target.unlink()
        target.symlink_to(self.source / 'README.md')
        self.assert_build_fails(root, 'symlink')

    def test_maintenance_material_cannot_enter_runtime(self):
        policy = copy.deepcopy(self.policy)
        policy['maintenance_only_files'].remove('AGENTS.md')
        policy['runtime_files'].append('AGENTS.md')
        with self.assertRaisesRegex(ValueError, 'maintenance material'):
            release.validate_policy(policy)

    def test_required_runtime_file_cannot_be_excluded(self):
        policy = copy.deepcopy(self.policy)
        policy['runtime_files'].remove('SKILL.md')
        policy['maintenance_only_files'].append('SKILL.md')
        with self.assertRaisesRegex(ValueError, 'required runtime'):
            release.validate_policy(policy)

    def test_policy_cannot_silently_remove_acceptance_cases(self):
        policy = copy.deepcopy(self.policy)
        policy['acceptance_cases'].pop()
        with self.assertRaisesRegex(ValueError, 'all six acceptance cases'):
            release.validate_policy(policy)

    def test_link_to_maintenance_fails_in_runtime_package(self):
        root = self.source_copy()
        with (root / 'SKILL.md').open('a') as handle:
            handle.write('\n[maintenance](05-tests/README.md)\n')
        self.assert_build_fails(root, 'returned non-zero')

    def test_link_outside_package_is_rejected(self):
        root = self.source_copy()
        (root.parent / 'outside.md').write_text('Exists but is not in the package')
        with (root / 'README.md').open('a') as handle:
            handle.write('\n[outside](../outside.md)\n')
        self.assert_build_fails(root, 'returned non-zero')

    def test_missing_node_script_is_rejected(self):
        root = self.source_copy()
        path = root / '06-assets/semiconductor-four-box-vue/package.json'
        package = release.read_json(path)
        package['scripts']['verify:broken'] = 'node missing.mjs'
        path.write_bytes(release.json_bytes(package))
        self.assert_build_fails(root, 'returned non-zero')

    def test_changed_version_requires_policy_update(self):
        root = self.source_copy()
        path = root / 'SKILL.md'
        path.write_text(path.read_text().replace('版本：0.6.9。', '版本：0.6.10。'))
        self.assert_build_fails(root, 'returned non-zero')

    def test_build_is_deterministic(self):
        with contextlib.redirect_stdout(io.StringIO()):
            release.build(self.source, self.root / 'second')
        first = {f.name: f.read_bytes() for f in self.bundle.iterdir()}
        second = {f.name: f.read_bytes() for f in (self.root / 'second').iterdir()}
        self.assertEqual(first, second)

    def test_existing_bundle_is_not_overwritten(self):
        with self.assertRaisesRegex(ValueError, 'already exists'):
            release.build(self.source, self.bundle)

    def test_archive_tampering_is_rejected(self):
        bundle = self.bundle_copy()
        record = release.read_json(bundle / 'release-record.json')
        path = bundle / record['artifacts']['runtime']['filename']
        path.write_bytes(path.read_bytes() + b'tampered')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            release.verify(bundle)

    def test_runtime_drift_is_rejected_even_with_updated_zip_checksum(self):
        bundle = self.bundle_copy()
        record = release.read_json(bundle / 'release-record.json')
        artifact = record['artifacts']['runtime']
        path = bundle / artifact['filename']
        files = release.unpack_bytes(path, record['skill_name'])
        files['README.md'] += b'changed only in runtime'
        data = release.zip_bytes(files, record['skill_name'])
        path.write_bytes(data)
        artifact.update(sha256=release.sha(data), bytes=len(data))
        (bundle / 'release-record.json').write_bytes(release.json_bytes(record))
        sums = {}
        for line in (bundle / 'SHA256SUMS').read_text().splitlines():
            _, name = line.split('  ', 1)
            sums[name] = release.sha((bundle / name).read_bytes())
        (bundle / 'SHA256SUMS').write_text(''.join(f'{digest}  {name}\n' for name, digest in sums.items()))
        with self.assertRaisesRegex(ValueError, 'runtime/maintainer content drift'):
            release.verify(bundle)

    def test_pending_acceptance_cannot_be_promoted(self):
        with self.assertRaisesRegex(ValueError, 'not complete'):
            release.promote(self.bundle, self.bundle / 'acceptance-template.json', self.root / 'published')

    def test_acceptance_for_another_zip_is_rejected(self):
        bundle = self.bundle_copy()
        path = self.acceptance(bundle)
        acceptance = release.read_json(path)
        acceptance['runtime_sha256'] = '0' * 64
        path.write_bytes(release.json_bytes(acceptance))
        with self.assertRaisesRegex(ValueError, 'different ZIP'):
            release.promote(bundle, path, self.root / 'published')

    def test_incomplete_case_coverage_is_rejected(self):
        bundle = self.bundle_copy()
        path = self.acceptance(bundle)
        acceptance = release.read_json(path)
        acceptance['cases'].pop()
        path.write_bytes(release.json_bytes(acceptance))
        with self.assertRaisesRegex(ValueError, 'coverage mismatch'):
            release.promote(bundle, path, self.root / 'published')

    def test_changed_evidence_is_rejected(self):
        bundle = self.bundle_copy()
        path = self.acceptance(bundle)
        (bundle / 'evidence/fixture-evidence.txt').write_text('Changed after sign-off')
        with self.assertRaisesRegex(ValueError, 'evidence hash mismatch'):
            release.promote(bundle, path, self.root / 'published')

    def test_promotion_copies_the_exact_accepted_zip(self):
        bundle = self.bundle_copy()
        acceptance = self.acceptance(bundle)
        with contextlib.redirect_stdout(io.StringIO()):
            artifact = release.promote(bundle, acceptance, self.root / 'published')
        self.assertEqual((bundle / artifact['filename']).read_bytes(),
                         (self.root / 'published' / artifact['filename']).read_bytes())
        self.assertEqual((bundle / 'evidence/fixture-evidence.txt').read_bytes(),
                         (self.root / 'published/evidence/fixture-evidence.txt').read_bytes())


if __name__ == '__main__':
    unittest.main()
