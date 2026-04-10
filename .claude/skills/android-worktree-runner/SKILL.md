---
name: android-worktree-runner
description: |
  基于 git worktree 隔离的 Plan 任务执行器。一个 Plan 对应一个 worktree。
  子任务在同一 worktree 内顺序执行。跟踪 pending/in-progress/completed
  三态进度。每次 commit 前执行 Android 验证 (Gradle build、lint、单元测试)。
  支持多个 plan/worktree 并行工作。支持 /clear 后恢复。
  适用场景: 执行 plan、跟踪任务进度、管理 worktree 开发工作流。
voice-triggers:
  - "执行任务"
  - "开始计划"
  - "任务运行"
  - "执行计划"
---

# Android Worktree Runner

## 概述

一个 Plan = 一个 Worktree。导入 Plan，创建隔离的 worktree，按顺序执行任务，
每个任务完成后执行 Android 验证并提交。

**启动时声明:** "我正在使用 android-worktree-runner skill。"

## 调用方式

```bash
/android-worktree-runner              # 显示所有 plan 状态，选择操作
/android-worktree-runner <plan-id>    # 直接恢复指定 plan
/android-worktree-runner import       # 强制导入新 plan (扫描发现)
/android-worktree-runner import <plan-file>  # 导入指定 plan 文件
/android-worktree-runner status       # 仅显示状态，不执行操作
```

**参数处理:**
- 带参数 `<plan-id>` 调用时，跳过 Phase 1 的状态展示，直接进入
  该 plan 的 Phase 2 执行阶段。如果 plan-id 匹配 `tasks.json` 中的某个 plan，
  进入其 worktree 并恢复。未找到则显示状态并提示 "未找到 Plan: <参数>"。
- `import <plan-file>` 调用时，跳过 Phase 0 步骤 1 的来源扫描，直接将
  指定的 plan 文件路径作为输入，进入步骤 2 (解析 Plan)。

**`/clear` 后恢复:** 此 skill 在 `/clear` 后可完整恢复。所有状态保存在磁盘上的
`tasks.json` 中，不依赖内存状态。每次调用时，skill 读取 `tasks.json` 作为唯一
真相源。详见下方「恢复保障」章节。

## 存储

所有持久化状态存储在**主项目根目录**的 `.claude/android-worktree-runner/tasks.json` 中
（不在任何 worktree 内部）。

### 从任意上下文定位 tasks.json

此 skill 可能在主 worktree、某个 plan worktree 中、或 `/clear` 之后无任何上下文时被调用。
使用以下方式定位 `tasks.json`:

```bash
# 找到主 worktree（worktree 列表的第一项）
MAIN_WORKTREE=$(git worktree list 2>/dev/null | head -1 | awk '{print $1}')
# 如果不在 git 仓库中，报错退出
if [ -z "$MAIN_WORKTREE" ]; then
  echo "错误: 当前不在 git worktree 中"
  exit 1
fi
TASKS_FILE="$MAIN_WORKTREE/.claude/android-worktree-runner/tasks.json"
```

**关键规则:** `tasks.json` 是唯一的真相源。每次任务状态变更（in-progress、
completed、验证结果、commit hash）必须**立即写入** `tasks.json`。不允许延迟写入，
不允许批量写入。文件必须始终反映磁盘上的最新状态，以确保 `/clear` 恢复生效。

### 数据结构

