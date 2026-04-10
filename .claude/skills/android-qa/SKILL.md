---
name: android-qa
description: |
  Android QA 测试 skill。在 worktree-runner plan 执行完毕后，
  对已实现的功能进行功能级验证。包括静态分析、日志检查、
  构建验证、以及基于 adb 的设备/模拟器测试。
  产出 bug 报告和修复建议。
  适用场景: 功能完成后验证、回归测试、上线前 QA。
voice-triggers:
  - "QA 测试"
  - "功能验证"
  - "测试一下"
---

# Android QA

## 概述

对当前分支或指定分支的变更进行分层 QA 测试，产出结构化 bug 报告。
静态分析 + 构建/单元测试 + 设备测试三层覆盖，自动修复简单问题。

**启动时声明:** "我正在使用 android-qa skill。"

**零外部依赖:** 仅使用 Claude Code 原生工具 + adb (如果可用)。
不依赖 gstack、browse、Codex、Figma MCP。

## 调用方式

```bash
/android-qa                  # 对当前分支的变更进行 QA
/android-qa <branch>         # 对指定分支 QA (与 main 或基准分支对比)
/android-qa smoke            # 仅冒烟测试 (快速验证核心功能)
/android-qa regression       # 回归测试 (验证已有功能未破坏)
```

**参数处理:**
- 无参数: 对当前分支进行完整 QA
- `<branch>`: 切换到指定分支后进行完整 QA (对比基准分支)
- `smoke`: 仅执行 Layer 2 (构建 + 单元测试) + Layer 1 的关键检查
- `regression`: 扩大测试范围，包含主分支已有功能的回归验证

---

## Phase 0: 环境检测

### 前置: 加载历史学习记录

**前置引导:** 若学习记录为空，先运行预加载:
```bash
bash .claude/skills/android-shared/bin/android-learnings-bootstrap 2>/dev/null || true
```

```bash
# 加载与 QA 相关的历史学习记录
LEARNINGS=$(bash .claude/skills/android-shared/bin/android-learnings-search --type pitfall --limit 5 2>/dev/null || true)
if [ -n "$LEARNINGS" ]; then
  echo "=== 相关学习记录 ==="
  echo "$LEARNINGS"
fi
```

如果找到相关学习记录，在 QA 测试过程中重点关注这些已知的 bug 模式。

### 步骤 1: 确定项目根目录和基准分支

> 参考: [android-shared/detection.md](.claude/skills/android-shared/detection.md) — 公共环境检测脚本

**环境检测优化:** 优先调用共享脚本获取技术栈信息:
```bash
ENV_JSON=$(bash .claude/skills/android-shared/bin/android-detect-env 2>/dev/null || true)
echo "$ENV_JSON"
```
脚本不可用时回退到以下内联检测命令。

```bash
# 项目根目录
PROJECT_ROOT=$(git rev-parse --show-toplevel)

# 确定基准分支 (main 或 master)
BASE_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
if [ -z "$BASE_BRANCH" ]; then
  BASE_BRANCH=$(git branch -r | grep -E 'origin/(main|master)' | head -1 | sed 's@.*origin/@@' | tr -d ' ')
fi
if [ -z "$BASE_BRANCH" ]; then
  BASE_BRANCH="main"
fi

# 当前分支
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
```

如果指定了 `<branch>` 参数:
- 切换到该分支: `git checkout <branch>`
- 更新 `CURRENT_BRANCH` 变量

### 步骤 2: 检测项目技术栈

```bash
# 确认是 Android 项目
if [ ! -f "build.gradle" ] && [ ! -f "build.gradle.kts" ] && \
   [ ! -f "app/build.gradle" ] && [ ! -f "app/build.gradle.kts" ]; then
  echo "NOT_ANDROID"
  exit 1
fi

# 构建系统
ls gradlew 2>/dev/null && echo "GRADLE_WRAPPER" || echo "NO_GRADLE_WRAPPER"
ls gradle 2>/dev/null && echo "GRADLE_DIR"

# 列出所有模块
cat "$PROJECT_ROOT/settings.gradle" "$PROJECT_ROOT/settings.gradle.kts" 2>/dev/null | grep "include"

# UI 框架
grep -rl "@Composable" "$PROJECT_ROOT" --include="*.kt" 2>/dev/null | head -3
find "$PROJECT_ROOT" -path "*/res/layout/*.xml" 2>/dev/null | head -3

# 语言 (Kotlin / Java / 混用)
grep -rl "package " "$PROJECT_ROOT/app/src/main" --include="*.kt" 2>/dev/null | head -1
grep -rl "package " "$PROJECT_ROOT/app/src/main" --include="*.java" 2>/dev/null | head -1

# 构建变体
grep -r "buildTypes\|productFlavors" "$PROJECT_ROOT/app" --include="*.gradle*" 2>/dev/null | head -5
```

产出环境摘要:
```
=== 环境摘要 ===
项目根目录:   /path/to/project
基准分支:     main
当前分支:     plan/auth-login-flow
Gradle:       gradlew available
模块列表:     app, feature:login, core:ui, core:common
UI 框架:      Compose + XML 混用
语言:         Kotlin
构建变体:     debug, release
```

### 步骤 3: 检测可用设备/模拟器

```bash
# 检测 adb 是否可用
which adb 2>/dev/null && echo "ADB_AVAILABLE" || echo "ADB_NOT_FOUND"

# 列出已连接设备
adb devices 2>/dev/null | grep -v "List of devices" | grep -v "^$"
```

