# Android Skill 流水线

## 流水线概览

```
brainstorm → autoplan → worktree-runner → code-review → qa → build → ship
    │              │              │                │           │        │       │
    │              │              ├─► tdd          │           │        │       │
    │              │              ├─► investigate  │           │        │       │
    │              │              └─► benchmark    │           │        │       │
    │              │                               │           │        │       │
    ├─► dump (UI分析)                              ├─► dump    │        │       │
    │                                              │           │        │       │
    └─► checkpoint (自动保存)                      └───────────┴────────┴───────┘
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

### 10. build
- **输入**: 当前分支
- **输出**: Release APK/AAB + 构建报告
- **前置条件**: qa 通过 + code-review 通过

### 11. dump
- **输入**: 目标 App 包名 (可自动检测)
- **输出**: UI 层次 XML + analysis.json + tree_view.html
- **下游**: design-review (UI 分析), qa (UI 验证)

## 状态传递规则

1. **Plan 文件** (`docs/plans/`) 是唯一真相源
2. **tasks.json** (`.claude/android-worktree-runner/tasks.json`) 是执行状态
3. **Review 报告** (`docs/reviews/`) 是质量门禁
4. **checkpoint** (`.claude/android-checkpoint/`) 是跨 session 恢复点

## 上下文继承机制

每个 skill 启动时,自动扫描并加载上游产出物:

```
brainstorm → docs/thinking/*.md
     ↓ 继承
autoplan 自动扫描最近 24h thinking 文档,提取需求/约束/假设
     ↓ 继承 (PRD + 任务 + 验收标准)
worktree-runner 从 plan 文件读取 PRD,执行时验证 AC 覆盖度
     ↓ 继承 (diff + review 问题)
code-review 读取变更范围,产出审查报告
     ↓ 继承 (审查问题列表)
qa 读取变更范围 + PRD,执行分层验证
```

**继承规则:**

| 上游 → 下游 | 继承内容 | 查找路径 |
|------------|---------|---------|
| brainstorm → autoplan | 需求/约束/假设/讨论结论 | `docs/thinking/*.md` (最近 7 天, 主题匹配) |
| autoplan → worktree-runner | PRD (FR/AC) + 任务树 + TDD 标注 | `docs/plans/*.md` + `plan-status.json` |
| worktree-runner → code-review | 变更范围 + tasks.json 执行状态 | `git diff` + `tasks.json` |
| code-review → qa | 审查问题列表 (BLOCKER/WARNING) | `docs/reviews/*-code-review.md` (最近 7 天) |
| qa → investigate | bug 列表 + 复现步骤 | `docs/reviews/*-qa-report.md` (最近 7 天) |
| investigate → fix | 根因分析 + 修复方案 | `docs/reviews/*-investigate-report.md` |
| qa/code-review → build | 验证通过的功能列表 | `docs/reviews/*-qa-report.md` + `*-code-review.md` |
| dump → design-review | UI 层次结构 + 元素列表 | `android-dumps/*/analysis.json` |

**匹配规则:**
- brainstorm → autoplan: 主题关键词匹配时自动加载,不匹配则询问
- 其他继承: 自动加载最近 7 天内的上游产出
- 如果上游产出为空: 从用户当前描述中提取,不阻塞流程

## Skill 调用规则

| 场景 | 调用 skill |
|------|-----------|
| 新想法 | brainstorm → autoplan |
| 有明确需求 | autoplan → worktree-runner |
| 执行中阻塞 | investigate → fix |
| 执行完成 | code-review → qa → ship |
| 跨 session | checkpoint save/restore |
