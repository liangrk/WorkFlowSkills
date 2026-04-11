---
name: android-learn
description: |
  Android 学习记录管理 -- 查看、搜索、添加、清理跨 session 知识积累。
  基于 android-learnings-log / android-learnings-search 工具，
  以 JSONL 格式存储在 ~/.android-skills/projects/<slug>/learnings.jsonl。
  支持置信度衰减、去重、跨项目搜索。
invocation: /android-learn [search <keyword> | add | prune | stats]
args: [subcommand]
voice-triggers:
  - "学习记录"
  - "添加经验"
  - "搜索知识"
  - "清理学习"
  - "学习统计"
---

# Android Learn

## 概述

跨 session 学习记录管理系统。将开发过程中积累的模式、陷阱、偏好、架构决策等
知识以结构化 JSONL 格式持久化存储，支持按类型/关键词搜索、置信度衰减、
去重、跨项目知识复用。

**启动时声明:** "我正在使用 android-learn skill。"

**零外部依赖:** 仅使用 Claude Code 原生工具 (Read、Write、Edit、Grep、Glob、Bash)
和 android-shared/bin/ 下的辅助脚本。不依赖 gstack、browse、Codex、Figma MCP。

## 调用方式

```bash
/android-learn                  # 显示全部学习记录 (Phase 2)
/android-learn search <keyword> # 搜索 (Phase 3)
/android-learn add              # 交互式添加 (Phase 4)
/android-learn prune            # 清理过期条目 (Phase 5)
/android-learn stats            # 统计信息 (Phase 6)
```

**参数处理:**
- 无参数或空: 路由到 Phase 2 显示全部
- `search <keyword>`: 路由到 Phase 3 搜索
- `add`: 路由到 Phase 4 交互式添加
- `prune`: 路由到 Phase 5 清理过期
- `stats`: 路由到 Phase 6 统计信息

---

## 存储规范

### 存储路径

```
~/.android-skills/projects/<project-slug>/
  └── learnings.jsonl
```

- `project-slug`: 从 `git remote get-url origin` 提取仓库名 (去 .git 后缀)，
  无 remote 时使用 `basename(pwd)`
- 每行一条 JSON 记录，追加写入

### 记录格式

```json
{
  "skill": "android-tdd",
  "type": "pattern",
  "key": "use-composable-preview-for-ui-testing",
  "insight": "Compose Preview 可替代部分 Espresso UI 测试，启动速度提升 10 倍",
  "confidence": 8,
  "source": "observed",
  "files": ["app/src/main/java/com/example/MyScreen.kt"],
  "ts": "2026-04-10T14:30:00Z"
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| skill | string | 否 | 产生该学习的 skill 名称 |
| type | string | 是 | 学习类型，见下方枚举 |
| key | string | 是 | kebab-case 短标识，用于去重 |
| insight | string | 是 | 一句话描述核心内容 |
| confidence | number | 是 | 置信度 1-10 |
| source | string | 是 | 来源: observed / user-stated / inferred |
| files | string[] | 否 | 相关文件路径列表 |
| ts | string | 否 | ISO 8601 UTC 时间戳 (自动注入) |

### type 枚举

| 值 | 含义 |
|----|------|
| pattern | 可复用的编码模式 |
| pitfall | 常见陷阱 / 反模式 |
| preference | 项目/团队偏好 |
| convention | 项目特有约定（命名、架构惯例等） |
| architecture | 架构决策 |
| tool | 工具使用技巧 |
| technique | 调试/开发技巧 |
| operational | 运维 / 构建相关 |

### source 枚举

| 值 | 含义 | 置信度衰减 |
|----|------|-----------|
| observed | 直接观察到的行为 | 每 30 天 -1 |
| user-stated | 用户明确说明 | 不衰减 |
| inferred | 间接推断 | 每 30 天 -1 |

### 置信度衰减规则

- `observed` 和 `inferred` 来源的学习: 每 30 天置信度 -1，最低为 0
- `user-stated` 来源的学习: 不衰减
- 衰减仅在搜索时计算，不修改原始数据

---

## Phase 0: 环境检测

**执行条件:** 所有子命令均先执行此阶段。

### 步骤

1. 检查 `~/.android-skills/` 目录是否存在:
   ```bash
   [ -d "$HOME/.android-skills" ] && echo "EXISTS" || echo "MISSING"
   ```
   - 若 MISSING: 创建目录 `mkdir -p ~/.android-skills/projects`，输出 "已创建学习存储目录"

2. 计算当前项目 slug:
   ```bash
   SLUG=$(git remote get-url origin 2>/dev/null | sed 's|.*/||;s|\.git$||;s|/$||' | tail -1)
   [ -z "$SLUG" ] && SLUG=$(basename "$(pwd)")
   echo "$SLUG"
   ```

3. 检查 learnings.jsonl 是否存在及条目数:
   ```bash
   LEARNINGS_FILE="$HOME/.android-skills/projects/$SLUG/learnings.jsonl"
   if [ -f "$LEARNINGS_FILE" ]; then
     COUNT=$(wc -l < "$LEARNINGS_FILE" | tr -d ' ')
     echo "FILE_EXISTS: $COUNT entries"
   else
     echo "FILE_MISSING"
   fi
   ```

   若 FILE_MISSING:
   1. 运行预加载脚本:
      ```bash
      _R="$(git worktree list | head -1 | awk '{print $1}')"
      SHARED_BIN="$_R/.claude/skills/android-shared/bin"
      [ ! -d "$SHARED_BIN" ] && SHARED_BIN="$HOME/.claude/skills/android-shared/bin"
      bash "$SHARED_BIN/android-learnings-bootstrap"
      ```
   2. 重新检查条目数

4. 输出环境摘要:
   ```
   [android-learn] 环境检测完成
   - 项目: <slug>
   - 存储路径: ~/.android-skills/projects/<slug>/learnings.jsonl
   - 现有条目: <N> 条
   ```

---

## Phase 1: 路由

根据 `args` 参数路由到对应 Phase:

| args 内容 | 目标 Phase |
|-----------|-----------|
| 空 / 无参数 | Phase 2: 显示全部 |
| `search <keyword>` | Phase 3: 搜索 |
| `add` | Phase 4: 交互式添加 |
| `prune` | Phase 5: 清理过期 |
| `stats` | Phase 6: 统计 |

若参数无法识别，输出帮助信息:
```
[android-learn] 未知命令: <args>
可用命令:
  /android-learn                  显示全部学习记录
  /android-learn search <keyword> 搜索学习记录
  /android-learn add              交互式添加学习记录
  /android-learn prune            清理过期条目
  /android-learn stats            显示统计信息
