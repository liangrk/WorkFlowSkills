---
name: android-benchmark
description: |
  Android 性能 benchmark skill。在独立 worktree 中运行：交互选 commit -> 测量基线 ->
  性能诊断 -> 输出报告+优化建议（默认）或全自动修复闭环（--auto）。
  混合方案: Jetpack Macrobenchmark 优先 + adb 命令行降级 + 静态分析兜底。
  适用场景: 性能回归检测、启动优化、帧率优化、内存泄漏排查。
voice-triggers:
  - "benchmark"
  - "性能测试"
  - "启动速度"
  - "帧率"
  - "内存分析"
---

# Android Benchmark

## 概述

Worktree 隔离的性能分析 skill。默认模式仅输出报告和优化建议，不修改代码。`--auto` 模式全自动闭环：自动修复 -> 编译验收 -> 回归检测。

**混合测量策略 (三级降级):**
- **Tier 1 (Macrobenchmark):** Jetpack Macrobenchmark 基准测试，数据最精确
- **Tier 2 (adb):** 通过 adb 命令行直接测量，无需额外配置
- **Tier 3 (static):** 静态代码分析，定性评估，无设备也可运行

**启动时声明:** "我正在使用 android-benchmark skill。"

**零外部依赖:** 仅使用 Claude Code 原生工具。不依赖 gstack、browse、Codex、Figma MCP。

## 调用方式

```bash
/android-benchmark                  # 默认: 报告+建议（不动代码）
/android-benchmark --auto           # 全自动闭环（修复+编译验收）
/android-benchmark cold-start       # 只测冷启动
/android-benchmark jank             # 只测帧率/Jank
/android-benchmark memory           # 只测内存
/android-benchmark cold-start --target 300ms  # 自定义目标
```

**参数处理:**

| 参数 | 说明 | 示例 |
|------|------|------|
| (无参数) | 测量全部维度，仅报告模式 | `/android-benchmark` |
| `--auto` | 全自动闭环模式（修复+编译验收） | `/android-benchmark --auto` |
| `cold-start` | 仅测量冷启动性能 | `/android-benchmark cold-start` |
| `jank` | 仅测量帧率/Jank | `/android-benchmark jank` |
| `memory` | 仅测量内存 | `/android-benchmark memory` |
| `--target <value>` | 自定义目标值（如 300ms、60fps） | `--target 300ms` |

**模式选择逻辑:**
1. 检查 `--auto` 标志 -> 全自动闭环模式 (Phase 0 -> Phase 5 全部执行)
2. 解析测量维度: `cold-start` / `jank` / `memory` / 无参数(全部)
3. 解析 `--target` 值作为自定义目标
4. 无 `--auto` -> 报告模式 (跳过 Phase 3 自动优化)

**默认目标值:**

| 维度 | 默认目标 | --target 格式 |
|------|---------|---------------|
| 冷启动 | 500ms | `--target 300ms` |
| 帧率/Jank | 95% 无卡顿 (<5% Jank) | `--target 98%` |
| 内存 | ≤ 基线 110% | `--target 200MB` |

---

## Phase 0: Worktree 准备（交互式）

在独立 worktree 中执行 benchmark，避免污染主分支。交互式选择要分析的 commit。

### 前置: 加载历史学习记录

**前置引导:** 若学习记录为空，先运行预加载:
```bash
bash .claude/skills/android-shared/bin/android-learnings-bootstrap 2>/dev/null || true
```

```bash
# 加载与 benchmark 相关的历史学习记录
LEARNINGS=$(bash .claude/skills/android-shared/bin/android-learnings-search --type pitfall --limit 5 2>/dev/null || true)
if [ -n "$LEARNINGS" ]; then
  echo "=== 相关学习记录 ==="
  echo "$LEARNINGS"
fi
```

如果找到相关学习记录，在 benchmark 配置和测量时注意这些已知的坑点（如 Macrobenchmark minSdk 要求、adb 权限问题、设备预热影响等）。

### 步骤 1: 创建 Worktree

```bash
# 生成时间戳
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
WORKTREE_NAME="bench-${TIMESTAMP}"
WORKTREE_PATH=".claude/worktrees/${WORKTREE_NAME}"

# 检查是否已存在同名 worktree
EXISTING=$(git worktree list 2>/dev/null | grep "$WORKTREE_NAME")
if [ -n "$EXISTING" ]; then
  echo "WARNING: Worktree '$WORKTREE_NAME' already exists"
  echo "Options: A) Reuse existing worktree  B) Create new worktree with different name"
  # AskUserQuestion: 选择 A 或 B
fi

# 创建 worktree
git worktree add "$WORKTREE_PATH" -b "$WORKTREE_NAME" HEAD
cd "$WORKTREE_PATH"
echo "WORKTREE: $WORKTREE_PATH"
echo "BRANCH: $WORKTREE_NAME"
```

