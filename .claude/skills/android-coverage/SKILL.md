---
name: android-coverage
description: |
  Android 独立覆盖率 skill。全自动覆盖率闭环：基线测量 -> 差距分析 -> 自动补写测试 -> 验证达标。
  专为夜间无人值守设计，也可快速出报告（report 模式）。
  复用 android-shared 环境检测，独立于 android-tdd/android-qa 的覆盖率逻辑。
  适用场景: 覆盖率提升、夜间自动化测试、覆盖率审计。
voice-triggers:
  - "覆盖率"
  - "coverage"
  - "覆盖率报告"
  - "补测试"
---

# Android Coverage

## 概述

独立的覆盖率闭环 skill，不依赖 TDD 或 QA 流程。自动完成: 基线测量 -> 差距分析 -> 自动补写测试 -> 验证达标。

**核心差异点:**
- **独立闭环:** 不需要 TDD 先行，不依赖 QA 触发。任何阶段都可独立运行。
- **夜间无人值守:** 全自动模式 (auto) 最多 10 轮补写循环，收敛检测自动停止。
- **快速审计:** report 模式仅测量+分析，不动代码，适合日常覆盖率巡检。
- **优先级驱动:** P0 关键路径 (ViewModel/Repository/UseCase) 优先，P1 工具类次之，P2 UI 最后。

**启动时声明:** "我正在使用 android-coverage skill。"

**零外部依赖:** 仅使用 Claude Code 原生工具。不依赖 gstack、browse、Codex、Figma MCP。

## 调用方式

```bash
/android-coverage                  # 全自动闭环（默认）
/android-coverage report           # 只出报告，不动代码
/android-coverage <module>         # 指定模块运行
```

**参数处理:**

| 模式 | 参数 | 行为 |
|------|------|------|
| 全自动闭环 | 无参数 | 执行完整 Phase 0 -> Phase 5，自动补写测试直到达标或收敛 |
| 报告模式 | `report` | 执行 Phase 0 -> Phase 2，跳过 Phase 3 自动补写，执行 Phase 4 验证 + Phase 5 报告 |
| 指定模块 | `<module>` | 仅对指定模块执行完整闭环 (如 `feature:login`) |

**模式选择逻辑:**
1. 第一个参数为 `report` -> 报告模式 (只读)
2. 参数匹配模块名 (`settings.gradle.kts` 中的 include) -> 指定模块模式
3. 无参数 -> 全自动闭环模式

---

## Phase 0: 环境检测

在执行任何覆盖率流程前，自动检测项目环境和 JaCoCo 配置。检测结果贯穿后续所有阶段。

### 前置: 加载历史学习记录

**前置引导:** 若学习记录为空，先运行预加载:
```bash
_R="$(git worktree list | head -1 | awk '{print $1}')"
SHARED_BIN="$_R/.claude/skills/android-shared/bin"
[ ! -d "$SHARED_BIN" ] && SHARED_BIN="$HOME/.claude/skills/android-shared/bin"
bash "$SHARED_BIN/android-learnings-bootstrap" 2>/dev/null || true
```

```bash
_R="$(git worktree list | head -1 | awk '{print $1}')"
SHARED_BIN="$_R/.claude/skills/android-shared/bin"
[ ! -d "$SHARED_BIN" ] && SHARED_BIN="$HOME/.claude/skills/android-shared/bin"
LEARNINGS=$(bash "$SHARED_BIN/android-learnings-search" --type pitfall --limit 5 2>/dev/null || true)
if [ -n "$LEARNINGS" ]; then
  echo "=== 相关学习记录 ==="
  echo "$LEARNINGS"
fi
```

如果找到相关学习记录，在覆盖率分析和测试生成时注意这些已知的坑点（如 JaCoCo 兼容性问题、特定测试框架的覆盖率盲区等）。

### 步骤 1: 确定项目根目录和基准分支

> 参考: [android-shared/detection.md](.claude/skills/android-shared/detection.md) -- 公共环境检测脚本

**环境检测优化:** 优先调用共享脚本获取技术栈信息:
```bash
_R="$(git worktree list | head -1 | awk '{print $1}')"
SHARED_BIN="$_R/.claude/skills/android-shared/bin"
[ ! -d "$SHARED_BIN" ] && SHARED_BIN="$HOME/.claude/skills/android-shared/bin"
ENV_JSON=$(bash "$SHARED_BIN/android-detect-env" 2>/dev/null || true)
echo "$ENV_JSON"
```
脚本不可用时回退到以下内联检测命令。