```json
{
  "version": 2,
  "plans": {
    "plan-<时间戳>": {
      "id": "plan-<时间戳>",
      "title": "Plan 标题",
      "status": "pending | in-progress | completed",
      "plan_source": {
        "type": "memory | markdown | gstack-design | superpowers | custom",
        "ref": "文件路径或标识符"
      },
      "worktree": {
        "path": ".claude/worktrees/plan-<时间戳>",
        "branch": "plan/<slug标题>",
        "created_at": "ISO-8601",
        "based_on_commit": "abc1234"
      },
      "tasks": [
        {
          "id": "plan-<时间戳>-1",
          "title": "任务标题",
          "status": "pending | in-progress | completed",
          "steps": [
            "步骤 1 描述",
            "步骤 2 描述"
          ],
          "commit": null,
          "verification": {
            "gradle_build": false,
            "lint": false,
            "unit_tests": false
          },
          "tdd": {
            "required": false,
            "executed": false,
            "skipped": false,
            "skip_reason": null,
            "coverage_percent": null,
            "report_path": null,
            "boundary_categories_covered": []
          },
          "timestamps": {
            "created": "ISO-8601",
            "started": null,
            "completed": null
          }
        }
      ],
      "timestamps": {
        "created": "ISO-8601",
        "started": null,
        "completed": null
      }
    }
  }
}
```

---

## Phase 0: 导入 Plan

当 `tasks.json` 不存在，或用户要求导入时执行。

### 步骤 1: 检测可用的 Plan 来源

检查所有来源，收集可用的 plan:

```bash
# 1. Markdown plan 文件
find . -path "*/node_modules" -prune -o -name "*plan*.md" -print 2>/dev/null | head -20

# 2. Superpowers plan
ls docs/plans/*.md 2>/dev/null

# 3. GStack design doc
ls ~/.gstack/projects/*/*-design-*.md 2>/dev/null | head -10

# 4. 当前 git 分支中与 plan 相关的文件
git diff --name-only HEAD~5..HEAD 2>/dev/null | grep -i plan
```

对于 **Claude Code 内存中的 plan**: 检查当前上下文中是否有活跃的 plan 文件路径
（系统消息中会提供 plan 文件路径）。如果找到，将其纳入。

### 步骤 2: 展示来源

使用 AskUserQuestion 展示所有检测到的来源 + "自定义路径" 选项。

> 检测到以下 Plan 来源:
> - A) `docs/plans/2026-04-10-auth.md` (superpowers 格式)
> - B) `~/.gstack/projects/myapp/main-design-20260410.md` (gstack design doc)
> - C) `.claude/plans/current-plan.md` (claude code plan)
> - D) 自定义路径...

### 步骤 3: 解析 Plan 为任务树

读取选中的 plan 文件，按以下规则解析任务:

**Superpowers 格式** (`docs/plans/YYYY-MM-DD-*.md`):
- `### Task N: <标题>` → 顶层任务
- `**Step N:**` 或编号列表 → 任务内的步骤
- 代码块 → 实现参考（存储，暂不执行）
- `@skill-name` 引用 → 在执行阶段标注

**GStack design doc** (`*-design-*.md`):
- `## Recommended Approach` 部分 → 提取实现步骤
- `## Next Steps` 部分 → 提取任务
- `## Approaches Considered` 部分 → 记录选定的方案

**通用 Markdown** (任意 plan 文件):
- `## Task N:` 或 `### Task N:` → 顶层任务
- `#### Task N.M:` 或缩进编号项 → 子任务
- `- [ ]` checkbox → 步骤
- 如果没有结构化标题 → 按 `##` 章节拆分，每个章节作为一个任务

**Claude Code 内存中的 plan**:
- 读取上下文中提供的 plan 文件
- 将各主要章节解析为任务（每个主要章节 = 一个任务）

### 步骤 4: 确认解析结果

展示解析后的任务树并请求确认:

```
解析来源: <文件路径>

Plan: <标题>
├── 任务 1: <标题>
│   ├── 步骤 1: <描述>
│   └── 步骤 2: <描述>
├── 任务 2: <标题>
│   └── ...
└── 任务 N: <标题>
```

AskUserQuestion: "导入这 N 个任务?" / "导入前编辑" / "取消"

### 步骤 5: 创建 Worktree 并写入状态

```bash
# 生成 plan ID 和 slug
PLAN_ID="plan-$(date +%Y%m%d-%H%M%S)"
PLAN_SLUG=$(echo "$PLAN_TITLE" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//' | head -c 50)
WORKTREE_PATH=".claude/worktrees/$PLAN_ID"
BRANCH_NAME="plan/$PLAN_SLUG"

# 记录当前 commit 作为基准
BASE_COMMIT=$(git rev-parse --short HEAD)

# 创建 worktree
git worktree add "$WORKTREE_PATH" -b "$BRANCH_NAME"
```

