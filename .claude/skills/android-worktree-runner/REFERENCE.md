# Android Worktree Runner — Reference

> 本文件包含不常需要的参考章节。仅在需要时 Read 此文件。

---

## 缺失工具

<MISSING_TOOLS 列表>

## 当前环境信息
- OS: <操作系统>
- 项目路径: <WORKTREE_PATH>
- ANDROID_HOME: <值>
- 已安装的工具: <列出可用的>

## 安装指南

**权限预检 (必须首先执行):**
```bash
# 检测是否有管理员/root 权限
HAS_SUDO=false
if sudo -n true 2>/dev/null; then HAS_SUDO=true; fi

# Windows: 检测 winget 是否可用
HAS_WINGET=false
if command -v winget &>/dev/null; then HAS_WINGET=true; fi

# macOS: 检查 brew 是否可用
HAS_BREW=false
if command -v brew &>/dev/null; then HAS_BREW=true; fi

echo "HAS_SUDO: $HAS_SUDO"
echo "HAS_WINGET: $HAS_WINGET"
echo "HAS_BREW: $HAS_BREW"
```

**平台策略:**
- **Windows:** 无 sudo 概念。优先 `winget`，不可用则直接标记 `blocked` 提供手动安装指南。
- **Linux:** 无 sudo 时直接标记 `blocked`，不尝试安装。
- **macOS:** brew 通常可用，直接安装。

**安装优先级:** JDK > CMake/NDK > Bazel (Bazel 本身是 JVM 程序，依赖 JDK)

按以下优先级尝试安装:

### Bazel
1. 检查是否有 bazelisk (bazel 版本管理器): `bazelisk version`
2. 尝试通过包管理器安装:
   - macOS: `brew install bazelisk`
   - Linux (Ubuntu/Debian): `sudo apt install bazel` 或下载 bazelisk 二进制
   - Windows: `choco install bazel` 或下载 bazelisk
3. 如果 bazelisk 不可用，尝试下载 Bazel 二进制:
   - 从 https://github.com/bazelbuild/bazel/releases 下载对应平台的安装包
4. 安装后验证: `bazel --version`

### CMake
1. Android SDK 自带的 CMake: 检查 $ANDROID_HOME/cmake/ 下是否有版本
2. 如果有，将其加入 PATH: `export PATH="$ANDROID_HOME/cmake/<version>/bin:$PATH"`
3. 如果没有，通过包管理器安装

### JDK
1. 检查已安装的 JDK: `java -version`
2. Android 项目通常需要 JDK 17+
3. macOS: `brew install openjdk@17`
4. Linux: `sudo apt install openjdk-17-jdk`
5. Windows: 从 Adoptium 下载

## 输出

安装完成后，**必须**按以下结构化格式输出 (主 agent 需要解析此格式来传递环境变量):

```
=== 工具安装结果 ===
bazel|installed|/usr/local/bin/bazel|7.2.1
cmake|installed|/usr/local/bin/cmake|3.30.5
jdk|installed|/Library/Java/JavaVirtualMachines/temurin-17/Contents/Home|17.0.12
ndk|skipped|NOT_INSTALLED|N/A
```

**格式说明:** 每行 `工具名|状态|路径|版本`，状态为 `installed`、`skipped` 或 `failed`。

> **主 agent 环境变量传递:** 解析 subagent 输出后，主 agent 需要将安装成功工具的路径
> 传递给后续的构建和测试命令。例如 JDK 安装到自定义路径时，需要设置 `JAVA_HOME`:
> ```bash
> # 根据 subagent 输出动态设置环境变量
> JAVA_HOME="<jdk_path_from_output>"
> export PATH="$JAVA_HOME/bin:$PATH"
> ```

---

## Phase 3: Plan 完成

### 步骤 1: 展示总结

**串行模式总结:**

