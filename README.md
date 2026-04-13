# WorkFlow Skills

一套 Claude Code skill 工具链，覆盖从开发到日常工作的完整生命周期。

## Skill 集合

| Skill | 类型 | 说明 |
|-------|------|------|
| `weekly-report` | 日常工作 | 自动生成周报，整合多仓库 git log 和任务状态 |
| `dump-android-ui` | UI 分析 | 一键 dump Android App UI 视图树，生成元素 ID/文本/布局分析和交互式可视化 |
| `android-*` | Android 开发 | Android 完整开发流程 (见下方详细说明) |

---

## weekly-report

自动生成结构化工作周报，整合多个仓库的 git 提交和任务状态。

### 快速开始

```bash
# 1. 复制配置模板
cp weekly-report/config-template.yaml my-weekly.yaml

# 2. 编辑配置 - 填写仓库路径和任务列表
# (用编辑器修改 my-weekly.yaml)

# 3. 生成周报
python weekly-report/scripts/generate-report.py --config my-weekly.yaml

# 4. (可选) 导出到文件
python weekly-report/scripts/generate-report.py --config my-weekly.yaml > weekly-$(date +%Y%m%d).md
```

### 配置示例

```yaml
repositories:
  - name: "主项目"
    path: "./main-project"
  - name: "后端服务"
    path: "../backend-service"

tasks:
  - name: "用户登录功能"
    status: "completed"       # completed / in_progress / planned
    description: "完成 OAuth2.0 登录"
    category: "feature"
  
  - name: "性能优化"
    status: "in_progress"
    progress: 60
    description: "数据库查询优化"
    category: "optimization"
  
  - name: "API 文档"
    status: "planned"
    description: "补充接口文档"
    category: "doc"
```

### 输出效果

```
==================================================
                     工作周报
报告周期: 2026-04-13 ~ 2026-04-19
==================================================

【本周完成工作】
--------------------------------------------------
用户登录功能
   - 修复用户登录成功后 Token 刷新逻辑
   - 完成用户登录模块开发，支持手机号和 OAuth 登录

【进行中任务】
--------------------------------------------------
性能优化 (60%)
   - 优化数据库查询性能

【下周计划】
--------------------------------------------------
API 文档
   补充接口文档

【进度总览】
--------------------------------------------------
总计: 3 | 完成: 1 | 进行中: 1 | 计划中: 1
总体进度: 53.3%
==================================================
```

### 文件结构

```
weekly-report/
├── SKILL.md                 # Skill 定义
├── weekly-config.yaml       # 默认配置模板
├── config-template.yaml     # 带注释的配置模板 (推荐)
├── README.md                # 详细文档
└── scripts/
    └── generate-report.py   # 周报生成脚本
```

### 依赖

- Python 3.7+
- PyYAML (`pip install pyyaml`)

---

## dump-android-ui

一键 dump Android App 的 UI 视图树，自动生成元素 ID、文本内容、布局结构分析和交互式可视化报告。

### 快速开始

```bash
# 自动检测当前前台 App 并 dump
python .claude/skills/dump-android-ui/scripts/dump_android_ui.py

# 指定 App 包名
python .claude/skills/dump-android-ui/scripts/dump_android_ui.py --package com.example.app

# 指定输出目录
python .claude/skills/dump-android-ui/scripts/dump_android_ui.py --package com.example.app --output ./dumps
```

### 输出文件

```
android-dumps/YYYYMMDD-HHMMSS/
├── ui_hierarchy.xml      # 原始 UI 层次 XML (仅目标 App)
├── screenshot.png        # 屏幕截图
├── analysis.json         # 结构化分析 (元素 ID、文本、类型分布)
├── tree_view.html        # 交互式可视化树 (可搜索/展开/复制 ID)
└── report.txt            # 文本摘要报告
```

### 功能特性

- **自动检测** — ADB、设备连接、前台 App 包名
- **智能过滤** — 只保留目标 App 相关节点，去除系统 UI 和其他 App 噪声
- **完整覆盖** — 所有控件都保留，无论是否有 resource-id
- **ID 简化** — 输出中去掉包名前缀 (如 `id/btn_ok` 而非 `com.app:id/btn_ok`)
- **交互式可视化** — HTML 树形视图，支持搜索、展开/折叠、点击复制 ID
- **Fallback** — uiautomator 失败自动切换 dumpsys activity

