---
name: feature-continue
description: 继续澄清并实现 Feature 细节，在同一 Issue 追加 Comment 并同步 GitHub Project Status。
metadata:
  short-description: 继续澄清并实现功能细节，在同一 Issue 追加 Comment 并同步 GitHub Project Status
---

# 继续开发 Feature

默认静默执行，不要输出执行过程、工具调用、推理或额外说明。成功结束时只在文本代码块中原样显示脚本返回的 `table` 字符表格，其中包含 Issue title、Project Status 和 Issue URL；不要添加 review、commit、merge 或其他后续操作提醒。

专业术语保留英文，不翻译 `Feature`、`Skill`、`Issue`、`Project`、`Project item`、`Status`、`Goal`、`Branch`、`commit`、`push`、`merge` 和 `review`。Status 流只使用 `Ready`、`In progress`、`In review`、`Done`，这些值必须保持原样。

后续请求仅指显式调用 `$feature-continue` 之后的用户文字。不要把 `$feature-continue` 本身写入请求或 Issue comment。将其余文字原样保存到临时 UTF-8 文件。脚本也会确定性地移除开头的一个 `$feature-continue` 标记，作为安全保障。

本 Skill 不管理 Codex Goal。是否使用 `/goal` 以及 Goal 的创建、检查、暂停、恢复和完成，全部由用户和外层 `/goal` 工作流决定。

1. 以本 `SKILL.md` 为基准解析 `../_feature-workflow/github_feature.py`，然后执行 `continue --request-file <文件>`。脚本使用 `.git/codex-feature-create.json` 中保存的 Issue number 定位 Issue，不关心它当前在哪个 Status；如果 Issue 已经关闭，先重新打开 Issue；然后把完整请求和不可见的操作标记作为一条 Issue comment 发布，并将 Project item 移动到 In progress。重试时会复用该标记，绝不会重复发布 comment。标准输出 JSON 中的 `project_status` 必须是配置的 In progress Status 名称，`issue_state` 必须是 `OPEN`。
   执行前先在沙箱中检查 `gh auth status`；如果明确显示认证无效或令牌失效，只将同一个必需的工作流命令以限定范围的主机权限重试一次，使其内部所需的 `gh` 命令使用主机认证；不得运行其他命令或扩大访问范围。
2. 只有 `continue` 成功且 `project_status` 确认 Issue 已经处于 In progress 后，才能开始实现后续请求。
3. 完成实现和适当验证。不要替用户 commit、push、merge 或 review 修改。
4. 完成实现和验证后，执行同一脚本的 `review`。它会确定性地解析同一 Issue，将 Project item 从 In progress 移至 In review，然后才清除待处理的 continue state 并返回 `table`。Status 转换和清理都可以安全重试。如果命令失败，立即停止。
5. 在文本代码块中原样显示 `table`，不要输出其他后续操作提醒。

找不到 Issue、发生脚本错误或需要用户输入时，立即停止。不要分析原因、重试或执行后续步骤；只报告最关键的错误或中断信息。脚本调用必须静默，除成功结果和错误信息外不要输出内容。
