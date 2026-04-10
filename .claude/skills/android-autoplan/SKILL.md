---
name: android-autoplan
description: |
  Android 专属的 Plan 拆分与审查 skill。接收功能需求，按 Android 拆分规则生成
  结构化 plan，经四层审查（CEO/Design占位/Eng/DX）后产出可直接交给
  android-worktree-runner 执行的 plan 文件。零外部依赖，纯 Claude Code 原生工具。
  自动检测项目技术栈和架构模式。
  适用场景: 功能需求拆分、plan 审查、Android 项目规划。
voice-triggers:
  - "拆分需求"
  - "Android 计划"
  - "规划功能"
  - "审查计划"
---

# Android AutoPlan

## 概述

功能需求 → Android 拆分 → 四层审查 + 自省 → 可执行的 Plan。

**启动时声明:** "我正在使用 android-autoplan skill。"

## 调用方式

```bash
/android-autoplan                         # 交互式: 输入需求 → 拆分 → 审查
/android-autoplan <需求描述>               # 直接传入需求
/android-autoplan review <plan-file>      # 仅审查已有 plan (跳过拆分)
/android-autoplan split <需求描述>        # 仅拆分不审查
```

**参数处理:**
- `review`: 读取指定的 plan 文件，直接进入 Phase 2 (CEO Review)
- `split`: 拆分完成后输出 plan，不进入审查流程
- 无参数或带需求描述: 完整流程 (拆分 → 审查)
- **执行问题修订模式:** 当 worktree-runner 执行中发现 plan 级别问题时，
  会附带 plan 文件调用本 skill 的 `review` 模式。此时:
  1. 跳过 Phase 1 (拆分)，直接读取 plan 文件
  2. 自动查找同名 execution-issues 文件:
     如果 plan 文件为 `docs/plans/2026-04-10-auth.md`，
     查找 `docs/plans/2026-04-10-auth-execution-issues.md`
  3. 如果找到: 将 execution-issues 作为额外输入贯穿所有审查阶段
     （按 android-worktree-runner 定义的 execution-issues 格式解析: 包含 "## 概要" 和 "### Task N:" 结构）
  4. 如果未找到: 正常执行 review 流程

**零外部依赖:** 此 skill 不依赖 gstack 二进制工具链、Codex、browse、design。
仅使用 Claude Code 原生工具 (Read、Write、Edit、Grep、Glob、Bash)。

## 前置: 项目环境检测

在所有流程开始前，自动检测项目环境。检测结果贯穿后续所有审查阶段。

### 步骤 1: 确认项目根目录

> 参考: [android-shared/detection.md](.claude/skills/android-shared/detection.md) — 公共环境检测脚本

```bash
# 从当前目录向上查找项目根 (含 build.gradle 或 settings.gradle)
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

echo "PROJECT_ROOT: $PROJECT_ROOT"
```

### 步骤 2: 技术栈检测

按以下规则扫描项目，生成技术栈档案:

**UI 框架:**
```bash
# Compose 检测
grep -r "androidx.compose" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
grep -rl "@Composable" "$PROJECT_ROOT/app/src" 2>/dev/null | head -5

# XML Views 检测
find "$PROJECT_ROOT/app/src/main/res/layout" -name "*.xml" 2>/dev/null | head -5
```

**异步框架:**
```bash
grep -r "kotlinx.coroutines" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
grep -rl "import kotlinx.coroutines" "$PROJECT_ROOT/app/src" 2>/dev/null | head -5
grep -rl "import io.reactivex" "$PROJECT_ROOT/app/src" 2>/dev/null | head -5
```

**依赖注入:**
```bash
grep -r "com.google.dagger:hilt" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
grep -r "io.insert-koin" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
```

**网络库:**
```bash
grep -r "com.squareup.retrofit2" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
grep -r "io.ktor" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
```

**数据库:**
```bash
grep -r "androidx.room" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
grep -r "app.cash.sqldelight" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
```

**图片加载:**
```bash
grep -r "io.coil-kt" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
grep -r "com.github.bumptech.glide" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
```

**导航:**
```bash
grep -r "androidx.navigation" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
```

**输出技术栈档案:**
```
=== 项目技术栈档案 ===
UI:         Compose / XML Views / 混用
异步:       Coroutines / RxJava / 无
DI:         Hilt / Koin / 无
网络:       Retrofit / Ktor / 无
数据库:     Room / SQLDelight / 无
图片:       Coil / Glide / 无
导航:       Navigation Compose / Navigation Component / 无
```

### 步骤 3: 架构检测

