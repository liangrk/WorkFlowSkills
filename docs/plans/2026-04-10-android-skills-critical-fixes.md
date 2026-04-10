# Android Skills Critical Fixes

> 生成于 2026-04-10 | android-skills review

## 问题清单

### Critical #1: autoplan 读取 design-review 产出路径错误
- **文件:** android-autoplan/SKILL.md Phase 3 Step 2 (line 385)
- **问题:** 写 `docs/designs/`，design-review 实际输出到 `docs/plans/<slug>-design-spec.md`
- **修复:** 修正路径为 `docs/plans/<slug>-design-spec.md`

### Critical #2: 设计规格注入格式不统一
- **文件:** android-autoplan/SKILL.md Phase 3 Step 3 (lines 392-430)
- **问题:** autoplan 用 `<!-- DESIGN:COLORS ... DESIGN:COLORS -->` 子标签格式，design-review 实际产出 `<!-- DESIGN -->` 和 `<!-- DESIGN-NEW -->` 格式
- **修复:** autoplan Phase 3 改为直接读取 design-review 的产出文件 (`<slug>-design-spec.md`)，不再自己组装注入格式。把 design-spec 文件路径引用和组件映射表/资源清单直接附加到 plan 末尾

### Critical #3: Figma MCP 工具名缺少命名空间
- **文件:** android-design-review/SKILL.md Phase 0 Step 1 (line 48)
- **问题:** 直接写 `get_figma_data`，但 Claude Code 中 MCP 工具通过 `mcp__<server-name>__<tool-name>` 命名
- **根因:** 用户配置的 server name 是 "Framelink MCP for Figma"，运行时工具名会被转换为 `mcp__framelink-mcp-for-figma__get_figma_data` 之类。skill 硬编码的名称与运行时不匹配
- **修复:** 改为 "意图驱动" 调用方式: skill 不硬编码工具名，而是指示 Claude 通过 ListMcpResourcesTool 先发现 Figma server 是否可用及其实际工具名，再按发现的名称调用

### Critical #4: worktree-runner Android 项目检测 bash 运算符优先级 bug
- **文件:** android-worktree-runner/SKILL.md Phase 2 Step 5 (lines 370-373)
- **问题:** `||` 链中 `&&` 绑定更紧，导致 `build.gradle` 存在时表达式短路为 true，echo 不执行
- **修复:** 改为 `if/then/fi` 结构

### Critical #5: autoplan 上下文溢出
- **文件:** android-autoplan/SKILL.md Phases 4-5
- **问题:** Phase 4 有 8 个子维度审查，Phase 5 有 5 个维度，加上 Phase 3 的 Figma 数据，整体上下文消耗极大
- **修复:** Phase 4 (Eng Review) 和 Phase 5 (DX Review) 改为 subagent 模式:
  - 主 context 保存 plan 到文件后，每个审查维度派发独立 subagent
  - subagent 只接收 plan 文件路径 + 项目技术栈档案 + 该维度的审查要求
  - subagent 输出紧凑的审查结论 (每维度 <500 字)
  - 主 context 汇总所有 subagent 结论，产出最终审批摘要
  - 预估上下文节省: 70%+ (每个 subagent 独立上下文，不累积)
