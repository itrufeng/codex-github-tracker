# 仓库指南

## 文档受众

让 `README.md` 聚焦初次使用者所需的内容：安装、端到端使用示例、卸载、Project 选择以及可配置的 Status 名称。实现细节和维护者指南应放在本文件或 `docs/workflows.md` 中，不要继续扩充 `README.md`。

## 组件

三个仅限显式调用的 Skill 是 `feature-create/`、`feature-continue/` 和 `feature-done/`。它们共用 `_feature-workflow/github_feature.py` 中的确定性执行脚本。详细的生命周期文档位于 `docs/workflows.md`。

向用户显示的 Skill 名称仍为 `feature-create`、`feature-continue` 和 `feature-done`。其中的中文文本仅作为描述性 UI 文案。Skill 不管理 Codex Goal；使用 Goal 时，其生命周期由外层 `/goal` 工作流管理。

## Project 和 Status 配置

默认的单选字段是 `Status`，选项为 Ready、In progress、In review 和 Done。仓库特定的覆盖配置位于 `.codex/feature-workflow.json`，对应配置项为 `status_field`、`ready_status`、`in_progress_status`、`in_review_status` 和 `done_status`。所有配置项均可省略；省略时保留默认值。

当一个仓库关联了多个符合条件的 Project 时，使用同一配置文件中的 `project_number` 选择目标。不要添加 `project_owner`：Project 命令始终使用 `@me`，且不支持组织拥有的 Project。保持 `feature-workflow.example.json` 与可接受的配置结构一致。

## Git 和 Branch 行为

该工作流不依赖 Spec Kit。Branch 不属于该工作流；除非用户明确要求 Git 操作，否则 Skill 不检查、创建、切换或记录 Branch。执行脚本可以运行识别仓库以及读写 Git 本地状态所需的最少 Git 命令。

不要根据 Branch、标题或 Status 列推断 Issue。应根据 Git 本地状态中保存的精确仓库、Issue URL 和编号、Project item ID、字段 ID 及选项 ID 解析 Issue。

## 调用内容

Skill 调用名称是控制语法，不是 Feature 内容。在写入 Issue 正文前移除一个位于开头的 `$feature-create`，在写入 Issue 评论或计算待处理状态的哈希前移除一个位于开头的 `$feature-continue`。`feature-done` 不向 GitHub 写入请求文本。Issue 标题应聚焦所请求的行为或结果，不要包含源自工作流的措辞。

## 恢复约束

`feature-create` 将 Issue 编号和请求哈希存储在 `.git/codex-feature-create.json` 中。重试时加载这个精确的 Issue，并验证仓库、Project、URL、完整正文、被指派用户和 `enhancement` 标签；绝不按摘要搜索。`create` 将 Issue 添加到 Project，记录返回的 Project item ID，并显式将其移至 Ready。在检查或实现 Feature 前，`start` 必须将其从 Ready 移至 In progress。

`feature-continue` 在 `.git/codex-feature-continue.json` 中存储一个继续开发周期。其不可见的操作标记使评论创建具备幂等性。继续前重新打开已关闭的 Issue，并且仅在 Project item 返回 In review 后清除继续开发状态。

`feature-done` 先将 Project item 移至 Done，再将 Issue 以 `completed` 状态关闭。仅在两项操作均成功后删除 `.git/codex-feature-create.json`。该状态一旦清除，已完成的 Feature 就无法通过 `feature-continue` 恢复。

Status 和 Issue 变更必须保持可安全重试。将 Project item 移至 Ready、In progress、In review 或 Done 后，把它放在该列顶部。如果 Status 更改后定位失败，重试同一操作时必须完成定位步骤，且不得重复其他副作用。

成功的 `review` 和 `done` 命令返回相同的字符表格格式。Skill 成功响应只包含该表格，不附加 commit、review、push 或 merge 提醒。
