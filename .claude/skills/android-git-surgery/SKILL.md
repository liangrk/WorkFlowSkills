---
name: android-git-surgery
description: |
  Use when encountering git merge/rebase conflicts, needing to remove specific commits
  from a chain (e.g., drop commit C from A->B->C->D to get A->B->D), or verifying
  post-merge/rebase impact (build, tests, functional regression). Handles conflict
  analysis, safe commit surgery with backup, and integration impact verification.
voice-triggers:
  - "合并冲突"
  - "解决冲突"
  - "移除commit"
  - "git冲突"
  - "rebase冲突"
  - "合并影响"
  - "commit surgery"
invocation: /android-git-surgery
args: [--mode resolve|surgery|verify] [target]
---

# Android Git Surgery

## 概述

Git 合并冲突解决 + commit 链手术 + 合并影响验收，三位一体的 git 精细操作工具。

**启动时声明:** "我正在使用 android-git-surgery skill。"

**安全第一:** 所有破坏性操作前自动创建备份分支。

**零外部依赖:** 仅使用 Claude Code 原生工具和 bash 命令。

## 调用方式

```bash
/android-git-surgery                         # 交互式: 自动检测当前 git 状态，引导选择操作
/android-git-surgery resolve                  # 冲突解决模式: 检测并解决当前 merge/rebase 冲突
/android-git-surgery surgery <commit-hash>    # commit 手术模式: 移除指定 commit (支持多个，空格分隔)
/android-git-surgery verify                   # 影响验收模式: 验证最近一次 merge/rebase 的构建和功能完整性
```

**参数处理:**

| 模式 | 参数 | 行为 |
|------|------|------|
| 交互式 | 无参数 | 自动检测 git 状态: 有冲突 → resolve，有 surgery 标记 → surgery，否则 → verify |
| resolve | `resolve` | 分析冲突文件，提出解决方案 |
| surgery | `surgery <hash>...` | 移除指定 commit，保留其余 |
| verify | `verify` | 编译 + 测试 + 功能回归检查 |

---

## Phase 0: 预检与备份

**所有模式共享的前置步骤。**

### 步骤 1: 当前状态分析

```bash
# 当前分支和状态
echo "BRANCH: $(git rev-parse --abbrev-ref HEAD)"
echo "HEAD: $(git rev-parse --short HEAD)"
echo ""

# 是否在 merge/rebase/cherry-pick 中间状态
if [ -d "$(git rev-parse --git-dir)/rebase-merge" ] || \
   [ -d "$(git rev-parse --git-dir)/rebase-apply" ]; then
  echo "STATE: rebase-in-progress"
elif [ -f "$(git rev-parse --git-dir)/MERGE_HEAD" ]; then
  echo "STATE: merge-in-progress"
elif [ -f "$(git rev-parse --git-dir)/CHERRY_PICK_HEAD" ]; then
  echo "STATE: cherry-pick-in-progress"
else
  echo "STATE: clean"
fi

# 未提交变更
git status --short
```

### 步骤 2: 自动备份

**对 resolve 和 surgery 模式，操作前自动创建备份分支:**

```bash
BACKUP_BRANCH="backup/$(git rev-parse --abbrev-ref HEAD)/$(date +%Y%m%d-%H%M%S)"

if [ "$(git status --porcelain | wc -l)" -gt 0 ]; then
  # 有未提交变更时，先 stash
  git stash push -m "git-surgery-backup-stash" --include-untracked
  STASHED=1
fi

git branch "$BACKUP_BRANCH" HEAD
echo "BACKUP: $BACKUP_BRANCH"
echo "恢复命令: git checkout $BACKUP_BRANCH"
```

> 即使操作失败，用户也可以通过 `git checkout $BACKUP_BRANCH` 恢复到操作前的状态。

**操作完成后恢复 stash:**
```bash
# 在每个模式的最后步骤中执行
if [ "${STASHED:-0}" = "1" ]; then
  git stash pop
  echo "已恢复工作区变更"
fi
```

