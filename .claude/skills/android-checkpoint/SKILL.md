---
name: android-checkpoint
description: |
  Android 跨 session 检查点 skill。保存和恢复 android-autoplan 的
  完整会话状态 (技术栈、架构、plan、审查结论、决策记录)。
  解决 /clear 或会话重启后上下文丢失的问题。
  适用场景: 保存进度、恢复进度、跨 session 连续工作。
voice-triggers:
  - "保存进度"
  - "恢复进度"
  - "检查点"
---

# Android Checkpoint

## 概述

跨 session 状态保存与恢复。将 android-autoplan 的完整会话上下文
(技术栈档案、架构推断、plan 内容、各阶段审查结论、决策记录)
序列化为 JSON 检查点文件，支持随时恢复。

**启动时声明:** "我正在使用 android-checkpoint skill。"

**零外部依赖:** 仅使用 Claude Code 原生工具 (Read、Write、Edit、Grep、Glob、Bash)。
不依赖 gstack、browse、Codex、Figma MCP。

## 调用方式

```bash
/android-checkpoint save              # 保存当前会话状态
/android-checkpoint restore           # 恢复上次保存的状态
/android-checkpoint restore <index>   # 恢复指定编号的检查点
/android-checkpoint status            # 显示所有检查点
```

**参数处理:**
- `save`: 执行 Phase 1，采集当前会话状态并写入检查点文件
- `restore`: 执行 Phase 2，列出可用检查点并恢复上下文
- `restore <index>`: 直接恢复指定编号的检查点 (从 status 列表中获取编号)
- `status`: 执行 Phase 3，列出所有检查点摘要

---

## 存储规范

### 存储路径

```
<项目根目录>/.claude/android-checkpoint/
  ├── checkpoint-20260410-143022.json
  ├── checkpoint-20260410-160545.json
  └── ...
```

### 文件命名

`checkpoint-<YYYYMMDD>-<HHmmss>.json`

时间戳使用当前系统时间，确保按文件名排序即等于按时间排序。

### 保留策略

- 最多保留最近 10 个检查点文件
- 每次保存新检查点后自动清理超出数量的旧文件
- 清理时按文件名排序 (即按时间倒序)，删除第 11 个及之后的文件

### .gitignore

检查点目录应被 git 忽略。首次运行 save 时自动处理:

```bash
# 检查 .gitignore 是否已包含检查点目录
CHECKPOINT_GITIGNORE=".claude/android-checkpoint/"
if ! grep -qF "$CHECKPOINT_GITIGNORE" "$PROJECT_ROOT/.gitignore" 2>/dev/null; then
  echo "" >> "$PROJECT_ROOT/.gitignore"
  echo "# Android checkpoint session state (not for commit)" >> "$PROJECT_ROOT/.gitignore"
  echo "$CHECKPOINT_GITIGNORE" >> "$PROJECT_ROOT/.gitignore"
fi
```

---

## Phase 1: 保存 (save 模式)

### 步骤 1: 确认项目环境

```bash
# 项目根目录
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -z "$PROJECT_ROOT" ]; then
  echo "错误: 未找到 git 仓库"
  exit 1
fi

# 当前分支
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

# 当前时间戳
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
ISO_TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# 检查点目录
CHECKPOINT_DIR="$PROJECT_ROOT/.claude/android-checkpoint"
mkdir -p "$CHECKPOINT_DIR"
```

### 步骤 2: 确保目录存在并配置 .gitignore

```bash
# 创建检查点目录
mkdir -p "$CHECKPOINT_DIR"

# 确保 .gitignore 包含检查点目录
CHECKPOINT_GITIGNORE=".claude/android-checkpoint/"
if ! grep -qF "$CHECKPOINT_GITIGNORE" "$PROJECT_ROOT/.gitignore" 2>/dev/null; then
  echo "" >> "$PROJECT_ROOT/.gitignore"
  echo "# Android checkpoint session state (not for commit)" >> "$PROJECT_ROOT/.gitignore"
  echo "$CHECKPOINT_GITIGNORE" >> "$PROJECT_ROOT/.gitignore"
fi
```

