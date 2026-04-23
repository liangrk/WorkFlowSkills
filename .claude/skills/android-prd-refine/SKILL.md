---
name: android-prd-refine
description: Use when a feature request is still ambiguous and must be refined into a constraint-driven PRD with testable acceptance criteria and runner-ready execution tasks.
voice-triggers:
  - "整理prd"
  - "细化需求"
  - "约束性prd"
  - "prd refine"
  - "需求收敛"
invocation: /android-prd-refine
args: [<raw-requirement-file>] [--from-thinking <file>] [--to-plan]
---

# Android PRD Refine

**启动声明:** "我正在使用 android-prd-refine skill。"
**定位:** 收敛需求，不做发散。目标是生成可执行、可验收、可交付给 runner 的 PRD。

## Core Method

从“想法”到“可执行需求”采用三层收敛:

1. 需求原子化: 把口语化需求拆成最小业务单元（角色/触发/动作/结果）
2. 约束化: 给每个单元补齐边界、例外、非目标、量化指标
3. 可执行化: 映射为 FR/AC 和 Runner Ready Task

每层都要做冲突检查；冲突未解，禁止进入下一层。

## Hard Gates

以下任一条件不满足，禁止进入下一阶段:

1. 目标用户/业务目标/范围边界不明确
2. FR 未编号 (`FR-*`) 或 AC 未编号 (`AC-*`)
3. FR 与 AC 不是一一可追踪映射
4. 未定义 Out of Scope
5. Execution Plan 缺少 `Task/Step/depends_on/DoD/验证命令`
6. 存在未决策冲突项（规则冲突、优先级冲突、依赖冲突）
7. 未输出变更控制规则（PRD Freeze + Change Request）

## Inputs

- 原始需求（对话或文件）
- 约束信息（时间、人员、技术、合规）
- 现有上下文（`docs/thinking/*.md`、设计稿、历史问题单）

可选:
- `--from-thinking <file>`: 从 brainstorm 输出继续收敛
- `--to-plan`: 产出后立即生成 `docs/plans/*.md` 并提示交接 runner

## Phase 0: 读取上下文

```bash
SHARED_BIN=$(bash android-resolve-path 2>/dev/null || true)
RUN_ID=$(bash "$SHARED_BIN/bin/android-run-id" --ensure 2>/dev/null || echo "run-local")
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
ls docs/thinking/*.md 2>/dev/null | tail -5
ls docs/plans/*.md 2>/dev/null | tail -5
```

若输入为空或仅有口号级描述，先进入 Phase 1，不得直接写 PRD。

## Phase 1: 去歧义澄清（必须先完成）

AskUserQuestion 按顺序收敛:

1. 业务目标与成功指标是什么？（量化）
2. 目标用户与核心场景是什么？（主路径）
3. 本次明确不做什么？（Out of Scope）
4. 硬约束是什么？（上线时间/兼容范围/依赖系统）
5. 失败条件是什么？（何种结果算不可接受）

若任一问题无答案，输出 `Open Questions` 并停止，不得进入 Phase 2。

新增输出: `Assumptions`（所有暂定假设要显式列出，并标记风险等级）。

## Phase 2: 约束性 PRD 生成

输出 `## PRD`，固定结构:

1. 背景与目标（仅 1 段）
2. 范围定义
   - In Scope
   - Out of Scope
3. 角色与关键场景（按 P0/P1）
4. 功能需求 `FR-*`
   - 描述
   - 优先级
   - 前置条件
   - 业务规则
5. 验收标准 `AC-*`
   - 与 FR 可追踪映射
   - 可测试、可量化
   - 至少覆盖正常流+异常流
6. 非功能约束（性能/稳定性/安全/可观测）
7. 依赖与风险（含回退策略）
8. 反例清单（哪些行为必须判定为不通过）
9. 变更控制（谁可改、何时可改、如何改）

禁止模糊语句:
- "优化一下"
- "支持更多"
- "后续再看"
- "视情况而定"

## Phase 3: FR-AC 映射与质量门禁

输出 `## FR-AC 映射表`:

| FR | AC | 覆盖说明 | 状态 |
|----|----|----------|------|
| FR-1 | AC-1, AC-2 | 主流程+异常 | pass/fail |

门禁:

- 每个 FR 至少一个 AC
- 每个 AC 仅归属明确 FR
- 异常场景至少 3 类（权限/网络/数据异常 或等价场景）

若门禁失败，回到 Phase 2 重写，不得继续。

新增门禁:
- 所有 `Assumptions` 必须有去向（确认/拒绝/延后）
- 关键冲突必须有明确裁决（记录在 `Decision Log`）

## Phase 4: Runner Ready 转换

输出 `## Execution Plan (Runner Ready)`，格式必须可被 `android-worktree-runner` 解析:

```markdown
### Task 1: <标题>
**优先级:** P0
**依赖:** Task 0 / 无
**涉及文件:** <模块或路径>

**Step 1:** ...
**Step 2:** ...

**DoD:**
- ...

**验证命令:**
- ./gradlew assembleDebug --no-daemon
- ./gradlew lintDebug --no-daemon
- ./gradlew testDebugUnitTest --no-daemon
```

要求:
- 所有 Task 都可独立完成并可验收
- 依赖关系明确（`depends_on` 或 `依赖`）
- Step 为可执行动作，不写抽象口号
- 每个 Task 必须注明“影响范围”（模块/页面/接口）
- 每个 Task 必须注明“失败回滚点”（撤回策略）

## Phase 5: 交付与落盘

默认输出顺序固定:

1. `## PRD`
2. `## FR-AC 映射表`
3. `## Execution Plan (Runner Ready)`
4. `## Open Questions`（无则写“无”）

若用户确认保存:

```bash
TS=$(date +%Y%m%d-%H%M%S)
SLUG="prd-refine-$TS"
PRD_FILE="docs/plans/${SLUG}.md"
STATUS_FILE="docs/plans/${SLUG}-status.json"
```

`STATUS_FILE` 最小字段:

```json
{
  "schema_version": 1,
  "type": "prd-refine",
  "run_id": "<RUN_ID>",
  "prd_version": "v1.0",
  "freeze": true,
  "approved": false,
  "approved_at": null
}
```

## Handoff Rules

- 仅当 `approved=true` 才允许建议进入 `android-worktree-runner import`
- 若存在未解决 `Open Questions`，禁止交接 runner
- 交接时必须附带 PRD 文件路径与版本时间戳
- 若 `freeze=true`，后续需求变更必须先生成 `Change Request` 再更新 Plan

## Output Contract (固定块)

最终输出必须包含以下区块，缺一不可:

1. `## PRD`
2. `## FR-AC 映射表`
3. `## Decision Log`（冲突裁决、权衡依据）
4. `## Execution Plan (Runner Ready)`
5. `## Change Control`（freeze 与 CR 规则）
6. `## Open Questions`

## 与现有 Skill 的边界

- 上游 `android-brainstorm`: 负责发散与方案探索
- 当前 `android-prd-refine`: 负责收敛与约束落地
- 下游 `android-autoplan` / `android-worktree-runner`: 负责任务执行与验证

## Capture Learnings

```bash
bash "$SHARED_BIN/bin/android-learnings-log" '{"skill":"prd-refine","type":"pattern","key":"KEY","insight":"INSIGHT","confidence":8,"source":"observed","files":[]}'
```