```bash
# Project root
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -z "$PROJECT_ROOT" ]; then
  echo "ERROR: Not a git repository"
  exit 1
fi

# Confirm Android project
if [ ! -f "$PROJECT_ROOT/build.gradle" ] && [ ! -f "$PROJECT_ROOT/build.gradle.kts" ] && \
   [ ! -f "$PROJECT_ROOT/app/build.gradle" ] && [ ! -f "$PROJECT_ROOT/app/build.gradle.kts" ] && \
   [ ! -f "$PROJECT_ROOT/settings.gradle" ] && [ ! -f "$PROJECT_ROOT/settings.gradle.kts" ]; then
  echo "ERROR: Not an Android project (missing build.gradle / settings.gradle)"
  exit 1
fi

echo "PROJECT_ROOT: $PROJECT_ROOT"

# Base branch
BASE_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
if [ -z "$BASE_BRANCH" ]; then
  BASE_BRANCH=$(git branch -r | grep -E 'origin/(main|master)' | head -1 | sed 's@.*origin/@@' | tr -d ' ')
fi
if [ -z "$BASE_BRANCH" ]; then
  BASE_BRANCH="main"
fi

# Current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "BASE_BRANCH: $BASE_BRANCH"
echo "CURRENT_BRANCH: $CURRENT_BRANCH"

# Gradle wrapper
if [ -f "$PROJECT_ROOT/gradlew" ]; then
  [ ! -x "$PROJECT_ROOT/gradlew" ] && chmod +x "$PROJECT_ROOT/gradlew"
  echo "GRADLE_WRAPPER: available"
else
  echo "GRADLE_WRAPPER: not found"
fi
```

### 步骤 2: 检测 JaCoCo 配置

```bash
# --- JaCoCo plugin ---
echo "=== JaCoCo Configuration ==="
JACOCO_PLUGIN=$(grep -r "jacoco" \
  "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" \
  "$PROJECT_ROOT/build.gradle" "$PROJECT_ROOT/build.gradle.kts" 2>/dev/null | head -5)

if [ -n "$JACOCO_PLUGIN" ]; then
  echo "JACOCO: CONFIGURED"

  # Extract JaCoCo version if configured
  grep -r "jacocoVersion\|jacoco.*version" \
    "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" \
    "$PROJECT_ROOT/build.gradle" "$PROJECT_ROOT/build.gradle.kts" 2>/dev/null | head -3

  # Check for testCoverageEnabled
  grep -r "testCoverageEnabled" \
    "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null | head -3

  # Check for coverage report task configuration
  grep -r "jacocoTestReport\|create.*CoverageReport" \
    "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" \
    "$PROJECT_ROOT/build.gradle" "$PROJECT_ROOT/build.gradle.kts" 2>/dev/null | head -5

  # Check for existing coverage thresholds
  echo "=== Coverage Thresholds ==="
  grep -r "minimumCoverage\|coveredRatio\|branchCoverage\|lineCoverage\|instructionCoverage" \
    "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" \
    "$PROJECT_ROOT/build.gradle" "$PROJECT_ROOT/build.gradle.kts" 2>/dev/null | head -5
else
  echo "JACOCO: NOT_CONFIGURED"
fi

# Check for JaCoCo test reports from previous runs
echo "=== Existing Coverage Reports ==="
find "$PROJECT_ROOT" -path "*/reports/jacoco/*" -type f 2>/dev/null | head -5
find "$PROJECT_ROOT" -name "jacocoTestReport.xml" -o -name "jacocoTestDebugUnitTestReport.xml" 2>/dev/null | head -5
```

### 步骤 3: 检测测试框架

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

# --- Mocking: Mockito vs MockK ---
MOCKK=$(grep -rl "import io.mockk" "$PROJECT_ROOT" --include="*.kt" --include="*.java" 2>/dev/null | head -5)
MOCKITO=$(grep -rl "import org.mockito" "$PROJECT_ROOT" --include="*.kt" --include="*.java" 2>/dev/null | head -5)

if [ -n "$MOCKK" ]; then
  echo "MOCK_FRAMEWORK: MockK"
elif [ -n "$MOCKITO" ]; then
  echo "MOCK_FRAMEWORK: Mockito"
else
  echo "MOCK_FRAMEWORK: NOT_DETECTED"
fi

# --- Robolectric ---
ROBOLECTRIC=$(grep -rl "import org.robolectric" "$PROJECT_ROOT" --include="*.kt" --include="*.java" 2>/dev/null | head -3)
if [ -n "$ROBOLECTRIC" ]; then
  echo "ROBOLECTRIC: DETECTED"
else
  echo "ROBOLECTRIC: NOT_DETECTED"
fi

# --- Espresso ---
ESPRESSO=$(grep -rl "import androidx.test.espresso" "$PROJECT_ROOT" --include="*.kt" --include="*.java" 2>/dev/null | head -3)
if [ -n "$ESPRESSO" ]; then
  echo "ESPRESSO: DETECTED"
else
  echo "ESPRESSO: NOT_DETECTED"
fi
```

### 步骤 4: 检测模块结构

```bash
# --- Modules from settings.gradle.kts ---
SETTINGS_FILE="$PROJECT_ROOT/settings.gradle"
[ -f "$PROJECT_ROOT/settings.gradle.kts" ] && SETTINGS_FILE="$PROJECT_ROOT/settings.gradle.kts"

