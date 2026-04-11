---
name: android-status
description: |
  Android 全局状态仪表盘。聚合 git、worktree runner、checkpoint、PR、
  review、plan、learnings、build 等数据源，输出单一 ASCII dashboard。
  适用于随时查看项目整体状态、决策下一步操作。
voice-triggers:
  - "状态"
  - "全局状态"
  - "仪表盘"
  - "dashboard"
  - "当前状态"
---

# Android Status Dashboard

## 概述

聚合所有 Android skill 的状态数据，输出单一 ASCII 仪表盘。
帮助开发者快速了解项目整体进展，决策下一步操作。

**启动时声明:** "我正在使用 android-status skill。"

**零外部依赖:** 仅使用 Claude Code 原生工具 (Bash、Read、Grep、Glob)。
所有数据通过 bash 命令采集 (git、gh、ls、cat、python)。

## 调用方式

```bash
/android-status              # 显示完整仪表盘
/android-status refresh      # 强制刷新 (跳过缓存)
```

---

## Phase 0: 数据采集 (并行执行)

使用 Bash 工具并行执行以下所有数据采集命令。每个命令独立运行，任一命令失败不影响其他。

### 0.1 Git 状态

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -n "$PROJECT_ROOT" ]; then
  BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
  AHEAD=$(git rev-list --count "@{upstream}..HEAD" 2>/dev/null || echo "0")
  BEHIND=$(git rev-list --count "HEAD..@{upstream}" 2>/dev/null || echo "0")
  STATUS=$(git status --porcelain 2>/dev/null | head -10)
  MODIFIED=$(git status --porcelain 2>/dev/null | grep -c "^ M" || echo "0")
  UNTRACKED=$(git status --porcelain 2>/dev/null | grep -c "^??" || echo "0")
  STAGED=$(git status --porcelain 2>/dev/null | grep -c "^[MADRC]" || echo "0")
  RECENT=$(git log --oneline -5 2>/dev/null)
  echo "BRANCH:$BRANCH"
  echo "AHEAD:$AHEAD"
  echo "BEHIND:$BEHIND"
  echo "MODIFIED:$MODIFIED"
  echo "UNTRACKED:$UNTRACKED"
  echo "STAGED:$STAGED"
  echo "---COMMITS---"
  echo "$RECENT"
else
  echo "GIT:N/A"
fi
```

### 0.2 Worktree Runner 状态

```bash
MAIN_WORKTREE=$(git worktree list 2>/dev/null | head -1 | awk '{print $1}')
TASKS_FILE="$MAIN_WORKTREE/.claude/android-worktree-runner/tasks.json"
if [ -f "$TASKS_FILE" ]; then
  # 读取 tasks.json 摘要
  PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
  if [ -n "$PYTHON" ]; then
    "$PYTHON" -c "
import json, sys
with open('$TASKS_FILE') as f:
    data = json.load(f)
plans = data.get('plans', {})
total_plans = len(plans)
in_progress = sum(1 for p in plans.values() if p.get('status') == 'in-progress')
completed_plans = sum(1 for p in plans.values() if p.get('status') == 'completed')
total_tasks = 0
done_tasks = 0
current_task = None
blocked_count = 0
for pid, plan in plans.items():
    tasks = plan.get('tasks', [])
    total_tasks += len(tasks)
    for t in tasks:
        if t.get('status') == 'completed':
            done_tasks += 1
        elif t.get('status') == 'in-progress' and current_task is None:
            current_task = t.get('title', 'unknown')
    if plan.get('status') == 'in-progress' and current_task is None:
        # 找 pending 的第一个作为当前
        for t in tasks:
            if t.get('status') == 'pending':
                current_task = t.get('title', 'unknown')
                break

