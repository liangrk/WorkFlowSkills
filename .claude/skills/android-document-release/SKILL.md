---
name: android-document-release
description: |
  Android 文档更新 skill。在功能开发完成后，自动检测需要更新的文档，
  包括 README、CHANGELOG、CLAUDE.md 和 API 文档。
  确保代码变更与文档同步。
  适用场景: 功能完成后、PR 合并前、发版前。
voice-triggers:
  - "更新文档"
  - "更新 README"
  - "文档同步"
---

# Android Document Release

## 概述

代码变更 → 文档影响评估 → 生成变更建议 → 用户确认 → 写入变更。

分析当前分支的代码变更，自动检测哪些文档需要同步更新，
生成 diff 格式的变更建议，经用户确认后写入。

**启动时声明:** "我正在使用 android-document-release skill。"

**零外部依赖:** 仅使用 Claude Code 原生工具 (Read、Write、Edit、Grep、Glob、Bash)。

## 调用方式

```bash
/android-document-release                  # 基于当前分支 vs main 的变更
/android-document-release <branch>         # 基于指定分支 vs main 的变更
```

**参数处理:**
- 无参数: 分析当前分支相对于 main 的所有变更
- `<branch>`: 分析指定分支相对于 main 的所有变更
  - 如果当前已在该分支上，等价于无参数
  - 如果不在该分支上，通过 `git diff main...<branch>` 读取远程/本地分支的变更

---

## Phase 1: 变更分析

### 步骤 1: 确定项目根目录和基准分支

```bash
# 项目根目录
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -z "$PROJECT_ROOT" ]; then
  echo "错误: 未找到 git 仓库"
  exit 1
fi

# 确认是 Android 项目
if [ ! -f "$PROJECT_ROOT/build.gradle" ] && [ ! -f "$PROJECT_ROOT/build.gradle.kts" ] && \
   [ ! -f "$PROJECT_ROOT/settings.gradle" ] && [ ! -f "$PROJECT_ROOT/settings.gradle.kts" ]; then
  echo "错误: 未检测到 Android 项目 (缺少 build.gradle / settings.gradle)"
  exit 1
fi

# 确定基准分支 (main 或 master)
BASE_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
if [ -z "$BASE_BRANCH" ]; then
  BASE_BRANCH=$(git branch -r | grep -E 'origin/(main|master)' | head -1 | sed 's@.*origin/@@' | tr -d ' ')
fi
if [ -z "$BASE_BRANCH" ]; then
  BASE_BRANCH="main"
fi

# 当前分支
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

# 目标分支 (如果指定了参数)
TARGET_BRANCH="${1:-$CURRENT_BRANCH}"
```

### 步骤 2: 获取变更摘要

```bash
# 获取变更文件列表
CHANGED_FILES=$(git diff --name-only "$BASE_BRANCH"...HEAD 2>/dev/null)

# 变更统计
git diff --stat "$BASE_BRANCH"...HEAD 2>/dev/null

# 变更类型分类
# 新增文件
ADDED_FILES=$(git diff --diff-filter=A --name-only "$BASE_BRANCH"...HEAD 2>/dev/null)
# 修改文件
MODIFIED_FILES=$(git diff --diff-filter=M --name-only "$BASE_BRANCH"...HEAD 2>/dev/null)
# 删除文件
DELETED_FILES=$(git diff --diff-filter=D --name-only "$BASE_BRANCH"...HEAD 2>/dev/null)

# 行数统计
git diff --shortstat "$BASE_BRANCH"...HEAD 2>/dev/null
```

### 步骤 3: 提取变更内容摘要

分析 diff 内容，归纳变更类别:

**新增了什么:**
- 新增的模块/功能 (通过新增目录、新类、新 Activity/Fragment 判断)
- 新增的公开 API (public class / public fun / @Composable 函数)
- 新增的依赖 (build.gradle / build.gradle.kts / libs.versions.toml 中的变更)

```bash
# 检测新增的公开 API
# 新增文件中的 public 类和函数
for file in $ADDED_FILES; do
  if echo "$file" | grep -qE '\.(kt|java)$'; then
    # 提取 public/open class 声明
    grep -n 'public class\|public interface\|public object\|open class\|data class' "$file" 2>/dev/null
    # 提取 public 函数 (排除 private/internal)
    grep -n 'fun [^i][^n]' "$file" 2>/dev/null | grep -v 'private\|internal\|//'
  fi
done

# 检测依赖变更
git diff "$BASE_BRANCH"...HEAD -- "**/build.gradle*" "**/libs.versions.toml" 2>/dev/null

# 检测 ProGuard/R8 规则变更
git diff "$BASE_BRANCH"...HEAD -- "**/proguard*" 2>/dev/null

# 检测新增的模块
git diff "$BASE_BRANCH"...HEAD -- "settings.gradle*" 2>/dev/null | grep "include"
```