echo "=== Modules ==="
cat "$SETTINGS_FILE" 2>/dev/null | grep -E "include\s*[\(:]" | sed 's/.*include\s*//;s/[\(,\)]//g;s/:/ /g'

# --- Build variants ---
echo "=== Build Variants ==="
grep -r "buildTypes\|productFlavors" "$PROJECT_ROOT/app" --include="*.gradle*" 2>/dev/null | head -10

# --- Determine test variant (default: Debug) ---
VARIANT="Debug"
grep -r "buildTypes" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null | grep -i "release" | head -1 && VARIANT="Release"
echo "TEST_VARIANT: $VARIANT"
```

如果指定了 `<module>` 参数，验证模块存在:
```bash
if [ -n "$TARGET_MODULE" ]; then
  if ! grep -q "include.*$TARGET_MODULE" "$SETTINGS_FILE" 2>/dev/null; then
    echo "ERROR: Module '$TARGET_MODULE' not found in settings.gradle.kts"
    exit 1
  fi
  echo "TARGET_MODULE: $TARGET_MODULE"
fi
```

### 步骤 5: JaCoCo 自动引导 (按需)

**触发条件:** 步骤 2 检测到 JaCoCo 未配置。

**不触发条件:** JaCoCo 已配置 -> 跳过此步骤，输出 "步骤 5: 跳过 (JaCoCo 已配置)"。

**流程:**

1. 提示 JaCoCo 缺失:
   ```
   检测到 JaCoCo 未配置。覆盖率测量需要 JaCoCo 插件。
   - A) 自动配置 JaCoCo
   - B) 跳过，仅使用测试通过率作为替代指标
   ```

2. 如果用户选择 A，执行以下操作:

   先准备 Variant 变量:
   ```bash
   VARIANT_LOWER=$(echo "$VARIANT" | tr '[:upper:]' '[:lower:]')
   echo "JaCoCo 自动引导使用 Variant: ${VARIANT} (${VARIANT_LOWER})"
   ```

   **在 app/build.gradle.kts 顶层 (plugins 块之后) 添加:**
   ```kotlin
   jacoco { toolVersion = "0.8.11" }
   ```

   **在 android 块中添加:**
   ```kotlin
   buildTypes {
       ${VARIANT_LOWER} {
           testCoverageEnabled = true
           // ... 已有配置
       }
   }
   ```

   **在 android 块之后添加 JaCoCo 任务:**
   ```kotlin
   tasks.register<JacocoReport>("create${VARIANT}UnitTestCoverageReport") {
       dependsOn("test${VARIANT}UnitTest")
       group = "reporting"
       description = "Generate JaCoCo coverage report for ${VARIANT_LOWER} unit tests"

       val classDirectories = fileTree("${buildDir}/tmp/kotlin-classes/${VARIANT_LOWER}") {
           exclude(
               "**/R.class",
               "**/R\$*.class",
               "**/BuildConfig.*",
               "**/Manifest*.*",
               "**/*Test*.*",
               "**/Hilt_*.*",
               "**/*_Factory.*",
               "**/*_MembersInjector.*",
               "**/*Module_*.*"
           )
       }
       val sourceDirectories = files("${projectDir}/src/main/java", "${projectDir}/src/main/kotlin")
       val executionData = files("${buildDir}/jacoco/test${VARIANT}UnitTest.exec")

       reports {
           xml.required.set(true)
           html.required.set(true)
       }
   }
   ```

3. 验证配置:
   ```bash
   ./gradlew tasks --all 2>&1 | grep -i jacoco
   ```

4. 验证通过后，提示: "JaCoCo 配置完成。可以继续覆盖率流程。"

### 输出环境档案

汇总以上所有检测结果，输出格式:

```
=== Coverage 环境档案 ===
项目根目录:   /path/to/project
基准分支:     main
当前分支:     feature/auth
语言:         Kotlin
Gradle:       gradlew available
构建变体:     debug, release

--- 覆盖率工具 ---
JaCoCo:       ✅ 已配置 / ❌ 未配置
覆盖率报告:   create${VARIANT}UnitTestCoverageReport
覆盖率门禁:   80% (行) / 90% (关键路径) / 75% (分支)

--- 测试基础设施 ---
单元测试框架: JUnit4
Mock 框架:    MockK
Robolectric:  DETECTED / NOT_DETECTED
Espresso:     DETECTED / NOT_DETECTED

--- 模块结构 ---
模块列表:     app, feature:login, core:data, core:common
目标模块:     app (全部) / feature:login (指定)
```

---

## Phase 1: 基线测量

运行测试并收集覆盖率数据，建立当前覆盖率基线。

### 步骤 1: 运行测试并生成覆盖率报告

```bash
# 运行测试 + 覆盖率报告
# 注意: JaCoCo 报告任务名取决于 Phase 0 检测结果
./gradlew test${VARIANT}UnitTest create${VARIANT}UnitTestCoverageReport 2>&1
```

如果覆盖率报告任务不存在:
```bash
# 回退: 仅运行测试，手动查找报告
./gradlew test${VARIANT}UnitTest 2>&1
```

### 步骤 2: 定位覆盖率报告

```bash
# 查找 JaCoCo XML 报告
JACOCO_XML=$(find "$PROJECT_ROOT" -path "*/reports/jacoco/*/*.xml" -type f 2>/dev/null | head -1)
JACOCO_HTML=$(find "$PROJECT_ROOT" -path "*/reports/jacoco/*/index.html" -type f 2>/dev/null | head -1)

