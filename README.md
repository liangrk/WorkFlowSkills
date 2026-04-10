# Android Development Skills

一套专为 Android 开发设计的 Claude Code skill 工具链。覆盖从需求定义到代码交付的完整生命周期。

## 工作流全景

```
┌─────────────┐    ┌──────────────┐    ┌───────────────────┐    ┌──────────────────┐
│ brainstorm │───▶│  autoplan   │───▶│ design-review    │    │ worktree-runner │
│  需求定义   │    │  拆分+审查  │    │  Figma 审查(按需)  │    │   任务执行       │
└─────────────┘    └──────────────┘    └───────────────────┘    └──────┬─────────┘
       │                                      │                        │
       ▼                                      ▼                        ▼
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌───────┴──────┐
│ checkpoint │    │  code-review│    │  investigate │    │ doc-release  │
│  保存/恢复  │    │  代码审查    │    │  调试排查   │    │  文档更新    │
└─────────────┘    └──────────────┘    └─────────────┘    └──────────────┘
       │                                      │
       ▼                                      ▼
┌─────────────┐    ┌──────────────┐
│    qa      │    │  反馈回路   │
│  功能测试   │◀───▶│  runner→plan │
└─────────────┘    └──────────────┘
```

## Skill 列表

| Skill | 阶段 | 说明 | 调用方式 |
|-------|------|------|---------|
| `android-brainstorm` | 需求定义 | 头脑风暴、需求分析、方案探索 | `/android-brainstorm` |
| `android-checkpoint` | 持续化 | 保存/恢复 autoplan 会话状态，防止 /clear 丢失上下文 | `/android-checkpoint save` / `restore` |
| `android-autoplan` | 规划 | 需求拆分、四层审查、自省，产出可执行 plan | `/android-autoplan <需求>` |
| `android-design-review` | 审查 | Figma 设计稿审查，产出设计规格 (按需) | `/android-design-review <figma-url>` |
| `android-worktree-runner` | 执行 | 基于 git worktree 隔离执行 plan 任务，每任务自动验证 | `/android-worktree-runner` |
| `android-code-review` | 审查 | 代码质量审查 (架构、命名、生命周期、线程安全等) | `/android-code-review` |
| `android-qa` | 验证 | 功能级 QA (静态分析、构建测试、设备测试) | `/android-qa` |
| `android-investigate` | 调试 | 系统化 bug 排查 (四层分析: 表现→数据→逻辑→平台) | `/android-investigate <问题描述>` |
| `android-document-release` | 收尾 | 文档同步更新 (README/CHANGELOG/CLAUDE.md) | `/android-document-release` |

## 快速开始

### 完整流程 (推荐)

```bash
# 1. 头脑风暴
/android-brainstorm

# 2. 拆分 + 审查 + 自省 → 自动执行
/android-autoplan 实现用户登录功能

# 3. 执行 plan (autoplan 完成后自动调用)
# worktree-runner 完成后可选: 代码审查 → QA → 文档更新

# 4. 如果执行中发现问题:
/android-investigate 登录页面 crash
```

### 单独使用

每个 skill 都可以独立使用，不依赖其他 skill:

```bash
# 只拆分不审查
/android-autoplan split 实现用户注册功能

# 只审查已有 plan
/android-autoplan review docs/plans/2026-04-10-auth.md

# 只做 Figma 设计审查
/android-design-review https://www.figma.com/design/xxxxx/...

# 只做代码审查
/android-code-review

# 只做 QA
/android-qa smoke

# 调试问题
/android-investigate 崩溃时出现 NullPointerException

# 保存当前进度
/android-checkpoint save

# 恢复进度
/android-checkpoint restore
```

## 详细流程说明

### 1. 需求定义 (android-brainstorm)

```
/android-brainstorm
```

输出: 思考文档 (`docs/designs/<slug>-brainstorm.md`)，包含:
- 目标和约束
- 技术方向
- 边界和假设
- 推荐方案

### 2. 计划拆分 + 审查 (android-autoplan)

```
/android-autoplan <需求描述>
```

