---
name: android-design-review
description: |
  Android 专属的 Figma 设计审查 skill。通过 Figma MCP (figma-developer-mcp) 读取设计稿，
  审查设计还原度、项目框架一致性、状态覆盖、平台适配。
  产出设计规格文档，可注入 android-autoplan 的 plan 任务。
  独立 skill，可单独使用或被 android-autoplan Phase 3 按需调用。
  适用场景: UI 实现前的设计审查、设计系统对齐、资源导出规划。
voice-triggers:
  - "设计审查"
  - "Figma 审查"
  - "设计稿对齐"
  - "设计还原"
---

# Android Design Review

## 概述

Figma 设计稿 → Android 实现规格。不写代码，只产出审查文档。

**启动时声明:** "我正在使用 android-design-review skill。"

**零外部依赖:** 不依赖 gstack 二进制、Codex、browse、design。仅使用 Claude Code
原生工具和 Figma MCP 工具。

## 调用方式

```bash
/android-design-review <figma-url>    # 直接传入 Figma 链接
/android-design-review                  # 交互式，询问 Figma URL
/android-design-review review          # 仅审查，不导出资源
```

**参数处理:**
- 带参数: 直接使用传入的 Figma URL
- 无参数: AskUserQuestion 询问 Figma 设计稿链接
- `review`: 跳过资源导出步骤

---

## Phase 0: Figma MCP 检查

### 步骤 1: 发现 Figma MCP 工具

**不硬编码工具名。** MCP 工具在运行时通过 `mcp__<server-name>__<tool-name>` 命名，
server name 取决于用户在 settings.json 中的配置。不同配置下工具名不同。

**发现流程:**

1. 检查当前可用工具列表中是否存在名称包含 `figma` 的 MCP 工具
   (即以 `mcp__` 开头且名称中包含 `figma` 的工具)
2. 如果找到:
   - 记录完整的工具名 (如 `mcp__framelink-mcp-for-figma__get_figma_data`)
   - 从工具名中提取 server-name 部分 (第一个和第二个 `__` 之间的部分)
   - 确认存在两个工具: `get_figma_data` 和 `download_figma_images`
3. 如果未找到: 进入错误处理

**注意:** `ListMcpResourcesTool` 列出的是 MCP **resources**，不是 **tools**。
Figma MCP 提供的是 tools，因此必须通过可用工具列表发现，而非 ListMcpResourcesTool。

**预期工具 (名称由 MCP server 提供):**
- `get_figma_data` — 读取 Figma 设计数据
- `download_figma_images` — 下载图片/icon

**三种结果处理:**

1. **未找到 Figma MCP 工具** (可用工具列表中无包含 `figma` 的 MCP 工具):
   - 中断执行，不继续
   - 输出安装指引:

   > Figma MCP 未就绪。请先安装 figma-mcp:
   >
   > 1. 获取 Figma API Token:
   >    Figma → 账号菜单 → Settings → Security → Personal Access Tokens → Generate new token
   >
   > 2. 在 Claude Code 中配置 MCP server:
   >    打开 ~/.claude/settings.json，在 mcpServers 中添加:
   >    ```json
   >    "Framelink MCP for Figma": {
   >      "command": "cmd",
   >      "args": ["/c", "npx", "-y", "figma-developer-mcp", "--figma-api-key=YOUR-KEY", "--stdio"]
   >    }
   >    ```
   >
   > 3. 配置完成后重启 Claude Code，再运行 /android-design-review

2. **Auth 失败** (工具返回 403 或 auth 错误):
   - 中断执行
   - 提示: "Figma API Token 无效或已过期。请更新 token 后重试。"

3. **发现成功**: 记录 `<server-name>` 和 `<tool-name>`，继续 Phase 0 步骤 2。

**后续所有 Figma 工具调用均使用 `mcp__<发现的server-name>__<tool-name>` 格式。**

> 以下文档中为简洁起见，工具名称仍写作 `get_figma_data` 和
> `download_figma_images`。实际调用时**必须**使用步骤 1 中发现的完整
> `mcp__<server-name>__<tool-name>` 格式。

### 步骤 2: 获取 Figma URL

- 带参数调用 → 直接使用传入的 URL
- 无参数 → AskUserQuestion 询问 Figma 设计稿链接

