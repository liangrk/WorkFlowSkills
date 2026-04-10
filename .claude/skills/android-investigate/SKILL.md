---
name: android-investigate
description: |
  Android 系统化调试 skill。在开发/测试/运行时遇到 bug 时，
  进行分层根因分析。从复现到隔离到假设到验证，系统化地定位问题。
  产出根因报告和修复方案。
  适用场景: bug 排查、crash 分析、性能问题、行为异常。
voice-triggers:
  - "调查 bug"
  - "为什么会崩溃"
  - "排查问题"
  - "debug"
---

# Android Investigate

## 概述

对 Android 项目中遇到的 bug、crash、性能问题或行为异常进行系统化的分层根因分析。
从信息收集到复现确认，再到四层排查 (表现层、数据层、逻辑层、平台层)，
最终产出根因报告和修复方案。

**启动时声明:** "我正在使用 android-investigate skill。"

**零外部依赖:** 仅使用 Claude Code 原生工具 (Read、Grep、Glob、Bash、Edit)。
不依赖 gstack、browse、Codex、adb、MCP 工具。

## 调用方式

```bash
/android-investigate <问题描述>         # 直接描述问题，开始调查
/android-investigate crash <log片段>    # 分析 crash，基于提供的日志/stack trace
/android-investigate                   # 交互式模式，询问问题详情
```

**参数处理:**

| 调用方式 | 行为 |
|----------|------|
| `/android-investigate <问题描述>` | 将描述作为问题上下文，直接进入 Phase 0 |
| `/android-investigate crash <log>` | 将 log 作为 crash 证据，跳到 Phase 0 优先分析 crash 信息 |
| `/android-investigate` | 进入交互模式，依次询问: 问题现象、发生时机、最近改动、设备信息 |

**交互模式提示语:**

```
请描述遇到的问题:

1. 问题现象是什么? (crash / 行为异常 / 性能问题 / UI 问题)
2. 何时发生? (特定操作后 / 随机 / 启动时 / 特定条件下)
3. 是否有错误信息或日志? (可直接粘贴)
4. 最近是否修改了相关代码? (git log / 变更的文件)
5. 设备和系统版本信息? (可选)
```

---

## Phase 0: 信息收集

**目标:** 建立问题的完整上下文，为后续排查提供线索。

### 前置: 性能问题路由

在开始调试排查之前，检查输入是否为性能类问题。

**性能类关键词检测:**

| 类别 | 关键词 |
|------|--------|
| ANR | ANR / 无响应 / not responding / 应用卡死 |
| 内存 | 内存 / OOM / memory / leak / 泄漏 |
| 启动 | 启动 / 冷启动 / startup / 启动慢 |
| 帧率 | 卡顿 / 帧率 / jank / 掉帧 / 流畅度 |
| 电量 | 电量 / 电池 / battery / 耗电 |
| 网络 | 网络 / 请求慢 / API 慢 / 超时 |
| 包大小 | 大小 / APK / 包大小 / 安装包 |
| 通用 | 变慢 / 性能 / performance |

**路由逻辑:**

若用户输入匹配到上述性能类关键词:

1. 提示用户: "检测到性能类问题，建议使用 /android-performance 进行专项分析。"
2. 使用 AskUserQuestion 提供选择:
   - A) 使用 /android-performance (推荐)
   - B) 继续使用 /android-investigate (通用调试)

若选 A: 使用 Skill tool 调用 `android-performance`，传入相同的参数。
若选 B: 继续当前 investigate 流程，跳过此路由步骤。

### 前置: 加载历史学习记录

**前置引导:** 若学习记录为空，先运行预加载:
```bash
SHARED_BIN="$(git worktree list | head -1 | awk '{print $1}')/.claude/skills/android-shared/bin"
bash "$SHARED_BIN/android-learnings-bootstrap" 2>/dev/null || true
```

```bash
SHARED_BIN="$(git worktree list | head -1 | awk '{print $1}')/.claude/skills/android-shared/bin"
# 加载与问题领域相关的历史学习记录
LEARNINGS=$(bash "$SHARED_BIN/android-learnings-search" --type pitfall --query "<bug领域关键词>" --limit 5 2>/dev/null || true)
if [ -n "$LEARNINGS" ]; then
  echo "=== 相关学习记录 ==="
  echo "$LEARNINGS"
fi
```

将 `<bug领域关键词>` 替换为问题描述中的关键术语（如 "NullPointerException"、"lifecycle"、"network" 等）。
如果找到相关学习记录，在排查过程中优先验证这些已知坑点。

