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

# Android TDD

## 概述

契约定义 -> RED (写失败测试) -> GREEN (最小实现) -> REFACTOR (安全重构) -> 覆盖率门禁 -> 自动修复循环 + 独立验收。

强制测试先行，不跳过 RED 阶段。每次实现前必须先有对应失败测试，
确保代码行为由测试驱动而非直觉驱动。Android 平台边界测试矩阵覆盖
空数据、网络错误、权限拒绝、生命周期等典型场景。

**启动时声明:** "我正在使用 android-tdd skill。"

**零外部依赖:** 仅使用 Claude Code 原生工具。不依赖 gstack、browse、Codex、Figma MCP。

## 调用方式

```bash
/android-tdd <feature-description>    # 独立调用: 对指定功能执行完整 TDD 流程
/android-tdd                           # 交互式: 引导输入功能描述后执行
/android-tdd verify <test-dir>         # 仅覆盖率验证: 检查指定测试目录的覆盖率是否达标
```

**参数处理:**

| 模式 | 参数 | 行为 |
|------|------|------|
| 独立调用 | `<feature-description>` | 直接对描述的功能执行完整 TDD 流程 (Phase 0 -> Phase 1 -> ... -> Phase 5) |
| 交互式 | 无参数 | 引导用户输入功能描述，确认后执行完整 TDD 流程 |
| 覆盖率验证 | `verify <test-dir>` | 跳过 Phase 1-4，直接进入 Phase 5 (覆盖率门禁)，验证指定测试目录 |

**模式选择逻辑:**
1. 第一个参数为 `verify` -> 覆盖率验证模式
2. 有参数但非 `verify` -> 独立调用模式
3. 无参数 -> 交互式模式

---

## Phase 0: 环境检测

在执行任何 TDD 流程前，自动检测项目测试基础设施。检测结果贯穿后续所有阶段。

### 步骤 1: 确定项目根目录和基本信息

```bash
# Project root
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -z "$PROJECT_ROOT" ]; then
  echo "ERROR: Not a git repository"
  exit 1
fi

# Confirm Android project
if [ ! -f "$PROJECT_ROOT/build.gradle" ] && [ ! -f "$PROJECT_ROOT/build.gradle.kts" ] && \
   [ ! -f "$PROJECT_ROOT/app/build.gradle" ] && [ ! -f "$PROJECT_ROOT/app/build.gradle.kts" ]; then
  echo "ERROR: Not an Android project (missing build.gradle / settings.gradle)"
  exit 1
fi

echo "PROJECT_ROOT: $PROJECT_ROOT"

# Gradle wrapper
if [ -f "$PROJECT_ROOT/gradlew" ]; then
  [ ! -x "$PROJECT_ROOT/gradlew" ] && chmod +x "$PROJECT_ROOT/gradlew"
  echo "GRADLE_WRAPPER: available"
else
  echo "GRADLE_WRAPPER: not found"
fi

# Current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "BRANCH: $CURRENT_BRANCH"
```

### 步骤 2: 检测测试框架

```bash
# --- Unit test framework: JUnit4 vs JUnit5 ---
JUNIT4=$(grep -rl "import org.junit" "$PROJECT_ROOT" --include="*.kt" --include="*.java" 2>/dev/null | head -5)
JUNIT5=$(grep -rl "import org.junit.jupiter" "$PROJECT_ROOT" --include="*.kt" --include="*.java" 2>/dev/null | head -5)

if [ -n "$JUNIT5" ]; then
  echo "UNIT_FRAMEWORK: JUnit5"
elif [ -n "$JUNIT4" ]; then
  echo "UNIT_FRAMEWORK: JUnit4"
else
  echo "UNIT_FRAMEWORK: NOT_DETECTED"
fi

# Gradle dependency check
grep -r "junit-jupiter\|junit-jupiter-api\|junit-jupiter-engine" \
  "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" \
  "$PROJECT_ROOT/build.gradle" "$PROJECT_ROOT/build.gradle.kts" 2>/dev/null | head -3
grep -r "junit:junit\|androidx.test.ext:junit" \
  "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" \
  "$PROJECT_ROOT/build.gradle" "$PROJECT_ROOT/build.gradle.kts" 2>/dev/null | head -3
```

```bash
# --- Mocking: Mockito vs MockK ---
MOCKITO=$(grep -rl "import org.mockito" "$PROJECT_ROOT" --include="*.kt" --include="*.java" 2>/dev/null | head -5)
MOCKK=$(grep -rl "import io.mockk" "$PROJECT_ROOT" --include="*.kt" --include="*.java" 2>/dev/null | head -5)

if [ -n "$MOCKK" ]; then
  echo "MOCK_FRAMEWORK: MockK"
elif [ -n "$MOCKITO" ]; then
  echo "MOCK_FRAMEWORK: Mockito"
else
  echo "MOCK_FRAMEWORK: NOT_DETECTED"
fi

# Gradle dependency check
grep -r "mockk\|mockito" \
  "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" \
  "$PROJECT_ROOT/build.gradle" "$PROJECT_ROOT/build.gradle.kts" 2>/dev/null | head -3
```

```bash
# --- Assertion: Truth vs AssertJ vs Standard ---
TRUTH=$(grep -rl "import com.google.common.truth" "$PROJECT_ROOT" --include="*.kt" --include="*.java" 2>/dev/null | head -5)
ASSERTJ=$(grep -rl "import org.assertj" "$PROJECT_ROOT" --include="*.kt" --include="*.java" 2>/dev/null | head -5)

if [ -n "$TRUTH" ]; then
  echo "ASSERTION_LIB: Truth"
elif [ -n "$ASSERTJ" ]; then
  echo "ASSERTION_LIB: AssertJ"
else
  echo "ASSERTION_LIB: Standard (assertEquals / assertThat from JUnit)"
fi

# Gradle dependency check
grep -r "com.google.truth\|assertj" \
  "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" \
  "$PROJECT_ROOT/build.gradle" "$PROJECT_ROOT/build.gradle.kts" 2>/dev/null | head -3
```

### 步骤 3: 检测 UI 测试框架