内部流程:

| Phase | 做什么 | 方式 |
|-------|--------|------|
| 前置 | 检测项目技术栈、架构、构建配置 | 主 context |
| Phase 1 | 需求拆分为结构化任务 | 主 context |
| Phase 2 | CEO Review: 范围砍伐、平台约束 | 主 context |
| Phase 3 | Design Review: Figma 设计规格 (按需加载) | Skill 调用 |
| Phase 4 | Eng Review: 架构/Gradle/生命周期/测试/性能 | **subagent** |
| Phase 5 | DX Review: 命名/复用/CI/文档 | **subagent** |
| Phase 3.5 | 自省: 假设审计/决策回溯/盲点探测 | **subagent** (条件触发) |
| 最终审批 | 展示决策统计，用户确认 | 主 context |

产出: `docs/plans/<slug>.md` (可执行 plan 文件)

**上下文优化:** Phase 4-5 和 Phase 3.5 使用 subagent 模式，
每个审查维度独立运行，主 context 仅接收紧凑结论。
整体上下文消耗约 35%，即使加载 Figma 设计数据也不会溢出。

### 3. 设计审查 (android-design-review, 按需)

当功能涉及 UI 时，autoplan Phase 3 会询问是否需要设计审查。
也可独立使用:

```
/android-design-review https://www.figma.com/design/xxxxx/...
```

产出: `docs/plans/<slug>-design-spec.md`，包含:
- 设计还原规格 (颜色、字体、间距、圆角、阴影)
- 组件映射表 (Figma 组件 → 项目已有组件)
- 资源导出清单 (icon、图片)
- 状态/深色模式/无障碍覆盖
- 可注入 plan 的 `<!-- DESIGN -->` 注释块

**关键规则:**
- Figma px = Android dp，1:1 直接转换
- 正文使用 sp，固定尺寸元素使用 dp
- 圆角/阴影使用项目已有组件方案，不直接用原生 API
- icon 默认 3 倍图导出
- SVG 导出失败不自行生成，列出给用户手动处理

### 4. 任务执行 (android-worktree-runner)

```
/android-worktree-runner
```

核心机制:
- 一个 Plan = 一个 git worktree (完全隔离)
- 逐任务顺序执行，每任务 commit 前自动验证 (build → lint → test)
- 任务状态实时持久化到 `tasks.json`，支持 `/clear` 后恢复
- 支持 `/clear` → `/android-worktree-runner` 无缝恢复

执行完成后提供后续操作:
- A) 保留 / B) 合并 / C) PR / D) 删除 worktree
- E) 反馈回路: 将问题传回 autoplan 修订 plan
- F) 代码审查 / G) QA / H) 文档更新

### 5. 代码审查 (android-code-review)

```
/android-code-review
/android-code-review feature/login
```

六维度审查 (每个维度派发独立 subagent):
1. 架构一致性 (模块依赖方向、分层、DI)
2. 命名与代码风格 (项目规范、Kotlin 惯例)
3. 生命周期与内存安全 (Context 泄漏、Listener、Coroutine scope)
4. 线程与并发 (主线程 IO、UI 线程安全、Compose 重组)
5. Android 特有 (资源泄漏、Bitmap、数据库事务、权限)
6. 可测试性 (依赖可 mock、硬编码检测)

产出: `docs/reviews/<branch>-code-review.md`

### 6. QA 测试 (android-qa)

```
/android-qa
/android-qa smoke
/android-qa regression
```

三层测试:
1. **静态分析** (无需设备): 代码模式、资源完整性、Manifest、ProGuard
2. **构建+单元测试** (无需设备): assembleDebug、lintDebug、testDebugUnitTest
3. **设备测试** (需要 adb): 安装 APK、运行 UI 验证

包含修复循环: 发现 bug 后自动修复 → 重新验证，最多 3 轮。

产出: `docs/reviews/<branch>-qa-report.md`

### 7. 调试排查 (android-investigate)

```
/android-investigate 登录页面 crash 时出现 NullPointerException
```

