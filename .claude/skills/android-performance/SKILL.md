---
name: android-performance
description: |
  Android 性能分析 skill。系统化排查 ANR、内存泄漏、启动耗时、
  帧率卡顿、电量消耗、网络性能、APK 大小等性能问题。
  四层分析: 症状->工具->根因->优化。
invocation: /android-performance <问题描述>
args: [问题描述]
voice-triggers:
  - "性能分析"
  - "ANR"
  - "内存泄漏"
  - "启动慢"
  - "卡顿"
  - "耗电"
---

# Android Performance

## 概述

对 Android 项目进行系统化的性能分析。覆盖 ANR、内存泄漏、启动耗时、
帧率卡顿、电量消耗、网络性能、APK 大小等七大性能维度。

采用四层分析方法: 症状采集 -> 工具诊断 -> 根因定位 -> 优化方案。
根据问题类型自动选择对应的分析工具和数据采集命令。

**启动时声明:** "我正在使用 android-performance skill。"

**零外部依赖:** 仅使用 Claude Code 原生工具 (Read、Grep、Glob、Bash、Edit)。
不依赖 gstack、browse、Codex、MCP 工具。adb 命令可选，无设备时降级为静态分析。

## 调用方式

```bash
/android-performance <问题描述>         # 描述性能问题，开始分析
/android-performance ANR               # 直接指定问题类型
/android-performance 内存泄漏           # 中文问题类型
/android-performance 启动慢             # 简短描述
/android-performance                   # 交互式模式，询问问题详情
```

**参数处理:**

| 调用方式 | 行为 |
|----------|------|
| `/android-performance <问题描述>` | 将描述作为问题上下文，进入 Phase 0 分类 |
| `/android-performance` | 进入交互模式，询问问题类型和详情 |

**交互模式提示语:**

```
请描述遇到的性能问题:

1. 问题类型? (ANR / 内存泄漏 / 启动慢 / 卡顿 / 耗电 / 网络慢 / 包太大 / 其他)
2. 何时发生? (特定操作后 / 启动时 / 后台运行时 / 随机)
3. 问题频率? (必现 / 偶发 / 仅在特定设备)
4. 最近是否修改了相关代码?
```

---

## Phase 0: 问题分类 + 环境检测

### 步骤 1: 问题分类

根据输入关键词自动分类问题类型:

| 关键词 | 类型 | 优先工具 |
|--------|------|---------|
| ANR / 无响应 / not responding / 应用卡死 | ANR | logcat ANR trace, traces.txt |
| 内存 / OOM / Memory / leak / 泄漏 / 内存泄漏 | 内存 | LeakCanary, Profiler, dumpsys meminfo |
| 启动 / 冷启动 / Startup / 启动慢 / 慢 | 启动 | systrace, am start-activity -W |
| 卡顿 / 帧率 / Jank / 掉帧 / 流畅度 | 帧率 | GPU profiler, Choreographer, Systrace |
| 电量 / 电池 / Battery / 耗电 | 电量 | Battery Historian, dumpsys batterystats |
| 网络 / 请求慢 / API / 超时 | 网络 | Network profiler, OkHttp logging |
| 大小 / APK / 包大小 / 安装包 / 体积 | 包大小 | APK Analyzer, R8, resources.arsc |
| 通用 / 变慢 / 性能 / performance / 慢 | 通用 | 综合分析 |

分类结果输出:
```
=== 问题分类 ===

问题类型:     内存泄漏
优先工具:     LeakCanary, Android Studio Profiler, dumpsys meminfo
分析策略:     内存专项分析
```

### 步骤 2: 环境检测

```bash
# 项目环境
bash .claude/skills/android-shared/bin/android-detect-env 2>/dev/null || true

# 设备连接
adb devices 2>/dev/null | head -5 || echo "ADB_NOT_AVAILABLE"

# 构建工具
./gradlew --version 2>/dev/null | head -3 || echo "GRADLE_NOT_AVAILABLE"
```

根据环境检测结果确定分析模式:
- **有设备:** 使用 adb 实时采集数据 + 静态分析
- **无设备:** 仅使用静态代码分析，报告中标注 "无设备，仅静态分析"

---

## Phase 1: 症状采集

根据问题类型，采集对应的症状数据。所有命令设置 10 秒超时，失败时优雅降级。

### ANR 症状采集