**修改了什么:**
- 修改的公开 API (参数变更、返回值变更、签名删除)
- 修改的模块配置 (build.gradle 变更)
- 修改的架构 (包结构变更、新增/删除包目录)

```bash
# 检测 API 签名变更 (函数参数/返回值变化)
git diff "$BASE_BRANCH"...HEAD -- '*.kt' '*.java' 2>/dev/null | grep -E '^\+.*fun |^\-.*fun ' | grep -v '^\+\+\+'

# 检测架构变更 (包结构变化)
git diff --diff-filter=A --name-only "$BASE_BRANCH"...HEAD 2>/dev/null | \
  grep -E '\.(kt|java)$' | sed 's|/[^/]*$||' | sort -u
```

**删除了什么:**
- 删除的公开 API
- 删除的模块/文件

```bash
# 检测删除的公开 API
for file in $DELETED_FILES; do
  if echo "$file" | grep -qE '\.(kt|java)$'; then
    echo "已删除: $file"
    # 尝试从 git 历史中恢复内容查看被删除的 public API
    git show "$BASE_BRANCH:$file" 2>/dev/null | grep -n 'public class\|public interface\|public object\|open class\|data class'
  fi
done
```

### 步骤 4: 输出变更摘要

```
=== 变更分析摘要 ===
比较:     main...<branch>
分支:     <branch>
文件数:   N (新增: A / 修改: M / 删除: D)
行数:     +X / -Y

新增功能:
  - 新增模块 feature:login (LoginActivity, LoginViewModel, LoginRepository)
  - 新增公开 API: LoginViewModel.login(email, password)
  - 新增依赖: com.google.dagger:hilt-android:2.51

修改功能:
  - 修改 UserRepository: 新增 logout() 方法
  - 修改 build.gradle: 升级 compileSdk 34 → 35

删除功能:
  - 删除 LegacyAuthManager (已迁移到 LoginViewModel)

Breaking Changes:
  - UserRepository.getAuthToken() 返回类型从 String 改为 Result<String>
```

**Breaking Change 检测规则:**
- 函数签名变更 (参数类型/数量变化、返回值类型变化)
- 删除公开类/接口/函数
- 删除模块
- 降级或移除已有依赖
- minSdk 提升

---

## Phase 2: 文档影响评估

逐项检查以下文档是否需要更新，输出评估结果。

### 2.1 README.md

**检查项目:**

| 检查项 | 触发条件 | 检测方式 |
|--------|----------|----------|
| 新增功能模块 | 新增了 feature/ 模块或主要功能 | settings.gradle 新增 include / 新增 Activity/Fragment |
| 依赖变更 | 新增或移除了第三方库 | build.gradle / libs.versions.toml diff |
| 使用方式变化 | 新增 API 或 changed API | Phase 1 提取的公开 API 变更 |
| 构建配置变化 | Gradle 配置变更 | build.gradle diff (compileSdk、minSdk、插件版本等) |
| 项目结构变化 | 新增模块或目录 | 新增的顶级目录/模块 |

```bash
# 检查 README.md 是否存在
if [ -f "$PROJECT_ROOT/README.md" ]; then
  echo "README_EXISTS"
  # 读取当前 README 内容
  wc -l "$PROJECT_ROOT/README.md"
else
  echo "README_NOT_FOUND"
fi

# 检查 README 中是否已包含相关内容
if [ -f "$PROJECT_ROOT/README.md" ]; then
  # 检查新增模块是否已记录
  for module in <新增模块列表>; do
    grep -q "$module" "$PROJECT_ROOT/README.md" || echo "README_MISSING_MODULE: $module"
  done
fi
```

**评估输出:**
```
README.md: 需要更新
  - [ ] 新增模块 feature:login 未在 README 中记录
  - [ ] 新增依赖 Hilt 未在 README 中说明
  - [ ] 新增公开 API LoginViewModel.login() 未在 README 中展示
```

### 2.2 CHANGELOG.md

**检查项目:**

