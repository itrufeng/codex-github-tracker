# 内部工作流程

  feature-create
      Ready → 开始实现前设为 In progress → 开发/验证 → In review
                                                    ↓
  feature-continue                       │
      开始实现前设为 In progress → 继续开发/验证 → In review
                                                ↓
  feature-done
      Done → 关闭 Issue → 清理本地状态

  ### 1. feature-create：创建并开发新 Feature

  用途：启动一个新的 Feature 开发周期，同时建立 GitHub Issue 和 Project 跟踪。

  主要流程：

  1. 读取 $feature-create 后面的完整用户请求。
  2. Codex 根据请求生成简洁的 Issue title。
  3. 脚本自动确定当前 GitHub repository 和关联的个人 Project。
  4. 创建 GitHub Issue：
      - body 是用户的完整原始请求
      - assign 给当前 GitHub 用户
      - 添加 enhancement label

  5. 将 Issue 加入 Project。
  6. Status 显式设为 Ready。
  7. 将 Issue、Project 等信息保存在：
      - .git/codex-feature-create.json

  8. 真正开始实现前，将 Status 从 Ready 改为 In progress。
  9. Codex 开始实现 Feature，并执行适当验证。
  10. 实现完成后执行 review：
      - Status 改成 In review
      - 输出 Issue title、Status、URL 表格

  11. 不执行 commit、push、merge 或真正的人工 review。

  它有恢复机制：如果创建 Issue 后流程中途失败，再次运行会根据本地状态恢复，不会根据 title 搜索或重复创建 Issue；但会严格核对 repository、Project、Issue
  URL、body、assignee 和 label。

  相关文件：.agents/skills/feature-create/SKILL.md

  ### 2. feature-continue：review 后继续修改

  用途：Feature 已经进入 In review，review 后发现还需要修改时，重新进入开发状态。

  主要流程：

  1. 读取 $feature-continue 后面的完整修改请求。
  2. 从 .git/codex-feature-create.json 找到原来的 Issue。
  3. 如果 Issue 已关闭，重新打开。
  4. 将本次修改请求作为一条 Issue comment 发布。
  5. comment 末尾加入不可见的操作标记：
      - 用于识别同一次操作
      - 重试时不会重复发布 comment

  6. 开始实现前，将 Project Status 直接改为 In progress，不经过 Ready。
  7. Codex 实现修改并验证。
  8. 完成后执行 review：
      - Status 再次改成 In review
      - 删除 .git/codex-feature-continue.json
      - 输出结果表格

  这里有两份本地状态：

  - codex-feature-create.json：整个 Feature 生命周期的主状态。
  - codex-feature-continue.json：某一次继续开发操作的临时状态。

  相关文件：feature-continue/SKILL.md

  ### 3. feature-done：结束 Feature 跟踪

  用途：用户已经完成 review 和 commit，确认这个 Feature 可以结束时，收尾 GitHub 跟踪流程。

  主要流程：

  1. 从 .git/codex-feature-create.json 找到当前 Issue。
  2. 将 Project Status 改为 Done。
  3. 以 completed 原因关闭 Issue。
  4. 前两步都成功后，删除 .git/codex-feature-create.json。
  5. 输出 Issue title、Done、Issue URL 表格。

  它是幂等的：

  - 已经是 Done：不重复修改。
  - Issue 已关闭：不重复关闭。
  - 中途失败：保留本地状态，方便再次执行。
  - 只有 Project 更新和 Issue 关闭全部成功，才清理状态。

  相关文件：feature-done/SKILL.md

  ### 三者的共同约束

  三个 Skill 共用同一个脚本：_feature-workflow/github_feature.py。

  共同特点：

  - 都是显式调用，allow_implicit_invocation: false，不会自动触发。
  - 使用当前 repository 关联的、由当前 GitHub 用户拥有的个人 Project。
  - Project 不明确时可通过 .codex/feature-workflow.json 配置 project_number。
  - Status 名称可以配置，默认是：
      - Ready
      - In progress
      - In review
      - Done

  - 不管理 Codex Goal。
  - 默认不读取或输出 Git 状态、历史或差异，也不执行 Branch、commit、push、merge、rebase、tag、stash 等 Git 操作。
  - 只有用户在 Skill 后面的请求说明中明确要求时，才执行对应的 Git 操作。
  - 工作流脚本为识别 repository 和读写 Git local state 而内部执行的必要命令不受此限制，但不得额外运行 Git 命令。
  - 除非用户明确要求，不执行人工 review。
  - 默认静默运行，成功时只输出最终表格。
  - 异常时立即停止，避免继续产生 GitHub 副作用。

  有一个值得注意的逻辑点：feature-done 的说明要求“已经完成 review 和 commit”后使用，但脚本本身不会检查当前 Status 是否真的是 In review，也不会检查是否已
  经 commit。也就是说，这是 Skill 层面的使用约束，不是脚本强制执行的状态机约束。仅供 feature-create 使用的 `start` 会强制要求当前 Status 为 Ready；其他 Status 更新仍允许从任意当前状态直接移动到目标状态。