### 使用场景

| 场景 | 说明 |
|------|------|
| UI 测试自动化 | 获取元素 ID 编写 Espresso/UIAutomator 测试 |
| UI 审查 | 检查布局层次和资源 ID 命名规范 |
| 竞品分析 | 分析其他 App 的 UI 结构和交互设计 |
| 无障碍检查 | 检测 content-desc 缺失情况 |

### 依赖

- Python 3.7+
- ADB (Android Debug Bridge)
- 已连接的 Android 设备或模拟器

---

# Android Development Skills

一套专为 Android 开发设计的 Claude Code skill 工具链。覆盖从需求定义到代码交付的完整生命周期。

## 工作流全景

```
┌──────────────────────────────────────────────────────────────────────┐
│                  android-init (项目档案，一次性)                       │
│          深度扫描 → .android-project-profile.json                     │
└──────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      android-status (全局监控)                        │
│          git / worktree / checkpoint / PR / build 一览                │
└──────────────────────────────────────────────────────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐
│ brainstorm │  │  checkpoint  │  │   status    │  │android-learn │
│  需求定义   │  │  保存/恢复   │  │  (监控所有)  │  │  学习记录    │
└──────┬──────┘  └──────┬───────┘  └─────────────┘  └──────────────┘
       │                │
       ▼                ▼
┌─────────────┐  ┌──────────────┐    ┌───────────────────┐    ┌──────────────────┐
│  autoplan  │──▶│design-review│───▶│ worktree-runner   │───▶│ android-tdd      │
│  拆分+审查  │  │Figma(按需)  │    │   任务执行         │    │ 测试先行(每任务)  │
└─────────────┘  └──────────────┘    └──────┬────────────┘    └──────────────────┘
                                              │
                         ┌────────────────────┼────────────────────┐
                         ▼                    ▼                    ▼
                  ┌──────────────┐    ┌─────────────┐    ┌──────────────┐
                  │  code-review │    │     qa     │    │ investigate  │
                  │  代码审查    │    │  功能测试   │    │  调试排查    │
                  └──────┬───────┘    └─────┬──────┘    └──────────────┘
                         │                  │
              ┌──────────┼──────────┐       │
              ▼          ▼          ▼       ▼
       ┌──────────┐ ┌────────┐ ┌────────┐ ┌──────────────┐
       │ coverage │ │benchmark│ │performance│ │  refactor  │
       │ 覆盖率   │ │性能测试│ │ 性能分析  │ │  重构       │
       └──────────┘ └────────┘ └────────┘ └──────────────┘
                         │                  │
                         ▼                  ▼
                  ┌──────────────┐    ┌──────────────┐
                  │  反馈回路    │    │ doc-release  │
                  │ runner→plan  │    │  文档更新     │
                  └──────────────┘    └──────┬───────┘
                                            │
                                            ▼
                                     ┌──────────────────┐
                                     │  android-ship    │
                                     │  范围检测+交付    │
                                     └──────────────────┘
```

## Skill 列表