设备检测结果:
- 有设备 → 记录设备序列号和型号，Layer 3 可执行
- 无设备但 adb 可用 → 记录 "无已连接设备"，Layer 3 跳过
- adb 不可用 → 记录 "adb 未安装"，Layer 3 跳过

### 步骤 4: 检测 Gradle 可用性

```bash
# 检查 gradlew 权限
if [ -f "gradlew" ]; then
  if [ ! -x "gradlew" ]; then
    chmod +x gradlew
  fi
  ./gradlew --version 2>&1 | head -3
  echo "GRADLE_READY"
else
  echo "GRADLE_NOT_FOUND"
fi
```

如果 Gradle 不可用: 中断执行，提示用户检查项目配置。

### 步骤 5: 检测 TDD 执行状态

```bash
# 定位 tasks.json
MAIN_WORKTREE=$(git worktree list 2>/dev/null | head -1 | awk '{print $1}')
TASKS_FILE="$MAIN_WORKTREE/.claude/android-worktree-runner/tasks.json"

if [ -f "$TASKS_FILE" ]; then
  echo "TASKS_JSON_FOUND: $TASKS_FILE"
else
  echo "NO_TASKS_JSON"
fi
```

**TDD 状态分析:**

读取 tasks.json，统计 TDD 执行情况:

1. 遍历当前 plan 的所有任务
2. 统计 tdd.executed = true 的任务数
3. 统计 tdd.skipped = true 的任务数 (特别是业务任务)
4. 计算 tdd.coverage_percent 的平均值
5. 收集 tdd.boundary_categories_covered
6. 读取 tdd.report_path

**产出 TDD 状态摘要:**

```
=== TDD 状态 ===
状态: 已检测 / 未检测
TDD 已执行: N/M 任务
TDD 跳过: N 任务
TDD 覆盖率: 平均 XX% (范围: XX%-XX%)
TDD 报告: <path> 或 "无"
```

**未检测到 TDD 记录时:**
```
=== TDD 状态 ===
未检测到 TDD 执行记录 — QA 将执行完整验证 (含覆盖率门禁)
```

**TDD 被跳过的业务任务警告:**
```
⚠️ 检测到 N 个业务任务跳过了 TDD:
  - Task 3: LoginViewModel (原因: user_override)
  - Task 5: UserProfileScreen (原因: user_override)

QA 将对这些任务加强验证:
  - 强制执行 Layer 2.3 (单元测试)
  - 覆盖率阈值提升至 90% (而非默认 80%)
  - 执行完整的边界矩阵检查
```

根据检测结果设置以下变量供后续阶段使用:
- `TDD_STATUS`: "detected" / "not_detected"
- `TDD_ALL_COVERED`: "true" / "false" (所有业务任务 TDD 已执行且覆盖率 >= 80%)
- `TDD_AVG_COVERAGE`: 平均覆盖率数字
- `TDD_REPORT_PATH`: 报告文件路径
- `TDD_SKIPPED_BUSINESS_TASKS`: 被跳过的业务任务数
- `COVERAGE_THRESHOLD`: 80 (默认) 或 90 (有 TDD 被跳过的业务任务时)

---

## Phase 1: 测试范围确定

### 步骤 1: 分析变更范围

```bash
# 获取当前分支相对于基准分支的变更文件列表
CHANGED_FILES=$(git diff --name-only "$BASE_BRANCH"...HEAD 2>/dev/null)

# 获取变更统计
git diff --stat "$BASE_BRANCH"...HEAD 2>/dev/null

# 仅 Kotlin/Java 源码变更
CODE_CHANGES=$(echo "$CHANGED_FILES" | grep -E '\.(kt|java)$')

# 资源文件变更
RESOURCE_CHANGES=$(echo "$CHANGED_FILES" | grep -E '\.(xml|png|webp|svg|jpg)$')

# Gradle 配置变更
GRADLE_CHANGES=$(echo "$CHANGED_FILES" | grep -E 'build\.gradle|settings\.gradle|gradle\.properties|libs\.versions\.toml')

# Manifest 变更
MANIFEST_CHANGES=$(echo "$CHANGED_FILES" | grep -E 'AndroidManifest\.xml')
```

### 步骤 2: 确定受影响模块

```bash
# 从变更文件路径提取受影响的模块
for file in $CHANGED_FILES; do
  # 提取模块名 (第一级目录)
  module=$(echo "$file" | cut -d'/' -f1)
  echo "$module"
done | sort -u
```

### 步骤 3: 查找关联的 Plan 文件

```bash
# 查找可能的 plan 文件
PLAN_SLUG=$(echo "$CURRENT_BRANCH" | sed 's/plan\///' | sed 's/-/\-/g')
find "$PROJECT_ROOT/docs/plans" -name "*.md" 2>/dev/null | head -5
find "$PROJECT_ROOT/.claude" -name "tasks.json" 2>/dev/null | head -5
```

如果找到关联的 plan 文件或 `tasks.json`:
- 读取 plan 中的功能描述和预期行为
- 用作测试用例的参考依据

### 步骤 4: 生成测试范围报告

```
=== 测试范围 ===
模式:         完整 QA / 冒烟测试 / 回归测试
分支:         plan/auth-login-flow
基准:         main
变更文件数:   23
  源码:       15 (.kt)
  资源:       5 (.xml, .png)
  Gradle:     2 (.gradle.kts, .toml)
  Manifest:   1
受影响模块:   app, feature:login, core:common
关联 Plan:    docs/plans/2026-04-10-auth.md
```

