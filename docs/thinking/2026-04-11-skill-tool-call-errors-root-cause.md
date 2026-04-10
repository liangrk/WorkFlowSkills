# 思考: Skills 工具调用报错根因分析

> 生成于 2026-04-11 | android-brainstorm skill
> 项目: WorkFlowSkills (kskills) | 分支: master
> 来源: 新建
> 状态: 审查通过 (7/10)

## 目标
- 一句话目标: 找出并分类所有导致 skill 执行时 bash 工具调用报错的根因
- 成功标准: 所有报错类别被识别，修复优先级明确，可执行
- 范围边界: 仅限 Windows Git Bash 环境下的兼容性问题
- 反边界: 不涉及 skill 逻辑错误、不涉及 Android 项目构建问题

## 外部信息
- 常规做法: 未搜索 (问题已通过代码扫描确认)
- 最新趋势: N/A
- 逆共识: N/A

## 前提
1. 运行环境是 Windows 11 + Git Bash → 状态: 确认 (xxd 验证了 CRLF)
2. SKILL.md 中的 bash 代码由 Claude 读取后通过 Bash 工具执行 → 状态: 确认
3. worktree 是相对路径失效的唯一场景 → 状态: 被挑战 (任何非根目录 CWD 都会触发)
4. CRLF 一定导致 shebang 失败 → 状态: 被挑战 (显式 `bash script.sh` 调用时 Git Bash 能容忍 `\r`)
5. grep -oP 在所有 Windows Git Bash 中都不可用 → 状态: 被挑战 (取决于 Git for Windows 版本)

## 问题分类

### 类别 1: CRLF 行尾 (CRITICAL)
- 覆盖: 9/9 bin 脚本 (100%)
- 根因: `#!/bin/bash\r\n` (0x0d 0x0a)
- 显式调用 (`bash script.sh`) 时 Git Bash 能容忍 `\r`，但 CRLF 在其他位置可能导致 `printf` 输出多出 `\r`、`$()` 命令替换尾部带 `\r`
- 修复: `.gitattributes` 添加 `*.sh text eol=lf` + `*.py text eol=lf`

### 类别 2: 相对路径在非根目录 CWD 失效 (HIGH)
- 覆盖: 11 skills, 44 处
- 根因: `bash .claude/skills/android-shared/bin/xxx` 在 worktree CWD 不是主仓库时失效
- 受影响 skill: android-coverage(6), android-tdd(5), android-qa(5), android-investigate(5), android-code-review(5), android-benchmark(5), android-refactor(4), android-learn(4), android-performance(3), android-init(1), android-autoplan(1)
- android-ship 不调用共享脚本，标记为"不适用"
- 修复: 引入 `$SHARED_BIN` 变量

### 类别 3: grep -oP Perl 正则不可用 (HIGH)
- 覆盖: 11 文件, 27 处 (SKILL.md 24 + bin 3)
- 根因: Windows Git Bash 的 grep 不支持 -P
- 受影响文件: android-worktree-runner(7), android-coverage(6), android-checkpoint(3), android-qa(2), android-status(2), android-tdd(2), android-benchmark(1), android-document-release(1), android-detect-env(1), android-scan-project(1), android-worktree-health(1)
- 修复: `grep -oP '\d+'` → `grep -oE '[0-9]+'`, `grep -oP 'missed="\K[^"]+'` → `sed -n 's/.*missed="\([^"]*\)".*/\1/p'`

### 类别 4: wc -l 前导空格 (MEDIUM)
- 覆盖: 10 skills, 23 处
- 根因: Git Bash `wc -l` 输出带前导空格
- 修复: `wc -l | tr -d ' '` 或 `$(( ... ))` 包裹

### 类别 5: echo -e 行为不一致 (MEDIUM)
- 覆盖: 1 脚本, 4 处 (android-worktree-health:106-109)
- 修复: `printf '%b\n' "$X"`

### 类别 6: here-string <<< (MEDIUM)
- 覆盖: 1 脚本, 1 处 (android-scan-project:379)
- 修复: `printf '%s\n' "$VAR" |`

### 类别 7: gh CLI 未检查可用性 (LOW)
- 覆盖: 1 skill (android-status)
- 修复: 添加条件保护

## 修复优先级

| # | 修复项 | 工时 | 影响 |
|---|--------|------|------|
| 1 | `.gitattributes` CRLF 修复 | 15min | 9 脚本 |
| 2 | 批量替换 44 处相对路径 → `$SHARED_BIN` | 2h | 11 skills |
| 3 | 替换 27 处 `grep -oP` | 3h | 11 文件 |
| 4 | `wc -l` 加 `tr -d ' '` | 1h | 23 处 |
| 5 | `echo -e` → `printf '%b'` + `<<<` 修复 | 15min | 2 脚本 |
| 6 | android-status gh CLI 保护 | 15min | 1 skill |

## 根本原因

1. **无跨平台 CI/lint**: 没有 pre-commit hook 阻止不兼容模式
2. **SKILL.md 是自然语言**: 无法被传统测试框架覆盖
3. **模式复制粘贴**: 初始 skill 的不兼容模式被复制到后续所有 skill

## 独立视角
- 盲点: CRLF 行尾问题被完全忽略 (100% 覆盖率但之前未发现)
- 反直觉洞察: `bash script.sh` 显式调用时 CRLF 不报错，`./script.sh` 才报错
- 48小时建议: 先 .gitattributes (15min) → 批量路径替换 (2h) → grep -oP 替换 (3h)
- 被忽略的风险: python 脚本 (android-scan-project.py) 的 CRLF 和编码问题

## 自我检验
- 审查轮次: 1
- 发现问题: 5 (已修复: 5)
- 质量分数: 7/10
- 待决事项:
  - CRLF 在 `bash script.sh` 显式调用模式下是否实际造成问题 (需要实机测试)
  - Git for Windows 哪些版本支持 grep -oP

## 下一步
- 按优先级表执行修复，从 `.gitattributes` 开始
- 修复完成后考虑添加 pre-commit hook 防止回归