### 步骤 3: 解析 Figma URL

从 URL 中提取 `file-key` 和可选的 `node-id`:

```
https://www.figma.com/design/{file-key}/{title}?node-id={node-id}
https://www.figma.com/file/{file-key}/{title}?node-id={node-id}
```

**解析规则:**
- `file-key`: URL 路径中第三个段落 (纯字母数字)
- `node-id`: URL 参数 `node-id` 的值 (用 `-` 分隔，工具内部替换为 `:`)
- 如果没有 `node-id`: 读取文件后列出所有页面 (Page)，AskUserQuestion 选择

### 步骤 4: 确定 slug

slug 用于产出文件命名。按以下优先级确定:
1. 如果被 autoplan 调用: slug 从 autoplan 传入 (plan 的 slug)
2. 如果用户指定了 plan 文件路径: 从文件名提取 (如 `2026-04-10-auth` → `2026-04-10-auth`)
3. 其他: 从 Figma 文件标题生成 (转小写，非字母数字替换为 `-`，截取前 50 字符)

### 步骤 5: 检测项目环境

扫描项目，确定 UI 框架、组件库、命名规范。

```bash
# 确定项目根目录
PROJECT_ROOT=$(git rev-parse --show-toplevel)

# 列出所有模块
cat "$PROJECT_ROOT/settings.gradle" "$PROJECT_ROOT/settings.gradle.kts" 2>/dev/null | grep "include"

# UI 框架检测 (扫描所有模块)
grep -rl "@Composable" "$PROJECT_ROOT" --include="*.kt" 2>/dev/null | head -5
find "$PROJECT_ROOT" -path "*/res/layout/*.xml" 2>/dev/null | head -5

# UI 库检测 (扫描所有 build.gradle)
grep -rl "com.google.android.material" "$PROJECT_ROOT" --include="*.gradle*" 2>/dev/null | head -5
grep -rl "io.github.aakira" "$PROJECT_ROOT" --include="*.gradle*" 2>/dev/null | head -5
grep -rl "coil" "$PROJECT_ROOT" --include="*.gradle*" 2>/dev/null | head -5
grep -rl "lottie" "$PROJECT_ROOT" --include="*.gradle*" 2>/dev/null | head -5
```

产出项目 UI 档案 (贯穿后续所有审查阶段):
```
=== 项目 UI 档案 ===
UI 框架:     Compose / XML / 混用
模块列表:    app, feature:login, core:ui, core:common
Material:    版本 X / 未使用
圆角方案:    Material ShapeableImageView / RoundedCorner / 原生 clip
背景方案:    Material CardView / 自定义 AppCard / ConstraintLayout bg
图片加载:    Coil / Glide
动画库:      Lottie / MotionLayout / 原生
```

---

## Phase 1: 设计稿数据读取

### 步骤 1: 读取设计数据

调用 Figma MCP 工具 `get_figma_data`:

```
参数:
- fileKey: <从 URL 提取的 file-key>
- nodeId: <从 URL 提取的 node-id，可选>
  格式: "1234:5678" (Figma URL 中的 "-" 会被工具自动替换为 ":")
  多个节点: "1234:5678;90:12;34:56" (用 ";" 分隔)
```

如果用户指定了 `review` 模式: 只读取数据，跳过后续的资源导出步骤。

### 步骤 2: 解析设计数据

**MCP 只有 2 个工具 (get_figma_data + download_figma_images)。**
**Design token 提取、组件分析、无障碍检查由 skill 自行完成。**

从 `get_figma_data` 的输出中解析:

1. **颜色** — 遍历节点，提取 `fill` / `stroke` 中的颜色值
2. **字体** — 遍历节点，提取 `style` 中的 fontFamily / fontSize / fontWeight
3. **间距** — 遍历节点，提取 autoLayout 中的 padding / gap
4. **圆角** — 遍历节点，提取 cornerRadius
5. **阴影** — 遍历节点，提取 effects 中的 drop-shadow
6. **图片引用** — 遍历节点，提取 imageRef / gifRef
7. **组件定义** — 识别 component / variant 节点
8. **页面结构** — 整理 Frame / Page 层级关系

**解析策略:**
- 节点树已由 MCP 简化，只需遍历 YAML/JSON 输出
- 重点关注叶子节点 (实际的 UI 元素)
- 收集所有唯一颜色值、字体组合、间距值