将 `tasks.json` 写入 `$MAIN_WORKTREE/.claude/android-worktree-runner/tasks.json`
（不在 worktree 内部）。路径与上方「存储」章节的解析方式一致。

如果 `tasks.json` 已存在并包含其他 plan，执行合并: 将新 plan 添加到现有的
`plans` 对象中，不覆盖已有数据。

### 步骤 6: 更新 worktree-info.md

创建 worktree 后，**立即更新**项目根目录下的 `worktree-info.md`:

- 如果文件**不存在**: 先执行 `git worktree list` 扫描已有 worktree，
  创建 `worktree-info.md`，将已有 worktree 列入（非 android-worktree-runner
  创建的标记为"外部 worktree"），然后将新 plan 添加到"进行中"部分。
- 如果文件**已存在**: 读取现有内容，在"进行中"部分添加新 plan 的条目。

条目包含: 分支名、worktree 路径、创建时间、基准 commit、任务标题和总数、
当前状态。格式参见上方「Worktree 管理文件」章节。

---

## Phase 1: 状态展示

### 基于参数的直接恢复

如果带 `<plan-id>` 参数调用:
1. 读取 `tasks.json`
2. 查找 `id` 匹配参数，或 `worktree.path` 包含参数的 plan
3. 找到 → 跳过状态展示，直接进入该 plan 的 Phase 2
4. 未找到 → 显示状态并提示 "未找到 Plan: <参数>"

无参数 → 展示完整状态。

### 完整状态展示

读取 `tasks.json` 并展示所有 plan 及其任务进度。

### 展示格式

```
╔══════════════════════════════════════════════════════╗
║              ANDROID WORKTREE RUNNER 状态                    ║
╠══════════════════════════════════════════════════════╣
║                                                       ║
║  ● Plan: 登录流程实现 [进行中]                        ║
║    分支: plan/auth-login-flow                         ║
║    worktree: .claude/worktrees/plan-20260410-001     ║
║    ├─ ✓ 任务 1: 配置 Gradle 依赖                    ║
║    │   commit: a1b2c3d  build✓ lint✓ tests✓         ║
║    ├─ ● 任务 2: 创建登录界面 [当前]                  ║
║    └─ ○ 任务 3: 添加表单验证                         ║
║                                                       ║
║  ○ Plan: Room 数据库搭建 [待开始]                     ║
║    ├─ ○ 任务 1: 定义实体类                            ║
║    └─ ○ 任务 2: 创建 DAO                             ║
║                                                       ║
║  ✓ Plan: 项目初始化 [已完成]                          ║
║    分支: plan/project-init  commit: f5e4d3c          ║
║    3/3 任务已完成                                      ║
║                                                       ║
║  PLAN 总数: 3 | 进行中: 1 | 待开始: 1 | 已完成: 1    ║
║  任务总数: 8 | 已完成: 4 | 剩余: 4                    ║
╚══════════════════════════════════════════════════════╝
```

**状态符号:** `○` 待开始, `●` 进行中, `✓` 已完成

### 操作选择

使用 AskUserQuestion。默认选择最合理的操作:

**存在进行中的 plan 时:**
> 推荐: 继续 "Plan: 登录流程" — 任务 2/3 进行中
> - A) 继续当前 plan (plan/auth-login-flow)
> - B) 开始另一个 plan
> - C) 导入新 plan
> - D) 刷新状态

**无进行中但有待开始的 plan 时:**
> 推荐: 开始 "Plan: Room 数据库搭建" — 0/2 任务完成
> - A) 开始待执行的 plan
> - B) 导入新 plan
> - C) 刷新状态

**所有 plan 都已完成时:**
> 所有 plan 已完成! 接下来做什么?
> - A) 导入新 plan
> - B) 查看已完成的 worktree
> - C) 清理已完成的 worktree

