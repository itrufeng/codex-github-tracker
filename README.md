# 功能开发工作流技能

本套件包含三个可分别调用的 Codex 技能和一个共用的确定性运行脚本：

```text
feature-create/
feature-continue/
feature-done/
_feature-workflow/
```

请先安装 `git` 和官方 GitHub 命令行工具（`gh`），确保它们位于 PATH 中；然后执行 `gh auth login` 登录，并通过 `gh auth refresh -s project` 授予项目访问权限。

## 安装与卸载

为当前用户安装。Codex 可以从所有项目中发现 `$HOME/.agents/skills` 下的这些技能：

```bash
./install.sh install --global
```

为单个项目安装，需要传入项目路径。脚本会解析 Git 仓库根目录，并安装到 `<仓库>/.agents/skills`：

```bash
./install.sh install --project /path/to/repository
```

从全局 Codex 目录卸载：

```bash
./install.sh uninstall --global
```

仓库配置保存在各自代码库中。卸载时可以提供需要同时删除用户数据的所有仓库；脚本会删除 `.codex/feature-workflow.json` 以及 `.git` 下待处理的功能工作流状态：

```bash
./install.sh uninstall --global \
  --repo /path/to/repository-one \
  --repo /path/to/repository-two
```

项目级卸载使用项目路径，并自动删除该项目的 `.codex/feature-workflow.json` 和 Git 本地待处理状态：

```bash
./install.sh uninstall --project /path/to/repository
```

安装器会标记由它管理的目录，并拒绝覆盖或删除同名但没有标记的目录。全局卸载不会扫描用户主目录查找仓库；请用可重复的 `--repo` 参数安全删除仓库本地配置。

当前仓库只关联一个由当前 `gh` 用户拥有且仍开放的项目时，不需要任何配置。脚本通过 `Repository.projectsV2` 自动发现它，并始终用 `--owner @me` 调用项目命令。

如果仓库关联了多个由当前用户拥有的项目，请创建 `.codex/feature-workflow.json`，写入所选项目编号：

```json
{
  "project_number": 123
}
```

只有当指定编号对应的项目已关联当前仓库，并且由当前 `gh` 用户拥有时，脚本才会接受该配置。由于工作流始终使用 `@me`，目前不支持组织拥有的项目。

## 使用方式

三个技能默认静默运行。成功结束时会显示字符表格，其中包含议题标题、项目列名和议题地址。任何异常或中断都会立即停止，不会自动分析原因、重试或继续目标。

三个技能都关闭了隐式调用，只能通过 `$feature-create`、`$feature-continue` 或 `$feature-done` 手动调用，不会由 AI 根据请求内容自动选择。

## 项目字段和状态名称

默认情况下，项目必须包含以下单选字段和选项：

```text
Status
├── Ready
├── In progress
├── In review
└── Done
```

如果你的项目使用其他名称，只需在 `.codex/feature-workflow.json` 中声明不同的值：

```json
{
  "status_field": "Workflow",
  "ready_status": "准备开发",
  "in_progress_status": "开发中",
  "in_review_status": "等待审核",
  "done_status": "已完成"
}
```

如果仓库关联了多个项目，请在同一文件中加入 `project_number`：

```json
{
  "project_number": 123,
  "status_field": "Workflow",
  "ready_status": "准备开发",
  "in_progress_status": "开发中",
  "in_review_status": "等待审核",
  "done_status": "已完成"
}
```

所有配置项都是可选的。不要添加 `project_owner`；项目命令始终使用 `@me`。完整配置参考见 `feature-workflow.example.json`。

## 分支工具兼容性

本工作流不依赖 Spec Kit。分支不是本工作流的一部分；技能不检查、创建、切换或记录分支，即使当前使用 `main` 或 `master` 也可以继续。

因此，同一个技能在使用和不使用 Spec Kit 的仓库中都可以运行。

脚本始终使用本地状态中保存的议题编号和精确的仓库、议题网址、项目项标识符、字段标识符、选项标识符进行操作；不根据分支名、标题或当前状态列猜测议题。缺少数据时会停止。

调用名称属于控制语法，不属于功能内容。`feature-create` 会在写入议题正文前移除开头的一个 `$feature-create`；`feature-continue` 会在写入议题评论或计算待处理状态哈希前移除开头的一个 `$feature-continue`。`feature-done` 不会向 GitHub 写入请求文字。

## 中断后的 feature-create 恢复

`feature-create` 会把议题编号和完整请求的哈希保存到 `.git/codex-feature-create.json`。再次执行 `feature-create` 不会创建另一个议题；它会加载精确的议题编号，并在恢复前验证仓库、项目、网址和完整议题正文。它绝不会根据摘要搜索。

脚本创建 Issue 时会使用 `--assignee @me` assign 给当前 GitHub 用户。恢复 pending Issue 时会校验 assignees，并仅在当前用户缺失时补齐。随后脚本把 Issue 加入 Project，要求 `gh project item-add` 返回 JSON，保存其中的 Project item ID，然后显式将 Project item 移至 Ready，再移至 In progress。它不假设 GitHub 会赋予任何初始 Status，也不会立即依赖 `gh project item-list` 查到刚加入的 Project item。Ready 步骤完成后会保存标记，确保中断恢复时补齐步骤且不会无故回退；旧版 `backlog_set` 标记会迁移为 `ready_set`。对于没有 Project item ID 的旧 pending state，脚本会查找现有 Project item，或以幂等方式重新添加。

如果恢复或手动加入的项目项最初落在其他状态，恢复时会先显式移动到 Ready，再移动到目标列。状态转换只校验目标是否存在，并且可以安全重试。

`feature-create` 只有在脚本成功返回 In progress 的 `project_status` 后，才会检查、创建或开始 Codex 目标。

`feature-continue` 会先用 `get_goal` 检查是否存在冲突目标，但此时不会开始目标任务。只有脚本成功返回 In progress 的 `project_status` 后，才会创建或开始目标。目标内容一致且未结束时继续使用；没有未结束目标或之前的目标已经结束时创建新目标；遇到内容不同的未结束目标时停止。

`feature-continue` 使用 `.git/codex-feature-continue.json` 保存当前继续开发周期。议题已经关闭时会先重新打开。发表评论前会生成不可见的唯一操作标记，因此发生部分失败后重试时，可以找到精确评论，而不会重复发表。只有项目项回到 In review 后才会清除该状态。内容一致且未结束的目标会继续使用；没有目标或目标已结束时，会为同一个待处理请求创建新目标。

项目状态修改和议题开关操作都是幂等的。`feature-done` 会先把项目项移到 Done，再以完成原因为议题执行关闭操作；两步都成功后删除 `.git/codex-feature-create.json`，让下一次 `feature-create` 创建新议题。部分失败时会保留状态以供重试。成功清理后，原功能不能再通过 `feature-continue` 恢复。

`review` 和 `done` 命令会生成统一字符表格。三个技能成功结束时均只以文本代码块显示该表格，不附加审核、提交、合并或其他后续操作提醒。
