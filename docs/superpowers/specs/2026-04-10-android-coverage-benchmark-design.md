# Android Coverage + Benchmark Skills Design Spec

**Date:** 2026-04-10
**Status:** Draft
**Author:** liangrk + Claude Opus 4.6

## Problem Statement

当前 Android skill chain 缺少两个独立的能力：

1. **独立覆盖率 skill** — 覆盖率检查嵌入在 `android-tdd` Phase 5 和 `android-qa` Layer 2.4 中，逻辑重复且不能脱离 TDD/QA 流程独立运行。夜间无人值守场景（跑完全部覆盖率 + 自动补测试 + 验证）无法实现。

2. **Android Benchmark skill** — 全局 `benchmark` skill 是纯 Web（gstack 浏览器 daemon，测 TTFB/FCP/LCP），与 Android 完全无关。`android-qa` Layer 3.4 只有极简的冷启动+内存检查，缺乏 Jetpack Benchmark 集成和深度性能分析能力。

## Goal

创建两个独立的 Android skill：

1. **android-coverage** — 全自动覆盖率闭环，可独立运行，专为夜间无人值守设计
2. **android-benchmark** — 在独立 worktree 中运行的性能分析+优化 skill，混合 Jetpack Benchmark + adb 命令行

两个 skill 与现有的 android-tdd/android-qa **完全独立**，不修改现有 skill 的覆盖率逻辑。

## Design

### Deliverables

| File | Change Type | Description |
|------|------------|-------------|
| `.claude/skills/android-coverage/SKILL.md` | New | 独立覆盖率闭环 skill |
| `.claude/skills/android-benchmark/SKILL.md` | New | 独立性能 benchmark skill |
| `CLAUDE.md` | Modify | Skill routing 表增加两个新条目 |

---

### android-coverage

#### 调用方式

| 命令 | 行为 |
|------|------|
| `/android-coverage` | 全自动闭环（默认） |
| `/android-coverage report` | 只出报告，不动代码 |
| `/android-coverage <module>` | 指定模块运行 |

#### 工作流

**Phase 0: 环境检测**
- 检测 JaCoCo 插件（复用 `android-shared/detection.md` Section 6.4）
- 未配置则自动引导配置（提取自 android-tdd Phase 0.5 的逻辑）
- 检测测试框架（JUnit4/5, MockK, Robolectric, Espresso）
- 检测模块结构（单模块 vs 多模块）

**Phase 1: 基线测量**
- 运行 `./gradlew test<Variant>UnitTest create<Variant>UnitTestCoverageReport`
- 解析 JaCoCo XML → 按模块/类/方法汇总
- 输出覆盖率仪表盘（行/分支/方法三维度）

**Phase 2: 差距分析（Gap Analysis）**
- 按优先级排序未覆盖的类/方法：
  - P0: ViewModel, Repository, UseCase（关键路径）
  - P1: 数据类、工具类、扩展函数
  - P2: UI 组件、Compose 预览
- 生成「待补测试清单」

**Phase 3: 自动补写测试（循环，最多 10 轮）**

收敛策略：
- 前 3 轮：每轮补 5 个类（量大优先）
- 4-6 轮：每轮补 3 个类（难度优先）
- 7-10 轮：每轮补 1 个类（精细打磨）

每轮流程：
1. 取 Top-K 未覆盖项
2. 分析源码，生成测试
3. 运行测试 + 覆盖率
4. 解析结果，更新待补清单

退出条件（任一）：
- 所有指标达到阈值
- 连续 2 轮覆盖率提升 < 0.5%
- 达到最大轮次（10 轮）

**Phase 4: 最终验证**
- 全量运行一次测试（确保无 regression）
- 编译验收：`./gradlew assembleDebug`
- 输出最终报告 → `docs/reviews/<branch>-coverage-report.md`

**Phase 5: 结果汇报**
- 覆盖率仪表盘（before → after 对比）
- 新增测试文件清单
- 未达标项清单（如有）

#### 覆盖率阈值

沿用 android-tdd 的标准：

| 指标 | 阈值 |
|------|------|
| 总体行覆盖率 | 80% |
| 关键路径覆盖率 | 90%（ViewModel, Repository, UseCase） |
| 分支覆盖率 | 75% |

#### 报告模式（report）

`/android-coverage report` 跳过 Phase 3（自动补写），直接从 Phase 2 进入 Phase 4 输出报告。适合快速了解覆盖率现状。

---

### android-benchmark

#### 调用方式