### 步骤 2: 列出最近 Commit

```bash
# 列出最近 15 个 commit
echo "=== Recent Commits ==="
git log --oneline -15
```

### 步骤 3: 询问用户选择

将 commit 列表呈现给用户，使用 AskUserQuestion 工具提供以下选项:

```
请选择要 benchmark 的 commit:
1. abc1234 feat: add login screen
2. def5678 fix: crash on rotation
...
15. opq9012 chore: update dependencies

选项:
- 输入编号选择单个 commit (如 "1")
- 输入多个编号选择多个 commit (如 "1,3,5")
- 输入 "all" 选择最近 5 个 commit
- 输入 "none" 仅使用当前 HEAD 作为基线（不 cherry-pick）
```

### 步骤 4: Cherry-pick 选择的 Commit

对用户选择的每个 commit 执行 cherry-pick (不自动 commit，便于后续合并):

```bash
# 示例: cherry-pick 选择的 commit
for HASH in $SELECTED_COMMITS; do
  if ! git cherry-pick "$HASH" --no-commit 2>&1; then
    echo "CONFLICT: Cherry-pick of $HASH failed"
    echo "Conflicting files:"
    git diff --name-only --diff-filter=U
    # AskUserQuestion: A) 手动解决冲突  B) 跳过此 commit  C) 中止
    # 如果用户选择跳过: git cherry-pick --abort
    # 如果用户选择中止: 退出流程
  fi
done

# 如果有未提交的更改 (成功 cherry-pick 的内容)
CHANGES=$(git diff --cached --stat 2>/dev/null)
if [ -n "$CHANGES" ]; then
  echo "=== Cherry-picked Changes ==="
  echo "$CHANGES"
fi
```

### 步骤 5: 检测 Benchmark 基础设施

确定可用的测量层级 (Tier 1/2/3):

```bash
# --- 检查 :benchmark 模块 ---
BENCHMARK_MODULE=$(grep -E "include.*:benchmark" settings.gradle* 2>/dev/null)
if [ -n "$BENCHMARK_MODULE" ]; then
  echo "BENCHMARK_MODULE: FOUND"
else
  echo "BENCHMARK_MODULE: NOT_FOUND"
fi

# --- 检查 Macrobenchmark 依赖 ---
MACRO_DEP=$(grep -r "androidx.benchmark:benchmark-macro-junit4" --include="*.gradle*" 2>/dev/null | head -3)
if [ -n "$MACRO_DEP" ]; then
  echo "MACROBENCHMARK_DEP: FOUND"
  echo "$MACRO_DEP"
else
  echo "MACROBENCHMARK_DEP: NOT_FOUND"
fi

# --- 检查设备连接 ---
DEVICES=$(adb devices 2>/dev/null | grep -v "List of devices" | grep -v "^$" | grep "device$")
if [ -n "$DEVICES" ]; then
  DEVICE_COUNT=$(echo "$DEVICES" | wc -l)
  echo "ADB_DEVICES: $DEVICE_COUNT connected"
  echo "$DEVICES"
else
  echo "ADB_DEVICES: NONE"
fi

# --- 确定测量层级 ---
if [ -n "$BENCHMARK_MODULE" ] && [ -n "$MACRO_DEP" ] && [ -n "$DEVICES" ]; then
  echo "MEASUREMENT_TIER: 1 (Macrobenchmark)"
elif [ -n "$DEVICES" ]; then
  echo "MEASUREMENT_TIER: 2 (adb commands)"
else
  echo "MEASUREMENT_TIER: 3 (static analysis only)"
fi

# --- 获取包名 ---
PACKAGE_NAME=$(grep -r "applicationId" app/build.gradle* 2>/dev/null | head -1 | sed 's/.*applicationId[[:space:]]*[\"'"'"']*\([a-z.]*\)[\"'"'"']*.*/\1/')
if [ -z "$PACKAGE_NAME" ]; then
  PACKAGE_NAME=$(grep -r "namespace" app/build.gradle* 2>/dev/null | head -1 | sed 's/.*namespace[[:space:]]*[\"'"'"']*\([a-z.]*\)[\"'"'"']*.*/\1/')
fi
echo "PACKAGE_NAME: $PACKAGE_NAME"
```

---

## Phase 1: 基线测量

根据参数确定的维度和检测到的测量层级，执行基线测量。

### 步骤 1: 确定测量维度

```
测量维度:
- cold-start (冷启动): scope 参数为 "cold-start" 或无参数(全部)
- jank (帧率/Jank): scope 参数为 "jank" 或无参数(全部)
- memory (内存): scope 参数为 "memory" 或无参数(全部)
```

### 步骤 2: 测量 - 冷启动