```bash
# 获取 ANR traces (需要 root 或 pull 权限)
adb pull /data/anr/traces.txt /tmp/ 2>/dev/null && echo "TRACES_PULLED" || echo "NO_ROOT_ACCESS"

# 最近 ANR 事件
adb logcat -d -b events 2>/dev/null | grep "am_anr" | tail -20 || echo "LOGCAT_EVENTS_UNAVAILABLE"

# ANR 相关日志
adb logcat -d 2>/dev/null | grep -i "ANR\|not responding\|Input dispatching timed out" | tail -30 || echo "LOGCAT_UNAVAILABLE"

# 搜索代码中可能导致 ANR 的模式
grep -rn "runBlocking\|withContext(Dispatchers.Main)\|Thread.sleep\|synchronized\|wait(" app/src/main --include="*.kt" | head -20
grep -rn "getWritableDatabase\|getReadableDatabase\|query(" app/src/main --include="*.kt" | head -10
```

### 内存症状采集

```bash
# 内存概况
adb shell dumpsys meminfo <package> 2>/dev/null | head -30 || echo "MEMINFO_UNAVAILABLE"

# 检查 LeakCanary 集成
grep -r "leakcanary" app/build.gradle* 2>/dev/null || echo "LEAKCANARY_NOT_FOUND"

# Bitmap 使用模式
grep -rn "Bitmap\|bitmap\|decodeResource\|BitmapFactory" app/src/main --include="*.kt" -l | head -10

# Context 泄漏风险
grep -rn "context\|Context\|applicationContext" app/src/main --include="*.kt" | grep -v "import\|//" | grep -E "companion|object|static|Singleton" | head -15

# 集合增长风险
grep -rn "ArrayList\|HashMap\|mutableListOf\|mutableMapOf" app/src/main --include="*.kt" | grep -v "import\|//" | grep -E "add\|put\|+=" | head -15

# 协程 scope 风险
grep -rn "GlobalScope\|CoroutineScope\|viewModelScope\|lifecycleScope" app/src/main --include="*.kt" | head -15
```

### 启动症状采集

```bash
# 测量启动时间 (有设备时)
adb shell am start-activity -W -n <package>/<activity> 2>&1 || echo "START_MEASURE_UNAVAILABLE"

# Application.onCreate 重操作
grep -rn "class.*Application" app/src/main --include="*.kt" -A 30 | head -50

# ContentProvider 自动初始化
grep -rn "ContentProvider" app/src/main --include="*.kt" | head -10
grep "ContentProvider" app/src/main/AndroidManifest.xml 2>/dev/null | head -10

# SDK 初始化
grep -rn "Firebase\|Analytics\|Crashlytics\|Bugly\|Umeng" app/src/main --include="*.kt" | head -10
```

### 帧率症状采集

```bash
# Compose 性能模式
grep -rn "LazyColumn\|LazyRow\|remember\|mutableStateOf\|LaunchedEffect\|derivedStateOf" app/src/main --include="*.kt" -l | head -10

# 布局嵌套深度
find app/src/main/res/layout -name "*.xml" -exec grep -l "LinearLayout\|ConstraintLayout\|FrameLayout" {} \; 2>/dev/null | head -10

# 过度绘制风险
grep -rn "setBackground\|background=\|setBackgroundColor\|setBackgroundColorResource" app/src/main --include="*.kt" --include="*.xml" | head -10

# 主线程 IO
grep -rn "Dispatchers.Main" app/src/main --include="*.kt" | grep -v "import" | head -15

# RecyclerView/Compose key
grep -rn "RecyclerView.Adapter\|@Composable.*items\|LazyColumn\s*{" app/src/main --include="*.kt" | head -10
```

### 电量症状采集

```bash
# WakeLock 使用
grep -rn "WakeLock\|PARTIAL_WAKE_LOCK\|newWakeLock" app/src/main --include="*.kt" | head -10

# 后台工作
grep -rn "WorkManager\|ForegroundService\|AlarmManager\|JobScheduler\|startForeground" app/src/main --include="*.kt" | head -15

# 位置更新
grep -rn "requestLocationUpdates\|FusedLocation\|LocationManager" app/src/main --include="*.kt" | head -10

# 网络轮询
grep -rn "setRepeat\|setInterval\|Timer\|ScheduledExecutor\|fixedRate\|fixedDelay" app/src/main --include="*.kt" | head -10
```

### 网络症状采集