### 步骤 1: 收集问题基本信息

根据调用方式，整理以下信息:

```
=== 问题上下文 ===

问题描述:     <用户描述的问题>
问题类型:     crash / 行为异常 / 性能问题 / UI 问题 / 编译错误
发生时机:     <触发条件>
影响范围:     <哪些功能/页面受影响>
设备信息:     <设备型号 / Android 版本 / ROM> (如有)
```

### 步骤 2: 收集错误证据

**如果有日志/stack trace:**

直接从用户输入中提取。分析:
- 异常类型 (NullPointerException、ClassCastException、IllegalStateException 等)
- 异常消息
- 关键堆栈帧 (应用代码部分，过滤掉框架代码)
- 发生的线程 (main、DefaultDispatcher 等)

**如果用户未提供日志:**

在代码中搜索可能的错误来源:

```bash
# 搜索最近的 crash 相关代码
grep -rn "try\s*{" <相关文件> --include="*.kt" --include="*.java" 2>/dev/null
grep -rn "catch\s*(" <相关文件> --include="*.kt" --include="*.java" 2>/dev/null
grep -rn "throw " <相关文件> --include="*.kt" --include="*.java" 2>/dev/null

# 搜索错误处理
grep -rn "error\|Error\|fail\|Fail\|exception\|Exception" <相关文件> --include="*.kt" --include="*.java" 2>/dev/null
```

### 步骤 3: 收集变更上下文

> 参考: [android-shared/detection.md](.claude/skills/android-shared/detection.md) — 公共环境检测脚本

**环境检测优化:** 优先调用共享脚本获取技术栈信息:
```bash
SHARED_BIN="$(git worktree list | head -1 | awk '{print $1}')/.claude/skills/android-shared/bin"
ENV_JSON=$(bash "$SHARED_BIN/android-detect-env" 2>/dev/null || true)
echo "$ENV_JSON"
```
脚本不可用时回退到以下内联检测命令。

```bash
# 项目根目录
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)

# 最近 5 次提交
git log --oneline -5 2>/dev/null

# 最近 5 次提交变更的文件
git diff HEAD~5 --name-only 2>/dev/null

# 如果提供了具体的文件/模块，查看该文件的 git blame 和历史
git log --oneline -10 -- <相关文件> 2>/dev/null
```

### 步骤 4: 收集项目技术栈信息

```bash
# 确认 Android 项目
ls "$PROJECT_ROOT"/app/build.gradle "$PROJECT_ROOT"/app/build.gradle.kts 2>/dev/null

# UI 框架 (Compose / XML)
grep -rl "@Composable" "$PROJECT_ROOT/app/src/main" --include="*.kt" 2>/dev/null | head -3

# 架构模式 (MVVM / MVI / MVP)
grep -rn "ViewModel\|ViewState\|UiState\|Intent\b" "$PROJECT_ROOT/app/src/main" --include="*.kt" 2>/dev/null | head -5

# 依赖注入框架
grep -rn "Hilt\|Dagger\|Koin\|@Inject\|@Module" "$PROJECT_ROOT/app/src/main" --include="*.kt" 2>/dev/null | head -3

# 网络库
grep -rn "Retrofit\|OkHttp\|Ktor" "$PROJECT_ROOT/app/src/main" --include="*.kt" 2>/dev/null | head -3

# 异步框架
grep -rn "CoroutineScope\|Flow\|LiveData\|RxJava" "$PROJECT_ROOT/app/src/main" --include="*.kt" 2>/dev/null | head -5
```

### 步骤 5: 生成信息收集摘要

```
=== 信息收集摘要 ===

问题描述:     用户点击"提交"按钮后应用崩溃
问题类型:     crash
错误类型:     NullPointerException
堆栈关键帧:   OrderViewModel.kt:87 -> submitOrder()
发生线程:     main

最近变更:
  HEAD~1: feat: 添加订单提交功能
  HEAD~2: refactor: 重构 Repository 层
  HEAD~3: ...

受影响文件:
  app/.../OrderViewModel.kt (HEAD~1)
  app/.../OrderRepository.kt (HEAD~2)
  core/.../OrderUseCase.kt (HEAD~1)

技术栈:
  UI: Compose
  架构: MVVM + Clean Architecture
  DI: Hilt
  网络: Retrofit + OkHttp
  异步: Coroutines + Flow
```

---

## Phase 1: 复现与确认

**目标:** 通过代码审查确认问题是否存在，定位问题代码路径。

### 步骤 1: 定位问题代码路径

