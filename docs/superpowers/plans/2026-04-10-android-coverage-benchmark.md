# Android Coverage + Benchmark Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create two independent Android skills: `android-coverage` (auto coverage loop) and `android-benchmark` (worktree-isolated performance analysis + auto-optimize).

**Architecture:** Two standalone SKILL.md files following the established Android skill pattern (frontmatter, phases, shared detection, learnings, integration table). Both are fully independent from existing skills — no modifications to android-tdd, android-qa, or android-worktree-runner.

**Tech Stack:** Markdown skill definitions, JaCoCo XML parsing, Gradle commands, adb shell commands, Jetpack Macrobenchmark integration.

**Spec:** `docs/superpowers/specs/2026-04-10-android-coverage-benchmark-design.md`

---

## Task 1: Create android-coverage skill directory

**Files:**
- Create: `.claude/skills/android-coverage/` (directory)

- [ ] **Step 1: Create directory**

```bash
mkdir -p .claude/skills/android-coverage
```

- [ ] **Step 2: Verify directory created**

```bash
ls -la .claude/skills/android-coverage/
```

Expected: empty directory exists.

---

## Task 2: Write android-coverage SKILL.md — frontmatter + overview + invocation

**Files:**
- Create: `.claude/skills/android-coverage/SKILL.md` (partial — frontmatter + 概述 + 调用方式)

- [ ] **Step 1: Write frontmatter + 概述 + 调用方式 sections**

Write the beginning of `.claude/skills/android-coverage/SKILL.md` with:

```yaml
---
name: android-coverage
description: |
  Android 独立覆盖率 skill。全自动覆盖率闭环：基线测量 → 差距分析 → 自动补写测试 → 验证达标。
  专为夜间无人值守设计，也可快速出报告（report 模式）。
  复用 android-shared 环境检测，独立于 android-tdd/android-qa 的覆盖率逻辑。
  适用场景: 覆盖率提升、夜间自动化测试、覆盖率审计。
voice-triggers:
  - "覆盖率"
  - "coverage"
  - "覆盖率报告"
  - "补测试"
---
```

Then the body sections:

1. **概述** — Purpose statement: independent coverage loop skill, not tied to TDD/QA flow
2. **启动时声明** — `"我正在使用 android-coverage skill。"`
3. **零外部依赖** — same pattern as other skills
4. **调用方式** — bash code block with 3 modes, then parameter table:
   - `/android-coverage` — 全自动闭环（默认）
   - `/android-coverage report` — 只出报告
   - `/android-coverage <module>` — 指定模块
5. **模式选择逻辑** — numbered steps for argument parsing (match android-tdd pattern)

---

## Task 3: Write android-coverage SKILL.md — Phase 0 environment detection

**Files:**
- Modify: `.claude/skills/android-coverage/SKILL.md` (append Phase 0)

- [ ] **Step 1: Write Phase 0**

Follow the android-qa pattern for Phase 0:

1. **前置: 加载历史学习记录** — bootstrap + search relevant learnings (pitfall type, limit 5)
2. **步骤 1: 确定项目根目录和基准分支** — reference `android-shared/detection.md`, call `android-detect-env` with fallback to inline detection
3. **步骤 2: 检测 JaCoCo 配置** — scan `build.gradle.kts` for `jacoco` plugin and `testCoverageEnabled`, report found/not found
4. **步骤 3: 检测测试框架** — JUnit4/5, MockK, Robolectric, Espresso (reuse detection commands from android-tdd Phase 0)
5. **步骤 4: 检测模块结构** — parse `settings.gradle.kts` for `include(":xxx")` lines, determine single vs multi-module
6. **步骤 5: JaCoCo 自动引导 (按需)** — if JaCoCo not detected, offer auto-configuration (extract from android-tdd Phase 0.5, simplified to only JaCoCo config since test frameworks are already checked in step 3)

Output format: box-drawing summary table (same as android-tdd/android-qa).

---

## Task 4: Write android-coverage SKILL.md — Phase 1 baseline measurement

**Files:**
- Modify: `.claude/skills/android-coverage/SKILL.md` (append Phase 1)