### 步骤 3: 采集技术栈档案

扫描项目，重建技术栈档案 (与 android-autoplan 前置检测逻辑一致):

```bash
# UI 框架
COMPOSE_DETECTED="false"
XML_DETECTED="false"
grep -rq "androidx.compose" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null && COMPOSE_DETECTED="true"
grep -rlq "@Composable" "$PROJECT_ROOT/app/src" 2>/dev/null && COMPOSE_DETECTED="true"
find "$PROJECT_ROOT/app/src/main/res/layout" -name "*.xml" 2>/dev/null | head -1 && XML_DETECTED="true"

# 异步框架
COROUTINES_DETECTED="false"
RXJAVA_DETECTED="false"
grep -rq "kotlinx.coroutines" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null && COROUTINES_DETECTED="true"
grep -rlq "import kotlinx.coroutines" "$PROJECT_ROOT/app/src" 2>/dev/null && COROUTINES_DETECTED="true"
grep -rlq "import io.reactivex" "$PROJECT_ROOT/app/src" 2>/dev/null && RXJAVA_DETECTED="true"

# 依赖注入
HILT_DETECTED="false"
KOIN_DETECTED="false"
grep -rq "com.google.dagger:hilt" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null && HILT_DETECTED="true"
grep -rq "io.insert-koin" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null && KOIN_DETECTED="true"

# 网络库
RETROFIT_DETECTED="false"
KTOR_DETECTED="false"
grep -rq "com.squareup.retrofit2" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null && RETROFIT_DETECTED="true"
grep -rq "io.ktor" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null && KTOR_DETECTED="true"

# 数据库
ROOM_DETECTED="false"
SQLDELIGHT_DETECTED="false"
grep -rq "androidx.room" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null && ROOM_DETECTED="true"
grep -rq "app.cash.sqldelight" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null && SQLDELIGHT_DETECTED="true"

# 图片加载
COIL_DETECTED="false"
GLIDE_DETECTED="false"
grep -rq "io.coil-kt" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null && COIL_DETECTED="true"
grep -rq "com.github.bumptech.glide" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null && GLIDE_DETECTED="true"

# 导航
NAV_DETECTED="false"
grep -rq "androidx.navigation" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null && NAV_DETECTED="true"
```

### 步骤 4: 采集架构信息

```bash
# 包结构
PACKAGE_DIRS=$(find "$PROJECT_ROOT/app/src/main/java" -type d 2>/dev/null | head -20)
if [ -z "$PACKAGE_DIRS" ]; then
  PACKAGE_DIRS=$(find "$PROJECT_ROOT/app/src/main/kotlin" -type d 2>/dev/null | head -20)
fi

# 架构模式推断
HAS_VIEWMODEL="false"
HAS_REPOSITORY="false"
HAS_USECASE="false"
HAS_REDUCER="false"
grep -rlq "ViewModel" "$PROJECT_ROOT/app/src" 2>/dev/null && HAS_VIEWMODEL="true"
grep -rlq "Repository" "$PROJECT_ROOT/app/src" 2>/dev/null && HAS_REPOSITORY="true"
grep -rlq "UseCase\|Interactor" "$PROJECT_ROOT/app/src" 2>/dev/null && HAS_USECASE="true"
grep -rlq "Reducer\|Action\|Event" "$PROJECT_ROOT/app/src" 2>/dev/null && HAS_REDUCER="true"

# 推断架构
if [ "$HAS_REDUCER" = "true" ]; then
  INFERRED_ARCH="MVI"
elif [ "$HAS_USECASE" = "true" ]; then
  INFERRED_ARCH="Clean Architecture"
elif [ "$HAS_VIEWMODEL" = "true" ]; then
  INFERRED_ARCH="MVVM"
else
  INFERRED_ARCH="未检测到"
fi
```

### 步骤 5: 采集构建配置

