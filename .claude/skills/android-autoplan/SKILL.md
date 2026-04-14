---
name: android-autoplan
description: |
  Android Plan 拆分与审查。需求→结构化Plan→四层审查→产出。
  适用场景: 功能需求拆分、plan 审查。
---

# Android Autoplan

**调用:** `/android-autoplan <需求描述>` | `split` | `review <plan-file>`

## Phase 0: 项目环境

```bash
SHARED_BIN=$(bash android-resolve-path 2>/dev/null || true)
[ -n "$SHARED_BIN" ] && export PATH="$SHARED_BIN/bin:$PATH"
bash "$SHARED_BIN/bin/bin/android-learnings-bootstrap" 2>/dev/null || true
bash "$SHARED_BIN/bin/bin/android-scan-project" 2>/dev/null || true
ENV_JSON=$(bash "$SHARED_BIN/bin/bin/android-detect-env" 2>/dev/null || true)
```

读取 `.android-project-profile.json` (如有)。

### 上下文继承: 自动加载上游 brainstorm 产出

```bash
# 查找最近的 thinking 文档 (最近 24 小时,最多 3 个)
THINKING=$(find docs/thinking -name "*.md" -mmin -10080 2>/dev/null | sort -r | head -3)
```

**继承规则:**

| 场景 | 行为 |
|------|------|
| 用户需求与 thinking 文档主题匹配 (slug/关键词) | 自动加载,合并需求 |
| 用户需求与 thinking 文档不匹配 | 提示存在,询问是否参考 |
| 无 thinking 文档 | 从用户描述提取 |

**实现:** 读取 thinking 文档的标题/主题,与用户当前需求做关键词匹配。
匹配到 → 直接作为输入。**不匹配 → AskUserQuestion: "检测到最近的思考文档: `<文件名>`, 主题: `<主题>`, 是否参考?"**

## Phase 1: 需求拆分

```
输入: 功能需求描述
输出: 结构化 PRD + 任务树

PRD 格式:
## PRD
功能需求 (FR-N):
  FR-1: ...
非功能需求 (NFR-N):
  NFR-1: ...
验收标准 (AC-N):
  AC-1: [FR-1] ...
明确不做:
  - ...

任务拆分规则 (Android 分层):
  1. 基础设施 (Gradle/Manifest/依赖)
  2. 数据层 (Model/Entity/DAO)
  3. 业务层 (Repository/UseCase/ViewModel)
  4. 表现层 (UI/Composable/Fragment)
  5. 测试 (ViewModelTest/UITest)

每个任务标注:
  - TDD: required / skip (基础设施/测试/配置 skip, 其余 required)
  - 关联需求: FR-N / AC-N
  - 具体步骤 (可执行的 commit 级别)
  - 涉及文件路径
```

## Phase 2: CEO Review

```
检查:
  1. 前提挑战: 需求假设是否成立?
  2. PRD 审查: AC 是否可验证? FR 是否具体?
  3. 平台约束: 是否忽略 Android 特性 (生命周期/配置变更)?
  4. 范围砍伐: 最小可交付范围是什么?

输出: 通过 / 需要调整 + 问题列表
```

## Phase 3: Design Review (按需)

AskUserQuestion: "此 plan 涉及 UI 变更,是否执行设计审查?"
- 是 → 调用 android-design-review skill
- 否 → 跳过,继续 Phase 4

## Phase 4: Eng Review (subagent)

```
审查维度:
  1. 架构一致性: 分层方向正确? DI 正确?
  2. Gradle/Manifest: 依赖声明正确? 组件声明完整?
  3. 生命周期安全: ViewModel 不持 Context? Coroutine scope 正确?
  4. 测试策略: 测试分层 (unit/instrumented)? Mock 正确?
  5. 性能/失败模式: 主线程无 IO? 错误处理完整?
  6. PRD 技术可行性: AC 在 Android 上可实现?

输出: 紧凑结论 (≤200 字),写入 docs/reviews/
```

## Phase 3.5: 自省 (条件触发)

触发条件: Phase 4 发现 ≥2 个 WARNING 或 plan 含新架构决策。

```
自省:
  1. 假设审计: 我们假设了什么? 有证据吗?
  2. 决策回溯: 关键技术决策有其他选项吗?
  3. 盲点探测: 遗漏了什么? (a11y/深色模式/平板适配)

输出: 结论摘要,仅在有问题时标注
```

## Phase 5: DX Review (subagent)

```
审查:
  1. 命名规范: 类/方法/变量命名一致?
  2. 代码复用: 有已有组件可复用?
  3. PRD 清晰度: 需求描述是否明确?
  4. 开发工作流: 任务粒度合适?

输出: 紧凑结论 (≤150 字)
```

## 最终审批

```
决策系统:
  机械决策 (构建/依赖/格式) → 自动修复
  品味决策 (架构/命名/设计) → 记录,不阻塞
  用户挑战 (需求范围) → 从不自动决策,交由用户

审批摘要:
  机械决策: N 项已自动调整
  品味决策: N 项已记录
  用户挑战: N 项需确认 (如有)

选项:
  A) 接受并生成 Plan 文件
  B) 修改后重新审查
  C) 取消

生成文件:
  - docs/plans/<slug>.md
  - docs/plans/<slug>-status.json (write-once 审批凭证)

衔接: "Plan 已生成,可使用 /android-worktree-runner 执行"
```