```

---

## Phase 2: 显示全部

### 步骤

1. 运行搜索脚本:
   ```bash
   _R="$(git worktree list | head -1 | awk '{print $1}')"
   SHARED_BIN="$_R/.claude/skills/android-shared/bin"
   [ ! -d "$SHARED_BIN" ] && SHARED_BIN="$HOME/.claude/skills/android-shared/bin"
   bash "$SHARED_BIN/android-learnings-search" --limit 50
   ```

2. 若输出为 `LEARNINGS: 0`，显示:
   ```
   [android-learn] 暂无学习记录。
   使用 /android-learn add 添加第一条记录。
   ```

3. 若有结果，按类型分组显示:
   ```
   [android-learn] 共 N 条学习记录

   ## pattern (模式)
   - [key1] (confidence: 8/10, observed, 2026-04-10)
     insight text
   ...

   ## pitfall (陷阱)
   - [key2] (confidence: 6/10, inferred, 2026-03-15)
     insight text
   ...

   ## preference (偏好)
   ...
   ```

---

## Phase 3: 搜索

### 步骤

1. 从 args 中提取关键词: `search` 后面的所有文本作为 `<keyword>`

2. 运行跨项目搜索:
   ```bash
   _R="$(git worktree list | head -1 | awk '{print $1}')"
   SHARED_BIN="$_R/.claude/skills/android-shared/bin"
   [ ! -d "$SHARED_BIN" ] && SHARED_BIN="$HOME/.claude/skills/android-shared/bin"
   bash "$SHARED_BIN/android-learnings-search" \
     --query "<keyword>" \
     --limit 20 \
     --cross-project
   ```

3. 若输出为 `LEARNINGS: 0 matches`，显示:
   ```
   [android-learn] 未找到与 "<keyword>" 相关的学习记录。
   ```

4. 若有结果，直接展示搜索脚本输出 (已包含 cross-project 标记)

---

## Phase 4: 交互式添加

### 步骤

依次使用 AskUserQuestion 收集以下信息:

#### 4.1 收集 type

```
选择学习类型:
1. pattern (可复用的编码模式)
2. pitfall (常见陷阱 / 反模式)
3. preference (项目/团队偏好)
4. architecture (架构决策)
5. tool (工具使用技巧)
6. operational (运维 / 构建相关)
```

将用户选择映射为英文枚举值。

#### 4.2 收集 key

```
输入学习标识 (kebab-case 短标识，如 use-hilt-for-di):
```

验证: 只允许小写字母、数字、连字符。若不符合格式，提示重新输入。

#### 4.3 收集 insight

```
输入学习内容 (一句话描述核心发现):
```

#### 4.4 收集 confidence

```
输入置信度 (1-10，1=不确定，10=非常确定):
```

验证: 必须为 1-10 的整数。若不符合，提示重新输入。

#### 4.5 收集 source

```
选择来源:
1. observed (直接观察到的行为)
2. user-stated (用户明确说明)
3. inferred (间接推断)
```

将用户选择映射为英文枚举值。

#### 4.6 收集 files (可选)

```
输入相关文件路径 (逗号分隔，留空跳过):
```

若非空，按逗号分割为列表。

#### 4.7 确认并写入

1. 构造 JSON 字符串:
   ```json
   {
     "skill": "android-learn",
     "type": "<type>",
     "key": "<key>",
     "insight": "<insight>",
     "confidence": <confidence>,
     "source": "<source>",
     "files": [<files>]
   }
   ```
   注意: `ts` 字段由 `android-learnings-log` 脚本自动注入，不需要手动添加。
   若 files 为空列表，则省略 files 字段。

2. 显示确认信息:
   ```
   即将添加学习记录:
   - 类型: <type>
   - 标识: <key>
   - 内容: <insight>
   - 置信度: <confidence>/10
   - 来源: <source>
   ```

3. 调用脚本写入:
   ```bash
   _R="$(git worktree list | head -1 | awk '{print $1}')"
   SHARED_BIN="$_R/.claude/skills/android-shared/bin"
   [ ! -d "$SHARED_BIN" ] && SHARED_BIN="$HOME/.claude/skills/android-shared/bin"
   bash "$SHARED_BIN/android-learnings-log" '<json>'
   ```

4. 若输出以 `OK:` 开头，显示:
   ```
   [android-learn] 学习记录已保存。
   ```
   否则显示错误信息。

---

## Phase 5: 清理过期

### 步骤

1. 读取所有学习记录:
   ```bash
   LEARNINGS_FILE="$HOME/.android-skills/projects/$SLUG/learnings.jsonl"
   if [ ! -f "$LEARNINGS_FILE" ]; then
     echo "[android-learn] 无学习记录可清理。"
     exit 0
   fi
   cat "$LEARNINGS_FILE"
   ```

2. 对每条记录，检查 `files` 字段引用的文件是否仍然存在:
   - 对 files 列表中的每个路径，使用 Glob 工具检查文件是否存在
   - 若 files 为空或全部存在，标记为 "正常"
   - 若有文件不存在，标记为 "可疑"

3. 列出可疑条目:
   ```
   [android-learn] 发现 N 条可疑条目 (引用的文件已不存在):

   #1 [key] (type, ts)
     insight
     缺失文件: path1, path2

   #2 ...
   ```

4. 若无可疑条目:
   ```
   [android-learn] 所有学习记录引用的文件均存在，无需清理。
   ```

5. 若有可疑条目，使用 AskUserQuestion 询问:
   ```
   是否删除以上可疑条目?
   1. 全部删除
   2. 逐条确认
   3. 取消
   ```

6. 根据用户选择:
   - **全部删除**: 读取原文件，过滤掉可疑条目，写回
   - **逐条确认**: 逐条显示并询问是否删除
   - **取消**: 不执行任何操作

7. 写回时保持格式: 有效条目按原样逐行写入 learnings.jsonl (覆盖原文件)

8. 输出结果:
   ```
   [android-learn] 清理完成。删除 N 条，保留 M 条。
   ```

---

## Phase 6: 统计

### 步骤

1. 读取学习记录并计算统计信息:
   ```bash
   LEARNINGS_FILE="$HOME/.android-skills/projects/$SLUG/learnings.jsonl"
   if [ ! -f "$LEARNINGS_FILE" ]; then
     echo "[android-learn] 无学习记录。"
     exit 0
   fi
   python3 -c "
