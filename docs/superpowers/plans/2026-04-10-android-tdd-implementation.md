# Android TDD Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create android-tdd skill with mandatory TDD enforcement, auto-fix loop with independent verification, and upgrade android-qa with coverage gates benchmarked against gstack.

**Architecture:** Four files changed — one new skill (android-tdd), three modified skills (worktree-runner, autoplan, qa). TDD is mandatory for business logic tasks, enforced at the autoplan level (task template tag) and worktree-runner level (execution gate). QA becomes a post-TDD incremental verifier with coverage gates.

**Tech Stack:** Claude Code native tools (Read, Write, Edit, Grep, Glob, Bash, Agent, Skill). Android build tools (Gradle, JaCoCo). No external dependencies.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `.claude/skills/android-tdd/SKILL.md` | Create | Standalone TDD skill: env detection, contract definition, RED/GREEN/REFACTOR, coverage gate, auto-fix loop (3+1), report output |
| `.claude/skills/android-worktree-runner/SKILL.md` | Modify | Add TDD fields to tasks.json schema, add TDD classification logic before task execution, add TDD invocation step |
| `.claude/skills/android-autoplan/SKILL.md` | Modify | Add `**TDD:**` tag to task template, add TDD tag assignment rules, enhance Phase 4 test review subagent |
| `.claude/skills/android-qa/SKILL.md` | Modify | Add TDD status detection in Phase 0, conditional execution in Layer 2.3, new Layer 2.4 coverage gate, TDD summary in bug report, TDD skip penalty |

---

### Task 1: Create android-tdd skill — frontmatter, overview, and Phase 0

**Files:**
- Create: `.claude/skills/android-tdd/SKILL.md`

- [ ] **Step 1: Create the skill file with frontmatter, overview, and invocation syntax**

Write the frontmatter block and overview section. This is the header of the skill — all other tasks build on this file.

The file starts with YAML frontmatter:
```yaml
---
name: android-tdd
description: |
  Android TDD 驱动 skill。强制执行测试先行方法论：先定义契约，再写失败测试 (RED)，
  然后最小实现 (GREEN)，最后安全重构 (REFACTOR)。
  包含 Android 平台边界测试矩阵、覆盖率门禁 (80%/90%)、自动修复循环 (3 修复 + 1 独立验收)。
  可独立调用，也可被 android-worktree-runner 自动触发。
  适用场景: 新功能开发、bug 修复、重构、代码质量保障。
voice-triggers:
  - "TDD"
  - "测试先行"
  - "写测试"
  - "测试驱动"
---
```

Then the overview section declaring zero external dependencies, startup declaration, and invocation syntax:
```
# Android TDD

## 概述

测试先行驱动的 Android 开发 skill。契约定义 → RED → GREEN → REFACTOR → 覆盖率门禁 → 自动修复 + 独立验收。

**启动时声明:** "我正在使用 android-tdd skill。"

**零外部依赖:** 仅使用 Claude Code 原生工具。不依赖 gstack、browse、Codex、Figma MCP。

## 调用方式

```bash
/android-tdd <feature-description>    # 独立调用: 对指定功能执行完整 TDD 流程
/android-tdd                           # 交互式: 输入功能描述
/android-tdd verify <test-dir>         # 仅运行覆盖率验证 (不写新测试)
```
```

