---
name: feature-create
description: 创建并开发新 Feature，同时同步 GitHub Issue 和 Project Status。适用于需要从 Ready、In progress 跟踪到 In review 的新 Feature 开发。
metadata:
  short-description: 创建并开发受跟踪的 Feature
---

# 创建 Feature

默认静默执行，不要输出执行过程、工具调用、推理或额外说明。成功结束时只在文本代码块中原样显示脚本返回的 `table` 字符表格，其中包含 Issue title、Project Status 和 Issue URL；不要添加 review、commit、merge 或其他后续操作提醒。

专业术语保留英文，不翻译 `Feature`、`Skill`、`Issue`、`Project`、`Project item`、`Status`、`Goal`、`Branch`、`commit`、`push`、`merge` 和 `review`。Status 流只使用 `Ready`、`In progress`、`In review`、`Done`，这些值必须保持原样。

Feature 请求仅指显式调用 `$feature-create` 之后的用户文字。不要把 `$feature-create` 本身写入请求、Issue body 或 Codex Goal。将其余文字原样保存到临时 UTF-8 文件，不要用摘要替代。脚本也会确定性地移除开头的一个 `$feature-create` 标记，作为安全保障。

1. 生成清晰且非空的 Issue title 摘要，让用户看到后能回想起 Feature 内容。只要内容已经是摘要，就不限制字符数量；Issue title 只使用摘要，不添加 Branch 前缀。
2. 以本 `SKILL.md` 为基准解析 `../_feature-workflow/github_feature.py`，然后执行 `create --summary <摘要> --request-file <文件>`。脚本会确定性地识别当前 GitHub repository 和 Project。对于新请求，它会创建 Issue，通过 `--assignee @me` assign 给当前 GitHub 用户并添加 `enhancement` label、加入 Project、显式移至 Ready，再移至 In progress，同时在 Git local state 中保存 Issue number 和 Ready 步骤完成标记；不要假设新 Project item 具有任何初始 Status。如果已有 pending state，脚本只会在验证 repository、Project、Issue URL 和完整 Issue body 都与本次请求一致后，按已保存的 Issue number 恢复，校验当前用户仍是 assignee 且 Issue 带有 `enhancement` label，并补齐尚未完成的 Status 步骤；绝不能根据摘要搜索。读取标准输出的 JSON：
   - `created`：已创建新 Issue。
   - `resumed`：已恢复现有 Issue。
   - `project_status`：必须是配置的 In progress Status 名称。

   执行前先在沙箱中检查 `gh auth status`；如果明确显示认证无效或令牌失效，只将同一个必需的工作流命令以限定范围的主机权限重试一次，使其内部所需的 `gh` 命令使用主机认证；不得运行其他命令或扩大访问范围。
3. 只有 `create` 成功且 `project_status` 确认 Issue 已经处于 In progress 后，才能协调或开始 Codex Goal；不得提前调用 `get_goal` 或 `create_goal`。然后调用 `get_goal`：如果没有未结束的 Goal，就调用 `create_goal`，并将完整 Feature 请求原样作为 Goal。如果未结束 Goal 的内容与请求完全一致，继续该 Goal，不要重复创建。如果未结束 Goal 的内容不同，停止并请用户先结束或取消该 Goal；不要替换它。Goal status 为 `complete` 或 `blocked` 时不能恢复：为这个仍待处理的 Feature 创建新 Goal。只有完成实现和适当验证后才能完成 Goal，不得仅因时间或预算不足而完成。
4. Branch 不是本工作流的一部分，不检查、创建、切换或记录 Branch；即使当前使用 `main` 或 `master` 也可以继续。
5. 持续执行 Goal，直到完成实现和适当验证。不要替用户 commit、push、merge 或 review 修改。
6. 完成 Goal 前，执行同一脚本的 `review`。它使用本地保存的 Issue number，将 Project item 从 In progress 移至 In review，并返回 `table`。如果命令失败，不要完成 Goal。
7. 将 Goal 标记为完成，然后在文本代码块中原样显示 `table`，不要输出其他后续操作提醒。

遇到任何异常、脚本错误、Goal 暂停、Goal 失败或需要用户输入，立即停止。不要分析原因、重试、继续 Goal 或执行后续步骤；只报告最关键的错误或中断信息。脚本调用必须静默，除成功结果和错误信息外不要输出内容。