**smoke 模式限制:** 仅关注核心功能路径，跳过边缘场景和回归测试。
**regression 模式扩展:** 额外包含基准分支上已有功能的关键路径验证。

---

## Phase 2: 分层测试

使用 Agent 工具派发 subagent 执行各层测试。

### Subagent 并发控制

- Layer 1 (静态分析) 和 Layer 2 (构建+测试) 可并行执行
- Layer 3 (设备测试) 依赖 Layer 2 的构建产出 (APK)，串行执行
- 最多同时运行 2 个 subagent

### Layer 1: 静态分析 (无需设备)

**目标:** 在不编译的情况下发现代码层面的问题。

**检查项目:**

#### 1.1 代码模式检查

扫描所有变更的 `.kt` / `.java` 文件:

| 检查项 | 检测方式 | 严重程度 |
|--------|----------|----------|
| 空指针风险 | `!!` 操作符、未做 null check 的可空类型引用 | 高 |
| 未处理的异常 | `catch` 块为空、`TODO` 标记、未处理的 `Result` | 中 |
| 硬编码字符串 | 字符串字面量 (非 `@StringRes` 注解的) 在 UI 代码中 | 中 |
| 硬编码尺寸 | 直接使用 `dp` 数值而非 `@DimenRes` | 低 |
| 内存泄漏风险 | 匿名内部类持有 Activity/View 引用、未取消的协程 | 高 |
| 线程问题 | 主线程 IO 操作、非主线程 UI 更新 | 高 |
| 未使用的导入 | `import` 语句未在代码中使用 | 低 |

```bash
# 空指针风险: !! 操作符
grep -n '!!' $CODE_CHANGES 2>/dev/null

# 空的 catch 块
grep -n 'catch.*{ *}' $CODE_CHANGES 2>/dev/null
grep -nA2 'catch' $CODE_CHANGES 2>/dev/null | grep '{ *}$'

# TODO/FIXME 标记
grep -rn 'TODO\|FIXME\|HACK\|XXX' $CODE_CHANGES 2>/dev/null

# 硬编码字符串 (UI 层中)
grep -n '"[^"]*"' $CODE_CHANGES 2>/dev/null | grep -v '@StringRes\|R\.string\|//\|Log\.\|TAG\|"$\|\.class'

# 主线程网络调用
grep -n 'Dispatchers\.Main' $CODE_CHANGES 2>/dev/null | grep -i 'http\|retrofit\|okhttp\|request\|api'
```

#### 1.2 资源完整性检查

```bash
# 提取代码中引用的所有资源 ID
grep -ohP 'R\.\w+\.\w+' $CODE_CHANGES 2>/dev/null | sort -u

# 提取 XML 中引用的所有资源
grep -ohP '@\w+/[\w.]+' $RESOURCE_CHANGES 2>/dev/null | sort -u

# 检查 drawable 引用是否存在
for ref in $(grep -ohP 'R\.drawable\.\w+' $CODE_CHANGES 2>/dev/null | sed 's/R\.drawable\.//'); do
  find "$PROJECT_ROOT" -path "*/res/drawable*/$ref.*" 2>/dev/null | head -1 || echo "MISSING: drawable/$ref"
done

# 检查 string 引用是否存在
for ref in $(grep -ohP 'R\.string\.\w+' $CODE_CHANGES 2>/dev/null | sed 's/R\.string\.//'); do
  grep -rq "name=\"$ref\"" "$PROJECT_ROOT"/app/src/main/res/values*/strings.xml 2>/dev/null || echo "MISSING: string/$ref"
done

# 检查 dimen 引用是否存在
for ref in $(grep -ohP 'R\.dimen\.\w+' $CODE_CHANGES 2>/dev/null | sed 's/R\.dimen\.//'); do
  grep -rq "name=\"$ref\"" "$PROJECT_ROOT"/app/src/main/res/values*/dimens.xml 2>/dev/null || echo "MISSING: dimen/$ref"
done

# 检查 color 引用是否存在
for ref in $(grep -ohP 'R\.color\.\w+' $CODE_CHANGES 2>/dev/null | sed 's/R\.color\.//'); do
  grep -rq "name=\"$ref\"" "$PROJECT_ROOT"/app/src/main/res/values*/colors.xml 2>/dev/null || echo "MISSING: color/$ref"
done
```

#### 1.3 Manifest 检查

```bash
# 提取变更代码中定义的 Activity 类
grep -rn 'class.*Activity' $CODE_CHANGES 2>/dev/null | grep -v test

# 检查这些 Activity 是否在 AndroidManifest.xml 中声明
for activity_class in $(grep -ohP 'class (\w+\.)*\w+Activity' $CODE_CHANGES 2>/dev/null | sed 's/class //'); do
  # 提取简单类名或全限定名
  simple_name=$(echo "$activity_class" | awk -F'.' '{print $NF}')
  grep -rq "$simple_name\|$activity_class" "$PROJECT_ROOT/app/src/main/AndroidManifest.xml" 2>/dev/null \
    || echo "NOT_DECLARED: $activity_class"
done

# 提取 Service / Receiver / Provider
grep -rn 'class.*Service\b\|class.*Receiver\b\|class.*Provider\b' $CODE_CHANGES 2>/dev/null | grep -v test

# 检查新增的权限是否合理
git diff "$BASE_BRANCH"...HEAD -- "**/AndroidManifest.xml" 2>/dev/null | grep 'uses-permission'
```