# 获取进行中 plan 的信息
active_plan_title = None
active_plan_branch = None
active_plan_path = None
for pid, plan in plans.items():
    if plan.get('status') == 'in-progress':
        active_plan_title = plan.get('title', '')
        wt = plan.get('worktree', {})
        active_plan_branch = wt.get('branch', '')
        active_plan_path = wt.get('path', '')
        break

print(f'PLANS_TOTAL:{total_plans}')
print(f'PLANS_ACTIVE:{in_progress}')
print(f'PLANS_COMPLETED:{completed_plans}')
print(f'TASKS_DONE:{done_tasks}/{total_tasks}')
print(f'CURRENT_TASK:{current_task or \"none\"}')
print(f'ACTIVE_PLAN:{active_plan_title or \"none\"}')
print(f'ACTIVE_BRANCH:{active_plan_branch or \"none\"}')
print(f'ACTIVE_PATH:{active_plan_path or \"none\"}')
" 2>/dev/null || echo "TASKS:PARSE_ERROR"
  else
    echo "TASKS:NO_PYTHON"
  fi
else
  echo "TASKS:N/A"
fi
```

### 0.3 Checkpoint 状态

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
CHECKPOINT_DIR="$PROJECT_ROOT/.claude/android-checkpoint"
if [ -d "$CHECKPOINT_DIR" ]; then
  COUNT=$(ls -1 "$CHECKPOINT_DIR"/checkpoint-*.json 2>/dev/null | wc -l | tr -d ' ')
  if [ "$COUNT" -gt 0 ]; then
    echo "CHECKPOINT_COUNT:$COUNT"
    echo "---CHECKPOINTS---"
    ls -1t "$CHECKPOINT_DIR"/checkpoint-*.json 2>/dev/null | head -5 | while read f; do
      basename "$f"
    done
  else
    echo "CHECKPOINT_COUNT:0"
  fi
else
  echo "CHECKPOINTS:N/A"
fi
```

### 0.4 Open Pull Requests

```bash
if command -v gh >/dev/null 2>&1; then
  gh pr list --state open --limit 5 --json number,title,headRefName,statusCheckRollup 2>/dev/null | \
    (command -v python3 2>/dev/null || command -v python 2>/dev/null) -c "
import json, sys
try:
    data = json.load(sys.stdin)
    if not data:
        print('PRS:0')
    else:
        print(f'PRS:{len(data)}')
        for pr in data:
            num = pr.get('number', '?')
            title = pr.get('title', '?')[:50]
            branch = pr.get('headRefName', '?')
            checks = pr.get('statusCheckRollup', [])
            passing = sum(1 for c in checks if c.get('status') == 'COMPLETED' and c.get('conclusion') == 'SUCCESS')
            total = len(checks)
            check_str = f'{passing}/{total} checks' if total > 0 else 'no checks'
            print(f'PR:{num}|{branch}|{title}|{check_str}')
except:
    print('PRS:PARSE_ERROR')
" 2>/dev/null || echo "PRS:N/A"
else
  echo "PRS:NO_GH"
fi
```