### 步骤 3: 导出资源 (非 review 模式)

调用 `download_figma_images` 导出图片/icon:

```
参数:
- fileKey: <file-key>
- nodes: [
    { nodeId: "1234:5678", fileName: "ic_back_24dp.svg" },
    { nodeId: "9012:3456", imageRef: "abc123", fileName: "img_banner.webp" },
    { nodeId: "7890:1234", gifRef: "def456", fileName: "anim_loading.gif" }
  ]
- pngScale: 3          ← 默认 3 倍图 (用户要求)
- localPath: "app/src/main/res"
```

**导出规则:**

| 资源类型 | 格式 | 密度 | 命名 |
|----------|------|------|------|
| Icon (单色/简单) | SVG | — | ic_xxx_24dp.svg |
| Icon (复杂路径/渐变) | PNG | 3x (xxhdpi) | ic_xxx.png → drawable-xxhdpi/ |
| 插画/图片 | PNG | 3x (xxhdpi) | img_xxx.png → drawable-xxhdpi/ |
| 动图 | GIF | — | anim_xxx.gif |

**SVG 导出失败处理:**
- MCP 支持直接导出 SVG (通过 fileName 以 .svg 结尾)
- 如果 SVG 导出的内容为空或格式异常 → 标记为失败
- **绝对不自己生成 SVG 代码**
- 列出导出失败的资源清单:
  > 以下 icon 的 SVG 导出失败，请手动从 Figma 导出:
  > - ic_search_24dp.svg → 目标: drawable/ic_search_24dp.svg
  - Figma 节点: https://www.figma.com/design/xxx?node-id=456

**文件保存位置:** 遵循 Phase 0 检测到的模块结构。
图标放 core 模块 (跨功能复用)，页面相关图片放 feature 模块。

---

## Phase 2: 项目上下文分析

### 步骤 1: 检测已有组件 (多模块扫描)

```bash
# Compose 自定义组件
grep -rl "@Composable" "$PROJECT_ROOT" --include="*.kt" | grep -v test | head -20

# XML 自定义 View
grep -rl "extends.*View\|extends.*ViewGroup" "$PROJECT_ROOT" --include="*.kt" --include="*.java" | grep -v test | head -20
```

### 步骤 2: 检测命名规范

```bash
# 扫描所有模块的资源命名
find "$PROJECT_ROOT" -path "*/res/drawable*" -name "*.xml" 2>/dev/null | xargs -I{} basename {} 2>/dev/null | head -30
find "$PROJECT_ROOT" -path "*/res/drawable*" \( -name "*.webp" -o -name "*.png" \) 2>/dev/null | xargs -I{} basename {} 2>/dev/null | head -20
```

推断命名模式:
```
=== 资源命名规范 (推断) ===
Icon:     ic_xxx_24dp / ic_xxx
Image:    img_xxx / bg_xxx
Layout:   item_xxx / fragment_xxx / activity_xxx
Color:    colorPrimary / brand_xxx / xxx_500
Dimens:   spacing_xxx / margin_xxx / dp_xxx
```

### 步骤 3: 检测主题系统

```bash
grep -rl "MaterialTheme" "$PROJECT_ROOT" --include="*.kt" | head -5
grep -rl "Theme.Material3" "$PROJECT_ROOT" --include="*.xml" | head -5
find "$PROJECT_ROOT" -path "*/values-night*" 2>/dev/null | head -5
```

### 步骤 4: 检测已有状态组件

```bash
grep -ril "skeleton\|shimmer\|loading" "$PROJECT_ROOT" --include="*.kt" | grep -v test | head -5
grep -ril "empty.*view\|no.*data\|empty.*state" "$PROJECT_ROOT" --include="*.kt" --include="*.xml" | grep -v test | head -5
grep -ril "error.*view\|error.*state\|retry" "$PROJECT_ROOT" --include="*.kt" --include="*.xml" | grep -v test | head -5
```

---

## Phase 3: 设计审查 (六维度)

### 维度 1: 设计还原度规划

将 Figma 设计数据映射为 Android 实现规格。

**映射规则:**

