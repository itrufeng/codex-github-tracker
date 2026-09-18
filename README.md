# 功能开发工作流技能

## 安装

首次使用前需要安装 `git` 和 GitHub 官方命令行工具 `gh`。先检查 `gh` 是否已安装：

```bash
gh --version
```

如果能看到版本号，可以跳过 `gh` 安装。否则请按 [GitHub CLI 官方安装说明](https://cli.github.com/) 安装。安装后登录 GitHub，并授予 Project 访问权限：

```bash
gh auth login
gh auth refresh -s project
```

获取本仓库并进入根目录：

```bash
gh repo clone itrufeng/codex-github-tracker
cd codex-github-tracker
```

然后选择一种方式安装本套件。

### 全局安装

安装后可以在所有项目中使用这三个 Skill：

```bash
./install.sh install --global
```

### 项目安装

只安装到指定的 Git repository：

```bash
./install.sh install --project /path/to/repository
```

把 `/path/to/repository` 替换为你的项目路径。

## 使用

假设你已经有一个 Todo List App，现在想让它在每天开始时，对昨天没完成的任务重新安排优先级。在 Codex 中输入：

```text
$feature-create 为 Todo List App 增加每日任务整理功能。每天第一次打开应用时，列出昨天未完成的任务，让用户通过拖拽重新安排它们的优先级，确认后保存新顺序。
```

`$feature-create` 会创建 Issue、加入 GitHub Project，并在真正开始实现前将 Status 从 Ready 移到 In progress。实现和验证完成后，Status 会进入 In review。

试用后，你可能发现某些昨日任务已经不需要再做。这时不需要重新创建 Feature，而是继续打磨当前 Feature：

```text
$feature-continue 在重新安排昨日任务优先级时，为每个任务增加“放弃任务”选项。被放弃的任务不再进入今日列表，但仍保留在历史记录中。
```

如果 review 后还有新想法，可以多次使用 `$feature-continue` 追加具体要求，直到功能满意。最后输入：

```text
$feature-done
```

`$feature-done` 会将 Status 移到 Done、关闭 Issue，并结束这次 Feature 工作流。

## 卸载

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

## 常见问题

### Issue 会被加入哪个 Project？

工作流会从当前 repository 关联的 Project 中，选择由当前 `gh` 用户拥有且仍开放的 Project。如果只有一个符合条件的 Project，不需要任何配置；脚本会通过 `Repository.projectsV2` 自动发现它，并使用 `--owner @me` 调用 Project 命令。

### 一个 repository 关联了多个 Project 怎么办？

如果有多个符合条件的 Project，请在当前 repository 中创建 `.codex/feature-workflow.json`，用 `project_number` 指定 Issue 应加入的 Project：

```json
{
  "project_number": 123
}
```

只有当该编号对应的 Project 已关联当前 repository，并且由当前 `gh` 用户拥有时，脚本才会接受该配置。

### 可以选择组织拥有的 Project 吗？

目前不支持。工作流始终使用 `@me`，因此只能选择当前 `gh` 用户拥有的 Project。

### 我的 Project 使用了不同的 Status 列名怎么办？

默认使用 `Status` 字段中的 Ready、In progress、In review 和 Done。如果你的 Project 使用了其他名称，请在当前 repository 的 `.codex/feature-workflow.json` 中建立对应关系：

```json
{
  "status_field": "Workflow",
  "ready_status": "准备开发",
  "in_progress_status": "开发中",
  "in_review_status": "等待审核",
  "done_status": "已完成"
}
```

只需写入与默认值不同的配置。如果还需要选择 Project，可在同一文件中加入 `project_number`。完整示例见 `feature-workflow.example.json`。
