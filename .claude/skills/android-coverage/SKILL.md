---
name: android-coverage
description: |
  Android 覆盖率闭环: 基线→差距→补测试→验证。
  适用场景: 覆盖率审计、自动补测试。
---

# Android Coverage

**调用:** `/android-coverage` | `report` | `feature:<name>`

## Phase 0: 环境检测

```bash
ENV_JSON=$(bash "$SHARED_BIN/bin/android-detect-env" 2>/dev/null || true)
# 检查 JaCoCo 配置、测试框架
```

## Phase 1: 基线测量

```bash
./gradlew testDebugUnitTest 2>&1
# 查找 JaCoCo 报告
JACOCO=$(find . -path "*/reports/jacoco/*/*.xml" | head -1)
# 输出: 行覆盖率/分支覆盖率/方法覆盖率
```

## Phase 2: 差距分析

```
识别低于阈值的文件:
  P0: 关键路径 (ViewModel/Repository/UseCase) <90%
  P1: 工具类 <80%
  P2: UI 层 <70%
```

## Phase 3: 自动补测试

```
按优先级补写测试 (max 10轮):
  前3轮: 每轮5个类
  后续: 精细化补充
收敛: 连续2轮提升<0.5% → 停止
```

## Phase 4: 最终验证

```bash
./gradlew testDebugUnitTest 2>&1
./gradlew assembleDebug 2>&1
```

## Phase 5: 结果

```
docs/reviews/<branch>-coverage-report.md:
  before→after 对比
  新增测试清单
  未达标项
```
