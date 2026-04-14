---
name: android-git-surgery
description: |
  Git 疑难杂症处理: 合并冲突/历史重写/cherry-pick/worktree 清理。
---

# Git Surgery

**调用:** `/android-git-surgery`

## 常见问题

| 问题 | 解决方案 |
|------|---------|
| 合并冲突 | `git diff --name-only --diff-filter=U` → 手动解决 → `git add` → `git commit` |
| 误提交 | `git reset HEAD~1` (保留变更) / `git revert <commit>` (撤销) |
| 历史重写 | `git rebase -i HEAD~N` |
| cherry-pick | `git cherry-pick <commit>` |
| worktree 清理 | `git worktree remove <path> --force` |
| 分支混乱 | `git branch -vv` 查看追踪关系 |

## 操作流程

1. 用户描述问题
2. 诊断: 运行相 git 命令查看状态
3. 展示解决方案选项
4. AskUserQuestion 确认后执行
5. 验证结果

## 安全规则

- 任何 destructive 操作 (force push, reset --hard) 前必须确认
- 重写历史前建议备份分支
- worktree 清理前确认无未提交变更