```bash
# 读取包结构
find "$PROJECT_ROOT/app/src/main/java" -type d 2>/dev/null | head -20
find "$PROJECT_ROOT/app/src/main/kotlin" -type d 2>/dev/null | head -20

# 检测分层关键词
grep -rl "ViewModel" "$PROJECT_ROOT/app/src" 2>/dev/null | head -5
grep -rl "Repository" "$PROJECT_ROOT/app/src" 2>/dev/null | head -5
grep -rl "UseCase\|Interactor" "$PROJECT_ROOT/app/src" 2>/dev/null | head -5
grep -rl "Reducer\|Action\|Event" "$PROJECT_ROOT/app/src" 2>/dev/null | head -5
```

根据包结构和代码模式，推断架构模式:
- `ui/` + `viewmodel/` + `repository/` → MVVM
- `presentation/` + `domain/` + `data/` → Clean Architecture
- `reducer/` + `action/` + `state/` → MVI
- 其他 → 记录实际观察到的模式

**输出:**
```
=== 项目架构 ===
推断架构: MVVM
包结构: com.example.app.ui / .viewmodel / .repository / .data.remote
注意: 架构为推断结果，不限定 plan 必须遵循
```

### 步骤 4: 构建配置检测

```bash
# 读取 SDK 版本
grep -E "minSdk|targetSdk|compileSdk" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null

# 检测多模块
cat "$PROJECT_ROOT/settings.gradle" "$PROJECT_ROOT/settings.gradle.kts" 2>/dev/null | grep "include"

# 检测已有 ProGuard 规则
find "$PROJECT_ROOT/app" -name "proguard-rules.pro" -o -name "proguard*.pro" 2>/dev/null
```

**输出:**
```
=== 构建配置 ===
minSdk: 24 | targetSdk: 34 | compileSdk: 34
模块: app, feature:login, core:data, core:common
ProGuard: app/proguard-rules.pro
```

---

## Phase 1: 需求拆分

接收功能需求，按 Android 拆分规则生成结构化 plan。

### 步骤 1: 接收需求

**交互式:** 使用 AskUserQuestion 收集需求描述。

> 请描述要实现的功能需求:
> (支持自然语言、issue 链接、user story 等格式)

**带参数:** 直接使用传入的需求描述。

### 步骤 2: 分析需求

分析需求中涉及的技术领域:

1. **是否需要网络请求?** → 涉及 API 接口、数据模型、网络权限
2. **是否需要本地存储?** → 涉及 Room/SP、Migration
3. **是否需要新页面?** → 涉及 UI、Navigation、Manifest
4. **是否需要新权限?** → 涉及 Manifest、运行时权限请求
5. **是否需要后台工作?** → 涉及 Service/WorkManager/Foreground Service
6. **是否涉及多媒体?** → 涉及相机/存储/音频权限、资源文件
7. **是否涉及第三方 SDK?** → 涉及 Gradle 依赖、初始化、ProGuard

### 步骤 3: 按 Android 拆分规则生成任务

按以下层次顺序生成任务。每个任务 = 一个独立 commit，commit 后项目可编译。

**第一层: 基础设施** (如果需要)

根据需求分析，如果涉及以下任何一项，生成对应任务:

- **Gradle 依赖变更:** 添加新库依赖、版本更新、新 Gradle 插件
- **Gradle 配置变更:** 新模块、BuildConfig 字段、BuildType、Flavor
- **Manifest 变更:** 权限声明、组件声明 (Activity/Service/Receiver/Provider)、
  intent-filter、metadata
- **ProGuard/R8 规则:** 新依赖的 keep 规则

> 这些任务不适合 TDD，标记 **TDD: skip**。

**第二层: 数据层**

- 数据模型定义 (data class / Entity / Parcelable)
- API 接口定义 (Retrofit interface / Ktor client)
- Repository 实现
- 本地存储 (Room DAO + Entity / SharedPreferences / DataStore)
- 数据映射器 (DTO ↔ Domain Model)

> 这些任务必须经过 TDD，标记 **TDD: required**。在步骤描述中包含 TDD 测试要求。

**第三层: 业务逻辑层**

- UseCase / Interactor
- ViewModel / 状态管理 (StateFlow / LiveData)
- 业务规则验证
- 错误处理策略

> 这些任务必须经过 TDD，标记 **TDD: required**。在步骤描述中包含 TDD 测试要求。

**第四层: 表现层**

- UI 组件 (Compose @Composable / XML layout)
- Navigation 路由定义
- 状态绑定 (collectAsState / observeAsState)
- 交互反馈 (Snackbar / Dialog / Toast)
- 动画 / 过渡效果

> 这些任务必须经过 TDD，标记 **TDD: required**。在步骤描述中包含 TDD 测试要求。

**第五层: 测试**

- 单元测试 (对应第二、三层的每个任务)
- UI 测试 / 集成测试 (对应第四层)
- 边界条件测试 (空数据、网络错误、权限拒绝)

> 测试任务本身不需要 TDD，标记 **TDD: skip**。