#### 1.4 ProGuard / R8 检查

```bash
# 检查是否启用了 minification
grep -rn 'minifyEnabled true\|isMinifyEnabled = true' "$PROJECT_ROOT/app" --include="*.gradle*" 2>/dev/null

# 如果启用了 minification，检查新增类是否有 keep 规则
if [ $? -eq 0 ]; then
  PROGUARD_DIR=$(find "$PROJECT_ROOT/app" -path "*/proguard*" -type d 2>/dev/null | head -1)
  echo "ProGuard 目录: $PROGUARD_DIR"
  # 列出 ProGuard 规则文件
  find "$PROGUARD_DIR" -name "*.pro" -o -name "*.rules" 2>/dev/null
fi
```

**Layer 1 输出格式:**

```
=== Layer 1: 静态分析 ===

问题总数: N

🔴 阻塞 (N)
  [L1-001] 空指针风险
    文件: app/src/main/java/com/example/login/LoginViewModel.kt:45
    描述: 对 user!!.email 使用了非空断言
    建议: 使用安全调用 user?.email ?: return

🟡 可用但有问题 (N)
  [L1-002] 硬编码字符串
    文件: app/src/main/java/com/example/login/LoginFragment.kt:32
    描述: "登录" 应使用字符串资源
    建议: 替换为 getString(R.string.login)

🟢 通过 (N 项检查)
  Manifest 声明: 3/3 Activity 已声明
  资源引用: 所有 drawable/string/dimen 引用均存在
  ProGuard: 未启用或规则已覆盖
```

---

### Layer 2: 构建与单元测试 (无需设备)

**目标:** 确认代码可编译、lint 无严重问题、单元测试通过。

**执行顺序:** 构建 → Lint → 单元测试 (严格串行，前一步失败不执行后一步)

#### 2.1 Gradle 构建

```bash
echo "=== Gradle Build ==="
./gradlew assembleDebug 2>&1
BUILD_EXIT=$?
```

**构建成功:** 继续 2.2
**构建失败:**
- 提取错误信息 (最后 30 行)
- 分析错误类型 (编译错误、依赖缺失、版本冲突)
- 记录为 🔴 阻塞问题
- 不继续后续测试

#### 2.2 Lint 检查

```bash
echo "=== Lint 检查 ==="
./gradlew lintDebug 2>&1
LINT_EXIT=$?
```

**解析 lint 报告:**
```bash
# Lint HTML 报告路径
LINT_REPORT=$(find "$PROJECT_ROOT/app/build/reports/lint-results-debug.html" 2>/dev/null | head -1)

# 如果 HTML 报告存在，读取关键问题
# Lint XML 报告
LINT_XML=$(find "$PROJECT_ROOT/app/build/reports/lint-results-debug.xml" 2>/dev/null | head -1)

# 提取严重问题 (Error 和 Warning)
if [ -f "$LINT_XML" ]; then
  grep -o 'severity="[^"]*"' "$LINT_XML" | sort | uniq -c
  grep 'severity="Error"' "$LINT_XML" -A5 2>/dev/null | head -50
  grep 'severity="Warning"' "$LINT_XML" -A5 2>/dev/null | head -50
fi
```

**Lint 问题分类:**

| Lint 级别 | 处理方式 |
|-----------|----------|
| Error (Fatal) | 🔴 阻塞，必须修复 |
| Error | 🟡 应修复，不阻塞测试 |
| Warning | 🟢 记录，建议后续处理 |
| Information | 忽略 |

#### 2.3 单元测试 (条件执行)

**根据 TDD 状态决定是否执行。**

```bash
if [ "$TDD_ALL_COVERED" = "true" ]; then
  echo "=== 单元测试 ==="
  echo "跳过: TDD 已执行且覆盖率达标 (平均 ${TDD_AVG_COVERAGE}%)"
  echo "来源: ${TDD_REPORT_PATH}"
  TEST_EXIT=0
elif [ "$TDD_STATUS" = "detected" ]; then
  echo "=== 单元测试 ==="
  echo "执行: TDD 已执行但部分任务覆盖率 < 80%，补充验证"
  ./gradlew testDebugUnitTest 2>&1
  TEST_EXIT=$?
else
  echo "=== 单元测试 ==="
  echo "执行: 未检测到 TDD 记录，完整验证"
  ./gradlew testDebugUnitTest 2>&1
  TEST_EXIT=$?
fi
```

**条件执行规则:**

| TDD 状态 | Layer 2.3 行为 |
|---------|---------------|
| 所有业务任务 TDD 已执行 且 覆盖率 >= 80% | 跳过，复用 TDD 结果 |
| TDD 已执行 但 部分任务覆盖率 < 80% | 执行，重点关注低覆盖率模块 |
| TDD 未执行 (无 tasks.json) | 执行 (完整验证) |
| 业务任务 TDD 被用户跳过 | 强制执行，覆盖率阈值提升至 90% |

**解析测试结果:**
```bash
# 测试报告路径
TEST_REPORT=$(find "$PROJECT_ROOT/app/build/reports/tests/testDebugUnitTest" -name "index.html" 2>/dev/null | head -1)

# 提取测试统计
./gradlew testDebugUnitTest 2>&1 | grep -E "tests|failures|passed|skipped"

# 失败测试详情
TEST_XML=$(find "$PROJECT_ROOT/app/build/test-results/testDebugUnitTest" -name "*.xml" 2>/dev/null | head -1)
if [ -f "$TEST_XML" ]; then
  grep 'testcase' "$TEST_XML" | grep 'failure' 2>/dev/null
fi
```