### 0.5 Review 报告

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
REVIEWS_DIR="$PROJECT_ROOT/docs/reviews"
if [ -d "$REVIEWS_DIR" ]; then
  COUNT=$(ls -1 "$REVIEWS_DIR"/*.md 2>/dev/null | wc -l | tr -d ' ')
  if [ "$COUNT" -gt 0 ]; then
    echo "REVIEWS_COUNT:$COUNT"
    echo "---REVIEWS---"
    ls -1t "$REVIEWS_DIR"/*.md 2>/dev/null | head -5 | while read f; do
      basename "$f"
    done
  else
    echo "REVIEWS_COUNT:0"
  fi
else
  echo "REVIEWS:N/A"
fi
```

### 0.6 Plan 文件

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
PLANS_DIR="$PROJECT_ROOT/docs/plans"
if [ -d "$PLANS_DIR" ]; then
  COUNT=$(ls -1 "$PLANS_DIR"/*.md 2>/dev/null | wc -l | tr -d ' ')
  if [ "$COUNT" -gt 0 ]; then
    echo "PLANS_COUNT:$COUNT"
    echo "---PLANS---"
    ls -1t "$PLANS_DIR"/*.md 2>/dev/null | head -5 | while read f; do
      basename "$f"
    done
  else
    echo "PLANS_COUNT:0"
  fi
else
  echo "PLANS:N/A"
fi
```

### 0.7 Learnings 统计

```bash
_R="$(git worktree list | head -1 | awk '{print $1}')"
SHARED_BIN="$_R/.claude/skills/android-shared/bin"
[ ! -d "$SHARED_BIN" ] && SHARED_BIN="$HOME/.claude/skills/android-shared/bin"
LEARN_BIN="$SHARED_BIN/android-learnings-search"
if [ -f "$LEARN_BIN" ]; then
  # 获取总数
  TOTAL=$(bash "$LEARN_BIN" --limit 1000 2>/dev/null | head -1 | grep -oE '[0-9]+' || echo "0")

  # 获取本周新增
  PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
  WEEK_NEW="0"
  AVG_CONF="0"
  if [ -n "$PYTHON" ]; then
    SLUG=$(git remote get-url origin 2>/dev/null | sed 's|.*/||;s|\.git$||;s|/$||' | tail -1)
    [ -z "$SLUG" ] && SLUG=$(basename "$(pwd)")
    LEARN_FILE="$HOME/.android-skills/projects/$SLUG/learnings.jsonl"
    if [ -f "$LEARN_FILE" ]; then
      STATS=$("$PYTHON" -c "
import json
from datetime import datetime, timedelta
now = datetime.utcnow()
week_ago = now - timedelta(days=7)
count = 0
conf_sum = 0
conf_n = 0
with open('$LEARN_FILE') as f:
    for line in f:
        line = line.strip()
        if not line: continue
        try:
            e = json.loads(line)
            ts = e.get('ts', '')
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace('Z','+00:00'))
                    if dt > week_ago:
                        count += 1
                except: pass
            conf = e.get('confidence', 5)
            conf_sum += conf
            conf_n += 1
        except: pass
print(f'{count}|{round(conf_sum/conf_n, 1) if conf_n > 0 else 0}')
" 2>/dev/null)
      WEEK_NEW=$(echo "$STATS" | cut -d'|' -f1)
      AVG_CONF=$(echo "$STATS" | cut -d'|' -f2)
    fi
  fi
  echo "LEARNINGS_TOTAL:$TOTAL"
  echo "LEARNINGS_WEEK:$WEEK_NEW"
  echo "LEARNINGS_AVG_CONF:$AVG_CONF"
else
  echo "LEARNINGS:N/A"
fi
```

### 0.8 Build 状态

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -n "$PROJECT_ROOT" ]; then
  # 检查 Gradle 存在
  if [ -f "$PROJECT_ROOT/gradlew" ] || [ -f "$PROJECT_ROOT/gradlew.bat" ]; then
    echo "GRADLE:EXISTS"

    # 检测 Kotlin 版本
    KOTLIN_VER=$(grep -rE "kotlin.*version\s*[=:]|kotlinVersion" \
      "$PROJECT_ROOT/build.gradle" "$PROJECT_ROOT/build.gradle.kts" \
      "$PROJECT_ROOT/gradle/libs.versions.toml" 2>/dev/null | \
      head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    echo "KOTLIN:${KOTLIN_VER:-unknown}"

    # 检测 Compose
    COMPOSE="disabled"
    grep -rq "androidx.compose" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null && COMPOSE="enabled"
    grep -rlq "@Composable" "$PROJECT_ROOT/app/src" 2>/dev/null && COMPOSE="enabled"
    echo "COMPOSE:$COMPOSE"
  else
    echo "GRADLE:N/A"
    echo "KOTLIN:N/A"
    echo "COMPOSE:N/A"
  fi
else
  echo "BUILD:N/A"
fi
```

---

## Phase 1: 渲染仪表盘

将 Phase 0 采集的数据渲染为以下 ASCII 仪表盘格式。

**关键规则:**
- 每行不超过 78 个字符 (兼容 80 列终端)
- 不可用的数据源显示 "N/A"
- 时间信息尽量人性化 (如 "2h ago", "1d ago")
- 使用中文输出

### 仪表盘模板

```
══════════════════════════════════════════════════════════════
            ANDROID SKILLS STATUS DASHBOARD
══════════════════════════════════════════════════════════════

┌─ GIT ─────────────────────────────────────────────────────┐
│ Branch: <branch>  (<N> commits ahead, <N> behind)        │
│ Status: <N> modified, <N> staged, <N> untracked          │
│ Recent:                                                    │
│   <hash> <message>                                        │
│   <hash> <message>                                        │
│   ...                                                     │
└────────────────────────────────────────────────────────────┘

┌─ WORKTREE RUNNER ─────────────────────────────────────────┐
│ Status: <ACTIVE/IDLE>  Task <done>/<total>                │
│ Current: [IN_PROGRESS] <task title>                       │
│ Plan:    <plan title> (branch: <branch>)                  │
│ Path:    <worktree path>                                  │
└────────────────────────────────────────────────────────────┘

┌─ PLANS ───────────────────────────────────────────────────┐
│ <plan file 1>  (<date>)                                   │
│ <plan file 2>  (<date>)                                   │
│ ...                                                       │
│ 共 <N> 个 plan 文件                                       │
└────────────────────────────────────────────────────────────┘

┌─ REVIEWS ─────────────────────────────────────────────────┐
│ <review file 1>  (<date>)                                 │
│ <review file 2>  (<date>)                                 │
│ ...                                                       │
│ 共 <N> 个 review 文件                                     │
└────────────────────────────────────────────────────────────┘

┌─ CHECKPOINTS ─────────────────────────────────────────────┐
│ <checkpoint file 1>  (<relative time>)                    │
│ <checkpoint file 2>  (<relative time>)                    │
│ ...                                                       │
│ 共 <N> 个检查点 (最多保留 10 个)                           │
└────────────────────────────────────────────────────────────┘

┌─ PULL REQUESTS ───────────────────────────────────────────┐
│ #<N>  <branch>  <title>  (<check status>)                │
│ ...                                                       │
│ 共 <N> 个 open PR                                         │
└────────────────────────────────────────────────────────────┘

┌─ LEARNINGS ───────────────────────────────────────────────┐
│ <total> records | <N> new this week | avg confidence <X>/10 │
└────────────────────────────────────────────────────────────┘

┌─ BUILD ───────────────────────────────────────────────────┐
│ Gradle: <EXISTS/N/A> | Kotlin <ver> | Compose: <state>   │
└────────────────────────────────────────────────────────────┘

══════════════════════════════════════════════════════════════
  Recommended next actions:
    → /android-worktree-runner  (continue task execution)
    → /android-code-review      (review current changes)
    ...
══════════════════════════════════════════════════════════════
```

### 渲染规则

1. **文件时间格式化**: 使用 bash 计算文件修改时间与当前时间的差值，输出为:
   - `<1h` — 不到 1 小时
   - `<Nh` — N 小时前
   - `<Nd` — N 天前
   - 否则输出完整日期 `YYYY-MM-DD`

   ```bash
   # 时间格式化辅助函数
   file_age() {
     local file="$1"
     if [ ! -f "$file" ]; then echo "unknown"; return; fi
     local now=$(date +%s)
     local mtime=$(stat -c %Y "$file" 2>/dev/null || stat -f %m "$file" 2>/dev/null)
     local diff=$(( (now - mtime) / 3600 ))
     if [ "$diff" -lt 1 ]; then echo "<1h"
     elif [ "$diff" -lt 24 ]; then echo "${diff}h ago"
     else echo "$((diff / 24))d ago"
     fi
   }
   ```

2. **文本截断**: 文件名或标题超过 40 字符时截断并添加 `...`

3. **空数据处理**: 如果某个 section 没有数据，显示一行 `  (无数据)` 而不是完全省略该 section

---

## Phase 2: 推荐下一步操作

基于 Phase 0 采集的数据，智能推荐下一步操作。按优先级排列，最多显示 3 条。

### 推荐逻辑

按以下优先级顺序检查，匹配到即添加推荐:

| 优先级 | 条件 | 推荐 | 说明 |
|--------|------|------|------|
| 1 | tasks.json 中有 `in-progress` 任务 | `/android-worktree-runner` | 继续执行当前任务 |
| 2 | tasks.json 中有 `pending` 任务 (无 in-progress) | `/android-worktree-runner` | 开始下一个任务 |
| 3 | 有未提交的修改 (modified > 0) 且不在 main/master | `/android-code-review` 或 `/android-ship` | 审查或提交当前改动 |
| 4 | docs/reviews/ 中有 code-review 但无 qa-report | `/android-qa` | 代码已审查但未做 QA |
| 5 | 有 open PR 但 reviews 为空 | `/android-code-review` | PR 需要代码审查 |
| 6 | docs/plans/ 为空 | `/android-autoplan` | 需要先制定 plan |
| 7 | 有 plan 文件但 tasks.json 不存在 | `/android-worktree-runner import` | plan 已就绪，导入执行 |
| 8 | 检查点为空 | `/android-checkpoint save` | 建议保存当前状态 |

### 输出格式

```
══════════════════════════════════════════════════════════════
  Recommended next actions:
    → /android-worktree-runner  (继续执行当前任务)
    → /android-code-review      (审查当前改动)
    → /android-qa               (执行功能验证)
══════════════════════════════════════════════════════════════
```

推荐说明使用中文。

---

## 执行流程

```
/android-status
  |
  v
Phase 0: 并行采集 8 个数据源
  |
  v
Phase 1: 渲染 ASCII 仪表盘
  |
  v
Phase 2: 基于状态推荐下一步操作
```

**性能要求:** 全部完成应在 10 秒内。数据采集命令并行执行，
每个命令单独设置 5 秒超时。

---

## 异常情况处理

| 场景 | 处理方式 |
|------|----------|
| 不在 git 仓库中 | 仅显示 "N/A" for all sections，不报错 |
| tasks.json 损坏 | Worktree Runner section 显示 "PARSE_ERROR" |
| gh 未安装 | PRs section 显示 "N/A (gh CLI not installed)" |
| python 未安装 | Learnings/PRs 显示 "N/A (python not found)" |
| 网络/gh API 超时 | PRs section 显示 "N/A (timeout)" |
| 某个数据源命令超时 | 该 section 显示 "N/A (timeout)"，其余正常 |
| 终端宽度 < 80 列 | 正常输出，用户自行横向滚动 |

---

## 与其他 Skill 的关系

android-status 是一个**只读监控** skill，不修改任何项目状态。

| Skill | 关系 | 数据来源 |
|-------|------|----------|
| android-worktree-runner | 读取 | tasks.json |
| android-checkpoint | 读取 | checkpoint 文件列表 |
| android-code-review | 读取 | docs/reviews/*.md |
| android-autoplan | 读取 | docs/plans/*.md |
| android-learn | 读取 | learnings.jsonl (via search script) |
| android-qa | 读取 | docs/reviews/*-qa-report.md |

---

## 文件结构

```
项目根目录/
├── .claude/
│   └── skills/
│       └── android-status/
│           └── SKILL.md    ← 本 skill (唯一文件)
```

此 skill 不产出任何文件。它是纯只读的聚合视图。
