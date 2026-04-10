# Android TDD Skill Design Spec

**Date:** 2026-04-10
**Status:** Approved (v2 — TDD 强制 + QA 覆盖率对标 gstack)
**Author:** liangrk + Claude Opus 4.6

## Problem Statement

The current WorkFlowSkills Android skill chain lacks a dedicated TDD (Test-Driven Development) skill. Testing is scattered across `android-qa` (post-implementation verification) and `android-autoplan` (test plan generation), but there is no skill that enforces the write-tests-first methodology.

The `everything-claude-code` plugin provides a solid TDD framework (tdd-guide agent, tdd-workflow skill, test-coverage command) for web/TypeScript projects, but it is not Android-specific. It lacks:
- Android platform boundary awareness (lifecycle, permissions, configuration changes)
- Android test framework auto-detection (JUnit4/5, Mockito/MockK, Espresso, Compose Testing, Robolectric)
- Integration with the existing Android skill workflow (worktree-runner, autoplan)

## Goal

Create an `android-tdd` skill that:
1. Enforces TDD methodology (RED -> GREEN -> REFACTOR) for Android development
2. **强制集成到 android-autoplan — 所有业务逻辑任务默认必须经过 TDD**
3. Integrates with `android-worktree-runner` for automatic TDD enforcement during plan execution
4. Provides a gstack-like auto-fix loop with independent verification subagent
5. Includes Android-specific boundary test matrix
6. Enforces coverage gates (80% general, 90% critical paths)
7. **改进 android-qa — 增加覆盖率验证、条件执行、感知 TDD 状态**

## Design

### Deliverables

| File | Change Type | Description |
|------|------------|-------------|
| `.claude/skills/android-tdd/SKILL.md` | New | Standalone TDD skill (~900 lines) |
| `.claude/skills/android-worktree-runner/SKILL.md` | Modify | Add TDD trigger (mandatory for business tasks) + tasks.json TDD fields |
| `.claude/skills/android-autoplan/SKILL.md` | Modify | **TDD 强制** — 业务任务默认 `tdd-required: true` |
| `.claude/skills/android-qa/SKILL.md` | Modify | **覆盖率门禁 + 条件执行 + TDD 状态感知** |

### Core Architecture: android-tdd Skill

#### Phase 0: Environment Detection

Auto-detect the project's testing infrastructure:

- **Test framework:** JUnit4 vs JUnit5, Mockito vs MockK, Truth vs AssertJ
- **UI testing:** Espresso vs Compose Testing (or both)
- **DI framework:** Hilt vs Koin (determines mock strategy)
- **Build variant and module structure** via `settings.gradle.kts`
- **Existing test directory structure** (standard Android test source sets)
- **Coverage tool:** JaCoCo configuration (check `build.gradle.kts` for jacoco plugin)

#### Phase 1: Contract Definition (Interfaces First)

Before any test or implementation:
- Analyze the requirement description
- Define interfaces/classes/function signatures only (no logic)
- Android-specific contracts:
  - ViewModel interface (state, events, intents)
  - Repository interface (data source methods)
  - UseCase interface (input/output types)
  - State/Event sealed classes
  - UI State data classes

Output: Interface skeleton files (placed in appropriate source directories).

#### Phase 2: RED — Write Failing Tests

Generate test cases organized by:

**Standard coverage:**
- Happy path (primary use case)
- Edge cases (null, empty, extreme values)
- Error paths (network failure, permission denial, timeout)

**Android Platform Boundary Matrix (auto-matched from requirement):**

| Category | Test Scenarios | Test Type |
|----------|---------------|-----------|
| Lifecycle | Activity/Fragment recreation, Process Death recovery | Instrumented |
| Config Change | Dark mode toggle, Locale switch, Screen rotation, Multi-window | Instrumented |
| Permissions | Permission denied, Permission revoked, Don't ask again | Instrumented |
| Network | No network -> network, Timeout, DNS failure, Slow network | JVM Unit (mock) |
| Storage | Disk full, Database corruption, SharedPreferences migration | JVM Unit |
| Concurrency | Coroutine race conditions, Flow backpressure, ViewModel double-click | JVM Unit |
| Memory | Large image OOM, Long RecyclerView list, Memory leak | Instrumented |
| Compatibility | API level boundary (minSdk), Different screen sizes | Static analysis |