| Figma 属性 | Android 值 | Compose 实现 | XML 实现 | 规则 |
|------------|-----------|-------------|----------|------|
| 位置/尺寸 (px) | dp | Modifier.size() / Modifier.padding() | layout_width/height | 1:1 |
| 颜色 (hex) | 颜色 token | MaterialTheme.colorScheme.xxx | @color/xxx | 先查已有 token |
| 字体大小 (px) | sp (正文) / dp (固定) | MaterialTheme.typography.xxx | TextAppearance.xxx | badge 等用 dp |
| 字重 | FontWeight | FontWeight.Bold | android:textStyle | 100-900 映射 |
| 间距 (px) | dp | Modifier.padding() | padding/margin | 检查 8dp 网格 |
| 圆角 (px) | dp | 项目圆角方案 | 项目圆角方案 | 不直接用 clip |
| 阴影 | elevation (dp) | Modifier.shadow() | app:elevation | 用项目已有方案 |

**Compose vs XML 关键差异:**

| 场景 | Compose | XML |
|------|---------|-----|
| 圆角 | Modifier.clip(RoundedCornerShape()) | app:cornerRadius |
| 背景 | Modifier.background() + Brush | android:background |
| 间距 | Modifier.padding() / Arrangement | padding / margin 属性 |
| 状态 | mutableStateOf + remember | ViewModel + LiveData/StateFlow |
| 列表 | LazyColumn | RecyclerView |

### 维度 2: 项目框架一致性

**组件映射决策逻辑:**

对 Figma 中的每个 UI 元素:
1. 匹配 Phase 2 检测到的项目已有组件列表
   → 匹配到已有组件 → 使用它 (标记 "✅ 已有")
2. 未匹配 → 检查 Figma 组件的 componentProperty / description
   → Button → AppButton / Material Button
   → Card → AppCard / Material Card
   → TextField → AppTextField / Material TextField
3. 仍无法匹配 → AskUserQuestion 让用户指定映射
4. 全新组件 → 标记 "❌ 需新建"

**匹配策略:**
- **名称匹配:** Figma 组件名与项目文件名相似度
- **语义匹配:** Figma 组件 description 与项目组件功能
- **视觉匹配:** 外观特征 (圆角、阴影、图标位)

**样式一致性规则:**
- 项目用自定义圆角库 → 新代码也用该库
- 项目用 Coil → 新代码也用 Coil
- 项目用 Lottie → 新动画也用 Lottie
- 项目用 Compose → 新 UI 用 Compose

### 维度 3: 状态覆盖审查

**必查状态:**

| 状态 | 说明 | 审查方式 |
|------|------|----------|
| Success | 数据就绪 | 对照 Figma 设计稿验证 |
| Loading | 首次加载/刷新 | 检查项目 Skeleton 组件 |
| Empty | 无数据 | 检查项目 EmptyView |
| Error | 网络/服务器/权限 | 检查项目 ErrorView |
| Partial | 分页加载中 | Figma 很少画，标记需补充 |

**审查逻辑:**
1. 遍历 Figma 设计稿的所有 Frame/Page
2. 检查 Frame 名称是否包含状态关键词 (loading, empty, error, skeleton)
3. 未找到 → 检查项目已有状态组件 (Phase 2 步骤 4)
4. 项目已有 → 标记 "沿用项目已有组件"
5. 都没有 → 标记 "❌ 需要补充设计或沿用通用方案"

### 维度 4: 平台适配

**1. 深色模式:**
- Figma 中是否有 "Dark" / "Dark mode" 页面/组件变体?
- 颜色是否通过 design tokens 定义 (可映射到 Material3 主题)?
- 项目是否已有 `values-night/` 目录?
- 产出: 深色模式适配方案

**2. 多屏幕/响应式:**
- 设计稿基准宽度: 记录 (375px / 390px / 其他)
- 布局是否使用 Auto Layout / ConstraintLayout (不是绝对定位)?
- 项目是否需要支持横屏/平板/折叠屏?

**3. 无障碍 (skill 自行计算):**
- Touch target < 48dp → 标记 (从节点尺寸计算)
- 对比度 < 4.5:1 → 标记 (从颜色和字体数据计算)
- ContentDescription → 标记 (从语义推断)

### 维度 5: 资源导出计划

**导出规则:**

