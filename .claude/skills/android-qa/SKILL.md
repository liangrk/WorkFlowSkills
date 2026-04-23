---
name: android-qa
description: Use when validating Android changes with layered QA gates (static/build/test/perf/a11y/device/UI-diff/PRD) and generating a structured qa report.
---

# Android QA

**启动声明:** "我正在使用 android-qa skill。"
**调用:** `/android-qa` | `<branch>` | `smoke` | `regression`

## Phase 0: 环境与上下文

```bash
SHARED_BIN=$(bash android-resolve-path 2>/dev/null || true)
bash "$SHARED_BIN/bin/android-tool-doctor" 2>/dev/null || true
RUN_ID=$(bash "$SHARED_BIN/bin/android-run-id" --ensure 2>/dev/null || echo "run-local")
export ANDROID_WORKFLOW_RUN_ID="$RUN_ID"
bash "$SHARED_BIN/bin/android-learnings-bootstrap" 2>/dev/null || true
LEARNINGS=$(bash "$SHARED_BIN/bin/android-learnings-search" --type pitfall --limit 5 2>/dev/null || true)
ENV_JSON=$(bash "$SHARED_BIN/bin/android-detect-env" 2>/dev/null || true)

PROJECT_ROOT=$(git rev-parse --show-toplevel)
BASE_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo main)
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
ls build.gradle build.gradle.kts app/build.gradle app/build.gradle.kts 2>/dev/null || { echo "NOT_ANDROID"; exit 1; }

MAIN_WORKTREE=$(git worktree list | head -1 | awk '{print $1}')
TASKS_FILE="$MAIN_WORKTREE/.claude/android-worktree-runner/tasks.json"

PRD_FILE=$(grep -l "^## PRD$" docs/plans/*.md 2>/dev/null | head -1)
if [ -n "$PRD_FILE" ]; then
  sed -n '/^## PRD$/,/^## [^#]/p' "$PRD_FILE" | head -n -1
fi

CODE_REVIEW=$(find docs/reviews -name "*-code-review.md" -mmin -10080 2>/dev/null | sort -r | head -1)
```

## Phase 1: 测试范围

```bash
CHANGED_FILES=$(git diff --name-only "$BASE_BRANCH"...HEAD 2>/dev/null)
CODE_CHANGES=$(echo "$CHANGED_FILES" | grep -E '\.(kt|java)$')
RESOURCE_CHANGES=$(echo "$CHANGED_FILES" | grep -E '\.(xml|png|webp|svg|jpg)$')
GRADLE_CHANGES=$(echo "$CHANGED_FILES" | grep -E 'build\.gradle|settings\.gradle|gradle\.properties|libs\.versions\.toml')
```

`smoke`: 核心路径。`regression`: 增加历史关键路径。

## Phase 2: 分层测试

### Layer 1: 静态分析（优先复用 code-review）

```bash
if [ -n "$CODE_REVIEW" ] && [ -f "$CODE_REVIEW" ]; then
  grep -E "^\[BLOCKER\]|^\[WARNING\]" "$CODE_REVIEW"
else
  grep -rn '!!' app/src/main --include="*.kt" | head -10
  grep -rn 'Dispatchers\.Main' app/src/main --include="*.kt" | grep -i "http\|request" | head -5
fi
```

### Layer 2: 构建+测试（强制串行）

```bash
./gradlew assembleDebug --no-daemon 2>&1
./gradlew lintDebug --no-daemon 2>&1
./gradlew testDebugUnitTest --no-daemon 2>&1
```

TDD 条件执行:

| TDD 状态 | 行为 |
|----------|------|
| 全部已执行且≥80% | 跳过, 复用 TDD 结果 |
| 部分<80% | 执行, 关注低覆盖率模块 |
| 未检测 | 执行完整验证 |
| 业务任务被跳过 | 强制执行, 阈值升至 90% |

覆盖率门禁:

| 指标 | 默认 | TDD跳过时 |
|------|------|-----------|
| 总体行覆盖率 | 80% | 90% |
| 关键路径 | 90% | 95% |
| 分支覆盖率 | 75% | 85% |

不达标: 自动补测试（最多 2 轮）。

### Layer 3: 性能基准

| 检查 | 基准 | 级别 |
|------|------|------|
| 构建耗时(冷) | <120s | WARN |
| Debug APK | <50MB | WARN |
| 冷启动 | <1000ms | WARN |
| 内存 | <200MB | WARN |
| StrictMode | 0 violations | WARN |

Compose 建议: Lazy 列表 key、`@Stable/@Immutable`、受控 `collectAsState`。

### Layer 4: 无障碍检测

| 检查 | 基准 |
|------|------|
| ImageView contentDescription | 100% |
| 可点击元素 contentDescription | 100% |
| 触摸目标 | ≥48dp |
| 文字大小单位 | 全部 sp |

