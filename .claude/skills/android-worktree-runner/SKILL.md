---
name: android-worktree-runner
description: |
  Git worktree 隔离的 Plan 执行器。一个 Plan = 一个 worktree。
  支持串行和波次并行。每次 commit 前执行 Android 验证 (build→lint→test)。
  支持 /clear 后恢复。
---

# Android Worktree Runner

**启动声明:** "我正在使用 android-worktree-runner skill。"

**调用:** `/android-worktree-runner` | `/android-worktree-runner <plan-id>` | `import` | `status`

## Subagent 权限与并发边界 (P1-1, H2)

### 权限边界
- Subagent **禁止**调用以下 skill: `android-worktree-runner`, `android-autoplan`, `android-ship`。
- Subagent **可以**调用: `android-tdd`, `android-code-review`, `android-investigate`, `android-fix`。

### 并发预算 (H2)
- 全局 Subagent 并发上限: **4**。
- `android-code-review` 和 `android-tdd` 每次调用计入 1 个并发名额。
- 若并发已满，Subagent 必须在队列中等待或回退到串行执行。

## 并发保护 (H3)

```
所有 tasks.json 写入必须:
  echo '<json>' | bash "$SHARED_BIN/bin/android-file-lock" "$TASKS_FILE.lock" \
    bash "$SHARED_BIN/bin/android-json-atomic" "$TASKS_FILE"
禁止直接使用 Write 工具写入 tasks.json。
Subagent 必须严格遵守此约束，否则可能导致数据丢失。
```

## 存储

`$MAIN_WORKTREE/.claude/android-worktree-runner/tasks.json`

```bash
MAIN_WORKTREE=$(git worktree list 2>/dev/null | head -1 | awk '{print $1}')
TASKS_FILE="$MAIN_WORKTREE/.claude/android-worktree-runner/tasks.json"
SHARED_BIN=$(bash "$MAIN_WORKTREE/.claude/skills/android-shared/bin/android-resolve-path" 2>/dev/null || bash android-resolve-path 2>/dev/null || true)
```

## Phase 0: 导入 Plan

```bash
# 预加载
bash "$SHARED_BIN/bin/android-learnings-bootstrap" 2>/dev/null || true
LEARNINGS=$(bash "$SHARED_BIN/bin/android-learnings-search" --type technique --limit 5 2>/dev/null || true)
ENV_JSON=$(bash "$SHARED_BIN/bin/android-detect-env" 2>/dev/null || true)
```

### 加载项目上下文

```bash
_R="$MAIN_WORKTREE"
INIT_STATUS="$_R/.claude/init-status.json"
if [ -f "$INIT_STATUS" ]; then
  PROFILE_PATH=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('profile_path',''))" "$INIT_STATUS")
  [ -n "$PROFILE_PATH" ] && [ -f "$PROFILE_PATH" ] && cat "$PROFILE_PATH"
fi
```

### 检测 Plan 来源

1. Markdown: `find . -name "*plan*.md" -print | head -20`
2. Superpowers: `ls docs/plans/*.md 2>/dev/null`
3. GStack: `ls ~/.gstack/projects/*/*-design-*.md 2>/dev/null | head -10`
4. 内存中的 plan (系统消息提供)

AskUserQuestion 展示来源 → 用户选择。

### 解析 Plan

| 格式 | 解析规则 |
|------|---------|
| Superpowers | `### Task N:` → 顶层任务, `**Step N:**` → 步骤 |
| GStack design | `## Recommended Approach` / `## Next Steps` |
| 通用 Markdown | `## Task N:` / `### Task N:` / `- [ ]` checkbox |

**依赖关系:** `depends_on: [task-id]` 或 `依赖: Task N` → 提取。无标注则为 `[]`。

### PRD 提取

```bash
sed -n '/^## PRD$/,/^## [^#]/p' "$PLAN_FILE" | head -n -1
```

解析 FR-N / AC-N / exclusions → 存入 tasks.json plan.prd 字段。

### Plan Status 读取

```bash
STATUS_FILE="${PLAN_FILE%.md}-status.json"
if [ -f "$STATUS_FILE" ]; then cat "$STATUS_FILE"; fi
```

若存在: 提取 plan_id / source / review_summary / approved_at 写入 tasks.json。
**审批检查:** 若 plan-status.json 存在但 approved_at 为空 → AskUserQuestion: "Plan 未通过审批。是否继续?" A) 继续 B) 先审批 C) 取消

### 创建 Worktree

```bash
PLAN_ID="plan-$(date +%Y%m%d-%H%M%S)"
PLAN_SLUG=$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | head -c 50)
WORKTREE_PATH=".claude/worktrees/$PLAN_ID"
BRANCH="plan/$PLAN_SLUG"
BASE_COMMIT=$(git rev-parse --short HEAD)
git worktree add "$WORKTREE_PATH" -b "$BRANCH"
```