Then Phase 0: Environment Detection — auto-detect test framework (JUnit4/5, Mockito/MockK, Truth/AssertJ), UI testing (Espresso/Compose Testing), DI (Hilt/Koin), build variant, module structure, existing test directories, JaCoCo config. Output a tech stack profile identical to the format used by android-autoplan and android-code-review.

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/android-tdd/SKILL.md
git commit -m "feat(android-tdd): create skill with frontmatter, overview, and Phase 0 env detection"
```

---

### Task 2: Create android-tdd skill — Phase 1 Contract Definition + Phase 2 RED

**Files:**
- Modify: `.claude/skills/android-tdd/SKILL.md`

- [ ] **Step 1: Write Phase 1 — Contract Definition**

Append to the skill file. Phase 1 defines interfaces/classes/function signatures before any test or implementation. Analyze the requirement description from the user or from worktree-runner's task description. Define:

- ViewModel interface (state, events, intents)
- Repository interface (data source methods)
- UseCase interface (input/output types)
- State/Event sealed classes
- UI State data classes

Output: Interface skeleton files placed in appropriate source directories. No logic, just signatures.

Include a decision matrix for what to define based on requirement keywords:
- "API" or "network" → Repository interface + DTO data classes
- "screen" or "page" or "UI" → ViewModel interface + UI State sealed class
- "business logic" or "use case" → UseCase interface
- "form" or "validation" → Validator interface + ValidationResult sealed class

- [ ] **Step 2: Write Phase 2 — RED (Write Failing Tests)**

Append Phase 2. This is the largest phase. It generates test cases in two categories:

**Category A: Standard coverage**
- Happy path (primary use case)
- Edge cases (null, empty, extreme values)
- Error paths (network failure, permission denial, timeout)

**Category B: Android Platform Boundary Matrix**
Include the full 8-category matrix table from the spec (Lifecycle, Config Change, Permissions, Network, Storage, Concurrency, Memory, Compatibility) with auto-matching rules.

Include test type selection logic:
- Pure logic (ViewModel, UseCase, Repository, Mapper) → JVM Unit Test (`src/test/`)
- UI-dependent (Composable, Activity, Fragment) → Instrumented Test (`src/androidTest/`)
- Hybrid → Split: JVM for logic, Instrumented for UI

After writing tests: run them and verify ALL fail. Include the exact Gradle commands:
```bash
# JVM unit tests
./gradlew test<Variant>UnitTest 2>&1

# Instrumented tests (if any)
./gradlew connected<Variant>AndroidTest 2>&1
```

RED confirmation: if tests PASS instead of failing, this is an error — report and stop.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/android-tdd/SKILL.md
git commit -m "feat(android-tdd): add Phase 1 contract definition and Phase 2 RED with boundary matrix"
```

---

### Task 3: Create android-tdd skill — Phase 3 GREEN + Phase 4 REFACTOR + Phase 5 Coverage Gate

**Files:**
- Modify: `.claude/skills/android-tdd/SKILL.md`

- [ ] **Step 1: Write Phase 3 — GREEN (Minimal Implementation)**

Append Phase 3. Rules:
- Write the minimum code to make all tests pass
- Strict rule: no untested features, no "while I'm at it" additions
- Run tests and verify ALL pass
- GREEN confirmation: if tests still fail, enter Phase 6 auto-fix loop

- [ ] **Step 2: Write Phase 4 — REFACTOR (Safe Refactoring)**

Append Phase 4. Under green test umbrella:
- Eliminate duplication, improve naming, optimize structure
- Run tests after each refactoring step
- If tests break during refactor → revert and try smaller change
- Optional step: if no refactoring needed, skip with note "No refactoring opportunities identified"

- [ ] **Step 3: Write Phase 5 — Coverage Gate**

Append Phase 5. This is the quality gate:

Run coverage:
```bash
./gradlew test<Variant>UnitTest --info 2>&1
# Find JaCoCo report
find "$PROJECT_ROOT" -path "*/reports/jacoco/*/*.xml" 2>/dev/null | head -1
```

Thresholds:
- 80%+ overall for all code
- 90%+ critical paths (files matching *ViewModel.kt, *Repository.kt, *UseCase.kt)

For files below threshold: auto-generate supplementary tests targeting uncovered branches. Show the exact logic:
1. Parse JaCoCo XML to find files below threshold
2. For each low-coverage file: read the source, identify untested branches
3. Generate targeted test methods for uncovered paths
4. Re-run tests and verify improvement