```bash
# --- Espresso vs Compose Testing ---
COMPOSE_TEST=$(grep -rl "import androidx.compose.ui.test" "$PROJECT_ROOT" --include="*.kt" 2>/dev/null | head -5)
ESPRESSO=$(grep -rl "import androidx.test.espresso" "$PROJECT_ROOT" --include="*.kt" --include="*.java" 2>/dev/null | head -5)

# Also check Compose usage in source (not just tests)
COMPOSE_SRC=$(grep -rl "@Composable" "$PROJECT_ROOT/app/src/main" --include="*.kt" 2>/dev/null | head -5)

if [ -n "$COMPOSE_TEST" ]; then
  echo "UI_TEST_FRAMEWORK: Compose Testing"
elif [ -n "$ESPRESSO" ]; then
  echo "UI_TEST_FRAMEWORK: Espresso"
elif [ -n "$COMPOSE_SRC" ]; then
  echo "UI_TEST_FRAMEWORK: Compose (source detected, no tests yet)"
else
  echo "UI_TEST_FRAMEWORK: NOT_DETECTED"
fi

# Gradle dependency check
grep -r "androidx.compose.ui:ui-test\|androidx.compose.ui:ui-test-junit4\|androidx.compose.ui:ui-test-manifest" \
  "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null | head -3
grep -r "androidx.test.espresso" \
  "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null | head -3
```

### 步骤 4: 检测 DI 框架

```bash
# --- Hilt vs Koin ---
HILT=$(grep -rl "import dagger.hilt\|import javax.inject" "$PROJECT_ROOT" --include="*.kt" --include="*.java" 2>/dev/null | head -5)
KOIN=$(grep -rl "import org.koin" "$PROJECT_ROOT" --include="*.kt" --include="*.java" 2>/dev/null | head -5)

if [ -n "$HILT" ]; then
  echo "DI_FRAMEWORK: Hilt"
elif [ -n "$KOIN" ]; then
  echo "DI_FRAMEWORK: Koin"
else
  echo "DI_FRAMEWORK: NOT_DETECTED"
fi

# Gradle dependency check
grep -r "com.google.dagger:hilt\|io.insert-koin" \
  "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" \
  "$PROJECT_ROOT/build.gradle" "$PROJECT_ROOT/build.gradle.kts" 2>/dev/null | head -3

# Check for Hilt Gradle plugin
grep -r "dagger.hilt.android.plugin\|com.google.dagger.hilt.android" \
  "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" \
  "$PROJECT_ROOT/build.gradle" "$PROJECT_ROOT/build.gradle.kts" 2>/dev/null | head -3
```

### 步骤 5: 检测模块结构和构建变体

```bash
# --- Modules from settings.gradle.kts ---
SETTINGS_FILE="$PROJECT_ROOT/settings.gradle"
[ -f "$PROJECT_ROOT/settings.gradle.kts" ] && SETTINGS_FILE="$PROJECT_ROOT/settings.gradle.kts"

echo "=== Modules ==="
cat "$SETTINGS_FILE" 2>/dev/null | grep -E "include\s*[\(:]" | sed 's/.*include\s*//;s/[\(,\)]//g;s/:/ /g'

# --- Build variants ---
echo "=== Build Variants ==="
grep -r "buildTypes\|productFlavors" "$PROJECT_ROOT/app" --include="*.gradle*" 2>/dev/null | head -10

# --- SDK versions ---
echo "=== SDK Versions ==="
grep -E "minSdk|targetSdk|compileSdk" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null | head -5
```

### 步骤 6: 检测已有测试目录结构

```bash
# --- Unit test directories ---
echo "=== Unit Test Dirs ==="
find "$PROJECT_ROOT" -path "*/src/test/*" -type f \( -name "*.kt" -o -name "*.java" \) 2>/dev/null | head -20

# --- Android instrumented test directories ---
echo "=== Instrumented Test Dirs ==="
find "$PROJECT_ROOT" -path "*/src/androidTest/*" -type f \( -name "*.kt" -o -name "*.java" \) 2>/dev/null | head -20

# --- Count existing tests ---
UNIT_TEST_COUNT=$(find "$PROJECT_ROOT" -path "*/src/test/*" -type f \( -name "*.kt" -o -name "*.java" \) 2>/dev/null | wc -l)
INSTRUMENTED_TEST_COUNT=$(find "$PROJECT_ROOT" -path "*/src/androidTest/*" -type f \( -name "*.kt" -o -name "*.java" \) 2>/dev/null | wc -l)

echo "UNIT_TEST_FILES: $UNIT_TEST_COUNT"
echo "INSTRUMENTED_TEST_FILES: $INSTRUMENTED_TEST_COUNT"

# --- Check for shared test utilities ---
echo "=== Shared Test Utilities ==="
find "$PROJECT_ROOT" -path "*/src/testFixtures/*" -type f \( -name "*.kt" -o -name "*.java" \) 2>/dev/null | head -10
find "$PROJECT_ROOT" -path "*/src/sharedTest/*" -type f \( -name "*.kt" -o -name "*.java" \) 2>/dev/null | head -10
```

### 步骤 7: 检测覆盖率工具 (JaCoCo)

```bash
# --- JaCoCo plugin ---
echo "=== Coverage Tool ==="
JACOCO_PLUGIN=$(grep -r "jacoco" \
  "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" \
  "$PROJECT_ROOT/build.gradle" "$PROJECT_ROOT/build.gradle.kts" 2>/dev/null | head -5)

if [ -n "$JACOCO_PLUGIN" ]; then
  echo "COVERAGE_TOOL: JaCoCo"

  # Extract JaCoCo version if configured
  grep -r "jacocoVersion\|jacoco.*version" \
    "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" \
    "$PROJECT_ROOT/build.gradle" "$PROJECT_ROOT/build.gradle.kts" 2>/dev/null | head -3

  # Check for existing coverage thresholds
  echo "=== Coverage Thresholds ==="
  grep -r "minimumCoverage\|coveredRatio\|branchCoverage\|lineCoverage\|instructionCoverage" \
    "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" \
    "$PROJECT_ROOT/build.gradle" "$PROJECT_ROOT/build.gradle.kts" 2>/dev/null | head -5
else
  echo "COVERAGE_TOOL: NOT_DETECTED"
  echo "NOTE: JaCoCo plugin not found in build config. Coverage verification will be limited."
fi

# Check for JaCoCo test reports from previous runs
echo "=== Existing Coverage Reports ==="
find "$PROJECT_ROOT" -path "*/reports/jacoco/*" -type f 2>/dev/null | head -5
find "$PROJECT_ROOT" -name "jacocoTestReport.xml" -o -name "jacocoTestDebugUnitTestReport.xml" 2>/dev/null | head -5
```