| Skill | 阶段 | 说明 | 调用方式 |
|-------|------|------|---------|
| `android-init` | 初始化 | 一次性深度扫描，生成持久化项目档案 (.android-project-profile.json) | `/android-init` |
| `android-status` | 监控 | 全局状态仪表盘: git/worktree/checkpoint/PR/build 一览 | `/android-status` |
| `android-brainstorm` | 需求定义 | 头脑风暴、需求分析、方案探索 | `/android-brainstorm` |
| `android-checkpoint` | 持续化 | 保存/恢复 autoplan 会话状态，防止 /clear 丢失上下文 | `/android-checkpoint save` / `restore` |
| `android-autoplan` | 规划 | 需求拆分、四层审查、自省，产出可执行 plan | `/android-autoplan <需求>` |
| `android-tdd` | 测试先行驱动 | TDD 流程 (RED/GREEN/REFACTOR)、覆盖率门禁 (80%/90%)、自动修复循环 (3+1) | `/android-tdd <功能描述>` |
| `android-design-review` | 审查 | Figma 设计稿审查，产出设计规格 (按需) | `/android-design-review <figma-url>` |
| `android-worktree-runner` | 执行 | 基于 git worktree 隔离执行 plan 任务，每任务自动验证 | `/android-worktree-runner` |
| `android-code-review` | 审查 | 代码质量审查 (架构、命名、生命周期、线程安全等) | `/android-code-review` |
| `android-qa` | 验证 | 功能级 QA (静态分析、构建测试、设备测试) | `/android-qa` |
| `android-coverage` | 覆盖率 | 独立覆盖率闭环: 基线测量→差距分析→自动补测试→验证达标 | `/android-coverage` |
| `android-benchmark` | 性能测试 | Worktree 隔离性能分析: 冷启动/帧率/内存，默认报告模式，`--auto` 全自动闭环 | `/android-benchmark` |
| `android-performance` | 性能分析 | ANR/内存泄漏/卡顿/耗电等运行时性能问题排查 | `/android-performance <问题描述>` |
| `android-investigate` | 调试 | 系统化 bug 排查 (四层分析: 表现→数据→逻辑→平台) | `/android-investigate <问题描述>` |
| `android-refactor` | 重构 | PRD 锚定重构，三档 scope 自动检测 (micro/medium/macro) | `/android-refactor <目标描述>` |
| `android-ship` | 交付 | 范围漂移检测、验证、提交、推送、创建 PR | `/android-ship` |
| `android-learn` | 学习记录 | 跨 session 知识积累、搜索、清理 | `/android-learn [search|add|prune|stats]` |
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

# 覆盖率闭环 (全自动补测试)
/android-coverage

# 只出覆盖率报告，不动代码
/android-coverage report

# 性能 benchmark (报告+建议，不动代码)
/android-benchmark

# 性能 benchmark (全自动闭环: 优化+编译验收)
/android-benchmark --auto

# 只测冷启动
/android-benchmark cold-start --target 300ms

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

输出: 思考文档 (`docs/thinking/<date>-<slug>.md`)，包含:
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

七维度审查 (架构、命名、生命周期、线程、Android特有、可测试性、安全):
1. 架构一致性 (模块依赖方向、分层、DI)
2. 命名与代码风格 (项目规范、Kotlin 惯例)
3. 生命周期与内存安全 (Context 泄漏、Listener、Coroutine scope)
4. 线程与并发 (主线程 IO、UI 线程安全、Compose 重组)
5. Android 特有 (资源泄漏、Bitmap、数据库事务、权限)
6. 可测试性 (依赖可 mock、硬编码检测)
7. 安全 (敏感数据、权限、网络安全、ProGuard)

产出: `docs/reviews/<branch>-code-review.md`

### 6. QA 测试 (android-qa)

```
/android-qa
/android-qa smoke
/android-qa regression
```

六层覆盖 (静态分析、构建测试、性能基准、无障碍、设备测试、PRD验收):
1. **静态分析** (无需设备): 代码模式、资源完整性、Manifest、ProGuard
2. **构建+单元测试** (无需设备): assembleDebug、lintDebug、testDebugUnitTest
3. **性能基准** (无需设备): 关键性能指标回归检测
4. **无障碍检查** (无需设备): a11y 合规性扫描
5. **设备测试** (需要 adb): 安装 APK、运行 UI 验证
6. **PRD 验收** (逻辑层): 对照验收标准逐条验证需求覆盖度

包含修复循环: 发现 bug 后自动修复 → 重新验证，最多 3 轮。

产出: `docs/reviews/<branch>-qa-report.md`

### 7. 覆盖率 (android-coverage)

独立的覆盖率闭环 skill，不依赖 TDD 或 QA 流程。

```bash
/android-coverage                  # 全自动闭环 (基线→分析→补测试→验证)
/android-coverage report           # 只出报告，不动代码
/android-coverage feature:login    # 指定模块运行
```

