---
name: android-fix
description: Use when there are known fix items (from qa/review/investigate/manual list) and you need to convert them into a worktree-runner executable plan.
voice-triggers:
  - "修复"
  - "实施修复"
  - "fix findings"
  - "修复结论"
  - "修复问题"
invocation: /android-fix
args:
  - "<file>"
  - "--resume <plan-file>"
---

# Android Fix

**启动声明:** "我正在使用 android-fix skill。"
**定位:** 只实施已知修复，不做诊断。诊断使用 `android-investigate` / `android-brainstorm`。

## 调用

```bash
/android-fix
/android-fix <file>
/android-fix --resume <plan-file>
```

参数行为:
- 无参数: 从当前对话提取修复项
- `<file>`: 从文件读取修复项
- `--resume`: 跳过 Phase 0-4，直接交接 worktree-runner

## Phase 0: 输入检测与早退

1. 提取修复项（对话或文件）
2. 可执行修复项必须同时满足:
   - 有具体文件路径
   - 有具体变更描述
3. 早退条件:
   - 修复项 = 0: 退出并建议先排查
   - 修复项 = 1 且改动极小: 建议手修，询问是否继续

文件模式最小校验:

```bash
if [ ! -f "$1" ]; then
  echo "错误: 文件不存在: $1"
  exit 1
fi
cat "$1"
```

## Phase 1: 确认修复项

展示标准化清单后让用户确认（可增删改）:

```text
#1 [P0] <file>
   <change>
```

已有优先级（P0/P1/P2/P3）保留；无优先级进入 Phase 2 自动分类。

## Phase 2: 分类、优先级、分组

分类:
- `security`: 泄漏、权限、敏感信息
- `reliability`: 崩溃/流程中断风险
- `consistency`: 规则统一、重复逻辑收敛
- `performance`: 性能/资源优化
- `cosmetic`: 风格与文档

优先级:
- `P0`: security
- `P1`: reliability
- `P2`: consistency + performance
- `P3`: cosmetic

分组规则:
- 同文件多修复 -> 合并同一 task
- 强依赖修复 -> 合并并写明顺序
- 无关修复 -> 独立 task

## Phase 3: 依赖与执行模式

为任务建立 `depends_on`:
- 有依赖: 交给 wave parallel
- 无依赖: 可并行
- 全链式依赖: 串行

默认交给 `android-worktree-runner` 自动选择波次并行/串行。

## Phase 4: 生成 Plan

写入:

```bash
PLAN_FILE="docs/plans/fix-$(date +%Y%m%d-%H%M%S).md"
```

格式要求（runner 可解析）:
- `### Task N`
- 优先级、分类、涉及文件
- `依赖` 或 `depends_on`
- 有序步骤列表

最小校验:

```bash
if [ -f "$PLAN_FILE" ]; then
  echo "Plan 文件已生成: $PLAN_FILE"
else
  echo "错误: Plan 文件生成失败"
  exit 1
fi
```

## Phase 5: 交接 Runner

调用 `android-worktree-runner`:

```text
import <PLAN_FILE>
```

Runner 负责:
- worktree 创建
- 任务执行与验证（build/lint/test）
- 提交与状态回写

## 结束建议

修复完成后建议顺序:
1. `/android-qa`
2. `/android-code-review`
3. `/android-ship`

## Skill 衔接

上游: `android-investigate`, `android-brainstorm`, `android-code-review`, `android-qa`  
下游: `android-worktree-runner`, `android-ship`

## 异常处理

| 场景 | 处理 |
|------|------|
| 无可执行修复项 | 早退，建议先排查 |
| 仅 1 个小修复 | 建议直接手修 |
| 修复项无文件路径 | 标记为待定位 |
| plan 生成失败 | 报错退出 |
| 非 git 仓库 | 报错退出 |
| 文件参数不存在 | 报错退出 |
