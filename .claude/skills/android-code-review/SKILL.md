---
name: android-code-review
description: |
  Android 代码审查 skill。在 worktree-runner 任务完成或 plan 执行完毕后，
  对代码变更进行质量审查。检查命名规范、架构一致性、生命周期安全、
  线程安全、资源管理等 Android 特有问题。
  适用场景: PR 审查、任务完成后代码质量检查、代码评审。
voice-triggers:
  - "代码审查"
  - "review 代码"
  - "检查代码质量"
---

# Android Code Review

## 概述

代码变更 → 六维度审查 → 审查报告。不写代码，只审查并产出报告。

**启动时声明:** "我正在使用 android-code-review skill。"

**零外部依赖:** 不依赖 gstack 二进制、Codex、browse、design。仅使用 Claude Code
原生工具 (Read、Write、Edit、Grep、Glob、Bash)。

## 调用方式

```bash
/android-code-review                     # 审查当前分支 vs main 的所有变更
/android-code-review <branch>            # 审查指定分支 vs main 的变更
/android-code-review diff                # 审查未提交的变更 (staged + unstaged)
```

**参数处理:**
- 无参数: 执行 `git diff main...HEAD` (或 `git diff origin/main...HEAD`)，
  审查当前分支相对于 main 的所有变更
- `<branch>`: 执行 `git diff main...<branch>`，审查指定分支的变更
- `diff`: 执行 `git diff` + `git diff --cached`，审查未提交的变更

---

## Phase 0: 项目环境检测

在所有流程开始前，自动检测项目环境。检测结果贯穿后续所有审查阶段。

### 步骤 1: 确认项目根目录和 git 状态

```bash
# 确认项目根目录
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -z "$PROJECT_ROOT" ]; then
  echo "错误: 未找到 git 仓库"
  exit 1
fi

# 确认是 Android 项目
if [ ! -f "$PROJECT_ROOT/build.gradle" ] && [ ! -f "$PROJECT_ROOT/build.gradle.kts" ] && \
   [ ! -f "$PROJECT_ROOT/settings.gradle" ] && [ ! -f "$PROJECT_ROOT/settings.gradle.kts" ]; then
  echo "错误: 未检测到 Android 项目 (缺少 build.gradle / settings.gradle)"
  exit 1
fi

echo "PROJECT_ROOT: $PROJECT_ROOT"
```

### 步骤 2: 技术栈检测

按以下规则扫描项目，生成技术栈档案。

**UI 框架:**
```bash
# Compose 检测
grep -r "androidx.compose" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
grep -rl "@Composable" "$PROJECT_ROOT/app/src" 2>/dev/null | head -5

# XML Views 检测
find "$PROJECT_ROOT/app/src/main/res/layout" -name "*.xml" 2>/dev/null | head -5
```

**异步框架:**
```bash
grep -r "kotlinx.coroutines" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
grep -rl "import kotlinx.coroutines" "$PROJECT_ROOT/app/src" 2>/dev/null | head -5
grep -rl "import io.reactivex" "$PROJECT_ROOT/app/src" 2>/dev/null | head -5
```

**依赖注入:**
```bash
grep -r "com.google.dagger:hilt" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
grep -r "io.insert-koin" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
```

**网络库:**
```bash
grep -r "com.squareup.retrofit2" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
grep -r "io.ktor" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
```

**数据库:**
```bash
grep -r "androidx.room" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
grep -r "app.cash.sqldelight" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
```

**图片加载:**
```bash
grep -r "io.coil-kt" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
grep -r "com.github.bumptech.glide" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
```

**导航:**
```bash
grep -r "androidx.navigation" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
```

**输出技术栈档案:**
```
=== 项目技术栈档案 ===
UI:         Compose / XML Views / 混用
异步:       Coroutines / RxJava / 无
DI:         Hilt / Koin / 无
网络:       Retrofit / Ktor / 无
数据库:     Room / SQLDelight / 无
图片:       Coil / Glide / 无
导航:       Navigation Compose / Navigation Component / 无
```