| Phase | 做什么 |
|-------|--------|
| Phase 0 | 环境检测: JaCoCo 配置、测试框架、模块结构 (按需自动引导配置) |
| Phase 1 | 基线测量: 运行测试 + JaCoCo 报告，输出三维度仪表盘 (行/分支/方法) |
| Phase 2 | 差距分析: 按优先级排序 (P0 关键路径→P1 工具类→P2 UI) |
| Phase 3 | 自动补写测试: 最多 10 轮收敛循环，前 3 轮每轮 5 个类，逐步精细化 |
| Phase 4 | 最终验证: 全量回归测试 + assembleDebug 编译验收 |
| Phase 5 | 结果汇报: before→after 对比 + 新增测试清单 + 未达标项 |

收敛策略: 连续 2 轮提升 < 0.5% 自动停止。所有关键路径 >= 90%、总体 >= 80% 时提前终止。

**适用场景:** 夜间无人值守自动补测试、覆盖率审计、TDD 后补充覆盖率。

产出: `docs/reviews/<branch>-coverage-report.md`

### 8. 性能 Benchmark (android-benchmark)

Worktree 隔离的性能分析 skill。默认报告模式不动代码，`--auto` 全自动闭环。

```bash
/android-benchmark                  # 报告+建议 (不动代码)
/android-benchmark --auto           # 全自动闭环 (修复+编译验收)
/android-benchmark cold-start       # 只测冷启动
/android-benchmark jank             # 只测帧率/Jank
/android-benchmark memory           # 只测内存
/android-benchmark cold-start --target 300ms  # 自定义目标
```

| Phase | 做什么 |
|-------|--------|
| Phase 0 | Worktree 创建 + 交互选 commit + Gradle 环境预热 + 基础设施检测 |
| Phase 1 | 基线测量: 三级降级 (Macrobenchmark→adb→静态分析)，每个维度 3 次取中位数 |
| Phase 2 | 性能诊断: 定位瓶颈并按影响/难度排序 |
| Phase 3 | 自动优化 (--auto 专属): 最多 8 轮，每轮 Top-1 瓶颈 + 回归检测 |
| Phase 4 | 编译验收: Debug+Release 编译 + 单元测试 (报告模式跳过重复测量) |
| Phase 5 | 结果汇报: 性能对比表 + 优化清单 + worktree 清理选项 |

**默认目标:** 冷启动 <500ms / Jank <5% / 内存 ≤基线 110%

**三级降级策略:**
- **Tier 1 (Macrobenchmark):** 项目已配置 benchmark module + 设备已连接
- **Tier 2 (adb):** 有设备，通过 `am start-activity -W`、`dumpsys gfxinfo`、`dumpsys meminfo` 测量
- **Tier 3 (静态分析):** 无设备，基于代码审查定性评估

产出: `docs/reviews/<branch>-benchmark-report.md`

### 9. 调试排查 (android-investigate)

```
/android-investigate 登录页面 crash 时出现 NullPointerException
```

四层排查:
1. **表现层**: stack trace 分析、异常模式
2. **数据层**: API 响应、DTO 映射、数据库、缓存
3. **逻辑层**: 状态转换、条件分支、边界条件
4. **平台层**: 生命周期、权限、内存、线程、兼容性

产出: `docs/reviews/<branch>-investigate-report.md`

### 10. 检查点 (android-checkpoint)

```
/android-checkpoint save    # 保存当前会话状态
/android-checkpoint restore  # 恢复上次保存的状态
/android-checkpoint status    # 查看所有检查点
```

保存内容: 技术栈档案、架构推断、plan 信息、审查结论、决策记录、待处理事项。
解决 `/clear` 或会话重启后上下文丢失的问题。