**Tier 1 (Macrobenchmark):**

```bash
# 运行 Macrobenchmark 冷启动测试
./gradlew :benchmark:connectedCheck 2>&1 | tail -50

# 解析结果
# 从 benchmark 输出中提取 startupMs
# 示例输出: startupMs    min 245.2, median 267.8, max 312.4
```

解析 Macrobenchmark 输出中的 `startupMs` 指标，取 median 值。

**Tier 2 (adb):**

```bash
# 冷启动测量 - 3 次取中位数
echo "=== Cold Start Measurement (3 runs) ==="
for i in 1 2 3; do
  # 清除应用状态
  adb shell am force-stop "$PACKAGE_NAME"
  adb shell pm clear "$PACKAGE_NAME" 2>/dev/null || true

  # 测量启动时间
  RESULT=$(adb shell am start-activity -W -n "$PACKAGE_NAME/.MainActivity" 2>&1)
  TOTAL_TIME=$(echo "$RESULT" | grep "TotalTime" | awk '{print $2}')
  WAIT_TIME=$(echo "$RESULT" | grep "WaitTime" | awk '{print $2}')
  echo "Run $i: TotalTime=${TOTAL_TIME}ms, WaitTime=${WAIT_TIME}ms"
done

# 计算中位数
echo "MEDIAN: $(echo "$TIMES" | sort -n | awk 'NR==2{print}')"
```

**Tier 3 (static analysis):**

```bash
# 分析 Application.onCreate
APP_ONCREATE=$(find . -path "*/main/java/*" -name "Application.kt" -o -name "*Application.kt" 2>/dev/null | head -5)
echo "=== Application Class ==="
echo "$APP_ONCREATE"

# 分析 MainActivity.onCreate
MAIN_ACTIVITY=$(find . -path "*/main/java/*" -name "MainActivity.kt" -o -name "MainActivity.java" 2>/dev/null | head -3)
echo "=== MainActivity ==="
echo "$MAIN_ACTIVITY"
```

读取 Application.onCreate 和 MainActivity.onCreate，分析以下重操作:
- SDK 初始化 (Firebase, Analytics, Crashlytics 等)
- 数据库初始化 / Room migration
- 网络 API 调用
- 大量 SharedPreferences 读取
- 依赖注入框架初始化
- ContentProvider 自动初始化

输出定性评估:
```
冷启动定性评估 (Tier 3):
- Application.onCreate: 检测到 3 个 SDK 初始化 + 1 次数据库读取
- MainActivity.onCreate: 检测到布局膨胀 (ConstraintLayout, 5 层嵌套)
- AndroidManifest: 检测到 2 个 ContentProvider
- 估计冷启动时间: 800ms-1200ms (中等到较慢)
```

### 步骤 3: 测量 - 帧率/Jank

**Tier 1 (Macrobenchmark):**

```bash
# 运行 Macrobenchmark 帧率测试
./gradlew :benchmark:connectedCheck 2>&1 | tail -50

# 解析 FrameTimingMetric
# 示例输出: frameDuration50thPercentile, frameDuration90thPercentile, jankRate
```

**Tier 2 (adb):**

```bash
# 重置帧率统计
adb shell dumpsys gfxinfo "$PACKAGE_NAME" reset

# 执行一些操作后收集帧率数据
adb shell dumpsys gfxinfo "$PACKAGE_NAME" framestats 2>&1

# 解析 jank 百分比
# 重点关注:
# - Janky frames: 超过 16.67ms 的帧
# - 90th percentile: 90% 帧的耗时
# - 95th percentile: 95% 帧的耗时
echo "=== Frame Stats ==="
echo "Jank percentage: $(计算结果)%"
echo "90th percentile: $(计算结果)ms"
```

**Tier 3 (static analysis):**

分析以下帧率影响因素:
- LazyColumn / RecyclerView 是否设置了 `key` 参数
- Compose 重组范围: 搜索 `mutableStateOf` / `mutableLiveData` / `StateFlow` 在 Composable 中的使用
- 主线程 IO: 搜索 `Dispatchers.Main` 中的网络/数据库调用
- 布局深度: 分析 XML layout 嵌套层级
- 自定义 View 的 `onDraw` 复杂度

输出定性评估:
```
帧率定性评估 (Tier 3):
- LazyColumn: 发现 3 处缺少 key 参数 (可能导致不必要的重组)
- 主线程 IO: 发现 2 处在 Dispatchers.Main 中执行数据库查询
- 布局深度: 最大嵌套 8 层 (建议 < 5 层)
- 估计 Jank 率: 15%-25% (较差)
```

### 步骤 4: 测量 - 内存

**Tier 1 (Macrobenchmark):**