**Auto-matching rules:**
- Requirement mentions "network" or "API" -> Network category (4 scenarios)
- Requirement mentions "list" or "RecyclerView" -> Memory category (2 scenarios)
- Requirement mentions "settings" or "preferences" -> Config Change category (4 scenarios)
- Requirement mentions "location" or "camera" or "storage" -> Permissions category (3 scenarios)

**Test type selection:**
- Pure logic (ViewModel, UseCase, Repository, Mapper) -> JVM Unit Test
- UI-dependent (Composable, Activity, Fragment) -> Instrumented Test
- Hybrid (ViewModel + Compose integration) -> Split: JVM for logic, Instrumented for UI

After writing tests: run them and verify ALL fail for the right reason (RED confirmation).

#### Phase 3: GREEN — Minimal Implementation

- Write the minimum code to make all tests pass
- Strict rule: no untested features, no "while I'm at it" additions
- Run tests and verify ALL pass (GREEN confirmation)

#### Phase 4: REFACTOR — Safe Refactoring

- Refactor under green test umbrella
- Goals: eliminate duplication, improve naming, optimize structure
- Run tests after each refactoring step to confirm green

#### Phase 5: Coverage Gate

- Run `./gradlew test<Variant>UnitTest --info` where `<Variant>` is determined in Phase 0 from the project's build configuration (default: `Debug`)
- Parse coverage report (JaCoCo XML or Gradle built-in)
- Enforce thresholds:
  - **80%+ overall** for all code
  - **90%+ critical paths** (ViewModel, Repository, UseCase)
- For files below threshold: auto-generate supplementary tests targeting uncovered branches
- Re-run to verify improvement

#### Phase 6: Auto-Fix Loop (3 fix + 1 verification)

This is the core differentiator vs gstack. A 4-round cycle with escalating severity:

**Round 1: Mechanical Fix (automatic, no user interaction)**
- Compilation errors (missing imports, type mismatches)
- Mock configuration errors (wrong return type, missing when/thenReturn)
- Test setup issues (missing annotations, wrong test runner)
- Execute automatically, report results

**Round 2: Logic Fix (subagent root cause analysis + user confirmation)**
- Spawn independent subagent with: failing test code, error output, implementation code
- Subagent analyzes root cause and proposes fix
- Present fix proposal to user for confirmation before applying
- Re-run tests after fix

**Round 3: Architecture Fix (report + user intervention)**
- If still failing after Round 2, the issue may be structural
- Generate detailed report: what's failing, why, suggested architectural changes
- Ask user whether to:
  - A) Revise the interface contract (back to Phase 1)
  - B) Simplify the test scope
  - C) Manually fix and re-run

**Round 4: Independent Verification Subagent (no context inheritance)**
- Spawn fresh subagent with ONLY these injected inputs:
  - Contract definition from Phase 1
  - Final test code
  - Final implementation code
  - Coverage report
- Subagent outputs: PASS / CONDITIONAL PASS / FAIL + specific issue list
- **No access to main conversation context** — avoids confirmation bias
- If FAIL: return to Round 1 with verification report as new context (max 1 retry cycle)

#### Phase 7: Output Report

Generate structured report including:
- Coverage summary (file-level + method-level)
- Pass/fail/skip statistics
- Boundary matrix coverage status (which categories covered, which skipped)
- Uncovered paths list (if any)
- Recommendations for future test improvements

### worktree-runner Integration

#### tasks.json TDD 字段扩展

在现有 task 数据结构中增加 TDD 相关字段:

```json
{
  "tdd": {
    "required": true,
    "executed": false,
    "coverage_percent": null,
    "report_path": null,
    "boundary_categories_covered": []
  }
}
```

字段说明:
- `required`: 来自 plan 的 `TDD` 标签，默认由 autoplan 设定
- `executed`: TDD 是否已完成
- `coverage_percent`: TDD 阶段的覆盖率数字
- `report_path`: TDD 报告文件路径
- `boundary_categories_covered`: 已覆盖的边界类别列表

#### Task Type Classification (强制规则)

**TDD 是默认行为，不是可选功能。** worktree-runner 按以下规则判断:

**TDD 强制执行 (tdd-required: true):**
- 带有 `**TDD: required**` 标签的任务 (来自 autoplan)
- 任务描述包含关键词: `ViewModel`、`Repository`、`UseCase`、`screen`、`feature`、`logic`、`component`、`service`
- 任务层级为 `数据层`、`业务逻辑层`、`表现层` (autoplan 的五层分类)