- [ ] **Step 1: Write Phase 1**

Phase 1: 基线测量

1. **步骤 1: 运行测试+覆盖率报告**
   ```bash
   ./gradlew test<Variant>UnitTest create<Variant>UnitTestCoverageReport 2>&1 | tail -30
   ```
   For multi-module: iterate over modules, run each separately.

2. **步骤 2: 查找 JaCoCo 报告**
   ```bash
   find "$PROJECT_ROOT" -path "*/reports/jacoco/*/*.xml" -type f 2>/dev/null
   find "$PROJECT_ROOT" -path "*/reports/jacoco/*/index.html" -type f 2>/dev/null
   ```
   If no XML found: warn, suggest JaCoCo config, use test pass rate as fallback.

3. **步骤 3: 解析覆盖率数据**
   Parse JaCoCo XML to extract per-class coverage:
   - LINE coverage (missed/instructions attributes)
   - BRANCH coverage
   - METHOD coverage
   Group by module → class.

4. **步骤 4: 输出覆盖率仪表盘**
   Three-dimension dashboard (行/分支/方法):
   ```
   ╔══════════════════════════════════════════════════╗
   ║              覆盖率基线测量                      ║
   ╠══════════════════════════════════════════════════╣
   ║  行覆盖率:    67%   [████████░░░░░░░░] 阈值: 80% ║
   ║  分支覆盖率:  54%   [██████░░░░░░░░░░░] 阈值: 75% ║
   ║  方法覆盖率:  71%   [███████░░░░░░░░░░] 阈值: 80% ║
   ║  关键路径:    73%   [███████░░░░░░░░░░] 阈值: 90% ║
   ╚══════════════════════════════════════════════════╝
   ```
   Plus per-module breakdown table.

---

## Task 5: Write android-coverage SKILL.md — Phase 2 gap analysis

**Files:**
- Modify: `.claude/skills/android-coverage/SKILL.md` (append Phase 2)

- [ ] **Step 1: Write Phase 2**

Phase 2: 差距分析

1. **步骤 1: 分类未覆盖类**
   Read JaCoCo XML, for each class with coverage < threshold, classify by priority:
   - P0 (关键路径): filename matches `*ViewModel.kt`, `*Repository*.kt`, `*UseCase.kt`
   - P1 (工具类): `*Mapper.kt`, `*Util*.kt`, `*Extension*.kt`, `*Converter.kt`, data classes
   - P2 (UI): `*Screen.kt`, `*Activity.kt`, `*Fragment.kt`, `*Composable*.kt`

2. **步骤 2: 生成待补测试清单**
   Output a prioritized table:
   ```
   === 待补测试清单 (按优先级排序) ===
   #  | 优先级 | 类名                    | 当前行覆盖率 | 与阈值差距
   ---|--------|------------------------|-------------|----------
   1  | P0     | LoginViewModel.kt       | 45%         | -45%
   2  | P0     | AuthRepositoryImpl.kt   | 52%         | -38%
   3  | P1     | TokenMapper.kt          | 30%         | -50%
   ...
   ```

3. **步骤 3: 确定补写策略**
   Based on total gap size:
   - Gap ≤ 10%: 直接补写（预计 1-3 轮）
   - Gap 10-30%: 分批补写（预计 3-6 轮）
   - Gap > 30%: 大量补写（预计 6-10 轮）
   Report the estimated rounds to user.

---

## Task 6: Write android-coverage SKILL.md — Phase 3 auto-generate tests loop

**Files:**
- Modify: `.claude/skills/android-coverage/SKILL.md` (append Phase 3)

- [ ] **Step 1: Write Phase 3**

Phase 3: 自动补写测试（核心循环）

This is the longest section. Structure:

1. **循环控制** — define max rounds (10), convergence detection (2 consecutive rounds < 0.5% improvement), and exit conditions table

2. **收敛策略表:**
   | 轮次 | 每轮补写数量 | 选择策略 |
   |------|-------------|---------|
   | 1-3  | 5 个类      | 量大优先（覆盖率最低的优先） |
   | 4-6  | 3 个类      | 难度优先（P0 未达标优先） |
   | 7-10 | 1 个类      | 精细打磨（最难啃的） |

