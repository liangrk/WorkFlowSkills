---
name: android-worktree-runner
description: |
  基于 git worktree 隔离的 Plan 任务执行器。支持串行和波次并行两种执行模式。
  串行模式: 一个 Plan 对应一个 worktree，子任务顺序执行。
  并行模式: 分析任务依赖图，无依赖任务同时在不同 worktree 中执行，按波次推进。
  跟踪 pending/in-progress/completed 三态进度。每次 commit 前执行 Android 验证。
  支持多个 plan/worktree 并行工作。支持 /clear 后恢复。
  适用场景: 执行 plan、跟踪任务进度、管理 worktree 开发工作流。
voice-triggers:
  - "执行任务"
  - "开始计划"
  - "任务运行"
  - "执行计划"
---

# Android Worktree Runner

<!--
  并发保护模式 (Concurrency Protection Pattern)
  =============================================
  tasks.json 是多 worktree 共享的唯一真相源。为防止并发写入导致数据损坏:

  1. **所有 tasks.json 写入必须使用原子写入脚本:**
     bash .claude/skills/android-shared/bin/android-json-atomic <filepath>
     读取 stdin 中的 JSON，验证后通过 temp+rename 原子写入。

  2. **所有读取-修改-写入序列必须加文件锁:**
     bash .claude/skills/android-shared/bin/android-file-lock <lockfile> <command> [args...]
     锁文件: $TASKS_FILE.lock，超时 3 秒，exit code 98 表示获取失败 (应重试)。

  3. **典型写法 (原子写入 + 文件锁):**
     cat "$TASKS_FILE" | python -c "import sys,json; ...修改逻辑..." |
       bash .claude/skills/android-shared/bin/android-file-lock "$TASKS_FILE.lock" \
         bash .claude/skills/android-shared/bin/android-json-atomic "$TASKS_FILE"

  4. **禁止直接使用 Write 工具写入 tasks.json。**
-->

## 概述

一个 Plan = 一个 Worktree。导入 Plan，创建隔离的 worktree，执行任务，
每个任务完成后执行 Android 验证并提交。

**两种执行模式:**
- **串行模式** (默认): 所有任务在同一个 worktree 中按顺序执行。
- **波次并行模式** (可选): 分析任务依赖图，无依赖的任务同时在不同 worktree 中执行，
  按波次 (wave) 推进。依赖全部满足后才进入下一波次。

**启动时声明:** "我正在使用 android-worktree-runner skill。"

## 调用方式

```bash
/android-worktree-runner              # 显示所有 plan 状态，选择操作
/android-worktree-runner <plan-id>    # 直接恢复指定 plan
/android-worktree-runner import       # 强制导入新 plan (扫描发现)
/android-worktree-runner import <plan-file>  # 导入指定 plan 文件
/android-worktree-runner status       # 仅显示状态，不执行操作
```

**参数处理:**
- 带参数 `<plan-id>` 调用时，跳过 Phase 1 的状态展示，直接进入
  该 plan 的 Phase 2 执行阶段。如果 plan-id 匹配 `tasks.json` 中的某个 plan，
  进入其 worktree 并恢复。未找到则显示状态并提示 "未找到 Plan: <参数>"。
- `import <plan-file>` 调用时，跳过 Phase 0 步骤 1 的来源扫描，直接将
  指定的 plan 文件路径作为输入，进入步骤 2 (解析 Plan)。

**`/clear` 后恢复:** 此 skill 在 `/clear` 后可完整恢复。所有状态保存在磁盘上的
`tasks.json` 中，不依赖内存状态。每次调用时，skill 读取 `tasks.json` 作为唯一
真相源。详见下方「恢复保障」章节。

## 存储

所有持久化状态存储在**主项目根目录**的 `.claude/android-worktree-runner/tasks.json` 中
（不在任何 worktree 内部）。

### 从任意上下文定位 tasks.json

此 skill 可能在主 worktree、某个 plan worktree 中、或 `/clear` 之后无任何上下文时被调用。
使用以下方式定位 `tasks.json`:

```bash
# 找到主 worktree（worktree 列表的第一项）
MAIN_WORKTREE=$(git worktree list 2>/dev/null | head -1 | awk '{print $1}')
# 如果不在 git 仓库中，报错退出
if [ -z "$MAIN_WORKTREE" ]; then
  echo "错误: 当前不在 git worktree 中"
  exit 1
fi
TASKS_FILE="$MAIN_WORKTREE/.claude/android-worktree-runner/tasks.json"
```

**关键规则:** `tasks.json` 是唯一的真相源。每次任务状态变更（in-progress、
completed、验证结果、commit hash）必须**立即写入** `tasks.json`。不允许延迟写入，
不允许批量写入。文件必须始终反映磁盘上的最新状态，以确保 `/clear` 恢复生效。

**并发安全:** 所有 `tasks.json` 写入必须使用原子写入脚本
(`android-json-atomic`) 和文件锁 (`android-file-lock`)，禁止直接使用 Write 工具
写入 tasks.json。详见文件顶部的「并发保护模式」注释。

### 数据结构

```json
{
  "version": 3,
  "plans": {
    "plan-<时间戳>": {
      "id": "plan-<时间戳>",
      "title": "Plan 标题",
      "status": "pending | in-progress | completed",
      "execution_mode": "serial | parallel",
      "plan_source": {
        "type": "memory | markdown | gstack-design | superpowers | custom",
        "ref": "文件路径或标识符"
      },
      "worktree": {
        "path": ".claude/worktrees/plan-<时间戳>",
        "branch": "plan/<slug标题>",
        "created_at": "ISO-8601",
        "based_on_commit": "abc1234"
      },
      "tasks": [
        {
          "id": "plan-<时间戳>-1",
          "title": "任务标题",
          "status": "pending | in-progress | completed | blocked | failed",
          "depends_on": [],
          "steps": [
            "步骤 1 描述",
            "步骤 2 描述"
          ],
          "commit": null,
          "verification": {
            "gradle_build": false,
            "lint": false,
            "unit_tests": false
          },
          "tdd": {
            "required": false,
            "executed": false,
            "skipped": false,
            "skip_reason": null,
            "coverage_percent": null,
            "report_path": null,
            "boundary_categories_covered": []
          },
          "timestamps": {
            "created": "ISO-8601",
            "started": null,
            "completed": null
          },
          "worktree": null,
          "branch": null,
          "wave": null
        }
      ],
      "timestamps": {
        "created": "ISO-8601",
        "started": null,
        "completed": null
      }
    }
  }
}
```

**数据结构说明 (新增字段):**

| 字段 | 位置 | 说明 |
|------|------|------|
| `version` | 根级 | 从 2 升级到 3，表示支持并行执行 |
| `execution_mode` | plan 级别 | `"serial"` (默认) 或 `"parallel"` |
| `depends_on` | task 级别 | 该任务依赖的 task ID 列表 (如 `["plan-xxx-1", "plan-xxx-2"]`) |
| `status` | task 级别 | 新增 `"blocked"` 和 `"failed"` 两种状态 |
| `worktree` | task 级别 | 并行模式下该任务的 worktree 路径 (串行模式为 `null`) |
| `branch` | task 级别 | 并行模式下该任务的分支名 (串行模式为 `null`) |
| `wave` | task 级别 | 并行模式下该任务所属的执行波次编号 (串行模式为 `null`) |

**向后兼容:** 如果 `tasks.json` 中 `version` 为 2 或缺失，视为串行模式。
`depends_on` 缺失时默认为空数组 `[]`。

---

## Phase 0: 导入 Plan

当 `tasks.json` 不存在，或用户要求导入时执行。

### 前置: 加载历史学习记录

**前置引导:** 若学习记录为空，先运行预加载:
```bash
bash .claude/skills/android-shared/bin/android-learnings-bootstrap 2>/dev/null || true
```

