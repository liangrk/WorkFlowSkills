---
name: android-brainstorm
description: |
  轻量级头脑风暴。结构化提问帮助用户想清楚目标、边界和方案。
  产出思考文档,可后续转为可执行 plan。
---

# Brainstorm

**调用:** `/android-brainstorm` | `<主题>` | `resume <file>`

## Phase 0: 环境

```bash
SHARED_BIN=$(bash android-resolve-path 2>/dev/null || true)
# SHARED_BIN resolved dynamically
# fallback handled
bash "$SHARED_BIN/bin/android-learnings-bootstrap" 2>/dev/null || true
ENV_JSON=$(bash "$SHARED_BIN/bin/android-detect-env" 2>/dev/null || true)
ls docs/thinking/ 2>/dev/null
```

## Phase 1: 需求明确

AskUserQuestion (逐一提问, 不复用):

| 问题 | 目的 |
|------|------|
| 你要解决什么具体问题? | 确认痛点 |
| 目标用户是谁? | 用户画像 |
| 有什么约束条件? (时间/技术/资源) | 边界 |
| 成功的标准是什么? | 验收指标 |
| 有其他方案考虑过吗? | 替代方案 |

## Phase 2: 方案发散

基于 Phase 1 的回答, 提供 2-3 个不同方向的方案:

```
方案 A: 最小可行 (快速验证)
  - 核心功能
  - 预期工时
  - 风险点

方案 B: 完整方案 (长期方案)
  - 功能完整
  - 架构设计
  - 扩展性

方案 C: 创新方案 (不同思路)
  - 非传统实现
  - 优势/劣势
```

AskUserQuestion: 选择方向 → 深入

## Phase 3: 对抗性审查 (subagent)

派发 subagent 做对抗性审查:
- 这个方案最可能失败的原因是什么?
- 有什么被忽略的边界情况?
- 有没有更简单的实现方式?

## Phase 4: 产出思考文档

```
docs/thinking/<date>-<slug>.md:
  - 问题和目标
  - 用户画像
  - 约束条件
  - 成功标准
  - 方案对比
  - 推荐方案
  - 开放问题
```

AskUserQuestion: 是否保存到文件? A) 保存 B) 仅对话 C) 转为 plan

## Phase 5: 下一步建议

```
有明确需求 → 推荐 /android-autoplan
需更多发散 → 推荐继续 brainstorm
有竞品参考 → 推荐 /android-dump 分析
```

## Capture Learnings

```bash
bash "$SHARED_BIN/bin/android-learnings-log" '{"skill":"brainstorm","type":"pattern","key":"KEY","insight":"INSIGHT","confidence":8,"source":"observed","files":[]}'
```