### 步骤 3: 架构检测

```bash
# 读取包结构
find "$PROJECT_ROOT/app/src/main/java" -type d 2>/dev/null | head -20
find "$PROJECT_ROOT/app/src/main/kotlin" -type d 2>/dev/null | head -20

# 检测分层关键词
grep -rl "ViewModel" "$PROJECT_ROOT/app/src" 2>/dev/null | head -5
grep -rl "Repository" "$PROJECT_ROOT/app/src" 2>/dev/null | head -5
grep -rl "UseCase\|Interactor" "$PROJECT_ROOT/app/src" 2>/dev/null | head -5
grep -rl "Reducer\|Action\|Event" "$PROJECT_ROOT/app/src" 2>/dev/null | head -5
```

根据包结构和代码模式，推断架构模式:
- `ui/` + `viewmodel/` + `repository/` → MVVM
- `presentation/` + `domain/` + `data/` → Clean Architecture
- `reducer/` + `action/` + `state/` → MVI
- 其他 → 记录实际观察到的模式

**输出:**
```
=== 项目架构 ===
推断架构: MVVM
包结构: com.example.app.ui / .viewmodel / .repository / .data.remote
注意: 架构为推断结果，不限定审查必须遵循
```

### 步骤 4: 命名规范检测

```bash
# 检测 Activity/Fragment 命名
find "$PROJECT_ROOT/app/src/main/java" -o -name "$PROJECT_ROOT/app/src/main/kotlin" 2>/dev/null | \
  xargs grep -l "Activity\|Fragment" 2>/dev/null | head -10

# 检测资源命名
find "$PROJECT_ROOT" -path "*/res/drawable*" -name "*.xml" 2>/dev/null | xargs -I{} basename {} 2>/dev/null | head -30
find "$PROJECT_ROOT" -path "*/res/layout*" -name "*.xml" 2>/dev/null | xargs -I{} basename {} 2>/dev/null | head -20

# 检测变量/函数命名风格 (Kotlin 约定)
grep -r "fun " "$PROJECT_ROOT/app/src/main/java" "$PROJECT_ROOT/app/src/main/kotlin" 2>/dev/null | head -20
```

**输出:**
```
=== 命名规范 (推断) ===
Activity:   XxxActivity / ActivityXxx
Fragment:   XxxFragment / FragmentXxx
Layout:     activity_xxx / fragment_xxx / item_xxx
Drawable:   ic_xxx_24dp / bg_xxx / img_xxx
函数:       camelCase / snake_case
类名:       PascalCase
```

---

## Phase 1: 变更范围分析

### 步骤 1: 获取 diff

根据调用参数获取对应的 diff:

```bash
# 无参数: 当前分支 vs main
git diff main...HEAD --stat
git diff main...HEAD

# 带分支参数: 指定分支 vs main
git diff main...<branch> --stat
git diff main...<branch>

# diff 参数: 未提交的变更
git diff --stat
git diff
git diff --cached --stat
git diff --cached
```

### 步骤 2: 分析变更范围

从 `--stat` 输出和 diff 内容中提取:

**1. 模块/包影响范围:**
```bash
# 提取被修改的模块
git diff main...HEAD --stat | awk '{print $1}' | sed 's|/.*||' | sort -u

# 提取被修改的包
git diff main...HEAD | grep "^+++ b/" | sed 's|^+++ b/||' | sed 's|/[^/]*$||' | sort -u
```

**2. 变更类型统计:**
```bash
# 新增文件
git diff main...HEAD --diff-filter=A --name-only

# 修改文件
git diff main...HEAD --diff-filter=M --name-only

# 删除文件
git diff main...HEAD --diff-filter=D --name-only
```

**3. 变更规模:**
```bash
# 行数统计
git diff main...HEAD --shortstat
```

### 步骤 3: 输出变更摘要

```
=== 变更范围摘要 ===
比较: main...<branch>
文件数: N (新增: A / 修改: M / 删除: D)
行数: +X / -Y
涉及模块: app, feature:login, core:data
涉及包: com.example.app.ui.login, com.example.app.data.repository
变更类型: 新增功能 / Bug 修复 / 重构 / 配置变更
```