if [ -f "$JACOCO_XML" ]; then
  echo "JACOCO_XML: $JACOCO_XML"
  echo "JACOCO_HTML: $JACOCO_HTML"
else
  echo "JACOCO_XML: NOT_FOUND"
  echo "NOTE: 尝试在 build/reports/tests/ 中查找测试报告"
  find "$PROJECT_ROOT" -path "*/build/reports/tests/*" -name "index.html" 2>/dev/null | head -3
fi
```

### 步骤 3: 解析覆盖率数据

从 JaCoCo XML 报告解析覆盖率数据，按类和模块分组:

```bash
if [ -f "$JACOCO_XML" ]; then
  echo "=== 覆盖率解析 ==="

  # 提取每个 package/class 的覆盖率
  # LINE 覆盖率
  echo "--- LINE ---"
  grep '<counter type="LINE"' "$JACOCO_XML" | while read line; do
    missed=$(echo "$line" | sed -n 's/.*missed="\([^"]*\)".*/\1/p')
    covered=$(echo "$line" | sed -n 's/.*covered="\([^"]*\)".*/\1/p')
    total=$((missed + covered))
    if [ "$total" -gt 0 ]; then
      pct=$((covered * 100 / total))
      echo "  LINE: ${pct}% (${covered}/${total})"
    fi
  done

  # BRANCH 覆盖率
  echo "--- BRANCH ---"
  grep '<counter type="BRANCH"' "$JACOCO_XML" | while read line; do
    missed=$(echo "$line" | sed -n 's/.*missed="\([^"]*\)".*/\1/p')
    covered=$(echo "$line" | sed -n 's/.*covered="\([^"]*\)".*/\1/p')
    total=$((missed + covered))
    if [ "$total" -gt 0 ]; then
      pct=$((covered * 100 / total))
      echo "  BRANCH: ${pct}% (${covered}/${total})"
    fi
  done

  # METHOD 覆盖率
  echo "--- METHOD ---"
  grep '<counter type="METHOD"' "$JACOCO_XML" | while read line; do
    missed=$(echo "$line" | sed -n 's/.*missed="\([^"]*\)".*/\1/p')
    covered=$(echo "$line" | sed -n 's/.*covered="\([^"]*\)".*/\1/p')
    total=$((missed + covered))
    if [ "$total" -gt 0 ]; then
      pct=$((covered * 100 / total))
      echo "  METHOD: ${pct}% (${covered}/${total})"
    fi
  done
else
  echo "WARNING: JaCoCo XML 报告未找到，无法解析覆盖率数据"
  echo "使用测试通过率作为替代指标"
fi
```

### 步骤 4: 输出三维度仪表盘

```
╔══════════════════════════════════════════════════════════════╗
║                    覆盖率基线仪表盘                         ║
╠══════════════════════════════════════════════════════════════╣
║                                                            ║
║  总体行覆盖率:  ████████████████░░░░░░░  67%              ║
║  分支覆盖率:    ██████████████░░░░░░░░░  54%              ║
║  方法覆盖率:    ███████████████████░░░░  78%              ║
║                                                            ║
║  --- 关键路径 (P0) ---                                     ║
║  ✅ LoginViewModel.kt          92%                         ║
║  ❌ AuthRepository.kt          45%                         ║
║  ❌ GetUserUseCase.kt          30%                         ║
║                                                            ║
║  --- 工具类 (P1) ---                                       ║
║  ❌ TokenMapper.kt             12%                         ║
║  🟡 DateUtils.kt               55%                         ║
║                                                            ║
║  --- UI (P2) ---                                          ║
║  ❌ LoginScreen.kt              0%                         ║
║  ❌ ProfileFragment.kt          0%                         ║
║                                                            ║
║  阈值: 行 80% | 分支 75% | 关键路径 90%                   ║
╚══════════════════════════════════════════════════════════════╝
```

**如果 JaCoCo 未配置:**
```
╔══════════════════════════════════════════════════════════════╗
║                    覆盖率基线仪表盘                         ║
╠══════════════════════════════════════════════════════════════╣
║  ⚠️ JaCoCo 未配置，使用替代指标                              ║
║                                                            ║
║  测试文件数: 15                                            ║
║  测试通过率: 100% (42/42)                                  ║
║                                                            ║
║  建议: 配置 JaCoCo 以获取精确覆盖率数据                     ║
╚══════════════════════════════════════════════════════════════╝
```

---

## Phase 2: 差距分析

基于基线数据，识别覆盖率缺口并生成优先级排序的测试清单。

### 步骤 1: 未覆盖类优先级分类

扫描项目中的所有源码文件，根据覆盖率数据分类:

**优先级定义:**

| 优先级 | 文件匹配模式 | 覆盖率目标 | 说明 |
|--------|-------------|-----------|------|
| P0 | `*ViewModel.kt`, `*Repository*.kt`, `*UseCase.kt` | 90%+ | 关键路径，业务逻辑核心 |
| P1 | `*Mapper.kt`, `*Util*.kt`, `*Extension*.kt`, `*Converter.kt`, data classes | 80%+ | 数据转换和工具方法 |
| P2 | `*Screen.kt`, `*Activity.kt`, `*Fragment.kt`, `*Composable*.kt` | 60%+ | UI 层，通过 Robolectric/Espresso 测 |

**扫描命令:**
```bash
# 列出所有需要测试的源码文件 (排除 R, BuildConfig 等)
echo "=== 待测源码清单 ==="

