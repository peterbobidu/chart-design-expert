# 通过 PR 修改 skill

`main` 是已合入版本。所有后续修改，包括文档和用例，都从新分支提交 PR，再合入 `main`。初次导入是建立仓库所需的基线提交。

首次克隆后运行 `git config core.hooksPath .githooks`，启用仓库自带的本地推送检查；它会阻止此检出直接推送到 `main`。本机当前检出已启用。

```bash
git switch main
git pull --ff-only
git switch -c codex/short-description
# 修改文件后
python3 scripts/check_package.py
# 若修改了 06-assets/semiconductor-four-box-vue：在该目录运行 npm ci、npm test、npm run build
git add -A
git commit -m "说明本次变更"
git push -u origin HEAD
```

推送后在 GitHub 的 “Compare & pull request” 页面创建以 `main` 为目标的 PR；已安装 GitHub CLI 时也可运行 `gh pr create --base main`。检查 PR 的文件差异和 Actions 结果，通过后从 PR 页面合入。合入后拉取 `main`，再把该版本同步到本机安装目录；不要直接编辑安装副本并把它当成仓库已更新。

当前仓库是 GitHub Free 账号下的私有仓库。GitHub 对此返回“Upgrade to GitHub Pro or make this repository public”，因此目前无法启用平台分支保护或规则集；本地推送检查只约束启用它的检出，其他客户端仍需遵守 PR 约定。保持仓库私有。若将来具备相应功能，应为 `main` 启用必须经 PR、必须通过 `package` 与 `prototype` 检查、限制强推与删除，并把管理员纳入规则。
