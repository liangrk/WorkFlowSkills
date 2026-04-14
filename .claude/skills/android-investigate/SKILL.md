---
name: android-investigate
description: |
  Android 系统化调试: 四层排查 (表现→数据→逻辑→平台)。
  适用场景: bug 排查、crash 分析、性能问题。
---

# Android Investigate

**调用:** `/android-investigate <问题描述>`

## Phase 0: 问题收集

```bash
SHARED_BIN=$(bash android-resolve-path 2>/dev/null || true)
# SHARED_BIN resolved dynamically
# fallback handled

# 上下文继承: 读取上游 QA 报告中的 bug 列表
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
QA_REPORT=$(find docs/reviews -name "${BRANCH}-qa-report.md" -mmin -10080 2>/dev/null | head -1)
if [ -z "$QA_REPORT" ]; then
  QA_REPORT=$(find docs/reviews -name "*-qa-report.md" -mmin -10080 2>/dev/null | sort -r | head -1)
fi
if [ -n "$QA_REPORT" ] && [ -f "$QA_REPORT" ]; then
  echo "=== 上游 QA 报告中的 bug ==="
  grep -E "^#### BUG-|^\[BLOCKER\]|^\[WARNING\]" "$QA_REPORT" | head -20
fi
```

```
输入: 问题描述 (自然语言) 或 QA 报告中的 BUG-N
输出: 结构化的问题定义
  - 症状: 发生了什么?
  - 预期: 应该发生什么?
  - 频率: 每次/偶尔/一次?
  - 环境: 设备/Android版本/构建变体
```

## Phase 1: 复现确认

```
1. 收集 stack trace (如有崩溃)
2. 检查相关日志: adb logcat / Gradle 输出
3. 确定触发条件
4. 最小复现步骤

产出: 可复现的测试用例或复现步骤
```

## Phase 2: 数据层分析

```
1. API 响应: 返回数据正确?
2. DTO 映射: 字段映射正确?
3. 数据库: 查询结果正确? 事务正确?
4. 缓存: 命中/失效符合预期?
```

## Phase 3: 逻辑层分析

```
1. 状态转换: 状态机正确?
2. 条件分支: 所有分支覆盖?
3. 边界条件: null/空/边界值处理?
4. 并发: 竞态条件? 死锁?
```

## Phase 4: 平台层分析

```
1. 生命周期: onCreate/onStart/onResume 顺序?
2. 配置变更: 旋转/多窗口/深色模式?
3. 权限: 运行时权限请求?
4. 内存: 泄漏? OOM?
5. 线程: 主线程阻塞? 线程安全?
6. 兼容性: API 版本差异?
```

## 产出

```
docs/reviews/<branch>-investigate-report.md:
  - 问题描述
  - 复现步骤
  - 四层分析过程
  - 根因
  - 修复方案
  - 预防措施
```

## Capture Learnings

```bash
bash "$SHARED_BIN/bin/android-learnings-log" '{"skill":"investigate","type":"pitfall","key":"KEY","insight":"INSIGHT","confidence":8,"source":"observed","files":[]}'
```
