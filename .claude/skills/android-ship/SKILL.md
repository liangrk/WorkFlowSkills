---
name: android-ship
description: |
  Android 交付工作流。范围漂移检测、最终验证、提交、推送、创建 PR。
  在功能开发完成后，执行从 commit 到 PR 的完整交付流程。
  自动检测范围漂移，验证构建和 lint，智能分组提交，生成 PR 描述。
  适用场景: 功能开发完成后交付、创建 PR、发布前最终检查。
invocation: /android-ship
args: [auto]
voice-triggers:
  - "交付"
  - "创建 PR"
  - "推送代码"
  - "发布"
---

# Android Ship

## 概述

从代码完成到 PR 创建的完整交付流水线。六阶段自动化: 状态检测 → 范围漂移检测 →
最终验证 → 智能提交 → 推送 → 创建 PR → 触发文档更新。

**启动时声明:** "我正在使用 android-ship skill。"

**零外部依赖:** 仅使用 Claude Code 原生工具 + git + gh (可选)。

## 调用方式

```bash
/android-ship                  # 交互式执行，逐步确认
/android-ship auto             # 自动执行全部流程，仅在异常时暂停
/android-ship <phase>          # 从指定阶段开始 (0-6)
```

**参数处理:**
- 无参数: 从 Phase 0 开始，每个阶段结束后暂停等待用户确认
- `auto`: 自动执行全部阶段，仅在遇到异常（构建失败、范围漂移、QA BLOCKER）时暂停
- `<phase>`: 直接从指定阶段编号开始。要求之前阶段已通过
  - 例如 `/android-ship 3` 直接进入提交阶段（跳过状态检测、漂移检测、最终验证）

---

## Phase 0: 状态检测

检查工作环境和前置条件，确保可以安全地执行交付流程。

### 步骤 1: 检查 git 仓库

```bash
# 确认在 git 仓库中
if ! git rev-parse --is-inside-work-tree 2>/dev/null; then
  echo "ERROR: 当前不在 git 仓库中"
  exit 1
fi

PROJECT_ROOT=$(git rev-parse --show-toplevel)

# 当前分支
BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Base branch
BASE_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
if [ -z "$BASE_BRANCH" ]; then
  BASE_BRANCH=$(git branch -r | grep -E 'origin/(main|master)' | head -1 | sed 's@.*origin/@@' | tr -d ' ')
fi
if [ -z "$BASE_BRANCH" ]; then
  BASE_BRANCH="main"
fi
```

输出当前状态摘要:

```
仓库: <PROJECT_ROOT>
当前分支: <BRANCH>
基准分支: <BASE_BRANCH>
```

### 步骤 2: 检查未提交变更

```bash
CHANGES=$(git status --short)
if [ -n "$CHANGES" ]; then
  echo "WARNING: 存在未提交变更:"
  echo "$CHANGES"
  # 不退出，Phase 3 会处理这些变更
else
  echo "工作区干净，无未提交变更"
fi
```

### 步骤 3: 检查 worktree 状态

```bash
# 检查是否在 worktree 中
WORKTREE_LIST=$(git worktree list)
WORKTREE_COUNT=$(echo "$WORKTREE_LIST" | wc -l)

if [ "$WORKTREE_COUNT" -gt 1 ]; then
  echo "INFO: 检测到 worktree 环境"
  echo "$WORKTREE_LIST"
  CURRENT_WORKTREE=$(git worktree list | grep -v "bare" | while read -r path _; do
    if [ "$(cd "$path" && pwd)" = "$PROJECT_ROOT" ]; then
      echo "$path"
    fi
  done)
fi
```

### 步骤 4: 检查 tasks.json

```bash
# 查找 tasks.json
TASKS_FILE=$(find "$PROJECT_ROOT/.claude" -name "tasks.json" -path "*/android-worktree-runner/*" 2>/dev/null | head -1)

if [ -n "$TASKS_FILE" ]; then
  echo "INFO: 发现 tasks.json: $TASKS_FILE"

  # 检查是否有未完成的任务
  PENDING_COUNT=$(python3 -c "
import json, sys
with open('$TASKS_FILE') as f:
    data = json.load(f)
pending = 0
total = 0
for plan in data.get('plans', {}).values():
    for task in plan.get('tasks', []):
        total += 1
        if task.get('status') != 'completed':
            pending += 1
print(f'{pending}/{total}')
" 2>/dev/null || echo "PARSE_ERROR")

  if [ "$PENDING_COUNT" != "0/0" ] && echo "$PENDING_COUNT" | grep -qE '^[1-9]'; then
    echo "WARNING: tasks.json 中有未完成的任务 ($PENDING_COUNT)"
  else
    echo "OK: 所有任务已完成 ($PENDING_COUNT)"
  fi
else
  echo "INFO: 未发现 tasks.json，跳过任务检查"
fi
```