**如果变更规模过大 (> 50 个文件或 > 3000 行):**
发出警告:
> 变更规模较大 (N 个文件, +X/-Y 行)。建议拆分为更小的 PR 以提高审查效率。
> 是否继续审查?
> - A) 继续审查全部变更
> - B) 仅审查指定模块/文件
> - C) 取消

---

## Phase 2: 代码审查 (六维度 Subagent)

将审查拆为独立维度派发 subagent，避免上下文溢出。
主 context 只接收每个 subagent 的紧凑结论。

### 上下文预算

| 阶段 | 预估消耗 | 方式 |
|------|---------|------|
| Phase 0 (环境检测) | ~10% | 主 context |
| Phase 1 (变更分析) | ~10% | 主 context |
| Phase 2 (六维度审查) | ~6% (仅汇总结论) | subagent x6 |
| Phase 3 (汇总报告) | ~15% | 主 context |

### 前置: 准备审查输入

在派发 subagent 前，准备共享输入:

**每个 subagent 接收的共享上下文:**
- diff 内容 (完整 diff，或按文件过滤后的 diff)
- 项目技术栈档案 (Phase 0 输出)
- 项目架构推断结果
- 命名规范推断结果
- 变更范围摘要

### 步骤 1: 派发架构一致性审查

```
你是 Android 架构审查员。审查以下代码变更的架构一致性。

项目技术栈: <技术栈档案>
项目架构: <架构推断>
变更范围: <变更摘要>

Diff:
<完整 diff 或相关文件 diff>

审查要点:
1. 模块依赖方向: 新增的 import/依赖是否违反分层规则?
   - UI 层是否直接依赖 data 层实现 (而非接口)?
   - feature 模块是否依赖了其他 feature 模块?
   - core 模块是否反向依赖了 app 或 feature 模块?
2. DI 正确性: 新增类是否正确使用 DI?
   - 构造函数注入 vs 字段注入?
   - 是否有手动 new 依赖的具体实现?
   - @Module / @Provides 是否在正确位置?
3. 分层规则: 新代码是否放在了正确的包/模块?
   - Repository 实现是否在 data 层?
   - ViewModel 是否在正确的 ui 包下?
   - 数据模型是否在正确的 domain/data 包下?
4. 接口隔离: 是否有违反接口隔离原则的倾向?

输出格式 (严格控制在 300 字以内):
- 结论: 通过 / 需要调整
- 问题列表 (如有):
  - 文件:行号 | 严重程度 (阻塞/建议) | 描述 | 修复建议
```

### 步骤 2: 派发命名与代码风格审查

```
你是 Android 代码风格审查员。审查以下代码变更的命名规范和代码风格。

项目命名规范 (推断): <命名规范档案>
项目技术栈: <技术栈档案>
变更范围: <变更摘要>

Diff:
<完整 diff 或相关文件 diff>

审查要点:
1. 类命名: 是否遵循 PascalCase? 是否与项目已有命名一致?
   - Activity: XxxActivity / ActivityXxx (遵循项目约定)
   - Fragment: XxxFragment / FragmentXxx
   - ViewModel: XxxViewModel
   - Repository: XxxRepository / XxxRepositoryImpl
   - UseCase: XxxUseCase
2. 函数/变量命名: 是否遵循 camelCase? 是否语义清晰?
   - 函数名是否表达了动词意图 (fetch/load/save 而非 process)?
   - 变量名是否避免了单字母 (循环变量除外)?
   - Boolean 变量是否使用 is/has/can/should 前缀?
3. 资源命名: 是否遵循项目资源命名规范?
   - drawable: ic_xxx / bg_xxx / img_xxx
   - layout: activity_xxx / fragment_xxx / item_xxx
   - id: snake_case (不带匈牙利前缀)
4. Kotlin 惯例:
   - 是否使用 data class 而非普通 class 传递数据?
   - 是否使用 sealed class 而非 enum + when 处理状态?
   - 是否使用 extension function 提高可读性?
   - 是否使用 scope function (let/apply/also/run/with) 合理?
   - 是否有不必要的 !! (非空断言)?
   - 是否使用 string resources 而非硬编码字符串?

输出格式 (严格控制在 300 字以内):
- 结论: 通过 / 需要调整
- 问题列表 (如有):
  - 文件:行号 | 严重程度 (阻塞/建议) | 描述 | 修复建议
```