# P0: 关键路径
echo "--- P0: 关键路径 ---"
find "$PROJECT_ROOT" -path "*/src/main/*" -name "*ViewModel.kt" -not -path "*/build/*" 2>/dev/null
find "$PROJECT_ROOT" -path "*/src/main/*" \( -name "*Repository.kt" -o -name "*RepositoryImpl.kt" \) -not -path "*/build/*" 2>/dev/null
find "$PROJECT_ROOT" -path "*/src/main/*" -name "*UseCase.kt" -not -path "*/build/*" 2>/dev/null

# P1: 工具类
echo "--- P1: 工具类 ---"
find "$PROJECT_ROOT" -path "*/src/main/*" \( -name "*Mapper.kt" -o -name "*Util*.kt" -o -name "*Extension*.kt" -o -name "*Converter.kt" \) -not -path "*/build/*" 2>/dev/null

# P2: UI 层
echo "--- P2: UI 层 ---"
find "$PROJECT_ROOT" -path "*/src/main/*" \( -name "*Screen.kt" -o -name "*Activity.kt" -o -name "*Fragment.kt" -o -name "*Composable*.kt" \) -not -path "*/build/*" 2>/dev/null
```

### 步骤 2: 生成优先级测试清单

结合覆盖率数据，输出排序后的测试清单:

```
=== 覆盖率差距清单 ===

| # | 优先级 | 类名 | 当前覆盖率 | 差距 | 建议测试类型 |
|---|--------|------|-----------|------|-------------|
| 1 | P0 | AuthRepository.kt | 45% | -45% | JVM Unit (MockK) |
| 2 | P0 | GetUserUseCase.kt | 30% | -60% | JVM Unit (MockK) |
| 3 | P1 | TokenMapper.kt | 12% | -68% | JVM Unit |
| 4 | P1 | DateUtils.kt | 55% | -25% | JVM Unit |
| 5 | P0 | LoginViewModel.kt | 92% | +2% | 已达标 |
| 6 | P2 | LoginScreen.kt | 0% | -80% | Robolectric/Espresso |
| 7 | P2 | ProfileFragment.kt | 0% | -60% | Espresso |

未达标: 5 个类
P0 未达标: 2 个
P1 未达标: 2 个
P2 未达标: 2 个
```

### 步骤 3: 确定批次策略

根据覆盖率差距大小决定自动补写的轮次和每轮批量:

| 总差距 (加权平均) | 预估轮次 | 策略 |
|-------------------|---------|------|
| <= 10% | 1-3 轮 | 快速补齐，每轮 5 个类 |
| 10% - 30% | 3-6 轮 | 稳步推进，前 3 轮每轮 5 个，之后每轮 3 个 |
| > 30% | 6-10 轮 | 分阶段，先 P0 再 P1 最后 P2 |

输出批次计划:
```
=== 批次策略 ===
当前总体覆盖率: 67%
目标覆盖率:     80%
差距:           13%