```
Plan: <标题> — 已完成
══════════════════════════════════════
任务: N/N 已完成
提交: <commit hash 列表>
验证: 全部通过 / <备注>
分支: plan/<slug>
Worktree: .claude/worktrees/<plan-id>
```

**PRD 完成度总结 (仅当 plan.prd 不为 null 时显示):**

遍历所有验收标准，汇总各任务的验证结果:

```
[PRD 覆盖] 需求完成度: 8/10
- AC-1: ✓ (Task 2)
- AC-2: ✓ (Task 2)
- AC-3: ⚠ (Task 3, 部分实现)
- AC-4: ✓ (Task 4)
- AC-5: ✗ (未覆盖)
...
明确不做: 3 项均未实现 ✓
```

显示给用户，建议下一步:
- 若有 ✗ → 建议补充任务或创建新 plan
- 若有 ⚠ → 建议代码审查时重点关注
- 若全部 ✓ → 建议进入 ship 流程

若 plan.prd 为 null，跳过此总结。

**并行模式总结:**

```
Plan: <标题> — 已完成 (并行模式)
══════════════════════════════════════
执行模式: 波次并行 (N 波)
任务: N/M 已完成 (K 个被跳过/失败)
波次明细:
  Wave 1: 任务 1 ✓ (分支: wr/slug-task-1, commit: a1b2c3d)
  Wave 1: 任务 6 ✓ (分支: wr/slug-task-6, commit: e5f6g7h)
  Wave 2: 任务 2 ✓ (分支: wr/slug-task-2, commit: b2c3d4e)
  Wave 2: 任务 3 ✗ (构建失败)
  Wave 3: 任务 4 ✓ (分支: wr/slug-task-4, commit: c3d4e5f)
  Wave 4: 任务 5 ⊘ (被跳过，依赖任务 3 失败)
合并: plan/<slug> (最终 commit: d4e5f6g)
验证: 全部通过 / <备注>
```

**PRD 完成度总结 (仅当 plan.prd 不为 null 时显示):**

与串行模式相同的 PRD 覆盖总结逻辑:

```
[PRD 覆盖] 需求完成度: 8/10
- AC-1: ✓ (Task 2)
- AC-2: ✓ (Task 2)
- AC-3: ⚠ (Task 3, 部分实现)
- AC-4: ✓ (Task 4)
- AC-5: ✗ (未覆盖)
...
明确不做: 3 项均未实现 ✓
```

建议逻辑与串行模式一致。若 plan.prd 为 null，跳过。

### 步骤 2: 更新状态

设置 plan `status` 为 `"completed"`，设置 `timestamps.completed`。

**使用原子写入 + 文件锁:**
```bash
cat "$TASKS_FILE" | python -c "
import sys, json, datetime
data = json.loads(sys.stdin.read())
plan = data['plans']['<PLAN_ID>']
plan['status'] = 'completed'
plan['timestamps']['completed'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
print(json.dumps(data, indent=2, ensure_ascii=False))
" | bash "$SHARED_BIN/android-file-lock" "$TASKS_FILE.lock" \
    bash "$SHARED_BIN/android-json-atomic" "$TASKS_FILE"
```

**同步更新 `worktree-info.md`:**
- 将该 plan 从"进行中"部分**移动**到"已完成"部分
- 填入完成时间和最终 commit hash
- 任务进度更新为 `(N/N 已完成)`
- 状态更新为"已完成"

### 步骤 3: 后续操作

AskUserQuestion:
> Plan 已完成! 如何处理该 worktree?
> - A) 保留 — 我会手动审查和合并
> - B) 合并分支到 main
> - C) 创建 Pull Request
> - D) 删除 worktree (保留分支)
> - E) 返回 autoplan 修订 — 执行中发现了 plan 级别的问题

选 B: 从主 worktree 合并 plan 分支到 main。
选 C: 使用 `gh pr create` 为 plan 分支创建 PR。
选 D: 执行 `git worktree remove <路径>` 但保留分支。

