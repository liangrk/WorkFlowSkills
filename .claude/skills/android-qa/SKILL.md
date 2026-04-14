---
name: android-qa
description: |
  Android 分层 QA: 静态分析→构建/测试→性能→无障碍→设备→PRD验收。
  产出结构化 bug 报告,自动修复简单问题。
---

# Android QA

**启动声明:** "我正在使用 android-qa skill。"
**调用:** `/android-qa` | `<branch>` | `smoke` | `regression`

## Phase 0: 环境检测

```bash
_R="$(git worktree list | head -1 | awk '{print $1}')"
SHARED_BIN="$_R/.claude/skills/android-shared/bin"
[ ! -d "$SHARED_BIN" ] && SHARED_BIN="$HOME/.claude/skills/android-shared/bin"
bash "$SHARED_BIN/android-learnings-bootstrap" 2>/dev/null || true
LEARNINGS=$(bash "$SHARED_BIN/android-learnings-search" --type pitfall --limit 5 2>/dev/null || true)
ENV_JSON=$(bash "$SHARED_BIN/android-detect-env" 2>/dev/null || true)

PROJECT_ROOT=$(git rev-parse --show-toplevel)
BASE_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo main)
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

# 确认 Android 项目
ls build.gradle build.gradle.kts app/build.gradle app/build.gradle.kts 2>/dev/null || { echo "NOT_ANDROID"; exit 1; }

# TDD 状态
MAIN_WORKTREE=$(git worktree list | head -1 | awk '{print $1}')
TASKS_FILE="$MAIN_WORKTREE/.claude/android-worktree-runner/tasks.json"
# 读取 TDD 状态 → 设置 TDD_STATUS / TDD_ALL_COVERED / TDD_AVG_COVERAGE / COVERAGE_THRESHOLD(80或90)

# PRD 加载
PRD_FILE=$(grep -l "^## PRD$" docs/plans/*.md 2>/dev/null | head -1)
if [ -n "$PRD_FILE" ]; then
  sed -n '/^## PRD$/,/^## [^#]/p' "$PRD_FILE" | head -n -1
  # 解析 FR-N / AC-N / exclusions
fi
```

## Phase 1: 测试范围

```bash
CHANGED_FILES=$(git diff --name-only "$BASE_BRANCH"...HEAD 2>/dev/null)
CODE_CHANGES=$(echo "$CHANGED_FILES" | grep -E '\.(kt|java)$')
RESOURCE_CHANGES=$(echo "$CHANGED_FILES" | grep -E '\.(xml|png|webp|svg|jpg)$')
GRADLE_CHANGES=$(echo "$CHANGED_FILES" | grep -E 'build\.gradle|settings\.gradle|gradle\.properties|libs\.versions\.toml')
```

**smoke 模式:** 仅关注核心功能路径。
**regression 模式:** 额外包含基准分支已有功能的关键路径验证。

## Phase 2: 分层测试

### Layer 1: 静态分析 (无需设备)

| 检查项 | 检测 | 严重 |
|--------|------|------|
| 空指针风险 | `!!` 操作符 | 高 |
| 空 catch 块 | `catch.*{ *}` | 中 |
| TODO/FIXME | `TODO\|FIXME\|HACK` | 中 |
| 硬编码字符串 | UI 代码中字符串字面量 | 中 |
| 内存泄漏 | 匿名类持有 Activity | 高 |
| 主线程 IO | `Dispatchers.Main` + http/retrofit | 高 |
| 资源完整性 | R.drawable/R.string 存在性 | 高 |
| Manifest 声明 | Activity/Service/Receiver 声明 | 高 |
| 新增权限 | AndroidManifest.xml 中 uses-permission diff | 中 |

### Layer 2: 构建+测试 (无需设备)

```bash
# 严格串行: 构建→lint→测试
./gradlew assembleDebug 2>&1           # 失败→停止
./gradlew lintDebug 2>&1               # Error→阻塞, Warning→记录
./gradlew testDebugUnitTest 2>&1       # 失败→修复循环(max 3轮)
```