### 步骤 5: 确认继续

展示状态摘要，询问用户是否继续。在 `auto` 模式下自动继续。

---

## Phase 1: 范围漂移检测

对比 plan 声明的范围与实际代码变更，检测范围漂移。

### 步骤 1: 查找 plan 文件

```bash
# 查找最近的 plan 文件
PLAN_FILE=$(ls -t docs/plans/*.md 2>/dev/null | head -1)

if [ -z "$PLAN_FILE" ]; then
  # 尝试其他位置
  PLAN_FILE=$(find . -name "*plan*.md" -not -path "*/node_modules/*" 2>/dev/null | head -1)
fi

if [ -z "$PLAN_FILE" ]; then
  echo "INFO: 未找到 plan 文件，跳过范围检测"
  echo "范围检测结果: SKIPPED (无 plan)"
  # 直接进入 Phase 2
fi
```

### 步骤 2: 获取实际变更文件列表

```bash
# 获取相对于 base branch 的所有变更文件
CHANGED_FILES=$(git diff "origin/$BASE_BRANCH"...HEAD --name-only 2>/dev/null)

if [ -z "$CHANGED_FILES" ]; then
  # 如果没有追踪到远程分支，使用本地 base
  CHANGED_FILES=$(git diff "$BASE_BRANCH"...HEAD --name-only 2>/dev/null)
fi

echo "实际变更文件 ($(echo "$CHANGED_FILES" | wc -l) 个):"
echo "$CHANGED_FILES"
```

### 步骤 3: 从 plan 提取预期文件

读取 plan 文件，提取其中提到的文件路径。支持以下格式:
- `创建/修改 <path>` 或 `Create/Modify <path>`
- 代码块中的文件路径（如 `// file: app/src/...`）
- 任务描述中直接引用的文件路径

```bash
# 提取 plan 中提到的文件
PLAN_FILES=$(grep -oE '[a-zA-Z0-9_/.-]+\.(kt|java|xml|gradle|kts|json|md)' "$PLAN_FILE" 2>/dev/null | sort -u || true)
```

### 步骤 4: 对比并分类

将实际变更文件与 plan 声明文件进行对比:

```
范围检测结果:
═══════════════════════════════════════

PLAN 声明: <N> 个文件
实际变更: <M> 个文件

--- SCOPE CREEP (不在 plan 中的变更) ---
<列出文件，每行一个>
或 "无"

--- MISSING (plan 声明但未涉及的文件) ---
<列出文件，每行一个>
或 "无"

结论: [CLEAN / DRIFT DETECTED / REQUIREMENTS MISSING]
```

**分类规则:**
- **CLEAN**: 所有变更文件都在 plan 中，且 plan 中所有文件都已变更
- **DRIFT DETECTED**: 存在 SCOPE CREEP 文件（实际变更不在 plan 中）
- **REQUIREMENTS MISSING**: 存在 MISSING 文件（plan 声明但未涉及）
- 两者同时存在时，显示为 `DRIFT DETECTED + REQUIREMENTS MISSING`

**处理方式:**
- 范围漂移**不阻塞**流程，仅作为信息提示
- 在 `auto` 模式下，漂移检测到时自动记录并继续
- 在交互模式下，展示漂移详情后询问: "范围漂移已检测到，是否继续? [Y/n]"

---

## Phase 2: 最终验证

执行构建和 lint 检查，确保代码质量。

### 步骤 1: 构建 Debug APK

```bash
echo ">>> 执行 assembleDebug..."
BUILD_OUTPUT=$(./gradlew assembleDebug 2>&1 | tail -20)
BUILD_EXIT=$?

echo "$BUILD_OUTPUT"

if [ $BUILD_EXIT -ne 0 ]; then
  echo "ERROR: 构建失败 (exit code: $BUILD_EXIT)"
  echo ""
  echo "构建错误摘要:"
  echo "$BUILD_OUTPUT" | grep -E "ERROR|FAILED|error:" | head -20
  echo ""
  echo ">>> 流程终止: 构建失败，请修复错误后重试"
  exit 1
fi

echo "OK: assembleDebug 通过"
```

