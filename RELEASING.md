# 双包发布标准

## 目录编号

两包共享 `01-router`、`02-methods`、`03-references`、`04-assets`，维护包再加 `05-tests`，因此各自的一级资料目录都从01连续排列。方法卡按两位业务编号开头命名，例如异常发现为 `02-methods/02-anomaly-discovery.md`；目录序号不改动Method 01–13的含义。脚本、入口和其他根文件沿用其用途名称。

更名时先修改维护源码，再同步所有链接、纯文本路径、工程/CI命令和分发清单，最后构建双包。包检查会拒绝过期编号的目录及文字引用；不允许在打包时为两包分别重命名。

## 两种包，一份运行源码

维护完整包用于修改、回归和排查，包含完整源码及维护工具。运行安装包用于内部 Agent 测试和最终上架。两者均以 `chart-design-advisor/` 为根目录，不是两套独立 Skill；日常环境安装 runtime 包，维护包作为源码资料使用。

`release.json` 是分发清单。每个源码文件必须且只能归入 `runtime_files` 或 `maintenance_only_files`；新增、删除、重命名文件后须更新清单。未分类文件使构建失败。`.git`、依赖/构建/缓存目录及明确的系统缓存文件不参与分发，ZIP 等其他文件不会被静默忽略。

运行规则、案例、规范、必要资产、原型检查脚本和运行验收留在 runtime。PR/CI 配置、维护用例、历史记录和发布工具仅在维护包。保留规范整理功能、旧编号兼容和历史 HTML 参考；本次不改变这些功能范围。`description.md` 保留以兼容未确认的宿主导入规则。

打包只选文件，不做正文替换、裁剪或模板渲染。修改运行文案应先修改源码并验证。共有运行文件必须逐字节相同；运行包内链接不能指向维护资料。评价规则的唯一正文在 `03-references/prototype/evaluation-status.md`，测试目录仅保留兼容入口。

## 版本与产物

`skill_version` 与 SKILL.md 一致。`distribution_revision` 表示同一 Skill 版本下的分发修订，例如 `0.6.9-r2`；文件名明确标识 revision，不覆盖此前的 0.6.9 ZIP。每次变更候选内容都提高 revision；方法/设计行为变更按项目版本策略提高 Skill 版本。

构建目录含两个 ZIP、`release-record.json`、`SHA256SUMS` 和 `acceptance-template.json`。记录包括所有源码文件的 SHA-256、大小、两个 ZIP 的 SHA-256 和文件数。ZIP 条目顺序、权限及时间固定，相同内容输入重复构建得到相同字节。输出目录必须在源码外且尚不存在，避免覆盖测试产物。

## 检查与生成候选

在维护端已有 Python 环境执行，设计师不用安装这些工具：

```bash
python3 scripts/check_package.py
python3 -m unittest discover -s 05-tests -p 'test_release.py'
python3 scripts/release.py build --out ../candidate-0.6.9-r2
python3 scripts/release.py verify --bundle ../candidate-0.6.9-r2
```

构建会检查源码、运行包的链接/锚点/路由、入口版本、锁文件顶层依赖和 Node 脚本文件引用；核对四箱体结构。`verify` 还检查 ZIP CRC、文件清单、逐文件哈希、两包共有运行内容及完整产物校验值。解包检查在临时目录进行，维护检查工具不进入 runtime。

这些静态检查不替代原型构建、视觉和内部 Agent 行为测试。修改四箱体骨架后仍运行 `npm ci`、`npm test` 和 `npm run build`。CI 执行检查并上传候选产物，CI 通过不自动等于可上架。

## 测试待上架 ZIP

直接在内部测试环境安装 runtime ZIP，记录其 SHA-256，再按清单的六类用例验收：HD 设计咨询、异常对象发现、有限空间小卡、半导体四箱体、既有工程交付、显式单文件 HTML。具体输入与可观察结果在 `05-tests/release-acceptance.md`。

将 `acceptance-template.json` 复制为 `acceptance.json`，保留绑定的 `runtime_sha256`。实际验收后填写 reviewer、tested_at、environment 和各案例状态。每项 evidence 为相对 acceptance 文件所在目录的证据路径与文件 SHA-256，例如：

```json
{"path": "evidence/HD-PLAN.md", "sha256": "填写该文件的真实SHA-256"}
```

证据文件放在 acceptance 所在目录的 `evidence/` 内，应包含输入、宿主/模型、输出或工程入口、实际观察及未验证项；原型用例需构建、目标尺寸、交互证据，要求导出时另有实际文件证据。可用已有运行日志和截图，不复制内部凭据或业务秘密。不得以包检查输出替代这些观察，也不得把维护端的自动化测试夹具当作真实验收。

只有全部六例实际 PASS 才将 decision 写为 ACCEPTED。未执行保持 UNVERIFIED；有 FAIL、PARTIAL 或不可核查项时修复、重建并重测，不手改已测试的 ZIP。修改清单或验收范围也要经过 PR 审阅，不能为跳过失败项临时缩减标准。

## 原包晋级

```bash
python3 scripts/release.py promote --bundle ../candidate-0.6.9-r2 --acceptance ../candidate-0.6.9-r2/acceptance.json --out ../publish-0.6.9-r2
```

晋级重新检查候选，要求验收绑定同一个 ZIP、六例覆盖且全部 PASS、审核人/时间/环境完整、证据存在且哈希匹配；随后原字节复制 runtime ZIP，不解包重打。发布目录附验收记录、对应证据文件及校验值。使用该 ZIP 通过内部平台上架；本脚本不会上传或修改线上 Skill。

这些检查能发现缺件、断链、内容漂移、证据文件变更和误用旧包，不能判断人工填写的测试结论是否真实，也不是身份签名系统。验收人员对实际观察负责；正式上架按平台流程完成。

## 维护约定

规则、分发清单、验收范围及发布脚本都通过 `codex/` 分支与 PR 修改。源码仓库保留完整测试与历史，不直接编辑安装副本。当前 revision 的验证范围见 VALIDATION.md；内部验收未完成前只交付候选包，不标记正式发布。