基于 Phase 0 收集的信息，定位问题涉及的代码文件和函数。

**如果提供了 stack trace:**
- 从 stack trace 提取应用代码的文件路径和行号
- 从最顶部的应用代码帧开始，逐帧向下追踪

**如果只有问题描述:**
- 根据问题涉及的模块/功能，搜索相关文件
- 根据用户描述的操作流程，在代码中找到对应的执行路径

```bash
# 搜索相关文件
find "$PROJECT_ROOT/app/src/main" -name "*.kt" -o -name "*.java" 2>/dev/null | xargs grep -l "<关键词>" 2>/dev/null

# 查看相关文件的结构
grep -n "fun \|class \|object \|interface " <相关文件> 2>/dev/null
```

### 步骤 2: 代码审查确认问题

阅读问题路径上的所有代码，理解数据流和控制流:

1. **读取问题入口点** (Activity/Fragment/Composable 的用户交互处理)
2. **读取 ViewModel/Presenter** (业务逻辑的入口)
3. **读取 UseCase/Interactor** (业务逻辑的实现)
4. **读取 Repository** (数据获取)
5. **读取数据模型** (DTO / Domain Model / UI Model)

**对每个文件，关注:**
- 变量是否可能为 null
- 异常是否被正确处理
- 数据转换是否正确
- 条件分支是否覆盖所有情况
- 是否有并发问题

### 步骤 3: 确认结果

```
=== 复现与确认 ===

问题可复现性: ✅ 代码中确认问题存在 / ⚠️ 无法在代码中确认 / ❌ 无法复现

问题代码路径:
  用户操作: 点击"提交"按钮
    -> OrderScreen.kt:45 onSubmitClick()
      -> OrderViewModel.kt:82 submitOrder()
        -> OrderRepository.kt:34 createOrder()
          -> NullPointerException at line 38 (order.items 为 null)

根因线索: order.items 在数据转换过程中丢失
```

**如果无法复现:**
- 记录 "无法复现"
- 列出代码中可能存在的问题点
- 基于代码分析继续 Phase 2

---

## Phase 2: 分层排查 (核心)

**目标:** 从外到内逐层排查，缩小问题范围。
每一层输出: 排除/确认 + 下一步方向。

### Layer 1: 表现层 -- 问题是什么?

**目标:** 精确描述问题的表现形式，提取所有可用证据。

**排查内容:**

| 排查项 | 方法 | 产出 |
|--------|------|------|
| 错误信息/异常类型 | 分析 stack trace 或日志 | 异常类型 + 消息 |
| 关键堆栈帧 | 定位应用代码中的帧 | 文件:行号列表 |
| 发生线程 | 判断 main/worker | 线程类型 |
| 用户可见现象 | 描述用户看到的 | 崩溃/白屏/错误状态/无响应 |
| 日志异常模式 | 搜索日志中的 ERROR/WARN | 相关日志片段 |

**对 crash 类问题的深度分析:**

```bash
# 如果有完整的 stack trace，提取所有应用代码帧
# 过滤掉以下包名开头的帧:
#   android., androidx., kotlin., java., dalvik., com.android.

# 提取异常链 (cause chain)
# "Caused by:" 链上的所有异常
```

**Layer 1 输出:**

```
=== Layer 1: 表现层 ===

状态: 🔴 确认问题

异常类型:    NullPointerException
异常消息:    "Parameter specified as non-null is null"
关键帧:
  1. OrderViewModel.kt:87  submitOrder()
  2. OrderRepository.kt:38 createOrder()
发生线程:    main (Dispatchers.Main)
用户现象:    点击提交按钮后应用立即崩溃

下一步方向:  进入 Layer 2，检查数据流
```

---

### Layer 2: 数据层 -- 数据流是否正确?

**目标:** 检查从数据源到 UI 的完整数据流，定位数据异常。

**排查内容:**

#### 2.1 API / 数据源

```bash
# 搜索 API 接口定义
grep -rn "@GET\|@POST\|@PUT\|@DELETE\|@PATCH" "$PROJECT_ROOT/app/src/main" --include="*.kt" --include="*.java" 2>/dev/null

# 搜索数据模型
grep -rn "data class\|@Entity\|@SerializedName\|@JsonClass" <相关模块> --include="*.kt" 2>/dev/null
```

**检查点:**
- API 响应结构是否与数据模型匹配?
- JSON 反序列化是否有默认值?
- 网络错误是否有 fallback?

#### 2.2 数据模型转换 (DTO <-> Domain <-> UI)