### 步骤 4: 必须检查项核对

逐项核对以下清单。如果需要但 plan 中没有，添加任务:

| # | 检查项 | 判断方法 |
|---|--------|----------|
| 1 | Gradle 变更 | 是否需要新依赖/新模块/新 buildConfig? |
| 2 | Manifest 变更 | 是否需要新权限/新组件/intent-filter? |
| 3 | ProGuard 规则 | 新依赖是否需要 keep 规则? |
| 4 | Navigation 变更 | 是否涉及新页面/新路由? |
| 5 | Room Migration | 是否修改了 Entity 结构? |
| 6 | 资源文件 | 是否需要新字符串/drawable/样式/主题? |
| 7 | 测试覆盖 | 每个非基础设施任务是否有对应测试? |

**核对结果:** 列出每项的判断和是否需要添加任务。

### 步骤 5: 输出初版 Plan

按 android-worktree-runner 兼容格式输出:

```markdown
# Plan: <功能标题>

> 生成于 <日期> | android-autoplan | 项目: <项目名>

## 任务列表

### Task 1: <标题>

**层级:** 基础设施 / 数据层 / 业务逻辑层 / 表现层 / 测试
**TDD:** required / skip

**步骤:**
- [ ] 步骤 1 描述
- [ ] 步骤 2 描述

**涉及文件:**
- 修改: `app/build.gradle.kts`
- 创建: `app/src/main/java/.../Xxx.kt`

---

### Task 2: <标题>
...
```

**TDD 标签分配规则 (强制):**

| 任务层级 | TDD 标签 | 原因 |
|---------|---------|------|
| 基础设施 | **skip** | Gradle/Manifest/ProGuard 不适合 TDD |
| 数据层 | **required** | Repository、数据模型、API 接口必须有测试 |
| 业务逻辑层 | **required** | UseCase、ViewModel 是核心逻辑，TDD 价值最高 |
| 表现层 | **required** | UI 组件需要测试状态绑定和交互逻辑 |
| 测试 | **skip** | 测试任务本身就是测试，不需要 TDD |

**规则: 除基础设施和测试层外，所有任务 TDD = required。不可协商。**

> 💾 **[检查点]** Plan 初版已生成。建议运行 `/android-checkpoint save` 保存进度，防止上下文丢失。

使用 AskUserQuestion 确认:
> 已生成 N 个任务。是否需要调整?
> - A) 确认，进入审查
> - B) 合并某些任务
> - C) 拆分某些任务
> - D) 添加遗漏的任务
> - E) 重新生成

---

## Phase 2: CEO Review (范围与策略)

审查 plan 的范围、策略和 Android 平台约束。

### 步骤 1: 前提挑战

对 plan 的核心假设提出质疑:

1. **这个功能真的需要吗?** 用户会在什么场景触发? 如果不做会怎样?
2. **Android 平台是这个功能的最佳载体吗?** 是否应该用 Web/小程序/PWA?
3. **需求的优先级是否正确?** 是否有更小的 MVP 可以先验证?
4. **时间线是否合理?** 考虑到 Android 开发的特殊性 (构建慢、测试慢、多设备适配)

### 步骤 2: Android 平台约束检查

检查 plan 中的功能是否受 Android 平台限制:

| 约束类型 | 检查内容 |
|----------|----------|
| Android 版本 | 功能所需 API 是否在 minSdk 上可用? 是否需要 version check? |
| 特殊权限 | 位置/相机/存储/电话/通知，哪些需要运行时请求? |
| 后台执行 | 是否受 Doze/App Standby 限制? 是否需要 WorkManager/FCM? |
| 分包限制 | 新增依赖是否导致 64K 方法数超限? 是否需要 multidex? |
| 存储访问 | Scoped Storage 限制? Media Store API? |
| 前台服务 | 是否需要 Foreground Service? Android 14+ 的限制? |
| 安全合规 | 是否涉及敏感数据? 加密要求? SAFETY_LABEL? |

**如果发现平台约束:** 标记受影响的任务，在任务描述中添加约束说明。

### 步骤 3: 范围砍伐

对 plan 进行范围评估:

1. **MVP 版本:** 哪些任务是核心路径? 哪些可以延后?
2. **Android 特有简化:** 是否有 Android SDK 原生 API 可以替代第三方库?
   (如用 `ActivityResultContracts` 替代 `onActivityResult`，
   用 `PhotoPicker` 替代自定义图片选择)
3. **已有能力复用:** 项目内已有的工具类/基类/扩展函数能否复用?
4. **Jetpack 库覆盖:** Jetpack 标准库是否已经提供了所需功能?

**范围砍伐规则:**
- 如果任务数 > 10，考虑是否可以拆分成两个 phase
- 基础设施任务不砍 (它们是骨架)
- 测试任务不砍 (它们是安全保障)
- 砍业务逻辑层的可选功能和表现层的可选效果