```bash
# 加载 operational 相关的历史学习记录
LEARNINGS=$(bash .claude/skills/android-shared/bin/android-learnings-search --type technique --limit 5 2>/dev/null || true)
if [ -n "$LEARNINGS" ]; then
  echo "=== 相关学习记录 ==="
  echo "$LEARNINGS"
fi
```

如果找到相关学习记录（如构建顺序依赖、环境配置问题），在执行任务时注意避免这些已知问题。

### 前置: 环境检测

**环境检测优化:** 优先调用共享脚本获取技术栈信息:
```bash
ENV_JSON=$(bash .claude/skills/android-shared/bin/android-detect-env 2>/dev/null || true)
echo "$ENV_JSON"
```
脚本不可用时回退到内联检测命令。

### 步骤 1: 检测可用的 Plan 来源

检查所有来源，收集可用的 plan:

```bash
# 1. Markdown plan 文件
find . -path "*/node_modules" -prune -o -name "*plan*.md" -print 2>/dev/null | head -20

# 2. Superpowers plan
ls docs/plans/*.md 2>/dev/null

# 3. GStack design doc
ls ~/.gstack/projects/*/*-design-*.md 2>/dev/null | head -10

# 4. 当前 git 分支中与 plan 相关的文件
git diff --name-only HEAD~5..HEAD 2>/dev/null | grep -i plan
```

对于 **Claude Code 内存中的 plan**: 检查当前上下文中是否有活跃的 plan 文件路径
（系统消息中会提供 plan 文件路径）。如果找到，将其纳入。

### 步骤 2: 展示来源

使用 AskUserQuestion 展示所有检测到的来源 + "自定义路径" 选项。

> 检测到以下 Plan 来源:
> - A) `docs/plans/2026-04-10-auth.md` (superpowers 格式)
> - B) `~/.gstack/projects/myapp/main-design-20260410.md` (gstack design doc)
> - C) `.claude/plans/current-plan.md` (claude code plan)
> - D) 自定义路径...

### 步骤 3: 解析 Plan 为任务树

读取选中的 plan 文件，按以下规则解析任务:

**Superpowers 格式** (`docs/plans/YYYY-MM-DD-*.md`):
- `### Task N: <标题>` → 顶层任务
- `**Step N:**` 或编号列表 → 任务内的步骤
- 代码块 → 实现参考（存储，暂不执行）
- `@skill-name` 引用 → 在执行阶段标注

**GStack design doc** (`*-design-*.md`):
- `## Recommended Approach` 部分 → 提取实现步骤
- `## Next Steps` 部分 → 提取任务
- `## Approaches Considered` 部分 → 记录选定的方案

**通用 Markdown** (任意 plan 文件):
- `## Task N:` 或 `### Task N:` → 顶层任务
- `#### Task N.M:` 或缩进编号项 → 子任务
- `- [ ]` checkbox → 步骤
- 如果没有结构化标题 → 按 `##` 章节拆分，每个章节作为一个任务

**依赖关系解析 (所有格式通用):**
- 如果任务描述中包含 `depends_on: [task-id]` 或 `依赖: Task N` 标注 → 提取为 `depends_on` 字段
- 如果 plan 由 android-autoplan 生成 → 检查任务间的隐式依赖:
  - 数据模型类通常是其他任务的前提 (如 ViewModel 依赖 Model)
  - API 接口定义通常被 Repository 依赖
  - 基础配置 (Gradle、Manifest) 通常是所有任务的前提
- 如果没有显式依赖标注 → `depends_on` 默认为空数组 `[]`
- **重要:** 依赖关系仅在并行模式下生效，串行模式忽略此字段

**Claude Code 内存中的 plan**:
- 读取上下文中提供的 plan 文件
- 将各主要章节解析为任务（每个主要章节 = 一个任务）

### 步骤 4: 确认解析结果

展示解析后的任务树并请求确认:

```
解析来源: <文件路径>

Plan: <标题>
├── 任务 1: <标题>
│   ├── 步骤 1: <描述>
│   └── 步骤 2: <描述>
├── 任务 2: <标题>
│   └── ...
└── 任务 N: <标题>
```

AskUserQuestion: "导入这 N 个任务?" / "导入前编辑" / "取消"

### 步骤 5: 创建 Worktree 并写入状态

```bash
# 生成 plan ID 和 slug
PLAN_ID="plan-$(date +%Y%m%d-%H%M%S)"
PLAN_SLUG=$(echo "$PLAN_TITLE" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//' | head -c 50)
WORKTREE_PATH=".claude/worktrees/$PLAN_ID"
BRANCH_NAME="plan/$PLAN_SLUG"

# 记录当前 commit 作为基准
BASE_COMMIT=$(git rev-parse --short HEAD)

# 创建 worktree
git worktree add "$WORKTREE_PATH" -b "$BRANCH_NAME"
```

将 `tasks.json` 写入 `$MAIN_WORKTREE/.claude/android-worktree-runner/tasks.json`
（不在 worktree 内部）。路径与上方「存储」章节的解析方式一致。

如果 `tasks.json` 已存在并包含其他 plan，执行合并: 将新 plan 添加到现有的
`plans` 对象中，不覆盖已有数据。

**使用原子写入 (必须):**
```bash
# 首次创建或合并写入 tasks.json
echo '<完整的 tasks.json 内容>' | \
  bash .claude/skills/android-shared/bin/android-file-lock "$TASKS_FILE.lock" \
    bash .claude/skills/android-shared/bin/android-json-atomic "$TASKS_FILE"

# 合并已有数据时，使用 python 读取现有数据并合并:
cat "$TASKS_FILE" | python -c "
import sys, json
existing = json.loads(sys.stdin.read())
new_plan = json.loads('''<新 plan 的 JSON>''')
existing['plans'][new_plan['id']] = new_plan
print(json.dumps(existing, indent=2, ensure_ascii=False))
" | bash .claude/skills/android-shared/bin/android-file-lock "$TASKS_FILE.lock" \
    bash .claude/skills/android-shared/bin/android-json-atomic "$TASKS_FILE"
```

### 步骤 6: 更新 worktree-info.md

创建 worktree 后，**立即更新**项目根目录下的 `worktree-info.md`:

- 如果文件**不存在**: 先执行 `git worktree list` 扫描已有 worktree，
  创建 `worktree-info.md`，将已有 worktree 列入（非 android-worktree-runner
  创建的标记为"外部 worktree"），然后将新 plan 添加到"进行中"部分。
- 如果文件**已存在**: 读取现有内容，在"进行中"部分添加新 plan 的条目。

条目包含: 分支名、worktree 路径、创建时间、基准 commit、任务标题和总数、
当前状态。格式参见上方「Worktree 管理文件」章节。

---

## Phase 0.5: Worktree 健康检查

每次 skill 启动时（无论是否带参数），在进入状态展示之前执行健康检查。

### 步骤 1: 运行健康检查脚本

```bash
bash .claude/skills/android-shared/bin/android-worktree-health
```

此调用**不带** `--cleanup` 参数，仅做报告，不执行任何修改操作。

### 步骤 2: 处理检查结果

**如果输出 "All worktrees healthy"** — 无问题，跳过后续步骤，直接进入 Phase 1。

**如果发现任何问题** — 显示完整输出，然后使用 AskUserQuestion 提供选项:

> Worktree 健康检查发现 N 个问题:
> <粘贴 health 脚本输出>
>
> - A) 自动清理 — 执行全部清理操作
> - B) 手动选择 — 逐项确认要清理的内容
> - C) 跳过 — 继续执行，稍后处理

选 A: 执行以下命令并显示结果:
```bash
bash .claude/skills/android-shared/bin/android-worktree-health --cleanup
```