策略: 3-6 轮 (10-30% 差距)
预估: 先补 P0 (2 个类) -> P1 (2 个类) -> P2 (按需)
```

---

## Phase 3: 自动补写测试

核心循环: 逐轮读取未覆盖源码 -> 生成测试 -> 运行验证 -> 更新覆盖率。

**跳过条件:** `report` 模式跳过整个 Phase 3。

### 循环控制

- **最大轮次:** 10 轮
- **收敛检测:** 连续 2 轮总体覆盖率提升 < 0.5% 时自动停止
- **提前终止:** 所有关键路径达标 (P0 >= 90%, 总体 >= 80%) 时自动停止

### 收敛策略

| 轮次范围 | 每轮类数 | 策略说明 |
|---------|---------|---------|
| Round 1-3 | 5 个类 | 大批量，快速提升覆盖率 |
| Round 4-6 | 3 个类 | 中批量，聚焦难测类 |
| Round 7-10 | 1 个类 | 精细化，逐个攻坚 |

### 每轮子步骤

**A) 选取 Top-K:** 从差距清单中选取当前覆盖率最低的 K 个未达标类。

**B) 读取源码:** 对每个目标类，读取完整源码，分析:
- 类的职责和依赖
- 公开方法和它们的参数/返回类型
- 需要的 mock 依赖
- 未覆盖的分支和边界条件

**C) 生成测试:** 根据类类型生成对应测试。

**测试生成规则 (按类类型):**

| 类类型 | 测试策略 | Mock 要求 | 覆盖重点 |
|--------|---------|----------|---------|
| ViewModel | Mock Repository，测试状态转换 | mockk() + coEvery | loading -> success/error, intent 处理, 边界输入 |
| Repository | Mock 数据源 (API/DB)，测试数据流 | mockk() + coEvery | 成功/失败路径, 空数据, 超时 |
| UseCase | Mock Repository，测试业务逻辑 | mockk() + coEvery | 参数验证, 业务规则, 异常处理 |
| Mapper | 纯函数，无需 mock | 无 | 正常映射, null 输入, 边界值 |
| Data class | 验证属性, equals/hashCode | 无 | 默认值, copy, toString |
| Extension | 直接调用扩展函数 | 视依赖而定 | 正常/边界/异常输入 |

**D) 运行测试:**
```bash
./gradlew test${VARIANT}UnitTest 2>&1
```

**E) 运行覆盖率:**
```bash
./gradlew test${VARIANT}UnitTest create${VARIANT}UnitTestCoverageReport 2>&1
```

**F) 更新清单:** 重新解析覆盖率数据，更新差距清单，标记已达标类。

**G) 输出本轮摘要。**

### 测试失败处理

每个生成的测试如果运行失败，执行 3 轮修复:

| 修复轮次 | 策略 | 说明 |
|---------|------|------|
| Round 1 | 自动修复 | 修复编译错误、import 缺失、类型不匹配 |
| Round 2 | 重新分析 | 重新读取源码，重新生成测试 (换一种 mock 策略) |
| Round 3 | 标记跳过 | 记录该类为 "测试生成失败"，跳过并继续下一个类 |

### 每轮输出格式

```
=== Phase 3: Round 3/10 ===

本轮目标: 3 个类 (P0: 1, P1: 2)

  [C1] AuthRepository.kt (P0, 当前 45%)
    生成: 8 个测试
    运行: ✅ 8/8 passed
    覆盖率: 45% -> 88% (+43%) ✅ 达标

  [C2] TokenMapper.kt (P1, 当前 12%)
    生成: 5 个测试
    运行: ✅ 5/5 passed
    覆盖率: 12% -> 85% (+73%) ✅ 达标

  [C3] DateUtils.kt (P1, 当前 55%)
    生成: 4 个测试
    运行: ❌ 2/4 failed
    修复 Round 1: 修复 import -> ✅ 4/4 passed
    覆盖率: 55% -> 82% (+27%) ✅ 达标

本轮总结:
  新增测试: 17 个
  覆盖率变化: 67% -> 76% (+9%)
  累计提升: +9% (3 轮)
  收敛检测: 未触发 (提升 >= 0.5%)

进度: ████████████████░░░░░░░░  76% / 80%
```

### 循环终止输出

```
=== Phase 3: 循环结束 ===

终止原因: 所有关键路径达标 / 收敛检测触发 / 达到最大轮次

总轮次: 5/10
新增测试: 42 个
覆盖率变化: 67% -> 84% (+17%)

跳过类 (测试生成失败):
  - ProfileFragment.kt: 3 轮修复后仍失败 (原因: Espresso 环境依赖)

未达标项:
  - LoginScreen.kt: 15% (P2, 目标 60%) -- UI 层，建议手动编写
```

---

## Phase 4: 最终验证

确保新增测试不破坏既有功能，项目可正常编译。

### 步骤 1: 全量回归测试

```bash
# 运行所有模块的单元测试
./gradlew test${VARIANT}UnitTest 2>&1
```

**通过条件:** 所有既有测试 + 新增测试全部通过。

**如果测试失败:**
1. 分析失败原因
2. 如果是既有测试被破坏 (回归失败) -> 删除导致回归的新增测试，标记对应类为 "回归冲突"
3. 如果是新增测试失败 -> 尝试修复，3 轮后仍失败则删除

### 步骤 2: 编译验证

```bash
./gradlew assembleDebug 2>&1
```

**通过条件:** 编译成功，无错误。

### 步骤 3: 最终覆盖率快照

```bash
./gradlew test${VARIANT}UnitTest create${VARIANT}UnitTestCoverageReport 2>&1
```

重新解析覆盖率数据，作为最终结果记录到报告中。

---

## Phase 5: 结果汇报

生成覆盖率报告并提交新增测试。

### 步骤 1: 写入报告文件

写入 `docs/reviews/<branch>-coverage-report.md`:

```markdown
# 覆盖率报告: <branch>