3. **每轮子流程:**
   - 步骤 A: 从待补清单取 Top-K 项
   - 步骤 B: 读取源码，分析未覆盖分支/方法
   - 步骤 C: 生成测试代码（写到对应 test 目录）
   - 步骤 D: 运行 `./gradlew test<Variant>UnitTest` 验证测试通过
   - 步骤 E: 运行覆盖率报告，解析结果
   - 步骤 F: 更新待补清单，计算本轮提升
   - 步骤 G: 输出本轮摘要

4. **测试生成规则** (reference android-tdd boundary matrix for test patterns):
   - ViewModel: test state transitions, error handling, loading states
   - Repository: test data mapping, error propagation, cache behavior
   - UseCase: test business logic, input validation, output formatting
   - Mapper/Converter: test all mapping branches including null/edge cases
   - Data classes: test equality, copy, default values
   - Extension functions: test each function with normal + edge inputs

5. **测试失败处理** — if generated test fails:
   - Round 1: auto-fix (imports, types, mock config)
   - Round 2: re-analyze source, regenerate test
   - Round 3: mark as "无法自动生成"，移到未达标清单

6. **每轮输出格式:**
   ```
   === Phase 3 · 第 N 轮 ===
   补写: 5 个类 (K 个测试)
   通过: K-1/K
   失败: 1 (已自动修复)
   覆盖率: 67% → 72% (+5%)
   进度: ████████░░░░░░░░ 72%/80%
   ```

7. **跳过条件** — `report` 模式跳过整个 Phase 3

---

## Task 7: Write android-coverage SKILL.md — Phase 4 verification + Phase 5 report

**Files:**
- Modify: `.claude/skills/android-coverage/SKILL.md` (append Phase 4 + Phase 5)

- [ ] **Step 1: Write Phase 4**

Phase 4: 最终验证

1. **步骤 1: 全量回归测试**
   ```bash
   ./gradlew test<Variant>UnitTest 2>&1 | tail -20
   ```
   Report pass/fail/skip counts. If any test fails: fix + re-run (max 2 attempts).

2. **步骤 2: 编译验收**
   ```bash
   ./gradlew assembleDebug 2>&1 | tail -10
   ```
   Must succeed. If fails: diagnose, fix, retry.

3. **步骤 3: 最终覆盖率快照**
   Re-run coverage report one final time, capture exact numbers.

- [ ] **Step 2: Write Phase 5**

Phase 5: 结果汇报

1. **步骤 1: 生成报告文件**
   Write to `docs/reviews/<branch>-coverage-report.md` with sections:
   - 摘要 (summary table with before/after)
   - 覆盖率仪表盘 (before → after, three dimensions)
   - 新增测试文件清单 (table: file, tests added, coverage contribution)
   - 未达标项清单 (if any)
   - Phase 3 循环记录 (per-round summary)

2. **步骤 2: 输出终端摘要**
   Box-drawing summary:
   ```
   ╔══════════════════════════════════════════════════╗
   ║              Coverage 完成                      ║
   ╠══════════════════════════════════════════════════╣
   ║  行覆盖率:    67% → 84%  ✅ (+17%)              ║
   ║  分支覆盖率:  54% → 78%  ✅ (+24%)              ║
   ║  关键路径:    73% → 93%  ✅ (+20%)              ║
   ║  新增测试:    23 个                               ║
   ║  耗时:        7 轮 / 10 轮上限                    ║
   ╚══════════════════════════════════════════════════╝
   ```

3. **步骤 3: 提交新增测试** (if in auto mode, not report mode)
   ```bash
   git add <new test files>
   git commit -m "test: auto-generated coverage tests (android-coverage)"
   ```

---

## Task 8: Write android-coverage SKILL.md — trailing sections (learnings, integration, error handling)

**Files:**
- Modify: `.claude/skills/android-coverage/SKILL.md` (append trailing sections)