四层排查:
1. **表现层**: stack trace 分析、异常模式
2. **数据层**: API 响应、DTO 映射、数据库、缓存
3. **逻辑层**: 状态转换、条件分支、边界条件
4. **平台层**: 生命周期、权限、内存、线程、兼容性

产出: `docs/reviews/investigate-<timestamp>.md`

### 8. 检查点 (android-checkpoint)

```
/android-checkpoint save    # 保存当前会话状态
/android-checkpoint restore  # 恢复上次保存的状态
/android-checkpoint status    # 查看所有检查点
```

保存内容: 技术栈档案、架构推断、plan 信息、审查结论、决策记录、待处理事项。
解决 `/clear` 或会话重启后上下文丢失的问题。

### 9. 文档更新 (android-document-release)

```
/android-document-release
```

自动检测需要更新的文档: README、CHANGELOG、CLAUDE.md、API 文档、模块文档。
展示 diff 格式的变更建议，用户确认后写入。

产出: `docs/reviews/<branch>-doc-update.md`

## 反馈回路

执行中发现 plan 级别问题时，可自动反馈给 autoplan 修订:

```
worktree-runner Phase 3
  └─ E) 反馈修订 → 写入 execution-issues → 调用 autoplan review
       └─ autoplan 读取 plan + issues → 重新审查 → 产出修订版
           └─ 用户确认 → 重新导入 worktree-runner 执行
```

## 检查点保存

autoplan 在关键节点自动保存检查点:
- Phase 1 完成后 (plan 初版)
- Phase 2 完成后 (CEO Review)
- Phase 4 完成后 (Eng Review)
- 最终审批前

恢复后可从任意阶段继续。

## 产出文件结构

```
项目根目录/
├── docs/
│   ├── plans/
│   │   ├── <slug>.md                        ← autoplan 产出
│   │   ├── <slug>-design-spec.md              ← design-review 产出
│   │   └── <slug>-test-plan.md               ← eng review 产出
│   ├── designs/
│   │   └── <slug>-brainstorm.md              ← brainstorm 产出
│   └── reviews/
│       ├── <branch>-code-review.md           ← code-review 产出
│       ├── <branch>-qa-report.md             ← qa 产出
│       ├── investigate-<timestamp>.md         ← investigate 产出
│       ├── <branch>-doc-update.md           ← document-release 产出
│       └── <slug>-execution-issues.md        ← 反馈回路 (worktree→autoplan)
├── .claude/
│   ├── android-checkpoint/
│   │   └── checkpoint-<timestamp>.json        ← 检查点数据
│   ├── android-worktree-runner/
│   │   └── tasks.json                      ← 执行状态 (唯一真相源)
│   └── skills/
│       ├── android-brainstorm/SKILL.md
│       ├── android-autoplan/SKILL.md
│       ├── android-design-review/SKILL.md
│       ├── android-worktree-runner/SKILL.md
│       ├── android-code-review/SKILL.md
│       ├── android-qa/SKILL.md
│       ├── android-investigate/SKILL.md
       ├── android-checkpoint/SKILL.md
│       └── android-document-release/SKILL.md
```

## 依赖要求

- **Claude Code** — 所有 skill 仅使用 Claude Code 原生工具 (Read、Write、Edit、Grep、Glob、Bash、Agent、Skill)
- **Android 项目** — 需要 build.gradle/settings.gradle、Kotlin/Java 源码
- **git** — worktree-runner 依赖 git worktree
- **Gradle** — 构建验证依赖 ./gradlew
- **Figma MCP** (可选) — design-review 需要配置 figma-developer-mcp

### Figma MCP 配置

在 `~/.claude/settings.json` 的 `mcpServers` 中添加:

```json
{
  "mcpServers": {
    "Framelink MCP for Figma": {
      "command": "cmd",
      "args": ["/c", "npx", "-y", "figma-developer-mcp", "--figma-api-key=YOUR-KEY", "--stdio"]
    }
  }
}
```

Figma API Token 获取: Figma → Settings → Security → Personal Access Tokens → Generate new token