```bash
# 搜索 Mapper / Converter
grep -rn "fun.*toDomain\|fun.*toDto\|fun.*toUi\|fun.*mapTo\|fun.*toEntity\|Mapper\|Converter\|Assembler" <相关模块> --include="*.kt" 2>/dev/null

# 搜索 as? / as 类型转换
grep -rn " as " <相关文件> --include="*.kt" 2>/dev/null
```

**检查点:**
- DTO 到 Domain 的映射是否完整? 是否有字段遗漏?
- Domain 到 UI Model 的映射是否正确?
- 类型转换是否安全? (`as` 强转 vs `as?` 安全转换)
- 集合类型的映射是否处理了空集合?

#### 2.3 数据库 / 缓存

```bash
# 搜索 Room / DataStore / SharedPreferences 使用
grep -rn "@Dao\|@Query\|@Insert\|@Update\|@Delete\|dataStore\|SharedPreferences" <相关模块> --include="*.kt" 2>/dev/null

# 搜索缓存逻辑
grep -rn "cache\|Cache\|CacheManager" <相关模块> --include="*.kt" 2>/dev/null
```

**检查点:**
- 数据库查询是否可能返回 null?
- 缓存数据是否可能过期或与最新数据不一致?
- 并发读写是否有冲突?

#### 2.4 状态管理

```bash
# 搜索 StateFlow / LiveData / MutableStateFlow
grep -rn "StateFlow\|MutableStateFlow\|LiveData\|MutableLiveData\|_state\|_uiState" <相关文件> --include="*.kt" 2>/dev/null

# 搜索 state 更新
grep -rn "\.value\s*=\|\.emit\|\.update" <相关文件> --include="*.kt" 2>/dev/null
```

**检查点:**
- 初始状态是否正确?
- 状态更新是否在正确的线程?
- 是否有状态丢失 (配置变更、进程重建)?
- 是否有竞态条件 (多个 Flow 合并时)?

**Layer 2 输出:**

```
=== Layer 2: 数据层 ===

状态: 🔴 确认问题

数据流路径:
  API Response (JSON)
    -> OrderDto (data class, Retrofit 反序列化)
      -> OrderMapper.toDomain()          ← 问题点
        -> Order (domain model)
          -> OrderUiState (UI model)

问题发现:
  OrderMapper.toDomain() 中，当 API 返回的 items 字段为空数组时，
  映射逻辑错误地将其转为 null 而非空列表。
  OrderRepository.createOrder() 期望 items 不为 null，导致 NPE。

下一步方向:  进入 Layer 3，检查逻辑层的错误处理
```

---

### Layer 3: 逻辑层 -- 业务逻辑是否正确?

**目标:** 检查 ViewModel、UseCase、Repository 中的业务逻辑。

**排查内容:**

#### 3.1 状态转换

```bash
# 搜索 ViewModel 中的状态管理
grep -rn "when\|sealed\|sealed class\|sealed interface" <相关文件> --include="*.kt" 2>/dev/null

# 搜索事件处理
grep -rn "onEvent\|handleEvent\|handleIntent\|reduce\|on\[A-Z]" <相关文件> --include="*.kt" 2>/dev/null
```

**检查点:**
- 状态机是否完整? 是否有未处理的状态?
- 状态转换是否有前置条件?
- 错误状态是否正确传播到 UI?

#### 3.2 条件分支

```bash
# 搜索条件判断
grep -rn "if\s*(\|when\s*(" <相关文件> --include="*.kt" 2>/dev/null
```

**检查点:**
- `if/else` 是否覆盖所有分支?
- `when` 表达式是否 exhaustive?
- 边界条件: null、空集合、空字符串、0、负数、最大值
- 短路求值是否导致逻辑跳过?

#### 3.3 错误处理策略

```bash
# 搜索错误处理
grep -rn "runCatching\|try\s*{\|Result\|onFailure\|onSuccess\|getOrElse\|getOrThrow" <相关文件> --include="*.kt" 2>/dev/null

# 搜索错误状态
grep -rn "isLoading\|isError\|error\s*=\|Error\s*=" <相关文件> --include="*.kt" 2>/dev/null
```

**检查点:**
- 是否所有可能失败的操作都有错误处理?
- 错误信息是否对用户友好?
- 是否有静默失败 (catch 后不处理)?
- 是否有重试机制?

#### 3.4 边界条件

