# Android Skill 流水线

## 流水线概览

```
brainstorm → autoplan → worktree-runner → code-review → qa → ship
                │              │
                │              ├─► tdd (自动调用)
                │              ├─► investigate (阻塞时调用)
                │              └─► benchmark (可选)
                │
                └─► checkpoint (自动保存)
```

## 各 Skill 的 输入/输出契约

### 1. brainstorm
- **输入**: 用户想法 (自然语言)
- **输出**: `docs/thinking/<date>-<slug>.md`
- **下游**: autoplan (读取 thinking 文档)

### 2. autoplan
- **输入**: 需求描述 / thinking 文档路径
- **输出**: `docs/plans/<slug>.md` (结构化 plan, 包含任务列表)
- **下游**: worktree-runner (读取 plan 文件)

### 3. worktree-runner
- **输入**: `docs/plans/<slug>.md`
- **输出**: `tasks.json` (执行状态) + git commits
- **下游**: code-review (读取 diff)

### 4. tdd
- **输入**: 功能描述
- **输出**: 测试文件 + 实现代码
- **调用方**: worktree-runner (自动调用)

### 5. code-review
- **输入**: 当前分支的 diff
- **输出**: `docs/reviews/<branch>-code-review.md`
- **下游**: fix (读取 review 问题列表)

### 6. qa
- **输入**: 当前分支
- **输出**: `docs/reviews/<branch>-qa-report.md`
- **下游**: investigate (QA 发现 bug 时调用)

### 7. investigate
- **输入**: 问题描述 + 可选的 qa-report 路径
- **输出**: `docs/reviews/<branch>-investigate-report.md`
- **下游**: fix (读取调查报告)

### 8. fix
- **输入**: 问题列表 (来自 code-review / investigate)
- **输出**: git commits
- **下游**: qa (重新验证)

### 9. ship
- **输入**: 当前分支 (qa 通过后)
- **输出**: PR merged to main
- **前置条件**: qa-report 中无 BLOCKER

## 状态传递规则

1. **Plan 文件** (`docs/plans/`) 是唯一真相源
2. **tasks.json** (`.claude/android-worktree-runner/tasks.json`) 是执行状态
3. **Review 报告** (`docs/reviews/`) 是质量门禁
4. **checkpoint** (`.claude/android-checkpoint/`) 是跨 session 恢复点

## Skill 调用规则

| 场景 | 调用 skill |
|------|-----------|
| 新想法 | brainstorm → autoplan |
| 有明确需求 | autoplan → worktree-runner |
| 执行中阻塞 | investigate → fix |
| 执行完成 | code-review → qa → ship |
| 跨 session | checkpoint save/restore |