选 B: 逐项列出问题，每项使用 AskUserQuestion 确认是否清理。
对于确认清理的项，手动执行对应的 git 命令:
- stale worktree: `git worktree remove <path> --force`
- orphan branch: `git branch -d <branch>`
- gradle-leak: `./gradlew --stop`

选 C: 不执行任何操作，直接进入 Phase 1。

### GRADLE_USER_HOME 隔离

当创建新 worktree（Phase 0 步骤 5）时，每个 worktree 应设置独立的
`GRADLE_USER_HOME` 以避免 daemon 冲突:

```bash
# 在 worktree 的 local.properties 或环境变量中设置
export GRADLE_USER_HOME="$WORKTREE_PATH/.gradle"
```

在 Phase 2 步骤 5 执行 Gradle 验证时，确保使用 worktree 的隔离路径:
```bash
GRADLE_USER_HOME="$WORKTREE_PATH/.gradle" ./gradlew assembleDebug
```

将 `.gradle/` 添加到 worktree 的 `.gitignore`（如果存在）。

---

## Phase 0.75: 执行策略分析

当 plan 导入完成（Phase 0 步骤 5）或恢复已有 plan 时，在进入 Phase 1 之前
分析任务依赖关系并确定执行模式。

**跳过条件:** 如果 plan 中所有任务都没有 `depends_on` 字段（或全部为空数组），
且用户未明确要求并行，直接进入串行模式，跳过本阶段。

### 步骤 1: 构建依赖图

读取当前 plan 的 tasks 数组，解析每个任务的 `depends_on` 字段:

```bash
# 从 tasks.json 中提取当前 plan 的依赖关系
cat "$TASKS_FILE" | python -c "
import sys, json
data = json.loads(sys.stdin.read())
plan = data['plans']['<PLAN_ID>']
for task in plan['tasks']:
    deps = task.get('depends_on', [])
    print(f\"{task['id']}: {task['title']} -> depends_on: {deps}\")
"
```

### 步骤 2: 拓扑排序与波次计算

对依赖图进行拓扑排序，计算每个任务所属的执行波次:

```python
# 伪代码 — 实际通过 bash python -c 执行
from collections import deque

def compute_waves(tasks):
    # 构建邻接表和入度表
    task_map = {t['id']: t for t in tasks}
    in_degree = {t['id']: 0 for t in tasks}
    dependents = {t['id']: [] for t in tasks}

    for t in tasks:
        for dep in t.get('depends_on', []):
            if dep in task_map:
                in_degree[t['id']] += 1
                dependents[dep].append(t['id'])

    # BFS 分层计算波次
    waves = []
    queue = deque([tid for tid, deg in in_degree.items() if deg == 0])
    visited = set()

    while queue:
        wave = []
        for _ in range(len(queue)):
            tid = queue.popleft()
            if tid in visited:
                continue
            visited.add(tid)
            wave.append(tid)
            for dep_tid in dependents[tid]:
                in_degree[dep_tid] -= 1
                if in_degree[dep_tid] == 0:
                    queue.append(dep_tid)
        if wave:
            waves.append(wave)

    return waves
```

### 步骤 3: 检测循环依赖

在拓扑排序过程中，如果 `visited` 集合中的任务数少于总任务数，
说明存在循环依赖。

**如果检测到循环依赖:**
- 列出涉及循环依赖的任务
- 将这些任务标记为 `blocked`
- 其余无循环的任务仍可正常执行
- 显示警告并继续

### 步骤 4: 展示分析结果并选择模式

根据波次计算结果，展示分析报告:

```
=== 执行策略分析 ===
Plan: <标题>
总任务数: N
依赖链任务: N 个
可并行任务: N 个
预计执行波次: N 波

波次规划:
  Wave 1: 任务 1 (创建数据模型), 任务 6 (编写单元测试) — 并行
  Wave 2: 任务 2 (创建 API 服务), 任务 3 (创建 Repository) — 并行
  Wave 3: 任务 4 (创建 ViewModel) — 串行
  Wave 4: 任务 5 (创建 UI 界面) — 串行
```

使用 AskUserQuestion 提供选择:

> 选择执行模式:
> - A) 波次并行 (推荐) — 无依赖任务同时执行，预计加速 X%
> - B) 纯串行 — 逐个执行，与当前行为一致

**预估加速比计算:**
```
加速比 = 串行总耗时估算 / 并行总耗时估算
串行总耗时 = 所有任务预估时间之和
并行总耗时 = 各波次中最大任务耗时之和
```

如果只有一个波次（所有任务串行依赖）或只有一个任务，
不需要询问，直接进入串行模式。

### 步骤 5: 写入执行模式

将用户选择的执行模式写入 `tasks.json`:

```bash
cat "$TASKS_FILE" | python -c "
import sys, json
data = json.loads(sys.stdin.read())
plan = data['plans']['<PLAN_ID>']
plan['execution_mode'] = 'parallel'  # 或 'serial'

# 写入每个任务的 wave 编号
for task in plan['tasks']:
    task['wave'] = <计算得到的波次编号>

data['version'] = 3
print(json.dumps(data, indent=2, ensure_ascii=False))
" | bash .claude/skills/android-shared/bin/android-file-lock "$TASKS_FILE.lock" \
    bash .claude/skills/android-shared/bin/android-json-atomic "$TASKS_FILE"
```

**串行模式时:** `wave` 字段为 `null`，行为与 version 2 完全一致。

---

## Phase 1: 状态展示

### 基于参数的直接恢复

如果带 `<plan-id>` 参数调用:
1. 读取 `tasks.json`
2. 查找 `id` 匹配参数，或 `worktree.path` 包含参数的 plan
3. 找到 → 跳过状态展示，直接进入该 plan 的 Phase 2
4. 未找到 → 显示状态并提示 "未找到 Plan: <参数>"

无参数 → 展示完整状态。

### 完整状态展示

读取 `tasks.json` 并展示所有 plan 及其任务进度。

### 展示格式

```
╔══════════════════════════════════════════════════════╗
║              ANDROID WORKTREE RUNNER 状态                    ║
╠══════════════════════════════════════════════════════╣
║                                                       ║
║  ● Plan: 登录流程实现 [进行中]                        ║
║    分支: plan/auth-login-flow                         ║
║    worktree: .claude/worktrees/plan-20260410-001     ║
║    模式: 并行 (3 波次)                                ║
║    ├─ ✓ 任务 1: 配置 Gradle 依赖 (Wave 1)           ║
║    │   commit: a1b2c3d  build✓ lint✓ tests✓         ║
║    ├─ ● 任务 2: 创建登录界面 (Wave 2) [当前]         ║
║    └─ ○ 任务 3: 添加表单验证 (Wave 2)                ║
║                                                       ║
║  ○ Plan: Room 数据库搭建 [待开始]                     ║
║    模式: 串行                                        ║
║    ├─ ○ 任务 1: 定义实体类                            ║
║    └─ ○ 任务 2: 创建 DAO                             ║
║                                                       ║
║  ✓ Plan: 项目初始化 [已完成]                          ║
║    分支: plan/project-init  commit: f5e4d3c          ║
║    3/3 任务已完成                                      ║
║                                                       ║
║  PLAN 总数: 3 | 进行中: 1 | 待开始: 1 | 已完成: 1    ║
║  任务总数: 8 | 已完成: 4 | 剩余: 4                    ║
╚══════════════════════════════════════════════════════╝
```

**状态符号:** `○` 待开始, `●` 进行中, `✓` 已完成

### 操作选择

使用 AskUserQuestion。默认选择最合理的操作:

**存在进行中的 plan 时:**
> 推荐: 继续 "Plan: 登录流程" — 任务 2/3 进行中
> - A) 继续当前 plan (plan/auth-login-flow)
> - B) 开始另一个 plan
> - C) 导入新 plan
> - D) 刷新状态