- [ ] **Step 1: Write trailing sections**

Add these sections (following android-tdd/android-qa pattern):

1. **与其他 Skill 的衔接** — table:
   | Skill | 关系 | 说明 |
   |-------|------|------|
   | android-tdd | 平行 | tdd 聚焦「先写测试再写代码」，coverage 聚焦「补齐覆盖率」 |
   | android-qa | 平行 | qa 的覆盖率门控保持不变，coverage 是独立能力 |
   | android-worktree-runner | 无关 | coverage 在当前目录工作 |
   | android-benchmark | 平行 | 覆盖率 vs 性能，正交维度 |

2. **Capture Learnings** — two types:
   - `pitfall`: 覆盖率配置问题、测试生成失败模式、JaCoCo 兼容性问题
   - `technique`: 高效的测试补写策略、特定框架的覆盖率技巧
   - Use `"skill":"coverage"` in the JSON payload

3. **文件结构** — ASCII tree:
   ```
   <target-android-project>/
   ├─ app/src/test/...          ← 新增测试文件
   ├─ build/reports/jacoco/...  ← JaCoCo 覆盖率报告
   └─ docs/reviews/
      └─ <branch>-coverage-report.md  ← 覆盖率报告
   ```

4. **异常情况处理** — table:
   | 场景 | 处理方式 |
   |------|---------|
   | JaCoCo 未配置 | Phase 0 自动引导配置 |
   | 测试全部通过但覆盖率 0% | 检查 JaCoCo 版本兼容性 |
   | 自动生成的测试编译失败 | 3 轮修复后标记跳过 |
   | 模块间依赖导致测试失败 | 按模块隔离运行 |
   | Gradle sync 失败 | 提示用户手动 sync 后重试 |

- [ ] **Step 2: Commit android-coverage skill**

```bash
git add .claude/skills/android-coverage/SKILL.md
git commit -m "feat: add android-coverage skill — auto coverage loop for night mode"
```

---

## Task 9: Create android-benchmark skill directory

**Files:**
- Create: `.claude/skills/android-benchmark/` (directory)

- [ ] **Step 1: Create directory**

```bash
mkdir -p .claude/skills/android-benchmark
```

- [ ] **Step 2: Verify**

```bash
ls -la .claude/skills/android-benchmark/
```

---

## Task 10: Write android-benchmark SKILL.md — frontmatter + overview + invocation

**Files:**
- Create: `.claude/skills/android-benchmark/SKILL.md` (partial)

- [ ] **Step 1: Write frontmatter + 概述 + 调用方式**

```yaml
---
name: android-benchmark
description: |
  Android 性能 benchmark skill。在独立 worktree 中运行：交互选 commit → 测量基线 →
  性能诊断 → 输出报告+优化建议（默认）或全自动修复闭环（--auto）。
  混合方案: Jetpack Macrobenchmark 优先 + adb 命令行降级 + 静态分析兜底。
  适用场景: 性能回归检测、启动优化、帧率优化、内存泄漏排查。
voice-triggers:
  - "benchmark"
  - "性能测试"
  - "启动速度"
  - "帧率"
  - "内存分析"
---
```

Body sections:

1. **概述** — Worktree-isolated performance analysis. Default: report+suggestions. `--auto`: full closed-loop with compile verification.
2. **启动时声明** — `"我正在使用 android-benchmark skill。"`
3. **零外部依赖** — same pattern
4. **调用方式** — 6 modes in bash code block:
   - `/android-benchmark` — 默认报告模式
   - `/android-benchmark --auto` — 全自动闭环
   - `/android-benchmark cold-start` — 冷启动
   - `/android-benchmark jank` — 帧率
   - `/android-benchmark memory` — 内存
   - `/android-benchmark cold-start --target 300ms` — 自定义目标
5. **参数处理** — table with mode, arguments, behavior
6. **模式选择逻辑** — numbered steps parsing arguments (mode, scope, auto flag, custom target)

---

## Task 11: Write android-benchmark SKILL.md — Phase 0 worktree preparation

**Files:**
- Modify: `.claude/skills/android-benchmark/SKILL.md` (append Phase 0)