| 资源类型 | 格式 | 密度 | 命名 | 导出方式 |
|----------|------|------|------|----------|
| Icon (单色/简单) | SVG | — | ic_xxx_24dp.svg | download_figma_images |
| Icon (复杂路径/渐变) | PNG | 3x | ic_xxx.png → drawable-xxhdpi/ | download_figma_images (pngScale=3) |
| 插画/图片 | PNG | 3x | img_xxx.png → drawable-xxhdpi/ | download_figma_images (pngScale=3) |
| 动图 | GIF | — | anim_xxx.gif | download_figma_images |

**命名规范:**
- 遵循 Phase 2 检测到的项目命名模式
- 不使用 Figma 原始命名 (除非项目约定如此)

**资源保存位置:**
- 跨功能复用的 icon → `core:ui/src/main/res/`
- 页面特定资源 → 对应 `feature:xxx/src/main/res/`
- 项目通用资源 → `app/src/main/res/`

### 维度 6: 动效规格 (如果有)

**如果 Figma 原型包含交互/动画:**

| Figma 属性 | Compose | XML |
|------------|---------|-----|
| Smart Animate (进入) | AnimatedVisibility | MotionLayout |
| Smart Animate (退出) | AnimatedVisibility | MotionLayout |
| 页面转场 | SharedTransition + Nav 动画 | Navigation animation |
| 按钮微交互 | Modifier.composed { ... } | ViewPropertyAnimator |
| Loading 动画 | CircularProgressIndicator / Lottie | ProgressBar / Lottie |
| duration | 直接使用 (ms) | 直接使用 (ms) |
| easing (ease-in) | FastOutSlowInEasing | @animator/fast_out_slow_in |
| easing (ease-out) | LinearOutSlowInEasing | @animator/linear_out_slow_in |
| easing (ease-in-out) | FastOutLinearInEasing | @animator/fast_out_linear_in |
| easing (自定义) | CubicBezierEasing(x1,y1,x2,y2) | PathInterpolator |

**如果 Figma 没有动效:** 标记 "使用项目默认动画"。

---

## Phase 4: 产出

### 产出物 1: 设计规格文档

写入 `docs/plans/<slug>-design-spec.md`:

```markdown
# 设计规格: <功能标题>

> 生成于 <日期> | android-design-review
> Figma: <链接>
> 项目框架: Compose + Material3
> 项目模块: app, feature:login, core:ui

## 设计还原规格

### 页面: <页面名>
- 基准宽度: 390dp (Figma 390px)
- 框架: Compose

### 组件: <组件名>
| 属性 | Figma 值 | Android 值 | Compose 实现 | 备注 |
|------|----------|-----------|-------------|------|
| 宽度 | 358px | 358dp | Modifier.fillMaxWidth().padding(horizontal = 16.dp) | |
| 高度 | 48px | 48dp | Modifier.height(48.dp) | |
| 背景色 | #6200EE | @color/primary | MaterialTheme.colorScheme.primary | 已有 token |
| 圆角 | 24px | 24dp | AppCard(cornerRadius = 24.dp) | 用项目组件 |
| 字号 | 16px | 16sp | MaterialTheme.typography.bodyLarge | |
```

### 产出物 2: 组件映射表

```markdown
## 组件映射

| Figma 组件 | Android 实现 | 项目组件 | 模块 | 备注 |
|------------|-------------|---------|------|------|
| Button / Primary | AppButton | ✅ 已有 | :feature:components | |
| Card / Container | AppCard | ✅ 已有 | :feature:components | |
| Input Field | AppTextField | ✅ 已有 | :feature:components | |
| Bottom Sheet | ModalBottomSheet | — | Material3 | 原生 |
| Status Badge | — | ❌ 需新建 | :feature:login | |
```

### 产出物 3: 资源清单

```markdown
## 资源导出清单

### Icon (SVG)
| 名称 | Figma 节点 | 目标路径 | 状态 |
|------|-----------|----------|------|
| ic_back_24dp | Frame 123 | core:ui/.../drawable/ic_back_24dp.svg | ✅ 已导出 |
| ic_search_24dp | Frame 456 | core:ui/.../drawable/ic_search_24dp.svg | ❌ SVG 导出失败 |

### 图片 (PNG 3x)
| 名称 | Figma 节点 | 目标路径 | 状态 |
|------|-----------|----------|------|
| img_banner | Frame 111 | feature:login/.../drawable-xxhdpi/img_banner.png | ✅ 已导出 |
```