**无进行中但有待开始的 plan 时:**
> 推荐: 开始 "Plan: Room 数据库搭建" — 0/2 任务完成
> - A) 开始待执行的 plan
> - B) 导入新 plan
> - C) 刷新状态

**所有 plan 都已完成时:**
> 所有 plan 已完成! 接下来做什么?
> - A) 导入新 plan
> - B) 查看已完成的 worktree
> - C) 清理已完成的 worktree

---

## Phase 2: 执行任务

**执行模式路由:** 根据 `execution_mode` 字段选择执行路径:
- `execution_mode` 为 `"serial"` 或缺失 → 进入下方「Phase 2A: 串行执行」
- `execution_mode` 为 `"parallel"` → 进入下方「Phase 2B: 波次并行执行」

---

### Phase 2A: 串行执行

**此为原有执行流程，行为与 version 2 完全一致。**

### Subagent 并发控制

当使用 Agent 工具派发 subagent 执行任务时，**最大并发数严格限制为 4 个**。

- 同时运行的 subagent 不得超过 4 个
- 如果有 4 个 subagent 正在运行，必须等待至少一个完成后再派发新的
- 通过 `run_in_background: true` 参数启动 subagent，在收到完成通知后再启动下一个
- 不得为绕过此限制而使用其他并发机制（如 team、多个 Agent 调用等）

### 步骤 1: 进入 Worktree

```bash
WORKTREE_PATH="<tasks.json 中的路径>"
cd "$WORKTREE_PATH"
```

后续所有工作在此 worktree 中进行。文件读取、写入、编辑和 bash 命令都相对于
worktree 根目录执行。

**重要:** `TASKS_FILE` 变量仍然指向主 worktree 的
`.claude/android-worktree-runner/tasks.json`。所有状态更新都写入这个文件，
不写入当前 worktree 内部的文件。

### 步骤 2: 查找下一个待执行任务

扫描当前 plan 的 tasks 数组，找到第一个 `status` 为 `"pending"` 的任务。

如果没有待执行任务，进入 Phase 3（Plan 完成）。

### 步骤 3: 标记任务为进行中

**立即写入 `tasks.json` (必须使用原子写入 + 文件锁):**
- 设置 task `status` 为 `"in-progress"`
- 设置 task `timestamps.started` 为当前时间

```bash
# 使用原子写入 + 文件锁更新任务状态
cat "$TASKS_FILE" | python -c "
import sys, json, datetime
data = json.loads(sys.stdin.read())
task = [t for p in data['plans'].values() for t in p['tasks'] if t['id'] == '<TASK_ID>'][0]
task['status'] = 'in-progress'
task['timestamps']['started'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
print(json.dumps(data, indent=2, ensure_ascii=False))
" | bash .claude/skills/android-shared/bin/android-file-lock "$TASKS_FILE.lock" \
    bash .claude/skills/android-shared/bin/android-json-atomic "$TASKS_FILE"
```

此写入必须在任何代码变更之前完成。如果 `/clear` 发生在任务执行过程中，
进行中状态已经在磁盘上。

### 步骤 3.5: TDD 分类与执行

在执行任务代码之前，判断该任务是否需要 TDD。

**读取 TDD 要求 (优先级从高到低):**
1. 检查任务步骤中是否包含 `**TDD:** required` 标签 (来自 autoplan)
2. 检查 tasks.json 中该任务的 `tdd.required` 字段
3. 以上都没有: 按关键词和层级分类

**TDD 强制关键词 (任务描述中出现任一即触发):**
`ViewModel`、`Repository`、`UseCase`、`screen`、`feature`、`logic`、`component`、`service`

**TDD 跳过关键词 (任务描述中出现任一即跳过):**
`Gradle`、`Manifest`、`ProGuard`、`migration`、`config`、`setup`、`基础设施`、`测试`

**默认规则:** 无法分类的任务默认走 TDD。宁可多测不可漏测。

**如果 TDD required:**

1. 使用 AskUserQuestion 展示 TDD 确认:
```
任务 "<任务标题>" 需要 TDD。
- A) 执行 TDD + 实现 (推荐)
- B) 跳过 TDD，直接实现 (不推荐)
```

2. 选择 A: 使用 Skill 工具调用 android-tdd:
   - skill: "android-tdd"
   - args: "<任务标题> — 基于步骤: <步骤摘要>"
   - 等待 android-tdd 完成后读取报告

3. 读取 TDD 报告，立即更新 tasks.json:
   - tdd.executed = true
   - tdd.coverage_percent = <报告中的覆盖率数字>
   - tdd.report_path = <报告文件路径>
   - tdd.boundary_categories_covered = <报告中已覆盖的边界类别>

4. 如果 TDD PASS: 检查 TDD 报告中的实现文件列表:
   - 如果 TDD Phase 3 已实现该任务的核心逻辑 → 跳过步骤 4 中已实现的步骤，仅执行 TDD 未覆盖的步骤 (如资源文件、Manifest 配置等)
   - 如果 TDD 仅写了测试未实现 → 正常执行步骤 4
   - 判断方法: 读取 TDD 报告中的 "## 实现文件" 章节，与 plan 步骤中涉及的文件做交集
5. 如果 TDD FAIL: 使用 AskUserQuestion 询问用户如何处理

**如果选择 B (用户跳过 TDD):**
- 立即更新 tasks.json:
  - tdd.skipped = true
  - tdd.skip_reason = "user_override"
- 记录警告: 后续 QA 会检测到 TDD 被跳过，对该任务加强验证
- 继续步骤 4

**如果 TDD not required:**
直接继续步骤 4。

### 步骤 4: 执行任务步骤

对任务 `steps` 数组中的每个步骤:

1. **先读后写。** 如果步骤引用了文件，先读取文件。
2. **严格按指令执行。** Plan 中的步骤是按特定顺序编写的，按顺序执行。
3. **不跳过步骤。** 每个步骤都有其存在的理由。
4. **不添加步骤。** 严格按照 plan 中描述的内容。

**如果步骤被阻塞:**
- 缺少依赖 → 停止，报告问题，等待用户指示
- 构建错误 → 停止，报告错误输出，等待用户指示
- 指令不明确 → 停止，请求澄清
- 测试失败 → 停止，报告失败信息，等待用户指示

**不猜测。不跳过。** 遇到问题停下来询问用户。

### 步骤 5: Android 验证 (commit 前必须执行)

任务中所有步骤完成后，执行验证。

**首先检测是否为 Android 项目:**

```bash
if [ -f "build.gradle" ] || [ -f "build.gradle.kts" ] || \
   [ -f "app/build.gradle" ] || [ -f "app/build.gradle.kts" ]; then
  echo "ANDROID_PROJECT"
else
  echo "NOT_ANDROID"
fi
```

**如果是 Android 项目，按顺序执行以下三项检查。任一项失败则停止。**

```bash
# 1. Gradle 构建
echo "=== Gradle Build ==="
./gradlew assembleDebug 2>&1
BUILD_EXIT=$?

if [ $BUILD_EXIT -ne 0 ]; then
  echo "BUILD FAILED"
  # 报告并询问用户
fi

# 2. Lint 检查 (仅在构建通过后执行)
echo "=== Lint 检查 ==="
./gradlew lintDebug 2>&1
LINT_EXIT=$?

# 3. 单元测试 (仅在 lint 通过后执行)
echo "=== 单元测试 ==="
./gradlew testDebugUnitTest 2>&1
TEST_EXIT=$?
```

**如果任一检查失败:**
- 显示错误输出（最后 50 行）
- AskUserQuestion:
  > Android 验证失败于: [哪个步骤]
  > - A) 修复后重试
  > - B) 跳过此检查并提交
  > - C) 中止任务 (保持进行中状态)

