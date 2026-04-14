---
name: android-fix
description: |
  Use when there are known fix items (from brainstorm, code-review, qa, investigate,
  or manual list) that need to be implemented. Classifies fixes by severity, groups
  related items, analyzes dependencies, generates a worktree-runner-compatible plan,
  and hands off to worktree-runner for execution. Does NOT diagnose problems — use
  android-investigate or android-brainstorm for that.
voice-triggers:
  - "修复"
  - "实施修复"
  - "fix findings"
  - "修复结论"
  - "修复问题"
invocation: /android-fix
args: [<file>] [--resume <plan-file>]
---

# Android Fix

## 概述

将排查结论转化为可执行的修复计划。输入已知修复项，输出 worktree-runner 可导入的 plan 文件。

**启动时声明:** "我正在使用 android-fix skill。"

**零外部依赖:** 仅使用 Claude Code 原生工具 + git + worktree-runner。

**不是诊断工具:** 本 skill 不排查问题，只实施已知修复。排查请用 `android-investigate` 或 `android-brainstorm`。

## 调用方式

```bash
/android-fix                          # 从对话上下文提取修复项
/android-fix <file>                    # 从文件读取修复项 (markdown/txt)
/android-fix --resume <plan-file>     # 恢复已有修复计划，继续执行
```

**参数处理:**

| 参数 | 行为 |
|------|------|
| 无参数 | 从当前对话上下文中提取修复项 |
| `<file>` | 读取指定文件中的修复项 |
| `--resume` | 跳过 Phase 0-4，直接调用 worktree-runner |

---

## Phase 0: 输入检测 + 早期退出

**所有模式共享的前置步骤。**

### 步骤 1: 获取修复项

**从对话上下文获取 (无参数):**

扫描当前对话中的修复项。修复项的判定标准 — 必须同时满足:
1. **有具体文件路径** (如 `.claude/skills/android-tdd/SKILL.md`)
2. **有具体变更描述** (如 "将 git add -A 替换为 git add")

仅满足其一的情况视为分析/发现，不是修复项:
- 只有文件路径没有变更描述 → 需要进一步排查
- 只有问题描述没有文件路径 → 需要定位到具体文件

**从文件获取 (<file>):**

```bash
if [ ! -f "$1" ]; then
  echo "错误: 文件不存在: $1"
  exit 1
fi
cat "$1"
```

### 步骤 2: 早期退出检查

统计提取到的修复项数量。

```
提取结果:
- 可执行修复项: N 个
- 仅分析项 (无文件路径或无变更描述): M 个
```

**早期退出条件 (满足任一即退出):**

| 条件 | 处理 |
|------|------|
| 修复项 = 0 | 提示: "未检测到可执行的修复项。建议先使用 /android-investigate 或 /android-brainstorm 排查问题。" 退出 |
| 修复项 = 1 且变更极小 | 提示: "仅 1 个修复项，建议直接手动修复而非启动 worktree。" 询问是否继续 |

修复项 >= 2 → 继续 Phase 1。

---

## Phase 1: 确认修复项

将提取到的修复项展示给用户确认。

### 步骤 1: 展示修复项清单

```
=== 修复项清单 ===

#1  [P0] .claude/skills/android-worktree-runner/SKILL.md
    替换 git add -A 为 git add (显式文件列表)

#2  [P1] .claude/skills/android-shared/bin/android-scan-project.py
    增加 schema_version 字段

#3  [P1] .claude/skills/android-shared/bin/android-detect-env
    统一检测逻辑与 scan-project 一致

...
```

如果输入中已有优先级标记 (P0/P1/P2)，保留。否则在 Phase 2 中分类。

### 步骤 2: 用户确认

使用 AskUserQuestion:
> 以上修复项是否正确? 可以增删改。
> - A) 确认，继续
> - B) 调整 (说明需要修改的内容)
> - C) 取消

---

## Phase 2: 分类 + 优先级 + 分组

### 步骤 1: 分类

对每个修复项分类:

| 分类 | 判定标准 | 示例 |
|------|----------|------|
| security | 涉及数据泄漏、敏感文件、权限问题 | git add -A 可能提交 .env |
| reliability | 修复后可避免运行时崩溃或流程中断 | schema version 防止解析失败 |
| consistency | 统一格式、消除重复逻辑 | detect-env 与 scan-project 对齐 |
| performance | 优化执行速度或资源使用 | learnings GC 减少启动时间 |
| cosmetic | 代码风格、注释、文档 | 步骤编号修正 |

### 步骤 2: 优先级

| 优先级 | 分类范围 | 说明 |
|--------|----------|------|
| P0 | security | 数据泄漏风险，必须立即修复 |
| P1 | reliability | 修复后可避免工作流中断 |
| P2 | consistency + performance | 改善质量但不阻塞工作流 |
| P3 | cosmetic | 美观改进，最低优先级 |

### 步骤 3: 分组合并

将同一文件或强相关的修复项合并为一个 task:

**合并规则:**
- 同一文件的多个修复 → 一个 task，步骤按顺序排列
- 有因果关系的修复 (A 的修复依赖 B) → 一个 task，B 为前置步骤
- 无关文件的修复 → 独立 task