| 检查项 | 触发条件 | 检测方式 |
|--------|----------|----------|
| 是否有 CHANGELOG | 项目应维护 CHANGELOG | 检查 CHANGELOG.md 是否存在 |
| 未记录的版本变更 | 有代码变更但 CHANGELOG 未更新 | CHANGELOG 最新版本与分支变更对比 |

```bash
# 检查 CHANGELOG.md 是否存在
if [ -f "$PROJECT_ROOT/CHANGELOG.md" ]; then
  echo "CHANGELOG_EXISTS"
  # 读取最新版本条目
  head -50 "$PROJECT_ROOT/CHANGELOG.md"
else
  echo "CHANGELOG_NOT_FOUND"
fi

# 检查最新版本是否已包含当前变更
if [ -f "$PROJECT_ROOT/CHANGELOG.md" ]; then
  # 从分支名推断版本号 (如果有)
  VERSION_FROM_BRANCH=$(echo "$TARGET_BRANCH" | grep -oP 'v?\d+\.\d+\.\d+' | head -1)
  if [ -n "$VERSION_FROM_BRANCH" ]; then
    grep -q "$VERSION_FROM_BRANCH" "$PROJECT_ROOT/CHANGELOG.md" && echo "VERSION_RECORDED" || echo "VERSION_NOT_RECORDED"
  fi
fi
```

**评估输出:**
```
CHANGELOG.md: 需要更新
  - [ ] 当前分支变更未记录在 CHANGELOG 中
  - [ ] 建议新增版本条目 (基于分支名推断版本号)
```

**如果 CHANGELOG.md 不存在:**
```
CHANGELOG.md: 建议创建
  - [ ] 项目缺少 CHANGELOG.md，建议创建以记录版本变更
  - [ ] 建议使用 Keep a Changelog 格式
```

### 2.3 CLAUDE.md

**检查项目:**

| 检查项 | 触发条件 | 检测方式 |
|--------|----------|----------|
| 架构变更 | 新增/删除模块、包结构变化 | settings.gradle diff、新增/删除目录 |
| 新依赖 | 新增第三方库 | build.gradle diff |
| 新约定 | 新增代码模式、命名规范 | Phase 1 分析结果 |
| 模块职责变化 | 模块边界调整 | 包结构变化、类迁移 |

```bash
# 检查 CLAUDE.md 是否存在 (项目根目录)
if [ -f "$PROJECT_ROOT/CLAUDE.md" ]; then
  echo "CLAUDE_MD_EXISTS"
  head -80 "$PROJECT_ROOT/CLAUDE.md"
elif [ -f "$PROJECT_ROOT/.claude/CLAUDE.md" ]; then
  echo "CLAUDE_MD_EXISTS_IN_CLAUDE_DIR"
  head -80 "$PROJECT_ROOT/.claude/CLAUDE.md"
else
  echo "CLAUDE_MD_NOT_FOUND"
fi
```

**评估输出:**
```
CLAUDE.md: 需要更新
  - [ ] 新增模块 feature:login 的职责说明未记录
  - [ ] 新增依赖 Hilt 的使用约定未说明
  - [ ] 架构图/模块依赖关系需更新
```

### 2.4 API 文档

**检查项目:**

| 检查项 | 触发条件 | 检测方式 |
|--------|----------|----------|
| 公开 API 变更 | 新增/修改/删除公开函数或类 | Phase 1 提取的 API 变更 |
| Breaking Changes | API 签名不兼容变更 | 参数/返回值类型变化、公开 API 删除 |
| KDoc 覆盖 | 新增公开 API 是否有文档注释 | 检查新增 public 类/函数是否有 KDoc |

```bash
# 检查是否有 API 文档目录
find "$PROJECT_ROOT/docs" -name "*.md" 2>/dev/null | grep -iE 'api|reference' | head -5

# 检查新增公开 API 是否有 KDoc
for file in $ADDED_FILES; do
  if echo "$file" | grep -qE '\.(kt|java)$'; then
    # 检查 public class/interface 前是否有 KDoc
    grep -B1 'public class\|public interface\|public object\|data class' "$file" 2>/dev/null | grep -c '/\*\*' || true
  fi
done
```

**评估输出:**
```
API 文档: 需要更新
  - [ ] 新增公开类 LoginViewModel 缺少 KDoc
  - [ ] 新增公开函数 login(email, password) 缺少 KDoc
  - [ ] Breaking Change: UserRepository.getAuthToken() 返回类型变更未记录
  - [ ] 建议更新 API 参考文档 (如有)
```

### 2.5 模块文档

**检查项目:**