If coverage still below threshold after supplement: continue to Phase 6.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/android-tdd/SKILL.md
git commit -m "feat(android-tdd): add Phase 3 GREEN, Phase 4 REFACTOR, Phase 5 coverage gate"
```

---

### Task 4: Create android-tdd skill — Phase 6 Auto-Fix Loop + Phase 7 Report

**Files:**
- Modify: `.claude/skills/android-tdd/SKILL.md`

- [ ] **Step 1: Write Phase 6 — Auto-Fix Loop (3 fix + 1 verification)**

Append Phase 6. This is the core differentiator. Four-round cycle with escalating severity:

**Round 1: Mechanical Fix** — automatic, no user interaction
- Target: compilation errors (missing imports, type mismatches), mock config errors (wrong return type, missing when/thenReturn), test setup issues (missing annotations, wrong test runner)
- Action: fix automatically using Edit tool, report results
- After fix: re-run tests

**Round 2: Logic Fix** — subagent root cause analysis + user confirmation
- Spawn independent subagent via Agent tool with: failing test code, error output, implementation code
- Subagent prompt must NOT include main conversation context — only the failing artifacts
- Subagent analyzes root cause, proposes fix
- Present fix proposal to user via AskUserQuestion: apply / skip / modify
- After fix: re-run tests

**Round 3: Architecture Fix** — report + user intervention
- Generate detailed report: what's failing, why, suggested architectural changes
- AskUserQuestion with three options:
  - A) Revise interface contract (back to Phase 1)
  - B) Simplify test scope
  - C) Manually fix and re-run

**Round 4: Independent Verification Subagent** — no context inheritance
- Spawn fresh subagent with ONLY these injected inputs (no main conversation context):
  - Contract definition from Phase 1
  - Final test code
  - Final implementation code
  - Coverage report from Phase 5
- Subagent outputs: PASS / CONDITIONAL PASS / FAIL + specific issue list
- If FAIL: return to Round 1 with verification report as new context (max 1 retry)
- If PASS: proceed to Phase 7

Include loop termination conditions:
- All tests pass + Round 4 PASS → Phase 7
- Round 4 FAIL after retry → stop, report to user with full diagnostic
- User chooses to stop at any round → save current state, report

- [ ] **Step 2: Write Phase 7 — Output Report**

Append Phase 7. Generate structured report to `docs/reviews/<branch>-tdd-report.md`:

```markdown
# TDD 报告: <branch>

> 生成于 <YYYY-MM-DD HH:mm> | android-tdd
> 功能描述: <requirement summary>

## 摘要
| 指标 | 结果 |
|------|------|
| 测试总数 | N |
| 通过 | N |
| 失败 | N |
| 跳过 | N |
| 总体覆盖率 | XX% |
| 关键路径覆盖率 | XX% |

## 覆盖率详情
(文件级 + 方法级)

## 边界矩阵覆盖
| 类别 | 状态 | 测试数 |
|------|------|--------|
| Lifecycle | ✅ 已覆盖 | 3 |
| Network | ✅ 已覆盖 | 4 |
| ... | ... | ... |

## 修复循环记录
| 轮次 | 类型 | 修复内容 |
|------|------|---------|
| Round 1 | 机械修复 | 2 个 import 缺失 |
| Round 2 | 逻辑修复 | mock 配置错误 |
| Round 4 | 独立验收 | PASS |

## 未覆盖路径
(如有)
```

Also include the "与其他 Skill 的衔接" section showing relationships with worktree-runner (caller), autoplan (plan source), qa (post-TDD verifier).

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/android-tdd/SKILL.md
git commit -m "feat(android-tdd): add Phase 6 auto-fix loop (3+1) and Phase 7 report output"
```

---

### Task 5: Modify android-worktree-runner — tasks.json TDD fields + classification + invocation

**Files:**
- Modify: `.claude/skills/android-worktree-runner/SKILL.md`

- [ ] **Step 1: Add TDD fields to tasks.json data structure**

In the "数据结构" section (around line 73-121), add the `tdd` field to each task object. The existing task structure at lines 91-111 has fields: `id`, `title`, `status`, `steps`, `commit`, `verification`, `timestamps`. Add after `verification`:

```
          "tdd": {
            "required": false,
            "executed": false,
            "skipped": false,
            "skip_reason": null,
            "coverage_percent": null,
            "report_path": null,
            "boundary_categories_covered": []
          },
```

Also update `version` from `1` to `2` to indicate schema change.