```bash
# 搜索可能的问题模式
grep -rn "\.first()\|\.last()\|\[0\]\|\.get(0)" <相关文件> --include="*.kt" 2>/dev/null
grep -rn "!!" <相关文件> --include="*.kt" 2>/dev/null
grep -rn "\.orEmpty()\|?:\|?:\s" <相关文件> --include="*.kt" 2>/dev/null
```

**检查点:**
- 集合操作是否考虑了空集合?
- 非空断言 (`!!`) 是否安全?
- Elvis 运算符 (`?:`) 的默认值是否合理?
- 分页加载的边界 (第一页、最后一页)?

**Layer 3 输出:**

```
=== Layer 3: 逻辑层 ===

状态: 🟡 部分相关

发现:
  1. OrderRepository.createOrder() 未对 items 参数做空检查
     位置: OrderRepository.kt:38
     风险: 高 -- 直接解引用可空变量

  2. OrderViewModel.submitOrder() 的错误处理仅捕获了 IOException
     位置: OrderViewModel.kt:85
     风险: 中 -- 其他异常 (如 NPE) 会直接传播到 main 线程

  3. OrderMapper.toDomain() 缺少单元测试
     位置: OrderMapper.kt:22
     风险: 低 -- 无法验证映射逻辑的正确性

下一步方向:  进入 Layer 4，检查是否有平台层因素
```

---

### Layer 4: 平台层 -- Android 平台问题?

**目标:** 检查是否是 Android 平台特有问题。

**排查内容:**

#### 4.1 生命周期问题

```bash
# 搜索生命周期相关代码
grep -rn "onCreate\|onStart\|onResume\|onPause\|onStop\|onDestroy\|onSaveInstanceState\|Lifecycle" <相关文件> --include="*.kt" --include="*.java" 2>/dev/null

# 搜索 viewModelScope / lifecycleScope
grep -rn "viewModelScope\|lifecycleScope\|repeatOnLifecycle\|collectAsStateWithLifecycle" <相关文件> --include="*.kt" 2>/dev/null
```

**检查点:**
- 协程是否绑定到正确的 scope? (viewModelScope vs GlobalScope)
- Flow 收集是否在正确的生命周期阶段? (repeatOnLifecycle)
- 配置变更 (旋转屏幕) 是否导致状态丢失?
- Activity 被系统回收后恢复是否正确?
- Navigation 返回栈是否导致内存泄漏?

#### 4.2 权限问题

```bash
# 搜索权限相关代码
grep -rn "permission\|Permission\|checkSelfPermission\|requestPermission\|rememberPermission" <相关文件> --include="*.kt" --include="*.java" --include="*.xml" 2>/dev/null

# 检查 AndroidManifest.xml 中的权限声明
grep "uses-permission" "$PROJECT_ROOT/app/src/main/AndroidManifest.xml" 2>/dev/null
```

**检查点:**
- 所需权限是否在 Manifest 中声明?
- 运行时权限是否在使用前检查和请求?
- 权限被拒绝后是否有降级处理?

#### 4.3 内存问题

```bash
# 搜索可能的内存问题
grep -rn "Bitmap\|bitmap\|Glide\|Coil\|ImageLoader\|LargeBitmap\|BitmapFactory" <相关文件> --include="*.kt" --include="*.java" 2>/dev/null

# 搜索可能的内存泄漏
grep -rn "GlobalScope\|companion object.*listener\|static.*reference\|WeakReference" <相关文件> --include="*.kt" --include="*.java" 2>/dev/null
```

**检查点:**
- Bitmap 是否被正确回收?
- 大列表是否有分页或懒加载?
- 是否有 Activity/Context 泄漏?
- 静态变量是否持有 View/Activity 引用?

#### 4.4 线程问题

```bash
# 搜索线程相关代码
grep -rn "Dispatchers\|withContext\|@MainThread\|@WorkerThread\|synchronized\|@Volatile\|Mutex\|Thread" <相关文件> --include="*.kt" --include="*.java" 2>/dev/null
```

**检查点:**
- 网络请求是否在 IO 线程?
- UI 更新是否在主线程?
- 是否有共享可变状态未做同步?
- 是否有主线程阻塞操作?
- 协程取消是否被正确处理?

#### 4.5 兼容性问题

```bash
# 搜索 API level 相关
grep -rn "@RequiresApi\|Build.VERSION\|SDK_INT\|@SuppressLint" <相关文件> --include="*.kt" --include="*.java" 2>/dev/null

# 检查 minSdk 和 targetSdk
grep -rn "minSdk\|targetSdk\|compileSdk" "$PROJECT_ROOT/app" --include="*.gradle*" 2>/dev/null
```