> 生成于 <YYYY-MM-DD HH:mm> | android-coverage
> 模式: 全自动闭环 / 报告模式
> 目标模块: app (全部) / feature:login (指定)

## 摘要

| 指标 | 基线 | 最终 | 变化 | 阈值 | 状态 |
|------|------|------|------|------|------|
| 总体行覆盖率 | 67% | 84% | +17% | 80% | ✅ |
| 分支覆盖率 | 54% | 71% | +17% | 75% | ❌ |
| 方法覆盖率 | 78% | 89% | +11% | - | - |
| 关键路径覆盖率 | 52% | 91% | +39% | 90% | ✅ |

## 覆盖率仪表盘

### Before
```
总体行覆盖率:  ████████████████░░░░░░░  67%
分支覆盖率:    ██████████████░░░░░░░░░  54%
```

### After
```
总体行覆盖率:  ██████████████████████░  84%
分支覆盖率:    ██████████████████░░░░░  71%
```

## 新增测试清单

| 文件 | 新增测试数 | 覆盖率变化 | 状态 |
|------|-----------|-----------|------|
| AuthRepositoryTest.kt | 8 | 45% -> 88% | ✅ |
| TokenMapperTest.kt | 5 | 12% -> 85% | ✅ |
| DateUtilsTest.kt | 4 | 55% -> 82% | ✅ |

## 未达标项

| 类名 | 当前覆盖率 | 目标 | 优先级 | 说明 |
|------|-----------|------|--------|------|
| LoginScreen.kt | 15% | 60% | P2 | UI 层，建议手动编写 Compose 测试 |
| ProfileFragment.kt | 0% | 60% | P2 | 测试生成失败，需要 Espresso 环境 |

## Phase 3 循环记录

| 轮次 | 新增测试 | 覆盖率 | 提升 | 状态 |
|------|---------|--------|------|------|
| Round 1 | 15 | 67% -> 73% | +6% | 正常 |
| Round 2 | 12 | 73% -> 78% | +5% | 正常 |
| Round 3 | 10 | 78% -> 82% | +4% | 正常 |
| Round 4 | 3 | 82% -> 83% | +1% | 正常 |
| Round 5 | 2 | 83% -> 84% | +1% | 收敛停止 |

总新增测试: 42 个
总覆盖率提升: +17%
```

### 步骤 2: 终端摘要

```
╔══════════════════════════════════════════════════════════════╗
║                  覆盖率提升报告摘要                           ║
╠══════════════════════════════════════════════════════════════╣
║                                                            ║
║  分支: feature/auth                                        ║
║  模式: 全自动闭环                                          ║
║                                                            ║
║  覆盖率:  67% -> 84%  (+17%)                               ║
║  关键路径: 52% -> 91%  (+39%)                               ║
║  分支率:  54% -> 71%  (+17%)                               ║
║                                                            ║
║  新增测试: 42 个 (5 轮)                                    ║
║  回归测试: ✅ 全部通过                                     ║
║  编译验证: ✅ assembleDebug 成功                            ║
║                                                            ║
║  达标: 总体行 ✅ | 关键路径 ✅ | 分支 ❌                   ║
║                                                            ║
║  完整报告: docs/reviews/feature-auth-coverage-report.md     ║
╚══════════════════════════════════════════════════════════════╝
```

### 步骤 3: 提交新增测试文件 (仅 auto 模式)

**report 模式跳过此步骤。**

```bash
# 收集新增的测试文件
NEW_TEST_FILES=$(git diff --name-only --diff-filter=A -- "*.kt" "*.java" 2>/dev/null | grep -E "src/test/|src/androidTest/|src/unitTest/|src/.*/test/")

if [ -n "$NEW_TEST_FILES" ]; then
  git add $NEW_TEST_FILES
  git commit -m "$(cat <<'EOF'
test: coverage auto-generated tests (+N tests, +X% coverage)

Generated by android-coverage skill.
Coverage: XX% -> YY% (+ZZ%)

New test files:
- path/to/Test1.kt (N tests)
- path/to/Test2.kt (N tests)
EOF
)"
  echo "Commit: $(git rev-parse --short HEAD)"