### 步骤 4: 产出范围确认后的 Plan

更新 plan 文件:
- 标记被砍掉的任务 (移到 "延后考虑" 部分)
- 添加平台约束说明到受影响的任务
- 添加复用已有代码的说明

> 💾 **[检查点]** CEO Review 已完成。建议运行 `/android-checkpoint save` 保存进度。

---

## Phase 3: Android Design Review (按需加载)

> Android UI 设计审查由独立 skill `/android-design-review` 执行。
> 此阶段仅在用户需要时加载，避免无谓消耗上下文。

### 步骤 1: 询问用户是否需要设计审查

在 Phase 2 (CEO Review) 完成后，进入 Phase 3 前询问:

> 当前功能是否需要基于 Figma 设计稿进行 UI 审查?
> - A) 需要 — 请提供 Figma 设计稿链接:
> - B) 不需要 — 跳过此阶段，直接进入 Phase 4 工程审查

**用户选择 A 时:** 收集 Figma URL 后继续步骤 2。URL 格式示例:
`https://www.figma.com/design/xxxxx/...?node-id=yyyyy`

**跳过条件:** 以下情况可直接跳过询问:
- 需求明确不涉及 UI (纯后端逻辑、数据迁移、SDK 集成等)
- 用户在需求描述中已说明"不需要设计审查"

### 步骤 2: 执行设计审查 (用户选择 A 时)

1. 使用 Skill 工具调用 android-design-review，传入步骤 1 收集到的 Figma URL
   (skill: "android-design-review", args: "<用户提供的 figma-url>"):
2. `/android-design-review` 执行完成后，产出以下文件:
   - **设计规格文档** — `docs/plans/<slug>-design-spec.md`
     (包含颜色、字体、间距、圆角、阴影等完整 token，组件映射表，
      资源导出清单，状态/深色模式/无障碍覆盖)
   - **Plan 注入片段** — `<!-- DESIGN -->` 和 `<!-- DESIGN-NEW -->` 格式块
     (已嵌入 design-spec 文件中，可直接追加到 plan 任务步骤)

### 步骤 3: 将设计规格关联到 Plan

**不复制设计数据到 plan 文件中** (避免上下文膨胀)。改为在 plan 文件中引用设计规格文件:

**在 plan 文件头部添加设计规格引用:**
```markdown
## Design Spec

> 来源: <figma-url> | 审查于 <日期>
> 完整规格: docs/plans/<slug>-design-spec.md
```

**将 design-spec.md 中的 `<!-- DESIGN -->` 和 `<!-- DESIGN-NEW -->` 注释块
追加到 plan 中对应任务的步骤末尾。** design-review 已按 plan 任务结构生成了
这些注释块，直接复制即可。

**将组件映射表和资源导出清单引用附加到 plan 末尾:**
```markdown
## 组件映射

> 完整映射见: docs/plans/<slug>-design-spec.md § 组件映射

| Figma 组件 | Android 实现 | 操作 |
|-----------|-------------|------|
| Primary Button | AppButton (core-ui) | 复用 |
| ... | ... | ... |

## 资源导出清单

> 完整清单见: docs/plans/<slug>-design-spec.md § 资源导出清单

| 资源名 | 类型 | 导出状态 |
|--------|------|---------|
| ic_arrow_back | SVG | 已导出 |
| ic_logo | SVG | 导出失败，需手动处理 |
```

**注意:** 组件映射表和资源清单在此处只列摘要。完整数据在 design-spec.md 中，
worktree-runner 执行任务时从 design-spec.md 读取。

### 步骤 4: 标记设计依赖

对于依赖设计规格的任务，在任务步骤中添加设计参考标记:
- 颜色值使用 `@color/xxx` 或 `MaterialTheme.colorScheme.xxx`，备注设计稿原始值
- 间距使用设计稿 dp 值 (Figma px = Android dp，1:1)
- 字体大小: 正文使用 sp (用户可调)，固定尺寸元素使用 dp
- 圆角/阴影使用项目已有组件方案，不直接用原生 clip/elevation

### 步骤 5: 继续 Phase 4

设计审查完成后 (或用户选择跳过)，继续进入 Phase 4 工程审查。
Phase 4 审查时参考已注入的 `<!-- DESIGN -->` 注释块和 design-spec.md 文件，
确保技术实现与设计意图一致。

---

## Phase 4: Android Eng Review (核心审查 — Subagent 模式)

这是最关键的审查阶段。为避免上下文溢出，**每个审查维度派发独立 subagent**。
主 context 只接收紧凑的审查结论。

### 上下文预算