**TDD 跳过 (tdd-required: false):**
- 带有 `**TDD: skip**` 标签的任务 (来自 autoplan)
- 任务层级为 `基础设施`、`测试` (autoplan 的五层分类)
- 任务描述包含关键词: `Gradle`、`Manifest`、`ProGuard`、`migration`、`config`、`setup`

**规则: 无法分类的任务默认走 TDD。** 宁可多测不可漏测。

#### Modified Execution Flow

```
task start -> read referenced files -> classify task type ->
  |- Infrastructure/config task -> execute directly -> Android verify -> commit
  |- Business logic/UI task -> INVOKE android-tdd (MANDATORY) ->
       |- TDD PASS -> update tasks.json tdd fields -> Android verify -> commit
       |- TDD FAIL (after 4-round cycle) -> pause, ask user
```

**关键变化: TDD 不是可选项。** 对于业务任务，worktree-runner 在执行代码之前
必须先调用 android-tdd。只有在 TDD 全部通过后，才进入常规的 Android 验证
(assembleDebug + lintDebug) 并提交。

#### User Override (有限)

用户可以在 worktree-runner 中对单个任务覆盖 TDD 要求:

```
Task 3: 实现 LoginViewModel — TDD required
> - A) 执行 TDD + 实现 (默认)
> - B) 跳过 TDD，直接实现 (不推荐，会记录到 tasks.json)
```

选择 B 时:
- tasks.json 中该任务记录 `tdd.skipped: true, tdd.skip_reason: "user_override"`
- 后续 QA 会注意到 TDD 被跳过，加强该任务的测试验证

### autoplan Integration (TDD 强制)

#### 核心原则: TDD 是默认行为

autoplan 产出的 plan 中，**业务逻辑任务默认必须经过 TDD**。这不是可选模式，
而是标准流程的一部分。只有基础设施类任务可以跳过。

#### 任务模板修改

将现有任务模板:

```markdown
### Task N: [task title]
**层级:** 基础设施 / 数据层 / 业务逻辑层 / 表现层 / 测试
```

改为:

```markdown
### Task N: [task title]
**层级:** 基础设施 / 数据层 / 业务逻辑层 / 表现层 / 测试
**TDD:** required / skip
```

#### TDD 标签分配规则

| 任务层级 | TDD 标签 | 原因 |
|---------|---------|------|
| 基础设施 | **skip** | Gradle/Manifest/ProGuard 不适合 TDD |
| 数据层 | **required** | Repository、数据模型、API 接口必须有测试 |
| 业务逻辑层 | **required** | UseCase、ViewModel 是核心逻辑，TDD 价值最高 |
| 表现层 | **required** | UI 组件需要测试状态绑定和交互逻辑 |
| 测试 | **skip** | 测试任务本身就是测试，不需要 TDD |

**规则: 除了基础设施和测试层，所有任务 TDD = required。不可协商。**

#### Phase 4 测试审查增强

现有的测试审查 subagent (Phase 4 步骤 4) 增加 TDD 相关检查:

```
审查要点 (在原有 4 点基础上增加):
5. 每个非基础设施任务是否标记了 TDD: required?
6. TDD 任务是否包含足够的边界条件描述? (引用边界矩阵)
7. 如果任务包含 UI 逻辑，是否同时包含 JVM 单元测试和 Instrumented 测试?
```

#### autoplan 产出示例

```markdown
### Task 1: 添加网络依赖
**层级:** 基础设施
**TDD:** skip
- [ ] 在 app/build.gradle.kts 添加 Retrofit + OkHttp 依赖
- [ ] 同步 Gradle 确认编译通过

### Task 2: 定义 API 接口和数据模型
**层级:** 数据层
**TDD:** required
- [ ] 创建 LoginRequest / LoginResponse 数据类
- [ ] 创建 AuthService Retrofit 接口
- [ ] TDD: 编写 Repository 接口测试 (happy path + 网络失败边界)

### Task 3: 实现 LoginViewModel
**层级:** 业务逻辑层
**TDD:** required
- [ ] 创建 LoginViewModel + LoginUiState
- [ ] TDD: 编写 ViewModel 测试 (登录成功/失败/加载中/边界输入)
- [ ] TDD: 覆盖网络超时、空输入、权限拒绝边界场景
```

## Comparison with gstack QA