**检查点:**
- 是否使用了高于 minSdk 的 API 且未做版本检查?
- 是否有厂商 ROM 兼容性问题?
- 是否有特定设备/屏幕尺寸的问题?
- Android 新版本行为变更是否已适配?

**Layer 4 输出:**

```
=== Layer 4: 平台层 ===

状态: 🟢 排除

排查结果:
  生命周期:  ✅ viewModelScope 正确使用，repeatOnLifecycle 已配置
  权限:      ✅ 无相关权限需求
  内存:      ✅ 无大 Bitmap 或泄漏风险
  线程:      ✅ IO 操作在 Dispatchers.IO，UI 更新在 Dispatchers.Main
  兼容性:    ✅ 无低版本 API 问题

结论: 问题非平台层因素，根因在数据层 (Layer 2)
```

---

### 分层排查汇总

```
=== 分层排查汇总 ===

Layer 1 表现层:  🔴 确认 -- NullPointerException at OrderViewModel.kt:87
Layer 2 数据层:  🔴 确认 -- OrderMapper.toDomain() 空数组映射为 null
Layer 3 逻辑层:  🟡 部分 -- Repository 未做空检查
Layer 4 平台层:  🟢 排除 -- 无平台相关问题

根因方向: 数据层映射错误，逻辑层缺乏防御
```

---

## Phase 3: 根因假设与验证

**目标:** 基于分层排查结果，提出假设并逐个验证。

### 步骤 1: 列出根因假设

基于 Phase 2 的排查结果，列出 1-3 个可能的根因假设:

```
=== 根因假设 ===

假设 1 (最可能): OrderMapper.toDomain() 中 items 字段映射逻辑错误
  证据: Layer 2 发现空数组被映射为 null
  置信度: 高 (85%)

假设 2: API 返回数据结构变更，items 字段可能为 null
  证据: Layer 2 发现 DTO 定义中 items 字段可能为可空
  置信度: 中 (60%)

假设 3: Repository 层未对输入参数做防御性校验
  证据: Layer 3 发现 createOrder() 直接使用 items 而无空检查
  置信度: 中 (50%)
```

### 步骤 2: 逐个验证假设

**假设 1 验证 -- OrderMapper 映射逻辑错误:**

```bash
# 读取 OrderMapper 的完整代码
# 检查 toDomain() 中对 items 字段的处理逻辑
```

验证方法: 代码检查
- 检查 `items` 字段的 DTO 定义 (是否可空? 默认值?)
- 检查 `toDomain()` 中 `items` 的映射逻辑
- 确认是否存在 `items ?: emptyList()` vs `items` 直接赋值的差异

验证结果:
```
假设 1 验证: ✅ 确认

OrderDto 中 items 定义为 List<ItemDto>? (可空)
toDomain() 中: items = dto.items  (直接赋值，未做空安全处理)
当 API 返回 {"items": []} 时，Gson/Moshi 反序列化为空列表
当 API 返回 {"items": null} 时，反序列化为 null
当 API 返回 {} 时 (缺少 items 字段)，反序列化为 null

createOrder() 中: order.items!!.forEach { ... }  (非空断言，NPE)
```

**假设 2 验证 -- API 返回数据结构变更:**

```bash
# 检查 DTO 定义中的注解和默认值
# 检查 API 文档或接口定义
# 检查是否有 JSON 序列化配置
```

验证方法: 代码检查
- 检查 DTO 类的 `@JsonClass` / `@SerializedName` 注解
- 检查是否有 `@Json(name = ...)` 别名
- 检查 Gson/Moshi/Kotlinx Serialization 的配置

验证结果:
```
假设 2 验证: ⚠️ 部分确认

OrderDto 使用 @JsonClass(generateAdapter = true)
items 字段声明为 List<ItemDto>? (无默认值)
确实缺少 items 字段时会导致 null
但这不是 API 结构变更，而是原始设计就存在风险
```

**假设 3 验证 -- Repository 未做防御性校验:**

```bash
# 读取 OrderRepository.createOrder() 的完整代码
# 检查参数校验逻辑
```

验证方法: 代码检查
- 检查函数签名中参数的可空性
- 检查函数入口是否有 require() / check() / if-null-return

验证结果:
```
假设 3 验证: ✅ 确认 (但为辅助因素)

createOrder(order: Order) 中直接使用 order.items
未做 null 检查或前置条件校验
这是根因的放大因素，但不是直接原因
```

### 步骤 3: 确定最终根因