---

## Phase 2: 执行任务

### Subagent 并发控制

当使用 Agent 工具派发 subagent 执行任务时，**最大并发数严格限制为 4 个**。

- 同时运行的 subagent 不得超过 4 个
- 如果有 4 个 subagent 正在运行，必须等待至少一个完成后再派发新的
- 通过 `run_in_background: true` 参数启动 subagent，在收到完成通知后再启动下一个
- 不得为绕过此限制而使用其他并发机制（如 team、多个 Agent 调用等）

### 步骤 1: 进入 Worktree

```bash
WORKTREE_PATH="<tasks.json 中的路径>"
cd "$WORKTREE_PATH"
```

后续所有工作在此 worktree 中进行。文件读取、写入、编辑和 bash 命令都相对于
worktree 根目录执行。

**重要:** `TASKS_FILE` 变量仍然指向主 worktree 的
`.claude/android-worktree-runner/tasks.json`。所有状态更新都写入这个文件，
不写入当前 worktree 内部的文件。

### 步骤 2: 查找下一个待执行任务

扫描当前 plan 的 tasks 数组，找到第一个 `status` 为 `"pending"` 的任务。

如果没有待执行任务，进入 Phase 3（Plan 完成）。

### 步骤 3: 标记任务为进行中

**立即写入 `tasks.json`:**
- 设置 task `status` 为 `"in-progress"`
- 设置 task `timestamps.started` 为当前时间

此写入必须在任何代码变更之前完成。如果 `/clear` 发生在任务执行过程中，
进行中状态已经在磁盘上。

### 步骤 3.5: TDD 分类与执行

在执行任务代码之前，判断该任务是否需要 TDD。

**读取 TDD 要求 (优先级从高到低):**
1. 检查任务步骤中是否包含 `**TDD:** required` 标签 (来自 autoplan)
2. 检查 tasks.json 中该任务的 `tdd.required` 字段
3. 以上都没有: 按关键词和层级分类

**TDD 强制关键词 (任务描述中出现任一即触发):**
`ViewModel`、`Repository`、`UseCase`、`screen`、`feature`、`logic`、`component`、`service`

**TDD 跳过关键词 (任务描述中出现任一即跳过):**
`Gradle`、`Manifest`、`ProGuard`、`migration`、`config`、`setup`、`基础设施`、`测试`

**默认规则:** 无法分类的任务默认走 TDD。宁可多测不可漏测。

**如果 TDD required:**

1. 使用 AskUserQuestion 展示 TDD 确认:
```
任务 "<任务标题>" 需要 TDD。
- A) 执行 TDD + 实现 (推荐)
- B) 跳过 TDD，直接实现 (不推荐)
```

2. 选择 A: 使用 Skill 工具调用 android-tdd:
   - skill: "android-tdd"
   - args: "<任务标题> — 基于步骤: <步骤摘要>"
   - 等待 android-tdd 完成后读取报告

3. 读取 TDD 报告，立即更新 tasks.json:
   - tdd.executed = true
   - tdd.coverage_percent = <报告中的覆盖率数字>
   - tdd.report_path = <报告文件路径>
   - tdd.boundary_categories_covered = <报告中已覆盖的边界类别>

4. 如果 TDD PASS: 检查 TDD 报告中的实现文件列表:
   - 如果 TDD Phase 3 已实现该任务的核心逻辑 → 跳过步骤 4 中已实现的步骤，仅执行 TDD 未覆盖的步骤 (如资源文件、Manifest 配置等)
   - 如果 TDD 仅写了测试未实现 → 正常执行步骤 4
   - 判断方法: 读取 TDD 报告中的 "## 实现文件" 章节，与 plan 步骤中涉及的文件做交集
5. 如果 TDD FAIL: 使用 AskUserQuestion 询问用户如何处理

**如果选择 B (用户跳过 TDD):**
- 立即更新 tasks.json:
  - tdd.skipped = true
  - tdd.skip_reason = "user_override"