| 检查项 | 触发条件 | 检测方式 |
|--------|----------|----------|
| 模块 README | 新增模块是否有 README | 检查每个新增模块目录下是否有 README.md |
| 模块职责说明 | 修改模块的职责是否变化 | 包结构/类变更分析 |

```bash
# 检查每个受影响模块是否有 README
AFFECTED_MODULES=$(echo "$CHANGED_FILES" | cut -d'/' -f1 | sort -u)
for module in $AFFECTED_MODULES; do
  if [ -d "$PROJECT_ROOT/$module" ]; then
    if [ ! -f "$PROJECT_ROOT/$module/README.md" ]; then
      echo "MODULE_NO_README: $module"
    else
      echo "MODULE_HAS_README: $module"
    fi
  fi
done
```

**评估输出:**
```
模块文档: 需要更新
  - [ ] 新增模块 feature:login 缺少 README.md
  - [ ] 修改模块 core:common 的 README.md 可能需要更新 (新增工具类)
```

### 步骤 3: 输出影响评估汇总

```
=== 文档影响评估 ===

  README.md:     需要更新 (3 项)
  CHANGELOG.md:  需要更新 (1 项)
  CLAUDE.md:     需要更新 (2 项)
  API 文档:      需要更新 (3 项)
  模块文档:      需要更新 (2 项)

  总计: 11 项文档变更建议
```

---

## Phase 3: 生成文档变更

对 Phase 2 中评估为"需要更新"的文档，生成具体的变更内容。

每个文档的变更格式:

```
=== <文档路径> ===

当前状态:
  <简述文档当前内容概况>

建议变更:
  --- a/README.md
  +++ b/README.md
  @@ -10,6 +10,12 @@
   ## 功能模块
   - core:common - 通用工具
   + feature:login - 登录功能
   +   - LoginActivity: 登录页面
   +   - LoginViewModel: 登录状态管理
   +   - LoginRepository: 登录数据层

变更原因:
  - 新增了 feature:login 模块，包含 3 个核心类
```

### 3.1 README.md 变更生成

根据 Phase 2 的评估项，生成具体变更:

**新增模块记录:**
```diff
+ ### feature:login
+ 登录功能模块，包含邮箱密码登录和第三方登录。
+
+ 核心类:
+ - `LoginViewModel` - 管理登录状态和认证流程
+ - `LoginRepository` - 登录数据层，处理网络请求和本地缓存
+ - `LoginScreen` - Compose 登录页面 UI
```

**新增依赖记录:**
```diff
+ ## 主要依赖
+ - [Hilt](https://dagger.dev/hilt/) - 依赖注入框架
```

**使用方式变更:**
```diff
+ ## 使用方式
+
+ ### 登录功能
+ ```kotlin
+ // 使用 Hilt 注入 ViewModel
+ @HiltViewModel
+ class LoginViewModel @Inject constructor(
+     private val repository: LoginRepository
+ ) : ViewModel() {
+     fun login(email: String, password: String) { ... }
+ }
+ ```
```

### 3.2 CHANGELOG.md 变更生成

如果 CHANGELOG.md 存在，生成新增条目:

```diff
+ ## [Unreleased]
+
+ ### Added
+ - 新增 `feature:login` 登录功能模块
+ - 新增 `LoginViewModel`、`LoginRepository`、`LoginScreen`
+ - 新增 Hilt 依赖注入框架
+
+ ### Changed
+ - `UserRepository.getAuthToken()` 返回类型改为 `Result<String>`
+ - 升级 compileSdk 34 -> 35
+
+ ### Removed
+ - 移除 `LegacyAuthManager` (已迁移到 `LoginViewModel`)
+
+ ### Breaking Changes
+ - `UserRepository.getAuthToken()` 返回类型从 `String` 改为 `Result<String>`，
+   调用方需处理 `Result` 包装
```

如果 CHANGELOG.md 不存在，生成完整的新文件建议:

```markdown
# Changelog

本项目的所有重要变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本管理遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added
- <基于 Phase 1 分析结果填写>

### Changed
- <基于 Phase 1 分析结果填写>

### Removed
- <基于 Phase 1 分析结果填写>

### Breaking Changes
- <基于 Phase 1 Breaking Change 检测结果填写>
```

### 3.3 CLAUDE.md 变更生成

根据架构和约定变更，生成具体更新:

```diff
+ ## 架构
+
+ ### 模块职责
+ - `feature:login` - 登录功能。依赖 `core:common` 和 `core:network`。
+   提供 LoginActivity、LoginViewModel、LoginRepository。
+
+ ### 新增约定
+ - 使用 Hilt 进行依赖注入，所有 ViewModel 通过 @HiltViewModel 注解
+ - Repository 实现通过 @Module + @Provides 提供
```

### 3.4 API 文档变更生成

**Breaking Changes 记录:**
```diff
+ ## Breaking Changes
+
+ ### `UserRepository.getAuthToken()`
+ - **变更前:** `suspend fun getAuthToken(): String`
+ - **变更后:** `suspend fun getAuthToken(): Result<String>`
+ - **影响:** 所有调用方需处理 `Result` 包装类型
+ - **迁移:**
+   ```kotlin
+   // Before
+   val token = repository.getAuthToken()
+
+   // After
+   val result = repository.getAuthToken()
+   result.onSuccess { token -> ... }
+     .onFailure { error -> ... }
+   ```
```

**新增 API 记录:**
```diff
+ ## 新增 API
+
+ ### LoginViewModel
+ | 函数 | 签名 | 说明 |
+ |------|------|------|
+ | login | `fun login(email: String, password: String)` | 执行登录 |
+ | logout | `fun logout()` | 执行登出 |
+ | loginState | `val loginState: StateFlow<LoginState>` | 登录状态流 |
```

### 3.5 模块文档变更生成

为缺少 README 的新增模块生成建议:

```markdown
# feature:login

登录功能模块。

## 职责
- 用户名密码登录
- 第三方登录 (Google, Facebook)
- 登录状态管理
- Token 持久化

## 核心类
- `LoginViewModel` - 登录状态管理
- `LoginRepository` - 登录数据层
- `LoginScreen` - 登录页面 UI (Compose)

## 依赖
- `core:common` - 通用工具和基础类
- `core:network` - 网络请求

## 使用示例
```kotlin
@HiltViewModel
class LoginViewModel @Inject constructor(
    private val repository: LoginRepository
) : ViewModel() {
    fun login(email: String, password: String) {
        viewModelScope.launch {
            repository.login(email, password)
        }
    }
}
```
```

---

## Phase 4: 用户确认与写入

### 步骤 1: 展示所有建议变更

将 Phase 3 生成的所有变更建议汇总展示:

```
╔═══════════════════════════════════════════════════════════╗
║                  文档变更建议汇总                         ║
╠═══════════════════════════════════════════════════════════╣
║  分支: <branch>                                         ║
║  比较: main...<branch>                                  ║
║  变更: N 个文件 (+X / -Y)                               ║
║                                                         ║
║  需更新文档: 5 个                                        ║
║  变更项: 11 项                                          ║
╚═══════════════════════════════════════════════════════════╝

[1] README.md (3 项变更)
[2] CHANGELOG.md (1 项变更)
[3] CLAUDE.md (2 项变更)
[4] API 文档 (3 项变更)
[5] feature:login/README.md (2 项变更 - 新建)
```

### 步骤 2: 用户确认

向用户展示选项:

```
请选择操作:
A) 全部应用 — 将所有建议变更写入对应文档
B) 选择性应用 — 逐个确认每项变更
C) 跳过 — 不修改任何文件，仅保留评估报告
```

**选择 B (选择性应用) 时的流程:**

逐项展示变更，每项询问:

```
[1/11] README.md: 新增模块 feature:login 记录
  变更: 在"功能模块"章节添加 feature:login 说明
  是否应用?
  Y) 是  N) 跳过  V) 查看详细 diff
```

用户选择 V 时，展示完整的 diff 内容。

### 步骤 3: 写入变更

根据用户确认结果，使用 Edit 工具写入变更。

**写入规则:**
- 已存在的文档 → 使用 Edit 工具精确修改
- 不存在的文档 → 使用 Write 工具创建
- 每次写入后读取文件确认变更正确
- 写入顺序: README.md → CHANGELOG.md → CLAUDE.md → 模块文档 → API 文档

**写入后验证:**
```bash
# 确认写入结果
git diff --stat

# 展示写入的文件列表
git diff --name-only
```

### 步骤 4: 生成文档变更记录

将完整的文档变更记录写入 `docs/reviews/<branch>-doc-update.md`:

```bash
# 确保目录存在
mkdir -p "$PROJECT_ROOT/docs/reviews"
```

**报告格式:**

