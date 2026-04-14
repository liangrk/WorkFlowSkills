---
name: android-checkpoint
description: |
  跨 session 状态持久化。保存/恢复 worktree-runner 进度, 防止 /clear 丢失上下文。
---

# Checkpoint

**调用:** `/android-checkpoint save` | `restore` | `status`

## 存储

`.claude/android-checkpoint/checkpoint-<timestamp>.json`

## save

```bash
_R="$(git worktree list | head -1 | awk '{print $1}')"
TASKS_FILE="$_R/.claude/android-worktree-runner/tasks.json"
```

保存内容:
- tasks.json 完整状态
- 当前 worktree 信息
- 进行中的任务 + 步骤
- 已完成的验证结果
- 待处理事项

```json
{
  "timestamp": "ISO-8601",
  "tasks_file_snapshot": "<tasks.json 内容>",
  "current_task": "<任务ID>",
  "current_step": "<步骤描述>",
  "worktree_path": "<路径>",
  "branch": "<分支>",
  "pending_issues": []
}
```

## restore

```bash
# 列出所有检查点
ls .claude/android-checkpoint/checkpoint-*.json | sort -r

# 读取最近的或指定的检查点
cat .claude/android-checkpoint/checkpoint-<timestamp>.json
```

恢复后:
- 写入 tasks.json
- 进入 worktree
- 显示上次中断位置
- 继续执行

## status

```
=== 检查点状态 ===
最近: checkpoint-20260413-150000.json
任务: plan/auth-login-flow
进度: 任务 2/5 进行中
分支: plan/auth-login-flow
```