| 阶段 | 预估消耗 | 方式 |
|------|---------|------|
| Phase 1 (拆分) | ~15% | 主 context |
| Phase 2 (CEO) | ~10% | 主 context |
| Phase 3 (Design) | ~5% (跳过) 或 ~20% (加载) | 主 context 或 skill |
| Phase 4 (Eng) | **~5%** (仅汇总结论) | subagent |
| Phase 5 (DX) | **~5%** (仅汇总结论) | subagent |
| Phase 3.5 (自省) | **~3%** (条件触发) | subagent |
| 最终审批 | ~10% | 主 context |

### 前置: 准备审查输入

在派发 subagent 前，将 plan 保存到文件并准备共享输入:

```bash
# plan 已保存到 docs/plans/<slug>.md
# 技术栈档案在前置检测阶段已生成
# 以下信息作为 subagent 的共享输入
```

**共享输入 (每个 subagent 都会收到):**
- plan 文件路径: `docs/plans/<slug>.md`
- 项目技术栈档案 (前置检测阶段的输出)
- 项目架构推断结果
- 构建配置 (minSdk/targetSdk/compileSdk/模块列表)
- 设计规格文件路径 (如果 Phase 3 执行了 design-review)

### 步骤 1: 派发架构一致性审查

使用 Agent 工具派发 subagent:

```
你是 Android 架构审查员。审查以下 plan 的架构一致性。

项目技术栈: <技术栈档案>
项目架构: <架构推断>
Plan 文件: <路径>

审查要点:
1. 新代码放在哪个模块/包? 是否遵循项目已有模块划分?
2. 依赖方向是否正确? (高层不依赖低层具体实现)
3. 是否违反项目已有分层规则?
4. 新依赖是否引入架构冲突?

输出格式 (控制在 300 字以内):
- 结论: 通过 / 需要调整
- 问题列表 (如有): 每个问题一行，包含任务编号和具体建议
```

### 步骤 2: 派发 Gradle + Manifest 审查

```
你是 Android 构建配置审查员。审查 plan 中所有 Gradle 和 Manifest 变更。

项目构建配置: <配置信息>
Plan 文件: <路径>

审查要点:
1. Gradle: 依赖版本一致性、新插件、BuildType、多模块依赖
2. Manifest: 组件声明、权限、exported 属性、intent-filter
3. ProGuard: 新依赖的 keep 规则

输出格式 (控制在 300 字以内):
- 结论: 通过 / 需要调整
- 问题列表 (如有)
```

### 步骤 3: 派发生命周期安全审查

```
你是 Android 生命周期安全审查员。审查 plan 中的生命周期风险。

项目技术栈: <技术栈档案>
Plan 文件: <路径>

审查要点:
1. ViewModel 是否持有 Context/View 引用?
2. Coroutine scope 是否正确绑定?
3. Flow 收集是否在正确生命周期? (collectAsStateWithLifecycle vs collectAsState)
4. 注册/注销是否配对? (BroadcastReceiver, Sensor, Location, DisposableEffect)

输出格式 (控制在 300 字以内):
- 结论: 通过 / 需要调整
- 问题列表 (如有): 每个问题标注具体任务和风险等级 (高/中/低)
```

### 步骤 4: 派发测试审查

```
你是 Android 测试策略审查员。审查 plan 的测试覆盖。

项目技术栈: <技术栈档案>
Plan 文件: <路径>

审查要点:
1. 每个非基础设施任务是否有对应测试?
2. 测试类型是否合理? (单元/Robolectric/UI)
3. 是否覆盖边界条件? (空数据/网络错误/权限拒绝)
4. Mock 策略是否明确? (MockK vs Mockito)
5. 每个非基础设施任务是否标记了 **TDD: required**?
6. TDD 任务的步骤描述中是否包含足够的边界条件? (参考 Android 平台边界矩阵: 生命周期、配置变更、权限、网络、存储、并发、内存、兼容性)
7. 如果任务包含 UI 逻辑，步骤中是否同时包含 JVM 单元测试和 Instrumented 测试描述?

输出格式 (控制在 300 字以内):
- 结论: 通过 / 需要调整
- 缺失测试列表 (如有): 任务编号 + 建议的测试类型
- TDD 合规性: N/M 非基础设施任务标记了 TDD: required
- 同时产出测试计划写入 docs/plans/<slug>-test-plan.md
```

### 步骤 5: 派发性能 + 失败模式审查