### 步骤 3: 派发生命周期与内存安全审查

```
你是 Android 生命周期安全审查员。审查以下代码变更的生命周期和内存安全风险。

项目技术栈: <技术栈档案>
项目架构: <架构推断>
变更范围: <变更摘要>

Diff:
<完整 diff 或相关文件 diff>

审查要点:
1. Context 泄漏:
   - ViewModel 是否持有 Activity/Fragment Context 引用?
   - 是否将 Context 存入 static 变量或单例?
   - 是否使用 Application Context 替代 Activity Context 在长生命周期场景?
   - 内部类/匿名类是否持有外部类引用? (应使用 static inner class)
2. Listener 注册/注销:
   - BroadcastReceiver 是否在 onPause/onDestroy 注销?
   - SensorManager/LocationManager Listener 是否配对注销?
   - ValueEventListener/DatabaseReference Listener 是否配对移除?
   - Compose DisposableEffect 是否正确 dispose?
3. Coroutine Scope:
   - viewModelScope 是否在 ViewModel 中使用? (正确)
   - lifecycleScope 是否在 Activity/Fragment 中使用? (正确)
   - GlobalScope 是否被使用? (几乎总是错误的)
   - Coroutine 启动方式: launch vs async 是否正确?
   - 是否在 Composable 中使用 rememberCoroutineScope?
4. ViewModel 持有 View:
   - ViewModel 是否引用了 View/Activity/Fragment?
   - ViewModel 是否引用了 Compose 的 MutableState (而非 StateFlow)?
5. Flow 收集生命周期:
   - collectAsState vs collectAsStateWithLifecycle 是否正确选择?
   - launchWhenStarted vs repeatOnLifecycle(Lifecycle.State.STARTED)?
   - 是否在 Fragment.viewLifecycleOwner 上收集 Flow?

输出格式 (严格控制在 300 字以内):
- 结论: 通过 / 需要调整
- 问题列表 (如有):
  - 文件:行号 | 严重程度 (阻塞/建议) | 风险类型 | 描述 | 修复建议
```

### 步骤 4: 派发线程与并发审查

```
你是 Android 线程安全审查员。审查以下代码变更的线程和并发问题。

项目技术栈: <技术栈档案>
变更范围: <变更摘要>

Diff:
<完整 diff 或相关文件 diff>

审查要点:
1. 主线程 IO:
   - 数据库查询是否在 IO dispatcher 执行?
   - 网络请求是否在 IO dispatcher 执行?
   - 文件读写是否在 IO dispatcher 执行?
   - SharedPreferences.apply() vs commit()? (apply 异步, commit 同步)
   - Room DAO 的 suspend 函数是否正确声明?
2. UI 线程安全:
   - LiveData/StateFlow 的更新是否在主线程? (setValue vs postValue)
   - UI 更新是否确保在主线程? (withContext(Main))
   - Compose state 更新是否在 Composable 外部误用?
3. 竞态条件:
   - 多个协程是否同时修改同一个共享状态?
   - 是否有对可变集合的非同步并发访问?
   - Flow 的 conflation/缓冲策略是否正确?
4. 同步问题:
   - Mutex/Semaphore 使用是否正确?
   - volatile/AtomicReference 是否在合适场景使用?
   - synchronized 块是否可能导致死锁?
5. Compose 重组线程:
   - Side effect (LaunchedEffect/DisposableEffect) 是否正确使用?
   - remember 的 key 是否正确设置以避免意外重置?
   - derivedStateOf 是否在需要时使用以减少重组?

输出格式 (严格控制在 300 字以内):
- 结论: 通过 / 需要调整
- 问题列表 (如有):
  - 文件:行号 | 严重程度 (阻塞/建议) | 线程模型 | 描述 | 修复建议
```