- [ ] **Step 1: Write Phase 0**

Phase 0: Worktree 准备

1. **前置: 加载历史学习记录** — same pattern as coverage

2. **步骤 1: 创建 worktree**
   ```bash
   BRANCH_NAME="bench-$(date +%Y%m%d-%H%M%S)"
   git worktree add ".claude/worktrees/$BRANCH_NAME" -b "$BRANCH_NAME"
   cd ".claude/worktrees/$BRANCH_NAME"
   ```
   If worktree already exists for this branch: warn and ask to reuse or create new.

3. **步骤 2: 列出最近 commit 供选择**
   ```bash
   git log --oneline -15
   ```
   Present as numbered list with commit hash, message, date.

4. **步骤 3: 询问用户选择**
   Use AskUserQuestion:
   - "选择要同步到 worktree 的 commit（可多选）"
   - List the 15 commits
   - Options: select individual commits, "all recent 5", "none (baseline only)"

5. **步骤 4: Cherry-pick 选中的 commit**
   ```bash
   git cherry-pick <commit-hash> --no-commit
   # or for multiple:
   for hash in $SELECTED_COMMITS; do git cherry-pick "$hash" --no-commit; done
   ```
   Handle conflicts: report to user, ask to resolve or skip.

6. **步骤 5: 检测 benchmark 基础设施**
   - Check for `:benchmark` module in `settings.gradle.kts`
   - Check for `androidx.benchmark:benchmark-macro-junit4` in dependencies
   - Check device connectivity: `adb devices`
   Determine which measurement tier to use (Macrobenchmark / adb / static).

---

## Task 12: Write android-benchmark SKILL.md — Phase 1 baseline measurement

**Files:**
- Modify: `.claude/skills/android-benchmark/SKILL.md` (append Phase 1)

- [ ] **Step 1: Write Phase 1**

Phase 1: 基线测量

1. **步骤 1: 确定测量维度**
   Based on scope argument:
   - No scope arg → all three (cold-start, jank, memory)
   - `cold-start` → only cold-start
   - `jank` → only frame timing
   - `memory` → only memory

2. **步骤 2: 测量 — 冷启动**

   **Tier 1 (Macrobenchmark available):**
   ```bash
   ./gradlew :benchmark:connectedCheck -Pandroid.testInstrumentationRunnerArguments.class=com.example.benchmark.StartupBenchmark 2>&1 | tail -20
   ```
   Parse output for `startupMs` median.

   **Tier 2 (adb available):**
   ```bash
   # Clear app state
   adb shell pm clear <package>
   # Cold start measurement (3 runs, take median)
   for i in 1 2 3; do
     adb shell am start -W -n <package>/.MainActivity 2>&1 | grep "TotalTime"
     adb shell am force-stop <package>
     sleep 2
   done
   ```
   Parse TotalTime from each run, compute median.

   **Tier 3 (static analysis):**
   Analyze Application.onCreate, MainActivity.onCreate for heavy operations. Estimate based on code complexity. Output: "无法实测，基于代码审查估算" with qualitative assessment.

3. **步骤 3: 测量 — 帧率/Jank**

   **Tier 1 (Macrobenchmark):**
   ```bash
   ./gradlew :benchmark:connectedCheck -Pandroid.testInstrumentationRunnerArguments.class=com.example.benchmark.FrameTimingBenchmark
   ```
   Parse `frameTime50thPercentileMs`, `jankRate`.

   **Tier 2 (adb + gfxinfo):**
   ```bash
   # Start app
   adb shell am start -n <package>/.MainActivity
   sleep 3
   # Trigger typical interaction (scroll, navigate)
   adb shell input swipe 500 1500 500 500 1000
   # Dump frame stats
   adb shell dumpsys gfxinfo <package> framestats
   ```
   Parse for jank percentage, frame time percentiles.

   **Tier 3 (static):** Analyze Compose recomposition patterns, RecyclerView adapter efficiency, layout nesting depth.