```
你是 Android 性能和安全审查员。评估 plan 的性能风险和失败模式。

项目技术栈: <技术栈档案>
Plan 文件: <路径>

性能评估:
| 检查项 | 关注点 |
|--------|--------|
| 内存泄漏 | ViewModel 持有 Context? Listener 未注销? |
| 列表性能 | LazyColumn 是否使用 key? N+1 查询? |
| 图片加载 | Coil/Glide 占位符? 大图压缩? |
| 数据库效率 | Room 索引? 全表扫描? |
| 启动时间 | Application.onCreate 重操作? |
| UI 渲染 | Compose 重组次数? 不必要的 state 读取? |
| APK 大小 | 新增依赖对体积的影响? |

失败模式:
| 失败模式 | 触发条件 | 应对策略 |
|----------|----------|----------|
| 网络不可用 | 飞行模式/无信号 | 缓存 + 错误提示 |
| API 错误 | 500/超时 | 重试 + 降级 |
| 权限被拒 | 用户拒绝 | 引导去设置页 |
| 数据库损坏 | Migration 失败 | 备份 + 重建 |
| 低内存被杀 | 后台回收 | SavedStateHandle |
| 并发冲突 | 同时修改 | 乐观锁/事务 |

输出格式 (控制在 300 字以内):
- 性能风险列表 + 缓解建议
- 失败模式补充 (plan 未覆盖的)
```

### 步骤 6: 汇总审查结论

所有 subagent 返回后，主 context 汇总:

1. 读取每个 subagent 的审查结论
2. 将发现的问题分类:
   - **阻塞问题** — 必须修复才能继续 (如架构冲突、安全风险)
   - **建议改进** — 应该修复但不阻塞 (如命名不一致、缺少测试)
   - **信息备注** — 供执行时参考 (如性能优化建议)
3. 更新 plan 文件:
   - 阻塞问题: 修改受影响任务的步骤
   - 建议改进: 添加注释到相关任务
   - 信息备注: 添加到 plan 末尾的 "## 审查备注" 部分
4. 更新失败模式注册表 (如果性能 subagent 发现了新失败模式)

**如果存在阻塞问题:** 使用 AskUserQuestion 展示阻塞问题并询问处理方式。
**如果没有阻塞问题:** 直接进入 Phase 5。

> 💾 **[检查点]** 工程审查已完成。建议运行 `/android-checkpoint save` 保存进度。

---

## Phase 5: Android DX Review (开发者体验 — Subagent 模式)

### 步骤 1: 派发 DX 审查

```
你是 Android 开发者体验审查员。审查 plan 对 DX 的影响。

项目技术栈: <技术栈档案>
项目架构: <架构推断>
Plan 文件: <路径>

检查维度:
1. 命名规范: 新增代码是否遵循项目已有命名风格?
2. 代码复用: 通用逻辑是否放 core/? 可复用 Compose 组件?
3. 文档更新: README/API 文档/CLAUDE.md 是否需要更新?
4. CI/CD: 新依赖是否需要更新 CI 缓存? 新测试是否影响 CI 时间?
5. 开发工作流: 是否需要新 Gradle task? 特定设备配置? 环境变量?

输出格式 (控制在 300 字以内):
- 结论: 通过 / 需要调整
- DX 建议列表 (如有)
```

### 步骤 2: 汇总并附加到 Plan

将 DX 审查结论附加到 plan 文件末尾的 "## DX 建议" 部分。

---

## Phase 3.5: 自省 (Subagent 模式)

Phase 2-5 回答 "plan 写得对不对?"。Phase 3.5 回答 "plan 写了正确的东西吗?"

这是一个对抗性审查，与其他审查维度互补。它不看 plan 的表面质量，
而是审视 plan 背后的决策过程和隐含假设。

### 步骤 1: 派发自省 subagent

**注意:** 仅在 Phase 4 发现至少 1 个"需要调整"的问题时才派发此 subagent。
如果 Phase 4-5 全部通过，说明 plan 质量已足够高，自省的边际收益低，跳过以节省上下文。

使用 Agent 工具派发:

```
你是这个 plan 的原作者的对手。你的工作是找出作者没想到的东西。

Plan 文件: <路径>
项目技术栈: <档案>
项目架构: <架构推断>

不要逐项检查 (其他审查员已经做了)。你要做的是:

1. 假设审计: 列出 plan 中所有隐含假设 (至少 3 个)。
   对每个假设: 如果假设不成立，哪个任务会失败? 严重程度?
   例: 假设 "API 返回格式与文档一致" → 如果不一致，数据层全废。

2. 决策回溯: 找出 plan 中 2-3 个品味决策 (非机械决策)。
   对每个: 如果反着选，结果会更好还是更差? 为什么?

3. 盲点探测: 想象你是拿到这个 plan 的开发者。
   你打开代码库，准备从 Task 1 开始。你会在哪里卡住?
   你会问什么问题但 plan 里没有回答?

4. 剪刀测试: 如果必须砍掉 30% 的任务，你会砍哪些?
   被砍掉的部分是否暴露了 plan 的过度设计?

输出: 严格控制在 500 字以内。只报告真正有洞察的发现，
不要重复其他审查维度已经覆盖的问题。
如果没有有价值的发现，直接说 "未发现显著盲点"。
```

