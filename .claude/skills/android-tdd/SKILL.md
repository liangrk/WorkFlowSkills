---
name: android-tdd
description: |
  Android TDD: RED→GREEN→REFACTOR + 覆盖率门禁 + 自动修复循环。
  适用场景: 新功能开发、bug 修复、重构。
---

# Android TDD

**调用:** `/android-tdd <功能描述>`

## RED 阶段

```
1. 定义契约:
   - 输入/输出类型
   - 边界条件
   - 异常场景

2. 编写失败测试:
   - 正常路径测试
   - 边界矩阵:
     | 维度 | 值 |
     |------|-----|
     | 空值 | null/""/emptyList |
     | 边界 | 0, 1, MAX_INT |
     | 网络 | 超时/断开/错误码 |
     | 线程 | Main/IO/Default |
     | 生命周期 | 配置变更/进程被杀 |

3. 验证测试失败 (RED):
   - 测试必须失败 (证明测试有效)
   - 失败原因符合预期
```

## GREEN 阶段

```
1. 最小实现:
   - 只写让测试通过的最少代码
   - 不预判,不过度设计

2. 验证测试通过:
   - 所有测试通过
   - 无编译错误
```

## REFACTOR 阶段

```
1. 安全重构:
   - 保持测试通过
   - 提取重复代码
   - 改善命名
   - 应用设计模式 (如需要)

2. 验证:
   - 所有测试仍通过
   - 代码质量提升
```

## 覆盖率门禁

| 指标 | 阈值 |
|------|------|
| 总体行覆盖率 | ≥80% |
| 关键路径 (ViewModel/Repository/UseCase) | ≥90% |
| 分支覆盖率 | ≥75% |

不达标→自动补测试(max 2轮)。

## 自动修复循环

```
测试失败 → 分析错误 → 修复 → 重跑 (max 3轮)
3轮后仍失败 → 报告问题,不阻塞
```

## 产出

```
- 测试文件: app/src/test/.../*Test.kt
- 实现文件: app/src/main/.../*
- 覆盖率报告: build/reports/jacoco/...
- TDD 报告: docs/reviews/<slug>-tdd-report.md
```

## Capture Learnings

```bash
bash "$SHARED_BIN/bin/android-learnings-log" '{"skill":"tdd","type":"technique","key":"KEY","insight":"INSIGHT","confidence":8,"source":"observed","files":[]}'
```

记录: 测试框架坑、有效测试模式。不记录: 一次性编译错误。