```bash
# 运行 Macrobenchmark 内存跟踪测试
./gradlew :benchmark:connectedCheck 2>&1 | tail -50

# 解析内存指标
# 示例输出: memoryRssMb, javaHeapAllocMb, nativeHeapAllocMb
```

**Tier 2 (adb):**

```bash
echo "=== Memory Info ==="
adb shell dumpsys meminfo "$PACKAGE_NAME" 2>&1

# 提取关键指标
# - Total RSS: 总常驻内存
# - Java Heap: Java 堆内存
# - Native Heap: Native 堆内存
# - Graphics: 图形内存
# - Stack: 栈内存
# - SQLite: SQLite 内存
echo "=== Key Metrics ==="
echo "Total RSS:    $(提取值) MB"
echo "Java Heap:    $(提取值) MB"
echo "Native Heap:  $(提取值) MB"
echo "Graphics:     $(提取值) MB"
```

**Tier 3 (static analysis):**

分析以下内存影响因素:
- Bitmap 加载: 搜索 `BitmapFactory` / `Glide` / `Coil` / `ImageLoader`，检查是否设置了 `inSampleSize`、`resize`
- 单例模式: 搜索 `object` 声明和 `companion object` 中持有大对象
- ViewModel 状态大小: 搜索 `ViewModel` 中的 `MutableStateFlow` / `MutableLiveData` 持有的集合大小
- 大集合: 搜索 `List` / `Map` / `ArrayList` 在内存中的大小
- 资源泄漏: 搜索未关闭的 `InputStream` / `Cursor` / `Connection`

输出定性评估:
```
内存定性评估 (Tier 3):
- Bitmap 加载: 发现 4 处未设置 inSampleSize (可能加载原始分辨率)
- 单例: 发现 2 个单例持有缓存集合 (未设上限)
- ViewModel: 1 个 ViewModel 持有最大 1000 条的列表 (建议使用 Paging3)
- 估计峰值内存: 150MB-250MB (中等到较高)
```

### 步骤 5: 输出基线仪表盘

```
╔════════════════════════════════════════════════════════════════════╗
║                       性能基线仪表盘                              ║
╠════════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  维度          基线值        目标          状态     测量层级       ║
║  ─────────────────────────────────────────────────────────────── ║
║  冷启动        267ms        500ms         ✅ 达标   Tier 1        ║
║  帧率/Jank     87% 无卡顿   95% 无卡顿    ❌ 未达标 Tier 2        ║
║  内存(RSS)     185MB        ≤204MB        ✅ 达标   Tier 2        ║
║                                                                  ║
║  测量环境: Pixel 7 / API 34 / Release 构建                      ║
║  Worktree: bench-20260410-143000                                ║
╚════════════════════════════════════════════════════════════════════╝
```

---

## Phase 2: 性能诊断

对每个超过目标的维度进行深入诊断，找出瓶颈并排序。

### 步骤 1: 冷启动诊断

读取以下关键文件并分析瓶颈:

```bash
# 读取 Application 类
# 读取 MainActivity
# 读取 AndroidManifest.xml (ContentProvider 数量、theme 设置)
# 读取 DI 模块 (Hilt/Koin module)
```

**诊断清单:**

| # | 检查项 | 位置 | 影响 | 难度 |
|---|--------|------|------|------|
| 1 | SDK 初始化 | Application.onCreate | 高 | 低 |
| 2 | 数据库初始化 | Application.onCreate | 高 | 中 |
| 3 | 网络预加载 | Application.onCreate | 中 | 低 |
| 4 | ContentProvider 自动启动 | AndroidManifest | 中 | 中 |
| 5 | 布局膨胀 | MainActivity.onCreate | 高 | 低 |
| 6 | 懒加载缺失 | MainActivity.onCreate | 中 | 低 |
| 7 | DI 模块初始化 | DI Module | 高 | 中 |

**输出格式:**

```
冷启动瓶颈排名:
1. [高影响/低难度] Application.onCreate 中 Firebase 初始化阻塞主线程 (~120ms)
   位置: app/src/main/java/com/example/MyApp.kt:42
   建议: 使用 FirebaseInitializer + StartIntent

2. [高影响/中难度] Room 数据库 migration 在启动时执行 (~200ms)
   位置: app/src/main/java/com/example/MyApp.kt:58
   建议: 异步执行 migration，使用 fallback 数据

3. [中影响/低难度] 布局膨胀 5 层嵌套 (~80ms)
   位置: app/src/main/res/layout/activity_main.xml
   建议: 使用 ViewStub 或 Compose 替换
```

### 步骤 2: 帧率/Jank 诊断

读取相关 Compose/XML 文件，分析 jank 来源:

**诊断清单:**