**推荐后续流程 (完成代码变更后):**
> - F) 代码审查 — 调用 /android-code-review 审查代码质量
> - G) QA 测试 — 调用 /android-qa 验证功能正确性
> - H) 更新文档 — 调用 /android-document-release 同步文档
> - I) 全部执行 — 按顺序自动执行 F → G → H
> - J) 清理所有过期 worktree 和孤立分支

如果用户选择 I (全部执行):
1. 调用 android-code-review 审查当前分支
2. 如果 code-review 通过: 调用 android-qa 进行 QA
3. 如果 QA 通过: 调用 android-document-release 更新文档
4. 任何步骤发现阻塞问题: 中断并报告给用户

选 J: 执行全量 worktree 清理。先运行健康检查展示问题，确认后执行清理:
```bash
bash "$SHARED_BIN/android-worktree-health"
# 显示问题后确认
bash "$SHARED_BIN/android-worktree-health" --cleanup
```
清理完成后，同步更新 `worktree-info.md`，移除已清理 worktree 的条目。
同步更新 `tasks.json`，移除对应 plan 的条目（仅当 worktree 被移除时）。

选 E: 将执行中遇到的问题标注到 plan 文件中，然后调用
  android-autoplan 重新审查。流程:
  1. 从 `plan_source.ref` 获取原始 plan 文件名 (如 `2026-04-10-auth.md`)
  2. 从 `plan_source.ref` 提取 basename (如 `2026-04-10-auth.md` → `2026-04-10-auth`)，
     将问题写入 `docs/plans/<plan-basename>-execution-issues.md`

**execution-issues 文件格式:**

```markdown
# 执行问题报告: <plan-slug>

## 概要
- 执行任务数: X/Y
- 失败任务: Z

## 失败任务详情

### Task N: <title>
**错误类型:** build_error / test_failure / dependency_missing / instruction_unclear
**错误信息:**
\`\`\`
<完整错误输出>
\`\`\`
**已尝试的修复:** <描述>
**建议:** <建议 autoplan 如何调整 plan>
```

  3. 使用 Skill 工具调用 android-autoplan:
     skill: "android-autoplan", args: "review docs/plans/<plan-filename>.md"
  4. autoplan 的 review 模式会自动查找同名
     `<plan-filename>-execution-issues.md` 作为额外输入
  5. autoplan 读取 plan + execution-issues，重新审查并产出修订版 plan
  6. 用户确认修订版后，重新导入 worktree-runner 执行

---

## 多 Worktree 支持

多个 plan 可以同时处于进行中状态，各自在独立的 worktree 中。

### Worktree 管理命令

**列出所有 worktree:**
```bash
git worktree list
```

**检查当前所在的 worktree:**
```bash
git worktree list | grep "$(pwd)"
```

**切换 worktree:**
当用户想要处理另一个进行中的 plan 时，使用 AskUserQuestion 确认，
然后 `cd` 到目标 worktree 的路径。

### 冲突预防

- 每个 plan 获得唯一分支: `plan/<slug>` — slug 由标题和时间戳生成，避免冲突
- 如果分支名冲突，追加递增数字: `plan/auth-login-flow-2`
- 如果两个 plan 修改相同文件，发出警告（检查任务步骤中的文件路径）

---

## 恢复保障

此 skill 设计为可抵御 `/clear`、会话重启和上下文窗口耗尽。恢复机制很简单:
**磁盘上的 `tasks.json` 始终是真相。**

### 恢复原理

1. **每次调用都以相同方式开始:** 从磁盘读取 `tasks.json`
2. **每次状态变更立即写入:** 不批量、不延迟
3. **没有仅存在于内存中的状态:** 不在 `tasks.json` 中的状态不存在

### 恢复场景

**`/clear` 之后:**
```
用户: /android-worktree-runner plan-auth
Skill: → 读取 tasks.json → 找到 plan-auth，任务 2 进行中
       → 进入 worktree → 显示任务 2 状态 → 恢复执行
```