```bash
# SDK 版本
MIN_SDK=$(grep -E "minSdk\s*=" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null | head -1 | grep -oP '\d+' | head -1)
TARGET_SDK=$(grep -E "targetSdk\s*=" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null | head -1 | grep -oP '\d+' | head -1)
COMPILE_SDK=$(grep -E "compileSdk\s*=" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null | head -1 | grep -oP '\d+' | head -1)

# 模块列表
MODULES=$(cat "$PROJECT_ROOT/settings.gradle" "$PROJECT_ROOT/settings.gradle.kts" 2>/dev/null | grep "include" | sed 's/.*include[(:]*\s*//' | tr -d "'\":)" | tr ',' '\n' | sed 's/^[[:space:]]*//' | sort -u)
```

### 步骤 6: 查找关联的 Plan 文件

```bash
# 查找 docs/plans 下的 plan 文件
PLAN_FILES=$(find "$PROJECT_ROOT/docs/plans" -name "*.md" -not -name "*design-spec*" -not -name "*test-plan*" -not -name "*qa-report*" 2>/dev/null)

# 如果找到 plan 文件，读取最近的
if [ -n "$PLAN_FILES" ]; then
  LATEST_PLAN=$(echo "$PLAN_FILES" | sort -r | head -1)
  PLAN_TITLE=$(head -1 "$LATEST_PLAN" | sed 's/^# Plan: //')
  PLAN_SLUG=$(basename "$LATEST_PLAN" .md)
  TASK_COUNT=$(grep -c "^### Task" "$LATEST_PLAN" 2>/dev/null)

  # 检查关联的 design-spec
  DESIGN_SPEC=$(find "$PROJECT_ROOT/docs/plans" -name "${PLAN_SLUG}-design-spec.md" 2>/dev/null | head -1)
  if [ -n "$DESIGN_SPEC" ]; then
    DESIGN_SPEC_PATH="$DESIGN_SPEC"
  else
    DESIGN_SPEC_PATH="null"
  fi
else
  LATEST_PLAN="null"
  PLAN_TITLE="null"
  PLAN_SLUG="null"
  TASK_COUNT=0
  DESIGN_SPEC_PATH="null"
fi
```

### 步骤 7: 采集审查结论

扫描 plan 文件和关联文件，提取各阶段审查结论:

```bash
# CEO Review 结论 (Phase 2)
# 查找 plan 文件中的范围砍伐/CEO Review 段落
CEO_REVIEW=$(grep -A 20 "## CEO Review\|## 范围确认\|## Phase 2" "$LATEST_PLAN" 2>/dev/null | head -20)
if [ -n "$CEO_REVIEW" ]; then
  # 提取结论摘要 (第一行非标题、非空行)
  CEO_SUMMARY=$(echo "$CEO_REVIEW" | grep -v "^##" | grep -v "^$" | head -3 | tr '\n' ' ')
else
  CEO_SUMMARY="null"
fi

# Design Review 结论 (Phase 3)
DESIGN_SPEC_FILE=$(find "$PROJECT_ROOT/docs/plans" -name "${PLAN_SLUG}-design-spec.md" 2>/dev/null | head -1)
if [ -n "$DESIGN_SPEC_FILE" ]; then
  DESIGN_SUMMARY="Design spec 已生成: $DESIGN_SPEC_FILE"
else
  DESIGN_SUMMARY="null"
fi

# Eng Review 结论 (Phase 4)
ENG_REVIEW=$(grep -A 30 "## 审查备注\|## Eng Review\|## Phase 4" "$LATEST_PLAN" 2>/dev/null | head -30)
if [ -n "$ENG_REVIEW" ]; then
  # 提取各维度结论
  ARCH_CONCLUSION=$(echo "$ENG_REVIEW" | grep -i "架构" | head -2 | tr '\n' ' ')
  GRADLE_CONCLUSION=$(echo "$ENG_REVIEW" | grep -i "gradle\|manifest" | head -2 | tr '\n' ' ')
  LIFECYCLE_CONCLUSION=$(echo "$ENG_REVIEW" | grep -i "生命周期\|lifecycle" | head -2 | tr '\n' ' ')
  TEST_CONCLUSION=$(echo "$ENG_REVIEW" | grep -i "测试\|test" | head -2 | tr '\n' ' ')
  PERF_CONCLUSION=$(echo "$ENG_REVIEW" | grep -i "性能\|performance" | head -2 | tr '\n' ' ')
else
  ARCH_CONCLUSION="null"
  GRADLE_CONCLUSION="null"
  LIFECYCLE_CONCLUSION="null"
  TEST_CONCLUSION="null"
  PERF_CONCLUSION="null"
fi

# DX Review 结论 (Phase 5)
DX_REVIEW=$(grep -A 20 "## DX 建议\|## Phase 5" "$LATEST_PLAN" 2>/dev/null | head -20)
if [ -n "$DX_REVIEW" ]; then
  DX_SUMMARY=$(echo "$DX_REVIEW" | grep -v "^##" | grep -v "^$" | head -3 | tr '\n' ' ')
else
  DX_SUMMARY="null"
fi

# 自省结论 (Phase 3.5)
INTROSPECTION=$(grep -A 20 "## 自省备注\|## Phase 3.5" "$LATEST_PLAN" 2>/dev/null | head -20)
if [ -n "$INTROSPECTION" ]; then
  INTROSPECTION_SUMMARY=$(echo "$INTROSPECTION" | grep -v "^##" | grep -v "^$" | head -3 | tr '\n' ' ')
else
  INTROSPECTION_SUMMARY="null"
fi
```