- 记录警告: 后续 QA 会检测到 TDD 被跳过，对该任务加强验证
- 继续步骤 4

**如果 TDD not required:**
直接继续步骤 4。

### 步骤 4: 执行任务步骤

对任务 `steps` 数组中的每个步骤:

1. **先读后写。** 如果步骤引用了文件，先读取文件。
2. **严格按指令执行。** Plan 中的步骤是按特定顺序编写的，按顺序执行。
3. **不跳过步骤。** 每个步骤都有其存在的理由。
4. **不添加步骤。** 严格按照 plan 中描述的内容。

**如果步骤被阻塞:**
- 缺少依赖 → 停止，报告问题，等待用户指示
- 构建错误 → 停止，报告错误输出，等待用户指示
- 指令不明确 → 停止，请求澄清
- 测试失败 → 停止，报告失败信息，等待用户指示

**不猜测。不跳过。** 遇到问题停下来询问用户。

### 步骤 5: Android 验证 (commit 前必须执行)

任务中所有步骤完成后，执行验证。

**首先检测是否为 Android 项目:**

```bash
if [ -f "build.gradle" ] || [ -f "build.gradle.kts" ] || \
   [ -f "app/build.gradle" ] || [ -f "app/build.gradle.kts" ]; then
  echo "ANDROID_PROJECT"
else
  echo "NOT_ANDROID"
fi
```

**如果是 Android 项目，按顺序执行以下三项检查。任一项失败则停止。**

```bash
# 1. Gradle 构建
echo "=== Gradle Build ==="
./gradlew assembleDebug 2>&1
BUILD_EXIT=$?

if [ $BUILD_EXIT -ne 0 ]; then
  echo "BUILD FAILED"
  # 报告并询问用户
fi

# 2. Lint 检查 (仅在构建通过后执行)
echo "=== Lint 检查 ==="
./gradlew lintDebug 2>&1
LINT_EXIT=$?

# 3. 单元测试 (仅在 lint 通过后执行)
echo "=== 单元测试 ==="
./gradlew testDebugUnitTest 2>&1
TEST_EXIT=$?
```

**如果任一检查失败:**
- 显示错误输出（最后 50 行）
- AskUserQuestion:
  > Android 验证失败于: [哪个步骤]
  > - A) 修复后重试
  > - B) 跳过此检查并提交
  > - C) 中止任务 (保持进行中状态)

选 A: 回到 Phase 2 步骤 4，由用户指导修复。
选 B: 继续提交，在 verification 中将该检查标记为 `"skipped"`。
选 C: 停止执行，任务保持进行中状态。

**如果不是 Android 项目:**
跳过所有 Android 验证。提示: "未检测到 Android 项目 — 跳过 Gradle/lint/测试验证。"

### 步骤 6: 提交代码