---

## Phase 1: 冲突解决 (resolve)

当 git merge/rebase/cherry-pick 产生冲突时使用。

### 步骤 1: 检测冲突文件

```bash
# 列出所有冲突文件及冲突类型
echo "=== 冲突文件 ==="
git diff --name-only --diff-filter=U
echo ""

# 统计
CONFLICT_COUNT=$(git diff --name-only --diff-filter=U | wc -l)
echo "冲突文件数: $CONFLICT_COUNT"
```

### 步骤 2: 分析每个冲突

对每个冲突文件，执行以下分析:

1. **读取冲突文件**，识别冲突标记 (`<<<<<<<`, `=======`, `>>>>>>>`)
2. **统计冲突数量** — 一个文件可能包含多个冲突块
3. **判断冲突类型:**

| 冲突类型 | 特征 | 处理策略 |
|---------|------|---------|
| import 冲突 | `<<<<<<<` 出现在文件顶部的 import 块 | 合并两侧 import，去重 |
| 简单行冲突 | 单行或少量行差异 | 根据语义判断保留哪一侧 |
| 方法/函数冲突 | 同一方法的不同实现 | 分析两侧变更意图，合并或选择 |
| 结构性冲突 | 大段代码被不同方式修改 | 展示给用户决策 |
| 删除/修改冲突 | 一侧删除、一侧修改 | 展示给用户决策 |

### 步骤 3: 自动解决简单冲突

**可自动解决的冲突 (无需用户确认):**

| 场景 | 处理方式 |
|------|---------|
| 两侧添加不同 import | 合并两侧 import，按字母排序 |
| 两侧添加不同常量/字段 | 合并两侧，无重叠则全部保留 |
| 一侧仅修改空格/格式 | 保留修改内容，采用项目格式规范 |
| 两侧修改同一方法的返回值但逻辑相同 | 合并为一份 |
| build.gradle 依赖版本冲突 | 保留较新版本 |

**需要用户确认的冲突:**

| 场景 | 原因 |
|------|------|
| 两侧修改同一方法的逻辑 | 需要理解业务意图 |
| 一侧删除代码、一侧修改 | 无法自动判断 |
| Composable 函数签名冲突 | 可能影响 UI 行为 |
| Manifest 权限/组件冲突 | 可能影响安全性 |

### 步骤 4: 解决冲突并标记

解决每个冲突后:

```bash
git add <resolved-file>
```

**全部解决后:**

```bash
# merge 冲突
git commit --no-edit

# 或 rebase 冲突
git rebase --continue
```

### 步骤 5: 输出冲突解决摘要

```
=== 冲突解决摘要 ===
冲突文件: 5 个
  自动解决: 3 个 (import 合并、版本冲突、格式冲突)
  用户确认: 2 个 (LoginViewModel.kt、build.gradle.kts)
解决方案:
  ✅ 合并两侧 import (AuthRepository.kt)
  ✅ 保留较新版本 (build.gradle.kts)
  ✅ 用户选择: 保留 ours (LoginViewModel.kt)
  ✅ 用户选择: 手动合并 (NavigationGraph.kt)
备份分支: backup/feature/login/20260411-143000
```

---

## Phase 2: Commit 链手术 (surgery)

从 commit 链中移除指定的 commit，保留其余 commit 不变。

### 核心原理

```
原始链: A → B → C → D → E
移除 C: A → B → D' → E'

D' 和 E' 是 D 和 E rebase 到 B 上的新版本，
内容和 commit message 与原 D、E 完全一致。
```

**底层命令:** `git rebase --onto <target-base> <commit-to-skip>`

### 步骤 1: 确认操作目标

```bash
# 显示当前 commit 链 (最近 15 个)
echo "=== 当前 Commit 链 ==="
git log --oneline --graph -15
```

如果用户指定了 commit hash，确认目标:

```bash
# 验证 commit 存在
if git cat-file -t "$TARGET_COMMIT" >/dev/null 2>&1; then
  echo "目标 commit: $(git log -1 --format='%h %s' $TARGET_COMMIT)"
  echo "父 commit:   $(git log -1 --format='%h %s' $TARGET_COMMIT^)"
else
  echo "错误: commit $TARGET_COMMIT 不存在"
  exit 1
fi
```

### 步骤 2: 分析影响范围

在移除前，分析目标 commit 的影响:

```bash
# 目标 commit 修改了哪些文件
echo "=== 目标 commit 修改的文件 ==="
git diff-tree --no-commit-id --name-status -r "$TARGET_COMMIT"

# 检查后续 commit 是否依赖这些修改
echo ""
echo "=== 后续 commit 对相同文件的修改 ==="
CHANGED_FILES=$(git diff-tree --no-commit-id --name-only -r "$TARGET_COMMIT")
for file in $CHANGED_FILES; do
  COMMITS=$(git log --oneline "$TARGET_COMMIT"..HEAD -- "$file" 2>/dev/null)
  if [ -n "$COMMITS" ]; then
    echo "⚠️ $file 在后续 commit 中被修改:"
    echo "$COMMITS"
  fi
done
```

**依赖检测规则:**
- 如果后续 commit 修改了目标 commit 的相同文件 → 警告: rebase 后可能产生冲突
- 如果后续 commit 没有触及目标 commit 的文件 → 安全: 不会产生冲突

### 步骤 3: 执行 commit 移除

**单个 commit 移除:**

```bash
# 移除 COMMIT_TO_REMOVE，将其后的所有 commit rebase 到其父 commit 上
# git rebase --onto <parent-of-target> <target>
git rebase --onto "${COMMIT_TO_REMOVE}^" "$COMMIT_TO_REMOVE"
```

**多个连续 commit 移除 (如移除 C 和 D):**

```bash
# 移除 C~D 范围，将 E 及之后的 commit rebase 到 B 上
# git rebase --onto <parent-of-first-to-remove> <last-to-remove>
git rebase --onto "${FIRST_COMMIT}^" "$LAST_COMMIT"
```

**多个不连续 commit 移除 (如移除 B 和 D):**

```bash
# 不连续 commit 需要多次 rebase，从最近的开始倒序移除
# 1. 先移除 D (不影响 B)
git rebase --onto "D^" "D"
# 2. 第一次 rebase 后，展示当前 commit 链让用户确认 B 的新 hash
echo "=== 请确认 B 的新 hash ==="
git log --oneline --graph -15
# 用户确认后使用新 hash
# B_NEW=<用户确认的hash>
git rebase --onto "${B_NEW}^" "$B_NEW"
```

> **重要:** 不连续移除时，第一次 rebase 后所有后续 commit 的 hash 都会改变。
> 不要通过 commit message 关键词搜索 hash (容易误匹配)，必须让用户从 `git log` 中确认。

**rebase 过程中如果产生冲突:**
1. 自动进入 Phase 1 (冲突解决)
2. 冲突解决后 `git rebase --continue`
3. 如果实在无法解决: `git rebase --abort` → 恢复到备份分支

### 步骤 4: 验证结果

```bash
# 确认目标 commit 已被移除
echo "=== 验证: Commit 链 ==="
git log --oneline --graph -15

# 通过原始 hash 确认目标 commit 不再在链中
if git log --oneline | grep -q "$TARGET_COMMIT"; then
  echo "⚠️ 警告: 目标 commit 的 hash 仍出现在链中"
else
  echo "✅ 目标 commit 已成功移除"
fi

# 确认后续 commit 的 message 保留
for expected_msg in "${EXPECTED_MESSAGES[@]}"; do
  if git log --oneline | grep -q "$expected_msg"; then
    echo "✅ 保留: $expected_msg"
  else
    echo "❌ 丢失: $expected_msg"
  fi
done
```

