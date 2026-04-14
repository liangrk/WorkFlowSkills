---
name: android-benchmark
description: |
  Android 性能基准: 冷启动/帧率/内存。--auto 全自动闭环。
  适用场景: 性能分析、优化验证。
---

# Android Benchmark

**调用:** `/android-benchmark` | `--auto` | `cold-start` | `jank` | `memory`

## Phase 0: Worktree 创建

```bash
git worktree add ".claude/worktrees/bench-$(date +%s)" -b "bench/<slug>"
# Gradle 环境预热
```

## Phase 1: 基线测量

```
三级降级:
  Tier 1: Macrobenchmark (已配置) → 3次取中位数
  Tier 2: adb (有设备) → am start-activity -W / dumpsys gfxinfo / dumpsys meminfo
  Tier 3: 静态分析 (无设备) → 代码审查定性评估

维度:
  - 冷启动: <500ms
  - Jank: <5%
  - 内存: ≤基线110%
```

## Phase 2: 性能诊断

```
定位瓶颈 → 按影响/难度排序
```

## Phase 3: 自动优化 (--auto 专属)

```
max 8轮:
  每轮优化 Top-1 瓶颈
  回归检测
```

## Phase 4: 编译验收

```bash
./gradlew assembleDebug assembleRelease 2>&1
./gradlew testDebugUnitTest 2>&1
```

## Phase 5: 结果

```
docs/reviews/<branch>-benchmark-report.md:
  性能对比表
  优化清单
  worktree 清理选项
```

## Capture Learnings

```bash
bash "$SHARED_BIN/android-learnings-log" '{"skill":"benchmark","type":"technique","key":"KEY","insight":"INSIGHT","confidence":8,"source":"observed","files":[]}'
```