- [ ] **Step 2: Add TDD classification logic in Phase 2 — new step between current step 3 and step 4**

Insert a new step after "步骤 3: 标记任务为进行中" (line ~343) and before "步骤 4: 执行任务步骤" (line ~350). The new step classifies whether the task requires TDD:

```
### 步骤 3.5: TDD 分类 (在任务执行前)

判断当前任务是否需要 TDD。

**读取 TDD 要求:**
1. 检查任务步骤中是否包含 `**TDD:** required` 标签 (来自 autoplan)
2. 检查 tasks.json 中该任务的 `tdd.required` 字段
3. 如果以上都没有: 按关键词分类

**TDD 强制关键词 (任一匹配即触发):**
`ViewModel`、`Repository`、`UseCase`、`screen`、`feature`、`logic`、`component`、`service`

**TDD 跳过关键词 (任一匹配即跳过):**
`Gradle`、`Manifest`、`ProGuard`、`migration`、`config`、`setup`

**默认规则:** 无法分类的任务默认走 TDD。

**如果 TDD required:**
1. 使用 Skill 工具调用 android-tdd:
   skill: "android-tdd", args: "<任务标题> — 基于步骤: <步骤摘要>"
2. 等待 android-tdd 完成
3. 读取 TDD 报告，更新 tasks.json:
   - tdd.executed = true
   - tdd.coverage_percent = <覆盖率数字>
   - tdd.report_path = <报告路径>
   - tdd.boundary_categories_covered = <已覆盖类别列表>
4. 如果 TDD PASS: 继续步骤 4
5. 如果 TDD FAIL: 暂停，使用 AskUserQuestion 询问用户

**如果 TDD not required:**
继续步骤 4 (直接执行)。
```

- [ ] **Step 3: Add user override for TDD**

In the same new step, add a user override option before invoking android-tdd:

```
**用户覆盖 (不推荐):**

如果任务标记为 TDD required，在调用 android-tdd 前展示:
> 任务 "<任务标题>" 需要 TDD。
> - A) 执行 TDD + 实现 (推荐)
> - B) 跳过 TDD，直接实现

选择 B 时:
- 更新 tasks.json: tdd.skipped = true, tdd.skip_reason = "user_override"
- 后续 QA 会检测到 TDD 被跳过，加强验证
```

- [ ] **Step 4: Update Phase 2 step 7 to write TDD fields**

In "步骤 7: 更新状态" (around line 440-459), add TDD fields to the list of fields written to tasks.json after commit:

```
**同步写入 TDD 状态:**
- 如果 TDD 已执行: 确保 tdd.executed、tdd.coverage_percent、tdd.report_path 已写入
- 如果 TDD 被跳过: 确保 tdd.skipped、tdd.skip_reason 已写入
- 如果 TDD 不适用: tdd.required 保持 false
```

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/android-worktree-runner/SKILL.md
git commit -m "feat(worktree-runner): add TDD classification, mandatory invocation, and tasks.json TDD fields"
```

---

### Task 6: Modify android-autoplan — TDD mandatory tags + enhanced test review

**Files:**
- Modify: `.claude/skills/android-autoplan/SKILL.md`

- [ ] **Step 1: Add TDD tag to task output template**

In Phase 1 步骤 5 (around line 270-297), modify the plan output template. The current template at line 283 has:

```
**层级:** 基础设施 / 数据层 / 业务逻辑层 / 表现层 / 测试
```

Add after this line:

```
**TDD:** required / skip
```

Also add the TDD tag assignment rules section after the template:

```
**TDD 标签分配规则 (强制):**

| 任务层级 | TDD 标签 |
|---------|---------|
| 基础设施 | skip |
| 数据层 | required |
| 业务逻辑层 | required |
| 表现层 | required |
| 测试 | skip |