### 步骤 2: Lint 检查

```bash
echo ">>> 执行 lintDebug..."
LINT_OUTPUT=$(./gradlew lintDebug 2>&1 | tail -20)
LINT_EXIT=$?

echo "$LINT_OUTPUT"

# 分类 lint 结果
LINT_ERRORS=$(echo "$LINT_OUTPUT" | grep -iE "error|ERROR" | grep -v "0 errors" || true)
LINT_WARNINGS=$(echo "$LINT_OUTPUT" | grep -iE "warning|WARNING" | grep -v "0 warnings" || true)

if [ -n "$LINT_ERRORS" ]; then
  echo "ERROR: Lint 检查发现错误:"
  echo "$LINT_ERRORS" | head -20
  echo ""
  echo ">>> 流程终止: Lint 有错误，请修复后重试"
  exit 1
fi

if [ -n "$LINT_WARNINGS" ]; then
  echo "WARNING: Lint 检查发现警告 (不阻塞):"
  echo "$LINT_WARNINGS" | head -20
else
  echo "OK: lintDebug 通过，无错误无警告"
fi
```

### 步骤 3: 检查 QA 报告

```bash
# 查找当前分支的 QA 报告
QA_REPORT=$(find docs/reviews -name "${BRANCH}-qa-report.md" 2>/dev/null | head -1)

if [ -z "$QA_REPORT" ]; then
  # 模糊匹配
  QA_REPORT=$(find docs/reviews -name "*qa-report*" -newer docs/plans/*.md 2>/dev/null | head -1)
fi

if [ -n "$QA_REPORT" ]; then
  echo "INFO: 发现 QA 报告: $QA_REPORT"

  # 检查是否有未修复的 BLOCKER
  BLOCKERS=$(grep -A 5 "BLOCKER\|severity.*blocker\|严重级别.*阻塞" "$QA_REPORT" 2>/dev/null | grep -v "已修复\|fixed\|resolved" || true)

  if [ -n "$BLOCKERS" ]; then
    echo "WARNING: QA 报告中存在未修复的 BLOCKER:"
    echo "$BLOCKERS" | head -10
    echo ""
    echo "是否继续? 建议先修复 BLOCKER"
    # 交互模式下等待用户确认
    # auto 模式下记录警告并继续
  else
    echo "OK: QA 报告无未修复的 BLOCKER"
  fi
else
  echo "INFO: 未找到 QA 报告，跳过 QA 检查"
fi
```

### 验证结果摘要

```
验证结果:
═══════════════════════════════════════
- assembleDebug: PASSED / FAILED
- lintDebug:     PASSED (N warnings) / FAILED (N errors)
- QA BLOCKER:   NONE / N unresolved
```

---

## Phase 3: Commit（如有未提交变更）

检查工作区状态，将未提交变更智能分组并提交。

### 步骤 1: 检查是否有未提交变更

```bash
UNSTAGED=$(git diff --name-only)
STAGED=$(git diff --cached --name-only)
UNTRACKED=$(git ls-files --others --exclude-standard)

if [ -z "$UNSTAGED" ] && [ -z "$STAGED" ] && [ -z "$UNTRACKED" ]; then
  echo "INFO: 所有变更已提交，跳过 Phase 3"
  # 直接进入 Phase 4
fi
```

### 步骤 2: 分析变更并分组

遍历所有未提交文件，按以下规则分类:

| 分类 | 文件模式 | Commit type |
|------|----------|-------------|
| 新功能 | `**/src/main/**/*.kt`, `**/src/main/**/*.java` (新文件) | `feat` |
| Bug 修复 | 包含 bug fix 关键词的变更 | `fix` |
| 重构 | 仅修改已有文件结构，无功能变更 | `refactor` |
| 测试 | `**/src/test/**`, `**/src/androidTest/**` | `test` |
| 文档 | `*.md`, `docs/**`, `README*` | `docs` |
| 配置 | `*.gradle`, `*.kts`, `*.properties`, `*.json` | `chore` |

**提交顺序:** 基础设施/配置 → 模型/数据层 → 服务层/Repository → UI → 测试 → 文档

### 步骤 3: 生成分组提交

对每个分组执行:

```bash
# 示例: 提交 feat 类变更
git add <feat-files...>
git commit -m "feat: <summary>

<可选: 详细描述变更内容>"
```

