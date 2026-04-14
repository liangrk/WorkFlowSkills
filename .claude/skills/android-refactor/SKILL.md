---
name: android-refactor
description: |
  PRD 锚定重构。三档 scope (micro/medium/macro) 自动检测。
---

# Refactor

**调用:** `/android-refactor <目标描述>`

## Phase 0: 环境

```bash
_R="$(git worktree list | head -1 | awk '{print $1}')"
SHARED_BIN="$_R/.claude/skills/android-shared/bin"
[ ! -d "$SHARED_BIN" ] && SHARED_BIN="$HOME/.claude/skills/android-shared/bin"
bash "$SHARED_BIN/android-learnings-bootstrap" 2>/dev/null || true
```

## Phase 1: Scope 选择

| Scope | 范围 | 示例 |
|-------|------|------|
| micro | 单文件/函数 | 提取方法、重命名、简化逻辑 |
| medium | 单模块 | 分层重构、依赖重组 |
| macro | 多模块 | 架构调整、模块拆分 |

AskUserQuestion 选择 scope。

## Phase 2: 变更分析

```bash
# 当前代码扫描
# 识别: 重复代码 / 过长函数 / 循环依赖 / 硬编码
# 对比 PRD 需求, 确认当前实现是否偏离
```

## Phase 3: 执行

```
1. 创建 worktree: git worktree add ... -b refactor/<slug>
2. 按 scope 执行重构
3. 验证: ./gradlew build lintDebug testDebugUnitTest
4. 提交
```

## Phase 4: 验证

- 功能不变 (测试通过)
- 代码质量提升 (指标对比)
- PRD 需求仍满足