规则: 除基础设施和测试层外，所有任务 TDD = required。
```

- [ ] **Step 2: Update Phase 1 步骤 3 to include TDD tag in task generation**

In "步骤 3: 按 Android 拆分规则生成任务" (around line 211-253), after generating each task in the five layers, add TDD tag assignment:

- After 第一层 (基础设施) tasks: "**TDD:** skip"
- After 第二层 (数据层) tasks: "**TDD:** required"
- After 第三层 (业务逻辑层) tasks: "**TDD:** required"
- After 第四层 (表现层) tasks: "**TDD:** required"
- After 第五层 (测试) tasks: "**TDD:** skip"

Also update the step description text to mention TDD:

In the "第一层: 基础设施" section, add note: "这些任务不适合 TDD，标记 **TDD: skip**"

In the "第二层: 数据层" through "第四层: 表现层" sections, add note: "这些任务必须经过 TDD，标记 **TDD: required**。在步骤描述中包含 TDD 测试要求。"

- [ ] **Step 3: Enhance Phase 4 test review subagent**

In Phase 4 步骤 4 (around line 544-562), update the test review subagent prompt. Current审查要点 has 4 items. Add 3 more:

After the existing 4 points, add:

```
5. 每个非基础设施任务是否标记了 TDD: required?
6. TDD 任务的步骤描述中是否包含足够的边界条件? (参考: 生命周期、配置变更、权限、网络、存储、并发、内存、兼容性)
7. 如果任务包含 UI 逻辑，步骤中是否同时包含 JVM 单元测试和 Instrumented 测试描述?
```

Also update the output format line to include TDD compliance:

```
- TDD 合规性: N/M 非基础设施任务标记了 TDD: required
```

- [ ] **Step 4: Update autoplan 产出文件 section**

In the "产出文件" section (around line 851-882), update the plan file example to include TDD tags. The current example at lines 866-881 shows tasks without TDD tags. Add `**TDD:**` to each task:

```markdown
### Task 1: 添加网络依赖
**层级:** 基础设施
**TDD:** skip
...

### Task 2: 定义 API 接口和数据模型
**层级:** 数据层
**TDD:** required
...
```

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/android-autoplan/SKILL.md
git commit -m "feat(autoplan): add mandatory TDD tags to all business logic tasks and enhance test review"
```

---

### Task 7: Modify android-qa — TDD status detection + conditional execution + coverage gate

**Files:**
- Modify: `.claude/skills/android-qa/SKILL.md`

- [ ] **Step 1: Add TDD status detection to Phase 0**

After Phase 0 步骤 4 (Gradle 可用性检测, around line 126-141), add a new step:

```
### 步骤 5: 检测 TDD 执行状态

```bash
# 定位 tasks.json
MAIN_WORKTREE=$(git worktree list 2>/dev/null | head -1 | awk '{print $1}')
TASKS_FILE="$MAIN_WORKTREE/.claude/android-worktree-runner/tasks.json"

# 检查 tasks.json 是否存在且包含 TDD 字段
if [ -f "$TASKS_FILE" ]; then
  # 提取 TDD 相关信息
  echo "TASKS_JSON_FOUND"
  # 读取每个任务的 tdd 字段
else
  echo "NO_TASKS_JSON"
fi
```

**TDD 状态分析:**
- tasks.json 存在且有 tdd 字段:
  - 统计 TDD 已执行/跳过/未执行的任务数
  - 计算平均覆盖率 (从 tdd.coverage_percent)
  - 识别 TDD 被跳过的业务任务 (tdd.skipped = true)
  - 记录 TDD 报告路径
- tasks.json 不存在或无 tdd 字段:
  - 标记为 "未检测到 TDD 执行记录"
  - QA 将执行完整验证 (含覆盖率门禁)

**产出 TDD 状态摘要:**
```
=== TDD 状态 ===
状态: 已检测 / 未检测
TDD 已执行: N/M 任务
TDD 跳过: N 任务 (原因列表)
TDD 覆盖率: 平均 XX% (范围: XX%-XX%)
TDD 报告: <path> 或 "无"
⚠️ TDD 被跳过的业务任务: N (加强验证)
```

**跳过的业务任务惩罚:**
如果检测到 tdd.skipped = true 的业务任务:
- 覆盖率阈值从 80% 提升到 90%
- Layer 2.3 强制执行 (不可跳过)
- 记录到 QA 报告的警告部分
```

- [ ] **Step 2: Modify Layer 2.3 to conditional execution**