4. **步骤 4: 测量 — 内存**

   **Tier 1 (Macrobenchmark):** Parse memory tracking output.

   **Tier 2 (adb):**
   ```bash
   adb shell am start -n <package>/.MainActivity
   sleep 5
   adb shell dumpsys meminfo <package> | head -30
   ```
   Parse: Total RSS, Java Heap, Native Heap, Graphics.

   **Tier 3 (static):** Analyze Bitmap loading, singleton patterns, ViewModel scope, large collections.

5. **步骤 5: 输出基线仪表盘**
   ```
   ╔══════════════════════════════════════════════════╗
   ║              Benchmark 基线                      ║
   ╠══════════════════════════════════════════════════╣
   ║  冷启动 (P50):   620ms   [目标: <500ms]  ❌     ║
   ║  Jank%:          8.2%    [目标: <5%]    ❌     ║
   ║  内存峰值:       185MB   [目标: ≤204MB] ✅     ║
   ║  测量方式:       adb (Tier 2)                  ║
   ╚══════════════════════════════════════════════════╝
   ```

---

## Task 13: Write android-benchmark SKILL.md — Phase 2 performance diagnosis

**Files:**
- Modify: `.claude/skills/android-benchmark/SKILL.md` (append Phase 2)

- [ ] **Step 1: Write Phase 2**

Phase 2: 性能诊断

For each dimension that exceeds its target:

1. **冷启动诊断** (if cold-start > target):
   - Read `Application.onCreate` — look for: heavy initialization, disk I/O, network calls, SDK init
   - Read `MainActivity.onCreate` — look for: layout inflation, lazy loading, splash screen logic
   - Check `AndroidManifest.xml` for: `android:largeHeap`, content providers, `android:theme`
   - Read startup-related dependency injection modules
   - Output: ranked list of bottlenecks with estimated impact

2. **帧率/Jank 诊断** (if jank% > target):
   - Check for `LazyColumn`/`RecyclerView` without `key` parameters
   - Look for heavy computation in Compose recomposition scopes
   - Check for main-thread I/O (disk, network, database)
   - Analyze layout hierarchy depth (XML or Compose)
   - Look for `Dispatchers.Main` usage in hot paths
   - Output: ranked list of jank sources

3. **内存诊断** (if memory > target):
   - Check Bitmap loading: `Glide`/`Coil` config, no `.recycle()`, large image decoding
   - Check for singleton-scoped large objects
   - Check ViewModel stored state size
   - Look for unclosed resources (streams, cursors)
   - Check `RecyclerView` item view types and pool config
   - Output: ranked list of memory hotspots

4. **输出性能瓶颈清单:**
   ```
   === 性能瓶颈清单 ===
   #  | 维度   | 瓶颈位置                    | 估计影响   | 修复难度 |
   ---|--------|----------------------------|-----------|---------|
   1  | 冷启动 | Application.onCreate:Retrofit初始化 | +180ms | 低     |
   2  | 冷启动 | MainActivity:布局inflate    | +120ms    | 中     |
   3  | Jank   | HomeScreen:LazyColumn无key  | +3.5%     | 低     |
   4  | 内存   | ProfileScreen:Bitmap未recycle| +25MB     | 低     |
   ```

---

## Task 14: Write android-benchmark SKILL.md — Phase 3 auto-optimize loop

**Files:**
- Modify: `.claude/skills/android-benchmark/SKILL.md` (append Phase 3)

- [ ] **Step 1: Write Phase 3**

Phase 3: 自动优化（仅 `--auto` 模式）

1. **循环控制** — max 8 rounds, exit conditions:
   - All metrics reach targets
   - 2 consecutive rounds with no improvement
   - Max rounds reached
   - Non-`--auto` mode: skip entirely

2. **每轮子流程:**
   - 步骤 A: 取 Top-1 瓶颈 from 瓶颈清单
   - 步骤 B: 读取相关源码，理解上下文
   - 步骤 C: 生成优化代码（Edit tool）
   - 步骤 D: 编译验证 `./gradlew assembleDebug`
   - 步骤 E: 重跑受影响的 benchmark 指标
   - 步骤 F: 回归检测 — 重跑其他指标确保未退化
   - 步骤 G: 对比结果，更新瓶颈清单