### 步骤 8: 检测语言和架构

```bash
# --- Language: Kotlin vs Java vs Mixed ---
KOTLIN_FILES=$(find "$PROJECT_ROOT/app/src/main" -name "*.kt" 2>/dev/null | wc -l)
JAVA_FILES=$(find "$PROJECT_ROOT/app/src/main" -name "*.java" 2>/dev/null | wc -l)

if [ "$KOTLIN_FILES" -gt 0 ] && [ "$JAVA_FILES" -gt 0 ]; then
  echo "LANGUAGE: Kotlin + Java (mixed)"
elif [ "$KOTLIN_FILES" -gt 0 ]; then
  echo "LANGUAGE: Kotlin"
elif [ "$JAVA_FILES" -gt 0 ]; then
  echo "LANGUAGE: Java"
else
  echo "LANGUAGE: NOT_DETECTED"
fi

# --- Architecture pattern ---
echo "=== Architecture Detection ==="
grep -rl "ViewModel" "$PROJECT_ROOT/app/src/main" --include="*.kt" 2>/dev/null | head -3
grep -rl "Repository" "$PROJECT_ROOT/app/src/main" --include="*.kt" 2>/dev/null | head -3
grep -rl "UseCase\|Interactor" "$PROJECT_ROOT/app/src/main" --include="*.kt" 2>/dev/null | head -3
grep -rl "Reducer\|Action\|Event" "$PROJECT_ROOT/app/src/main" --include="*.kt" 2>/dev/null | head -3

# Package structure
echo "=== Package Structure ==="
find "$PROJECT_ROOT/app/src/main/java" -type d -maxdepth 6 2>/dev/null | head -20
find "$PROJECT_ROOT/app/src/main/kotlin" -type d -maxdepth 6 2>/dev/null | head -20
```

### 步骤 9: 输出技术栈档案

汇总以上所有检测结果，输出格式:

```
=== TDD 环境档案 ===
项目根目录:   /path/to/project
当前分支:     feature/login
语言:         Kotlin
Gradle:       gradlew available

--- 测试基础设施 ---
单元测试框架: JUnit4
Mock 框架:    MockK
断言库:       Truth
UI 测试框架:  Compose Testing
DI 框架:      Hilt

--- 项目结构 ---
模块列表:     app, feature:login, core:data, core:common
构建变体:     debug, release
SDK:          minSdk 24 | targetSdk 34 | compileSdk 34
架构:         MVVM

--- 测试现状 ---
单元测试文件: 23
插桩测试文件: 5
覆盖率工具:   JaCoCo (已配置)
覆盖率门禁:   NOT_CONFIGURED (使用默认 80%)

--- 目录结构 ---
src/test:         已存在 (23 files)
src/androidTest:  已存在 (5 files)
testFixtures:     未检测到
```

**检测结果使用规则:**

| 检测项 | 已检测到 | 未检测到 | 处理方式 |
|--------|---------|---------|----------|
| 单元测试框架 | 使用检测到的框架 | 提示用户确认 | 写测试时使用对应注解和 API |
| Mock 框架 | 使用检测到的框架 | 默认 MockK (Kotlin 项目) | 影响模拟对象的写法 |
| 断言库 | 使用检测到的库 | 默认 JUnit 标准 | 影响断言语法 |
| UI 测试框架 | 使用检测到的框架 | 根据 UI 框架推断 | Compose 项目 -> Compose Testing |
| DI 框架 | 记录 | 记录 | 影响测试中的依赖注入方式 |
| 覆盖率工具 | 使用 JaCoCo | 提示配置 JaCoCo | Phase 5 依赖覆盖率报告 |

**如果覆盖率工具未检测到:**
提示用户在 build.gradle.kts 中添加 JaCoCo 插件配置，或使用 `./gradlew testDebugUnitTest` 执行测试后在 build/reports 中查找覆盖率数据。

---

## Phase 1: 契约定义

在写任何测试或实现之前，先定义接口和类型签名。这是 TDD 的基础 — 测试需要依赖稳定的契约。

### 步骤 1: 分析需求描述

从调用参数或 worktree-runner 的任务描述中提取功能需求:
- 核心功能是什么? (CRUD / 状态管理 / 数据转换 / UI 交互)
- 涉及哪些 Android 组件? (ViewModel / Repository / UseCase / Composable)
- 数据流向是什么? (UI → ViewModel → UseCase → Repository → API/DB)

### 步骤 2: 定义接口和类型

根据需求自动判断需要定义的契约类型:

**需求关键词 → 契约映射表:**

| 需求关键词 | 需要定义的契约 |
|-----------|-------------|
| "API" / "network" / "接口" | Repository 接口 + DTO data class + API Response sealed class |
| "screen" / "page" / "UI" / "界面" | ViewModel 接口 + UI State sealed class + Event sealed class |
| "business logic" / "use case" / "业务" | UseCase 接口 (input type → output type) |
| "form" / "validation" / "表单" | Validator 接口 + ValidationResult sealed class |
| "list" / "RecyclerView" / "LazyColumn" | Item model + Diff callback / key extractor |
| "navigation" / "route" | NavRoute sealed class / deep link mapping |

**Android 标准契约模板:**

**ViewModel 契约:**
```kotlin
// 接口 (测试 mock 用)
interface XxxViewModel {
    val uiState: StateFlow<XxxUiState>
    fun onIntent(intent: XxxIntent)
}

// UI 状态
sealed interface XxxUiState {
    data object Loading : XxxUiState
    data class Success(val data: XxxData) : XxxUiState
    data class Error(val message: String) : XxxUiState
}

// 用户意图
sealed interface XxxIntent {
    data class LoadData(val id: String) : XxxIntent
    data class Refresh(val force: Boolean = false) : XxxIntent
}
```