### 步骤 8: 采集决策记录

```bash
# 机械决策
MECHANICAL_DECISIONS=$(grep -E "机械决策|自动处理" "$LATEST_PLAN" 2>/dev/null | head -10)

# 品味决策
TASTE_DECISIONS=$(grep -A 5 "品味决策" "$LATEST_PLAN" 2>/dev/null | head -20)

# 用户挑战
USER_CHALLENGES=$(grep -A 5 "用户挑战" "$LATEST_PLAN" 2>/dev/null | head -20)
```

### 步骤 9: 确定当前阶段

根据已采集的信息推断当前所在的阶段:

```
阶段判断逻辑:
- 如果 LATEST_PLAN == null         → "未开始 (Phase 0)"
- 如果 CEO_SUMMARY == null         → "Phase 1 完成 (Plan 已生成)"
- 如果 DESIGN_SUMMARY == null      → "Phase 2 完成 (CEO Review 已通过)"
- 如果 ARCH_CONCLUSION == null     → "Phase 3 完成 (Design Review 已通过)"
- 如果 DX_SUMMARY == null          → "Phase 4 完成 (Eng Review 已通过)"
- 如果有 "审批摘要" 关键词          → "Phase 5 完成 (最终审批前)"
- 如果有 "审批通过" 关键词          → "已批准 (待执行)"
```

### 步骤 10: 采集待处理事项

```bash
# 未完成的 plan 任务
PENDING_TASKS=$(grep "^### Task" "$LATEST_PLAN" 2>/dev/null | wc -l)
COMPLETED_TASKS=$(grep -E "^\- \[x\]" "$LATEST_PLAN" 2>/dev/null | wc -l)

# 产出待处理事项列表
PENDING_ACTIONS=()
if [ -n "$LATEST_PLAN" ] && [ "$CEO_SUMMARY" = "null" ]; then
  PENDING_ACTIONS+=("CEO Review 未完成")
fi
if [ -n "$LATEST_PLAN" ] && [ "$ARCH_CONCLUSION" = "null" ]; then
  PENDING_ACTIONS+=("Eng Review 未完成")
fi
if [ -n "$LATEST_PLAN" ] && [ "$DX_SUMMARY" = "null" ]; then
  PENDING_ACTIONS+=("DX Review 未完成")
fi
if [ -n "$LATEST_PLAN" ] && [ "$COMPLETED_TASKS" -lt "$PENDING_TASKS" ]; then
  REMAINING=$((PENDING_TASKS - COMPLETED_TASKS))
  PENDING_ACTIONS+=("${REMAINING} 个 Plan 任务未完成")
fi
```

### 步骤 11: 写入检查点文件

将所有采集的数据组装为 JSON 并写入文件:

```json
{
  "timestamp": "<ISO_TIMESTAMP>",
  "branch": "<CURRENT_BRANCH>",
  "phase": "<推断的当前阶段>",
  "project": {
    "root": "<PROJECT_ROOT>",
    "tech_stack": {
      "ui": "Compose / XML Views / 混用",
      "async": "Coroutines / RxJava / 无",
      "di": "Hilt / Koin / 无",
      "network": "Retrofit / Ktor / 无",
      "database": "Room / SQLDelight / 无",
      "image_loading": "Coil / Glide / 无",
      "navigation": "Navigation Compose / Navigation Component / 无"
    },
    "architecture": "<INFERRED_ARCH>",
    "build_config": {
      "min_sdk": "<MIN_SDK>",
      "target_sdk": "<TARGET_SDK>",
      "compile_sdk": "<COMPILE_SDK>",
      "modules": <MODULES JSON 数组>  // 从换行符分隔字符串转为数组
    }
  },
  "plan": {
    "file": "<LATEST_PLAN 或 null>",
    "title": "<PLAN_TITLE 或 null>",
    "task_count": <TASK_COUNT>,
    "slug": "<PLAN_SLUG 或 null>",
    "design_spec": "<DESIGN_SPEC_PATH>"
  },
  "reviews": {
    "ceo": "<CEO_SUMMARY>",
    "design": "<DESIGN_SUMMARY>",
    "eng": {
      "architecture": "<ARCH_CONCLUSION>",
      "gradle_manifest": "<GRADLE_CONCLUSION>",
      "lifecycle": "<LIFECYCLE_CONCLUSION>",
      "testing": "<TEST_CONCLUSION>",
      "performance": "<PERF_CONCLUSION>"
    },
    "dx": "<DX_SUMMARY>",
    "introspection": "<INTROSPECTION_SUMMARY>"
  },
  "decisions": {
    "mechanical": [ "<MECHANICAL_DECISIONS 行列表>" ],
    "taste": [ "<TASTE_DECISIONS 行列表>" ],
    "user_challenge": [ "<USER_CHALLENGES 行列表>" ]
  },
  "pending_actions": [ "<PENDING_ACTIONS 列表>" ]
}
```

写入命令:

```bash
CHECKPOINT_FILE="$CHECKPOINT_DIR/checkpoint-${TIMESTAMP}.json"
# 使用 Write 工具写入 JSON (保持格式化)
```

### 步骤 12: 清理旧检查点

```bash
# 列出所有检查点文件，按时间倒序排序
ALL_CHECKPOINTS=$(ls -1 "$CHECKPOINT_DIR"/checkpoint-*.json 2>/dev/null | sort -r)
COUNT=$(echo "$ALL_CHECKPOINTS" | wc -l)

# 保留最近 10 个，删除其余
if [ "$COUNT" -gt 10 ]; then
  echo "$ALL_CHECKPOINTS" | tail -n +11 | while read old_file; do
    rm -f "$old_file"
  done
fi
```

### 步骤 13: 输出保存结果

```
=== 检查点已保存 ===

文件:     .claude/android-checkpoint/checkpoint-<TIMESTAMP>.json
分支:     <CURRENT_BRANCH>
阶段:     <推断的当前阶段>
Plan:     <PLAN_TITLE 或 "无">

技术栈:   <简短技术栈描述>
架构:     <INFERRED_ARCH>

保留检查点: <当前数量>/10
```

---

## Phase 2: 恢复 (restore 模式)

### 步骤 1: 列出可用检查点

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
CHECKPOINT_DIR="$PROJECT_ROOT/.claude/android-checkpoint"

# 列出所有检查点文件
ALL_CHECKPOINTS=$(ls -1 "$CHECKPOINT_DIR"/checkpoint-*.json 2>/dev/null | sort -r)
COUNT=$(echo "$ALL_CHECKPOINTS" | wc -l)

if [ "$COUNT" -eq 0 ]; then
  echo "未找到检查点。请先使用 /android-checkpoint save 保存状态。"
  exit 0
fi
```

### 步骤 2: 展示检查点列表

如果用户没有指定 `<index>` 参数，展示列表供选择:

```
=== 可用检查点 ===

