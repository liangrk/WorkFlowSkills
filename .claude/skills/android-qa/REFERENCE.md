# Android QA Reference

> 本文件包含 SKILL.md 中不常需要的参考章节。仅在遇到对应场景时 Read 此文件。

---

## Phase 5: 修复循环

### 步骤 1: 问题分类

将 Bug 分为三类:

| 类别 | 条件 | 处理方式 |
|------|------|----------|
| 自动修复 | 缺少资源文件、lint 警告、未使用的导入、简单硬编码 | 直接修复 |
| 需确认 | 逻辑错误、架构问题、需要业务判断的修复 | 询问用户 |
| 覆盖率不达标 | 自动补测试 → 重新验证覆盖率 | 新增 |
| PRD 验收 ✗ | 验收标准未通过 (Phase 3) | 尝试补充实现，重新验证 |

### 步骤 2: 自动修复

**自动修复范围:**

1. **缺少资源文件** — 创建缺失的 string/dimen/color/drawable 资源
2. **未使用的导入** — 删除无用 import 语句
3. **Lint Warning (简单)** — 按 lint 建议修改
4. **硬编码字符串** — 抽取到 strings.xml
5. **硬编码尺寸** — 抽取到 dimens.xml
6. **覆盖率缺口** — 为低于阈值的文件生成补充测试，重新验证覆盖率
7. **缺少 contentDescription** — 为 ImageView/Icon 添加 contentDescription (Layer 4)
8. **缺少 LazyColumn key** — 为 LazyColumn/LazyRow items 添加 key 参数 (Layer 3)
9. **缺少 @Stable 注解** — 为 Composable 参数 data class 添加 @Stable (Layer 3)
10. **PRD 验收 ✗ 项** — 对 Phase 3 中判定为 ✗ FAIL 的 AC，尝试补充实现缺失的功能代码 (Phase 3)

```bash
# 示例: 创建缺失的字符串资源
# 在 values/strings.xml 中添加:
# <string name="missing_string">默认值</string>

# 示例: 删除未使用的导入
# 通过 Edit 工具精确删除对应行
```

**修复后验证:**
- 修复资源问题 → 重新运行 Layer 1 资源完整性检查
- 修复 lint 问题 → 重新运行 `./gradlew lintDebug`
- 修复编译问题 → 重新运行 `./gradlew assembleDebug`
- 修复 a11y 问题 (contentDescription 等) → 重新运行 Layer 4 无障碍检测
- 修复 Compose 性能问题 (LazyColumn key 等) → 重新运行 Layer 3C 静态检查
- 修复 PRD 验收 ✗ 项 → 重新运行 Phase 3 PRD 验收，验证对应的 AC 是否从 ✗ 升级为 ✓ 或 ⚠

### 步骤 3: 复杂问题处理

对于无法自动修复的问题:

```
以下问题需要确认是否修复:

🔴 BUG-001: 登录按钮点击后无响应
  位置: app/src/main/java/com/example/login/LoginViewModel.kt:67
  原因: coroutine scope 未正确绑定到 viewModelScope
  修复: 将 GlobalScope.launch 替换为 viewModelScope.launch

是否自动修复此问题?
- A) 是，修复所有可自动修复的问题
- B) 逐个确认每个修复
- C) 跳过修复，仅报告
```

### 步骤 4: 修复循环控制

```
修复循环: 第 1/3 轮

本轮修复: 4 个问题
  ✅ 自动修复: BUG-003 (缺少资源)
  ✅ 自动修复: TIP-001 (未使用导入)
  ✅ 用户确认: BUG-001 (逻辑错误)
  ✅ PRD 修复: AC-5 [FR-3] 记住我 — 补充功能代码

重新验证...
  构建: ✅
  Lint: ✅ (0 Warning)
  单元测试: ✅ (42/42)
  PRD 验收: 9/10 通过, 1 部分实现, 0 未实现

剩余问题: 1 (AC-3 部分实现，需人工确认)
修复循环完成。
```

**循环终止条件:**
- 所有阻塞和严重问题已修复 → 完成
- 达到 3 轮上限 → 提示用户手动处理剩余问题
- 用户选择停止 → 记录当前状态

### 步骤 5: 提交修复 (如有)

```bash
# 如果有自动修复的变更
git add -A
git commit -m "$(cat <<'EOF'
fix: QA 自动修复 - <问题摘要>

修复内容:
- <修复 1 描述>
- <修复 2 描述>

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

```bash
# 记录 QA 修复到 tasks.json (如果存在)
TASKS_JSON="$MAIN_WORKTREE/.claude/android-worktree-runner/tasks.json"
if [ -f "$TASKS_JSON" ]; then
  echo "QA 自动修复已记录到 tasks.json"