**Repository 契约:**
```kotlin
interface XxxRepository {
    suspend fun getData(id: String): Result<XxxData>
    suspend fun saveData(data: XxxData): Result<Unit>
}
```

**UseCase 契约:**
```kotlin
class XxxUseCase(
    private val repository: XxxRepository
) {
    suspend operator fun invoke(params: XxxParams): Result<XxxOutput>
}
```

### 步骤 3: 输出契约文件

将定义的接口和类型写入对应模块的源码目录:
- 接口: `src/main/java/.../XxxViewModel.kt` (仅签名，无实现)
- 测试可以引用这些接口进行 mock

**契约确认:**
使用 AskUserQuestion 展示定义的契约摘要:
> 已定义以下契约:
> - XxxViewModel 接口 + XxxUiState + XxxIntent
> - XxxRepository 接口
> - XxxData data class
>
> 是否需要调整?
> - A) 确认，进入 Phase 2
> - B) 修改契约
> - C) 补充契约

---

## Phase 2: RED — 写失败测试

基于 Phase 1 定义的契约，编写测试用例。所有测试在此阶段必须失败 (因为实现还不存在)。

### 步骤 1: 生成标准测试用例

对每个契约接口，生成以下测试类别:

**Happy Path (正常路径):**
- 主要功能的正常调用
- 预期输入 → 预期输出

**Edge Cases (边界条件):**
- 空值 (null input)
- 空集合 (empty list)
- 极端值 (Int.MAX_VALUE, Long.MIN_VALUE, empty string, very long string)
- 边界索引 (0, size-1, size)
- 重复操作 (idempotency)

**Error Paths (异常路径):**
- 网络失败 (IOException, SocketTimeoutException)
- 权限拒绝 (SecurityException)
- 数据不存在 (NotFoundException)
- 超时 (TimeoutCancellationException)
- 并发冲突 (OptimisticLockException)

### 步骤 2: 匹配 Android 平台边界测试矩阵

根据需求描述自动匹配需要覆盖的边界类别:

| 类别 | 测试场景 | 测试类型 | 匹配关键词 |
|------|---------|---------|-----------|
| 生命周期 | Activity/Fragment 重建、Process Death 恢复 | Instrumented | "Activity"、"Fragment"、"process" |
| 配置变更 | 深色模式切换、Locale 切换、屏幕旋转、多窗口 | Instrumented | "theme"、"locale"、"rotation"、"config" |
| 权限 | 权限拒绝、权限撤销、永不询问 | Instrumented | "permission"、"camera"、"location"、"storage" |
| 网络 | 无网络→有网络、超时、DNS 失败、慢网络 | JVM Unit (mock) | "network"、"API"、"http"、"retrofit" |
| 存储 | 磁盘满、数据库损坏、SharedPreferences 迁移 | JVM Unit (mock) | "database"、"Room"、"storage"、"cache" |
| 并发 | 协程竞争、Flow 背压、ViewModel 重复点击 | JVM Unit (mock) | "coroutine"、"Flow"、"concurrent"、"click" |
| 内存 | 大图片 OOM、长列表 RecyclerView、内存泄漏 | Instrumented | "image"、"RecyclerView"、"LazyColumn"、"memory" |
| 兼容性 | API level 边界 (minSdk)、不同屏幕尺寸 | 静态分析 | "compatibility"、"minSdk"、"screen"、"responsive" |

**自动匹配规则:**
- 需求提到 "网络" / "API" / "http" / "retrofit" → Network 类别 (4 个场景)
- 需求提到 "列表" / "RecyclerView" / "LazyColumn" → Memory 类别 (2 个场景)
- 需求提到 "设置" / "preferences" / "配置" → Config Change 类别 (4 个场景)
- 需求提到 "定位" / "相机" / "存储" / "权限" → Permissions 类别 (3 个场景)
- 需求提到 "数据库" / "Room" / "缓存" → Storage 类别 (3 个场景)
- 需求提到 "协程" / "Flow" / "并发" → Concurrency 类别 (3 个场景)
- 需求提到 "图片" / "Bitmap" / "加载" → Memory 类别 (2 个场景)

**如果需求没有匹配任何关键词:** 默认覆盖 Network 和 Concurrency 两个类别 (最常见的风险点)。

### 步骤 3: 选择测试类型

根据被测代码的性质选择测试类型:

| 被测类型 | 测试类型 | 测试目录 | 运行命令 |
|---------|---------|---------|---------|
| ViewModel / UseCase / Repository / Mapper | JVM Unit Test | `src/test/` | `./gradlew test<Variant>UnitTest` |
| Composable (纯 UI 逻辑) | JVM Unit Test (with Robolectric) | `src/test/` | `./gradlew test<Variant>UnitTest` |
| Activity / Fragment / 真实 UI 交互 | Instrumented Test | `src/androidTest/` | `./gradlew connected<Variant>AndroidTest` |
| 混合 (ViewModel + Compose) | 拆分: JVM 测逻辑, Instrumented 测 UI | 两处 | 分别运行 |

**其中 `<Variant>` 由 Phase 0 检测到的构建变体决定 (默认: `Debug`)。**

### 步骤 4: 编写测试代码

根据 Phase 1 的契约和上述分析，生成测试文件。

**测试文件命名规范:**
```
src/test/java/.../XxxViewModelTest.kt
src/test/java/.../XxxRepositoryTest.kt
src/test/java/.../XxxUseCaseTest.kt
src/androidTest/java/.../XxxScreenTest.kt
```