原子写入 tasks.json (合并已有 plan 不覆盖)。

更新 `worktree-info.md` (不存在则创建)。

## Phase 0.5: 健康检查

```bash
bash "$SHARED_BIN/bin/android-worktree-health"
```

发现问题 → AskUserQuestion: A) 自动清理 B) 手动选择 C) 跳过

**Gradle 策略:** worktree 中所有 Gradle 调用加 `--no-daemon` (避免多 worktree daemon 锁冲突)。

## Phase 0.75: 执行策略分析

读取 tasks 的 depends_on → 拓扑排序 → 计算波次。

```python
# 伪代码: BFS 分层
waves = []; queue = [入度为0的任务]; visited = set()
while queue:
    wave = []
    for _ in range(len(queue)):
        tid = queue.popleft()
        if tid not in visited: visited.add(tid); wave.append(tid)
        for dep in dependents[tid]:
            in_degree[dep] -= 1
            if in_degree[dep] == 0: queue.append(dep)
    if wave: waves.append(wave)
```

循环依赖 → 标记 blocked，其余正常执行。

AskUserQuestion 选择: A) 波次并行 B) 纯串行。无依赖/单任务 → 直接串行。

## Phase 1: 状态展示

```
╔══════════════════════════════════════╗
║ ● Plan: 登录流程 [进行中]  并行(3波) ║
║   ├─ ✓ 任务 1: Gradle (Wave 1)      ║
║   ├─ ● 任务 2: UI (Wave 2) [当前]   ║
║   └─ ○ 任务 3: 验证 (Wave 2)        ║
║                                      ║
║ ○ Plan: 数据库 [待开始]  串行        ║
╚══════════════════════════════════════╝
```

**符号:** `○` 待开始 `●` 进行中 `✓` 已完成 `⊘` 阻塞 `✗` 失败

AskUserQuestion 提供操作选项。存在 blocked/failed 任务 → 额外提供恢复选项。

## Phase 2A: 串行执行

### Subagent 并发上限: 4 个

### 执行流程

```
1. cd "$WORKTREE_PATH"
2. 找第一个 pending 任务 → 无则 Phase 3
3. 标记 in-progress (原子写入 tasks.json)
4. TDD 分类:
   强制关键词: ViewModel/Repository/UseCase/screen/feature/logic/component/service
   跳过关键词: Gradle/Manifest/ProGuard/migration/config/setup/基础设施/测试
   若 required → 调用 android-tdd skill → 更新 tdd.* 字段
5. 执行步骤: 严格按 plan 顺序, 遇阻即停
6. Android 验证 (commit 前必须):
   a. 构建系统检测 (gradle/bazel/cmake/ndk-build)
   b. 工具检测 → 缺失则派发 subagent 安装
   c. 版本检测 (AGP→JDK, .bazelversion, cmake_minimum_required)
   d. ./gradlew assembleDebug --no-daemon
   e. ./gradlew lintDebug --no-daemon
   f. ./gradlew testDebugUnitTest --no-daemon (不可跳过)
   g. 测试失败 → 修复循环(max 3轮) → 仍失败 → status=failed
   h. PRD 验证 (若 prd 不为 null): 匹配 AC → 验证实现 → 记录 ✗ 项到 prd_notes
7. git add -A && git commit -m "feat($PLAN_SLUG): complete task N - $TITLE"
8. 更新 tasks.json: status=completed, commit=hash, verification=true, timestamps.completed
9. **自动代码审查** (commit 后立即执行):
   ```
   调用 android-code-review skill (针对当前 worktree 分支)
   审查维度: 架构/命名/生命周期/线程/Android特有/可测试性/安全
   输出: docs/reviews/<branch>-code-review.md
   
   结果处理:
   - 🔴 BLOCKER → 提示用户，标记任务需修复
   - 🟠 WARNING ≤ 3 → 记录到 review_notes，继续
   - 🟠 WARNING > 3 → 提示用户，询问是否修复
   - ✅ 无严重问题 → 继续
   ```
10. **自动 TDD 验证** (审查通过后):
    ```
    检查任务 TDD 分类:
    - 若 required → 调用 android-tdd skill
    - 若 skip → 跳过
    
    TDD 执行:
    1. 检查测试覆盖率是否达标 (≥80%)
    2. 不达标 → 自动补测试 (max 2轮)
    3. 验证所有测试通过
    4. 输出覆盖率报告
    
    结果处理:
    - 通过 → 继续
    - 不通过 (max 2轮后) → 记录到 tdd_notes，状态设为 completed-with-tdd-issues (M5)
    ```
11. 更新 worktree-info.md (包含审查和 TDD 状态)
12. 回到步骤 2
```