```bash
# 网络库配置
grep -rn "OkHttp\|Retrofit\|HttpLoggingInterceptor\|cache\|Cache" app/src/main --include="*.kt" | head -20

# 序列化库
grep -rn "Gson\|Moshi\|kotlinx.serialization\|@SerializedName" app/src/main --include="*.kt" | head -10

# 网络超时配置
grep -rn "connectTimeout\|readTimeout\|writeTimeout\|callTimeout" app/src/main --include="*.kt" | head -10

# 并发请求
grep -rn "async\|awaitAll\|awaitAny\|zip\|combine\|parallel" app/src/main --include="*.kt" | head -10
```

### 包大小症状采集

```bash
# APK 构建
./gradlew :app:assembleDebug 2>/dev/null
ls -lh app/build/outputs/apk/debug/*.apk 2>/dev/null || echo "APK_NOT_FOUND"

# 大资源文件
find app/src/main/res -type f \( -name "*.png" -o -name "*.jpg" -o -name "*.webp" \) | xargs ls -lhS 2>/dev/null | head -20

# 资源压缩配置
grep -rn "shrinkResources\|minifyEnabled\|isShrinkResources\|isMinifyEnabled" app/build.gradle* 2>/dev/null || echo "NO_SHRINK_CONFIG"

# Native libraries
find app/src/main/jniLibs -type f -name "*.so" 2>/dev/null | xargs ls -lhS 2>/dev/null | head -10

# 多语言/多密度资源
find app/src/main/res -type d | grep -E "values-[a-z]{2}|drawable-.*dpi|mipmap-.*dpi" | head -20
```

### Phase 1 输出

```
=== 症状采集摘要 ===

问题类型:     内存泄漏
采集状态:     ADB 部分可用 (meminfo 成功, LeakCanary 未集成)
代码扫描:     发现 15 个潜在内存风险点

关键发现:
  1. CacheManager 单例持有 HashMap (无大小限制)
  2. 3 处 Bitmap 未设置 inSampleSize
  3. 2 处 Context 被静态变量引用
  4. 1 处 viewModelScope 外使用 GlobalScope

下一步: 进入 Phase 2 深度分析
```

---

## Phase 2: 深度分析

对 Phase 1 采集的数据进行深度分析。读取相关源代码文件，追踪数据流，定位根因。

### 分析方法

读取 Phase 1 发现的每个风险点涉及的源文件，进行以下分析:

1. **数据流追踪:** 从数据创建到释放的完整生命周期
2. **引用链分析:** 检查是否有未断开的引用链导致对象无法回收
3. **生命周期匹配:** 检查对象生命周期是否超出其容器生命周期
4. **量级评估:** 评估问题对性能的实际影响程度

### ANR 深度分析要点

1. ANR 发生的主线程堆栈 -- 哪个操作阻塞了主线程?
2. 是否是死锁? (检查 BLOCKED/WAITING 状态)
3. 是否是 I/O 操作在主线程? (数据库查询、文件读写、网络请求)
4. 是否是 Binder 调用超时?
5. 是否是锁竞争?

### 内存深度分析要点

1. Java Heap vs Native Heap 分布
2. Bitmap 内存占用和回收策略
3. Context/View 泄漏模式 (静态引用、单例持有、监听器未注销)
4. 集合类增长模式 (ArrayList/HashMap 无限增长)
5. 协程 scope 未取消导致隐式引用
6. 资源未关闭 (InputStream/Cursor/Connection)

### 启动深度分析要点

1. Application.onCreate 中的重操作及其耗时
2. ContentProvider 自动初始化链
3. DI 模块初始化顺序和依赖
4. 首帧布局膨胀复杂度
5. 主题/样式加载开销

### 帧率深度分析要点

1. Compose 重组范围和频率
2. LazyColumn/RecyclerView 的 item 稳定性和复用
3. 主线程上的 I/O 和计算操作
4. 布局嵌套深度和过度绘制
5. 自定义 View 的 onMeasure/onDraw/onLayout 复杂度

### 电量深度分析要点

1. WakeLock 持有时长和释放逻辑
2. 后台任务调度频率和必要性
3. 位置更新的频率和精度要求
4. 网络轮询间隔是否合理
5. ForegroundService 使用是否合规

### 网络深度分析要点

1. 请求 payload 大小和响应体大小
2. 并发请求管理和连接池配置
3. 缓存策略 (ETag/Cache-Control/本地缓存)
4. 重试策略和超时配置
5. 序列化/反序列化开销

### 包大小深度分析要点

1. 资源文件格式优化空间 (PNG->WebP, 矢量图)
2. 未使用资源的检测和清理
3. R8/ProGuard 混淆和裁剪效果
4. Native library 架构支持 (ABI split)
5. 动态功能模块拆分可能性