**测试结构 (JUnit5 + MockK 示例):**
```kotlin
@OptIn(ExperimentalCoroutinesApi::class)
class LoginViewModelTest {

    private lateinit var viewModel: LoginViewModel
    private val repository: AuthRepository = mockk()

    @Before
    fun setup() {
        Dispatchers.setMain(StandardTestDispatcher())
        viewModel = LoginViewModel(repository)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    // --- Happy Path ---
    @Test
    fun `login success - updates uiState to Success`() = runTest {
        // Arrange
        coEvery { repository.login(any()) } returns Result.success(UserToken("abc"))

        // Act
        viewModel.onIntent(LoginIntent.Submit("user@example.com", "pass"))

        // Assert
        assertEquals(LoginUiState.Success(UserToken("abc")), viewModel.uiState.value)
    }

    // --- Edge Cases ---
    @Test
    fun `login with empty email - stays in Idle`() = runTest {
        viewModel.onIntent(LoginIntent.Submit("", "pass"))
        assertEquals(LoginUiState.Idle, viewModel.uiState.value)
    }

    // --- Error Paths ---
    @Test
    fun `login network failure - updates uiState to Error`() = runTest {
        coEvery { repository.login(any()) } returns Result.failure(IOException("Network error"))

        viewModel.onIntent(LoginIntent.Submit("user@example.com", "pass"))

        assertTrue(viewModel.uiState.value is LoginUiState.Error)
    }

    // --- Android Platform Boundary: Network ---
    @Test
    fun `login timeout - updates uiState to Error with timeout message`() = runTest {
        coEvery { repository.login(any()) } returns Result.failure(
            TimeoutCancellationException("Request timed out")
        )

        viewModel.onIntent(LoginIntent.Submit("user@example.com", "pass"))

        val state = viewModel.uiState.value as LoginUiState.Error
        assertTrue(state.message.contains("timeout", ignoreCase = true))
    }
}
```

**如果检测到 JUnit4 (非 JUnit5):** 使用 `@RunWith(MockKJUnitRunner::class)` 替代 `@Test`，使用 `@Before` / `@After` (JUnit4 风格)。

**如果检测到 Mockito (非 MockK):** 使用 `@Mock` + `when().thenReturn()` 替代 `mockk()` + `coEvery`。

**如果检测到 Truth:** 使用 `assertThat(x).isEqualTo(y)` 替代 `assertEquals(x, y)`。

**如果检测到 Espresso (非 Compose Testing):** 使用 `@RunWith(AndroidJUnit4::class)` + `ActivityScenario` + `onView().perform()` 模式。

### 步骤 5: 运行测试并验证 RED

```bash
# JVM 单元测试
./gradlew test<Variant>UnitTest 2>&1
```

**RED 确认规则:**

| 测试结果 | 判定 | 处理 |
|---------|------|------|
| 全部失败 (编译错误) | ✅ RED 确认 | 继续 Phase 3 |
| 部分失败 (部分通过) | ⚠️ 异常 | 检查是否有既有代码被意外测试到 |
| 全部通过 | ❌ RED 失败 | 测试没有实际验证行为，必须重写 |

**如果测试意外通过:** 说明契约定义可能不完整，或测试断言不够严格。回退到 Phase 1 检查契约，或增强测试断言。

**如果存在 Instrumented 测试:**
```bash
./gradlew connected<Variant>AndroidTest 2>&1
```

**注意:** Instrumented 测试需要设备/模拟器。如果没有可用设备，跳过并记录:
```
⚠️ Instrumented 测试跳过: 无可用设备/模拟器
受影响的测试: XxxScreenTest.kt (N 个测试用例)
这些测试需要在有设备的环境中手动运行
```

### 步骤 6: 输出测试摘要

```
=== RED 确认 ===
JVM 单元测试: N written, N failed ✅
Instrumented 测试: N written, N skipped (无设备)
边界矩阵覆盖: Network (4), Concurrency (3), Storage (2)

测试文件:
  src/test/.../LoginViewModelTest.kt (12 tests)
  src/test/.../AuthRepositoryTest.kt (8 tests)
  src/androidTest/.../LoginScreenTest.kt (5 tests, skipped)
```

---

## Phase 3: GREEN — 最小实现

写刚好让 Phase 2 所有测试通过的最少代码。

**在实现代码前，保存当前工作区状态 (savepoint):**

```bash
# 保存 TDD 前状态，便于失败时回滚
git add -A 2>/dev/null || true
git stash push -m "tdd-savepoint-before-green" --keep-index 2>/dev/null || true
echo "TDD savepoint created"
```

> 如果后续 Phase 5 或 Phase 6 失败，可以执行 `git stash pop` 恢复到此状态。

### 步骤 1: 实现契约

根据 Phase 1 定义的接口，编写最小实现:

**实现原则:**
- 只写让测试通过的代码，不写多余功能
- 如果一个 if-else 能让测试通过，不要写策略模式
- 如果一个简单循环能通过，不要用 Stream
- 每次只实现一个测试所需的逻辑

**实现顺序:**
1. 先实现 Happy Path 测试所需的最少代码
2. 运行测试 → 部分 PASS
3. 逐个实现 Edge Case 和 Error Path 所需的代码
4. 每实现一个，运行一次测试
5. 直到全部 PASS

### 步骤 2: 运行测试验证 GREEN

```bash
./gradlew test<Variant>UnitTest 2>&1
```

**GREEN 确认规则:**

| 测试结果 | 判定 | 处理 |
|---------|------|------|
| 全部通过 | ✅ GREEN 确认 | 继续 Phase 4 |
| 部分失败 | ❌ 继续实现 | 分析失败原因，补充实现 |
| 全部失败 | ❌ 实现有误 | 回退检查实现 |

**如果测试仍然失败:**
1. 读取失败测试的错误信息
2. 判断失败原因:
   - 编译错误 → 修复语法/类型
   - Mock 配置错误 → 修复 when/thenReturn
   - 逻辑错误 → 修复实现
3. 修复后重新运行
4. 如果连续 3 次修复后仍有失败 → 进入 Phase 6 自动修复循环

**禁止事项:**
- ❌ "顺便" 添加未测试的功能
- ❌ 在实现中添加 "未来可能需要" 的代码
- ❌ 跳过失败的测试
- ❌ 修改测试来匹配实现 (只能修改实现)

### 步骤 3: 输出 GREEN 摘要

```
=== GREEN 确认 ===
JVM 单元测试: N/N passed ✅
实现文件:
  src/main/java/.../LoginViewModel.kt
  src/main/java/.../AuthRepositoryImpl.kt
```

---

## Phase 4: REFACTOR — 安全重构

在测试绿灯下改善代码质量。

### 步骤 1: 识别重构机会

扫描刚实现的代码，寻找:
- 重复代码 (提取函数/扩展函数)
- 命名不清晰的变量/函数
- 过长的函数 (>30 行)
- 嵌套过深的逻辑 (>3 层)
- 可以用 Kotlin 标准库简化的代码

