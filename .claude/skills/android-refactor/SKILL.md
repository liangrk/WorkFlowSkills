---
name: android-refactor
description: |
  Android 重构 skill。PRD 锚定 + 三档 scope 自动检测。
  确保重构不破坏需求，支持 micro/medium/macro 三档执行策略。
  Micro: 单文件直接改。Medium: worktree 隔离分步验证。
  Macro: 生成迁移 plan → worktree-runner 执行。
invocation: /android-refactor <目标描述>
args: [重构目标描述]
voice-triggers:
  - "重构"
  - "提取"
  - "拆分"
  - "迁移"
  - "优化结构"
---

# Android Refactor

## 概述

PRD 锚定 → Scope 检测 → 安全网评估 → 分档执行 → PRD 回归验证。

核心原则: **重构改代码结构，不改产品行为。** 每一步都可验证、可回滚。

**启动时声明:** "我正在使用 android-refactor skill。"

**零外部依赖:** 仅使用 Claude Code 原生工具 (Read、Write、Edit、Grep、Glob、Bash)
和 android-shared/bin/ 下的辅助脚本。不依赖 gstack、browse、Codex、Figma MCP。

## 调用方式

```bash
/android-refactor <目标描述>           # 指定重构目标
/android-refactor                      # 交互式: 引导输入重构目标
```

**参数处理:**
- 有参数: 直接进入 Phase 0，以参数为重构目标描述
- 无参数: 引导用户输入重构目标后进入 Phase 0

## 核心原则

1. **PRD 不变是硬约束** — 重构改代码结构，不改产品行为
2. **测试是安全网** — 没有测试的重构是在走钢丝
3. **小步前进** — 每步可验证、可回滚
4. **显式确认** — 每步完成展示变更，用户确认后继续

---

## Phase 0: PRD 锚定 + Scope 检测 + 安全网评估

### 前置: 加载历史学习记录

```bash
_R="$(git worktree list | head -1 | awk '{print $1}')"
SHARED_BIN="$_R/.claude/skills/android-shared/bin"
[ ! -d "$SHARED_BIN" ] && SHARED_BIN="$HOME/.claude/skills/android-shared/bin"
bash "$SHARED_BIN/android-learnings-bootstrap" 2>/dev/null || true
```

```bash
_R="$(git worktree list | head -1 | awk '{print $1}')"
SHARED_BIN="$_R/.claude/skills/android-shared/bin"
[ ! -d "$SHARED_BIN" ] && SHARED_BIN="$HOME/.claude/skills/android-shared/bin"
LEARNINGS=$(bash "$SHARED_BIN/android-learnings-search" --type pattern --limit 5 2>/dev/null || true)
if [ -n "$LEARNINGS" ]; then
  echo "=== 相关学习记录 ==="
  echo "$LEARNINGS"
fi
```

### 前置: 环境检测

```bash
_R="$(git worktree list | head -1 | awk '{print $1}')"
SHARED_BIN="$_R/.claude/skills/android-shared/bin"
[ ! -d "$SHARED_BIN" ] && SHARED_BIN="$HOME/.claude/skills/android-shared/bin"
ENV_JSON=$(bash "$SHARED_BIN/android-detect-env" 2>/dev/null || true)
echo "$ENV_JSON"
```

### 步骤 1: PRD 加载

```bash
# 查找关联 plan 文件
grep -l "^## PRD$" docs/plans/*.md 2>/dev/null
```

**若找到 PRD:**
- 解析功能需求 (FR-N)、验收标准 (AC-N)、明确不做列表
- 输出: "[refactor] 已加载 PRD: X 条功能需求, Y 条验收标准"

**若未找到 PRD:**
- 输出: "[refactor] 未找到 PRD，降级为测试驱动验证模式"
- 使用 AskUserQuestion:
  - A) 继续 (仅依赖测试验证)
  - B) 先用 /android-autoplan 生成 PRD

### 步骤 2: 需求-代码映射

根据重构目标描述，分析受影响的代码范围，建立需求到代码的映射。

```bash
# 根据目标描述搜索相关文件
# 例如: 目标为 "拆分 LoginActivity" 则搜索 LoginActivity 相关类
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
```

对每条 PRD 需求:
1. 定位当前实现文件/类/方法
2. 标记重构影响范围 (将被改动 / 不受影响)
3. 生成"需求保护清单"

