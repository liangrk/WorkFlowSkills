---
name: android-performance
description: |
  Android 性能诊断: ANR/内存泄漏/卡顿/耗电。定性分析为主, 定量测量为辅。
---

# Android Performance

**调用:** `/android-performance <问题描述>`

## Phase 0: 问题收集

```bash
_R="$(git worktree list | head -1 | awk '{print $1}')"
SHARED_BIN="$_R/.claude/skills/android-shared/bin"
[ ! -d "$SHARED_BIN" ] && SHARED_BIN="$HOME/.claude/skills/android-shared/bin"
ENV_JSON=$(bash "$SHARED_BIN/android-detect-env" 2>/dev/null || true)
```

## Phase 1: 症状分类

| 症状类型 | 排查重点 |
|---------|---------|
| 启动慢 | Application.onCreate / 首屏渲染 / 初始化 |
| 滑动卡顿 | 过度重组 / 主线程阻塞 / 图片加载 |
| 内存增长 | 泄漏 / Bitmap / 缓存无限 |
| 耗电 | 后台服务 / WakeLock / 频繁定位 |
| 网络慢 | 请求数量 / 响应大小 / 重试逻辑 |

## Phase 2: 数据采集

```bash
# 内存
adb shell dumpsys meminfo <package> | head -30

# CPU
adb shell top -n 5 -d 1 | grep <package>

# 严格模式
adb logcat -d | grep StrictMode | tail -20

# ANR
adb shell ls /data/anr/ 2>/dev/null

# 帧率
adb shell dumpsys gfxinfo <package> | head -30
```

## Phase 3: 根因分析

```
表现层 → 数据层 → 逻辑层 → 平台层

1. 表现层: UI 重组次数 / 主线程阻塞
2. 数据层: 网络请求数量/大小 / 数据库查询
3. 逻辑层: 算法复杂度 / 不必要的计算
4. 平台层: 线程模型 / 生命周期 / 内存管理
```

## Phase 4: 优化建议

按影响程度排序:
- P0: 解决主要瓶颈 (预估提升 X%)
- P1: 次要优化
- P2: 最佳实践建议

产出: `docs/reviews/<branch>-performance-report.md`