### 步骤 2: 执行重构

**重构规则:**
- 每次只做一个小重构
- 每次重构后立即运行测试
- 如果测试失败 → 立即回退，尝试更小的重构
- 不改变外部行为 (测试是行为规范)

**常见 Android 重构:**

| 重构类型 | 示例 |
|---------|------|
| 提取扩展函数 | `String.isValidEmail()` 替代内联验证逻辑 |
| 使用 Kotlin 协程作用域 | `viewModelScope.launch` 替代 `GlobalScope` |
| 使用 sealed class | 替代 `when + else` 分支 |
| 使用 Result 封装 | 替代 try-catch 散布 |
| 提取 Mapper | `Dto.toDomain()` 替代在 Repository 中转换 |

### 步骤 3: 运行测试确认仍为 GREEN

```bash
./gradlew test<Variant>UnitTest 2>&1
```

**如果测试失败:** 立即回退重构，记录原因。

**如果没有重构机会:**
```
=== REFACTOR ===
未发现显著重构机会。代码质量可接受。
```

---

## Phase 5: 覆盖率门禁

验证测试覆盖率是否达标。

### 步骤 1: 运行覆盖率分析

```bash
# 运行测试并生成覆盖率报告
./gradlew test<Variant>UnitTest 2>&1

# 查找 JaCoCo XML 报告
JACOCO_XML=$(find "$PROJECT_ROOT" -path "*/reports/jacoco/*/*.xml" -type f 2>/dev/null | head -1)
JACOCO_HTML=$(find "$PROJECT_ROOT" -path "*/reports/jacoco/*/index.html" -type f 2>/dev/null | head -1)

# 如果没有 JaCoCo 报告，检查 Gradle 内置覆盖率
if [ -z "$JACOCO_XML" ]; then
  echo "NOTE: JaCoCo XML 报告未找到，尝试 Gradle 内置覆盖率"
  ./gradlew test<Variant>UnitTest --info 2>&1 | grep -i "coverage"
fi
```

### 步骤 2: 解析覆盖率数据

**从 JaCoCo XML 报告解析:**

```bash
if [ -f "$JACOCO_XML" ]; then
  # 提取总体行覆盖率
  LINE_COVERAGE=$(grep 'LINE' "$JACOCO_XML" | grep -oP 'missed="\d+"' | head -1)
  BRANCH_COVERAGE=$(grep 'BRANCH' "$JACOCO_XML" | grep -oP 'missed="\d+"' | head -1)
fi
```

**覆盖率门禁规则:**

| 指标 | 阈值 | 不达标的处理 |
|------|------|-------------|
| 总体行覆盖率 | 80% | 自动补测试 |
| 关键路径覆盖率 | 90% | 自动补测试 |
| 分支覆盖率 | 75% | 记录为建议 |

**关键路径定义:**
文件名匹配以下模式的文件要求 90%+ 覆盖率:
- `*ViewModel.kt`
- `*Repository.kt` / `*RepositoryImpl.kt`
- `*UseCase.kt`

### 步骤 3: 覆盖率不达标时自动补测试

对于低于阈值的文件:

1. **读取源码** — 识别未覆盖的分支和逻辑
2. **生成补充测试** — 针对未覆盖路径
3. **运行测试** — 验证补充测试通过
4. **重新检查覆盖率** — 确认改善

```bash
# 补充测试后重新运行覆盖率
./gradlew test<Variant>UnitTest 2>&1
```

**最多补 2 轮。** 如果 2 轮后仍不达标:
- 记录未达标文件和当前覆盖率
- 继续进入 Phase 6 (修复循环可能进一步改善)

### 步骤 4: 输出覆盖率摘要

```
=== 覆盖率门禁 ===
来源: JaCoCo / Gradle 内置

总体行覆盖率: 87% ✅ (阈值: 80%)
分支覆盖率:   79% ✅ (阈值: 75%)
关键路径:     92% ✅ (阈值: 90%)

文件级详情:
  ✅ LoginViewModel.kt      94% (关键路径)
  ✅ AuthRepositoryImpl.kt  91% (关键路径)
  🟡 LoginScreen.kt         78% (建议: 补充状态绑定测试)
  ❌ TokenMapper.kt         45% → 已补充 3 个测试，提升至 72%

补充测试: N 个新增测试
```

**如果 JaCoCo 未配置:**
```
=== 覆盖率门禁 ===
⚠️ JaCoCo 未配置，无法精确测量覆盖率。
建议: 在 build.gradle.kts 中添加 JaCoCo 插件配置。
使用测试通过率作为替代指标: N/N passed ✅
```

---

## Phase 6: 自动修复循环

当 Phase 2-5 中任何阶段失败时，进入自动修复循环。
4 轮循环，严重程度逐级升级。

### 进入条件

以下任一情况触发 Phase 6:
- Phase 2 (RED): 测试意外通过 (非预期行为)
- Phase 3 (GREEN): 测试仍然失败 (实现有误)
- Phase 4 (REFACTOR): 重构后测试失败
- Phase 5 (Coverage): 覆盖率不达标 (2 轮补充后仍不足)

### Round 1: 机械修复 (自动，无需用户确认)

**目标:** 修复编译错误、配置错误、简单语法问题。

**自动修复范围:**

| 问题类型 | 修复方式 | 示例 |
|---------|---------|------|
| 缺少 import | 添加对应 import 语句 | `import java.io.IOException` |
| 类型不匹配 | 修正变量/返回类型 | `String` → `Int` |
| Mock 配置错误 | 修正 when/thenReturn | `coEvery { ... } returns ...` |
| 测试注解缺失 | 添加 @Test / @Before | JUnit5 注解 |
| 错误的测试运行器 | 修正 @RunWith | `MockKJUnitRunner` |
| 方法签名不匹配 | 修正参数或返回值 | 对齐接口定义 |
| 空安全错误 | 添加 ?./!! 修正 | `user?.email` |

**执行方式:**
1. 读取错误信息
2. 定位出错的文件和行号
3. 使用 Edit 工具直接修复
4. 重新运行测试