### 产出物 4: 状态覆盖 + 深色模式 + 无障碍

```markdown
## 状态覆盖

| 状态 | Figma | 项目已有组件 | 实现 |
|------|-------|------------|------|
| Success | ✅ 有设计 | — | 按设计规格实现 |
| Loading | ❌ 未覆盖 | ✅ AppSkeleton | 沿用 |
| Empty | ❌ 未覆盖 | ✅ AppEmptyView | 沿用 |
| Error | ❌ 未覆盖 | ✅ AppErrorView | 沿用 |

## 深色模式

- Figma 是否包含深色变体: 是/否
- 颜色是否通过 Material3 主题定义: 是/否
- 适配方案: 自动切换 / 需手动适配 / 不需要

## 无障碍

| 问题 | Figma 节点 | 描述 | 严重程度 |
|------|-----------|------|----------|
| Touch target 过小 | Frame 456 | 按钮 32x32dp < 48dp | 高 |
| 对比度不足 | Text 789 | 灰色文字在白色背景上 | 中 |
```

### 产出物 5: 注入 plan 文件 (被 autoplan 调用时)

**注意:** 当被 android-autoplan Phase 3 调用时，注入步骤由 autoplan 执行
(读取 design-spec.md 中的注释块并追加到 plan 文件)，而非本 skill 直接执行。
仅当 design-review 被**单独使用**且用户指定了 plan 文件路径时，才在此步骤中直接注入。

**注入格式:** 在 plan 文件的相关任务步骤末尾添加 `<!-- DESIGN -->` 注释块。

```markdown
### Task 3: 创建登录界面

**层级:** 表现层

**步骤:**
- [ ] 创建 LoginScreen Composable
- [ ] 实现邮箱输入框
- [ ] 实现密码输入框
- [ ] 实现登录按钮

<!-- DESIGN
设计规格: docs/plans/<slug>-design-spec.md
使用 AppCard (圆角 24dp), AppTextField, AppButton
背景色: MaterialTheme.colorScheme.surface
字号: MaterialTheme.typography.bodyLarge
状态: Loading 沿用 AppSkeleton, Empty/Error 沿用项目组件
资源: 需导出 ic_back_24dp, ic_visible_24dp
深色模式: 颜色通过主题定义，自动适配
-->
```

**新增任务 (如果 Figma 覆盖了状态但 plan 没有):**

```markdown
### Task N+1: 实现登录页面状态组件

**层级:** 表现层

<!-- DESIGN-NEW
Figma 未覆盖此状态，项目已有组件可沿用:
- Loading: AppSkeleton
- Empty: AppEmptyView (文案: "暂无登录记录")
- Error: AppErrorView (含重试按钮)
-->
```

---

## 异常情况处理

| 场景 | 处理方式 |
|------|----------|
| Figma MCP 工具不存在 | 中断，输出安装指引，不继续 |
| Figma API Token 失效 (403) | 中断，提示更新 token |
| Figma 文件无权限 | 提示检查 Figma 文件权限设置 |
| Figma URL 格式错误 | 提示正确格式，提供示例 |
| get_figma_data 调用失败 | 重试一次，仍失败则中断 |
| download_figma_images 调用失败 | 跳过资源导出，标记失败资源 |
| SVG 导出内容为空/异常 | 标记失败，列出资源让用户手动导出 |
| 多模块项目 | 扫描所有模块，新文件放最合适模块 |
| 设计稿版本过旧 | 提示用户确认是否为最新版本 |
| 项目非 Android 项目 | 报错: 需要 Android 项目 |

---

## 文件结构

```
项目根目录/
├── docs/
│   ├── plans/
│   │   ├── <slug>.md                     ← autoplan 产出的 plan 文件
│   │   └── <slug>-design-spec.md           ← 本 skill 产出的设计规格
│   └── ...
├── .claude/
│   ├── skills/
│   │   ├── android-design-review/
│   │   │   └── SKILL.md                     ← 本 skill
│   │   ├── android-autoplan/
│   │   │   └── SKILL.md                     ← 调用本 skill
│   │   └── android-worktree-runner/
│   │       └── SKILL.md                     ← 下游执行
│   └── ...
```