**Commit message 格式:**
```
<type>: <summary>

<可选 body，描述变更动机和影响>
```

**规则:**
- `summary` 使用祈使句，不超过 72 个字符
- 每个分组一个 commit
- 如果分组内文件属于同一功能，合并为一个 commit
- 如果变更很少（< 5 个文件），考虑合并为一个 commit

### 步骤 4: 确认提交结果

```
提交摘要:
═══════════════════════════════════════
<commit-hash> feat: 实现 X 功能
<commit-hash> test: 添加 X 单元测试
<commit-hash> docs: 更新 README

共 <N> 个 commit
```

---

## Phase 4: Push

将本地提交推送到远程仓库，支持幂等操作。

### 步骤 1: 幂等检查

```bash
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "origin/$BRANCH" 2>/dev/null)

if [ "$LOCAL" = "$REMOTE" ]; then
  echo "INFO: 本地与远程已同步，跳过推送"
  # 直接进入 Phase 5
else
  echo "INFO: 本地领先远程 $(git rev-list "origin/$BRANCH"..HEAD --count 2>/dev/null || echo '?') 个 commit"
fi
```

### 步骤 2: 执行推送

```bash
echo ">>> 推送 $BRANCH 到 origin..."
PUSH_OUTPUT=$(git push -u origin "$BRANCH" 2>&1)
PUSH_EXIT=$?

if [ $PUSH_EXIT -ne 0 ]; then
  echo "ERROR: 推送失败:"
  echo "$PUSH_OUTPUT"
  echo ""
  echo "常见原因:"
  echo "  - 远程有冲突 → 执行 git pull --rebase 后重试"
  echo "  - 权限不足 → 检查 SSH key 或 token 配置"
  echo "  - 分支被保护 → 联系管理员"
  exit 1
fi

echo "OK: 推送成功"
```

---

## Phase 5: 创建 PR

基于 plan 文件和 git log 生成 PR 描述并创建。

### 步骤 1: 检查 gh CLI

```bash
if ! command -v gh &>/dev/null; then
  echo "WARNING: 未安装 gh CLI，跳过 PR 创建"
  echo "安装指南: https://cli.github.com/"
  echo "安装后执行: gh pr create --title '...' --body '...'"
  exit 0
fi
```

### 步骤 2: 检查 PR 是否已存在

```bash
EXISTING_PR=$(gh pr list --head "$BRANCH" --json number,title,url --jq '.[0]' 2>/dev/null)

if [ -n "$EXISTING_PR" ] && [ "$EXISTING_PR" != "null" ]; then
  PR_NUMBER=$(echo "$EXISTING_PR" | python3 -c "import json,sys; print(json.load(sys.stdin)['number'])" 2>/dev/null)
  PR_URL=$(echo "$EXISTING_PR" | python3 -c "import json,sys; print(json.load(sys.stdin)['url'])" 2>/dev/null)
  echo "INFO: PR 已存在 (#$PR_NUMBER)，将更新 PR body"
  # 后续使用 gh pr edit $PR_NUMBER --body "..." 而非 gh pr create
fi
```

### 步骤 3: 生成 PR 标题

从 plan 文件提取标题:

```bash
# 从 plan 文件提取标题
if [ -n "$PLAN_FILE" ]; then
  PR_TITLE=$(head -5 "$PLAN_FILE" | grep -E "^#" | head -1 | sed 's/^#*\s*//')
fi

# 如果未找到，从 git log 生成
if [ -z "$PR_TITLE" ]; then
  PR_TITLE=$(git log "origin/$BASE_BRANCH"...HEAD --oneline | head -5 | \
    sed 's/^[a-f0-9]*\s*//' | tr '\n' ', ' | sed 's/, $//')
  PR_TITLE="feat: $PR_TITLE"
fi

# 标题不超过 72 字符
PR_TITLE=$(echo "$PR_TITLE" | head -c 72)
```

### 步骤 4: 生成 PR Body