### 步骤 5: 派发 Android 特有审查

```
你是 Android 平台专项审查员。审查以下代码变更的 Android 特有问题。

项目技术栈: <技术栈档案>
构建配置: <minSdk/targetSdk/compileSdk>
变更范围: <变更摘要>

Diff:
<完整 diff 或相关文件 diff>

审查要点:
1. 资源泄漏:
   - Cursor/InputStream/OutputStream 是否在 finally 或 use{} 块中关闭?
   - Bitmap 是否在不使用时 recycle()? (使用 Coil/Glide 时通常不需要)
   - WebView 是否在 onDestroy 中 destroy()?
   - Animator/Animation 是否在适当时候 cancel()?
2. Bitmap 处理:
   - 是否直接加载大图而不采样? (应使用 BitmapFactory.Options.inSampleSize)
   - 图片加载是否使用 Coil/Glide? (不应手动管理 Bitmap)
   - 圆角/裁剪是否使用已有的图片加载库而非手动 Canvas 操作?
3. 数据库事务:
   - Room @Transaction 是否在批量操作上使用?
   - 多个写操作是否包裹在事务中?
   - Migration 是否正确处理? (addMigrations)
   - 是否有全表扫描的查询? (缺少索引)
4. 权限检查:
   - 运行时权限是否在请求前检查? (ContextCompat.checkSelfPermission)
   - 权限请求回调是否正确处理? (requestPermissionLauncher)
   - Manifest 声明与运行时请求是否一致?
5. Android 版本兼容:
   - API 调用是否检查 Build.VERSION.SDK_INT?
   - 是否使用了已废弃的 API? (如 onActivityResult)
   - 是否使用 AndroidX/Jetpack 替代方案?
6. Manifest 检查:
   - 新增的 Activity/Service/Receiver 是否在 Manifest 声明?
   - exported 属性是否正确设置? (Android 12+ 默认 false)
   - intent-filter 是否安全?
   - 网络安全配置 (networkSecurityConfig) 是否合理?
7. ProGuard/R8:
   - 新增的模型类是否添加 @Keep 或 keep 规则?
   - 反射使用的类是否有 keep 规则?
   - 第三方库是否有必要的 keep 规则?

输出格式 (严格控制在 300 字以内):
- 结论: 通过 / 需要调整
- 问题列表 (如有):
  - 文件:行号 | 严重程度 (阻塞/建议) | 问题类型 | 描述 | 修复建议
```

### 步骤 6: 派发可测试性审查

```
你是 Android 可测试性审查员。审查以下代码变更的可测试性。

项目技术栈: <技术栈档案>
项目架构: <架构推断>
变更范围: <变更摘要>

Diff:
<完整 diff 或相关文件 diff>

审查要点:
1. 依赖可 mock:
   - 类的依赖是否通过构造函数注入? (可 mock)
   - 是否有硬编码的单例调用? (如 Retrofit.Builder().build() 在方法内部)
   - 是否有 static 方法调用? (如 Log.d, TextUtils.isEmpty)
   - 是否有 System.currentTimeMillis() 等不可控的系统调用?
2. 代码结构可测试:
   - 函数是否是纯函数或副作用明确?
   - 是否有上帝类 (God Class) 职责过多难以测试?
   - 业务逻辑是否与 Android 框架解耦?
3. 硬编码检测:
   - 是否硬编码了 URL/API endpoint?
   - 是否硬编码了超时时间/重试次数等配置?
   - 是否硬编码了测试数据/魔法数字?
   - 是否硬编码了字符串 (而非 string resource)?
4. 测试覆盖:
   - 新增代码是否有对应的测试文件?
   - 边界条件是否被测试覆盖? (null 输入、空集合、异常情况)
   - 是否有测试辅助工具? (TestRule、TestDispatcher、Fake 数据)

输出格式 (严格控制在 300 字以内):
- 结论: 通过 / 需要调整
- 问题列表 (如有):
  - 文件:行号 | 严重程度 (阻塞/建议) | 可测试性问题 | 描述 | 修复建议
```

