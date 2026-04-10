---
name: android-init
description: |
  Android 项目初始化扫描。深度扫描项目结构、依赖、架构、组件、约定，
  产出持久化项目档案 (.android-project-profile.json)。
  所有 skill 的共享上下文基础，design-review/autoplan/code-review 等均依赖此档案。
invocation: /android-init
args: [--force]
voice-triggers:
  - "初始化"
  - "扫描项目"
  - "项目档案"
  - "init"
---

# Android Init

## 概述

一次性深度项目扫描，产出持久化项目档案。所有下游 skill 的共享上下文基础。

**启动时声明:** "我正在使用 android-init skill。"

**零外部依赖:** 仅使用 Claude Code 原生工具和 bash 脚本。

## 调用方式

```bash
/android-init             # 扫描项目，生成档案
/android-init --force     # 强制重新扫描 (忽略已有档案)
```

**参数处理:**
- 无参数: 如果已有档案，显示档案年龄和摘要，询问是否重新扫描
- `--force`: 跳过确认，直接重新扫描

---

## Phase 0: 环境检测

### 步骤 1: 确认 Android 项目

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ ! -f "$PROJECT_ROOT/build.gradle" ] && [ ! -f "$PROJECT_ROOT/build.gradle.kts" ] && \
   [ ! -f "$PROJECT_ROOT/settings.gradle" ] && [ ! -f "$PROJECT_ROOT/settings.gradle.kts" ]; then
  echo "错误: 未检测到 Android 项目"
  exit 1
fi
```

### 步骤 2: 检测 Android SDK/NDK 环境

检测本地 Android 开发环境配置，结果写入项目档案的 `sdk` 字段。

```bash
# --- ANDROID_HOME / ANDROID_SDK_ROOT ---
if [ -n "$ANDROID_HOME" ]; then
  echo "ANDROID_HOME: $ANDROID_HOME"
elif [ -n "$ANDROID_SDK_ROOT" ]; then
  echo "ANDROID_HOME: $ANDROID_SDK_ROOT"
else
  # 常见默认路径探测
  for candidate in \
    "$HOME/AppData/Local/Android/Sdk" \
    "$HOME/Library/Android/sdk" \
    "$HOME/Android/Sdk" \
    "/usr/lib/android-sdk" \
    "/opt/android-sdk"; do
    if [ -d "$candidate" ]; then
      ANDROID_HOME="$candidate"
      echo "ANDROID_HOME: $ANDROID_HOME (自动探测)"
      break
    fi
  done
  [ -z "$ANDROID_HOME" ] && echo "ANDROID_HOME: NOT_FOUND"
fi

SDK_ROOT="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
```

```bash
# --- 已安装的 SDK Platform 版本 ---
if [ -n "$SDK_ROOT" ] && [ -d "$SDK_ROOT/platforms" ]; then
  echo "=== SDK Platforms ==="
  ls -1 "$SDK_ROOT/platforms" 2>/dev/null | sort -V | while read -r p; do
    echo "  $p"
  done
else
  echo "SDK Platforms: 无法读取 (ANDROID_HOME 未设置或目录不存在)"
fi
```

```bash
# --- 已安装的 Build Tools 版本 ---
if [ -n "$SDK_ROOT" ] && [ -d "$SDK_ROOT/build-tools" ]; then
  echo "=== Build Tools ==="
  ls -1 "$SDK_ROOT/build-tools" 2>/dev/null | sort -V
else
  echo "Build Tools: 无法读取"
fi
```

```bash
# --- 已安装的 NDK 版本 ---
if [ -n "$SDK_ROOT" ] && [ -d "$SDK_ROOT/ndk" ]; then
  echo "=== NDK Versions ==="
  ls -1 "$SDK_ROOT/ndk" 2>/dev/null | sort -V
else
  echo "NDK: 未安装或目录不存在"
fi
```

```bash
# --- CMake 版本 (NDK 构建常用) ---
if [ -n "$SDK_ROOT" ] && [ -d "$SDK_ROOT/cmake" ]; then
  echo "=== CMake Versions ==="
  ls -1 "$SDK_ROOT/cmake" 2>/dev/null | sort -V
else
  echo "CMake: 未安装"
fi
```

```bash
# --- 关键 SDK 组件检查 ---
echo "=== 关键组件检查 ==="
if [ -z "$SDK_ROOT" ]; then
  echo "  ANDROID_HOME 未设置，跳过组件检查"
else
COMPONENTS=(
  "platform-tools:adb"
  "cmdline-tools:latest"
  "emulator:模拟器"
  "ndk-bundle:NDK (legacy)"
)
for comp in "${COMPONENTS[@]}"; do
  name="${comp%%:*}"
  desc="${comp##*:}"
  dir="$SDK_ROOT/$name"
  if [ -d "$dir" ]; then
    echo "  ✅ $desc: 已安装"
  else
    echo "  ❌ $desc: 未安装"
  fi