### Layer 5: 设备测试（需要 adb）

```bash
DEVICES=$(adb devices 2>/dev/null | grep -v "List" | grep -v "^$" | grep -v "unauthorized")
if [ -n "$DEVICES" ]; then
  APK=$(find app/build/outputs/apk/debug -name "*.apk" | head -1)
  adb install -r "$APK" 2>&1
  adb shell am start -n "$PACKAGE/$LAUNCH_ACTIVITY" 2>&1
  sleep 3
  adb logcat -d -t 50 | grep -i "FATAL EXCEPTION\|AndroidRuntime\|CRASH"
  adb shell screencap -p /sdcard/qa.png && adb pull /sdcard/qa.png
  adb shell am start -W -n "$PACKAGE/$LAUNCH_ACTIVITY" | grep TotalTime
  adb shell dumpsys meminfo "$PACKAGE" | grep TOTAL
fi
```

无设备: 跳过，不阻塞。

### Layer 6: UI Dump Gate

```bash
DUMP_SCRIPT=".claude/skills/android-dump/scripts/dump_android_ui.py"
BASELINE_DIR="android-dumps/baseline"
QA_DUMP_DIR="android-dumps/qa-$(date +%Y%m%d-%H%M%S)"

if [ -n "$DEVICES" ] && [ -f "$DUMP_SCRIPT" ] && [ -n "$PACKAGE" ]; then
  python "$DUMP_SCRIPT" \
    --package "$PACKAGE" \
    --output "$QA_DUMP_DIR" \
    --run-id "$RUN_ID" \
    --json-only \
    --no-open \
    --compact \
    --max-ids 30 \
    --max-text 15 \
    $( [ -d "$BASELINE_DIR" ] && echo "--baseline $BASELINE_DIR" )

  bash "$SHARED_BIN/bin/android-artifact-validate" "$QA_DUMP_DIR" 2>/dev/null || true
fi
```

上下文约束:
- 优先读取 `llm_summary.json`
- 仅在必要时读取 `ui_diff.json`
- 不把 `ui_hierarchy.xml/tree_view.html` 直接注入上下文

门禁阈值:

| 条件 | 级别 |
|------|------|
| `id_similarity < 0.70` 或 `removed_ids > 15` | 🔴 BLOCKER |
| `id_similarity < 0.85` 或 `removed_ids > 5` | 🟠 WARNING |
| 其他差异 | 🟡 INFO |

无 baseline: 仅产出 `screen_fingerprint.json`，不阻塞。

## Phase 3: PRD 验收

若 PRD 未加载则跳过。对每条 AC 标记:
- `PASS`: 功能完整且有测试
- `PARTIAL`: 功能存在但测试不足
- `FAIL`: 不满足
- `SKIP`: 外部条件无法验证

若 "明确不做" 被实现，标记范围蔓延风险。

## Phase 4: Bug 报告

写入 `docs/reviews/<branch>-qa-report.md`。

| 级别 | 符号 | 定义 | 处理 |
|------|------|------|------|
| 阻塞 | 🔴 | Crash/功能不可用/编译失败 | 必须修复 |
| 严重 | 🟠 | 主要功能异常/数据丢失 | 强烈建议 |
| 一般 | 🟡 | 可用但有问题/UX受影响 | 建议修复 |
| 提示 | 🟢 | 代码质量/最佳实践 | 后续处理 |

## Phase 5: 修复循环

```bash
ROUND=1
while [ "$ROUND" -le 3 ]; do
  ./gradlew assembleDebug --no-daemon || break
  ./gradlew testDebugUnitTest --no-daemon || true
  ROUND=$((ROUND + 1))
done
```

超过 3 轮仍失败: 标记 BLOCKER，交给 `android-investigate`。

## Capture Learnings

```bash
bash "$SHARED_BIN/bin/android-learnings-log" '{"skill":"qa","type":"pitfall","key":"KEY","insight":"INSIGHT","confidence":8,"source":"observed","files":[]}'
```

## 异常处理

| 场景 | 处理 |
|------|------|
| 无 ADB 设备 | 跳过 Layer 5/6 |
| 无 baseline | 仅产出 fingerprint |
| dump 脚本缺失 | warning, 不阻塞 |
| dump 执行失败 | 重试 1 次后 warning |
| 覆盖率报告缺失 | 回退 testDebugUnitTest 结果 |
| Gradle 超时 | 记录 blocked, 建议拆分 |

## Skill 衔接

| 上游/下游 | 说明 |
|----------|------|
| 上游 `android-code-review` | 复用 BLOCKER/WARNING |
| 下游 `android-investigate` | 深挖 BLOCKER |
| 下游 `android-fix` | 从 qa-report 生成修复计划 |
| 依赖 `android-dump` | Layer 6 做 UI 回归门禁 |