### Subagent 并发控制

**最大并发数: 3 个。** 同时运行的 subagent 不得超过 3 个。
如果 diff 较小 (< 500 行)，可以串行派发以减少资源消耗。

派发顺序: 先派发维度 1-3 (架构、风格、生命周期)，收到结果后再派发维度 4-6
(线程、Android 特有、可测试性)。这样可以根据前三个维度的结果判断是否需要调整
后续审查的重点。

---

## Phase 3: 汇总审查结论

### 步骤 1: 收集所有 subagent 结论

所有 subagent 返回后，主 context 读取每个维度的审查结论。

### 步骤 2: 按严重程度分类

将所有维度发现的问题统一分类:

**分类标准:**

| 等级 | 标识 | 含义 | 处理 |
|------|------|------|------|
| 阻塞 | BLOCKER | 必须修复。存在崩溃风险、内存泄漏、安全漏洞或严重架构违反 | 阻止合并 |
| 建议 | WARNING | 应该修复。影响代码质量、可维护性或性能 | 建议修复 |
| 信息 | INFO | 供参考。风格偏好、优化建议 | 可选改进 |

### 步骤 3: 生成审查报告

```
╔══════════════════════════════════════════════════════╗
║              ANDROID 代码审查报告                      ║
╠══════════════════════════════════════════════════════╣
║                                                       ║
║  分支: <branch>                                       ║
║  比较: main...<branch>                                ║
║  变更: N 个文件 (+X / -Y)                             ║
║  审查时间: <日期>                                     ║
║                                                       ║
║  阻塞: N | 建议: N | 信息: N                         ║
║                                                       ║
║  总评: PASS / CONDITIONAL PASS / FAIL                ║
╚══════════════════════════════════════════════════════╝
```

**总评规则:**
- **PASS** — 无阻塞问题
- **CONDITIONAL PASS** — 有阻塞问题但可快速修复 (< 5 处)
- **FAIL** — 有阻塞问题且修复量大

### 步骤 4: 写入审查报告

审查报告写入 `docs/reviews/<branch>-code-review.md`:

```bash
# 确保目录存在
mkdir -p docs/reviews
```

**报告格式:**

```markdown
# 代码审查: <branch>

> 审查于 <日期> | android-code-review
> 比较: main...<branch>
> 变更: N 个文件 (+X / -Y 行)

## 总评: PASS / CONDITIONAL PASS / FAIL

- 阻塞: N
- 建议: N
- 信息: N

## 变更范围

- 涉及模块: app, feature:login, core:data
- 变更类型: 新增功能
- 主要变更: 实现登录功能，包含 UI、网络请求和本地存储

## BLOCKER (阻塞)

### [B1] Context 泄漏 — LoginViewModel
- **文件:** `app/src/main/java/.../LoginViewModel.kt:42`
- **维度:** 生命周期与内存安全
- **描述:** ViewModel 持有 Activity Context 引用，Activity 销毁后导致泄漏
- **建议:** 使用 AndroidViewModel 的 application context，或将 Context 依赖移除

### [B2] 主线程数据库查询
- **文件:** `app/src/main/java/.../LoginRepository.kt:78`
- **维度:** 线程与并发
- **描述:** Room DAO 查询未使用 suspend 或 IO dispatcher
- **建议:** 将函数声明为 suspend 函数，让 Room 自动在 IO 线程执行

## WARNING (建议)

### [W1] 硬编码 API URL
- **文件:** `app/src/main/java/.../AuthService.kt:15`
- **维度:** 可测试性
- **描述:** Base URL 硬编码在代码中
- **建议:** 使用 BuildConfig.BASE_URL 或 DI 注入

### [W2] 缺少 @Keep 注解
- **文件:** `app/src/main/java/.../LoginResponse.kt:5`
- **维度:** Android 特有
- **描述:** Retrofit 响应模型在 R8 混淆后可能字段丢失
- **建议:** 添加 @Keep 注解或在 proguard-rules.pro 中添加 keep 规则

## INFO (信息)

### [I1] 建议使用 sealed class
- **文件:** `app/src/main/java/.../LoginState.kt:3`
- **维度:** 命名与代码风格
- **描述:** 当前使用 enum 表示加载/成功/失败状态，sealed class 更灵活
- **建议:** 考虑改为 sealed class 以支持携带数据

## 维度审查总结

| 维度 | 结论 | 问题数 |
|------|------|--------|
| 架构一致性 | 通过 | 0 |
| 命名与代码风格 | 需要调整 | 1 建议 + 1 信息 |
| 生命周期与内存安全 | 需要调整 | 1 阻塞 |
| 线程与并发 | 需要调整 | 1 阻塞 |
| Android 特有 | 需要调整 | 1 建议 |
| 可测试性 | 需要调整 | 1 建议 |
```