### 步骤 5: 输出手术摘要

```
=== Commit 手术摘要 ===
操作: 移除 commit
目标: abc1234 feat: add intermediate debug logging
父 commit: def5678 fix: resolve login race condition

结果:
  ✅ 目标 commit 已移除
  ✅ 后续 3 个 commit 保留 (message 不变)
  ⚠️ rebase 过程中 1 个冲突已自动解决

Commit 链变化:
  移除前: A → B → C(debug) → D → E
  移除后: A → B → D' → E'

备份分支: backup/feature/login/20260411-143000
```

---

## Phase 3: 合并影响验收 (verify)

merge/rebase 完成后，验证构建和功能完整性。

### 步骤 1: 编译检查

```bash
# Gradle 编译检查
BUILD_OUTPUT=$(./gradlew assembleDebug 2>&1)
BUILD_RESULT=$?

echo "$BUILD_OUTPUT" | tail -20

if [ $BUILD_RESULT -eq 0 ]; then
  echo "✅ 编译通过"
else
  echo "❌ 编译失败"
  # 从已有输出中提取编译错误，避免重复运行
  echo "$BUILD_OUTPUT" | grep -E "error:|FAILURE" | head -20
fi
```

**编译失败时的处理:**
1. 分析编译错误类型 (依赖缺失、API 不兼容、类型错误)
2. 如果是依赖冲突: 检查 `build.gradle` 中是否有版本冲突
3. 如果是 API 不兼容: 检查 SDK 版本和 API 使用
4. 尝试自动修复 (机械修复，最多 3 次)
5. 无法自动修复: 报告错误，建议回退到备份分支

### 步骤 2: 测试执行

```bash
# 运行单元测试
./gradlew testDebugUnitTest 2>&1 | tail -20

TEST_RESULT=$?
if [ $TEST_RESULT -eq 0 ]; then
  echo "✅ 单元测试全部通过"
else
  echo "❌ 单元测试有失败"
  # 提取失败测试
  ./gradlew testDebugUnitTest 2>&1 | grep -E "FAILED|Test >" | head -20
fi
```

### 步骤 3: 功能回归检查

**检查合并引入的变更范围:**

```bash
# 如果是 merge commit，检查 merge 引入的变更
MERGE_HEAD=$(git log -1 --format='%P' HEAD | awk '{print $2}' 2>/dev/null)
if [ -n "$MERGE_HEAD" ]; then
  echo "=== Merge 变更文件 ==="
  git diff-tree --name-status -r HEAD^ HEAD
else
  echo "=== 最近操作变更文件 ==="
  git diff --name-status HEAD~1 HEAD
fi
```

**根据变更文件判断影响范围:**

| 变更文件类型 | 检查项 |
|-------------|--------|
| `build.gradle*` | 依赖是否一致、版本是否兼容 |
| `AndroidManifest.xml` | 权限/组件声明是否冲突 |
| `*ViewModel.kt` | 状态管理逻辑是否完整 |
| `*Repository.kt` | 数据层接口是否对齐 |
| `*Navigation*.kt` | 路由是否断裂、deep link 是否失效 |
| `res/*` | 资源 ID 是否重复或缺失 |
| `proguard-rules.pro` | keep 规则是否覆盖新增代码 |

**如果项目有 `.android-project-profile.json`:**
读取档案中的架构和依赖信息，对照变更文件检查是否有遗漏的集成点。

### 步骤 4: 输出验收报告

```
=== 合并影响验收 ===
操作: merge feature/login into master

编译: ✅ 通过 (assembleDebug)
单元测试: ✅ 通过 (47/47)

变更文件: 12 个
  - 修改: 8 个 (ViewModel, Repository, build.gradle, Manifest...)
  - 新增: 3 个 (LoginScreen.kt, TokenManager.kt, nav_graph_login.xml)
  - 删除: 1 个 (LegacyAuthHandler.kt)

影响分析:
  ✅ 无依赖冲突
  ✅ Navigation 路由完整
  ✅ Manifest 权限无冲突
  ⚠️ LegacyAuthHandler.kt 被删除，但 SearchFeature 中仍有引用 → 需确认

结论: PASS (1 个建议项)
备份分支: backup/feature/login/20260411-143000
```