### Phase 2 输出

```
=== 深度分析结果 ===

问题类型: 内存泄漏

发现列表:

[BLOCKER] (confidence: 9/10) CacheManager.kt:15
  描述: 单例 CacheManager 持有无限增长的 HashMap，无 eviction 策略
  影响: 长时间使用后内存持续增长，预计每小时增长 20-50MB
  引用链: CacheManager.instance -> cacheMap -> Entry -> (Bitmap/DTO)

[WARNING] (confidence: 7/10) ProfileScreen.kt:89
  描述: Composable 中使用 remember 保存大列表引用，屏幕旋转时不释放
  影响: 旋转屏幕时内存翻倍
  引用链: ProfileScreen (remember) -> userList (List<UserProfile>)

[WARNING] (confidence: 6/10) ImageLoader.kt:23
  描述: BitmapFactory.decodeResource 未设置 inSampleSize，全尺寸加载
  影响: 加载 4K 图片时单张占用 30-50MB
  引用链: ImageLoader -> BitmapFactory -> Bitmap (全尺寸)

[INFO] (confidence: 5/10) LocationService.kt:45
  描述: GlobalScope.launch 在 Service 销毁后继续运行
  影响: Service 泄漏，协程持有 Service 引用
  引用链: GlobalScope -> coroutine -> LocationService (leaked)

根因总结: CacheManager 无限缓存 + Bitmap 未缩放 + Context 泄漏
```

---

## Phase 3: 优化方案

根据 Phase 2 的分析结果，生成具体的优化方案。按优先级和性价比排序。

### 优先级分类

| 优先级 | 标准 | 标记 |
|--------|------|------|
| 高 | 直接影响用户体验，修复简单 | HIGH |
| 中 | 改善明显，修复适中 | MEDIUM |
| 低 | 锦上添花，需较大改动 | LOW |

### 优化方案模板

```
## 优化方案

### 高优先级 (直接影响用户体验)

1. [HIGH] 替换 CacheManager 的 HashMap 为 LruCache
   - 预期改善: 内存峰值降低 50-100MB
   - 修改文件: app/src/main/java/.../CacheManager.kt
   - 修改方案:
     ```kotlin
     // Before
     private val cacheMap = HashMap<String, CacheEntry>()

     // After
     private val cache = LruCache<String, CacheEntry>(50 * 1024 * 1024) // 50MB
     ```

2. [HIGH] 为 BitmapFactory 设置 inSampleSize
   - 预期改善: 图片内存降低 60-75%
   - 修改文件: app/src/main/java/.../ImageLoader.kt
   - 修改方案:
     ```kotlin
     val options = BitmapFactory.Options().apply {
       inJustDecodeBounds = true
       BitmapFactory.decodeResource(res, resId, this)
       inSampleSize = calculateInSampleSize(this, targetWidth, targetHeight)
       inJustDecodeBounds = false
     }
     ```

### 中优先级 (改善明显)

3. [MEDIUM] 使用 Glide/Coil 替代手动 Bitmap 加载
   - 预期改善: 自动管理内存和缓存，减少 OOM 风险
   - 修改文件: app/src/main/java/.../ImageLoader.kt, 相关 Adapter/Composable
   - 注意: 需要全局替换，影响范围较广

4. [MEDIUM] 替换 GlobalScope 为 lifecycleScope
   - 预期改善: 消除 Service 泄漏
   - 修改文件: app/src/main/java/.../LocationService.kt

### 低优先级 (锦上添花)

5. [LOW] 优化 Composable remember 策略
   - 预期改善: 旋转屏幕时减少内存波动
   - 修改文件: app/src/main/java/.../ProfileScreen.kt

### 需要架构调整

6. [ARCH] 引入 Paging3 替代全量列表加载
   - 预期改善: 列表页内存降低 80%+
   - 影响范围: ViewModel + Repository + UI 层
   - 建议: 单独作为 feature 任务规划
```

### 风险评估

```
=== 优化风险评估 ===

| # | 优化项 | 风险等级 | 影响范围 | 回滚难度 |
|---|--------|---------|---------|---------|
| 1 | LruCache | 低 | CacheManager | 简单 |
| 2 | inSampleSize | 低 | ImageLoader | 简单 |
| 3 | Glide/Coil | 中 | 全局图片加载 | 中等 |
| 4 | lifecycleScope | 低 | LocationService | 简单 |
| 5 | remember 优化 | 低 | ProfileScreen | 简单 |
| 6 | Paging3 | 高 | 多个列表页面 | 复杂 |
```