#  | 时间                | 分支                  | 阶段                       | Plan
---|---------------------|----------------------|---------------------------|------------------
1  | 2026-04-10 16:05:45 | plan/auth-login-flow  | Phase 4 完成 (Eng Review)  | Auth Login Flow
2  | 2026-04-10 14:30:22 | plan/auth-login-flow  | Phase 1 完成 (Plan 已生成) | Auth Login Flow
3  | 2026-04-09 11:20:15 | main                  | 未开始                     | 无

请输入要恢复的检查点编号 (默认 1):
```

**如果用户指定了 `<index>` 参数:** 直接使用对应编号的检查点文件，跳过选择。

### 步骤 3: 读取并解析检查点文件

使用 Read 工具读取选定的检查点 JSON 文件。

### 步骤 4: 输出恢复上下文

按照以下格式输出完整的恢复上下文，让用户 (和后续 skill) 快速了解状态:

```
╔═══════════════════════════════════════════════════════════════════╗
║                    检查点已恢复                                  ║
╠═══════════════════════════════════════════════════════════════════╣
║  保存时间: <timestamp>                                          ║
║  分支:     <branch>                                             ║
║  阶段:     <phase>                                              ║
╚═══════════════════════════════════════════════════════════════════╝

=== 项目技术栈 ===
UI:           <ui>
异步:         <async>
DI:           <di>
网络:         <network>
数据库:       <database>
图片:         <image_loading>
导航:         <navigation>

=== 项目架构 ===
推断架构:     <architecture>
minSdk:       <min_sdk> | targetSdk: <target_sdk> | compileSdk: <compile_sdk>
模块:         <modules>

=== Plan 信息 ===
标题:         <plan_title>
文件:         <plan_file>
任务数:       <task_count> (<completed_count> 已完成)
Design Spec:  <design_spec 或 "无">

=== 审查进度 ===
Phase 2 CEO Review:     <ceo 结论或 "未完成">
Phase 3 Design Review:  <design 结论或 "未完成">
Phase 4 Eng Review:
  - 架构一致性:         <architecture 结论或 "未完成">
  - Gradle/Manifest:    <gradle_manifest 结论或 "未完成">
  - 生命周期安全:       <lifecycle 结论或 "未完成">
  - 测试覆盖:           <testing 结论或 "未完成">
  - 性能/失败模式:      <performance 结论或 "未完成">
Phase 5 DX Review:      <dx 结论或 "未完成">
Phase 3.5 自省:         <introspection 结论或 "未完成">

=== 决策记录 ===
机械决策: <数量> 项
品味决策: <数量> 项
用户挑战: <数量> 项

=== 待处理事项 ===
1. <pending_action_1>
2. <pending_action_2>
...

=== 建议继续 ===
从 <phase> 继续。
运行 /android-autoplan review <plan_file> 可恢复审查流程。
```

### 步骤 5: 读取并输出决策详情

如果检查点中有决策记录，输出详细信息:

```
=== 决策详情 ===

--- 机械决策 ---
1. <mechanical_decision_1>
2. <mechanical_decision_2>
...

--- 品味决策 ---
1. <taste_decision_1>
2. <taste_decision_2>
...

--- 用户挑战 ---
1. <user_challenge_1>
2. <user_challenge_2>
...
```

---

## Phase 3: 状态展示 (status 模式)

### 步骤 1: 查找检查点

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
CHECKPOINT_DIR="$PROJECT_ROOT/.claude/android-checkpoint"

ALL_CHECKPOINTS=$(ls -1 "$CHECKPOINT_DIR"/checkpoint-*.json 2>/dev/null | sort -r)
COUNT=$(echo "$ALL_CHECKPOINTS" | wc -l)

if [ "$COUNT" -eq 0 ]; then
  echo "未找到检查点。请先使用 /android-checkpoint save 保存状态。"
  exit 0
fi
```

### 步骤 2: 输出检查点列表

读取每个检查点文件，提取关键字段并展示:

```
=== 检查点列表 ===

#  | 时间                | 分支                  | 阶段                       | Plan
---|---------------------|----------------------|---------------------------|------------------
1  | 2026-04-10 16:05:45 | plan/auth-login-flow  | Phase 4 完成 (Eng Review)  | Auth Login Flow
2  | 2026-04-10 14:30:22 | plan/auth-login-flow  | Phase 1 完成 (Plan 已生成) | Auth Login Flow
3  | 2026-04-09 11:20:15 | main                  | 未开始                     | 无

共 <COUNT> 个检查点 (最多保留 10 个)

使用 /android-checkpoint restore <编号> 恢复指定检查点
```

---

## 自动保存时机 (与 autoplan 集成)

当 android-autoplan 执行时，在以下关键节点自动触发检查点保存:

### 自动保存节点

| 节点 | 触发条件 | 自动保存内容 |
|------|----------|-------------|
| Phase 1 完成后 | Plan 初版生成完毕 | 包含技术栈、架构、plan 文件路径 |
| Phase 2 完成后 | CEO Review 通过 | 追加 CEO 审查结论 |
| Phase 4 完成后 | Eng Review 完成 | 追加所有 Eng 审查维度结论 |
| 最终审批前 | 所有审查完成 | 完整状态 (含品味决策、用户挑战) |

### autoplan 中的集成提示

在 android-autoplan 的 SKILL.md 中，每个关键节点完成后添加:

```
[检查点] 当前阶段已完成。建议运行 /android-checkpoint save 保存进度。
```

autoplan 在以下位置插入此提示:
- Phase 1 步骤 5 (Plan 初版输出后)
- Phase 2 步骤 4 (CEO Review 产出后)
- Phase 4 步骤 6 (Eng Review 汇总后)
- 最终审批摘要展示前

### 自动保存的实现方式

自动保存不是由本 skill 主动触发的 (skill 无法监听其他 skill 的状态)。
而是在 android-autoplan 的上述节点，以注释提示的形式提醒用户手动保存。
用户看到提示后，可随时运行 `/android-checkpoint save`。

---

## 检查点 JSON Schema

完整的检查点 JSON 结构定义:

```jsonc
{
  // 元信息
  "timestamp": "2026-04-10T14:30:22Z",        // ISO-8601 UTC 时间戳
  "branch": "plan/auth-login-flow",             // 保存时的 git 分支
  "phase": "Phase 4 完成 (Eng Review)",         // 当前所在阶段描述

  // 项目信息
  "project": {
    "root": "/path/to/project",                 // 项目根目录 (绝对路径)
    "tech_stack": {
      "ui": "Compose",                          // UI 框架: Compose / XML Views / 混用
      "async": "Coroutines",                    // 异步: Coroutines / RxJava / 无
      "di": "Hilt",                             // DI: Hilt / Koin / 无
      "network": "Retrofit",                    // 网络: Retrofit / Ktor / 无
      "database": "Room",                       // 数据库: Room / SQLDelight / 无
      "image_loading": "Coil",                  // 图片: Coil / Glide / 无
      "navigation": "Navigation Compose"        // 导航: Navigation Compose / Navigation Component / 无
    },
    "architecture": "MVVM",                     // 架构推断: MVVM / Clean Architecture / MVI / 未检测到
    "build_config": {
      "min_sdk": "24",
      "target_sdk": "34",
      "compile_sdk": "34",
      "modules": ["app", "feature:login", "core:data", "core:common"]
    }
  },

  // Plan 信息
  "plan": {
    "file": "docs/plans/2026-04-10-auth-login-flow.md",  // plan 文件路径 (相对项目根)
    "title": "Auth Login Flow",                           // plan 标题
    "task_count": 8,                                      // 任务总数
    "slug": "2026-04-10-auth-login-flow",                 // plan slug
    "design_spec": "docs/plans/2026-04-10-auth-login-flow-design-spec.md"  // design-spec 路径或 null
  },

  // 审查结论
  "reviews": {
    "ceo": "范围确认，砍掉了社交登录，保留核心邮箱登录流程",  // Phase 2 结论摘要或 null
    "design": "Design spec 已生成: docs/plans/...-design-spec.md",  // Phase 3 结论或 null
    "eng": {
      "architecture": "通过，新代码遵循项目 MVVM 架构",      // 架构审查结论或 null
      "gradle_manifest": "通过，ProGuard 规则已覆盖",        // Gradle/Manifest 审查结论或 null
      "lifecycle": "需调整，ViewModel 中发现 Context 引用",   // 生命周期审查结论或 null
      "testing": "通过，覆盖了核心路径",                      // 测试审查结论或 null
      "performance": "建议改进，列表建议使用 key 参数"         // 性能审查结论或 null
    },
    "dx": "通过，命名规范一致",                              // Phase 5 结论或 null
    "introspection": "未发现显著盲点"                        // Phase 3.5 结论或 null
  },

  // 决策记录
  "decisions": {
    "mechanical": [
      "DI 框架: 跟随项目已有 Hilt",
      "序列化: 跟随项目已有 kotlinx.serialization",
      "构建脚本: 跟随项目已有 .kts 格式"
    ],
    "taste": [
      "State 管理: 选择 StateFlow (项目已有 Coroutines 基础设施)",
      "错误处理: 选择 sealed class Result"
    ],
    "user_challenge": [
      "社交登录 API 未提供官方 SDK，建议延后"
    ]
  },

  // 待处理事项
  "pending_actions": [
    "Phase 4 生命周期安全审查发现 1 个需调整项",
    "DX Review 未完成",
    "最终审批未完成"
  ]
}
```

