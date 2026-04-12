# 思考: android-autoplan 状态持久化

> 生成于 2026-04-12 | android-brainstorm skill
> 项目: WorkFlowSkills | 分支: master
> 来源: 新建
> 状态: 审查通过

## 目标

- **一句话目标:** android-autoplan 的每一条调用路径都必须将 plan 状态持久化，使 android-status 可查、中断/clear 后可恢复执行。
- **成功标准:** /clear 后运行 /android-status 能看到已批准但未执行的 plan，并提示恢复路径。
- **范围边界:** autoplan 的所有入口路径（全流程/review/split/外部 plan 执行）。
- **反边界:** 不改动 worktree-runner 的核心执行逻辑和 tasks.json 格式。

## 问题根因

autoplan → runner 的衔接是内存级 Skill 调用，没有持久化状态。一旦 /clear 或 session 中断：
- autoplan 的审查结论和"已批准"状态丢失
- worktree-runner 从未被调用（或只执行了一半）
- android-status 读不到任何进行中的 plan（因为 tasks.json 还没创建）

## 方案方向

### 方向 A+B 结合: Write-Once Plan Status (选定)

- **思路:** autoplan 审批完成后生成 write-once 的 `docs/plans/<slug>-status.json`，作为"审批凭证"。runner 读取但不修改此文件，执行状态仍由 tasks.json 管理。status 交叉验证两个文件。
- **优点:** 零状态同步问题（plan-status.json 不可变）；职责清晰（autoplan 管审批，runner 管执行）；改动面小。
- **代价:** 新增一个文件格式；status 需增加一个数据源。

### 方向 A: 复用 tasks.json (排除)

- 直接写 runner 格式，零新文件。
- 问题: autoplan 耦合 runner 内部格式；审查阶段状态无法跟踪。

### 方向 B: 独立 plan-lifecycle 系统 (排除)

- 独立状态系统，职责最清晰。
- 问题: 改动量大，需要同时改 autoplan/runner/status 三个 skill。

### 方向 C: 升级 checkpoint (排除)

- 扩展现有 checkpoint 机制。
- 问题: checkpoint 的设计初衷是快照恢复，不是状态查询，语义不匹配。

## 详细设计

### plan-status.json 格式 (Write-Once)

```json
{
  "version": 1,
  "plan_id": "plan-20260412-143000",
  "title": "用户登录功能",
  "plan_file": "docs/plans/user-login.md",
  "source": "autoplan",
  "status": "approved",
  "phase": "final-approval",
  "created_at": "2026-04-12T14:30:00Z",
  "approved_at": "2026-04-12T15:00:00Z",
  "review_summary": {
    "mechanical_decisions": 5,
    "taste_decisions": 2,
    "user_challenges": 0
  }
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| version | number | 格式版本，当前为 1 |
| plan_id | string | plan 唯一标识，格式 `plan-YYYYMMDD-HHMMSS` |
| title | string | plan 标题 |
| plan_file | string | plan 文件相对路径 |
| source | string | 产生来源: autoplan / investigate / fix / manual |
| status | string | 固定为 `approved`（write-once，不会变更） |
| phase | string | 审批完成时的阶段: final-approval / split-only / review-only |
| created_at | string | ISO 8601 UTC 创建时间 |
| approved_at | string | ISO 8601 UTC 审批时间 |
| review_summary | object | 审查摘要（机械决策/品味决策/用户挑战数量） |

### 生命周期状态推断 (status 仪表盘)

```
IF tasks.json 存在且 plan_id 匹配:
  → 用 tasks.json 的聚合状态 (全部 completed = completed, 有 in-progress = executing, 全 pending = queued)
ELIF plan-status.json 存在且 plan_file 存在:
  → 显示 "已批准，待执行"
ELIF plan 文件存在但无 status 文件:
  → 显示 "plan 已就绪，未审批"
ELSE:
  → 不显示