**TDD 条件执行:**

| TDD 状态 | 行为 |
|----------|------|
| 全部已执行且≥80% | 跳过,复用TDD结果 |
| 部分<80% | 执行,关注低覆盖率模块 |
| 未检测 | 执行(完整验证) |
| 业务任务被跳过 | 强制执行,阈值提升至90% |

**覆盖率门禁:**

| 指标 | 默认 | TDD跳过时 |
|------|------|-----------|
| 总体行覆盖率 | 80% | 90% |
| 关键路径 | 90% | 95% |
| 分支覆盖率 | 75% | 85% |

不达标→自动补测试(max 2轮)。

### Layer 3: 性能基准

| 检查 | 基准 | 级别 |
|------|------|------|
| 构建耗时(冷) | <120s | WARN |
| Debug APK | <50MB | WARN |
| 冷启动 | <1000ms | WARN |
| 内存 | <200MB | WARN |
| StrictMode | 0 violations | WARN |

**3C Compose (仅 Compose 项目):**
- LazyColumn/LazyRow 缺少 key → 建议
- @Stable/@Immutable 缺失 → 建议
- collectAsState 无限定 → 建议

### Layer 4: 无障碍检测

| 检查 | 基准 |
|------|------|
| ImageView contentDescription | 100% |
| 可点击元素 contentDescription | 100% |
| 触摸目标 | ≥48dp |
| 文字大小单位 | 全部 sp |

### Layer 5: 设备测试 (需要 adb)

```bash
DEVICES=$(adb devices 2>/dev/null | grep -v "List" | grep -v "^$" | grep -v "unauthorized")
if [ -n "$DEVICES" ]; then
  APK=$(find app/build/outputs/apk/debug -name "*.apk" | head -1)
  adb install -r "$APK" 2>&1
  adb shell am start -n "$PACKAGE/$LAUNCH_ACTIVITY" 2>&1
  sleep 3
  # 崩溃检测
  adb logcat -d -t 50 | grep -i "FATAL EXCEPTION\|AndroidRuntime\|CRASH"
  # 截图
  adb shell screencap -p /sdcard/qa.png && adb pull /sdcard/qa.png
  # 性能
  adb shell am start -W -n "$PACKAGE/$LAUNCH_ACTIVITY" | grep TotalTime
  adb shell dumpsys meminfo "$PACKAGE" | grep TOTAL
fi
```

无设备→跳过,不阻塞。

## Phase 3: PRD 验收

若 PRD_LOADED != true → 跳过。

对每条 AC-N:
- ✓ PASS: 测试覆盖 + 功能完整
- ⚠ PARTIAL: 功能存在但测试不足/不完整
- ✗ FAIL: 无功能代码或不满足
- ⊘ SKIP: 依赖外部条件无法验证

检查"明确不做"列表→若有代码实现→⚠ 范围蔓延风险。

## Phase 4: Bug 报告

写入 `docs/reviews/<branch>-qa-report.md`

| 级别 | 符号 | 定义 | 处理 |
|------|------|------|------|
| 阻塞 | 🔴 | Crash/功能不可用/编译失败 | 必须修复 |
| 严重 | 🟠 | 主要功能异常/数据丢失 | 强烈建议 |
| 一般 | 🟡 | 可用但有问题/UX受影响 | 建议修复 |
| 提示 | 🟢 | 代码质量/最佳实践 | 后续处理 |

报告格式参见 REFERENCE.md。

## Phase 5: 修复循环

详见 `REFERENCE.md` — Phase 5 修复循环。

## Capture Learnings

详见 `REFERENCE.md` — Capture Learnings。

## 异常处理

详见 `REFERENCE.md` — 异常情况处理表。

## 与其他 Skill 衔接

详见 `REFERENCE.md` — 与其他 Skill 的衔接。