选 A: 回到 Phase 2 步骤 4，由用户指导修复。
选 B: 继续提交，在 verification 中将该检查标记为 `"skipped"`。
选 C: 停止执行，任务保持进行中状态。

**如果不是 Android 项目:**
跳过所有 Android 验证。提示: "未检测到 Android 项目 — 跳过 Gradle/lint/测试验证。"

### 步骤 6: 提交代码

```bash
# 暂存 worktree 中的所有变更
git add -A

# 使用结构化消息提交
TASK_NUM="<任务编号>"
TASK_TITLE="<任务标题>"
PLAN_SLUG="<plan slug>"

git commit -m "$(cat <<EOF
feat($PLAN_SLUG): complete task $TASK_NUM - $TASK_TITLE

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

### 步骤 7: 更新状态 (立即执行 — 恢复机制的关键)

**commit 后立即写入 `tasks.json`:**
- 设置 task `status` 为 `"completed"`
- 设置 task `commit` 为新的 commit hash
- 设置 task `timestamps.completed` 为当前时间
- 更新所有 `verification` 字段为 `true`（或 `"skipped"`）

**同步写入 TDD 状态 (如果适用):**
- 如果 TDD 已执行 (tdd.executed = true): 确保 tdd.coverage_percent、tdd.report_path、tdd.boundary_categories_covered 已写入
- 如果 TDD 被跳过 (tdd.skipped = true): 确保 tdd.skip_reason 已写入
- 如果 TDD 不适用 (tdd.required = false): 保持默认值

此写入不是可选的。它是以下能力的核心机制:
- `/clear` 恢复（状态在上下文清除后仍然存在）
- 跨会话恢复（状态在进程重启后仍然存在）
- 多 worktree 协调（状态在所有 worktree 间共享）

**写入模式 (必须使用原子写入 + 文件锁):**
```bash
# 读取当前状态并更新任务为 completed
TASKS_JSON="$MAIN_WORKTREE/.claude/android-worktree-runner/tasks.json"
COMMIT_HASH=$(git rev-parse --short HEAD)
TASK_ID="<当前任务 ID>"

cat "$TASKS_JSON" | python -c "
import sys, json, datetime
data = json.loads(sys.stdin.read())
task = [t for p in data['plans'].values() for t in p['tasks'] if t['id'] == '${TASK_ID}'][0]
task['status'] = 'completed'
task['commit'] = '${COMMIT_HASH}'
task['timestamps']['completed'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
task['verification'] = {'gradle_build': True, 'lint': True, 'unit_tests': True}
print(json.dumps(data, indent=2, ensure_ascii=False))
" | bash .claude/skills/android-shared/bin/android-file-lock "$TASKS_JSON.lock" \
    bash .claude/skills/android-shared/bin/android-json-atomic "$TASKS_JSON"
```

**注意:** 禁止使用 Write 工具直接写入 `tasks.json`。所有写入必须通过
`android-json-atomic` (原子写入) 和 `android-file-lock` (文件锁) 完成。

**同步更新 `worktree-info.md`:**
- 读取 `worktree-info.md`，更新对应 plan 的任务进度 `(X/N 已完成)`
- 更新状态描述（如"任务 2 执行中" → "任务 3 执行中"）
- 如果这是 plan 的最后一个任务，状态更新为"即将完成"

### 步骤 8: 下一个任务或 Plan 完成

- 当前 plan 中还有待执行任务 → 回到步骤 2
- 没有待执行任务 → 进入 Phase 3

---

### Phase 2B: 波次并行执行

**此为新增的并行执行流程。** 仅在 `execution_mode` 为 `"parallel"` 时使用。

#### 并行执行概览

```
波次 1 (Wave 1): [Task A] [Task F]    ← 同时在不同 worktree 中执行
         ↓ 全部完成后
波次 2 (Wave 2): [Task B] [Task C]    ← 同时执行
         ↓ 全部完成后
波次 3 (Wave 3): [Task D]             ← 单任务，在 plan 主 worktree 中执行
         ↓ 完成后
波次 4 (Wave 4): [Task E]             ← 单任务
         ↓ 全部完成后
最终合并 → Phase 3
```

#### 并发控制

- **最大并发 subagent 数: 4 个**（与串行模式限制一致）
- 如果某波次任务数超过 4，分批执行: 前 4 个先启动，完成一个再启动下一个
- 每个 subagent 独立运行在各自的 worktree 中

#### 步骤 1: 进入 Plan 主 Worktree

```bash
WORKTREE_PATH="<tasks.json 中 plan 的 worktree.path>"
cd "$WORKTREE_PATH"
```

主 worktree 用作并行任务的基准分支和最终合并目标。

#### 步骤 2: 计算当前波次

读取 `tasks.json`，找到当前应执行的波次:

```bash
cat "$TASKS_FILE" | python -c "
import sys, json
data = json.loads(sys.stdin.read())
plan = data['plans']['<PLAN_ID>']
tasks = plan['tasks']

# 找到当前最高已完成波次
max_completed_wave = 0
for t in tasks:
    if t['status'] == 'completed' and t.get('wave'):
        max_completed_wave = max(max_completed_wave, t['wave'])

# 下一波次
next_wave = max_completed_wave + 1

# 收集该波次的任务
wave_tasks = [t for t in tasks if t.get('wave') == next_wave]
print(f'WAVE:{next_wave}')
for t in wave_tasks:
    print(f'TASK:{t[\"id\"]}|{t[\"title\"]}|{t[\"status\"]}')
"
```

如果没有找到下一波次的任务，进入 Phase 3。

#### 步骤 3: 准备波次任务

对当前波次的每个任务:

1. **检查依赖:** 确认所有 `depends_on` 中的任务都已完成
2. **检查前置条件:** 确认任务状态为 `pending`

**如果波次只有 1 个任务:** 回退到串行模式执行该任务（复用 Phase 2A 步骤 3-7）。
在 plan 主 worktree 中执行，无需创建额外 worktree。

**如果波次有多个任务:** 进入并行执行流程。

#### 步骤 4: 为并行任务创建 Worktree

为波次中的每个任务创建独立的 worktree 和分支:

```bash
# 为每个并行任务创建 worktree
TASK_ID="<task-id>"
TASK_SHORT_ID=$(echo "$TASK_ID" | sed 's/.*-//')  # 提取末尾数字
PLAN_SLUG="<plan-slug>"
TASK_WORKTREE_PATH=".claude/worktrees/wr-${PLAN_SLUG}-task-${TASK_SHORT_ID}"
TASK_BRANCH="wr/${PLAN_SLUG}-task-${TASK_SHORT_ID}"

# 从 plan 主分支创建 worktree
git worktree add "$TASK_WORKTREE_PATH" -b "$TASK_BRANCH" "plan/$PLAN_SLUG"
```

**设置隔离的 GRADLE_USER_HOME:**

```bash
export GRADLE_USER_HOME="$TASK_WORKTREE_PATH/.gradle"
```

**写入 tasks.json (使用原子写入 + 文件锁):**

```bash
cat "$TASKS_FILE" | python -c "
import sys, json
data = json.loads(sys.stdin.read())
task = [t for p in data['plans'].values() for t in p['tasks'] if t['id'] == '<TASK_ID>'][0]
task['worktree'] = '<TASK_WORKTREE_PATH>'
task['branch'] = '<TASK_BRANCH>'
task['status'] = 'in-progress'
task['timestamps']['started'] = __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
print(json.dumps(data, indent=2, ensure_ascii=False))
" | bash .claude/skills/android-shared/bin/android-file-lock "$TASKS_FILE.lock" \
    bash .claude/skills/android-shared/bin/android-json-atomic "$TASKS_FILE"
```

#### 步骤 5: 派发并行 Subagent

使用 Agent 工具为每个并行任务派发独立 subagent。

**每个 subagent 接收的指令:**

```
你正在 android-worktree-runner 的并行模式下执行任务。

## 任务信息
- 任务 ID: <TASK_ID>
- 任务标题: <TASK_TITLE>
- Worktree 路径: <TASK_WORKTREE_PATH>
- 分支: <TASK_BRANCH>
- TASKS_FILE: <MAIN_WORKTREE>/.claude/android-worktree-runner/tasks.json

## 执行步骤

1. cd 到 <TASK_WORKTREE_PATH>
2. 设置 GRADLE_USER_HOME="$TASK_WORKTREE_PATH/.gradle"
3. 按 task.steps 中的步骤逐一执行代码实现
4. 执行 Android 验证:
   - GRADLE_USER_HOME="$TASK_WORKTREE_PATH/.gradle" ./gradlew assembleDebug
   - GRADLE_USER_HOME="$TASK_WORKTREE_PATH/.gradle" ./gradlew lintDebug
   - GRADLE_USER_HOME="$TASK_WORKTREE_PATH/.gradle" ./gradlew testDebugUnitTest
5. 验证通过后提交:
   git add -A
   git commit -m "feat(<plan-slug>): complete task <task-num> - <task-title>"
6. 更新 tasks.json (必须使用原子写入 + 文件锁):
   - status → completed
   - commit → commit hash
   - verification → all true
   - timestamps.completed → 当前时间
7. 如果验证失败，更新 tasks.json:
   - status → failed
   - 在 commit 字段中记录错误摘要

## 重要约束
- 只修改与当前任务相关的文件
- 不要修改其他任务的文件
- 所有 tasks.json 写入必须使用 android-json-atomic + android-file-lock
- GRADLE_USER_HOME 必须隔离到 worktree 内
```

**subagent 并发控制:**

```python
# 伪代码 — 控制并发不超过 4 个
MAX_CONCURRENT = 4
running = []
pending = list(wave_tasks)

while pending or running:
    # 启动新 subagent (有空位时)
    while len(running) < MAX_CONCURRENT and pending:
        task = pending.pop(0)
        agent = Agent(name=f"task-{task.short_id}", ...)
        running.append(agent)

    # 等待任意 subagent 完成
    completed = wait_for_any(running)
    running.remove(completed)

    # 处理结果
    if completed.success:
        mark_task_completed(completed.task_id)
    else:
        mark_task_failed(completed.task_id)
```

#### 步骤 6: 波次完成检查

所有 subagent 完成后，检查本波次的执行结果:

**全部成功:**
- 显示波次完成摘要
- 进入下一波次 (回到步骤 2)

**部分失败:**
- 列出失败任务及其错误信息
- 使用 AskUserQuestion 提供选项:

> Wave N 中 N/M 个任务失败:
> - 失败: 任务 2 (构建错误), 任务 3 (测试失败)
> - 成功: 任务 1
>
> - A) 重试失败任务 — 在原 worktree 中重新执行
> - B) 跳过失败任务 — 标记为 blocked，继续下一波次
> - C) 暂停执行 — 手动修复后恢复

**选择 A (重试):** 对失败任务重新执行步骤 5 (subagent 派发)。
**选择 B (跳过):** 将失败任务标记为 `blocked`，记录原因。下游依赖这些
失败任务的任务也会被标记为 `blocked`。
**选择 C (暂停):** 停止执行，保持当前状态。用户可通过
`/android-worktree-runner <plan-id>` 恢复。

#### 步骤 7: 最终合并

所有波次完成后，将各任务 worktree 的变更合并到 plan 主分支:

```bash
cd "$WORKTREE_PATH"  # 回到 plan 主 worktree

# 按拓扑顺序合并 (wave 1 → wave 2 → ...)
# 对每个已完成任务:
for TASK_ID in $(按波次顺序的任务列表); do
  TASK_BRANCH="wr/<plan-slug>-task-<task-short-id>"
  TASK_COMMIT=$(git rev-parse "$TASK_BRANCH" --short)

  echo "=== 合并 $TASK_BRANCH ($TASK_COMMIT) ==="
  git merge "$TASK_BRANCH" --no-ff -m "merge: task <task-short-id> into plan branch"

  if [ $? -ne 0 ]; then
    echo "合并冲突! 请手动解决:"
    git diff --name-only --diff-filter=U
    # 暂停，提示用户解决
    AskUserQuestion:
    > 合并冲突于: <文件列表>
    > - A) 我来手动解决 — 解决后继续合并
    > - B) 跳过此任务 — 不合并该任务的变更
  fi
