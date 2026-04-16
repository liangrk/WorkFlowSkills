---
name: android-ship
description: |
  交付: 范围漂移检测、验证、提交、创建 PR。
---

# Ship

**调用:** `/android-ship`

## Phase 0: 环境

```bash
SHARED_BIN=$(bash android-resolve-path 2>/dev/null || true)
# SHARED_BIN resolved dynamically
# fallback handled

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
BASE_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@.*/@@' || echo main)
```

## Phase 1: 范围漂移检测

```bash
# Plan 预期范围
PLAN_FILE=$(find docs/plans -name "*.md" -mmin -10080 2>/dev/null | sort -r | head -1)

# 实际变更
CHANGED=$(git diff --name-only "$BASE_BRANCH"...HEAD 2>/dev/null)

# 对比: 计划 vs 实际
# 预期外文件 → 漂移警告
# 缺失文件 → 未完成警告
```

## Phase 2: 质量门禁

### 门禁检查流程

```bash
# 1. code-review BLOCKER 检查 (必须解析文件内容)
REVIEW_FILE="docs/reviews/${CURRENT_BRANCH}-code-review.md"
if [ -f "$REVIEW_FILE" ]; then
  # 解析 BLOCKER 数量 (检查是否已标记为 resolved)
  BLOCKER_COUNT=$(grep -c "🔴 BLOCKER" "$REVIEW_FILE" 2>/dev/null || echo 0)
  RESOLVED_COUNT=$(grep -c "🔴 BLOCKER.*resolved\|🔴 BLOCKER.*已修复\|BLOCKER.*✅" "$REVIEW_FILE" 2>/dev/null || echo 0)
  UNRESOLVED_BLOCKER=$((BLOCKER_COUNT - RESOLVED_COUNT))
  REVIEW_MISSING=0
else
  # H1 修复: 审查文件缺失视为严重风险
  UNRESOLVED_BLOCKER=1
  REVIEW_MISSING=1
fi

# 2. TDD 覆盖率检查 (M5 修复)
TDD_STATUS=$(python3 -c "
import json, sys
try:
    tasks = json.load(open('.claude/android-worktree-runner/tasks.json'))
    # 检查是否有任务处于 completed-with-tdd-issues 状态
    issues = sum(1 for t in tasks if t.get('status') == 'completed-with-tdd-issues')
    print('has_issues' if issues > 0 else 'ok')
except: print('ok')
" 2>/dev/null || echo "ok")

# 3. QA BLOCKER 检查
QA_FILE="docs/reviews/${CURRENT_BRANCH}-qa-report.md"
QA_BLOCKER=$([ -f "$QA_FILE" ] && grep -c "🔴 BLOCKER" "$QA_FILE" 2>/dev/null || echo 0)
```

### 门禁决策表

| 门禁 | 条件 | 行为 |
|------|------|------|
| code-review | `UNRESOLVED_BLOCKER > 0` | 🔴 阻塞 (若 `REVIEW_MISSING=1` 则提示未做审查) |
| QA | `QA_BLOCKER > 0` | 🔴 阻塞，提示修复或记录豁免决策 |
| build | 构建失败 | 🔴 阻塞 |
| TDD | `TDD_STATUS = has_issues` | 🟡 警告，提醒存在覆盖率不足的任务，需用户确认 |

### 阻塞处理

```bash
if [ $UNRESOLVED_BLOCKER -gt 0 ] || [ $QA_BLOCKER -gt 0 ] || [ "$TDD_STATUS" = "has_issues" ]; then
  MSG="质量门禁未通过:"
  [ $REVIEW_MISSING -eq 1 ] && MSG="$MSG\n- 🔴 缺少代码审查文件"
  [ $UNRESOLVED_BLOCKER -gt 0 ] && [ $REVIEW_MISSING -eq 0 ] && MSG="$MSG\n- 🔴 未解决 BLOCKER: $UNRESOLVED_BLOCKER"
  [ $QA_BLOCKER -gt 0 ] && MSG="$MSG\n- 🔴 QA BLOCKER: $QA_BLOCKER"
  [ "$TDD_STATUS" = "has_issues" ] && MSG="$MSG\n- 🟡 部分任务 TDD 覆盖率未达标"

  AskUserQuestion: "$MSG\n\n是否继续?"
  - A) 修复后再提交 (推荐)
  - B) 记录豁免决策并继续 (需说明原因)
  - C) 取消

  若选 B:
    写入 docs/reviews/${CURRENT_BRANCH}-ship-decision.md:
      决策时间: $(date -Iseconds)
      未解决 BLOCKER: $UNRESOLVED_BLOCKER
      QA BLOCKER: $QA_BLOCKER
      豁免原因: <用户输入>
      决策者: <用户名>
fi
```

## Phase 3: 提交 + PR

```bash
# 确认提交
git add -A
git commit -m "feat: <描述>

Co-Authored-By: Claude <noreply@anthropic.com>"

# 推送 + PR
git push origin "$CURRENT_BRANCH"
gh pr create \
  --base "$BASE_BRANCH" \
  --title "feat: <描述>" \
  --body "<PR 描述>"
```

## Phase 4: 合并

AskUserQuestion:
- A) 合并 PR (squash merge)
- B) 保留 PR, 稍后合并
- C) 关闭 PR

若 A:
```bash
gh pr merge --squash --delete-branch
git checkout "$BASE_BRANCH"
git pull
```

## Phase 5: 清理

- 清理 worktree
- 清理 checkpoint
- 更新 tasks.json 状态
- 推荐 /android-document-release