import json, sys
from datetime import datetime, timedelta

now = datetime.utcnow()
week_ago = now - timedelta(days=7)

total = 0
by_type = {}
recent = 0
conf_sum = 0
conf_count = 0

with open('$LEARNINGS_FILE') as f:
    for line in f:
        line = line.strip()
        if not line: continue
        try:
            e = json.loads(line)
            total += 1
            t = e.get('type', 'unknown')
            by_type[t] = by_type.get(t, 0) + 1
            ts = e.get('ts', '')
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace('Z', '+00:00')).replace(tzinfo=None)
                    if dt >= week_ago:
                        recent += 1
                except: pass
            c = e.get('confidence')
            if c is not None:
                conf_sum += c
                conf_count += 1
        except: pass

avg_conf = conf_sum / conf_count if conf_count > 0 else 0

print(f'TOTAL: {total}')
print(f'RECENT_7D: {recent}')
print(f'AVG_CONFIDENCE: {avg_conf:.1f}')
print('TYPE_DISTRIBUTION:')
for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
    print(f'  {t}: {c}')
"
   ```

2. 格式化输出:
   ```
   [android-learn] 学习记录统计

   - 总条目数: N
   - 最近 7 天新增: M
   - 平均置信度: X.X/10

   按类型分布:
     pattern:     N
     pitfall:     N
     preference:  N
     architecture: N
     tool:        N
     operational: N
   ```

---

## 错误处理

| 场景 | 处理方式 |
|------|---------|
| learnings.jsonl 不存在 | 提示使用 /android-learn add 添加 |
| JSON 解析失败 (log) | 显示错误信息，不写入 |
| python3 不可用 | 显示错误，建议安装 python3 |
| 项目 slug 无法确定 | 回退到 basename(pwd) |
| 无搜索结果 | 显示 "未找到相关记录" |

## 注意事项

- 所有写入操作均为追加模式，不会覆盖已有数据 (prune 除外)
- `ts` 字段由脚本自动注入，无需手动填写
- 搜索时的置信度衰减仅影响排序，不修改原始数据
- 跨项目搜索时会在结果中标记 `[cross-project]`
- prune 操作会直接修改 learnings.jsonl 文件，操作前请确认