In Phase 2, Layer 2 "步骤 2.3 单元测试" (around line 410-437), replace the unconditional execution with conditional logic:

Current text starts with:
```
#### 2.3 单元测试

```bash
echo "=== 单元测试 ==="
./gradlew testDebugUnitTest 2>&1
TEST_EXIT=$?
```
```

Replace with:
```
#### 2.3 单元测试 (条件执行)

**根据 TDD 状态决定是否执行:**

```bash
if [ "$TDD_ALL_COVERED" = "true" ]; then
  echo "=== 单元测试 ==="
  echo "跳过: TDD 已执行且覆盖率达标 (平均 ${TDD_AVG_COVERAGE}%)"
  echo "来源: ${TDD_REPORT_PATH}"
  TEST_EXIT=0
else
  echo "=== 单元测试 ==="
  ./gradlew testDebugUnitTest 2>&1
  TEST_EXIT=$?
fi
```

**条件执行规则:**

| TDD 状态 | Layer 2.3 行为 |
|---------|---------------|
| 所有业务任务 TDD 已执行 且 覆盖率 >= 80% | 跳过，复用 TDD 结果 |
| TDD 已执行 但 部分任务覆盖率 < 80% | 执行，仅针对低覆盖率模块 |
| TDD 未执行 (无 tasks.json) | 执行 (完整验证) |
| 业务任务 TDD 被用户跳过 | 强制执行，覆盖率阈值提升至 90% |

**解析测试结果** (仅在实际执行时):
(保留现有的测试结果解析逻辑，不变)
```

- [ ] **Step 3: Add Layer 2.4 — Coverage Gate**

After Layer 2.3, insert a new section:

```
#### 2.4 覆盖率门禁

**无论 Layer 2.3 是否跳过，都执行覆盖率验证。**

**获取覆盖率数据:**

```bash
# 优先使用 TDD 报告中的覆盖率
if [ -n "$TDD_REPORT_PATH" ] && [ -f "$TDD_REPORT_PATH" ]; then
  echo "覆盖率来源: TDD 报告 ($TDD_REPORT_PATH)"
  # 从 TDD 报告解析覆盖率
  COVERAGE_SOURCE="tdd"
else
  # 自己运行覆盖率
  echo "=== 覆盖率分析 ==="
  ./gradlew test<Variant>UnitTest 2>&1 | tail -20

  # 查找 JaCoCo 报告
  JACOCO_REPORT=$(find "$PROJECT_ROOT" -path "*/reports/jacoco/*/*.xml" 2>/dev/null | head -1)
  COVERAGE_SOURCE="qa"
fi
```

**覆盖率门禁规则:**

| 指标 | 阈值 | TDD 跳过任务时阈值 | 不达标处理 |
|------|------|-------------------|-----------|
| 总体行覆盖率 | 80% | 90% | 触发自动补测试 |
| 关键路径覆盖率 | 90% | 95% | 触发自动补测试 |
| 分支覆盖率 | 75% | 85% | 记录为 🟡 建议 |

**关键路径定义:** 文件名匹配以下模式的文件:
- `*ViewModel.kt`、`*Repository.kt`、`*RepositoryImpl.kt`、`*UseCase.kt`

**覆盖率报告格式:**

```
=== 覆盖率门禁 ===
来源: TDD 报告 / QA 执行

总体覆盖率: XX% ✅/❌ (阈值: 80%)
分支覆盖率: XX% ✅/❌ (阈值: 75%)
关键路径:   XX% ✅/❌ (阈值: 90%)

文件级详情:
  ✅ XxxViewModel.kt      XX%
  ✅ XxxRepository.kt     XX%
  🟡 XxxScreen.kt         XX% (建议: 补充测试)
  ❌ XxxMapper.kt         XX% → 触发自动补测试
```

**覆盖率不达标的自动补测试:**
1. 识别低于阈值的文件
2. 读取源码，分析未覆盖的分支
3. 生成针对性测试代码
4. 运行测试验证
5. 重新检查覆盖率
6. 最多补 2 轮，仍不达标则记录到 Bug 报告
```