done
```

**合并冲突处理规则:**
- 如果用户选择手动解决 → 等待用户完成 `git add` + `git commit --continue`，然后继续合并下一个
- 如果用户选择跳过 → 删除该任务的 worktree 和分支，标记任务为 `blocked`，跳过后续依赖任务

**合并后完整验证:**

所有任务分支合并完成后，在 plan 主 worktree 中运行完整验证:

```bash
cd "$WORKTREE_PATH"
./gradlew assembleDebug
./gradlew lintDebug
./gradlew testDebugUnitTest
```

验证通过后，在 plan 主分支创建合并提交。

#### 步骤 8: 清理并行 Worktree

合并完成后，清理所有任务级 worktree:

```bash
# 清理每个任务的 worktree
for TASK_ID in $(所有任务 ID); do
  TASK_WORKTREE_PATH=".claude/worktrees/wr-<plan-slug>-task-<task-short-id>"
  TASK_BRANCH="wr/<plan-slug>-task-<task-short-id>"

  # 移除 worktree (保留分支作为备份)
  git worktree remove "$TASK_WORKTREE_PATH" --force

  # 清理隔离的 Gradle 缓存
  rm -rf "$TASK_WORKTREE_PATH/.gradle" 2>/dev/null || true
done
```

进入 Phase 3。

---

## Phase 3: Plan 完成

### 步骤 1: 展示总结

**串行模式总结:**

```
Plan: <标题> — 已完成
══════════════════════════════════════
任务: N/N 已完成
提交: <commit hash 列表>
验证: 全部通过 / <备注>
分支: plan/<slug>
Worktree: .claude/worktrees/<plan-id>
```

**并行模式总结:**

```
Plan: <标题> — 已完成 (并行模式)
══════════════════════════════════════
执行模式: 波次并行 (N 波)
任务: N/M 已完成 (K 个被跳过/失败)
波次明细:
  Wave 1: 任务 1 ✓ (分支: wr/slug-task-1, commit: a1b2c3d)
  Wave 1: 任务 6 ✓ (分支: wr/slug-task-6, commit: e5f6g7h)
  Wave 2: 任务 2 ✓ (分支: wr/slug-task-2, commit: b2c3d4e)
  Wave 2: 任务 3 ✗ (构建失败)
  Wave 3: 任务 4 ✓ (分支: wr/slug-task-4, commit: c3d4e5f)
  Wave 4: 任务 5 ⊘ (被跳过，依赖任务 3 失败)