---

## 与其他 Skill 的衔接

### 上游: android-autoplan

android-autoplan 在关键节点提示用户保存检查点。
保存的检查点可在新 session 中恢复后，继续执行 `/android-autoplan review <plan-file>`。

### 下游: android-worktree-runner

恢复检查点后，如果 plan 已通过最终审批，
可直接调用 `/android-worktree-runner import <plan-file>` 执行。

### 与其他 skill 的关系

| Skill | 关系 | 说明 |
|-------|------|------|
| android-autoplan | 上游 | 产出 plan，在关键节点提示保存检查点 |
| android-worktree-runner | 下游 | 恢复已审批的 plan 后，执行 plan |
| android-design-review | 参考 | 恢复时包含 design-spec 路径引用 |
| android-qa | 参考 | 恢复时包含已完成的审查信息 |

### 恢复后的衔接流程

```
/android-checkpoint restore
  |
  v
输出完整会话上下文
  |
  +---> 阶段未完成 → /android-autoplan review <plan-file>  (继续审查)
  |
  +---> 已审批     → /android-worktree-runner import <plan-file>  (执行 plan)
  |
  +---> 执行中     → /android-worktree-runner  (继续执行)
  |
  +---> 执行完毕   → /android-qa  (QA 测试)
```

---

## 异常情况处理

| 场景 | 处理方式 |
|------|----------|
| 不在 git 仓库中 | 报错: "android-checkpoint 需要 git 仓库" |
| 无可用检查点 | 提示: "未找到检查点，请先使用 /android-checkpoint save" |
| 检查点 JSON 格式损坏 | 报错并跳过该检查点，继续处理其他可用检查点 |
| Plan 文件被删除 | 标记 plan.file 为 null，其余信息正常恢复 |
| Design spec 被删除 | 标记 plan.design_spec 为 null，其余信息正常恢复 |
| .gitignore 不存在 | 自动创建 .gitignore 并添加检查点目录 |
| 检查点目录被手动删除 | 下次 save 时自动重建 |
| 恢复时分支已切换 | 警告: "检查点保存于分支 X，当前在分支 Y"，询问是否继续 |
| 恢复时项目根目录不同 | 警告: "检查点保存于不同项目路径"，询问是否继续 |

---

## 文件结构

```
项目根目录/
├── .claude/
│   ├── android-checkpoint/
│   │   ├── checkpoint-20260410-143022.json     ← 检查点文件
│   │   ├── checkpoint-20260410-160545.json     ← 检查点文件
│   │   └── ...                                  ← 最多保留 10 个
│   └── skills/
│       └── android-checkpoint/
│           └── SKILL.md                        ← 本 skill
├── .gitignore                                  ← 自动添加 .claude/android-checkpoint/
└── ...
```