```bash
# 暂存 worktree 中的所有变更
git add -A

# 使用结构化消息提交
TASK_NUM="<任务编号>"
TASK_TITLE="<任务标题>"
PLAN_SLUG="<plan slug>"

git commit -m "$(cat <<EOF
feat($PLAN_SLUG): complete task $TASK_NUM - $TASK_TITLE

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

### 步骤 7: 更新状态 (立即执行 — 恢复机制的关键)

**commit 后立即写入 `tasks.json`:**
- 设置 task `status` 为 `"completed"`
- 设置 task `commit` 为新的 commit hash
- 设置 task `timestamps.completed` 为当前时间
- 更新所有 `verification` 字段为 `true`（或 `"skipped"`）

**同步写入 TDD 状态 (如果适用):**
- 如果 TDD 已执行 (tdd.executed = true): 确保 tdd.coverage_percent、tdd.report_path、tdd.boundary_categories_covered 已写入
- 如果 TDD 被跳过 (tdd.skipped = true): 确保 tdd.skip_reason 已写入
- 如果 TDD 不适用 (tdd.required = false): 保持默认值

此写入不是可选的。它是以下能力的核心机制:
- `/clear` 恢复（状态在上下文清除后仍然存在）
- 跨会话恢复（状态在进程重启后仍然存在）
- 多 worktree 协调（状态在所有 worktree 间共享）

**写入模式:**
```bash
# 读取当前状态
TASKS_JSON="$MAIN_WORKTREE/.claude/android-worktree-runner/tasks.json"
# 通过 Edit 工具更新（精确修改）或 Write 工具重写
# 文件必须在进入下一个任务之前已写入磁盘
```

**同步更新 `worktree-info.md`:**
- 读取 `worktree-info.md`，更新对应 plan 的任务进度 `(X/N 已完成)`
- 更新状态描述（如"任务 2 执行中" → "任务 3 执行中"）
- 如果这是 plan 的最后一个任务，状态更新为"即将完成"

### 步骤 8: 下一个任务或 Plan 完成

- 当前 plan 中还有待执行任务 → 回到步骤 2
- 没有待执行任务 → 进入 Phase 3

---

## Phase 3: Plan 完成

### 步骤 1: 展示总结

```
Plan: <标题> — 已完成
══════════════════════════════════════
任务: N/N 已完成
提交: <commit hash 列表>
验证: 全部通过 / <备注>
分支: plan/<slug>
Worktree: .claude/worktrees/<plan-id>
```

### 步骤 2: 更新状态

设置 plan `status` 为 `"completed"`，设置 `timestamps.completed`。

**同步更新 `worktree-info.md`:**
- 将该 plan 从"进行中"部分**移动**到"已完成"部分
- 填入完成时间和最终 commit hash
- 任务进度更新为 `(N/N 已完成)`
- 状态更新为"已完成"

### 步骤 3: 后续操作

AskUserQuestion:
> Plan 已完成! 如何处理该 worktree?
> - A) 保留 — 我会手动审查和合并
> - B) 合并分支到 main
> - C) 创建 Pull Request
> - D) 删除 worktree (保留分支)
> - E) 返回 autoplan 修订 — 执行中发现了 plan 级别的问题

选 B: 从主 worktree 合并 plan 分支到 main。
选 C: 使用 `gh pr create` 为 plan 分支创建 PR。
选 D: 执行 `git worktree remove <路径>` 但保留分支。

**推荐后续流程 (完成代码变更后):**
> - F) 代码审查 — 调用 /android-code-review 审查代码质量
> - G) QA 测试 — 调用 /android-qa 验证功能正确性
> - H) 更新文档 — 调用 /android-document-release 同步文档
> - I) 全部执行 — 按顺序自动执行 F → G → H

如果用户选择 I (全部执行):
1. 调用 android-code-review 审查当前分支
2. 如果 code-review 通过: 调用 android-qa 进行 QA
3. 如果 QA 通过: 调用 android-document-release 更新文档
4. 任何步骤发现阻塞问题: 中断并报告给用户
选 E: 将执行中遇到的问题标注到 plan 文件中，然后调用
  android-autoplan 重新审查。流程:
  1. 从 `plan_source.ref` 获取原始 plan 文件名 (如 `2026-04-10-auth.md`)
  2. 将问题写入 `docs/plans/<plan-filename>-execution-issues.md`

**execution-issues 文件格式:**

```markdown
# 执行问题报告: <plan-slug>

## 概要
- 执行任务数: X/Y
- 失败任务: Z

## 失败任务详情

### Task N: <title>
**错误类型:** build_error / test_failure / dependency_missing / instruction_unclear
**错误信息:**
\`\`\`
<完整错误输出>
\`\`\`
**已尝试的修复:** <描述>
**建议:** <建议 autoplan 如何调整 plan>
```

  3. 使用 Skill 工具调用 android-autoplan:
     skill: "android-autoplan", args: "review docs/plans/<plan-filename>.md"
  4. autoplan 的 review 模式会自动查找同名
     `<plan-filename>-execution-issues.md` 作为额外输入
  5. autoplan 读取 plan + execution-issues，重新审查并产出修订版 plan
  6. 用户确认修订版后，重新导入 worktree-runner 执行

