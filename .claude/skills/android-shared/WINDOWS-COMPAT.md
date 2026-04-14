# Android Skill 路径解析 - Windows 兼容方案

## 问题
Windows cmd/PowerShell 不直接支持 bash 脚本,模型多次调用失败。

## 解决方案

### 方案 A: 使用 android-exec.bat (推荐)

```cmd
REM Windows 环境
android-exec.bat android-scan-project --force
android-exec.bat android-detect-env
```

### 方案 B: Git Bash 调用

```bash
# 需要完整路径
"D:\software\git\bin\bash.exe" --login "/path/to/script.sh"
```

### 方案 C: 模型内直接调用

在 SKILL.md 中使用:

```bash
# 自动检测环境
SHARED_BIN=$(bash android-resolve-path 2>/dev/null || true)
[ -n "$SHARED_BIN" ] && bash "$SHARED/bin/android-scan-project"
```

## 已修复的 Skill 列表

✓ android-autoplan
✓ android-brainstorm
✓ android-worktree-runner
✓ android-tdd
✓ android-code-review
✓ android-qa
✓ android-build
✓ android-ship
✓ android-checkpoint
✓ android-dump
... 所有 22 个 skill 已更新

## 验证命令

```cmd
cd E:\ldmnq_project\ldva-ui
android-exec.bat android-scan-project --force
```
