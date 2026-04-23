---
name: android-worktree-runner
description: Use when executing a multi-task Android plan via git worktree isolation, with serial/wave scheduling, mandatory pre-commit verification, and resumable state.
---

# Android Worktree Runner

**启动声明:** "我正在使用 android-worktree-runner skill。"
**调用:** `/android-worktree-runner` | `/android-worktree-runner <plan-id>` | `import` | `status`

## Hard Rules

- Subagent 禁止调用: `android-worktree-runner`, `android-autoplan`, `android-ship`
- Subagent 可调用: `android-tdd`, `android-code-review`, `android-investigate`, `android-fix`
- 全局并发上限: `4`
- 所有 Gradle 命令必须带 `--no-daemon`
- `tasks.json` 只允许原子写入，禁止直接写文件

## Shared State

`$MAIN_WORKTREE/.claude/android-worktree-runner/tasks.json`

```bash
MAIN_WORKTREE=$(git worktree list 2>/dev/null | head -1 | awk '{print $1}')
TASKS_FILE="$MAIN_WORKTREE/.claude/android-worktree-runner/tasks.json"
SHARED_BIN=$(bash "$MAIN_WORKTREE/.claude/skills/android-shared/bin/android-resolve-path" 2>/dev/null || bash android-resolve-path 2>/dev/null || true)
RUN_ID=$(bash "$SHARED_BIN/bin/android-run-id" --ensure 2>/dev/null || echo "run-local")
bash "$SHARED_BIN/bin/android-tasks-meta" --file "$TASKS_FILE" --run-id "$RUN_ID" --init-if-missing
```

原子写入模板:

```bash
bash "$SHARED_BIN/bin/android-tasks-meta" --file "$TASKS_FILE" --run-id "$RUN_ID" --init-if-missing
echo '<json>' | bash "$SHARED_BIN/bin/android-file-lock" "$TASKS_FILE.lock" \
  bash "$SHARED_BIN/bin/android-json-atomic" "$TASKS_FILE"
```

## Phase 0: Import Plan

1. 预加载: `android-learnings-bootstrap` / `android-detect-env`
2. 发现计划源: `docs/plans/*.md`、通用 `*plan*.md`、GStack、内存计划
3. 解析任务与步骤:
   - Superpowers: `### Task N` + `**Step N**`
   - 通用 Markdown: `##/### Task N`、`- [ ]`
   - 依赖: `depends_on` 或 `依赖: Task N`
4. 提取 PRD: `FR-*`, `AC-*`, exclusions
5. 读取 `<plan>-status.json`:
   - 写入 `plan_id/source/review_summary/approved_at`
   - 若有 status 文件但 `approved_at` 为空: AskUserQuestion 是否继续
6. 创建工作树与分支:
   - `PLAN_ID=plan-<timestamp>`
   - `BRANCH=plan/<slug>`
   - `git worktree add ".claude/worktrees/$PLAN_ID" -b "$BRANCH"`
7. 更新 `tasks.json` 与 `worktree-info.md`（不存在则创建）

## Phase 0.5: Health

```bash
bash "$SHARED_BIN/bin/android-worktree-health"
```

异常时 AskUserQuestion: 自动清理 / 手动 / 跳过。

## Phase 0.75: Scheduling

- 根据 `depends_on` 做拓扑分层
- 有环依赖: 标记 `blocked`，其余任务继续
- AskUserQuestion: `波次并行` 或 `串行`
- 单任务或无依赖默认串行

## Phase 1: Status View

状态符号: `○` pending, `●` in-progress, `✓` completed, `⊘` blocked, `✗` failed  
若存在 failed/blocked，必须提供恢复选项。

## Phase 2A: Serial Execution

循环处理第一个 pending 任务:

1. `cd "$WORKTREE_PATH"`，任务标记 `in-progress`
2. TDD 分类:
   - required 关键词: `ViewModel/Repository/UseCase/screen/feature/logic/component/service`
   - skip 关键词: `Gradle/Manifest/ProGuard/migration/config/setup/基础设施/测试`
3. 执行计划步骤，遇阻即停
4. 提交前验证（强制）:
   - `./gradlew assembleDebug --no-daemon`
   - `./gradlew lintDebug --no-daemon`
   - `./gradlew testDebugUnitTest --no-daemon`
   - 测试失败最多修复 3 轮；仍失败 → `failed`（不提交）
5. PRD 验证（如存在）: 对齐 AC，未满足写入 `prd_notes`
6. 提交: `git add -A && git commit -m "feat($PLAN_SLUG): complete task N - $TITLE"`
7. 更新 `tasks.json`: `status/commit/verification/timestamps`
8. 任务后自动执行:
   - `android-code-review`
   - required 任务再执行 `android-tdd`（覆盖率门槛 80%，补测最多 2 轮）
9. 审查结果处理:
   - `BLOCKER` → 提示并进入待修复
   - `WARNING <= 3` → 记录后继续
   - `WARNING > 3` → 询问是否先修复
10. 写回 `worktree-info.md`，继续下一个任务

## Phase 2B: Wave Parallel

1. 按波次执行；单任务波次回退串行
2. 每任务独立 worktree:
   - `git worktree add ".claude/worktrees/wr-<slug>-task-N" -b "wr/<slug>-task-N"`
3. 并发派发 subagent（总并发 <= 4）
4. 子任务必须执行: 实现 → 验证 → 提交 → code-review → TDD → 回写 `tasks.json`
5. 波次完成判断:
   - 全成功 → 下一波
   - 部分失败 → AskUserQuestion: 重试 / 标记 blocked / 暂停
6. 所有波次后顺序合并到 plan 分支
7. 最终全量验证: `assembleDebug` → `lintDebug` → `testDebugUnitTest`
8. 清理临时 worktree 与缓存

## Phase 3: Finalize Plan

输出 `docs/reviews/${PLAN_SLUG}-final-report.md`，至少包含:

- 任务统计: total/completed/failed/blocked
- 审查统计: `BLOCKER/WARNING/INFO`
- 覆盖率统计: 行覆盖、关键路径、分支覆盖
- 每任务报告链接: code-review / tdd
- 最终状态: 通过 / 有条件通过 / 未通过

最后 AskUserQuestion: 是否立即修复 BLOCKER，或继续 `/android-ship`。

## Recovery and Errors

- worktree 已存在: 提供恢复入口
- 分支名冲突: 自动追加后缀
- tasks.json 损坏: 从 plan 重建
- 无代码变更: 跳过提交并记录
- 验证超时 (>5min): 询问用户
- 合并冲突: 手动解决或跳过
- 工具缺失: 尝试安装，失败则 `blocked`
- `/clear` 后恢复: 从 `tasks.json` 继续

## Capture Learnings

```bash
bash "$SHARED_BIN/bin/android-learnings-log" '{"skill":"worktree-runner","type":"technique","key":"KEY","insight":"INSIGHT","confidence":8,"source":"observed","files":[]}'
```