### 验证失败处理

| 结果 | 处理 |
|------|------|
| 全部通过 | commit |
| 部分失败 | 修复循环(max 3) |
| 3轮后仍失败 | status=failed, 不提交 |
| 工具缺失 | subagent 安装 → 仍失败 → status=blocked |

## Phase 2B: 波次并行

```
Wave 1: [Task A] [Task F]  ← 不同 worktree 同时执行
  ↓ 全部完成
Wave 2: [Task B] [Task C]
  ↓ 全部完成
Wave 3: [Task D]  ← 单任务回退串行
最终合并 → Phase 3
```

### 执行流程

1. 进入 plan 主 worktree
2. 计算当前波次 (max(completed_wave) + 1)
3. 单任务 → 回退 Phase 2A。多任务 → 并行:
   - 为每个任务创建独立 worktree: `git worktree add ".claude/worktrees/wr-<slug>-task-N" -b "wr/<slug>-task-N"`
   - 写入 tasks.json: worktree/branch/status=in-progress
   - 派发 subagent (并发≤4), 每个接收: 任务信息/worktree路径/SHARED_BIN/项目档案
   - subagent 执行: 实现→验证(--no-daemon)→PRD→提交→更新tasks.json
   - **subagent 自动执行**: code-review → TDD 验证 (同 Phase 2A 步骤 9-10)
4. 波次完成检查:
   - 全部成功 → 下一波次
   - 部分失败 → AskUserQuestion: A) 重试 B) 跳过(mark blocked) C) 暂停
5. 最终合并: 按波次顺序 `git merge` 各任务分支到 plan 主分支
6. 完整验证: assembleDebug → lintDebug → testDebugUnitTest
7. 清理 worktree: `git worktree remove` + 清理 .gradle 缓存

## Phase 3: Plan 完成

### 审查汇总

```bash
# 收集所有任务的审查和 TDD 结果
REVIEWS=$(find docs/reviews -name "*${PLAN_SLUG}*-code-review.md" 2>/dev/null)
TDD_REPORTS=$(find docs/reviews -name "*${PLAN_SLUG}*-tdd.md" 2>/dev/null)

# 生成综合报告
docs/reviews/${PLAN_SLUG}-final-report.md:
  任务完成情况:
    总任务数: N
    完成: N | 失败: N | 阻塞: N
  
  代码审查统计:
    🔴 BLOCKER: N (需修复)
    🟠 WARNING: N (建议修复)
    🟡 INFO: N
  
  TDD 覆盖率:
    总体行覆盖率: XX%
    关键路径覆盖率: XX%
    分支覆盖率: XX%
  
  审查报告列表:
    - Task 1: docs/reviews/<branch>-code-review.md
    - Task 1: docs/reviews/<branch>-tdd.md
    - ...
  
  最终状态:
    ✅ 通过 (无 BLOCKER, WARNING ≤ 阈值)
    ⚠️ 有条件通过 (有 WARNING，可后续修复)
    ❌ 未通过 (有 BLOCKER，需修复)
```

### 用户确认

```
AskUserQuestion: "Plan 执行完成，审查结果: <状态>。是否现在修复 BLOCKER?"
- A) 立即修复 (针对有 BLOCKER 的任务)
- B) 跳过，继续下一步 (ship)
- C) 暂停，手动检查

最终提示:
"所有任务已完成，审查报告已生成。
可使用 /android-ship 合并到主分支并提交 PR。"
```


## 多 Worktree 管理


## 恢复机制


## 异常处理

| 场景 | 处理 |
|------|------|
| worktree 已存在 | 提供恢复选项 |
| 分支名冲突 | 追加 -2, -3 |
| tasks.json 损坏 | 从 plan 源文件重建 |
| 无变更 | 跳过提交, 备注"无变更" |
| 验证超时(>5min) | 询问用户 |
| 合并冲突 | AskUserQuestion: 手动解决 / 跳过 |
| Gradle daemon 锁 | --no-daemon |
| 工具缺失 | subagent 安装 → 失败则 blocked |
| 测试失败 | 修复3轮 → failed, 不跳过 |
| 依赖循环 | blocked, 其余正常 |
| tasks.json 并发 | file-lock 自动串行化 |
| /clear 后恢复 | 从 tasks.json 读取继续 |

## Capture Learnings

```bash
bash "$SHARED_BIN/bin/android-learnings-log" '{"skill":"worktree-runner","type":"technique","key":"KEY","insight":"INSIGHT","confidence":8,"source":"observed","files":[]}'
```

记录: 构建顺序依赖、环境配置问题。不记录: 一次性编译错误、重复发现。