```

### 恢复流程

1. `/clear` 后运行 `/android-status`
2. status 扫描 `docs/plans/*-status.json`
3. 发现 `status: "approved"` 但 tasks.json 中无匹配 plan
4. 仪表盘显示: "已批准待执行: 用户登录功能 → `/android-worktree-runner import docs/plans/user-login.md`"

### 各入口路径的持久化时机

| 入口路径 | 持久化时机 | plan-status.json 的 phase |
|---------|-----------|--------------------------|
| 全流程 (split → review → approve) | 最终审批通过后 | `final-approval` |
| `review <plan-file>` (审查外部 plan) | 审查通过后 | `review-only` |
| `split <需求>` (仅拆分不审查) | 拆分完成后，用户确认 | `split-only` |
| 外部 plan (investigate/fix 产出) | 用户选择"批准并执行"时 | `review-only` |

## 改动清单

### android-autoplan (核心改动)

1. **最终审批阶段:** 用户选择"批准并执行"或"仅保存"时，生成 `docs/plans/<slug>-status.json`
2. **plan_id 生成:** 使用 `plan-YYYYMMDD-HHMMSS` 格式，与 runner 的 plan_id 格式对齐
3. **传递给 runner:** 调用 runner 时传递 plan-status.json 路径（可选，runner 也可以自行扫描）
4. **所有入口路径:** review/split/全流程 均在完成时生成 plan-status.json

### android-worktree-runner (小改动)

1. **import 阶段:** 检查是否存在对应的 plan-status.json，若有则读取 source/review_summary 丰富 tasks.json 元数据
2. **不修改 plan-status.json:** 遵循 write-once 原则

### android-status (读取改动)

1. **新增数据源:** 扫描 `docs/plans/*-status.json`
2. **交叉验证逻辑:** 实现上述状态推断算法
3. **仪表盘展示:** 新增"已批准待执行"状态行
4. **恢复提示:** 检测到 approved 但未执行的 plan 时，提示 import 命令

## 独立视角

- **盲点:** 并发写入风险 → 已通过 write-once 原则解决
- **反直觉洞察:** plan-status.json 应该是 write-once 的"审批凭证"，不是可变的"状态追踪器"
- **48h 建议:** 只改 runner 的 tasks.json header → 拒绝，不满足用户需求
- **被忽略的风险:**
  - Windows 路径含中文/空格 → slug 生成时确保 ASCII
  - plan 文件被删除导致悬空引用 → status 交叉验证时检查 plan_file 是否存在
  - 幽灵 plan → status 通过 tasks.json 聚合推断实际状态

## 前提

1. plan-status.json 是 write-once → 状态: 确认
2. tasks.json 仍是执行阶段唯一真相源 → 状态: 确认
3. plan_id 格式需要对齐 → 状态: 确认
4. status 能做交叉验证 → 状态: 确认（需要改 status skill）

## 实施记录

所有 4 个 skill 的改动已完成。以下为实施后审查发现的 8 个问题及修复状态:

| # | 优先级 | 问题 | 修复状态 |
|---|--------|------|---------|
| 1 | HIGH | autoplan split-only 路径缺少 status 生成指令 | 已修复: 在参数处理 split 分支添加明确指令 |
| 2 | HIGH | autoplan review 外部 plan 时 source 固定为 autoplan，无法识别 investigate/fix 来源 | 已修复: 添加 plan 文件头部 `> 来源:` 检测规则 |
| 3 | MED | runner 步骤 4.6 缺少 plan_id 显式提取代码 | 已修复: 添加 python3 提取代码块 |
| 4 | MED | status 0.3.5 未与 tasks.json 交叉比对，无法区分已导入/未导入 | 已修复: 脚本增加 tasks.json 读取和 plan_id 过滤 |
| 5 | LOW | autoplan source 表缺少 `manual` 取值 | 已修复: 添加 manual 行 |
| 6 | LOW | autoplan 执行选项 A/B 措辞歧义 (C/D 未说明) | 已修复: 添加 C/D 为回滚操作的说明 |
| 7 | LOW | runner tasks.json schema 未声明 source/approved_at/review_summary | 已修复: 数据结构定义中添加三个可选字段 |
| 8 | LOW | runner 缺少 source 与 plan_source.type 的区别说明 | 已修复: 步骤 4.6 添加映射对比表 |

## 下一步

1. 修改 android-autoplan SKILL.md: 在最终审批阶段添加 plan-status.json 生成逻辑 ✓
2. 修改 android-worktree-runner SKILL.md: import 阶段读取 plan-status.json ✓
3. 修改 android-status SKILL.md: 增加 plan-status.json 扫描和交叉验证 ✓
4. 测试: 全流程 / review-only / split-only / 外部 plan 四条路径
