# Repository workflow

This repository is the source of truth for the `chart-design-advisor` skill.

- Make every change on a `codex/` feature branch. Do not commit or push changes directly to `main`.
- Open a pull request into `main` for every change, including documentation and version updates. Merge only after the package check and prototype checks pass and the change has been reviewed.
- Keep `SKILL.md`, linked references, `README.md`, `CHANGELOG.md`, and `VALIDATION.md` consistent when changing behavior. Record what was actually verified; do not present historical tests as current results.
- Run `python3 scripts/check_package.py` before opening a PR. For changes to `06-assets/semiconductor-four-box-vue`, run `npm ci`, `npm test`, and `npm run build` from that directory.
- Keep generated dependencies, build output, archives, secrets, and unrelated workspace projects out of this repository.
- After a PR merges, update the local installed copy at `~/.codex/skills/chart-design-advisor` from `main` as a separate deployment step.