**测试失败分析:**
- 提取失败测试的类名、方法名、错误消息
- 判断是否与本次变更相关 (通过变更文件匹配)
- 与本次变更无关的测试失败 → 标记为 "既有失败"
- 与本次变更相关的测试失败 → 🔴 阻塞

#### 2.4 覆盖率门禁

**无论 Layer 2.3 是否跳过，都执行覆盖率验证。**

```bash
# 覆盖率来源判断
if [ "$TDD_ALL_COVERED" = "true" ] && [ -n "$TDD_REPORT_PATH" ] && [ -f "$TDD_REPORT_PATH" ]; then
  echo "=== 覆盖率门禁 ==="
  echo "来源: TDD 报告 ($TDD_REPORT_PATH)"
  echo "总体覆盖率: ${TDD_AVG_COVERAGE}% (阈值: ${COVERAGE_THRESHOLD}%)"
  COVERAGE_INT=$(printf "%.0f" "$TDD_AVG_COVERAGE" 2>/dev/null || echo "$TDD_AVG_COVERAGE")
  echo "结果: $(if [ -n "$COVERAGE_INT" ] && [ "$COVERAGE_INT" -ge "$COVERAGE_THRESHOLD" ] 2>/dev/null; then echo "✅ 达标"; else echo "❌ 不达标"; fi)"
  COVERAGE_GATE_PASSED=$(if [ -n "$COVERAGE_INT" ] && [ "$COVERAGE_INT" -ge "$COVERAGE_THRESHOLD" ] 2>/dev/null; then echo "true"; else echo "false"; fi)
else
  echo "=== 覆盖率门禁 ==="
  
  # 自己运行覆盖率
  ./gradlew test<Variant>UnitTest 2>&1 | tail -20
  
  # 查找 JaCoCo 报告
  JACOCO_XML=$(find "$PROJECT_ROOT" -path "*/reports/jacoco/*/*.xml" -type f 2>/dev/null | head -1)
  
  if [ -f "$JACOCO_XML" ]; then
    echo "来源: JaCoCo XML 报告"
    echo "报告路径: $JACOCO_XML"
  else
    echo "来源: Gradle 测试输出"
    echo "⚠️ 未找到 JaCoCo 报告，覆盖率数据可能不完整"
  fi
  
  COVERAGE_GATE_PASSED="unknown"
fi
```

**覆盖率门禁规则:**

| 指标 | 默认阈值 | TDD 被跳过时阈值 | 不达标处理 |
|------|---------|-------------------|-----------|
| 总体行覆盖率 | 80% | 90% | 触发自动补测试 |
| 关键路径覆盖率 | 90% | 95% | 触发自动补测试 |
| 分支覆盖率 | 75% | 85% | 记录为 🟡 建议 |

**关键路径定义:** 文件名匹配 `*ViewModel.kt`、`*Repository.kt`、`*RepositoryImpl.kt`、`*UseCase.kt`

**覆盖率不达标时自动补测试:**
1. 识别低于阈值的文件
2. 读取源码，分析未覆盖的分支
3. 生成针对性测试代码
4. 运行测试验证
5. 重新检查覆盖率 (最多 2 轮)

**覆盖率报告格式:**

```
=== 覆盖率门禁 ===
来源: TDD 报告 / QA 执行

总体覆盖率: XX% ✅/❌ (阈值: 80%)
分支覆盖率: XX% ✅/❌ (阈值: 75%)
关键路径:   XX% ✅/❌ (阈值: 90%)

文件级详情:
  ✅ XxxViewModel.kt      XX%
  ✅ XxxRepository.kt     XX%
  🟡 XxxScreen.kt         XX% (建议: 补充测试)
  ❌ XxxMapper.kt         XX% → 触发自动补测试
```

**JaCoCo 未配置时:**
```
⚠️ JaCoCo 未配置，无法精确测量覆盖率。
建议: 在 build.gradle.kts 中添加 JaCoCo 插件。
使用测试通过率作为替代指标: N/N passed ✅
```

**Layer 2 输出格式:**

```
=== Layer 2: 构建与单元测试 ===

构建:     ✅ 通过 (耗时 45s)
Lint:     🟡 2 Warning, 0 Error
单元测试: ✅ 42 passed, 0 failed (耗时 12s)
覆盖率:   XX% (总体) / XX% (关键路径) ✅/❌
TDD:      N/M 任务已执行 / N 跳过

Lint 问题:
  [L2-001] Warning: "UnusedResource" - app/src/main/res/values/strings.xml:15
    描述: 未使用的字符串资源 R.string.unused_text
  [L2-002] Warning: "IconMissingDensityFolder" - app/src/main/res/

测试详情:
  模块: app (42 tests)
  模块: feature:login (8 tests)
  模块: core:common (15 tests)
```

---

### Layer 3: 设备测试 (需要 adb)

**前置条件:** Layer 2 构建成功 (需要 APK)

**设备检测:**
```bash
# 检查是否有可用设备
DEVICES=$(adb devices 2>/dev/null | grep -v "List of devices" | grep -v "^$" | grep -v "unauthorized")
DEVICE_COUNT=$(echo "$DEVICES" | wc -l)
```