| Dimension | gstack QA | android-tdd | android-qa (改进后) |
|-----------|-----------|-------------|---------------------|
| Test timing | Post-implementation | Pre-implementation (test-first) | Post-TDD 增量验证 |
| Fix loop | 3 rounds | 3 fix + 1 verification | 分级修复 + TDD 职责分离 |
| Coverage analysis | None | 80%/90% gates + auto-fill | 80%/90% gates (TDD 复用或自执行) |
| Boundary coverage | No systematic list | 8-category matrix | 读取 TDD 矩阵结果 |
| Subagent usage | None | Round 2+ + isolated Round 4 | 无 (QA 自身修复) |
| Framework awareness | Browser/web only | Android frameworks auto-detect | 读取 TDD 检测结果 |
| Integration | Standalone | Deep worktree-runner | 感知 tasks.json TDD 状态 |
| Redundancy with TDD | N/A | N/A | 条件执行避免重复 |

## Dependencies

- **Claude Code native tools:** Read, Write, Edit, Grep, Glob, Bash, Agent, Skill
- **Android build tools:** Gradle, JaCoCo (for coverage)
- **No external MCP dependencies**
- **Consumes:** android-worktree-runner's tasks.json format
- **Produces:** Test reports, coverage data

## Non-Goals

- UI snapshot/diff testing (handled by gstack/browser tools)
- Performance benchmarking (separate concern)
- CI/CD pipeline configuration (out of scope)
- Figma-driven testing (handled by android-design-review)

---

## android-qa 改进 (对标 gstack)

### 问题分析

当前 android-qa 与 android-tdd 存在重叠，且缺少 gstack 的覆盖率验证能力:

| 环节 | android-qa (当前) | gstack QA | android-qa (改进后) |
|------|------------------|-----------|---------------------|
| 单元测试执行 | 无条件执行 | 无 (浏览器测试为主) | 条件执行，感知 TDD 状态 |
| 覆盖率验证 | **无** | 无 (但有自动修复循环) | **80%/90% 门禁** |
| 修复循环 | 3 轮，粒度均匀 | 3 轮，自动修复 | 分级修复 + TDD 结果复用 |
| TDD 状态感知 | 无 | 无 | 读取 tasks.json tdd 字段 |
| 静态分析 | 有 (Layer 1) | 无 | 保留，不变 |
| 设备测试 | 有 (Layer 3) | 有 (浏览器) | 保留，不变 |

### 改进 1: Phase 0 增加 TDD 状态检测

在现有环境检测之后，增加一步:

```bash
# 读取 tasks.json 中的 TDD 状态
TASKS_FILE="<main_worktree>/.claude/android-worktree-runner/tasks.json"
# 提取当前 plan 中每个任务的 tdd 字段
```

产出:
```
=== TDD 状态 ===
TDD 已执行: 5/7 任务
TDD 跳过: 2 任务 (基础设施)
TDD 覆盖率: 平均 87% (范围: 82%-94%)
TDD 报告: docs/reviews/plan-xxx-tdd-report.md
```

如果 tasks.json 不存在或没有 TDD 字段:
```
=== TDD 状态 ===
未检测到 TDD 执行记录 — QA 将执行完整验证 (含覆盖率门禁)
```

### 改进 2: Layer 2 条件执行

**当前行为:** 无条件执行 assembleDebug → lintDebug → testDebugUnitTest

**改进后:**

```
步骤 2.1: assembleDebug — 始终执行 (最终集成验证)
步骤 2.2: lintDebug — 始终执行 (TDD 不覆盖 lint)
步骤 2.3: testDebugUnitTest — 条件执行:
  ├── TDD 已执行 且 覆盖率 >= 80% → 跳过，复用 TDD 结果
  ├── TDD 已执行 但 覆盖率 < 80% → 执行，重点关注低覆盖率模块
  └── TDD 未执行 → 执行 (完整验证)
```

**条件执行逻辑:**
- 读取 tasks.json 中所有任务的 `tdd.coverage_percent`
- 如果所有业务任务的覆盖率 >= 80%: Layer 2.3 跳过，记录 "由 TDD 覆盖"
- 如果存在覆盖率 < 80% 的任务: 执行单元测试，但只针对低覆盖率模块
- 如果 TDD 未执行: 完整执行 (向后兼容)

### 改进 3: 新增 Layer 2.4 — 覆盖率门禁