```
=== 根因确认 ===

直接根因:
  OrderMapper.toDomain() 未对 items 字段做空安全处理。
  当 API 返回 null 或缺少 items 字段时，Domain Model 中 items 为 null。
  OrderRepository.createOrder() 使用 !! 非空断言解引用 items，导致 NPE。

触发条件:
  API 返回的订单数据中 items 字段为 null 或缺失

影响范围:
  所有通过 OrderMapper.toDomain() 转换的订单数据
  影响订单详情页、订单列表页、订单提交功能

置信度: 95%
```

---

## Phase 4: 修复方案

**目标:** 给出具体、可执行的修复方案。

### 步骤 1: 提出修复方案

#### 方案 A: 数据层修复 (推荐)

修复位置: `OrderMapper.kt` toDomain()

```kotlin
// 修复前
fun toDomain(dto: OrderDto): Order {
    return Order(
        id = dto.id,
        items = dto.items,  // 可能为 null
        // ...
    )
}

// 修复后
fun toDomain(dto: OrderDto): Order {
    return Order(
        id = dto.id,
        items = dto.items.orEmpty(),  // 空安全处理
        // ...
    )
}
```

同时修改 Domain Model，将 items 声明为非空:
```kotlin
// 修复前
data class Order(
    val id: String,
    val items: List<Item>?,  // 可空
)

// 修复后
data class Order(
    val id: String,
    val items: List<Item>,   // 非空，空列表表示无 items
)
```

- **修复风险:** 低 -- 将 null 转为空列表是安全的语义变更
- **影响范围:** 所有使用 Order.items 的地方需要确认对空列表的处理
- **是否需要其他修改:** Repository 中 `order.items!!` 可以去掉 `!!`

#### 方案 B: 逻辑层修复 (防御性)

修复位置: `OrderRepository.kt` createOrder()

```kotlin
// 修复前
fun createOrder(order: Order) {
    order.items!!.forEach { ... }
}

// 修复后
fun createOrder(order: Order) {
    val items = order.items ?: emptyList()
    items.forEach { ... }
}
```

- **修复风险:** 低
- **影响范围:** 仅 Repository 内部
- **缺点:** 治标不治本，Domain Model 中 items 仍然可空

#### 方案 C: 综合修复 (最佳)

同时应用方案 A 和方案 B:
1. Mapper 层: 使用 `orEmpty()` 确保数据正确转换
2. Domain Model: 将 items 改为非空 `List<Item>`
3. Repository: 移除 `!!` 非空断言
4. 补充单元测试: 覆盖 items 为 null 的场景

### 步骤 2: 标注修复风险

```
=== 修复风险评估 ===

推荐方案: C (综合修复)

变更文件:
  1. app/.../mapper/OrderMapper.kt        -- items.orEmpty()
  2. app/.../domain/model/Order.kt        -- items: List<Item> (非空)
  3. app/.../repository/OrderRepository.kt -- 移除 !!
  4. app/src/test/.../OrderMapperTest.kt   -- 新增测试用例

影响分析:
  - Order.items 的所有消费者需要确认对空列表的兼容性
  - 搜索所有使用 order.items 的代码:
    (列出所有使用点)
  - 如果有地方依赖 items == null 来判断"无 items"，需改为 items.isEmpty()

回滚方案: 保留原始 DTO 定义不变，仅在 Mapper 层做转换
```

### 步骤 3: 标注修复验证方法

```
=== 修复验证 ===

验证方式 1: 单元测试
  - OrderMapperTest: 测试 items 为 null、空数组、正常数组三种场景
  - OrderRepositoryTest: 测试 items 为空列表时 createOrder() 不崩溃
  运行: ./gradlew testDebugUnitTest

验证方式 2: 代码审查
  - 确认所有 order.items 的使用点对空列表兼容
  - 确认无 !! 非空断言残留
  运行: grep -rn "order\.items!!" --include="*.kt"

验证方式 3: 集成测试 (如有设备)
  - 模拟 API 返回 items 为 null 的场景
  - 验证应用不崩溃，UI 正确显示空状态
```

---

## Capture Learnings

调查完成后，将根因和发现记录到学习系统以供未来 session 参考。

**记录时机:**

1. **根因确认后** — 使用 android-learnings-log 记录根因模式:
   ```bash
   SHARED_BIN="$(git worktree list | head -1 | awk '{print $1}')/.claude/skills/android-shared/bin"
   bash "$SHARED_BIN/android-learnings-log" '{"skill":"investigate","type":"pitfall","key":"<根因简述>","insight":"<根因描述和触发条件>","confidence":9,"source":"observed","files":["<根因文件>"]}'
   ```