- [ ] **Step 4: Update Layer 2 output format**

In the "Layer 2 输出格式" section (around line 439-457), add coverage gate results:

After the existing "测试详情:" block, add:
```
覆盖率门禁:
  来源: TDD 报告 / QA 执行
  总体: XX% ✅/❌
  关键路径: XX% ✅/❌
  分支: XX% ✅/❌
```

- [ ] **Step 5: Update Phase 3 Bug Report template — add TDD summary and coverage gate**

In Phase 3 步骤 2 (around line 610-684), in the bug report markdown template, after the "## 摘要" table (line 622-633), add two new sections:

```markdown
## TDD 执行摘要

| 指标 | 结果 |
|------|------|
| TDD 状态 | 已检测 / 未检测 |
| TDD 任务数 | N/M |
| TDD 平均覆盖率 | XX% |
| TDD 跳过任务 | N (原因列表) |
| QA 复用 TDD 结果 | 是/否 |

## 覆盖率门禁

| 指标 | 结果 | 阈值 | 状态 |
|------|------|------|------|
| 总体行覆盖率 | XX% | 80% | ✅/❌ |
| 分支覆盖率 | XX% | 75% | ✅/❌ |
| 关键路径覆盖率 | XX% | 90% | ✅/❌ |
```

- [ ] **Step 6: Update Phase 4 fix loop — add coverage fix type**

In Phase 4 步骤 1 (around line 709-718), in the problem classification table, add a new row:

After the existing two rows (自动修复 / 需确认), add:

```
| 覆盖率不达标 | 自动补测试 → 重新验证覆盖率 | 新增 |
```

In Phase 4 步骤 2 (around line 719-741), in the "自动修复范围" list, add item 6:

```
6. **覆盖率缺口** — 为低于阈值的文件生成补充测试
```

- [ ] **Step 7: Update Phase 3 report summary box**

In Phase 3 步骤 3 (around line 690-704), in the terminal output summary box, add coverage gate line:

After "设备测试:" line, add:
```
║  覆盖率: XX% (总体) / XX% (关键路径)                ║
║  TDD: N/M 任务已执行                                ║
```

- [ ] **Step 8: Update 异常情况处理 table**

In the "异常情况处理" section (around line 825-838), add a new row:

```
| TDD 被跳过的业务任务 | 覆盖率阈值提升至 90%，Layer 2.3 强制执行，记录警告 |
| 无 JaCoCo 配置 | 记录为 🟡 建议: "配置 JaCoCo 以启用覆盖率门禁" |
```

- [ ] **Step 9: Update 与其他 Skill 的衔接 table**

In the "与其他 Skill 的衔接" section (around line 869-876), add android-tdd to the table:

```
| android-tdd | 上游 | QA 读取 TDD 报告和 tasks.json TDD 状态，避免重复测试 |
```

- [ ] **Step 10: Commit**

```bash
git add .claude/skills/android-qa/SKILL.md
git commit -m "feat(qa): add TDD status detection, conditional execution, coverage gate (80%/90%), and TDD skip penalty"
```

---

### Task 8: Update README.md and commit all changes

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README to include android-tdd in the skill list**

Read the current README.md, find the skill listing section, and add android-tdd to the workflow chain diagram and skill table. Add it between android-brainstorm and android-autoplan in the workflow:

```
android-brainstorm → android-tdd → android-autoplan → android-worktree-runner → android-qa
```

Add a row to the skill table:
```
| android-tdd | 测试先行驱动 | TDD 流程执行 (RED/GREEN/REFACTOR)、覆盖率门禁、自动修复循环 |
```

- [ ] **Step 2: Final review — verify all four files are consistent**

Read all four modified/created files and verify:
1. android-tdd SKILL.md references worktree-runner correctly
2. worktree-runner references android-tdd invocation syntax correctly
3. autoplan task template TDD tags match worktree-runner classification keywords
4. qa TDD status detection reads the same tasks.json fields that worktree-runner writes
5. Coverage thresholds are consistent: 80% general, 90% critical paths, 75% branch

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README with android-tdd skill and revised workflow chain"
```