| # | 检查项 | 影响 | 难度 |
|---|--------|------|------|
| 1 | LazyColumn/RecyclerView 无 key | 高 | 低 |
| 2 | Compose 过度重组 | 高 | 中 |
| 3 | 主线程 IO | 高 | 低 |
| 4 | 布局深度过大 | 中 | 中 |
| 5 | 自定义 View.onDraw 复杂 | 中 | 中 |
| 6 | Dispatchers.Main 热路径 | 高 | 低 |
| 7 | 过度绘制 | 中 | 中 |

**输出格式:**

```
帧率瓶颈排名:
1. [高影响/低难度] LazyColumn 缺少 key 参数导致全量重组
   位置: app/src/main/java/com/example/HomeScreen.kt:87
   建议: 为每个 item 添加 stable key

2. [高影响/低难度] 主线程执行数据库查询
   位置: app/src/main/java/com/example/DetailViewModel.kt:34
   建议: 使用 Dispatchers.IO 或 Room 的 suspend 函数

3. [中影响/中难度] Compose 重组范围过大
   位置: app/src/main/java/com/example/FeedScreen.kt:56
   建议: 使用 remember 和 derivedStateOf 缩小重组范围
```

### 步骤 3: 内存诊断

读取 Bitmap 加载、缓存、ViewModel 相关代码:

**诊断清单:**

| # | 检查项 | 影响 | 难度 |
|---|--------|------|------|
| 1 | Bitmap 未缩放加载 | 高 | 低 |
| 2 | 单例缓存无上限 | 高 | 低 |
| 3 | ViewModel 状态过大 | 中 | 中 |
| 4 | 未关闭的资源 | 高 | 低 |
| 5 | RecyclerView pool 未配置 | 低 | 低 |
| 6 | 大集合未分页 | 中 | 中 |
| 7 | 内存泄漏 (WeakReference) | 高 | 中 |

**输出格式:**

```
内存瓶颈排名:
1. [高影响/低难度] Bitmap 加载未设置 inSampleSize，原始分辨率解码
   位置: app/src/main/java/com/example/ImageLoader.kt:23
   建议: 使用 Glide/Coil 的 resize 或 BitmapFactory.Options.inSampleSize

2. [高影响/低难度] CacheManager 单例持有无限增长的 HashMap
   位置: app/src/main/java/com/example/CacheManager.kt:15
   建议: 替换为 LruCache(maxSize = 50MB)

3. [中影响/中难度] FeedViewModel 持有最多 1000 条 item 的列表
   位置: app/src/main/java/com/example/FeedViewModel.kt:28
   建议: 使用 Paging3 替代
```

### 步骤 4: 输出性能瓶颈清单

```
╔════════════════════════════════════════════════════════════════════╗
║                       性能瓶颈清单                                ║
╠════════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  #  维度      瓶颈位置                    估计影响  修复难度      ║
║  ─────────────────────────────────────────────────────────────── ║
║  1  冷启动    MyApp.kt:42 Firebase 阻塞    ~120ms   低            ║
║  2  冷启动    MyApp.kt:58 Room migration   ~200ms   中            ║
║  3  帧率      HomeScreen.kt:87 无 key      ~15%     低            ║
║  4  帧率      DetailVM.kt:34 主线程 DB     ~10%     低            ║
║  5  内存      ImageLoader.kt:23 未缩放     ~50MB    低            ║
║  6  内存      CacheManager.kt:15 无限缓存  ~30MB    低            ║
║                                                                  ║
╚════════════════════════════════════════════════════════════════════╝
```

---

## Phase 3: 自动优化（仅 --auto 模式）

> **非 --auto 模式跳过此 Phase。** 报告模式直接进入 Phase 4。

### 循环控制

```
最大轮次: 8 轮
退出条件:
- 所有维度均达标 -> 退出并进入 Phase 4
- 连续 2 轮无改善 -> 退出 (标记为收敛)
- 达到最大轮次 -> 退出 (标记为达到上限)
```

### 每轮子步骤

**A) 选取 Top-1 瓶颈**

从 Phase 2 的瓶颈清单中选择最高优先级（影响 x 1/难度）的未处理瓶颈。

**B) 读取源代码**

```bash
# 读取瓶颈相关文件
# 分析当前实现
```

**C) 生成优化代码**

使用 Edit 工具直接修改源代码。遵循以下优化策略表:

| 瓶颈类型 | 优化策略 | 具体操作 |
|----------|---------|---------|
| 冷启动 - SDK 初始化 | 延迟初始化 | 使用 `Lazy` / `StartIntent` / `AppInitializer` 延迟非关键 SDK |
| 冷启动 - 布局膨胀 | ViewStub / 异步膨胀 | 使用 `ViewStub` 延迟加载非首屏布局，或 `AsyncLayoutInflater` |
| 冷启动 - IO 阻塞 | 后台线程 | 将 `Application.onCreate` 中的 IO 操作移到 `Dispatchers.IO` |
| 帧率 - 过度绘制 | 减少层级 | 移除不必要的背景色、使用 `ViewCompat.setLayerType`、减少布局嵌套 |
| 帧率 - 主线程 IO | Dispatchers.IO | 将数据库查询、文件读写移到 `withContext(Dispatchers.IO)` |
| 帧率 - 重组 | remember / derivedStateOf / key | 使用 `remember` 缓存计算结果、`derivedStateOf` 缩小重组范围、`key` 稳定标识 |
| 内存 - Bitmap | 缩放 / 回收 / 配置 | 使用 `inSampleSize`、`Bitmap.recycle()`、配置 Glide/Coil 的 `memoryCache` 和 `diskCache` |
| 内存 - 泄漏 | WeakReference / 生命周期感知 | 使用 `WeakReference`、`LifecycleObserver`、避免 Activity Context 泄漏 |
| 内存 - 大集合 | Paging3 / LRU | 替换大 `List` 为 `Paging3`，替换无限缓存为 `LruCache` |

**D) 编译验证**

```bash
./gradlew assembleDebug 2>&1 | tail -20
```

编译失败 -> 回滚修改，标记此瓶颈为 "优化失败"，选择下一个瓶颈。

**E) 重新测量受影响的维度**

仅重新测量本轮优化影响的维度。例如优化了冷启动，则只重测冷启动。

**F) 回归检测**

检查其他维度是否因优化而退化:

```
回归检测规则:
- 优化冷启动 -> 重新检查内存 (延迟初始化可能增加峰值内存)
- 优化帧率 -> 重新检查内存 (减少层级可能影响绘制内存)
- 优化内存 -> 重新检查帧率 (缩小 Bitmap 可能影响渲染质量)

任何维度回归 >10% -> 自动回滚本轮修改
```

**G) 对比并更新瓶颈清单**

```
╔════════════════════════════════════════════════════════════════════╗
║                    Round 1/8 优化结果                             ║
╠════════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  瓶颈: MyApp.kt:42 Firebase 阻塞初始化                          ║
║  策略: 延迟初始化 (AppInitializer)                               ║
║                                                                  ║
║  冷启动:  267ms -> 187ms  (-80ms)  ✅ 改善                      ║
║  帧率:    87% -> 87%      (无变化) ✅ 无回归                     ║
║  内存:    185MB -> 188MB  (+3MB)   ✅ 无回归 (<10%)              ║
║                                                                  ║
║  编译: ✅ assembleDebug 成功                                     ║
║  状态: 继续下一轮                                                ║
╚════════════════════════════════════════════════════════════════════╝
```

---

## Phase 4: 编译验收

验证优化后的代码完整性和正确性。

### 步骤 1: Debug + Release 编译

```bash
./gradlew assembleDebug assembleRelease 2>&1 | tail -30
```

两个构建变体均需成功。失败则进入异常处理流程。

### 步骤 2: 单元测试

```bash
# 确定构建变体
VARIANT="Debug"

# 运行单元测试
./gradlew test${VARIANT}UnitTest 2>&1 | tail -30
```

记录测试结果:
```
单元测试: 142 passed, 0 failed, 3 skipped
```

### 步骤 3: 最终 Benchmark 快照

重新测量所有维度，作为最终结果:

```bash
# 根据测量层级执行对应测量
# Tier 1: ./gradlew :benchmark:connectedCheck
# Tier 2: adb 测量命令
# Tier 3: 静态分析
```

---

## Phase 5: 结果汇报

生成完整报告并清理 worktree。

### 步骤 1: 写入报告文件

写入 `docs/reviews/<branch>-benchmark-report.md`:

```markdown
# 性能 Benchmark 报告: <branch>

> 生成于 <YYYY-MM-DD HH:mm> | android-benchmark
> 模式: 报告模式 / 全自动闭环 (--auto)
> 测量层级: Tier 1 (Macrobenchmark) / Tier 2 (adb) / Tier 3 (static)

## 摘要

| 维度 | 基线 | 最终 | 变化 | 目标 | 状态 |
|------|------|------|------|------|------|
| 冷启动 | 267ms | 187ms | -80ms | 500ms | ✅ |
| 帧率/Jank | 87% | 94% | +7% | 90% | ✅ |
| 内存(RSS) | 185MB | 162MB | -23MB | -- | ✅ |

## 性能指标对比表

### 冷启动

| 指标 | 基线 | 最终 | 变化 |
|------|------|------|------|
| TotalTime | 267ms | 187ms | -80ms (-30%) |
| WaitTime | 312ms | 221ms | -91ms (-29%) |

### 帧率/Jank

| 指标 | 基线 | 最终 | 变化 |
|------|------|------|------|
| 无卡顿帧率 | 87% | 94% | +7% |
| 90th percentile | 22ms | 14ms | -8ms |

### 内存

| 指标 | 基线 | 最终 | 变化 |
|------|------|------|------|
| Total RSS | 185MB | 162MB | -23MB |
| Java Heap | 68MB | 55MB | -13MB |
| Native Heap | 45MB | 42MB | -3MB |
| Graphics | 38MB | 30MB | -8MB |

## 优化操作清单

| 轮次 | 维度 | 瓶颈 | 策略 | 效果 | 文件 |
|------|------|------|------|------|------|
| 1 | 冷启动 | Firebase 阻塞 | 延迟初始化 | -80ms | MyApp.kt |
| 2 | 帧率 | LazyColumn 无 key | 添加 key | +5% | HomeScreen.kt |
| 3 | 内存 | Bitmap 未缩放 | Glide resize | -15MB | ImageLoader.kt |

## 回归检测结果

| 维度 | 优化前 | 优化后 | 变化 | 状态 |
|------|--------|--------|------|------|
| 冷启动 | 267ms | 187ms | -30% | ✅ |
| 帧率 | 87% | 94% | +7% | ✅ |
| 内存 | 185MB | 162MB | -12% | ✅ |

所有维度无回归 (>10%)。

## 未达标项

| 维度 | 当前值 | 目标值 | 差距 | 建议 |
|------|--------|--------|------|------|
| -- | -- | -- | -- | 全部达标 |

## Phase 3 循环记录 (仅 --auto)

| 轮次 | 瓶颈 | 维度变化 | 状态 |
|------|------|---------|------|
| Round 1 | Firebase 延迟初始化 | 冷启动 -80ms | 改善 |
| Round 2 | LazyColumn key | 帧率 +5% | 改善 |
| Round 3 | Glide resize | 内存 -15MB | 改善 |

总优化: 3 轮
总改善: 冷启动 -30%, 帧率 +7%, 内存 -12%
```

### 步骤 2: 终端摘要

```
╔════════════════════════════════════════════════════════════════════╗
║                    性能 Benchmark 摘要                            ║
╠════════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  分支: bench-20260410-143000                                     ║
║  模式: 全自动闭环 (--auto)                                       ║
║  测量层级: Tier 2 (adb)                                          ║
║                                                                  ║
║  冷启动:  267ms -> 187ms  (-30%)   ✅ 目标 500ms                 ║
║  帧率:    87%  -> 96%    (+9%)    ✅ 目标 95%                    ║
║  内存:    185MB -> 162MB  (-12%)   ✅ 目标 ≤204MB (≤基线110%)    ║
║                                                                  ║
║  优化轮次: 3 轮                                                 ║
║  回归检测: ✅ 全部通过                                           ║
║  编译验证: ✅ Debug + Release 成功                                ║
║  单元测试: ✅ 142 passed                                         ║
║                                                                  ║
║  完整报告: docs/reviews/bench-20260410-143000-benchmark-report.md║
╚════════════════════════════════════════════════════════════════════╝
```

### 步骤 3: 提交优化代码（仅 --auto 模式）

> **报告模式跳过此步骤。**

```bash
# 收集修改的文件
MODIFIED_FILES=$(git diff --name-only 2>/dev/null)

if [ -n "$MODIFIED_FILES" ]; then
  git add $MODIFIED_FILES
  git commit -m "$(cat <<'EOF'
perf: auto-optimized by android-benchmark (--auto)

Optimizations:
- Cold start: Firebase lazy init (-80ms)
- Jank: LazyColumn key (+5% smooth frames)
- Memory: Glide resize config (-15MB RSS)

Before: 267ms / 87% / 185MB
After:  187ms / 94% / 162MB

Generated by android-benchmark skill.
EOF
)"
  echo "Commit: $(git rev-parse --short HEAD)"
fi
```

### 步骤 4: Worktree 清理

使用 AskUserQuestion 询问用户:

```
Worktree 清理选项:
A) 保留 worktree 和分支 (稍后手动处理)
B) 删除 worktree 目录和分支 (完全清理)
C) 仅保留分支 (删除 worktree 目录)
```

```bash
# 选项 A: 不做任何操作
# 选项 B:
git worktree remove "$WORKTREE_PATH"
git branch -D "$WORKTREE_NAME"

# 选项 C:
git worktree remove "$WORKTREE_PATH"
# 分支保留
```

---

## 与其他 Skill 的衔接

| Skill | 关系 | 说明 |
|-------|------|------|
| android-qa | 替代 Layer 3.4 | QA 流程的 Layer 3.4 性能检测可由本 skill 替代，提供更专业的性能分析 |
| android-tdd | 互补 | TDD 中 Phase 5 的覆盖率门禁之后可运行 benchmark 确保性能未退化 |
| android-coverage | 互补 | 覆盖率提升后可运行 benchmark 验证性能未退化。两者独立运行互不干扰 |
| android-worktree-runner | 上游 | worktree-runner 在任务执行完成后可自动调用本 skill 进行性能验证 |

