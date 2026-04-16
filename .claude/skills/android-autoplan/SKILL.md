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
# 运行锁: 防止多实例冲突
LOCKFILE=".claude/android-autoplan.lock"
if [ -f "$LOCKFILE" ]; then
  # 检查进程是否还在 (跨平台 PID 检查)
  OLD_PID=$(cat "$LOCKFILE" 2>/dev/null || echo "")
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "ERROR: android-autoplan 已在运行 (PID: $OLD_PID)。请稍后再试。"
    exit 1
  fi
fi
echo $$ > "$LOCKFILE"
trap 'rm -f "$LOCKFILE"' EXIT

SHARED_BIN=$(bash android-resolve-path 2>/dev/null || true)
[ -n "$SHARED_BIN" ] && export PATH="$SHARED_BIN/bin:$PATH"
# ... (rest of environment setup)
```

## Phase 3: Design Review (按需，含 MCP 自动检测)

### 步骤 1: 判断是否需要设计审查

AskUserQuestion: "此 plan 涉及 UI 变更，是否执行 Figma 设计审查?"
- A) 是，我有 Figma 设计稿
- B) 跳过，不需要设计审查

如果选 B:
```
在 plan 中标注 "未做设计审查"
继续 Phase 4
```

### 步骤 2: Figma MCP 状态检测 (仅当用户选择 A)

```bash
SHARED_BIN=$(bash android-resolve-path 2>/dev/null || true)
[ -n "$SHARED_BIN" ] && export PATH="$SHARED_BIN/bin:$PATH"

# M1 修复: 检查脚本是否存在
if [ ! -f "$SHARED_BIN/bin/figma-mcp-check" ]; then
  echo "ERROR: 核心组件缺失 ($SHARED_BIN/bin/figma-mcp-check)。请检查安装。"
  FIGMA_MCP_STATUS='{"configured":false, "error":"script_missing"}'
else
  FIGMA_MCP_STATUS=$(bash "$SHARED_BIN/bin/figma-mcp-check" --format json 2>/dev/null || echo '{"configured":false}')
fi
```

**根据检测结果自动处理：**

| 检测状态 | 行为 |
|---------|------|
| `configured: true` + `api_key_set: true` | MCP 已就绪，跳到步骤 3 |
| `configured: true` + `api_key_set: false` | 提示用户更新 API Key |
| `configured: false` | 提示用户安装配置 MCP |

**如果 MCP 未就绪：**

AskUserQuestion: "Figma MCP 未配置或配置不完整。请选择："
- A) 现在配置 MCP (提供安装指引)
- B) 跳过设计审查，继续 plan
- C) 取消

如果选 A: 提供配置指引，等待用户完成后继续
如果选 B: 标注 "未做设计审查 - MCP 未配置"，继续 Phase 4

### 步骤 3: 执行设计审查

AskUserQuestion: "请提供 Figma 设计稿 URL:"
- 输入 URL → 继续
- 留空 → 稍后手动运行 /android-design-review

如果用户提供了 URL:
```
使用 Skill 工具调用 android-design-review，传入 Figma URL
等待设计审查完成
读取产出的设计规格文档
将 <!-- DESIGN --> 注释块注入 plan 文件的相关任务
为缺失的状态添加补充任务
```

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
```

### 自动触发 Worktree Runner

Plan 文件生成后，立即询问用户:

AskUserQuestion: "Plan 已生成 (`docs/plans/<slug>.md`)。是否现在执行?"
- A) 是，立即执行 (调用 /android-worktree-runner)
- B) 稍后手动执行
- C) 取消

**如果选 A:**
```
1. 确认 git worktree 环境:
   - 检查 git worktree 是否可用
   - 检查 ./gradlew 是否可执行

2. 调用 /android-worktree-runner:
   - 传入 plan 文件路径
   - 自动导入 plan 中的任务列表
   - 开始逐任务执行

3. 提示用户:
   "Worktree Runner 已启动，将逐任务执行并自动验证。
   可随时中断或查看状态。"
```

**如果选 B:**
```
保存执行状态到 docs/plans/<slug>-status.json:
{
  "status": "ready",
  "plan_file": "docs/plans/<slug>.md",
  "created_at": "<timestamp>",
  "runner_invoked": false
}

提示: "可使用 /android-worktree-runner 手动执行"
```