```bash
# 从 git log 生成变更摘要
CHANGE_SUMMARY=$(git log "origin/$BASE_BRANCH"...HEAD --pretty=format:"- %s" 2>/dev/null || \
  git log "$BASE_BRANCH"...HEAD --pretty=format:"- %s" 2>/dev/null)

# 从 tasks.json 读取任务完成情况
TASK_COMPLETION="N/A"
if [ -n "$TASKS_FILE" ]; then
  TASK_COMPLETION=$(python3 -c "
import json
with open('$TASKS_FILE') as f:
    data = json.load(f)
total = completed = 0
for plan in data.get('plans', {}).values():
    for task in plan.get('tasks', []):
        total += 1
        if task.get('status') == 'completed':
            completed += 1
print(f'{completed}/{total}')
" 2>/dev/null || echo "N/A")
fi

# 从 QA 报告读取摘要
QA_SUMMARY="未执行 QA"
if [ -n "$QA_REPORT" ]; then
  QA_SUMMARY=$(grep -E "总结|Summary|结论" -A 10 "$QA_REPORT" 2>/dev/null | head -10 || echo "见 QA 报告")
fi

# 范围检测结果
SCOPE_STATUS="${SCOPE_RESULT:-CLEAN}"
```

### 步骤 5: 创建或更新 PR

```bash
PR_BODY=$(cat <<'BODY_EOF'
## Summary
<CHANGE_SUMMARY>

## Scope Check
<SCOPE_STATUS>

## Plan Completion
<范围: TASK_COMPLETION tasks completed>

## QA Results
<QA_SUMMARY>

## Verification
- [x] assembleDebug passed
- [x] lintDebug passed
BODY_EOF
)

if [ -n "$PR_NUMBER" ]; then
  # 更新已有 PR
  gh pr edit "$PR_NUMBER" --body "$PR_BODY"
  echo "OK: PR 已更新: $PR_URL"
else
  # 创建新 PR
  gh pr create \
    --base "$BASE_BRANCH" \
    --title "$PR_TITLE" \
    --body "$PR_BODY"
  echo "OK: PR 已创建"
fi
```

### 步骤 6: 输出 PR 信息

```
PR 创建成功:
═══════════════════════════════════════
URL:    <PR_URL>
分支:   <BRANCH> → <BASE_BRANCH>
标题:   <PR_TITLE>
```

---

## Phase 6: 触发文档更新

在 PR 创建成功后，自动触发文档更新流程。

### 步骤 1: 调用 android-document-release

使用 Skill 工具调用 `android-document-release` skill:

```
调用 Skill: android-document-release
```

该 skill 会:
- 分析当前分支的代码变更
- 检测需要更新的文档（README、CHANGELOG、CLAUDE.md、API 文档）
- 生成变更建议
- 经用户确认后写入

### 步骤 2: 文档更新完成

文档更新完成后，如果产生新的 commit，自动追加推送:

```bash
# 检查是否有新的未推送 commit
NEW_LOCAL=$(git rev-parse HEAD)
NEW_REMOTE=$(git rev-parse "origin/$BRANCH" 2>/dev/null)

if [ "$NEW_LOCAL" != "$NEW_REMOTE" ]; then
  echo "INFO: 文档更新产生新 commit，追加推送..."
  git push origin "$BRANCH"
fi
```

---

## 异常处理

| 场景 | 处理方式 |
|------|----------|
| 不在 git 仓库中 | 报错退出，提示 `git init` |
| 构建 (assembleDebug) 失败 | 停止流程，报告错误详情 |
| Lint 有 ERROR | 停止流程，报告错误详情 |
| Lint 有 WARNING | 报告警告，不阻塞流程 |
| QA 报告有未修复 BLOCKER | 警告提示，交互模式下等待确认，auto 模式记录并继续 |
| PR 已存在 | 更新 PR body，不重复创建 |
| 未安装 gh CLI | 跳过 PR 创建，提示安装方法 |
| 推送失败 (冲突) | 报告错误，建议 `git pull --rebase` |
| 推送失败 (权限) | 报告错误，提示检查认证 |
| tasks.json 中有未完成任务 | 警告提示，不阻塞 |
| plan 文件不存在 | 跳过范围检测，记录 SKIPPED |
| 未提交变更中有 .env 或密钥文件 | 警告: "检测到可能的敏感文件，请确认是否应提交" |

---

## 产出

### 终端输出: Ship 摘要

流程完成后，输出完整摘要:

```
Ship 完成
═══════════════════════════════════════

分支:     <BRANCH> → <BASE_BRANCH>
范围检测: <CLEAN / DRIFT DETECTED / SKIPPED>
验证:     assembleDebug PASSED | lintDebug PASSED
提交:     <N> commits
PR:       <PR_URL> (或 "未创建: <原因>")
文档更新: <已执行 / 已跳过>
```

### 文件产出

无额外文件产出。所有变更通过 git commit 和 PR 管理。
