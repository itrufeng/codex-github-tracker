---
name: feature-create
description: 创建并实现新 Feature，创建 Issue 并同步 GitHub Project Status。
metadata:
  short-description: 创建并实现新功能，创建 Issue 并同步 GitHub Project Status
---

# 创建 Feature

默认静默执行，不要输出执行过程、工具调用、推理或额外说明。成功结束时只在文本代码块中原样显示脚本返回的 `table` 字符表格，其中包含 Issue title、Project Status 和 Issue URL；不要添加 review、commit、merge 或其他后续操作提醒。

专业术语保留英文，不翻译 `Feature`、`Skill`、`Issue`、`Project`、`Project item`、`Status`、`Goal`、`Branch`、`commit`、`push`、`merge` 和 `review`。Status 流只使用 `Ready`、`In progress`、`In review`、`Done`，这些值必须保持原样。

Feature 请求仅指显式调用 `$feature-create` 之后的用户文字。不要把 `$feature-create` 本身写入请求或 Issue body。将其余文字原样保存到临时 UTF-8 文件，不要用摘要替代。脚本也会确定性地移除开头的一个 `$feature-create` 标记，作为安全保障。

本 Skill 不管理 Codex Goal。是否使用 `/goal` 以及 Goal 的创建、检查、暂停、恢复和完成，全部由用户和外层 `/goal` 工作流决定。

1. 生成清晰且非空的 Issue title 摘要，让用户看到后能回想起 Feature 内容。只要内容已经是摘要，就不限制字符数量。Issue title 只概括请求本身的内容或预期结果，不描述调用来源、工作流或创建动作；不得加入“Feature Create 创建的”“使用 feature-create”“由 Codex 创建”等元叙述，也不添加 Branch 前缀。即使请求本身是在修改 `feature-create`，也应概括实际行为变化，例如使用“新 Issue 自动添加 enhancement label”，而不是“Feature Create 创建的 Issue 自动添加 enhancement label”。
2. 以本 `SKILL.md` 为基准解析 `../_feature-workflow/github_feature.py`，然后执行 `create --summary <摘要> --request-file <文件>`。脚本会确定性地识别当前 GitHub repository 和 Project。对于新请求，它会创建 Issue，通过 `--assignee @me` assign 给当前 GitHub 用户并添加 `enhancement` label、加入 Project，再显式移至 Ready，同时在 Git local state 中保存 Issue number 和 Ready 步骤完成标记；不要假设新 Project item 具有任何初始 Status。如果已有 pending state，脚本只会在验证 repository、Project、Issue URL 和完整 Issue body 都与本次请求一致后，按已保存的 Issue number 恢复，校验当前用户仍是 assignee 且 Issue 带有 `enhancement` label，并补齐尚未完成的 Ready 步骤；绝不能根据摘要搜索。读取标准输出的 JSON：
   - `created`：已创建新 Issue。
   - `resumed`：已恢复现有 Issue。
   - `project_status`：必须是配置的 Ready Status 名称。

   执行前先在沙箱中检查 `gh auth status`；如果明确显示认证无效或令牌失效，只将同一个必需的工作流命令以限定范围的主机权限重试一次，使其内部所需的 `gh` 命令使用主机认证；不得运行其他命令或扩大访问范围。
3. `create` 成功且 `project_status` 确认 Issue 处于 Ready 后，在真正开始检查代码、制定实现方案或修改文件之前，执行同一脚本的 `start`。读取标准输出的 JSON，要求 `action` 为 `started`，且 `project_status` 必须是配置的 In progress Status 名称。只有两项都确认后，才能检查并实现 Feature。`start` 可安全重试；如果 Status 已经是 In progress，它会补齐置顶和 local state。
4. Branch 不是本工作流的一部分，不检查、创建、切换或记录 Branch；即使当前使用 `main` 或 `master` 也可以继续。
5. 完成实现和适当验证。不要替用户 commit、push、merge 或 review 修改。
6. 完成实现和验证后，执行同一脚本的 `review`。它使用本地保存的 Issue number，将 Project item 从 In progress 移至 In review，并返回 `table`。如果命令失败，立即停止。
7. 在文本代码块中原样显示 `table`，不要输出其他后续操作提醒。

遇到任何异常、脚本错误或需要用户输入，立即停止。不要分析原因、重试或执行后续步骤；只报告最关键的错误或中断信息。脚本调用必须静默，除成功结果和错误信息外不要输出内容。