合并后输出:
```
=== 任务分组 ===

Task 1: [P0] worktree-runner + tdd + qa + refactor — git add -A 安全修复
  - 替换所有 git add -A 为显式文件列表
  - 添加敏感文件排除 (.env, *.jks, local.properties)
  - 涉及文件: 5 个 SKILL.md

Task 2: [P1] android-scan-project.py — 增加 schema version
  - 输出增加 "schema_version": 1
  - 涉及文件: 1 个 bin 脚本

Task 3: [P1] android-detect-env — 统一检测逻辑
  - 与 scan-project 使用相同的检测入口
  - 涉及文件: 1 个 bin 脚本
```

---

## Phase 3: 依赖分析

### 步骤 1: 确定依赖关系

分析任务间的依赖:

```
依赖分析:
- Task 2 (schema version) 应在 Task 3 (统一检测) 之前
  → Task 3 depends_on Task 2
- Task 1 (git add -A) 独立于 Task 2, 3
  → 无依赖
```

### 步骤 2: 确定执行模式

| 情况 | 执行模式 | 原因 |
|------|----------|------|
| 所有任务无依赖 | parallel | 可并行执行，最快 |
| 部分任务有依赖 | parallel | worktree-runner 的波次并行处理依赖 |
| 所有任务有依赖链 | serial | 必须按顺序执行 |

---

## Phase 4: 生成 plan 文件

### 步骤 1: 生成 plan

写入 `docs/plans/fix-<slug>-<timestamp>.md`:

```bash
PLAN_FILE="docs/plans/fix-$(date +%Y%m%d-%H%M%S).md"
```

**Plan 文件格式 (worktree-runner 兼容):**

```markdown
# fix: <修复主题摘要>

## 概述
<修复背景: 来自哪个 skill/排查, 修复了什么问题>

## Tasks

### Task 1: <任务标题>
**优先级:** P0 | **分类:** security
**涉及文件:** <文件列表>

**步骤:**
1. <具体修复步骤>
2. <具体修复步骤>

### Task 2: <任务标题>
**优先级:** P1 | **分类:** reliability
**依赖:** Task 1
**涉及文件:** <文件列表>

**步骤:**
1. <具体修复步骤>
```

### 步骤 2: 验证 plan 文件

```bash
if [ -f "$PLAN_FILE" ]; then
  echo "Plan 文件已生成: $PLAN_FILE"
  wc -l < "$PLAN_FILE"
else
  echo "错误: Plan 文件生成失败"
  exit 1
fi
```

---

## Phase 5: 交接 worktree-runner

### 步骤 1: 调用 worktree-runner

使用 Skill 工具调用 `android-worktree-runner`:

```
调用 Skill: android-worktree-runner
参数: import $PLAN_FILE
```

worktree-runner 接管后:
1. 解析 plan 文件
2. 创建 worktree
3. 逐任务执行修复
4. 每个任务完成后执行验证 (构建 + lint + 测试)
5. 提交修复

### 步骤 2: 修复完成后

worktree-runner 完成后，建议:

```
修复完成。建议下一步:
- /android-ship        # 提交 + 推送 + 创建 PR
- /android-qa         # 验证修复无回归
- /android-code-review # 审查修复质量
```

---

## 与其他 Skill 的衔接

```
brainstorm / investigate / code-review / qa / coverage
    │
    ▼ (产出修复项)
android-fix (提取 → 分类 → 分组 → 生成 plan)
    │
    ▼ (交接 plan 文件)
android-worktree-runner import (执行修复)
    │
    ▼ (修复完成)
android-ship / android-qa / android-code-review
```

| Skill | 关系 | 说明 |
|-------|------|------|
| android-investigate | 上游 | investigate 排查后产出修复项，android-fix 执行修复 |
| android-brainstorm | 上游 | brainstorm 发散分析后产出修复建议 |
| android-code-review | 上游 | code-review 发现 BLOCKER/WARNING 后产出修复项 |
| android-qa | 上游 | qa 发现 bug 后产出修复项 |
| android-worktree-runner | 下游 | android-fix 生成 plan，worktree-runner 执行 |
| android-ship | 下游 | 修复完成后通过 ship 提交 |
| android-tdd | 并行 | 修复涉及逻辑变更时，可配合 tdd 补测试 |

---

## 异常情况处理

| 场景 | 处理方式 |
|------|----------|
| 无修复项 (纯分析) | 早期退出，建议用 investigate/brainstorm 先排查 |
| 仅 1 个小修复 | 提示直接手动修复，无需启动 worktree |
| 修复项无文件路径 | 标记为"需定位"，提示用户提供文件路径 |
| plan 文件生成失败 | 报错退出 |
| worktree-runner 执行失败 | worktree-runner 自身处理 (blocked/failed 状态) |
| 不在 git 仓库中 | 报错: "需要 git 仓库" |
| 文件参数不存在 | 报错: "文件不存在" |

## 修复完成后

修复完成后,推荐运行 `/android-qa` 重新验证,确保修复没有引入回归:
```
修复完成 → /android-qa → 验证通过 → /android-ship 提交
```