3. **优化策略参考表:**

   | 瓶颈类型 | 优化方向 | 示例 |
   |---------|---------|------|
   | 冷启动-SDK初始化 | 延迟初始化、懒加载 | `lazy { Retrofit.Builder()... }` |
   | 冷启动-布局inflate | ViewStub、异步inflate、Compose 优化 | `SubcomposeLayout` |
   | 冷启动-磁盘IO | 后台线程、缓存 | `Dispatchers.IO` |
   | Jank-过度绘制 | 减少层级、`android:background=null` | 重组 Compose layout |
   | Jank-主线程IO | 挪到 IO dispatcher | `withContext(Dispatchers.IO)` |
   | Jank-重组过多 | `remember`/`derivedStateOf`/`key` | `LazyColumn(key = { it.id })` |
   | 内存-Bitmap | 缩放解码、`recycle()`、Glide/Coil 配置 | `requestBuilder.size(w,h)` |
   | 内存-泄漏 | WeakReference、Lifecycle感知、clearOnDestroy | `viewModel.clear()` |
   | 内存-大集合 | 分页、LRU缓存 | `Paging3` |

4. **回归检测规则:**
   - 优化冷启动 → 必须重跑内存检查（延迟初始化可能增加内存峰值）
   - 优化帧率 → 必须重跑内存检查（减少过度绘制可能增加绘制内存）
   - 优化内存 → 必须重跑帧率检查（Bitmap 缩小可能影响渲染）
   - 任何指标退化 > 10% → 回滚本次优化

5. **每轮输出:**
   ```
   === Phase 3 · 第 N 轮 ===
   优化: Application.onCreate 延迟初始化 Retrofit
   编译: ✅
   冷启动: 620ms → 540ms (-80ms)
   内存:   185MB → 190MB (+5MB, 未退化)
   回归:   ✅ 全部指标未退化
   进度:   2/3 指标达标
   ```

---

## Task 15: Write android-benchmark SKILL.md — Phase 4 verification + Phase 5 report

**Files:**
- Modify: `.claude/skills/android-benchmark/SKILL.md` (append Phase 4 + Phase 5)

- [ ] **Step 1: Write Phase 4**

Phase 4: 编译验收

1. **步骤 1: Debug + Release 编译**
   ```bash
   ./gradlew assembleDebug assembleRelease 2>&1 | tail -15
   ```

2. **步骤 2: 全量单元测试**
   ```bash
   ./gradlew test<Variant>UnitTest 2>&1 | tail -10
   ```
   If tests fail: fix + re-run (max 2 attempts).

3. **步骤 3: 最终 benchmark 快照** — re-measure all metrics one final time.

- [ ] **Step 2: Write Phase 5**

Phase 5: 结果汇报

1. **步骤 1: 生成报告文件**
   Write to `docs/reviews/<branch>-benchmark-report.md`:
   - 摘要 (summary table: before/after per metric)
   - 性能指标对比表 (metric, baseline, final, target, delta, status)
   - 优化操作清单 (table: round, bottleneck, change made, impact)
   - 回归检测结果
   - 未达标项清单 (if any)

2. **步骤 2: 输出终端摘要**
   ```
   ╔══════════════════════════════════════════════════╗
   ║              Benchmark 完成                     ║
   ╠══════════════════════════════════════════════════╣
   ║  冷启动:  620ms → 480ms  ✅ (-140ms, 目标 <500ms) ║
   ║  Jank%:   8.2% → 3.1%   ✅ (-5.1%, 目标 <5%)     ║
   ║  内存:    185MB → 178MB  ✅ (-7MB, 目标 ≤204MB)   ║
   ║  优化轮次: 4 / 8 上限                            ║
   ║  回归:    ✅ 无退化                                ║
   ╚══════════════════════════════════════════════════╝
   ```

3. **步骤 3: 提交优化代码** (if --auto mode)
   ```bash
   git add <modified files>
   git commit -m "perf: auto-optimized by android-benchmark (--auto)"
   ```

