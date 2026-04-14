---
name: android-document-release
description: |
  文档同步更新。检测变更影响, 更新 README/CHANGELOG/CLAUDE.md。
---

# Document Release

**调用:** `/android-document-release`

## Phase 0: 变更分析

```bash
SHARED_BIN=$(bash android-resolve-path 2>/dev/null || true)
# SHARED_BIN resolved dynamically
# fallback handled

# 最近的变更
CHANGES=$(git diff --name-only HEAD~10..HEAD 2>/dev/null)
# Plan 执行记录
MAIN_WORKTREE=$(git worktree list 2>/dev/null | head -1 | awk '{print $1}')
TASKS="$MAIN_WORKTREE/.claude/android-worktree-runner/tasks.json"
# Review 报告
REVIEWS=$(find docs/reviews -name "*.md" -mmin -10080 2>/dev/null | sort -r | head -5)
```

## Phase 1: 影响检测

| 变更类型 | 影响文档 |
|---------|---------|
| 新功能 | README (功能列表), CHANGELOG |
| API 变更 | README (API 文档) |
| 依赖变更 | README (依赖说明) |
| 配置变更 | CLAUDE.md, README |
| bug 修复 | CHANGELOG |

## Phase 2: 文档更新

对每个受影响的文档:

```markdown
# CHANGELOG.md 更新
## [Unreleased]
### Added
- <新功能>
### Changed
- <变更>
### Fixed
- <修复>
```

AskUserQuestion 展示 diff 格式的变更建议:
- A) 接受并写入
- B) 修改后接受
- C) 跳过

## Phase 3: 产出

```
docs/reviews/<branch>-doc-update.md:
  - 受影响的文档列表
  - 每个文档的变更摘要
  - 跳过的项目及原因
```