**会话重启后 (Claude Code 关闭后重新打开):**
```
用户: /android-worktree-runner
Skill: → 读取 tasks.json → 展示所有 plan 的当前状态
       → "Plan: 登录流程 [进行中] — 任务 2/3"
       → 提供恢复选项
```

**上下文窗口压缩后:**
```
上下文在任务执行过程中被压缩 → skill 在下次交互时重新读取 tasks.json
→ 状态是最新的 → 无缝继续
```

**`/clear` 之后 (并行模式):**
```
用户: /android-worktree-runner plan-20260410-001
Skill: → 读取 tasks.json → execution_mode = parallel
       → Wave 1 已完成 (任务 1, 6)，Wave 2 进行中 (任务 2 完成, 任务 3 in-progress)
       → 检查任务 3 的 worktree 是否存在
       → 如果存在 → 进入该 worktree 恢复执行
       → 如果不存在 (被清理) → 标记任务 3 为 failed，继续下一波次
```

### 什么会被持久化

| 时机 | 写入 tasks.json 的内容 |
|------|------------------------|
| Plan 导入时 | 包含所有任务的 plan 条目 (状态: pending)，依赖关系 |
| 执行模式选择时 | execution_mode，各任务 wave 编号 |
| 任务开始时 | 任务状态 → in-progress，启动时间戳 |
| 任务完成时 | 任务状态 → completed，commit hash，验证结果，完成时间戳，PRD 验证备注 |
| 任务失败时 (并行) | 任务状态 → failed，错误摘要 |
| 任务被阻塞时 | 任务状态 → blocked，阻塞原因 |
| 波次合并完成时 | 各任务 worktree/branch 信息清除 (已合并) |
| Plan 完成时 | Plan 状态 → completed，完成时间戳 |
| 验证被跳过时 | 验证字段 → "skipped" |

### 什么不需要持久化

- Plan 文件内容（恢复时从 `plan_source.ref` 重新读取）
- 代码变更（已在 worktree 的 git 工作区中）
- 构建输出（临时的，下次验证时重新运行）

---

## Worktree 管理文件 (worktree-info.md)

项目根目录下维护一个 `worktree-info.md` 文件，作为所有 worktree 的**人类可读索引**。
与 `tasks.json`（机器可读的执行状态）互补。

### 文件位置

`$MAIN_WORKTREE/worktree-info.md`（项目根目录，与 `.git` 同级）

### 文件格式

```markdown
# Worktree 索引

> 自动生成于 2026-04-10 | 由 android-worktree-runner 维护

## 进行中

### plan/auth-login-flow [并行模式]
- **worktree:** `.claude/worktrees/plan-20260410-001`
- **创建于:** 2026-04-10
- **基准 commit:** `abc1234`
- **任务:** 登录流程实现 (2/5 已完成, Wave 2/4)
- **状态:** 进行中 — Wave 2 执行中
- **并行分支:**
  - wr/auth-login-flow-task-1 (Wave 1, 已完成)
  - wr/auth-login-flow-task-6 (Wave 1, 已完成)
  - wr/auth-login-flow-task-2 (Wave 2, 进行中)
  - wr/auth-login-flow-task-3 (Wave 2, 进行中)

### plan/room-database [串行模式]
- **worktree:** `.claude/worktrees/plan-20260410-002`
- **创建于:** 2026-04-10
- **基准 commit:** `abc1234`
- **任务:** Room 数据库搭建 (0/2 已完成)
- **状态:** 待开始

## 已完成

### plan/project-init
- **worktree:** `.claude/worktrees/plan-20260409-001`
- **创建于:** 2026-04-09
- **基准 commit:** `a1b2c3d`
- **任务:** 项目初始化 (3/3 已完成)
- **状态:** 已完成 — 2026-04-10
- **最终 commit:** `f5e4d3c`
```

