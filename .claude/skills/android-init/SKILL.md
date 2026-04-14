---
name: android-init
description: |
  一次性项目扫描。生成 .android-project-profile.json 供所有 skill 共享。
---

# Init

**调用:** `/android-init`

## Phase 1: 项目根目录

```bash
SHARED_BIN=$(bash android-resolve-path 2>/dev/null || true)
# SHARED_BIN resolved dynamically
# fallback handled
```

## Phase 2: 扫描

```bash
bash "$SHARED_BIN/bin/android-scan-project" 2>/dev/null || true
bash "$SHARED_BIN/bin/android-detect-env" 2>/dev/null || true
```

扫描内容:
- 构建系统 (Gradle/Bazel)
- 模块列表
- 技术栈 (UI 框架/异步/DI/网络/数据库/图片加载/导航)
- 架构模式 (MVVM/Clean/MVI)
- 测试框架
- 依赖信息

## Phase 3: 产出

```
.claude/init-status.json:
  - profile_path
  - scanned_at
  - project_type

.android-project-profile.json:
  - build_system
  - modules
  - tech_stack
  - architecture
  - test_framework
  - dependencies
```

## 后续

所有 skill 启动时读取 `.android-project-profile.json` 获取项目上下文。
项目结构发生重大变化时重新运行 `/android-init`。