---

## 多 Worktree 支持

多个 plan 可以同时处于进行中状态，各自在独立的 worktree 中。

### Worktree 管理命令

**列出所有 worktree:**
```bash
git worktree list
```

**检查当前所在的 worktree:**
```bash
git worktree list | grep "$(pwd)"
```

**切换 worktree:**
当用户想要处理另一个进行中的 plan 时，使用 AskUserQuestion 确认，
然后 `cd` 到目标 worktree 的路径。

### 冲突预防

- 每个 plan 获得唯一分支: `plan/<slug>` — slug 由标题和时间戳生成，避免冲突
- 如果分支名冲突，追加递增数字: `plan/auth-login-flow-2`
- 如果两个 plan 修改相同文件，发出警告（检查任务步骤中的文件路径）

---

## 恢复保障

此 skill 设计为可抵御 `/clear`、会话重启和上下文窗口耗尽。恢复机制很简单:
**磁盘上的 `tasks.json` 始终是真相。**

### 恢复原理

1. **每次调用都以相同方式开始:** 从磁盘读取 `tasks.json`
2. **每次状态变更立即写入:** 不批量、不延迟
3. **没有仅存在于内存中的状态:** 不在 `tasks.json` 中的状态不存在

### 恢复场景

**`/clear` 之后:**
```
用户: /android-worktree-runner plan-auth
Skill: → 读取 tasks.json → 找到 plan-auth，任务 2 进行中
       → 进入 worktree → 显示任务 2 状态 → 恢复执行
```

**会话重启后 (Claude Code 关闭后重新打开):**
```
用户: /android-worktree-runner
Skill: → 读取 tasks.json → 展示所有 plan 的当前状态
       → "Plan: 登录流程 [进行中] — 任务 2/3"
       → 提供恢复选项
```

**上下文窗口压缩后:**
```
上下文在任务执行过程中被压缩 → skill 在下次交互时重新读取 tasks.json
→ 状态是最新的 → 无缝继续
```

### 什么会被持久化

| 时机 | 写入 tasks.json 的内容 |
|------|------------------------|
| Plan 导入时 | 包含所有任务的 plan 条目 (状态: pending) |
| 任务开始时 | 任务状态 → in-progress，启动时间戳 |
| 任务完成时 | 任务状态 → completed，commit hash，验证结果，完成时间戳 |
| Plan 完成时 | Plan 状态 → completed，完成时间戳 |
| 验证被跳过时 | 验证字段 → "skipped" |

### 什么不需要持久化

- Plan 文件内容（恢复时从 `plan_source.ref` 重新读取）
- 代码变更（已在 worktree 的 git 工作区中）
- 构建输出（临时的，下次验证时重新运行）

---

## 异常情况处理

| 场景 | 处理方式 |
|------|----------|
| Plan 对应的 worktree 已存在 | 通过 `git worktree list` 检测，提供恢复选项 |
| 分支名已存在 | 分支名后追加 `-2`、`-3` 等 |
| Plan 源文件已被删除 | 发出警告，使用 `tasks.json` 中存储的步骤继续 |
| Plan 源文件已被修改 | 提示变更，提供重新导入选项 |
| 不在 git 仓库中 | 报错: "android-worktree-runner 需要 git 仓库" |
| `tasks.json` 损坏 | 发出警告，提供从 plan 源文件重建的选项 |
| 任务没有步骤 | 视为单个原子任务处理 |
| 提交失败 (没有变更) | 跳过提交，标记任务完成，备注 "无变更" |
| Android 验证超时 (>5 分钟) | 询问用户: 继续等待或跳过 |

---

## Worktree 管理文件 (worktree-info.md)

项目根目录下维护一个 `worktree-info.md` 文件，作为所有 worktree 的**人类可读索引**。
与 `tasks.json`（机器可读的执行状态）互补。

### 文件位置

`$MAIN_WORKTREE/worktree-info.md`（项目根目录，与 `.git` 同级）

### 文件格式