```markdown
# 文档更新记录: <branch>

> 生成于 <YYYY-MM-DD HH:mm> | android-document-release
> 基准分支: <base-branch>
> 操作: 全部应用 / 选择性应用 (N/M)

## 变更摘要

| 指标 | 结果 |
|------|------|
| 代码变更文件数 | N |
| 评估的文档数 | 5 |
| 需更新的文档 | 5 |
| 已应用的变更 | N 项 |
| 跳过的变更 | N 项 |

## 变更详情

### README.md
- 状态: 已更新 / 跳过
- 变更内容:
  - 新增 feature:login 模块说明
  - 新增 Hilt 依赖记录
  - 新增登录功能使用示例

### CHANGELOG.md
- 状态: 已创建 / 已更新 / 跳过
- 变更内容:
  - 新增 Unreleased 版本条目
  - 记录 Added/Changed/Removed/Breaking Changes

### CLAUDE.md
- 状态: 已更新 / 跳过
- 变更内容:
  - 新增 feature:login 模块职责说明
  - 新增 Hilt 使用约定

### API 文档
- 状态: 已更新 / 跳过
- 变更内容:
  - 记录 LoginViewModel 新增 API
  - 记录 UserRepository.getAuthToken() Breaking Change

### 模块文档
- 状态: 已创建 / 跳过
- 变更内容:
  - 创建 feature:login/README.md

## 原始变更分析

<Phase 1 的变更分析摘要>
```

---

## 产出

### 产出物 1: 文档变更记录

- 路径: `docs/reviews/<branch>-doc-update.md`
- 内容: 完整的文档更新记录，包含评估、变更详情和操作结果

### 产出物 2: 文档变更 (根据用户确认)

- 已更新的文档文件列表
- 每个文件的变更内容摘要

---

## 异常情况处理

| 场景 | 处理方式 |
|------|----------|
| 不在 git 仓库中 | 报错: "android-document-release 需要 git 仓库" |
| 不是 Android 项目 | 报错: "未检测到 Android 项目" |
| main 分支不存在 | 尝试 origin/main、master，仍不存在则报错 |
| 指定分支不存在 | 报错: "未找到分支: <branch>" |
| 无任何变更 | 提示: "当前分支相对于 main 没有变更，无需更新文档" |
| README.md 不存在 | 建议创建 README.md，包含项目基本说明 |
| CHANGELOG.md 不存在 | 建议创建 CHANGELOG.md，使用 Keep a Changelog 格式 |
| CLAUDE.md 不存在 | 建议创建 CLAUDE.md，包含项目架构和约定说明 |
| 文档无写入权限 | 报错并提示用户检查文件权限 |
| docs/reviews 目录不存在 | 自动创建 |
| 变更规模过大 (>50 文件) | 警告并询问是否继续 |

---

## 与其他 Skill 的衔接

```
/android-brainstorm       → 头脑风暴 → 需求定义
/android-autoplan         → 拆分 + 审查 → plan 文件
/android-design-review    → Figma 设计审查 → 设计规格
/android-worktree-runner  → 执行 plan → 代码变更
/android-code-review      → 代码审查 → 审查报告
/android-qa               → QA 测试 → bug 报告
/android-document-release → 文档更新 → 文档变更记录 ← 当前
```

**上游调用场景:**
- android-worktree-runner 完成 Phase 3 (Plan 完成) 后，
  可调用 `/android-document-release` 同步文档
- android-code-review 完成后，
  可调用 `/android-document-release` 确保文档与代码一致
- android-qa 完成后，
  可调用 `/android-document-release` 在发版前更新文档

**衔接协议:**
- 接收分支名作为参数
- 不修改源代码文件 (仅修改文档)
- 产出物写入 `docs/reviews/` 目录

### 与其他 skill 的关系

| Skill | 关系 | 说明 |
|-------|------|------|
| android-worktree-runner | 上游 | Plan 执行完毕后调用本 skill 同步文档 |
| android-code-review | 上游 | 代码审查完成后调用本 skill 同步文档 |
| android-qa | 上游 | QA 通过后调用本 skill 更新发版文档 |
| android-investigate | 无直接关系 | 各自独立运行 |

---

## 文件结构

```
项目根目录/
├── docs/
│   └── reviews/
│       └── <branch>-doc-update.md          ← 本 skill 产出的文档变更记录
├── .claude/
│   └── skills/
│       └── android-document-release/
│           └── SKILL.md                    ← 本 skill
├── README.md                               ← 可能被更新的文档
├── CHANGELOG.md                            ← 可能被创建/更新的文档
├── CLAUDE.md                               ← 可能被更新的文档
└── ...
```
