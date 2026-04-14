---
name: android-learn
description: |
  跨 session 知识积累。记录/搜索/清理学习记录。
---

# Learn

**调用:** `/android-learn` | `search <关键词>` | `add` | `prune` | `stats`

## search

```bash
_R="$(git worktree list | head -1 | awk '{print $1}')"
SHARED_BIN="$_R/.claude/skills/android-shared/bin"
[ ! -d "$SHARED_BIN" ] && SHARED_BIN="$HOME/.claude/skills/android-shared/bin"

bash "$SHARED_BIN/android-learnings-search" --limit 10 2>/dev/null
```

按类型搜索: `--type pitfall|pattern|technique`

## add

AskUserQuestion 收集信息:
- 关键内容 (一句话描述)
- 类型 (pitfall/pattern/technique/preference)
- 置信度 (1-10)
- 来源 (observed/user-stated/inferred)

```bash
bash "$SHARED_BIN/android-learnings-log" '{"skill":"learn","type":"TYPE","key":"KEY","insight":"INSIGHT","confidence":8,"source":"observed","files":[]}'
```

## prune

```bash
# 显示统计
bash "$SHARED_BIN/android-learnings-search" --stats 2>/dev/null

# 清理低置信度或过期记录
# 询问用户是否清理
```

## stats

```
=== 学习记录统计 ===
总数: N 条
  - pitfall: N
  - pattern: N
  - technique: N
最近: <最新记录>
最常搜索: <TOP 5 关键词>
```