---

## 操作模式选择逻辑

```
当前 git 状态
  │
  ├─ 有未解决的冲突 (CONFLICT 文件)
  │   → resolve 模式
  │
  ├─ 用户指定了 commit hash + surgery 参数
  │   → surgery 模式
  │
  ├─ 最近 1 次操作是 merge/rebase
  │   → 询问: verify 或其他?
  │
  └─ 干净状态
      → 交互式选择:
        A) surgery — 指定要移除的 commit
        B) verify — 验证最近一次 merge/rebase
        C) resolve — 如果有冲突文件待解决
```

---

## 与其他 Skill 的衔接

| Skill | 关系 | 说明 |
|-------|------|------|
| android-ship | 上游 | ship 流程中 merge 后调用 verify 模式验收 |
| android-worktree-runner | 上游 | runner 合并 worktree 分支后调用 verify |
| android-code-review | 并行 | surgery 后可配合 code-review 检查代码质量 |
| android-tdd | 下游 | verify 中测试失败时，可调用 tdd 修复 |
| android-investigate | 下游 | verify 中发现回归问题时，调用 investigate 深入排查 |

```
android-ship (合并分支)
  │
  ▼
android-git-surgery verify (验收合并影响)
  │
  ├─ 编译失败 → 自动修复 / 回退
  ├─ 测试失败 → android-tdd / android-investigate
  └─ 全部通过 → 完成

android-worktree-runner (合并 worktree)
  │
  ▼
android-git-surgery verify (验收)
  │
  └─ 发现问题 → android-investigate

用户请求移除 commit
  │
  ▼
android-git-surgery surgery (commit 链手术)
  │
  ├─ rebase 冲突 → Phase 1 (冲突解决)
  └─ 手术完成 → verify (验收)
```

## 异常情况处理

| 场景 | 处理方式 |
|------|----------|
| 不在 git 仓库中 | 报错: "需要 git 仓库" |
| rebase 中途放弃 | `git rebase --abort` → 恢复到备份分支 |
| merge 中途放弃 | `git merge --abort` → 恢复到备份分支 |
| commit hash 不存在 | 报错并列出最近的 commit 供选择 |
| 移除 commit 后编译失败 | 提示具体错误，建议回退到备份分支 |
| Gradle 网络问题 | 切换阿里云镜像 (同 android-tdd 的 Gradle 网络回退策略) |
| 目标 commit 是 merge commit | 警告: 移除 merge commit 可能导致历史分支丢失，需要用户确认 |
| 工作区有未提交变更 | 自动 stash，操作完成后恢复 stash |

## 常见操作速查

| 操作 | 命令 |
|------|------|
| 查看当前冲突 | `git diff --name-only --diff-filter=U` |
| 接受当前分支版本 | `git checkout --ours <file>` |
| 接受传入分支版本 | `git checkout --theirs <file>` |
| 移除单个 commit | `git rebase --onto COMMIT^ COMMIT` |
| 移除连续多个 commit | `git rebase --onto FIRST^ LAST` |
| 放弃 rebase | `git rebase --abort` |
| 放弃 merge | `git merge --abort` |
| 查看备份分支 | `git branch \| grep backup/` |
| 恢复到备份 | `git checkout backup/<branch>/<timestamp>` |

> **注意:** rebase 中 `--ours` / `--theirs` 语义与 merge **相反**。
> merge 中 `--ours` = 当前分支，`--theirs` = 传入分支。
> rebase 中 `--ours` = 上游分支 (被 rebase 进来的)，`--theirs` = 当前分支 (正在 rebase 的)。