done
fi
```

**检测结果输出示例:**
```
=== Android SDK/NDK 环境 ===
ANDROID_HOME: C:\Users\xxx\AppData\Local\Android\Sdk
SDK Platforms: android-33, android-34, android-35
Build Tools: 34.0.0, 35.0.0
NDK: 26.1.10909125, 27.0.12077973
CMake: 3.22.1, 3.30.5

关键组件:
  ✅ adb: 已安装
  ✅ cmdline-tools: 已安装
  ❌ 模拟器: 未安装
```

**写入档案:** 将以上检测结果以如下结构写入 `.android-project-profile.json` 的 `sdk` 字段:
```json
{
  "sdk": {
    "android_home": "/path/to/sdk",
    "platforms": ["android-33", "android-34", "android-35"],
    "build_tools": ["34.0.0", "35.0.0"],
    "ndk_versions": ["26.1.10909125", "27.0.12077973"],
    "cmake_versions": ["3.22.1", "3.30.5"],
    "components": {
      "platform-tools": true,
      "cmdline-tools": true,
      "emulator": false
    }
  }
}
```

**环境异常提示:**
- 如果 `ANDROID_HOME` 未设置且自动探测也失败: 提示用户配置 `ANDROID_HOME` 环境变量
- 如果项目 `build.gradle` 中指定的 `compileSdk` 对应的 platform 未安装: 提示通过 `sdkmanager` 安装
- 如果项目使用了 NDK (检测到 `externalNativeBuild` 配置) 但本地未安装 NDK: 提示安装对应版本

### 步骤 3: 检查已有档案

```bash
PROFILE_PATH="$PROJECT_ROOT/.android-project-profile.json"
if [ -f "$PROFILE_PATH" ] && [ "${1:-}" != "--force" ]; then
  # 显示档案年龄
  PROFILE_AGE_SECONDS=$(python3 -c "import os,time; print(int(time.time()-os.path.getmtime('$PROFILE_PATH')))" 2>/dev/null \
    || python -c "import os,time; print(int(time.time()-os.path.getmtime('$PROFILE_PATH')))" 2>/dev/null \
    || echo "0")
  PROFILE_AGE_DAYS=$(( PROFILE_AGE_SECONDS / 86400 ))

  echo "=== 已有项目档案 ==="
  echo "档案路径: $PROFILE_PATH"
  echo "档案年龄: ${PROFILE_AGE_DAYS} 天前生成"

  # 读取并显示档案摘要
  cat "$PROFILE_PATH"

  # 询问是否重新扫描
  # 使用 AskUserQuestion:
  # > 项目档案已存在 (${PROFILE_DAYS} 天前生成)。是否重新扫描?
  # > - A) 重新扫描
  # > - B) 使用已有档案
  # > - C) 取消
fi
```

如果用户选择重新扫描，或档案不存在，或使用了 `--force`，继续 Phase 1。

---

## Phase 1: 深度扫描

### 步骤 1: 运行扫描脚本

```bash
SHARED_BIN="$(git worktree list | head -1 | awk '{print $1}')/.claude/skills/android-shared/bin"
bash "$SHARED_BIN/android-scan-project" --force
```

脚本会自动:
1. 扫描所有 build.gradle / build.gradle.kts 文件
2. 解析 gradle/libs.versions.toml (version catalog)
3. 检测源码目录结构、组件、命名规范
4. 检测资源文件 (主题、图标、字体、drawable)
5. 检测构建配置 (flavor、build type、proguard)
6. 输出 JSON 到 stdout 和 `.android-project-profile.json`

### 步骤 2: 验证输出

确认脚本成功执行，输出文件已生成:

```bash
if [ -f "$PROJECT_ROOT/.android-project-profile.json" ]; then
  echo "档案生成成功: .android-project-profile.json"
  echo "文件大小: $(wc -c < "$PROJECT_ROOT/.android-project-profile.json") bytes"
else
  echo "错误: 档案生成失败"
  exit 1
fi
```

---

## Phase 2: 结果展示

读取 `.android-project-profile.json` 并以可读格式展示关键发现:

```bash
cat "$PROJECT_ROOT/.android-project-profile.json"
```

从 JSON 中提取关键信息，格式化展示:

```
[android-init] 项目档案已生成

项目: MyApp (com.example.myapp)
模块: app, core, feature-login, feature-home
Kotlin: 1.9.22 | AGP: 8.2.0 | Compose: true

架构: Clean Architecture (MVVM + StateFlow)
DI: Hilt | 导航: Compose Navigation
网络: Retrofit + OkHttp + kotlinx.serialization
数据库: Room | 存储: DataStore + EncryptedSharedPreferences