### 步骤 5: 展示审查结果

在终端输出审查报告摘要，并告知报告文件路径:

> 审查完成。
> - 阻塞问题: N (必须修复)
> - 建议改进: N
> - 信息备注: N
> - 总评: CONDITIONAL PASS
> - 完整报告: `docs/reviews/<branch>-code-review.md`

如果有阻塞问题:
> 发现 N 个阻塞问题。建议修复后再合并。
> - A) 查看完整报告
> - B) 自动修复阻塞问题
> - C) 忽略并标记为 CONDITIONAL PASS

---

## 与其他 Skill 的衔接

```
/android-brainstorm       → 头脑风暴 → 需求定义
/android-autoplan         → 拆分 + 审查 → plan 文件
/android-design-review    → Figma 设计审查 → 设计规格
/android-worktree-runner  → 执行 plan → 代码变更 → /android-code-review (Phase 3 后自动调用)
/android-code-review      → 代码审查 → 审查报告
```

**自动调用场景:**
- android-worktree-runner Phase 3 (Plan 完成) 后，自动调用
  `/android-code-review <plan-branch>` 审查完成的 worktree 变更
- 用户手动调用 `/android-code-review` 审查任意分支或未提交变更

**衔接协议:**
- android-worktree-runner 完成后，传入 worktree 分支名作为参数
- 审查报告写入 `docs/reviews/` 目录，不修改源代码
- 审查报告中的阻塞问题可作为后续修复任务的输入

---

## 异常情况处理

| 场景 | 处理方式 |
|------|----------|
| 不在 Android 项目中 | 报错: "android-code-review 需要 Android 项目" |
| 不在 git 仓库中 | 报错: "android-code-review 需要 git 仓库" |
| main 分支不存在 | 尝试 origin/main、master，仍不存在则报错 |
| 指定分支不存在 | 报错: "未找到分支: <branch>" |
| 无任何变更 | 提示: "当前分支相对于 main 没有变更" 并退出 |
| diff 为空 | 提示: "没有需要审查的代码变更" 并退出 |
| 技术栈检测不明确 | 列出检测结果，标注置信度，不阻塞审查 |
| docs/reviews 目录不存在 | 自动创建 |
| Subagent 执行失败 | 重试一次，仍失败则跳过该维度并标注 "审查跳过" |
| 变更规模过大 (>50 文件) | 警告并询问是否继续，建议拆分 PR |

---

## 文件结构

```
项目根目录/
├── docs/
│   └── reviews/
│       └── <branch>-code-review.md     ← 审查报告
├── .claude/
│   ├── skills/
│   │   ├── android-code-review/
│   │   │   └── SKILL.md                ← 本 skill
│   │   ├── android-autoplan/
│   │   │   └── SKILL.md
│   │   ├── android-design-review/
│   │   │   └── SKILL.md
│   │   ├── android-worktree-runner/
│   │   │   └── SKILL.md
│   │   └── android-brainstorm/
│   │       └── SKILL.md
│   └── ...
└── ...
```