---

## Phase 4: 学习记录

将发现的性能模式记录到学习系统，供未来 session 参考。

**记录时机:**

1. **发现性能反模式** -- 记录为 pitfall:
   ```bash
   bash .claude/skills/android-shared/bin/android-learnings-log '{"skill":"android-performance","type":"pitfall","key":"<反模式简述>","insight":"<问题描述和触发条件>","confidence":8,"source":"observed","files":["<相关文件>"]}'
   ```

2. **发现高效优化策略** -- 记录为 technique:
   ```bash
   bash .claude/skills/android-shared/bin/android-learnings-log '{"skill":"android-performance","type":"technique","key":"<策略名>","insight":"<策略描述和适用场景>","confidence":7,"source":"inferred","files":["<相关文件>"]}'
   ```

**不记录:**
- 临时的设备性能问题 (如设备过热降频)
- 第三方库的性能 bug (除非有项目特有 workaround)
- 已知且已在历史记录中的性能模式

---

## 产出

### 产出物: 性能分析报告

写入 `docs/reviews/<branch>-performance-report.md`:

```markdown
# 性能分析报告: <问题标题>

> 生成于 <YYYY-MM-DD HH:mm> | android-performance
> 问题类型: ANR / 内存泄漏 / 启动慢 / 帧率 / 电量 / 网络 / 包大小 / 通用
> 分析模式: ADB + 静态分析 / 仅静态分析

## 摘要

| 指标 | 结果 |
|------|------|
| 问题类型 | 内存泄漏 |
| 发现数量 | 4 个 (1 BLOCKER, 2 WARNING, 1 INFO) |
| 最高优先级 | HIGH |
| 估计改善 | 内存峰值降低 50-100MB |
| 分析模式 | 静态分析 (无设备) |

## 症状采集

<Phase 1 采集的关键数据和发现>

## 深度分析

<Phase 2 的分析结果和根因>

## 优化方案

<Phase 3 的优化建议和风险评估>

## 验证方法

<如何确认优化有效>
```

### 产出物路径

```
docs/reviews/
└── <branch>-performance-report.md    <- 本次性能分析报告
```

---

## 与其他 Skill 的衔接

| Skill | 关系 | 说明 |
|-------|------|------|
| android-investigate | 互补 | investigate 发现性能类问题后路由到本 skill |
| android-benchmark | 互补 | benchmark 量化性能指标，本 skill 定性分析根因 |
| android-qa | 上游 | QA 发现性能问题后调用本 skill 深入分析 |
| android-code-review | 下游 | 优化方案确认后可进行 code review |
| android-autoplan | 下游 | 大规模优化可拆分为 plan 执行 |
| android-worktree-runner | 下游 | 优化实施可在 worktree 中隔离进行 |

### 与 android-benchmark 的区别

| 维度 | android-performance | android-benchmark |
|------|-------------------|-------------------|
| 目的 | 定性分析性能问题根因 | 定量测量性能指标 |
| 输入 | 性能问题描述 | commit 或代码变更 |
| 方法 | 代码分析 + 症状采集 | Macrobenchmark / adb 测量 |
| 产出 | 根因报告 + 优化建议 | 基线数据 + 对比报告 |
| 工作区 | 当前分支 | 独立 worktree |
| 代码修改 | 不修改代码 (仅建议) | --auto 模式自动修改 |

---

## 异常情况处理

| 场景 | 处理方式 |
|------|----------|
| 无设备连接 | 降级为静态分析，报告中标注 "无设备，仅静态分析" |
| adb 命令超时 | 跳过该数据采集，使用已有数据继续分析 |
| 不在 git 仓库中 | 仍可执行代码分析，跳过 git 相关步骤 |
| 不是 Android 项目 | 报错: "未检测到 Android 项目" |
| 问题类型无法确定 | 进入交互模式，引导用户选择 |
| docs/reviews 目录不存在 | 自动创建 |
| 问题过于模糊 | 进入交互模式，追问更多细节 |
| 多种问题类型叠加 | 按优先级逐个分析，或综合分析 |

---

## 文件结构

```
项目根目录/
├── docs/
│   └── reviews/
│       └── <branch>-performance-report.md   <- 本 skill 产出的报告
├── .claude/
│   └── skills/
│       └── android-performance/
│           └── SKILL.md                    <- 本文件
└── ...
```