```markdown
# Worktree 索引

> 自动生成于 2026-04-10 | 由 android-worktree-runner 维护

## 进行中

### plan/auth-login-flow
- **worktree:** `.claude/worktrees/plan-20260410-001`
- **创建于:** 2026-04-10
- **基准 commit:** `abc1234`
- **任务:** 登录流程实现 (0/3 已完成)
- **状态:** 进行中 — 任务 1 执行中

### plan/room-database
- **worktree:** `.claude/worktrees/plan-20260410-002`
- **创建于:** 2026-04-10
- **基准 commit:** `abc1234`
- **任务:** Room 数据库搭建 (0/2 已完成)
- **状态:** 待开始

## 已完成

### plan/project-init
- **worktree:** `.claude/worktrees/plan-20260409-001`
- **创建于:** 2026-04-09
- **基准 commit:** `a1b2c3d`
- **任务:** 项目初始化 (3/3 已完成)
- **状态:** 已完成 — 2026-04-10
- **最终 commit:** `f5e4d3c`
```

### 维护规则

1. **创建 worktree 时更新:** Phase 0 步骤 5 创建 worktree 后，将新 plan 添加到
   `worktree-info.md` 的"进行中"部分。
2. **任务完成时更新:** Phase 2 步骤 7 每个任务完成后，更新对应 plan 的任务进度
   `(X/N 已完成)` 和当前状态描述。
3. **Plan 完成时更新:** Phase 3 步骤 2 将 plan 从"进行中"移动到"已完成"部分，
   填入完成时间和最终 commit hash。
4. **文件不存在时自动创建:** 首次创建 worktree 时，如果 `worktree-info.md` 不存在，
   先扫描 `git worktree list` 获取已有的 worktree 列表，创建文件并填入已有条目。
   对于不是由 android-worktree-runner 创建的 worktree，标记为"外部 worktree"。
5. **文件已存在时追加:** 不覆盖已有内容。读取现有文件，在对应部分添加或更新条目。

### 与 tasks.json 的关系

| 文件 | 用途 | 读者 |
|------|------|------|
| `tasks.json` | 执行状态，机器可读 | android-worktree-runner skill |
| `worktree-info.md` | worktree 索引，人类可读 | 开发者、代码审查 |

`tasks.json` 是执行时的唯一真相源。`worktree-info.md` 是它的**派生视图**，
始终从 `tasks.json` 的状态生成内容，不持有独立状态。

---

## 文件结构

```
项目根目录/                           ← 主 worktree
├── worktree-info.md                 ← worktree 索引 (人类可读)
├── .claude/
│   ├── android-worktree-runner/
│   │   └── tasks.json              ← 唯一真相源 (始终在此)
│   └── worktrees/
│       ├── plan-20260410-001/      ← plan 1 的 worktree
│       │   └── (实际的代码变更)
│       ├── plan-20260410-002/      ← plan 2 的 worktree
│       │   └── (实际的代码变更)
│       └── ...
├── docs/
│   └── plans/
│       └── *.md                    ← plan 源文件
└── ...
```

**核心规则:** `tasks.json` 位于主 worktree 的 `.claude/` 目录中。
所有 plan worktree（在 `.claude/worktrees/` 下）读写同一个文件。
没有任何 worktree 持有 `tasks.json` 的副本。
`worktree-info.md` 位于项目根目录，作为所有 worktree 的人类可读索引。

---

## 与其他 Skill 的集成

此 skill 设计为与产出的 plan 的各类 skill 协同工作:

| Plan 来源 | 产出方 | 连接方式 |
|-----------|--------|----------|
| `docs/plans/*.md` | superpowers:writing-plans | 导入时自动检测 |
| `~/.gstack/projects/*/` | gstack:office-hours + autoplan | 导入时自动检测 |
| 内存中的 plan | Claude Code /plan | 从上下文读取 |
| 任意 Markdown | 手动或自定义 skill | 导入时提供路径 |

任何 skill 产出 plan 后，调用 `/android-worktree-runner` 导入并开始执行。