### 11. 文档更新 (android-document-release)

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
├── .android-project-profile.json              ← android-init 产出 (gitignored)
├── docs/
│   ├── plans/
│   │   ├── <slug>.md                        ← autoplan 产出
│   │   ├── <slug>-design-spec.md              ← design-review 产出
│   │   └── <slug>-test-plan.md               ← eng review 产出
│   ├── thinking/
│   │   └── <date>-<slug>.md                 ← brainstorm 产出
│   └── reviews/
│       ├── <branch>-code-review.md           ← code-review 产出
│       ├── <branch>-qa-report.md             ← qa 产出
│       ├── <branch>-coverage-report.md       ← coverage 产出
│       ├── <branch>-benchmark-report.md      ← benchmark 产出
│       ├── <branch>-investigate-report.md     ← investigate 产出
│       ├── <branch>-doc-update.md           ← document-release 产出
│       └── <slug>-execution-issues.md        ← 反馈回路 (worktree→autoplan)
├── .claude/
│   ├── android-checkpoint/
│   │   └── checkpoint-<timestamp>.json        ← 检查点数据
│   ├── android-worktree-runner/
│   │   └── tasks.json                      ← 执行状态 (唯一真相源)
│   ├── worktrees/
│   │   └── bench-<timestamp>/              ← android-benchmark 创建的 worktree
│   └── skills/
│       ├── android-init/SKILL.md
│       ├── android-brainstorm/SKILL.md
│       ├── android-status/SKILL.md
│       ├── android-autoplan/SKILL.md
│       ├── android-tdd/SKILL.md
│       ├── android-design-review/SKILL.md
│       ├── android-worktree-runner/SKILL.md
│       ├── android-code-review/SKILL.md
│       ├── android-qa/SKILL.md
│       ├── android-coverage/SKILL.md
│       ├── android-benchmark/SKILL.md
│       ├── android-performance/SKILL.md
│       ├── android-refactor/SKILL.md
│       ├── android-investigate/SKILL.md
│       ├── android-ship/SKILL.md
│       ├── android-learn/SKILL.md
│       ├── android-checkpoint/SKILL.md
│       ├── android-document-release/SKILL.md
│       └── android-shared/bin/
│           └── android-scan-project          ← init 深度扫描脚本
```

### 12. 学习记录 (android-learn)

```
/android-learn              # 查看所有学习记录
/android-learn search xxx   # 搜索学习记录
/android-learn add          # 手动添加学习记录
/android-learn prune        # 清理过期记录
/android-learn stats        # 统计信息
```

跨 session 知识积累。自动记录 code-review/investigate/qa/tdd 发现的模式，
下次 session 自动加载。支持跨项目搜索。

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

## 安装与更新

### 全局安装（推荐）

在任意项目的 Claude Code 中粘贴以下 prompt：

```
将 https://github.com/liangrk/WorkFlowSkills 仓库中的 Android 开发 skills 安装到我的全局 Claude Code 环境（~/.claude/skills/）。步骤：1) 克隆仓库到临时目录 2) 将 .claude/skills/ 下所有 android-* 目录和 android-shared 目录复制到 ~/.claude/skills/ 3) 清理临时目录 4) 列出已安装的 skills 确认成功。
```

或使用一行命令：

```bash
tmpdir=$(mktemp -d) && git clone --depth 1 https://github.com/liangrk/WorkFlowSkills.git "$tmpdir/WorkFlowSkills" && mkdir -p ~/.claude/skills && cp -r "$tmpdir/WorkFlowSkills/.claude/skills/"* ~/.claude/skills/ && rm -rf "$tmpdir" && echo "Installed:" && ls ~/.claude/skills/android-*
```

安装后重启 Claude Code，在任意 Android 项目中运行 `/android-init` 生成项目档案。

### 更新

在 Claude Code 中粘贴：

```
更新我的全局 Android skills（~/.claude/skills/ 下的 android-* 和 android-shared）。从 https://github.com/liangrk/WorkFlowSkills 拉取最新版本覆盖安装，完成后列出已安装的 skills 确认。
```

或使用一行命令：

```bash
tmpdir=$(mktemp -d) && git clone --depth 1 https://github.com/liangrk/WorkFlowSkills.git "$tmpdir/WorkFlowSkills" && cp -r "$tmpdir/WorkFlowSkills/.claude/skills/"* ~/.claude/skills/ && rm -rf "$tmpdir" && echo "Updated:" && ls ~/.claude/skills/android-*
```

> **注意：** 更新只覆盖 skill 定义文件和共享脚本，不会影响项目级运行时数据（tasks.json、checkpoint 等）。