合并: plan/<slug> (最终 commit: d4e5f6g)
验证: 全部通过 / <备注>
```

### 步骤 2: 更新状态

设置 plan `status` 为 `"completed"`，设置 `timestamps.completed`。

**使用原子写入 + 文件锁:**
```bash
cat "$TASKS_FILE" | python -c "
import sys, json, datetime
data = json.loads(sys.stdin.read())
plan = data['plans']['<PLAN_ID>']
plan['status'] = 'completed'
plan['timestamps']['completed'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
print(json.dumps(data, indent=2, ensure_ascii=False))
" | bash .claude/skills/android-shared/bin/android-file-lock "$TASKS_FILE.lock" \
    bash .claude/skills/android-shared/bin/android-json-atomic "$TASKS_FILE"
```

**同步更新 `worktree-info.md`:**
- 将该 plan 从"进行中"部分**移动**到"已完成"部分
- 填入完成时间和最终 commit hash
- 任务进度更新为 `(N/N 已完成)`
- 状态更新为"已完成"

### 步骤 3: 后续操作

AskUserQuestion:
> Plan 已完成! 如何处理该 worktree?
> - A) 保留 — 我会手动审查和合并
> - B) 合并分支到 main
> - C) 创建 Pull Request
> - D) 删除 worktree (保留分支)
> - E) 返回 autoplan 修订 — 执行中发现了 plan 级别的问题

选 B: 从主 worktree 合并 plan 分支到 main。
选 C: 使用 `gh pr create` 为 plan 分支创建 PR。
选 D: 执行 `git worktree remove <路径>` 但保留分支。

**推荐后续流程 (完成代码变更后):**
> - F) 代码审查 — 调用 /android-code-review 审查代码质量
> - G) QA 测试 — 调用 /android-qa 验证功能正确性
> - H) 更新文档 — 调用 /android-document-release 同步文档
> - I) 全部执行 — 按顺序自动执行 F → G → H
> - J) 清理所有过期 worktree 和孤立分支

如果用户选择 I (全部执行):
1. 调用 android-code-review 审查当前分支
2. 如果 code-review 通过: 调用 android-qa 进行 QA
3. 如果 QA 通过: 调用 android-document-release 更新文档
4. 任何步骤发现阻塞问题: 中断并报告给用户

选 J: 执行全量 worktree 清理。先运行健康检查展示问题，确认后执行清理:
```bash
bash .claude/skills/android-shared/bin/android-worktree-health
# 显示问题后确认
bash .claude/skills/android-shared/bin/android-worktree-health --cleanup
```
清理完成后，同步更新 `worktree-info.md`，移除已清理 worktree 的条目。
同步更新 `tasks.json`，移除对应 plan 的条目（仅当 worktree 被移除时）。

选 E: 将执行中遇到的问题标注到 plan 文件中，然后调用
  android-autoplan 重新审查。流程:
  1. 从 `plan_source.ref` 获取原始 plan 文件名 (如 `2026-04-10-auth.md`)
  2. 从 `plan_source.ref` 提取 basename (如 `2026-04-10-auth.md` → `2026-04-10-auth`)，
     将问题写入 `docs/plans/<plan-basename>-execution-issues.md`

**execution-issues 文件格式:**

```markdown
# 执行问题报告: <plan-slug>

## 概要
- 执行任务数: X/Y
- 失败任务: Z

## 失败任务详情

### Task N: <title>
**错误类型:** build_error / test_failure / dependency_missing / instruction_unclear
**错误信息:**
\`\`\`
<完整错误输出>
\`\`\`
**已尝试的修复:** <描述>
**建议:** <建议 autoplan 如何调整 plan>
```

  3. 使用 Skill 工具调用 android-autoplan:
     skill: "android-autoplan", args: "review docs/plans/<plan-filename>.md"
  4. autoplan 的 review 模式会自动查找同名
     `<plan-filename>-execution-issues.md` 作为额外输入
  5. autoplan 读取 plan + execution-issues，重新审查并产出修订版 plan
  6. 用户确认修订版后，重新导入 worktree-runner 执行

---

## 多 Worktree 支持

多个 plan 可以同时处于进行中状态，各自在独立的 worktree 中。

### Worktree 管理命令

**列出所有 worktree:**
```bash
git worktree list
```

**检查当前所在的 worktree:**
```bash
git worktree list | grep "$(pwd)"
```

**切换 worktree:**
当用户想要处理另一个进行中的 plan 时，使用 AskUserQuestion 确认，
然后 `cd` 到目标 worktree 的路径。

### 冲突预防

- 每个 plan 获得唯一分支: `plan/<slug>` — slug 由标题和时间戳生成，避免冲突
- 如果分支名冲突，追加递增数字: `plan/auth-login-flow-2`
- 如果两个 plan 修改相同文件，发出警告（检查任务步骤中的文件路径）

---

## 恢复保障

此 skill 设计为可抵御 `/clear`、会话重启和上下文窗口耗尽。恢复机制很简单:
**磁盘上的 `tasks.json` 始终是真相。**

### 恢复原理

1. **每次调用都以相同方式开始:** 从磁盘读取 `tasks.json`
2. **每次状态变更立即写入:** 不批量、不延迟
3. **没有仅存在于内存中的状态:** 不在 `tasks.json` 中的状态不存在

### 恢复场景

**`/clear` 之后:**
```
用户: /android-worktree-runner plan-auth
Skill: → 读取 tasks.json → 找到 plan-auth，任务 2 进行中
       → 进入 worktree → 显示任务 2 状态 → 恢复执行
```

**会话重启后 (Claude Code 关闭后重新打开):**
```
用户: /android-worktree-runner
Skill: → 读取 tasks.json → 展示所有 plan 的当前状态
       → "Plan: 登录流程 [进行中] — 任务 2/3"
       → 提供恢复选项
```

**上下文窗口压缩后:**
```
上下文在任务执行过程中被压缩 → skill 在下次交互时重新读取 tasks.json
→ 状态是最新的 → 无缝继续
```

**`/clear` 之后 (并行模式):**
```
用户: /android-worktree-runner plan-20260410-001
Skill: → 读取 tasks.json → execution_mode = parallel
       → Wave 1 已完成 (任务 1, 6)，Wave 2 进行中 (任务 2 完成, 任务 3 in-progress)
       → 检查任务 3 的 worktree 是否存在
       → 如果存在 → 进入该 worktree 恢复执行
       → 如果不存在 (被清理) → 标记任务 3 为 failed，继续下一波次
```

### 什么会被持久化

| 时机 | 写入 tasks.json 的内容 |
|------|------------------------|
| Plan 导入时 | 包含所有任务的 plan 条目 (状态: pending)，依赖关系 |
| 执行模式选择时 | execution_mode，各任务 wave 编号 |
| 任务开始时 | 任务状态 → in-progress，启动时间戳 |
| 任务完成时 | 任务状态 → completed，commit hash，验证结果，完成时间戳 |
| 任务失败时 (并行) | 任务状态 → failed，错误摘要 |
| 任务被阻塞时 | 任务状态 → blocked，阻塞原因 |
| 波次合并完成时 | 各任务 worktree/branch 信息清除 (已合并) |
| Plan 完成时 | Plan 状态 → completed，完成时间戳 |
| 验证被跳过时 | 验证字段 → "skipped" |

### 什么不需要持久化

- Plan 文件内容（恢复时从 `plan_source.ref` 重新读取）
- 代码变更（已在 worktree 的 git 工作区中）
- 构建输出（临时的，下次验证时重新运行）

---

## Capture Learnings

Plan 执行完成后，将 operational 发现记录到学习系统以供未来 session 参考。

**记录时机:**

1. **构建顺序依赖** — 如果发现某些任务必须按特定顺序执行（如 Gradle 插件配置必须在模块创建之前），记录:
   ```bash
   bash .claude/skills/android-shared/bin/android-learnings-log '{"skill":"worktree-runner","type":"technique","key":"<依赖描述>","insight":"<顺序要求和原因>","confidence":8,"source":"observed","files":[]}'
   ```

2. **环境配置问题** — 如 Gradle daemon 内存不足、worktree 权限问题，记录:
   ```bash
   bash .claude/skills/android-shared/bin/android-learnings-log '{"skill":"worktree-runner","type":"technique","key":"<环境问题>","insight":"<问题描述和解决方案>","confidence":7,"source":"observed","files":[]}'
   ```

**不记录:**
- 一次性的编译错误
- 与历史记录完全重复的发现

---

## 异常情况处理

| 场景 | 处理方式 |
|------|----------|
| Plan 对应的 worktree 已存在 | 通过 `git worktree list` 检测，提供恢复选项 |
| 分支名已存在 | 分支名后追加 `-2`、`-3` 等 |
| Plan 源文件已被删除 | 发出警告，使用 `tasks.json` 中存储的步骤继续 |
| Plan 源文件已被修改 | 提示变更，提供重新导入选项 |
| 不在 git 仓库中 | 报错: "android-worktree-runner 需要 git 仓库" |
| `tasks.json` 损坏 | 发出警告，提供从 plan 源文件重建的选项。原子写入脚本会在写入前验证 JSON 合法性，降低损坏风险 |
| 任务没有步骤 | 视为单个原子任务处理 |
| 提交失败 (没有变更) | 跳过提交，标记任务完成，备注 "无变更" |
| Android 验证超时 (>5 分钟) | 询问用户: 继续等待或跳过 |
| 并行任务间合并冲突 | 暂停合并流程，提示用户手动解决冲突文件，解决后输入继续 |
| Gradle 守护进程端口冲突 | 每个 worktree 使用隔离的 `GRADLE_USER_HOME`，自动避免冲突 |
| 并行 subagent 中某个失败 | 标记该任务为 `failed`，其他任务继续执行。波次完成后统一报告 |
| Worktree 创建失败 (并行模式) | 回退到串行模式执行该任务，在 plan 主 worktree 中运行 |
| 磁盘空间不足 (多个 worktree) | 检测磁盘空间，不足时警告并建议: 减少并行度或清理已有 worktree |
| 任务依赖循环检测 | 标记循环中的任务为 `blocked`，其余无循环任务正常执行 |
| 并行任务修改相同文件 | 在波次规划阶段检查步骤中的文件路径，发现冲突时发出警告。运行时如果发生文件冲突，合并阶段会检测到 |
| tasks.json 并发写入冲突 | 通过 `android-file-lock` 文件锁机制自动串行化，获取锁失败时重试 (最多 3 次) |
| `/clear` 后并行任务状态丢失 | 不会丢失 — 所有状态通过原子写入立即持久化到 tasks.json。恢复时读取 wave 信息继续执行 |

---

## Worktree 管理文件 (worktree-info.md)

项目根目录下维护一个 `worktree-info.md` 文件，作为所有 worktree 的**人类可读索引**。
与 `tasks.json`（机器可读的执行状态）互补。

### 文件位置

`$MAIN_WORKTREE/worktree-info.md`（项目根目录，与 `.git` 同级）

### 文件格式

```markdown
# Worktree 索引

> 自动生成于 2026-04-10 | 由 android-worktree-runner 维护

## 进行中

### plan/auth-login-flow [并行模式]
- **worktree:** `.claude/worktrees/plan-20260410-001`
- **创建于:** 2026-04-10
- **基准 commit:** `abc1234`
- **任务:** 登录流程实现 (2/5 已完成, Wave 2/4)
- **状态:** 进行中 — Wave 2 执行中
- **并行分支:**
  - wr/auth-login-flow-task-1 (Wave 1, 已完成)
  - wr/auth-login-flow-task-6 (Wave 1, 已完成)
  - wr/auth-login-flow-task-2 (Wave 2, 进行中)
  - wr/auth-login-flow-task-3 (Wave 2, 进行中)

### plan/room-database [串行模式]
- **worktree:** `.claude/worktrees/plan-20260410-002`
- **创建于:** 2026-04-10
- **基准 commit:** `abc1234`
- **任务:** Room 数据库搭建 (0/2 已完成)
- **状态:** 待开始

## 已完成

### plan/project-init
- **worktree:** `.claude/worktrees/plan-20260409-001`
- **创建于:** 2026-04-09
- **基准 commit:** `a1b2c3d`
- **任务:** 项目初始化 (3/3 已完成)
- **状态:** 已完成 — 2026-04-10
- **最终 commit:** `f5e4d3c`
```

### 维护规则

1. **创建 worktree 时更新:** Phase 0 步骤 5 创建 worktree 后，将新 plan 添加到
   `worktree-info.md` 的"进行中"部分。
2. **任务完成时更新:** Phase 2 步骤 7 每个任务完成后，更新对应 plan 的任务进度
   `(X/N 已完成)` 和当前状态描述。
3. **并行波次推进时更新:** Phase 2B 每个波次完成后，更新对应 plan 的波次进度
   `(Wave M/N)` 和各并行分支的状态。
4. **Plan 完成时更新:** Phase 3 步骤 2 将 plan 从"进行中"移动到"已完成"部分，
   填入完成时间和最终 commit hash。并行模式下同时清理并行分支列表。
5. **文件不存在时自动创建:** 首次创建 worktree 时，如果 `worktree-info.md` 不存在，
   先扫描 `git worktree list` 获取已有的 worktree 列表，创建文件并填入已有条目。
   对于不是由 android-worktree-runner 创建的 worktree，标记为"外部 worktree"。
6. **文件已存在时追加:** 不覆盖已有内容。读取现有文件，在对应部分添加或更新条目。

### 与 tasks.json 的关系

| 文件 | 用途 | 读者 |
|------|------|------|
| `tasks.json` | 执行状态，机器可读 | android-worktree-runner skill |
| `worktree-info.md` | worktree 索引，人类可读 | 开发者、代码审查 |

`tasks.json` 是执行时的唯一真相源。`worktree-info.md` 是它的**派生视图**，
始终从 `tasks.json` 的状态生成内容，不持有独立状态。

---

## 文件结构

```
项目根目录/                           ← 主 worktree
├── worktree-info.md                 ← worktree 索引 (人类可读)
├── .claude/
│   ├── android-worktree-runner/
│   │   └── tasks.json              ← 唯一真相源 (始终在此)
│   └── worktrees/
│       ├── plan-20260410-001/      ← plan 1 的 worktree (串行模式)
│       │   └── (实际的代码变更)
│       ├── plan-20260410-002/      ← plan 2 的主 worktree (并行模式)
│       │   └── (合并后的代码变更)
│       ├── wr-slug-task-1/         ← plan 2 并行任务的 worktree
│       │   └── (任务 1 的代码变更)
│       ├── wr-slug-task-2/         ← plan 2 并行任务的 worktree
│       │   └── (任务 2 的代码变更)
│       └── ...
├── docs/
│   └── plans/
│       └── *.md                    ← plan 源文件
└── ...
```

**并行模式文件结构说明:**
- `plan-*` worktree 是 plan 的主 worktree，作为并行任务的基准分支和合并目标
- `wr-*` worktree 是并行模式中各任务的工作目录，完成后合并到 plan 主分支并清理
- 串行模式不创建 `wr-*` worktree，所有任务在 plan 主 worktree 中执行

**核心规则:** `tasks.json` 位于主 worktree 的 `.claude/` 目录中。
所有 plan worktree（在 `.claude/worktrees/` 下）读写同一个文件。
没有任何 worktree 持有 `tasks.json` 的副本。
`worktree-info.md` 位于项目根目录，作为所有 worktree 的人类可读索引。

---

## 与其他 Skill 的集成

此 skill 设计为与产出的 plan 的各类 skill 协同工作:

| Plan 来源 | 产出方 | 连接方式 |
|-----------|--------|----------|
| `docs/plans/*.md` | superpowers:writing-plans | 导入时自动检测 |
| `~/.gstack/projects/*/` | gstack:office-hours + autoplan | 导入时自动检测 |
| 内存中的 plan | Claude Code /plan | 从上下文读取 |
| 任意 Markdown | 手动或自定义 skill | 导入时提供路径 |

任何 skill 产出 plan 后，调用 `/android-worktree-runner` 导入并开始执行。