输出格式:
```
需求保护清单:
FR-1: 用户登录 -> LoginActivity.kt, LoginViewModel.kt, AuthRepository.kt [将被改动]
FR-2: 错误提示 -> LoginActivity.kt [将被改动]
FR-3: 记住我 -> AuthRepository.kt [不受影响]
NFR-1: 响应 <500ms -> AuthRepository.kt [将被改动]
明确不做: 第三方登录 [不受影响]
```

**无 PRD 降级模式:** 跳过需求保护清单，直接进入安全网评估。

### 步骤 3: 安全网评估

```bash
# 检查测试覆盖情况
./gradlew testDebugUnitTest 2>&1 | tail -5

# 检查 JaCoCo
grep -r "jacoco" app/build.gradle* 2>/dev/null | head -3

# 统计测试文件数
find app/src/test -name "*Test.kt" -o -name "*Spec.kt" 2>/dev/null | wc -l | tr -d ' '
find app/src/androidTest -name "*Test.kt" 2>/dev/null | wc -l | tr -d ' '
```

**评估结果判定:**

| 条件 | 判定 | 处理 |
|------|------|------|
| 覆盖率 >60% 且相关测试存在 | 安全，继续 | 直接进入步骤 4 |
| 覆盖率 <60% 或无相关测试 | 风险，警告 | AskUserQuestion |

**测试不足时 AskUserQuestion:**
> 当前测试覆盖不足。重构可能引入回归风险。
> - A) 先补测试 (调用 /android-tdd)
> - B) 继续 (接受风险)
> - C) 取消

### 步骤 4: Scope 检测

分析重构影响范围，自动判定 scope 档位:

```bash
# 根据目标描述估算影响文件数
# 搜索目标类/接口被引用的位置
# 统计跨模块影响
```

**Scope 判定规则:**

| Scope | 条件 | 执行策略 |
|-------|------|---------|
| Micro | 单文件或 <3 个文件 | 直接在当前分支改 |
| Medium | 跨文件或 3-10 个文件 | worktree 隔离 |
| Macro | 跨模块或 >10 个文件 | 生成 plan -> worktree-runner |

输出: "[refactor] Scope: Medium (影响 5 个文件, 跨 2 个模块)"

---

## Phase 1: 重构计划

### Micro scope

- 列出具体变更点 (哪个类/方法怎么改)
- 标记风险点 (final 类、反射、序列化、公开 API)
- 简短计划，跳过详细文档
- 使用 AskUserQuestion 确认

输出:
```
=== Micro 重构计划 ===
变更点:
  1. LoginActivity.kt:35 - 提取 validateInput() 方法
  2. LoginActivity.kt:78 - 提取 showLoading() 方法
风险点: 无
```

### Medium scope

- 详细的分步计划 (每步改什么、验证什么)
- 每步生成一个 commit
- 使用 AskUserQuestion 确认计划

输出:
```
=== Medium 重构计划 ===
Step 1: 创建 AuthViewModel.kt，迁移登录逻辑
  验证: assembleDebug + testDebugUnitTest
Step 2: 创建 AuthRepository.kt，迁移 API 调用
  验证: assembleDebug + testDebugUnitTest
Step 3: 简化 LoginActivity.kt，仅保留 UI 逻辑
  验证: assembleDebug + testDebugUnitTest
每步完成后对照需求保护清单。
```

### Macro scope

- 生成完整的迁移 plan 文件 (docs/plans/<slug>-refactor.md)
- plan 格式与 autoplan 兼容 (可被 worktree-runner 导入)
- 包含: 需求保护清单 + 分步任务 + 验证标准
- 使用 AskUserQuestion 确认后调用 /android-worktree-runner

**Macro plan 文件格式 (worktree-runner 兼容):**

```markdown
# 重构: <目标描述>

## PRD 保护清单

| 需求 | 当前实现 | 影响状态 |
|------|---------|---------|
| FR-1: 用户登录 | LoginActivity.kt, LoginViewModel.kt | 将被改动 |
| FR-2: 错误提示 | LoginActivity.kt | 将被改动 |

### Task 1: <标题>
- [ ] 步骤 1 描述
- [ ] 步骤 2 描述
**验证:** assembleDebug + testDebugUnitTest
**TDD:** required (如有新类)

### Task 2: <标题>
- [ ] 步骤 1 描述
- [ ] 步骤 2 描述
**验证:** assembleDebug + testDebugUnitTest
```