fi
```

记录修复 commit hash 列表。

---

## Capture Learnings

QA 完成后，将发现的典型 bug 模式记录到学习系统以供未来 session 参考。

**记录时机:**

1. **发现典型 bug 模式** — 如果 bug 不是简单的拼写/配置错误，而是具有普遍性的模式，使用 android-learnings-log 记录:
   ```bash
   _R="$(git worktree list | head -1 | awk '{print $1}')"
   SHARED_BIN="$_R/.claude/skills/android-shared/bin"
   [ ! -d "$SHARED_BIN" ] && SHARED_BIN="$HOME/.claude/skills/android-shared/bin"
   bash "$SHARED_BIN/android-learnings-log" '{"skill":"qa","type":"pitfall","key":"<bug模式简述>","insight":"<bug描述和修复方式>","confidence":8,"source":"observed","files":["<bug文件>"]}'
   ```

2. **发现项目特有的测试配置问题** — 如特定的 lint 规则误报、测试环境配置坑，记录为 technique:
   ```bash
   _R="$(git worktree list | head -1 | awk '{print $1}')"
   SHARED_BIN="$_R/.claude/skills/android-shared/bin"
   [ ! -d "$SHARED_BIN" ] && SHARED_BIN="$HOME/.claude/skills/android-shared/bin"
   bash "$SHARED_BIN/android-learnings-log" '{"skill":"qa","type":"technique","key":"<配置名>","insight":"<配置坑描述>","confidence":7,"source":"observed","files":["<配置文件>"]}'
   ```

**不记录:**
- 一次性的拼写错误
- 已被自动修复的简单 lint warning
- 与历史记录完全重复的发现

---

## 异常情况处理

| 场景 | 处理方式 |
|------|----------|
| 不在 git 仓库中 | 报错: "android-qa 需要 git 仓库" |
| 不是 Android 项目 | 报错: "未检测到 Android 项目" |
| Gradle 不可用 | 报错: "gradlew 未找到或不可执行" |
| 当前分支无变更 (与基准相同) | 提示: "当前分支无变更，无需 QA" |
| 构建失败 | 记录为 🔴 阻塞，不执行后续测试 |
| 单元测试超时 (>10 分钟) | 终止测试，标记为超时 |
| adb 设备未授权 | 提示: "请在设备上授权 USB 调试"，跳过 Layer 5 |
| APK 安装失败 (签名冲突) | 先 `adb uninstall <package>` 再重试 |
| docs/reviews 目录不存在 | 自动创建 |
| 与 android-investigate 集成 | 发现复杂 bug 时，建议调用 android-investigate 进行根因分析 |
| TDD 被跳过的业务任务 | 覆盖率阈值提升至 90%，Layer 2.3 强制执行，记录警告 |
| 无 JaCoCo 配置 | 提示配置 JaCoCo 以启用覆盖率门禁，使用测试通过率替代 |
| 性能基准超时 (--profile 超过 10 分钟) | 终止构建性能测试，标记为超时 |
| 无 res/layout 目录 (纯 Compose 项目) | Layer 4A 静态分析跳过 XML 检查，仅执行 4B Compose 检查 |
| 未找到 PRD | Phase 0 输出提示，Phase 3 PRD 验收自动跳过，其余 QA 正常执行 |

---

## 与其他 Skill 的衔接

### 上游: android-worktree-runner

当 android-worktree-runner 完成 Plan 的所有任务后 (Phase 3)，
可自动调用 `/android-qa` 对完成的分支进行 QA。

调用方式:
```
Plan 所有任务已完成。是否执行 QA 测试?
- A) 是，运行 /android-qa
- B) 跳过 QA
```

### 下游: android-investigate

当 QA 发现复杂的 bug (非简单修复) 时，建议调用 android-investigate 进行根因分析。

调用方式:
```
发现复杂问题 BUG-001，建议使用 /android-investigate 进行根因分析。
是否启动调查?
- A) 是，启动 /android-investigate
- B) 跳过，仅记录在报告中
```

**如果发现可修复的功能 bug (非复杂根因):**
1. 输出 `docs/reviews/<branch>-qa-fix-tasks.md`，格式与 autoplan plan 兼容:
   ```markdown
   ### Task 1: 修复 &lt;bug 标题&gt;
   **层级:** &lt;对应层级&gt;
   **TDD:** required
   **步骤:**
   - [ ] &lt;修复步骤&gt;
   ```
2. 建议用户运行: `/android-worktree-runner import docs/reviews/<branch>-qa-fix-tasks.md`

### 与其他 skill 的关系

| Skill | 关系 | 说明 |
|-------|------|------|
| android-worktree-runner | 上游 | Plan 执行完毕后调用本 skill |
| android-investigate | 下游 | 发现复杂 bug 时调用进行根因分析 |
| android-design-review | 参考 | QA 时对照 design-spec.md 验证设计还原度 |
| android-autoplan | 参考 | QA 时对照 plan 文件验证功能完整性 |
| android-tdd | 上游 | QA 读取 TDD 报告和 tasks.json TDD 状态，避免重复测试，复用覆盖率数据 |

---

## 文件结构

```
项目根目录/
├── docs/
│   └── reviews/
│       ├── <branch>-qa-report.md          ← 本 skill 产出的 bug 报告
│       └── screenshots/                   ← 设备测试截图 (如有)
│           └── qa_screenshot_*.png
├── .claude/
│   └── skills/
│       └── android-qa/
│           └── SKILL.md                   ← 本 skill
└── ...
```