### 步骤 2: 处理自省结论

**如果 subagent 报告 "未发现显著盲点":**
- 跳过，直接进入决策系统和最终审批

**如果 subagent 发现了盲点:**

将发现分为两类:

1. **需要行动的盲点** — 隐含假设不成立会导致任务失败
   - 添加新任务或修改现有任务来覆盖
   - 或将假设明确记录到 plan 中，让执行者注意

2. **需要用户知晓的盲点** — 决策回溯发现更好的选择
   - 记录为品味决策，附到最终审批摘要中
   - 不自动修改 plan，让用户决定

**将自省结论附加到 plan 文件末尾的 "## 自省备注" 部分。**

---

## 决策系统

沿用 autoplan 的三分法决策系统:

### 机械决策 (自动处理)

有明确正确答案的决策，静默自动处理，不中断流程。

**Android 场景示例:**
- 依赖注入方式: 跟随项目已有 (项目用 Hilt 就用 Hilt)
- 测试框架: 跟随项目已有 (项目用 JUnit5 就用 JUnit5)
- 构建脚本语言: 跟随项目已有 (项目用 .kts 就用 .kts)
- 序列化方式: 跟随项目已有 (项目用 kotlinx.serialization 就用它)
- 日志框架: 跟随项目已有 (项目用 Timber 就用它)

**记录:** 所有机械决策记录到决策审计日志。

### 品味决策 (记录到最终审批)

合理人可能有不同看法的决策，不自动决定，记录下来供用户最终审批。

**Android 场景示例:**
- State 管理: StateFlow vs LiveData vs Compose State
- 错误处理: sealed class Result vs Either
- 模块化粒度: 按 feature 拆还是按 layer 拆
- 测试覆盖深度: 只测 happy path 还是覆盖所有边界

**记录格式:**
```
品味决策 #1: State 管理方式
- 选项: StateFlow / LiveData / Compose State
- 选择: StateFlow (项目已有 Coroutines 基础设施)
- 原因: 与项目技术栈一致，支持 lifecycle-aware 收集
```

### 用户挑战 (从不自动决策)

两个视角 (审查者 + 项目上下文) 都认为用户的方向需要改变时，绝不自动决策。

**Android 场景示例:**
- 使用已废弃的 API (如 AsyncTask)
- 引入与项目架构冲突的库
- 跳过安全性检查 (如 HTTPS 证书校验)
- 在主线程执行耗时操作
- 硬编码敏感信息 (API key、密码)

**处理:** 标记为用户挑战，在最终审批中明确列出，需要用户确认。

---

## 最终审批

所有审查阶段完成后，展示审批摘要:

```
=== Android AutoPlan 审批摘要 ===

Plan: <功能标题>
任务数: N (原 N + 新增 M - 砍掉 K)

决策统计:
- 机械决策: X 项 (已自动处理)
- 品味决策: Y 项 (附下文)
- 用户挑战: Z 项 (需要确认)

用户挑战:
1. [描述] → 建议: [替代方案]

品味决策:
1. [描述] → 选择: [方案] → 原因: [理由]

性能风险:
1. [描述] → 缓解: [方案]

延后考虑:
1. [描述] → 原因: [理由]

产出文件:
- Plan: docs/plans/<slug>.md
- 测试计划: docs/plans/<slug>-test-plan.md
```

> 💾 **[检查点]** 即将进入执行阶段。建议运行 `/android-checkpoint save` 保存进度。

使用 AskUserQuestion:
> 审查完成。如何处理?
> - A) 批准并执行 — 保存 plan 文件，自动调用 /android-worktree-runner 开始执行
> - B) 仅保存 — 保存 plan 文件，稍后手动 /android-worktree-runner import
> - C) 修改 — 指定需要调整的部分
> - D) 重新审查 — 从某个阶段重新开始

### 自动衔接 android-worktree-runner

**当用户选择 A (批准并执行) 时:**

1. 将 plan 文件保存到 `docs/plans/<slug>.md`
2. 使用 Skill 工具调用 android-worktree-runner (skill: "android-worktree-runner", args: "import docs/plans/<slug>.md"):
3. android-worktree-runner 接管执行流程

**衔接协议:**
- `android-autoplan` 产出的 plan 文件使用 Superpowers 格式 (`### Task N:`)，
  android-worktree-runner 的 Phase 0 可直接解析此格式
- plan 文件路径作为参数传递给 android-worktree-runner
- android-worktree-runner 负责创建 worktree、执行任务、Android 验证
- `android-autoplan` 的审查结论 (失败模式、性能风险、ProGuard 提醒)
  已嵌入 plan 文件的任务步骤中，android-worktree-runner 执行时会看到