4. **步骤 4: Worktree 清理**
   Ask user: "Worktree `bench-<timestamp>` 处理完成。选择: A) 保留 worktree 和分支 B) 删除 worktree 和分支 C) 仅保留分支（删除 worktree 目录）"

---

## Task 16: Write android-benchmark SKILL.md — trailing sections + commit

**Files:**
- Modify: `.claude/skills/android-benchmark/SKILL.md` (append trailing sections)

- [ ] **Step 1: Write trailing sections**

1. **与其他 Skill 的衔接** — table:
   | Skill | 关系 | 说明 |
   |-------|------|------|
   | android-qa | 替代 | benchmark 替代 qa Layer 3.4 的极简性能检查 |
   | android-tdd | 平行 | 性能 vs 测试覆盖率，正交维度 |
   | android-coverage | 平行 | 覆盖率 vs 性能，正交维度 |
   | android-worktree-runner | 参考 | benchmark 自带 worktree，不依赖 runner |

2. **Capture Learnings** — two types:
   - `pitfall`: benchmark 配置问题、adb 命令兼容性、Macrobenchmark 陷阱
   - `technique`: 高效的优化策略、特定场景的性能模式
   - Use `"skill":"benchmark"` in the JSON payload

3. **文件结构** — ASCII tree:
   ```
   .claude/worktrees/bench-<timestamp>/  ← worktree 目录
   ├─ <optimized source files>
   └─ docs/reviews/
      └─ <branch>-benchmark-report.md    ← benchmark 报告
   ```

4. **异常情况处理** — table:
   | 场景 | 处理方式 |
   |------|---------|
   | 无设备连接 | 降级到 Tier 3 静态分析 |
   | Macrobenchmark 配置缺失 | 降级到 Tier 2 adb |
   | Cherry-pick 冲突 | 报告冲突，询问用户 |
   | 优化导致编译失败 | 回滚本次修改，标记瓶颈为"手动处理" |
   | 优化导致回归 | 回滚本次修改，跳过该瓶颈 |
   | Worktree 创建失败 | 检查 .git 目录权限 |

- [ ] **Step 2: Commit android-benchmark skill**

```bash
git add .claude/skills/android-benchmark/SKILL.md
git commit -m "feat: add android-benchmark skill — worktree-isolated perf analysis + auto-optimize"
```

---

## Task 17: Update CLAUDE.md routing table

**Files:**
- Modify: `CLAUDE.md` — add two new rows to Skill Routing table

- [ ] **Step 1: Add routing entries**

Add after the `android-qa` row:

```markdown
| 覆盖率、补测试、夜间测试 | `android-coverage` | "覆盖率"、"coverage"、"补测试"、"夜间测试" |
| 性能测试、benchmark、启动优化 | `android-benchmark` | "benchmark"、"性能测试"、"启动速度"、"帧率"、"内存分析" |
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add android-coverage and android-benchmark to CLAUDE.md routing"
```

---

## Task 18: Final review

- [ ] **Step 1: Spec coverage check**

Verify every section in the spec has a corresponding task:
- [x] android-coverage 调用方式 (3 modes) → Task 2
- [x] android-coverage Phase 0-5 → Tasks 3-7
- [x] android-coverage 覆盖率阈值 → Task 4
- [x] android-coverage report 模式 → Task 6
- [x] android-benchmark 调用方式 (6 modes) → Task 10
- [x] android-benchmark Phase 0-5 → Tasks 11-15
- [x] android-benchmark 默认目标 → Task 12
- [x] android-benchmark --auto 模式 → Task 14
- [x] android-benchmark worktree → Task 11
- [x] CLAUDE.md routing → Task 17
- [x] 与现有 skill 独立 → no modification tasks for tdd/qa/runner

- [ ] **Step 2: Placeholder scan**

Search plan for TBD, TODO, "implement later", "add appropriate" — none found.

- [ ] **Step 3: Verify files exist**

```bash
ls -la .claude/skills/android-coverage/SKILL.md .claude/skills/android-benchmark/SKILL.md
```