无论 Layer 2.3 是否跳过，都执行覆盖率验证:

```bash
# 运行覆盖率报告 (如果项目配置了 JaCoCo)
./gradlew test<Variant>UnitTest --info 2>&1 | grep -i "coverage"

# 查找 JaCoCo 报告
JACOCO_REPORT=$(find "$PROJECT_ROOT" -path "*/reports/jacoco/*/*.xml" 2>/dev/null | head -1)
```

**覆盖率门禁规则:**

| 指标 | 阈值 | 不达标的处理 |
|------|------|-------------|
| 总体行覆盖率 | 80% | 触发修复循环，自动补测试 |
| 关键路径覆盖率 | 90% (ViewModel, Repository, UseCase) | 触发修复循环 |
| 分支覆盖率 | 75% | 记录为 🟡 建议 |

**与 TDD 覆盖率的协同:**
- 如果 TDD 已达标: QA 读取 TDD 报告，不再重复计算，直接标记 PASS
- 如果 TDD 未达标或未执行: QA 自己运行覆盖率，使用相同的门禁标准

**覆盖率报告格式:**
```
=== 覆盖率门禁 ===
来源: TDD 报告 / QA 执行

总体覆盖率: 87% ✅ (阈值: 80%)
分支覆盖率: 79% ✅ (阈值: 75%)
关键路径:   92% ✅ (阈值: 90%)

文件级详情:
  ✅ LoginViewModel.kt     94%
  ✅ AuthRepository.kt     91%
  🟡 LoginScreen.kt        78% (建议: 补充状态绑定测试)
  ❌ TokenMapper.kt        45% → 触发自动补测试
```

### 改进 4: 修复循环与 TDD 的职责分离

| 修复触发 | 负责方 | 修复方式 | QA 行为 |
|---------|--------|---------|---------|
| TDD 阶段测试失败 | android-tdd | 修改实现代码 | 不介入 |
| QA 发现测试失败 (TDD 已通过) | android-qa | 可能是集成/环境问题 | 深入调查 |
| QA 发现测试失败 (TDD 未执行) | android-qa | 修复代码 + 补测试 | 全权处理 |
| 静态分析问题 | android-qa | 独有领域 | 全权处理 (不变) |
| 设备测试问题 | android-qa | 独有领域 | 全权处理 (不变) |
| 覆盖率不达标 | android-qa | 自动补测试 | 新增能力 |

### 改进 5: QA 报告增加 TDD 摘要

在现有 QA 报告模板的"摘要"部分增加:

```markdown
## TDD 执行摘要

| 指标 | 结果 |
|------|------|
| TDD 任务数 | N/M |
| TDD 平均覆盖率 | XX% |
| TDD 跳过任务 | N (原因: 基础设施) |
| QA 复用 TDD 结果 | 是/否 |

## 覆盖率门禁

| 指标 | 结果 | 阈值 | 状态 |
|------|------|------|------|
| 总体行覆盖率 | XX% | 80% | ✅/❌ |
| 分支覆盖率 | XX% | 75% | ✅/❌ |
| 关键路径覆盖率 | XX% | 90% | ✅/❌ |
```

### 改进 6: QA 与 TDD 被跳过任务的处理

如果 tasks.json 显示某些业务任务 TDD 被用户跳过 (`tdd.skipped: true`):

```
⚠️ 检测到 N 个业务任务跳过了 TDD:
  - Task 3: LoginViewModel (原因: user_override)
  - Task 5: UserProfileScreen (原因: user_override)

QA 将对这些任务加强验证:
  - 强制执行 Layer 2.3 (单元测试)
  - 覆盖率阈值提升至 90% (而非默认 80%)
  - 执行完整的边界矩阵检查
```

### QA 改动汇总

| QA 章节 | 变更 | 影响范围 |
|---------|------|---------|
| Phase 0 | 新增 TDD 状态检测步骤 | +15 行 |
| Phase 2 Layer 2.3 | 从无条件执行改为条件执行 | 修改 ~20 行 |
| Phase 2 | 新增 Layer 2.4 覆盖率门禁 | +40 行 |
| Phase 3 Bug 报告 | 摘要增加 TDD 执行摘要和覆盖率门禁 | +15 行 |
| Phase 4 修复循环 | 增加"覆盖率不达标"修复类型 | +10 行 |
| 异常情况 | 增加"TDD 被跳过"处理 | +5 行 |