---

## Capture Learnings

Benchmark 流程完成后，将过程中的发现记录到学习系统以供未来 session 参考。

**记录时机:**

1. **发现 benchmark 配置问题** -- 如 Macrobenchmark minSdk 不匹配、benchmark 模块配置错误、adb 权限不足导致测量失败，记录为 pitfall:
   ```bash
   bash .claude/skills/android-shared/bin/android-learnings-log '{"skill":"benchmark","type":"pitfall","key":"<配置问题简述>","insight":"<问题描述和解决方案>","confidence":8,"source":"observed","files":["<配置文件>"]}'
   ```

2. **发现 adb 兼容性问题** -- 如特定 Android 版本的 dumpsys 输出格式不同、设备特定限制，记录为 pitfall:
   ```bash
   bash .claude/skills/android-shared/bin/android-learnings-log '{"skill":"benchmark","type":"pitfall","key":"<adb兼容问题简述>","insight":"<问题描述和绕过方案>","confidence":7,"source":"observed","files":[]}'
   ```

3. **发现高效优化策略** -- 如某个优化策略效果特别显著、某种性能模式有通用解法，记录为 technique:
   ```bash
   bash .claude/skills/android-shared/bin/android-learnings-log '{"skill":"benchmark","type":"technique","key":"<策略名>","insight":"<策略描述>","confidence":7,"source":"inferred","files":["<相关文件>"]}'
   ```

**不记录:**
- 常规的 benchmark 测量过程
- 与历史记录完全重复的发现
- 已知且已在历史记录中的优化策略

---

## 文件结构

```
项目根目录/
├── .claude/
│   └── worktrees/
│       └── bench-<timestamp>/            ← 本 skill 创建的 worktree
│           ├── app/
│           │   ├── build.gradle.kts
│           │   └── src/
│           │       ├── main/
│           │       │   ├── java/com/example/
│           │       │   │   ├── *Application.kt      ← 冷启动诊断目标
│           │       │   │   ├── *MainActivity.kt     ← 冷启动诊断目标
│           │       │   │   ├── *ViewModel.kt        ← 帧率/内存诊断
│           │       │   │   └── *Screen.kt           ← 帧率诊断
│           │       │   └── AndroidManifest.xml      ← ContentProvider 检查
│           │       └── test/                       ← Phase 4 单元测试
│           ├── benchmark/                         ← Tier 1 Macrobenchmark (可选)
│           │   └── src/
│           │       └── androidTest/
│           │           └── ...Benchmark.kt
│           ├── build.gradle.kts
│           └── settings.gradle.kts                ← 模块检测
├── docs/
│   └── reviews/
│       └── bench-<timestamp>-benchmark-report.md  ← 本 skill 产出的报告
└── .claude/
    └── skills/
        └── android-benchmark/
            └── SKILL.md                           ← 本文件
```

---

## 异常情况处理

| 场景 | 处理方式 |
|------|----------|
| 无设备连接 (adb devices 为空) | 降级到 Tier 3 静态分析，输出定性评估。报告中标注 "无设备，仅静态分析" |
| 无 Macrobenchmark 配置 | 降级到 Tier 2 adb 测量。报告中标注 "Macrobenchmark 未配置，使用 adb 降级方案" |
| Cherry-pick 冲突 | 报告冲突文件列表，AskUserQuestion: A) 手动解决 B) 跳过此 commit C) 中止 |
| 优化后编译失败 | 自动回滚本轮修改 (`git checkout -- .`)，标记瓶颈为 "优化失败"，选择下一个瓶颈 |
| 优化导致回归 (>10%) | 自动回滚本轮修改，记录为 "回滚: 回归 >10%"，选择下一个瓶颈 |
| Worktree 创建失败 | 检查磁盘空间和 git 版本。如果 `.claude/worktrees/` 目录已存在同名目录，提示用户清理 |
| Gradle 构建超时 | 终止当前轮次，提交已完成的结果，报告中标注 "因构建超时提前终止" |
| 单元测试失败 (Phase 4) | 报告失败的测试，标记为 "优化导致测试失败"，提供失败测试列表和可能原因 |
| 所有维度已达标 | 立即退出优化循环，进入 Phase 4 验收 |
| 连续 2 轮无改善 | 退出优化循环，标记为 "收敛"，报告中标注 "已达性能瓶颈" |
| 测量数据波动大 (>15%) | 增加 adb 测量次数到 5 次，取中位数。Macrobenchmark 增加迭代次数 |
