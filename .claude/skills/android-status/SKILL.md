---
name: android-status
description: |
  全局状态仪表盘: git/worktree/checkpoint/PR/build 一览。
---

# Status

**调用:** `/android-status`

## 采集

```bash
SHARED_BIN=$(bash android-resolve-path 2>/dev/null || true)

# git 状态
git status --short 2>/dev/null | head -20
git log --oneline -5 2>/dev/null

# worktree
git worktree list 2>/dev/null

# checkpoint
ls .claude/android-checkpoint/*.json 2>/dev/null | sort -r | head -5

# tasks
if [ -f "$_R/.claude/android-worktree-runner/tasks.json" ]; then
  python3 -c "
import json
data = json.load(open('$_R/.claude/android-worktree-runner/tasks.json'))
for pid, p in data.get('plans',{}).items():
    done = sum(1 for t in p['tasks'] if t['status']=='completed')
    total = len(p['tasks'])
    print(f\"  {p['title']}: {done}/{total} [{p['status']}]\")
" 2>/dev/null
fi

# PR
gh pr list 2>/dev/null | head -10
```

## 展示

```
=== Android Skill 状态 ===
Git: 3 文件变更 | HEAD: abc1234
Worktree: 2 活跃
  - plan/auth-login-flow
  - plan/user-profile
Checkpoints: 2 可用
  - checkpoint-20260413-150000
Plan 进度:
  - 登录流程: 2/5 [进行中]
  - 用户资料: 0/3 [待开始]
PR: 1 待合并
  - #42 feat: login flow
```