**输出:**
```
=== Round 1: 机械修复 ===
自动修复: N 个问题
  ✅ [F1-001] 缺少 import java.io.IOException
  ✅ [F1-002] Mock 返回类型不匹配
  ✅ [F1-003] 缺少 @OptIn 注解

重新运行测试...
结果: N/N passed ✅ → 覆盖率检查...
```

### Round 2: 逻辑修复 (Subagent 根因分析 + 用户确认)

**触发条件:** Round 1 后测试仍然失败。

**目标:** 深入分析失败的根本原因，提出修复方案。

**执行方式:**

1. 收集失败信息:
   - 失败测试的完整错误消息
   - 失败测试的源码
   - 被测实现的源码
   - Phase 1 的契约定义

2. 派发独立 subagent 进行根因分析:
```
使用 Agent 工具派发:

你是 Android 测试调试专家。分析以下测试失败的根本原因。

契约定义:
<Phase 1 的接口/类型定义>

失败测试代码:
<测试源码>

被测实现代码:
<实现源码>

错误信息:
<测试运行输出>

你的任务:
1. 分析失败的根本原因 (不是表面症状)
2. 判断是测试问题还是实现问题
3. 提出具体的修复方案 (包含代码片段)
4. 评估修复后是否可能引入新问题

输出格式:
- 根因: <一句话描述>
- 修复方案: <具体代码变更>
- 风险评估: <低/中/高>
```

3. 展示修复方案给用户确认:
```
Round 2 分析完成:

根因: Repository 实现中未处理网络超时，导致 ViewModel 测试失败
修复方案: 在 AuthRepositoryImpl 中添加 timeout 配置
风险: 低

是否应用修复?
- A) 应用修复
- B) 跳过，手动处理
- C) 修改修复方案
```

4. 应用修复后重新运行测试

**输出:**
```
=== Round 2: 逻辑修复 ===
Subagent 分析: 1 个根因
  根因: Repository 未处理超时
  修复: 添加 withTimeout 配置
  用户确认: ✅ 已应用

重新运行测试...
结果: N/N passed ✅
```

### Round 3: 架构修复 (报告 + 用户介入)

**触发条件:** Round 2 后测试仍然失败。

**目标:** 问题可能出在架构层面，需要用户决策。

**执行方式:**

1. 生成详细诊断报告:
```
=== Round 3: 架构修复 ===

经过 2 轮修复仍未解决。问题可能是架构层面的。

诊断报告:
  失败测试: LoginViewModelTest.testLoginSuccess
  错误类型: IllegalStateException
  错误位置: LoginViewModel.kt:45
  根因分析: ViewModel 直接持有 Repository 的 MutableLiveData 引用，
           导致在测试中无法隔离。需要通过接口抽象或 StateFlow 解耦。

建议方案:
  A) 回到 Phase 1 重新定义契约 — 将 Repository 返回类型改为 Flow<Result<T>>
  B) 简化测试范围 — 暂时不测试此边界条件
  C) 手动修复 — 由用户直接修改代码
```

2. 使用 AskUserQuestion 让用户选择处理方式

3. 如果用户选择 A: 回到 Phase 1，重新定义契约后重新走 Phase 2-5
4. 如果用户选择 B: 标记该测试为已知限制，继续
5. 如果用户选择 C: 暂停 TDD 流程，等待用户手动修复

### Round 4: 独立验收 Subagent (无上下文继承)

**触发条件:** Round 1-3 完成后（无论是否全部修复），进行独立验收。

**核心原则:** 此 subagent 不继承主对话的任何上下文。
只注入 Phase 1 的契约定义和最终代码。避免确认偏见。

**执行方式:**

1. 派发独立验收 subagent:
```
使用 Agent 工具派发:

你是独立的代码验收员。你不了解任何背景信息，只根据提供的材料进行评估。

## 材料

契约定义 (Phase 1 产出):
<契约定义的接口和类型>

最终测试代码:
<所有测试文件的路径，让 subagent 自己读取>

最终实现代码:
<所有实现文件的路径，让 subagent 自己读取>

覆盖率报告 (Phase 5 产出):
<覆盖率数据>

## 你的任务

评估以下维度:

1. **契约合规性:** 实现是否完全满足契约定义?
2. **测试充分性:** 测试是否覆盖了 happy path + edge cases + error paths?
3. **覆盖率达标:** 是否满足 80% 总体 / 90% 关键路径?
4. **代码质量:** 命名是否清晰? 是否有不必要的复杂性?
5. **Android 最佳实践:** 是否遵循 Android 编码规范?

## 输出格式

结论: PASS / CONDITIONAL PASS / FAIL

如果是 CONDITIONAL PASS 或 FAIL:
- 问题列表 (每项一行，包含文件路径和建议)
- 严重程度: Critical / Important / Minor

如果是 PASS:
- 简要确认 (1-2 句话)
```

2. 处理验收结果:

| 验收结果 | 处理 |
|---------|------|
| PASS | 进入 Phase 7 |
| CONDITIONAL PASS | 记录问题，进入 Phase 7，在报告中标注 |
| FAIL | 回到 Round 1，附带验收报告作为新上下文 (最多 1 次重试) |
| FAIL (重试后仍失败) | 停止 TDD，输出完整诊断报告给用户 |

### 循环终止条件

```
修复循环终止:
  ✅ 所有测试通过 + Round 4 PASS → Phase 7
  ⚠️ Round 4 CONDITIONAL PASS → Phase 7 (报告标注条件性通过)
  ❌ Round 4 FAIL (重试后) → 停止，输出诊断报告
  🛑 用户在任何轮次选择停止 → 保存当前状态
```

### 修复循环记录格式

```
=== 修复循环摘要 ===
Round 1 (机械修复): 3 个问题自动修复
Round 2 (逻辑修复): 1 个根因，用户确认后修复
Round 3: 未触发
Round 4 (独立验收): PASS
总耗时: ~5 分钟
```

---

## Phase 7: 输出报告

生成结构化 TDD 报告，写入文件并展示摘要。

### 步骤 1: 生成报告文件

写入 `docs/reviews/<branch>-tdd-report.md`:

```markdown
# TDD 报告: <branch>

> 生成于 <YYYY-MM-DD HH:mm> | android-tdd
> 功能描述: <需求摘要>

## 摘要

| 指标 | 结果 |
|------|------|
| 测试总数 | N |
| 通过 | N |
| 失败 | N |
| 跳过 | N |
| 总体覆盖率 | XX% |
| 关键路径覆盖率 | XX% |
| 修复循环 | N 轮 |
| 独立验收 | PASS / CONDITIONAL PASS / FAIL |

## 覆盖率详情

| 文件 | 覆盖率 | 关键路径 | 状态 |
|------|--------|---------|------|
| XxxViewModel.kt | XX% | 是 | ✅ / ❌ |
| XxxRepositoryImpl.kt | XX% | 是 | ✅ / ❌ |
| XxxMapper.kt | XX% | 否 | ✅ / ❌ |

## 边界矩阵覆盖

| 类别 | 状态 | 测试数 |
|------|------|--------|
| 生命周期 | ✅ 已覆盖 / ⏭ 跳过 / ❌ 未覆盖 | N |
| 配置变更 | ✅ 已覆盖 / ⏭ 跳过 / ❌ 未覆盖 | N |
| 权限 | ✅ 已覆盖 / ⏭ 跳过 / ❌ 未覆盖 | N |
| 网络 | ✅ 已覆盖 / ⏭ 跳过 / ❌ 未覆盖 | N |
| 存储 | ✅ 已覆盖 / ⏭ 跳过 / ❌ 未覆盖 | N |
| 并发 | ✅ 已覆盖 / ⏭ 跳过 / ❌ 未覆盖 | N |
| 内存 | ✅ 已覆盖 / ⏭ 跳过 / ❌ 未覆盖 | N |
| 兼容性 | ✅ 已覆盖 / ⏭ 跳过 / ❌ 未覆盖 | N |

## 修复循环记录

| 轮次 | 类型 | 修复内容 | 结果 |
|------|------|---------|------|
| Round 1 | 机械修复 | N 个问题 | 通过/失败 |
| Round 2 | 逻辑修复 | N 个根因 | 通过/失败 |
| Round 3 | 架构修复 | N 个建议 | 通过/失败 |
| Round 4 | 独立验收 | PASS/CONDITIONAL/FAIL | 最终结果 |

## 未覆盖路径

<如果有>
- XxxMapper.kt:45 — 空字符串输入的分支未覆盖
- XxxViewModel.kt:78 — 并发重复提交的场景未覆盖
</如果有>

## 建议

<基于验收结果的改进建议>
```

### 步骤 2: 展示报告摘要

```
╔══════════════════════════════════════════════════╗
║                TDD 报告摘要                      ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║  功能: <需求摘要>                                 ║
║                                                  ║
║  测试: N/N passed                                ║
║  覆盖率: XX% (总体) / XX% (关键路径)              ║
║  边界矩阵: 6/8 类别已覆盖                        ║
║  修复循环: 2 轮                                  ║
║  独立验收: PASS ✅                                ║
║                                                  ║
║  完整报告: docs/reviews/<branch>-tdd-report.md   ║
╚══════════════════════════════════════════════════╝
```

### 步骤 3: 更新 worktree-runner 状态

如果被 worktree-runner 调用，TDD 完成后需要更新 tasks.json:

```json
{
  "tdd": {
    "required": true,
    "executed": true,
    "coverage_percent": 87,
    "report_path": "docs/reviews/<branch>-tdd-report.md",
    "boundary_categories_covered": ["Network", "Concurrency", "Storage", "Memory", "Lifecycle", "Config Change"]
  }
}
```

此更新由 worktree-runner 在收到 TDD 完成通知后执行，
不是 android-tdd skill 的职责。

---

## 与其他 Skill 的衔接

| Skill | 关系 | 说明 |
|-------|------|------|
| android-worktree-runner | 上游调用者 | worktree-runner 在执行业务任务前调用本 skill，TDD 通过后继续执行 |
| android-autoplan | 计划来源 | autoplan 的 task 描述中的 `**TDD: required**` 标签触发 TDD |
| android-qa | 下游验证者 | QA 读取 TDD 报告和 tasks.json TDD 字段，避免重复测试 |
| android-investigate | 异常处理 | TDD 修复循环无法解决的问题，建议调用 investigate 深入调查 |
| android-checkpoint | 状态持久化 | TDD 状态通过 tasks.json 持久化，checkpoint 可恢复 |

## 调用流程

```
android-worktree-runner (执行任务)
  │
  ├─ 检测到 **TDD: required** 标签
  │
  ▼
android-tdd (被调用)
  │
  ├─ Phase 0: 环境检测
  ├─ Phase 1: 契约定义 → 用户确认
  ├─ Phase 2: RED (写失败测试) → 验证失败
  ├─ Phase 3: GREEN (最小实现) → 验证通过
  ├─ Phase 4: REFACTOR (安全重构) → 验证仍通过
  ├─ Phase 5: 覆盖率门禁 → 80%/90% 达标
  ├─ Phase 6: 自动修复循环 (如需要) → 3修复 + 1验收
  └─ Phase 7: 输出报告
  │
  ▼
android-worktree-runner (继续执行 Android 验证 + commit)
  │
  ▼
android-qa (后续验证，读取 TDD 结果)
```

## 文件结构

```
项目根目录/
├── docs/
│   └── reviews/
│       ├── <branch>-tdd-report.md          ← 本 skill 产出的 TDD 报告
│       └── <branch>-qa-report.md           ← android-qa 产出 (后续)
└── ...
```

## 异常情况处理

| 场景 | 处理方式 |
|------|----------|
| 不在 git 仓库中 | 报错: "android-tdd 需要 git 仓库" |
| 不是 Android 项目 | 报错: "未检测到 Android 项目" |
| Gradle 不可用 | 报错: "gradlew 未找到或不可执行" |
| JaCoCo 未配置 | 提示配置 JaCoCo，使用测试通过率替代 |
| 无设备/模拟器 | 跳过 Instrumented 测试，记录受影响测试 |
| 修复循环 4 轮后仍失败 | 恢复到 TDD 前状态 (`git stash pop` 恢复 savepoint)，输出完整诊断报告。已通过的测试和实现代码保留在工作区供用户参考 |
| 用户中断修复循环 | 保存当前状态，记录到 tasks.json |
| worktree-runner 未找到 tasks.json | 以独立模式运行，不更新 TDD 状态 |
