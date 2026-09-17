---
name: feature-done
description: 将当前已完成 review 的 Feature 在关联 GitHub Project 中标记为 Done 并关闭 Issue。仅在用户已经完成 review 和 commit、准备结束跟踪流程时使用。
metadata:
  short-description: 将完成 review 的 Feature 标记为 Done 并关闭 Issue
---

# 完成 Feature

默认静默执行，不要输出执行过程、工具调用、推理或额外说明。成功结束时只在文本代码块中原样显示脚本返回的 `table` 字符表格，其中包含 Issue title、Project Status 和 Issue URL；不要添加 review、commit、merge 或其他后续操作提醒。

专业术语保留英文，不翻译 `Feature`、`Skill`、`Issue`、`Project`、`Project item`、`Status`、`Goal`、`Branch`、`commit`、`push`、`merge` 和 `review`。Status 流只使用 `Ready`、`In progress`、`In review`、`Done`，这些值必须保持原样。

本 Skill 不管理 Codex Goal。是否使用 `/goal` 以及 Goal 的完成或其他生命周期操作，全部由用户和外层 `/goal` 工作流决定。

1. 以本 `SKILL.md` 为基准解析 `../_feature-workflow/github_feature.py`，然后执行 `done`。
2. 脚本使用 `.git/codex-feature-create.json` 中保存的 Issue number 定位 Issue，不检查它当前的 Status；先将 Project item 移动到 Done，再以完成原因为 Issue 执行关闭操作，最后删除这个 local state 文件，让下一次 `feature-create` 可以创建新 Issue。只有前两步都成功后才能删除 local state；部分失败时必须保留 local state 以供重试。Project item 已经处于 Done 或 Issue 已经关闭时，对应操作视为成功的空操作。标准输出 JSON 中的 `project_status` 必须是配置的 Done Status 名称，`issue_state` 必须是 `CLOSED`，`local_state` 必须是 `cleared`，并且必须包含 `table`。执行前先在沙箱中检查 `gh auth status`；如果明确显示认证无效或令牌失效，只将同一个必需的工作流命令以限定范围的主机权限重试一次，使其内部所需的 `gh` 命令使用主机认证；不得运行其他命令或扩大访问范围。
3. 在文本代码块中原样显示 `table`，不要输出其他后续操作提醒。

不要替用户 commit、push、merge 或 review 代码。找不到 Issue 或发生任何脚本错误时，立即停止；不要分析原因、重试或执行其他操作，只报告最关键的错误信息。脚本调用必须静默，除成功结果和错误信息外不要输出内容。