**无设备:**
```
=== Layer 3: 设备测试 ===
状态: 跳过 (无可用设备/模拟器)
原因: adb 未安装 / 无已连接设备 / 设备未授权
建议: 连接设备或启动模拟器后重新运行 /android-qa
```

**有设备:**

#### 3.1 安装 APK

```bash
# 确定 APK 路径
APK_PATH=$(find "$PROJECT_ROOT/app/build/outputs/apk/debug" -name "*.apk" 2>/dev/null | head -1)

if [ -z "$APK_PATH" ]; then
  echo "APK_NOT_FOUND"
  exit 1
fi

# 安装到设备
adb install -r "$APK_PATH" 2>&1
INSTALL_EXIT=$?
```

**安装失败:** 记录为 🔴 阻塞，输出错误信息 (签名冲突、版本降级、空间不足)

#### 3.2 启动应用

```bash
# 获取包名
PACKAGE_NAME=$(grep -r 'applicationId\|namespace' "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null | head -1 | grep -oP '"[^"]+"' | tr -d '"' | head -1)

# 获取启动 Activity
LAUNCH_ACTIVITY=$(grep -A5 'android.intent.category.LAUNCHER' "$PROJECT_ROOT/app/src/main/AndroidManifest.xml" 2>/dev/null | grep 'android:name' | head -1 | grep -oP '"[^"]+"' | tr -d '"')

# 启动应用
adb shell am start -n "$PACKAGE_NAME/$LAUNCH_ACTIVITY" 2>&1
```

#### 3.3 关键 UI 测试

根据 Phase 1 确定的测试范围，执行以下检查:

```bash
# 等待应用启动
sleep 3

# 检查应用是否崩溃
CRASH_LOG=$(adb logcat -d -t 50 | grep -i "FATAL EXCEPTION\|AndroidRuntime\|CRASH" | tail -10)

# 如果有崩溃
if [ -n "$CRASH_LOG" ]; then
  echo "CRASH_DETECTED"
  echo "$CRASH_LOG"
fi

# 截取当前屏幕 (用于报告)
adb shell screencap -p /sdcard/qa_screenshot.png
adb pull /sdcard/qa_screenshot.png "$PROJECT_ROOT/docs/reviews/screenshots/" 2>/dev/null
```

**基于 adb 的功能验证:**

```bash
# 模拟点击操作 (根据测试范围中的页面/流程)
# 示例: 登录流程
# adb shell input tap <x> <y>  -- 点击输入框
# adb shell input text "test@example.com"  -- 输入文本
# adb shell input tap <x> <y>  -- 点击登录按钮

# 检查页面跳转
adb shell dumpsys activity activities | grep "mResumedActivity"

# 检查 Toast 消息
adb logcat -d | grep -i "toast\|snackbar" | tail -5

# 检查网络请求 (如有)
adb logcat -d | grep -i "okhttp\|retrofit\|http" | tail -10
```

**注意:** 具体的 adb 操作命令取决于 Phase 1 确定的测试范围。
根据 plan 文件和变更文件推断出需要验证的关键用户流程，
生成对应的 adb 命令序列。

#### 3.4 性能基础检查

```bash
# 启动时间
adb shell am start -W -n "$PACKAGE_NAME/$LAUNCH_ACTIVITY" 2>&1 | grep "TotalTime"

# 内存占用
adb shell dumpsys meminfo "$PACKAGE_NAME" | grep "TOTAL" | head -3

# ANR 检查
adb logcat -d | grep -i "ANR" | tail -5
```

**Layer 3 输出格式:**

```
=== Layer 3: 设备测试 ===
设备:   Pixel 6 (emulator-5554)
安装:   ✅ 成功
启动:   ✅ 无崩溃
启动时间: 320ms (冷启动)
内存:   85MB (TOTAL PSS)

功能验证:
  ✅ 应用正常启动
  ✅ 登录页面加载
  ✅ 输入框可交互
  ❌ 登录按钮点击后无响应 (ANR 3s)

性能:
  ✅ 启动时间 < 500ms
  ✅ 内存 < 150MB
  ✅ 无 ANR
```

---

## Phase 3: Bug 报告

### 步骤 1: 汇总所有层的结果

合并 Layer 1、Layer 2、Layer 3 的发现，按严重程度分类。

**严重程度定义:**

| 级别 | 符号 | 定义 | 处理要求 |
|------|------|------|----------|
| 阻塞 | 🔴 | Crash、功能不可用、编译失败 | 必须修复 |
| 严重 | 🟠 | 主要功能异常、数据丢失风险 | 强烈建议修复 |
| 一般 | 🟡 | 可用但有问题、UX 受影响 | 建议修复 |
| 提示 | 🟢 | 代码质量、最佳实践、优化建议 | 后续处理 |

### 步骤 2: 生成 Bug 报告

写入 `docs/reviews/<branch>-qa-report.md`:

```markdown
# QA 报告: <branch>

> 生成于 <YYYY-MM-DD HH:mm> | android-qa
> 基准分支: <base-branch>
> 测试模式: 完整 QA / 冒烟测试 / 回归测试
> 设备: <设备信息 或 "无设备">

## 摘要

| 指标 | 结果 |
|------|------|
| 变更文件数 | N |
| 🔴 阻塞 | N |
| 🟠 严重 | N |
| 🟡 一般 | N |
| 🟢 提示 | N |
| 构建状态 | ✅ / ❌ |
| 单元测试 | N passed / N failed |
| 设备测试 | ✅ / ❌ / 跳过 |

## TDD 执行摘要

| 指标 | 结果 |
|------|------|
| TDD 状态 | 已检测 / 未检测 |
| TDD 任务数 | N/M |
| TDD 平均覆盖率 | XX% |
| TDD 跳过任务 | N (原因列表) |
| QA 复用 TDD 结果 | 是/否 |

## 覆盖率门禁

| 指标 | 结果 | 阈值 | 状态 |
|------|------|------|------|
| 总体行覆盖率 | XX% | 80% | ✅/❌ |
| 分支覆盖率 | XX% | 75% | ✅/❌ |
| 关键路径覆盖率 | XX% | 90% | ✅/❌ |

## Bug 列表

### 🔴 阻塞

#### BUG-001: <标题>
- **描述:** <问题描述>
- **严重程度:** 🔴 阻塞
- **来源:** Layer 1 静态分析 / Layer 2 构建 / Layer 3 设备
- **文件:** `<文件路径>:<行号>`
- **复现步骤:**
  1. <步骤 1>
  2. <步骤 2>
  3. <预期结果> → <实际结果>
- **建议修复:**
  ```<语言>
  <修复代码示例>
  ```

### 🟠 严重

(同上格式)

### 🟡 一般

(同上格式)

### 🟢 提示

#### TIP-001: <标题>
- **描述:** <问题描述>
- **来源:** Layer 1 / Layer 2
- **文件:** `<文件路径>:<行号>`

## 测试详情

### Layer 1: 静态分析
(静态分析详细结果)

### Layer 2: 构建与单元测试
(构建和测试详细结果)

### Layer 3: 设备测试
(设备测试详细结果，含截图路径)

## 修复建议优先级

1. BUG-001: <标题> — <预估工作量: 小/中/大>
2. BUG-002: <标题> — <预估工作量: 小/中/大>
3. ...
```

### 步骤 3: 展示报告摘要

在终端输出:

```
╔═══════════════════════════════════════════════════════════╗
║                    QA 报告摘要                           ║
╠═══════════════════════════════════════════════════════════╣
║  分支: plan/auth-login-flow                              ║
║  基准: main                                             ║
║  模式: 完整 QA                                          ║
║                                                         ║
║  🔴 阻塞: 1   🟠 严重: 0   🟡 一般: 2   🟢 提示: 3    ║
║                                                         ║
║  构建: ✅     单元测试: ✅ (42/42)    设备: ✅          ║
║                                                         ║
║  完整报告: docs/reviews/plan-auth-login-flow-qa-report.md║
╚═══════════════════════════════════════════════════════════╝
```

---

## Phase 4: 修复循环

### 步骤 1: 问题分类

将 Bug 分为两类:

| 类别 | 条件 | 处理方式 |
|------|------|----------|
| 自动修复 | 缺少资源文件、lint 警告、未使用的导入、简单硬编码 | 直接修复 |
| 需确认 | 逻辑错误、架构问题、需要业务判断的修复 | 询问用户 |
| 覆盖率不达标 | 自动补测试 → 重新验证覆盖率 | 新增 |

### 步骤 2: 自动修复

**自动修复范围:**

1. **缺少资源文件** — 创建缺失的 string/dimen/color/drawable 资源
2. **未使用的导入** — 删除无用 import 语句
3. **Lint Warning (简单)** — 按 lint 建议修改
4. **硬编码字符串** — 抽取到 strings.xml
5. **硬编码尺寸** — 抽取到 dimens.xml
6. **覆盖率缺口** — 为低于阈值的文件生成补充测试，重新验证覆盖率

```bash
# 示例: 创建缺失的字符串资源
# 在 values/strings.xml 中添加:
# <string name="missing_string">默认值</string>

# 示例: 删除未使用的导入
# 通过 Edit 工具精确删除对应行
```

**修复后验证:**
- 修复资源问题 → 重新运行 Layer 1 资源完整性检查
- 修复 lint 问题 → 重新运行 `./gradlew lintDebug`
- 修复编译问题 → 重新运行 `./gradlew assembleDebug`

### 步骤 3: 复杂问题处理

对于无法自动修复的问题:

```
以下问题需要确认是否修复:

🔴 BUG-001: 登录按钮点击后无响应
  位置: app/src/main/java/com/example/login/LoginViewModel.kt:67
  原因: coroutine scope 未正确绑定到 viewModelScope
  修复: 将 GlobalScope.launch 替换为 viewModelScope.launch

是否自动修复此问题?
- A) 是，修复所有可自动修复的问题
- B) 逐个确认每个修复
- C) 跳过修复，仅报告
```

### 步骤 4: 修复循环控制

```
修复循环: 第 1/3 轮

本轮修复: 3 个问题
  ✅ 自动修复: BUG-003 (缺少资源)
  ✅ 自动修复: TIP-001 (未使用导入)
  ✅ 用户确认: BUG-001 (逻辑错误)

重新验证...
  构建: ✅
  Lint: ✅ (0 Warning)
  单元测试: ✅ (42/42)

剩余问题: 0
修复循环完成。
```

**循环终止条件:**
- 所有阻塞和严重问题已修复 → 完成
- 达到 3 轮上限 → 提示用户手动处理剩余问题
- 用户选择停止 → 记录当前状态

### 步骤 5: 提交修复 (如有)