**完整流程链路:**
```
功能需求
  ↓
android-brainstorm: 头脑风暴 → 思考文档
  ↓
android-autoplan Phase 1: 需求拆分 → 初版 plan
  ↓
android-autoplan Phase 2: CEO Review → 范围确认
  ↓
android-autoplan Phase 3: Design Review (按需)
  ├─ 需要设计审查 → 调用 /android-design-review → 注入设计规格
  └─ 不需要 → 跳过
  ↓
android-autoplan Phase 4-5: Eng Review + DX Review → 已审查 plan (subagent)
  ↓
android-autoplan Phase 3.5: 自省 (条件触发) → 盲点/假设/决策回溯
  ├─ Phase 4 有问题 → 执行自省
  └─ Phase 4 全部通过 → 跳过
  ↓
android-autoplan 最终审批: 用户批准
  ↓
自动调用 /android-worktree-runner import <plan-file>
  ↓
android-worktree-runner Phase 2: 执行任务 → Android 验证 → commit
  ↓
android-worktree-runner Phase 3: 完成
  ├─ 代码审查 → /android-code-review
  ├─ QA 测试 → /android-qa
  ├─ 文档更新 → /android-document-release
  ├─ 反馈修订 → /android-autoplan review (带 execution-issues)
  └─ 合并/PR/保留
```

---

## 产出文件

### Plan 文件

写入 `docs/plans/<slug>.md`，格式兼容 android-worktree-runner 导入:

```markdown
# Plan: <功能标题>

> 生成于 <日期> | android-autoplan | 审查通过
> 项目技术栈: Compose + Hilt + Room + Coroutines
> 项目架构: MVVM

## 任务列表

### Task 1: 添加网络依赖
**TDD:** skip
- [ ] 在 app/build.gradle.kts 添加 Retrofit + OkHttp 依赖
- [ ] 同步 Gradle 确认编译通过

### Task 2: 定义 API 接口和数据模型
**TDD:** required
- [ ] 创建 LoginRequest / LoginResponse 数据类
- [ ] 创建 AuthService Retrofit 接口
- [ ] TDD: 编写 Repository 接口测试 (happy path + 网络失败边界)

### Task 3: 实现 Repository
**TDD:** required
- [ ] 创建 AuthRepository 接口
- [ ] 实现 AuthRepositoryImpl (网络 + 本地缓存)
- [ ] TDD: 编写单元测试 (缓存命中/未命中 + 网络错误降级)

...
```

### 测试计划文件

写入 `docs/plans/<slug>-test-plan.md` (详见 Phase 4 步骤 4)

### 失败模式注册表

嵌入 plan 文件末尾的 "## 失败模式" 部分 (详见 Phase 4 步骤 5)

---

## 与其他 Skill 的衔接

```
/android-brainstorm       → 头脑风暴 → 需求定义
/android-checkpoint        → 保存/恢复 autoplan 会话状态
/android-autoplan         → 拆分 + 审查 + 自省 → plan 文件 → 自动调用 android-worktree-runner
/android-design-review    → Figma 设计审查 (Phase 3 按需调用)
/android-worktree-runner  → 导入 plan → 执行 → 代码
/android-code-review     → 代码质量审查 (worktree-runner 完成后)
/android-qa               → 功能级 QA 测试 (worktree-runner 完成后)
/android-investigate      → 系统化 bug 排查 (执行中遇到 bug 时)
/android-document-release → 文档同步更新 (代码完成后)
```

**衔接规则:**
- `android-autoplan` 审查通过后，**自动调用** `/android-worktree-runner import <plan-file>`
- 产出的 plan 文件使用 Superpowers 格式 (`### Task N:`)，
  android-worktree-runner 的 Phase 0 可直接解析此格式
- 审查中发现的 Android 特有问题 (生命周期、ProGuard、Manifest)
  已在 plan 的任务步骤中明确标注，android-worktree-runner 执行时会看到
- 用户也可以选择仅保存不执行，稍后手动调用 android-worktree-runner

## 异常情况处理

| 场景 | 处理方式 |
|------|----------|
| 不在 Android 项目中 | 报错: "android-autoplan 需要 Android 项目" |
| build.gradle 解析失败 | 尝试 .kts 变体，仍失败则报错 |
| 技术栈检测不明确 | 列出检测结果让用户确认 |
| 架构检测失败 | 使用 "未检测到" 作为默认值，不限定架构 |
| Plan 文件已存在 | 询问: 覆盖 / 追加 / 取消 |
| 用户挑战未被解决 | 不自动通过，要求用户确认或修改 |
| android-worktree-runner 不可用 | 提示用户安装 android-worktree-runner skill，或选择仅保存 plan |
| git 仓库未初始化 | 提示用户先 `git init`，android-worktree-runner 依赖 git |
