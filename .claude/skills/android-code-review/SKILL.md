---
name: android-code-review
description: |
  Android 代码审查: 七维度 (架构/命名/生命周期/线程/Android特有/可测试性/安全)。
  适用场景: 代码提交前审查、PR 审查。
---

# Android Code Review

**调用:** `/android-code-review` | `<branch>`

## Phase 0: 变更收集

```bash
BASE=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@.*/@@' || echo main)
CHANGED=$(git diff --name-only "$BASE"...HEAD | grep -E '\.(kt|java|xml|gradle|kts)$')
DIFF=$(git diff "$BASE"...HEAD)
```

## Phase 1: 七维度审查 (subagent)

| 维度 | 检查项 |
|------|--------|
| **架构** | 分层方向、DI、模块依赖 |
| **命名** | Kotlin 惯例、Android 惯例 |
| **生命周期** | Context 泄漏、Listener 取消、Coroutine scope |
| **线程** | 主线程 IO、UI 线程安全、Compose 重组 |
| **Android 特有** | 资源泄漏、Bitmap、数据库事务、权限 |
| **可测试性** | 依赖可 mock、硬编码检测 |
| **安全** | 敏感数据、权限、网络安全、ProGuard |

每个维度: 通过 / 问题列表 + 严重程度

## Phase 2: 汇总

```
docs/reviews/<branch>-code-review.md:
  摘要: 🔴 BLOCKER N | 🟠 WARNING N | 🟡 INFO N
  按维度组织问题
  修复建议
```

## Capture Learnings

```bash
bash "$SHARED_BIN/android-learnings-log" '{"skill":"code-review","type":"pitfall","key":"KEY","insight":"INSIGHT","confidence":8,"source":"observed","files":[]}'
```
