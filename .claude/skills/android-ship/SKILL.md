---
name: android-ship
description: |
  交付: 范围漂移检测、验证、提交、创建 PR。
---

# Ship

**调用:** `/android-ship`

## Phase 0: 环境

```bash
_R="$(git worktree list | head -1 | awk '{print $1}')"
SHARED_BIN="$_R/.claude/skills/android-shared/bin"
[ ! -d "$SHARED_BIN" ] && SHARED_BIN="$HOME/.claude/skills/android-shared/bin"

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

| 门禁 | 检查 |
|------|------|
| QA | `docs/reviews/${CURRENT_BRANCH}-qa-report.md` 无 BLOCKER |
| code-review | `docs/reviews/${CURRENT_BRANCH}-code-review.md` 无未解决 BLOCKER |
| build | `docs/reviews/${CURRENT_BRANCH}-build-report.md` 构建成功 |
| TDD | tasks.json 中 TDD 任务已执行 |

任一门禁未通过 → AskUserQuestion: 是否继续?

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