fi
```

---

## 与其他 Skill 的衔接

| Skill | 关系 | 说明 |
|-------|------|------|
| android-tdd | 互补 | TDD 聚焦"测试先行"方法论，本 skill 聚焦"覆盖率闭环"。TDD 中 Phase 5 的覆盖率门禁可调用本 skill 进行深度补写 |
| android-qa | 上下游 | QA 发现覆盖率不达标时可调用本 skill 补测试。本 skill 完成后 QA 可复用覆盖率数据 |
| android-worktree-runner | 上游 | worktree-runner 在任务执行完成后可自动调用本 skill 进行覆盖率提升 |
| android-benchmark | 参考 | 覆盖率提升后可运行 benchmark 验证性能未退化 |

---

## Capture Learnings

覆盖率流程完成后，将过程中的发现记录到学习系统以供未来 session 参考。

**记录时机:**

1. **发现覆盖率配置问题** -- 如 JaCoCo 版本兼容性、排除规则不当、多模块覆盖率合并失败，使用 android-learnings-log 记录:
   ```bash
   _R="$(git worktree list | head -1 | awk '{print $1}')"
   SHARED_BIN="$_R/.claude/skills/android-shared/bin"
   [ ! -d "$SHARED_BIN" ] && SHARED_BIN="$HOME/.claude/skills/android-shared/bin"
   bash "$SHARED_BIN/android-learnings-log" '{"skill":"coverage","type":"pitfall","key":"<配置问题简述>","insight":"<问题描述和解决方案>","confidence":8,"source":"observed","files":["<配置文件>"]}'
   ```

2. **发现测试生成失败模式** -- 如特定类类型难以自动生成测试、mock 策略失效，记录为 pitfall:
   ```bash
   _R="$(git worktree list | head -1 | awk '{print $1}')"
   SHARED_BIN="$_R/.claude/skills/android-shared/bin"
   [ ! -d "$SHARED_BIN" ] && SHARED_BIN="$HOME/.claude/skills/android-shared/bin"
   bash "$SHARED_BIN/android-learnings-log" '{"skill":"coverage","type":"pitfall","key":"<失败模式简述>","insight":"<失败原因和绕过方案>","confidence":7,"source":"observed","files":["<相关文件>"]}'
   ```

3. **发现高效测试策略** -- 如某个 mock 模式特别高效、某个覆盖率提升技巧特别有效，记录为 technique:
   ```bash
   _R="$(git worktree list | head -1 | awk '{print $1}')"
   SHARED_BIN="$_R/.claude/skills/android-shared/bin"
   [ ! -d "$SHARED_BIN" ] && SHARED_BIN="$HOME/.claude/skills/android-shared/bin"
   bash "$SHARED_BIN/android-learnings-log" '{"skill":"coverage","type":"technique","key":"<策略名>","insight":"<策略描述>","confidence":7,"source":"inferred","files":[]}'
   ```

**不记录:**
- 常规的测试生成过程
- 与历史记录完全重复的发现

---

## 文件结构

```
目标 Android 项目/
├── app/
│   ├── build.gradle.kts                  ← JaCoCo 配置 (按需添加)
│   ├── src/
│   │   ├── main/
│   │   │   ├── java/com/example/
│   │   │   │   ├── *ViewModel.kt         ← P0 关键路径
│   │   │   │   ├── *Repository.kt        ← P0 关键路径
│   │   │   │   ├── *UseCase.kt           ← P0 关键路径
│   │   │   │   ├── *Mapper.kt            ← P1 工具类
│   │   │   │   ├── *Utils.kt             ← P1 工具类
│   │   │   │   └── *Screen.kt            ← P2 UI 层
│   │   │   └── ...
│   │   └── test/
│   │       └── java/com/example/
│   │           ├── *ViewModelTest.kt      ← 自动生成
│   │           ├── *RepositoryTest.kt     ← 自动生成
│   │           ├── *UseCaseTest.kt        ← 自动生成
│   │           ├── *MapperTest.kt         ← 自动生成
│   │           └── *UtilsTest.kt          ← 自动生成
│   └── build/
│       └── reports/
│           └── jacoco/
│               ├── *.xml                 ← JaCoCo 覆盖率 XML
│               └── html/                 ← JaCoCo 覆盖率 HTML
├── docs/
│   └── reviews/
│       └── <branch>-coverage-report.md    ← 本 skill 产出的覆盖率报告
└── settings.gradle.kts                    ← 模块定义
```

---

## 异常情况处理

| 场景 | 处理方式 |
|------|----------|
| JaCoCo 未配置 | Phase 0 步骤 5 提供自动配置，用户拒绝则使用测试通过率替代 |
| 覆盖率 0% | 检查 JaCoCo exec 文件是否生成，检查排除规则是否过度排除 |
| 生成的测试编译失败 | 3 轮自动修复: import 修复 -> 重新分析 -> 标记跳过 |
| 生成的测试运行失败 | 3 轮自动修复: 机械修复 -> 换策略重写 -> 标记跳过 |
| 跨模块依赖 mock 失败 | 记录为 "跨模块依赖"，跳过并建议手动编写 |
| Gradle sync 失败 | 报错: "Gradle sync 失败"，建议检查网络和依赖配置 |
| 回归测试失败 (既有测试被破坏) | 删除导致回归的新增测试，标记对应类为 "回归冲突" |
| 不在 git 仓库中 | 报错: "android-coverage 需要 git 仓库" |
| 不是 Android 项目 | 报错: "未检测到 Android 项目" |
| Gradle 不可用 | 报错: "gradlew 未找到或不可执行" |
| 收敛后仍未达标 | 输出未达标清单和建议，不强制继续 |
| Phase 3 中 Gradle 构建超时 | 终止当前轮次，提交已完成的结果 |