---

## Phase 2: 执行重构

### Micro 执行

```
Step 1: 创建重构前 savepoint
  git add -A
  git commit -m "refactor: savepoint before $SLUG" --no-verify 2>/dev/null || true
  SAVEPOINT=$(git rev-parse HEAD 2>/dev/null || echo "")

Step 2: 执行重构代码变更

Step 3: 运行测试验证
  ./gradlew assembleDebug && ./gradlew testDebugUnitTest

Step 4: 对照需求保护清单 (如有 PRD)

Step 5: 若通过 -> git commit; 若失败 -> 回滚到 savepoint
```

**失败回滚:**
```bash
# 回滚到重构前状态 (变更保留在暂存区)
if [ -n "$SAVEPOINT" ]; then
  git reset --soft "$SAVEPOINT"
  echo "[refactor] 已回滚到重构前状态。变更保留在暂存区 (git diff --cached 查看)。"
fi
```

### Medium 执行

```
Step 1: 创建 worktree
  git worktree add .claude/worktrees/wr-refactor-<slug> -b refactor/<slug>

Step 2: 逐步执行 (按 Phase 1 的分步计划)
  每步:
  - 修改代码
  - GRADLE_USER_HOME=".claude/worktrees/wr-refactor-<slug>/.gradle" ./gradlew assembleDebug
  - GRADLE_USER_HOME=".claude/worktrees/wr-refactor-<slug>/.gradle" ./gradlew testDebugUnitTest
  - 对照需求保护清单
  - git add -A && git commit

Step 3: 全量验证
  - 所有测试通过
  - 需求保护清单全部通过

Step 4: 合并回主分支
  git checkout <original-branch>
  git merge refactor/<slug> --no-ff
  git worktree remove .claude/worktrees/wr-refactor-<slug> --force
```

**每步 AskUserQuestion:**
> Step N 完成: <变更摘要>
> - A) 确认，继续下一步
> - B) 回滚此步
> - C) 暂停，手动调整

### Macro 执行

```
Step 1: 将 plan 文件导入 worktree-runner
  使用 Skill 工具调用 android-worktree-runner:
  skill: "android-worktree-runner"
  args: "import docs/plans/<slug>-refactor.md"

Step 2: worktree-runner 执行各任务
  (自动处理 worktree 创建、Android 验证、commit)

Step 3: 完成后进入 Phase 3 做 PRD 回归验证
```

**plan 导入失败降级:**
- worktree-runner 导入失败 -> 降级为 Medium scope
- 输出: "[refactor] plan 导入失败，降级为 Medium scope"

---

## Phase 3: PRD 回归验证

无论哪个 scope，完成后都要做 PRD 回归。

**有 PRD 时:**
```
逐条对照需求保护清单:

FR-1: 用户登录 -- LoginViewModel 仍实现登录逻辑
FR-2: 错误提示 -- 错误信息显示逻辑未变
FR-3: 记住我 -- AuthRepository 未被改动
NFR-1: 响应时间 -- 网络调用逻辑未变
明确不做: 第三方登录 -- 未新增相关代码

需求回归: 全部通过 (5/5)
```

**无 PRD 时:**
```
[refactor] 无 PRD，跳过需求回归。
测试验证: N/N passed
```

**若有未通过项:**
- 分析原因 (是否为预期变更?)
- 使用 AskUserQuestion 确认
- 必要时回滚到重构前状态

---

## Phase 4: 清理 + 收尾

```
Step 1: 删除被替换的旧代码 (如提取后残留的冗余方法)
Step 2: 清理无用 import
Step 3: 更新需求-代码映射 (代码路径变了)
Step 4: 后续建议
```

**后续建议 AskUserQuestion:**
> 重构完成。建议后续操作:
> - A) /android-code-review (审查重构质量)
> - B) /android-qa (全面验证)
> - C) 全部执行 (A -> B)
> - D) 跳过，直接完成

---

## Phase 5: 学习记录

记录重构模式到 learnings:

```bash
_R="$(git worktree list | head -1 | awk '{print $1}')"
SHARED_BIN="$_R/.claude/skills/android-shared/bin"
[ ! -d "$SHARED_BIN" ] && SHARED_BIN="$HOME/.claude/skills/android-shared/bin"
bash "$SHARED_BIN/android-learnings-log" '{"skill":"android-refactor","type":"pattern","key":"<refactoring-pattern>","insight":"<insight>","confidence":8,"source":"observed","files":["<files>"]}'
```

**常见可记录的模式:**
- 提取 ViewModel + Repository 分层
- View -> Compose 迁移模式
- LiveData -> StateFlow 迁移
- 回调 -> Flow 转换
- 单模块 -> 多模块拆分策略

---

## 输出

| Scope | 输出位置 | 格式 |
|-------|---------|------|
| Micro | 对话中直接输出 | 变更摘要文本 |
| Medium | `docs/reviews/<branch>-refactor-report.md` | Markdown 报告 |
| Macro | plan 文件 + worktree-runner 执行结果 | plan.md + tasks.json |

**Medium 报告格式:**

```markdown
# 重构报告: <目标描述>

> 生成于 <日期> | android-refactor
> Scope: Medium | 分支: refactor/<slug>

## 摘要

| 指标 | 结果 |
|------|------|
| 影响文件数 | N |
| 执行步数 | N |
| 测试通过 | N/N |
| PRD 回归 | 全部通过 / X 项需确认 |

## 需求保护清单

| 需求 | 状态 | 备注 |
|------|------|------|
| FR-1 | 通过 | 逻辑迁移到 ViewModel |
| FR-2 | 通过 | 错误提示未变 |
| FR-3 | 不受影响 | 代码未改动 |

## 变更文件列表

| 文件 | 操作 | 说明 |
|------|------|------|
| AuthViewModel.kt | 新增 | 从 Activity 提取的登录逻辑 |
| AuthRepository.kt | 新增 | API 调用封装 |
| LoginActivity.kt | 修改 | 简化为纯 UI |
```

---

## 异常情况处理

| 场景 | 处理方式 |
|------|---------|
| 无 PRD | 降级为测试驱动验证，明确告知用户 |
| 测试不足 | 强制建议先补测试 (AskUserQuestion) |
| 重构后测试失败 | 自动回滚到重构前状态 (git reset --soft 到 savepoint / worktree 删除) |
| 需求回归失败 | 暂停，分析原因，用户确认后决定回滚或继续 |
| worktree 创建失败 | 降级为 Micro scope |
| Macro plan 导入失败 | 降级为 Medium scope |
| 不在 git 仓库中 | 报错: "android-refactor 需要 git 仓库" |
| 不是 Android 项目 | 报错: "未检测到 Android 项目" |
| Gradle 构建超时 | 询问用户: 继续等待或跳过验证 |
| 合并冲突 (Medium) | 暂停，提示用户手动解决 |

---

## 与其他 Skill 的集成

```
android-refactor
  |-- 缺少测试 -> android-tdd (补测试)
  |-- Medium scope -> worktree 隔离
  |-- Macro scope -> autoplan plan 格式 -> android-worktree-runner
  |-- 完成后 -> android-code-review
  |-- 完成后 -> android-qa
  +-- 发现模式 -> android-learn (记录)
```

| Skill | 关系 | 说明 |
|-------|------|------|
| android-tdd | 前置补测试 | 测试不足时调用补测试 |
| android-worktree-runner | Macro 执行器 | 生成兼容 plan 由其执行 |
| android-autoplan | PRD 生成 | 无 PRD 时建议先生成 |
| android-code-review | 后置审查 | 重构完成后审查代码质量 |
| android-qa | 后置验证 | 重构完成后全面验证 |
| android-learn | 知识沉淀 | 记录重构模式供未来参考 |
| android-investigate | 异常排查 | 重构后测试失败时深入调查 |

---

## 文件结构

```
项目根目录/
  docs/
    plans/
      <slug>-refactor.md            <-- Macro scope 生成的迁移 plan
    reviews/
      <branch>-refactor-report.md   <-- Medium scope 生成的重构报告
  .claude/
    worktrees/
      wr-refactor-<slug>/           <-- Medium scope 的隔离 worktree
    skills/
      android-refactor/
        SKILL.md                    <-- 本 skill
```