### 维护规则

1. **创建 worktree 时更新:** Phase 0 步骤 5 创建 worktree 后，将新 plan 添加到
   `worktree-info.md` 的"进行中"部分。
2. **任务完成时更新:** Phase 2 步骤 7 每个任务完成后，更新对应 plan 的任务进度
   `(X/N 已完成)` 和当前状态描述。
3. **并行波次推进时更新:** Phase 2B 每个波次完成后，更新对应 plan 的波次进度
   `(Wave M/N)` 和各并行分支的状态。
4. **Plan 完成时更新:** Phase 3 步骤 2 将 plan 从"进行中"移动到"已完成"部分，
   填入完成时间和最终 commit hash。并行模式下同时清理并行分支列表。
5. **文件不存在时自动创建:** 首次创建 worktree 时，如果 `worktree-info.md` 不存在，
   先扫描 `git worktree list` 获取已有的 worktree 列表，创建文件并填入已有条目。
   对于不是由 android-worktree-runner 创建的 worktree，标记为"外部 worktree"。
6. **文件已存在时追加:** 不覆盖已有内容。读取现有文件，在对应部分添加或更新条目。

### 与 tasks.json 的关系

| 文件 | 用途 | 读者 |
|------|------|------|
| `tasks.json` | 执行状态，机器可读 | android-worktree-runner skill |
| `worktree-info.md` | worktree 索引，人类可读 | 开发者、代码审查 |

`tasks.json` 是执行时的唯一真相源。`worktree-info.md` 是它的**派生视图**，
始终从 `tasks.json` 的状态生成内容，不持有独立状态。

---

## 文件结构

```
项目根目录/                           ← 主 worktree
├── worktree-info.md                 ← worktree 索引 (人类可读)
├── .claude/
│   ├── android-worktree-runner/
│   │   └── tasks.json              ← 唯一真相源 (始终在此)
│   └── worktrees/
│       ├── plan-20260410-001/      ← plan 1 的 worktree (串行模式)
│       │   └── (实际的代码变更)
│       ├── plan-20260410-002/      ← plan 2 的主 worktree (并行模式)
│       │   └── (合并后的代码变更)
│       ├── wr-slug-task-1/         ← plan 2 并行任务的 worktree
│       │   └── (任务 1 的代码变更)
│       ├── wr-slug-task-2/         ← plan 2 并行任务的 worktree
│       │   └── (任务 2 的代码变更)
│       └── ...
├── docs/
│   └── plans/
│       └── *.md                    ← plan 源文件
└── ...
```

**并行模式文件结构说明:**
- `plan-*` worktree 是 plan 的主 worktree，作为并行任务的基准分支和合并目标
- `wr-*` worktree 是并行模式中各任务的工作目录，完成后合并到 plan 主分支并清理
- 串行模式不创建 `wr-*` worktree，所有任务在 plan 主 worktree 中执行

**核心规则:** `tasks.json` 位于主 worktree 的 `.claude/` 目录中。
所有 plan worktree（在 `.claude/worktrees/` 下）读写同一个文件。
没有任何 worktree 持有 `tasks.json` 的副本。
`worktree-info.md` 位于项目根目录，作为所有 worktree 的人类可读索引。

---

## 与其他 Skill 的集成

此 skill 设计为与产出的 plan 的各类 skill 协同工作:

| Plan 来源 | 产出方 | 连接方式 |
|-----------|--------|----------|
| `docs/plans/*.md` | superpowers:writing-plans | 导入时自动检测 |
| `~/.gstack/projects/*/` | gstack:office-hours + autoplan | 导入时自动检测 |
| 内存中的 plan | Claude Code /plan | 从上下文读取 |
| 任意 Markdown | 手动或自定义 skill | 导入时提供路径 |

任何 skill 产出 plan 后，调用 `/android-worktree-runner` 导入并开始执行。