2. **发现新的排查路径** — 如果排查过程中发现了非直觉的调试方法，记录为 technique:
   ```bash
   SHARED_BIN="$(git worktree list | head -1 | awk '{print $1}')/.claude/skills/android-shared/bin"
   bash "$SHARED_BIN/android-learnings-log" '{"skill":"investigate","type":"technique","key":"<方法名>","insight":"<方法描述>","confidence":7,"source":"inferred","files":[]}'
   ```

3. **验证或推翻历史记录** — 如果历史学习记录中的某条在本轮调查中被验证或推翻，更新置信度。

**不记录:**
- 临时性的环境问题（如网络超时、设备连接问题）
- 第三方库的已知 bug（除非有项目特有 workaround）

---

## 产出

### 产出物: 根因报告

写入 `docs/reviews/<branch>-investigate-report.md`:

```markdown
# 调查报告: <问题标题>

> 生成于 <YYYY-MM-DD HH:mm> | android-investigate
> 调查模式: 直接描述 / crash 分析 / 交互式

## 摘要

| 指标 | 结果 |
|------|------|
| 问题类型 | crash / 行为异常 / 性能问题 |
| 根因位置 | `<文件路径>:<行号>` |
| 根因类型 | 空指针 / 逻辑错误 / 平台问题 / 数据映射 |
| 置信度 | 高 / 中 / 低 |
| 修复方案 | A / B / C |

## 问题描述

<问题的完整描述，包含复现步骤和现象>

## 信息收集

<Phase 0 收集的所有上下文>

## 分层排查过程

### Layer 1: 表现层
<分析过程和结论>

### Layer 2: 数据层
<分析过程和结论>

### Layer 3: 逻辑层
<分析过程和结论>

### Layer 4: 平台层
<分析过程和结论>

## 根因

<最终确认的根因描述，包含触发条件和影响范围>

## 修复方案

<推荐的修复方案，包含代码变更、风险评估、验证方法>

## 验证方法

<如何确认修复有效>
```

### 产出物路径

```
docs/reviews/
└── plan/auth-login-flow-investigate-report.md    ← 本次调查报告
```

---

## 异常情况处理

| 场景 | 处理方式 |
|------|----------|
| 不在 git 仓库中 | 仍可执行代码排查，但跳过 git diff/log 步骤 |
| 不是 Android 项目 | 报错: "未检测到 Android 项目" |
| 无法复现问题 | 记录 "无法复现"，基于代码分析继续排查 |
| 多个可能的根因 | 列出所有假设，按可能性排序，逐一验证 |
| 根因在第三方库 | 记录根因，给出 workaround 方案 |
| 根因在 API 后端 | 记录根因，给出客户端防御方案，建议协调后端修复 |
| docs/reviews 目录不存在 | 自动创建 |
| 问题过于模糊 | 进入交互模式，追问更多细节 |

---

## 与其他 Skill 的衔接

### 上游: android-qa

当 android-qa 发现复杂 bug (非简单修复) 时，可调用 `/android-investigate` 进行根因分析。

触发方式:
```
QA 发现复杂问题 BUG-001，建议使用 /android-investigate 进行根因分析。
是否启动调查?
- A) 是，启动 /android-investigate
- B) 跳过，仅记录在报告中
```

### 上游: android-worktree-runner

当 android-worktree-runner 在执行 plan 任务时遇到阻塞 (编译错误、测试失败、运行时异常)，可调用 `/android-investigate` 进行调试。

触发方式:
```
任务 #3 执行失败: 编译错误。是否启动 /android-investigate 调查?
- A) 是，启动调查
- B) 跳过，手动处理
```

### 与其他 Skill 的关系

| Skill | 关系 | 说明 |
|-------|------|------|
| android-qa | 上游 | QA 发现复杂 bug 后调用本 skill |
| android-worktree-runner | 上游 | 执行中遇到阻塞时调用本 skill |
| android-design-review | 参考 | 排查 UI 问题时对照设计规范 |
| android-autoplan | 参考 | 排查时对照 plan 文件确认预期行为 |
| android-code-review | 下游 | 修复方案确认后可进行 code review |

---

## 文件结构

```
项目根目录/
├── docs/
│   └── reviews/
│       └── <branch>-investigate-report.md   ← 本 skill 产出的调查报告
├── .claude/
│   └── skills/
│       └── android-investigate/
│           └── SKILL.md                 ← 本 skill
└── ...
```
