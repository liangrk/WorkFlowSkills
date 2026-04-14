---
name: android-build
description: |
  Android 构建验证: Debug/Release/APK/AAB, 版本管理, 签名验证, Flavor 矩阵。
  适用场景: 发布前验证、版本管理、构建优化。
---

# Android Build

**调用:** `/android-build` | `release` | `flavor` | `apk` | `aab`

## Phase 0: 环境检测

```bash
_R="$(git worktree list | head -1 | awk '{print $1}')"
SHARED_BIN="$_R/.claude/skills/android-shared/bin"
[ ! -d "$SHARED_BIN" ] && SHARED_BIN="$HOME/.claude/skills/android-shared/bin"
ENV_JSON=$(bash "$SHARED_BIN/android-detect-env" 2>/dev/null || true)
```

## Phase 1: 构建系统检测

```bash
# 模块列表
cat settings.gradle settings.gradle.kts 2>/dev/null | grep include

# 构建变体
grep -r "buildTypes\|productFlavors" app/ --include="*.gradle*" 2>/dev/null

# 版本信息
grep -E "versionCode|versionName" app/build.gradle* 2>/dev/null

# 签名配置
grep -E "signingConfig\|storeFile" app/build.gradle* 2>/dev/null
```

## Phase 2: Debug 构建验证

```bash
./gradlew assembleDebug --no-daemon 2>&1
./gradlew lintDebug --no-daemon 2>&1
./gradlew testDebugUnitTest --no-daemon 2>&1
```

## Phase 3: Release 构建验证

```bash
./gradlew assembleRelease --no-daemon 2>&1
./gradlew bundleRelease --no-daemon 2>&1  # AAB
```

### R8/ProGuard 检查

```bash
# R8 报告
find app/build -name "mapping.txt" 2>/dev/null | head -1
find app/build -name "configuration.txt" 2>/dev/null | head -1

# 常见 R8 问题
grep -i "missing class\|unresolved reference" app/build/outputs/mapping/*/mapping.txt 2>/dev/null | head -20
```

## Phase 4: 产物验证

```bash
# APK
APK=$(find app/build/outputs/apk -name "*.apk" 2>/dev/null | head -1)
if [ -n "$APK" ]; then
  ls -lh "$APK"
  # 签名验证
  apksigner verify --print-certs "$APK" 2>/dev/null || echo "apksigner 不可用"
  # 权限检查
  aapt dump badging "$APK" 2>/dev/null | grep "uses-permission"
fi

# AAB
AAB=$(find app/build/outputs/bundle -name "*.aab" 2>/dev/null | head -1)
if [ -n "$AAB" ]; then
  ls -lh "$AAB"
  # Bundle 工具检查
  bundletool validate --bundle="$AAB" 2>/dev/null || echo "bundletool 不可用"
fi
```

### 产物检查项

| 检查 | 标准 |
|------|------|
| APK 大小 | Debug <50MB, Release <30MB |
| AAB 大小 | <20MB |
| 签名 | release 签名 (非 debug) |
| 版本 | versionCode 递增 |
| 权限 | 无意外新增权限 |

## Phase 5: Flavor 矩阵 (如有)

```bash
# 列出所有 flavor
./gradlew tasks --all 2>/dev/null | grep assemble | grep -v test

# 按 flavor 构建 (并行)
./gradlew assembleFlavor1Debug assembleFlavor2Release --no-daemon 2>&1
```

## 产出

```
docs/reviews/<branch>-build-report.md:
  - 构建结果 (Debug/Release/AAB)
  - APK/AAB 大小
  - 签名验证结果
  - 版本信息
  - R8/ProGuard 报告
  - Flavor 矩阵结果
```