```bash
# 如果有自动修复的变更
git add -A
git commit -m "$(cat <<'EOF'
fix: QA 自动修复 - <问题摘要>

修复内容:
- <修复 1 描述>
- <修复 2 描述>

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

```bash
# 记录 QA 修复到 tasks.json (如果存在)
TASKS_JSON="$MAIN_WORKTREE/.claude/android-worktree-runner/tasks.json"
if [ -f "$TASKS_JSON" ]; then
  echo "QA 自动修复已记录到 tasks.json"
fi
```

记录修复 commit hash 列表。

---

## Capture Learnings

QA 完成后，将发现的典型 bug 模式记录到学习系统以供未来 session 参考。

**记录时机:**

1. **发现典型 bug 模式** — 如果 bug 不是简单的拼写/配置错误，而是具有普遍性的模式，使用 android-learnings-log 记录:
   ```bash
   bash .claude/skills/android-shared/bin/android-learnings-log '{"skill":"qa","type":"pitfall","key":"<bug模式简述>","insight":"<bug描述和修复方式>","confidence":8,"source":"observed","files":["<bug文件>"]}'
   ```

2. **发现项目特有的测试配置问题** — 如特定的 lint 规则误报、测试环境配置坑，记录为 technique:
   ```bash
   bash .claude/skills/android-shared/bin/android-learnings-log '{"skill":"qa","type":"technique","key":"<配置名>","insight":"<配置坑描述>","confidence":7,"source":"observed","files":["<配置文件>"]}'
   ```

**不记录:**
- 一次性的拼写错误
- 已被自动修复的简单 lint warning
- 与历史记录完全重复的发现

---

## 产出

### 产出物 1: Bug 报告

- 路径: `docs/reviews/<branch>-qa-report.md`
- 内容: 完整的 QA 报告，包含所有问题、复现步骤、修复建议

### 产出物 2: 修复 Commit (如有)

- 列出所有修复 commit 的 hash
- 每个 commit 对应修复的问题编号

### 产出物 3: 截图 (如有设备)

- 路径: `docs/reviews/screenshots/`
- 内容: 测试过程中的屏幕截图

---

## 异常情况处理

| 场景 | 处理方式 |
|------|----------|
| 不在 git 仓库中 | 报错: "android-qa 需要 git 仓库" |
| 不是 Android 项目 | 报错: "未检测到 Android 项目" |
| Gradle 不可用 | 报错: "gradlew 未找到或不可执行" |
| 当前分支无变更 (与基准相同) | 提示: "当前分支无变更，无需 QA" |
| 构建失败 | 记录为 🔴 阻塞，不执行后续测试 |
| 单元测试超时 (>10 分钟) | 终止测试，标记为超时 |
| adb 设备未授权 | 提示: "请在设备上授权 USB 调试"，跳过 Layer 3 |
| APK 安装失败 (签名冲突) | 先 `adb uninstall <package>` 再重试 |
| docs/reviews 目录不存在 | 自动创建 |
| 与 android-investigate 集成 | 发现复杂 bug 时，建议调用 android-investigate 进行根因分析 |
| TDD 被跳过的业务任务 | 覆盖率阈值提升至 90%，Layer 2.3 强制执行，记录警告 |
| 无 JaCoCo 配置 | 提示配置 JaCoCo 以启用覆盖率门禁，使用测试通过率替代 |

---

## 与其他 Skill 的衔接

### 上游: android-worktree-runner

当 android-worktree-runner 完成 Plan 的所有任务后 (Phase 3)，
可自动调用 `/android-qa` 对完成的分支进行 QA。

调用方式:
```
Plan 所有任务已完成。是否执行 QA 测试?
- A) 是，运行 /android-qa
- B) 跳过 QA
```

### 下游: android-investigate

当 QA 发现复杂的 bug (非简单修复) 时，建议调用 android-investigate 进行根因分析。

调用方式:
```
发现复杂问题 BUG-001，建议使用 /android-investigate 进行根因分析。
是否启动调查?
- A) 是，启动 /android-investigate
- B) 跳过，仅记录在报告中
```

**如果发现可修复的功能 bug (非复杂根因):**
1. 输出 `docs/reviews/<branch>-qa-fix-tasks.md`，格式与 autoplan plan 兼容:
   ```markdown
   ### Task 1: 修复 &lt;bug 标题&gt;
   **层级:** &lt;对应层级&gt;
   **TDD:** required
   **步骤:**
   - [ ] &lt;修复步骤&gt;
   ```
2. 建议用户运行: `/android-worktree-runner import docs/reviews/<branch>-qa-fix-tasks.md`

### 与其他 skill 的关系

| Skill | 关系 | 说明 |
|-------|------|------|
| android-worktree-runner | 上游 | Plan 执行完毕后调用本 skill |
| android-investigate | 下游 | 发现复杂 bug 时调用进行根因分析 |
| android-design-review | 参考 | QA 时对照 design-spec.md 验证设计还原度 |
| android-autoplan | 参考 | QA 时对照 plan 文件验证功能完整性 |
| android-tdd | 上游 | QA 读取 TDD 报告和 tasks.json TDD 状态，避免重复测试，复用覆盖率数据 |

---

## 文件结构

```
项目根目录/
├── docs/
│   └── reviews/
│       ├── <branch>-qa-report.md          ← 本 skill 产出的 bug 报告
│       └── screenshots/                   ← 设备测试截图 (如有)
│           └── qa_screenshot_*.png
├── .claude/
│   └── skills/
│       └── android-qa/
│           └── SKILL.md                   ← 本 skill
└── ...
```