| 命令 | 行为 |
|------|------|
| `/android-benchmark` | 交互选 commit → 测量 → 诊断 → 出报告+优化建议，不动代码 |
| `/android-benchmark --auto` | 交互选 commit → 测量 → 诊断 → 自动修复闭环 → 编译验收 |
| `/android-benchmark cold-start` | 只测冷启动 |
| `/android-benchmark jank` | 只测帧率/Jank |
| `/android-benchmark memory` | 只测内存 |

#### 工作流

**Phase 0: Worktree 准备（交互式）**
- 创建独立 worktree（`bench-<timestamp>`）
- 列出最近 N 个 commit，询问用户同步哪些进来
- Cherry-pick 选中的 commit 到 worktree

**Phase 1: 基线测量**

检测 benchmark 基础设施（自动降级）：

| 优先级 | 方式 | 条件 |
|--------|------|------|
| 1 | Jetpack Macrobenchmark（Gradle target） | 项目已配置 benchmark module |
| 2 | adb 命令行 | 设备/模拟器已连接 |
| 3 | 静态分析 | 无设备，基于代码审查 |

测量维度：
- **冷启动**：`adb shell am start -W` 或 Macrobenchmark StartupMetric
- **帧率/Jank**：GPU profiling 或 Macrobenchmark FrameTimingMetric
- **内存**：`dumpsys meminfo` 或 Macrobenchmark 内存追踪

每个指标运行 3 次取中位数，记录基线。

**Phase 2: 性能诊断**

根据测量结果，定位瓶颈：

- 冷启动 > 目标 → Startup Tracing → 定位耗时操作（Application.onCreate、懒加载、IO）
- Jank% > 目标 → GPU profiling → 定位掉帧场景（过度绘制、布局嵌套、主线程 IO）
- 内存 > 目标 → Heap dump 分析 → 定位泄漏/膨胀（长生命周期引用、Bitmap 未回收）

输出「性能瓶颈清单」。

**Phase 3: 自动优化（仅 `--auto` 模式，循环最多 8 轮）**

每轮流程：
1. 取 Top-1 瓶颈
2. 生成优化代码
3. 编译
4. 重跑 benchmark
5. 对比：优化后 vs 基线 + 回归检测（优化 A 不能退化指标 B）

退出条件（任一）：
- 所有指标达到目标
- 连续 2 轮无改善
- 达到最大轮次（8 轮）

非 `--auto` 模式：跳过 Phase 3，直接进入 Phase 4。

**Phase 4: 编译验收**
- `./gradlew assembleDebug` + `assembleRelease`
- 运行全量单元测试（确保优化没引入 bug）
- 最终 benchmark 报告 → `docs/reviews/<branch>-benchmark-report.md`

**Phase 5: 结果汇报**
- 性能指标对比表（before → after）
- 优化操作清单（改了什么、为什么）
- Worktree 清理选项（保留/删除）

#### 默认性能目标

| 指标 | 目标 | 说明 |
|------|------|------|
| 冷启动（P50） | < 500ms | 从 am start -W 的 TotalTime |
| Jank% | < 5% | 掉帧比例 |
| 内存峰值 | ≤ 基线 110% | 防止优化引入内存膨胀 |

用户可在调用时自定义目标，如 `/android-benchmark cold-start --target 300ms`。

---

### 与现有 skill 的关系

| 关系 | 说明 |
|------|------|
| android-coverage ↔ android-tdd | 独立。coverage 聚焦「补齐覆盖率」，tdd 聚焦「先写测试再写代码」 |
| android-coverage ↔ android-qa | 独立。qa 的覆盖率门控保持不变 |
| android-benchmark ↔ android-qa | 独立。benchmark 替代 qa Layer 3.4 的极简性能检查，提供深度分析 |
| android-coverage ↔ android-worktree-runner | coverage 在当前目录工作，不创建 worktree |
| android-benchmark ↔ android-worktree-runner | benchmark 自带 worktree，复用 worktree 模式但不依赖 runner |

---

### 共享依赖

两个 skill 共同依赖：
- `android-shared/detection.md` — 环境检测（JaCoCo、测试框架、模块结构）
- `android-shared/bin/android-learnings-log` — 学习记录
- Gradle wrapper（目标 Android 项目中）

## Non-Goals

- 不修改现有 android-tdd/android-qa 中的覆盖率逻辑
- 不做 CI/CD 集成（GitHub Actions, GitLab CI）
- 不做 UI 截图对比（由 gstack/browser 工具处理）
- 不做电量profiling（batterystats 需要真实设备长时间运行，不适合自动化闭环）
- 不做 APK 大小分析（属于 build 优化范畴，非运行时性能）
