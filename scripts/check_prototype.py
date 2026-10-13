#!/usr/bin/env python3
"""Check standalone Vite/Vue/ECharts prototypes only; hosted projects must use their designated pipeline gates."""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--run", action="store_true", help="Run npm test and npm run build")
    args = parser.parse_args()
    root = args.project.resolve()
    failures: list[str] = []

    if not root.is_dir():
        print(f"FAIL: project directory does not exist: {root}")
        return 1

    required = ("package.json", "index.html", "README.md", "HANDOFF.md")
    for name in required:
        if not (root / name).is_file():
            failures.append(f"missing {name}")
    lockfiles = ("package-lock.json", "pnpm-lock.yaml", "yarn.lock")
    available_locks = [name for name in lockfiles if (root / name).is_file()]
    if not available_locks:
        failures.append("missing dependency lockfile")

    source = root / "src"
    if not source.is_dir() or not list(source.rglob("*.vue")):
        failures.append("missing src Vue component")
    if not source.is_dir() or not list(source.rglob("*.ts")):
        failures.append("missing src TypeScript logic")

    package_path = root / "package.json"
    if package_path.is_file():
        try:
            package = json.loads(package_path.read_text(encoding="utf-8"))
            deps = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
            for name in ("vue", "echarts", "vite", "typescript"):
                if name not in deps:
                    failures.append(f"missing dependency {name}")
            scripts = package.get("scripts", {})
            for name in ("test", "build"):
                if name not in scripts:
                    failures.append(f"missing npm script {name}")
        except (json.JSONDecodeError, UnicodeError) as exc:
            failures.append(f"invalid package.json: {exc}")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("PASS: default Vue/ECharts project structure")

    if not args.run:
        print("UNVERIFIED: npm test/build and browser visual checks were not run")
        return 0

    manager = "pnpm" if "pnpm-lock.yaml" in available_locks else "yarn" if "yarn.lock" in available_locks else "npm"
    if not shutil.which(manager):
        print(f"UNVERIFIED: {manager} is unavailable")
        return 2
    if not (root / "node_modules").is_dir():
        print(f"UNVERIFIED: dependencies are not installed; install from {available_locks[0]}")
        return 2

    commands = ((manager, "test"), (manager, "run", "build"))
    for command in commands:
        print(f"RUN: {' '.join(command)}", flush=True)
        completed = subprocess.run(command, cwd=root, check=False)
        if completed.returncode:
            print(f"FAIL: {' '.join(command)} exited {completed.returncode}")
            return 1
        print(f"PASS: {' '.join(command)}")
    print("UNVERIFIED: browser visual checks and actual PNG export require separate evidence")
    return 0


if __name__ == "__main__":
    sys.exit(main())