自定义组件: 5 composables, 2 custom views
测试框架: JUnit, MockK, Truth, Turbine, Compose UI Test
覆盖率要求: JaCoCo

设计系统: Material3 + 自定义主题
图片加载: Coil
图标集: material-icons-extended

档案路径: .android-project-profile.json
```

**展示规则:**
- 如果某项检测为 null/unknown，显示 "未检测到" 而非空白
- 组件列表超过 5 个时只显示数量，不逐个列出
- 聚焦于对下游 skill 有用的信息

---

## Phase 3: 下游集成检查

检查哪些 skill 会从此档案中受益，给出建议:

```
=== 下游 Skill 集成状态 ===

以下 skill 可直接读取项目档案，跳过重复扫描:
- android-design-review: 将使用 dependencies + components 信息进行 Figma -> 代码映射
- android-autoplan: 将使用 architecture + dependencies 信息生成更准确的 plan
- android-code-review: 将使用 conventions + architecture 信息进行审查
- android-tdd: 将使用 testing 信息配置测试环境
- android-detect-env: 将优先从档案读取，大幅加快检测速度

建议: 在项目结构发生重大变更时 (添加新模块、切换 DI 框架等) 重新运行 /android-init --force
```

---

## Phase 4: .gitignore 更新

检查 `.android-project-profile.json` 是否已在 `.gitignore` 中:

```bash
if [ -f "$PROJECT_ROOT/.gitignore" ]; then
  if ! grep -q ".android-project-profile.json" "$PROJECT_ROOT/.gitignore" 2>/dev/null; then
    echo "建议将 .android-project-profile.json 添加到 .gitignore"
    echo "此文件为项目特定的扫描结果，不应纳入版本控制"
    # 使用 AskUserQuestion:
    # > 是否将 .android-project-profile.json 添加到 .gitignore?
    # > - A) 自动添加
    # > - B) 跳过
  fi
else
  echo "未找到 .gitignore 文件"
fi
```

---

## 项目档案结构

`.android-project-profile.json` 包含以下部分:

| 部分 | 内容 | 下游使用者 |
|------|------|-----------|
| meta | 项目名、包名、模块、SDK 版本、构建系统 | 所有 skill |
| sdk | ANDROID_HOME、已安装 Platform/Build Tools/NDK/CMake、关键组件 | tdd, worktree-runner, benchmark, performance |
| dependencies | UI/网络/DI/数据库/测试等全部依赖 | design-review, autoplan, tdd |
| architecture | 架构模式、分层、状态管理、导航 | code-review, autoplan |
| components | 自定义 Composable/View、基类、Repository | design-review (核心) |
| conventions | 命名规范、包结构、代码模式 | code-review, autoplan |
| resources | 主题、图标集、字体、本地化 | design-review |
| build | flavor、build type、proguard、version catalog | autoplan |

---

## 与其他 Skill 的衔接

```
/android-init           → 生成 .android-project-profile.json
    │
    ├── android-design-review → 读取 dependencies + components (Figma 映射)
    ├── android-autoplan     → 读取 architecture + dependencies (准确拆分)
    ├── android-code-review  → 读取 conventions + architecture (审查基准)
    ├── android-tdd          → 读取 testing (测试环境配置)
    └── android-detect-env   → 优先读取档案 (快速检测)
```

**档案更新时机:**
- 新项目首次使用任何 skill 前
- 添加/删除模块后
- 切换主要依赖 (如 DI 框架、UI 框架) 后
- 重大架构重构后

---

## 异常情况处理

| 场景 | 处理方式 |
|------|----------|
| 不在 Android 项目中 | 报错: "需要 Android 项目" |
| ANDROID_HOME 未设置且探测失败 | 提示配置 ANDROID_HOME 环境变量，继续生成档案但 sdk 字段标记为 NOT_FOUND |
| python3/python 不可用 | 报错: "需要 python3 或 python 用于 JSON 输出" |
| 扫描脚本执行失败 | 显示错误信息，建议手动检查 build.gradle |
| 已有档案且无 --force | 显示档案年龄和摘要，询问是否重新扫描 |
| .gitignore 不存在 | 提示创建，但不自动创建 |
| 无任何依赖被检测到 | 输出空档案 (全部 null)，不报错 |

---

## 文件结构

```
项目根目录/
├── .android-project-profile.json          ← 本 skill 产出的项目档案 (gitignored)
├── .claude/
│   └── skills/
│       ├── android-init/
│       │   └── SKILL.md                    ← 本 skill
│       └── android-shared/
│           └── bin/
│               └── android-scan-project     ← 深度扫描脚本
└── ...
```
