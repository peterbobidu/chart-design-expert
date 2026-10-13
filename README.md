# chart-design-advisor v0.6.8

## 仓库维护

本仓库根目录就是可安装的 `chart-design-advisor` skill。`main` 保存已合入版本；修改时从 `main` 创建 `codex/` 分支，更新相关文档与验证记录，运行检查后提交 PR。PR 合入后再将仓库 `main` 同步到本机 `~/.codex/skills/chart-design-advisor`。操作步骤与当前 GitHub 权限限制见 [CONTRIBUTING.md](CONTRIBUTING.md)；Agent 约定见 [AGENTS.md](AGENTS.md)，自动检查见 [Validate skill](.github/workflows/validate.yml)。

本版在v0.6.7基础上增加既有工程与编译交付管道适配，保留设计规范、四箱体骨架和独立工程验证路径。运行入口是[SKILL.md](SKILL.md)，方法状态由[索引](03-methods/index.md)维护。

交互原型优先接入既有工程；无承载工程时默认生成Vue 3 + TypeScript + ECharts组件及Vite预览工程，遵从用户指定的其他技术栈。原型工程随附[HANDOFF.md交接说明](04-references/prototype/handoff.md)。ECharts无法实现、需要其他技术配合或尚无法确认的能力，按[告知规则](04-references/prototype/echarts-capabilities.md)说明原因、建议与交付影响。

维护者在已配置Python的维护机上执行 `python3 scripts/check_package.py`（生成原型时不需要，不为此安装Python或Command Line Tools）；验证范围见[VALIDATION.md](VALIDATION.md)，用例与历史分别见[测试索引](05-tests/README.md)、[CHANGELOG](CHANGELOG.md)。已编写方法、代码中有实现和真实运行通过是不同状态。

半导体规范以用户提供文档的整理版接入，待核对项和缺失依赖随包记录；其他原始规范资产、六领域内部组件API未随包提供；不虚构业务接入或负责人。历史HTML保留原字节，其框架和旧视觉参数不覆盖当前交付要求，外部CDN依赖不代表离线可运行。

本版支持既有Vue工程与统一编译交付管道；见[承载工程规则](04-references/prototype/hosted-project.md)。Vite与check_prototype.py仅为无承载工程时的独立默认路径。内网脚手架及管道脚本不随本包分发，未声明已完成内网运行验证。

接入chart-vue-creator时，同步其design目录中的本版引用文档，并更新其入口对交付规则的引用；将“验证与限制只写verify结果”调整为“编译以verify为据，其他验证与限制分别记录”。本包不修改外部creator的脚本或固定工程约定。
