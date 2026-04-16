# Design: Android Design Review Skill

> 生成于 2026-04-10 | /office-hours | v3
> 项目: kskills | 状态: DRAFT
> 模式: Builder

## 问题

需要一个独立的 Figma-to-Android 设计审查 skill。不嵌入 autoplan，运行时按需加载。

## 核心需求 (用户定义)

1. 获取 Figma session URL 作为设计稿来源
2. 直接调用 Claude Code 中定义的 figma-mcp 工具，没有则中断让用户安装
3. icon 导出默认 3 倍图到项目
4. SVG 导出失败时让用户手动完成，不可自己生成
5. Figma px = Android dp (1:1)
6. 用项目已有 UI 库实现样式，不用原生方案重复造轮子
7. 项目风格保持一致
8. **独立 skill，autoplan 执行时询问是否需要，否则不加载节省上下文**

## Figma MCP 依赖

### 自动检测与连接流程

**Phase 0 自动化流程:**

```
1. skill 启动后，自动运行 figma-mcp-check 脚本
   ↓
2. 检测 ~/.claude/settings.json 和项目 .claude/settings.json
   ↓
3. 判断配置状态:
   ├─ 已配置 + API Key 有效 → 自动连接，继续执行
   ├─ 已配置 + API Key 缺失/占位符 → 提示用户更新
   └─ 未配置 → 提示用户安装配置
   ↓
4. 根据检测结果提供对应指引
   ↓
5. 用户确认完成后，尝试调用 get_figma_data 验证可用性
   ↓
6. 验证通过 → 继续 Phase 1
   验证失败 → 返回对应步骤
```

**检测脚本 (figma-mcp-check) 功能:**
- 自动搜索全局和项目级 settings.json
- 检测 MCP server 名称匹配 (支持 `Framelink MCP for Figma` 和 `figma-developer-mcp`)
- 检查 API Key 是否为占位符或真实值
- 输出结构化 JSON 状态，供 skill 解析
- 提供文本格式的安装指引

**优势:**
- ✅ 无需用户手动检查配置状态
- ✅ 自动检测，减少出错概率
- ✅ 根据检测结果提供针对性指引
- ✅ 配置完成后可自动验证可用性
- ✅ 支持跨平台 (Windows/macOS/Linux)

### 目标 MCP

**包:** `figma-developer-mcp` (npm)
**GitHub:** https://github.com/glips/figma-context-mcp
**MCP Server 名称:** `Framelink MCP for Figma`

**注意:** 此 MCP 只有 2 个工具，没有内置的 design token 提取、组件分析、无障碍检查等功能。
这些分析由 skill 自行完成 (解析 `get_figma_data` 的输出)。

### 安装配置

**Figma API Token 获取:**
1. Figma → 账号菜单 → Settings → Security 标签
2. Personal access tokens → Generate new token
3. 输入名称，选择权限范围，生成
4. 复制 token (仅显示一次)

**Claude Code 配置 (Windows):**

```json
{
  "mcpServers": {
    "Framelink MCP for Figma": {
      "command": "cmd",
      "args": ["/c", "npx", "-y", "figma-developer-mcp", "--figma-api-key=YOUR-KEY", "--stdio"]
    }
  }
}
```

**Claude Code 配置 (macOS/Linux):**

```json
{
  "mcpServers": {
    "Framelink MCP for Figma": {
      "command": "npx",
      "args": ["-y", "figma-developer-mcp", "--figma-api-key=YOUR-KEY", "--stdio"]
    }
  }
}
```

配置文件位置: `~/.claude/settings.json` (全局) 或 `.claude/settings.json` (项目)

### 可用工具 (仅 2 个)

#### 工具 1: `get_figma_data`

获取 Figma 文件的完整设计数据 (布局、样式、组件信息)。输出为简化后的 YAML/JSON。

**参数:**

| 参数 | 必需 | 说明 |
|------|------|------|
| `fileKey` | 是 | Figma 文件 key (从 URL 提取) |
| `nodeId` | 否 | 特定节点 ID，格式 `1234:5678` 或 `I5666:180910;1:10515` (多个节点用 `;` 分隔) |
| `depth` | 否 | 遍历深度 (不要主动设置，除非用户要求) |

**nodeId 格式注意:** Figma URL 中 `node-id=1-2-3` 用 `-` 分隔，工具内部会替换为 `:`。

**返回内容:**
- `metadata` — 文件元信息
- `nodes` — 节点树 (包含布局、样式、文本、图片引用)
- `globalVars` — 全局变量 (颜色、字体、效果等)

**特性:** 自动简化原始 Figma API 响应，只保留布局和样式相关信息。自动折叠 SVG 容器。

#### 工具 2: `download_figma_images`

从 Figma 导出 SVG 和 PNG 图片到本地。

**参数:**

| 参数 | 必需 | 说明 |
|------|------|------|
| `fileKey` | 是 | Figma 文件 key |
| `nodes` | 是 | 节点数组，每个节点包含: |
| `nodes[].nodeId` | 是 | Figma 节点 ID |
| `nodes[].fileName` | 是 | 输出文件名 (必须以 `.png` / `.svg` / `.gif` 结尾) |
| `nodes[].imageRef` | 否 | 图片填充引用 (PNG 需要) |
| `nodes[].gifRef` | 否 | 动图填充引用 (GIF 需要) |
| `nodes[].needsCropping` | 否 | 是否需要裁剪 |
| `pngScale` | 否 | PNG 导出倍率，**默认 2，skill 中设为 3** |
| `localPath` | 是 | 保存目录 (相对于项目根目录) |

**返回:** 下载的图片列表，包含文件路径和尺寸信息。

### MCP 可用性检查策略

**不使用 bash 命令检查。直接调用 MCP 工具。**

```
流程:
1. skill 启动后，直接尝试调用 get_figma_data
2. 如果工具不存在 (Claude Code 报错 "tool not found") → 中断
3. 如果工具调用返回 403/auth 错误 → 中断，提示 token 问题
4. 如果工具调用成功 → 继续执行

中断时的提示:
"Figma MCP 未就绪。请先安装 figma-mcp:
1. 获取 Figma API Token: Figma → Settings → Security → Personal Access Tokens
2. 在 Claude Code 中配置 MCP server:
   打开 ~/.claude/settings.json，在 mcpServers 中添加:
   { \"Framelink MCP for Figma\": { \"command\": \"cmd\", \"args\": [\"/c\", \"npx\", \"-y\", \"figma-developer-mcp\", \"--figma-api-key=YOUR-KEY\", \"--stdio\"] } }
3. 配置完成后重新运行 /android-design-review"
```

## 前提

1. Figma MCP 是设计数据的唯一来源，不猜测设计
2. 项目代码是实现的唯一真相源，不发明新模式
3. 设计稿可能有遗漏 (状态、深色模式、响应式)，审查时要标记
4. 资源导出遵循 Android 多密度规范 (drawable-xxhdpi 为基准)
5. SVG → VectorDrawable 转换有时不可靠 (复杂路径、渐变、mask 等情况)，失败时交给人工

## Skill 设计

### 名称: android-design-review

### 调用方式

```bash
/android-design-review <figma-url>    # 直接传入 Figma 链接
/android-design-review                  # 交互式，询问 Figma URL
/android-design-review review          # 仅审查，不导出资源
```

### Phase 0: Figma MCP 检查

**步骤 1: 直接调用 MCP 工具**

尝试调用 `get_figma_data`，传入用户提供的 Figma URL (或占位 URL)。

**三种结果:**
- **工具不存在** → 中断，输出安装指引
- **Auth 失败 (403)** → 中断，提示检查 API Token
- **成功** → 继续到步骤 2

**步骤 2: 获取 Figma URL**

- 带参数 → 直接使用
- 无参数 → AskUserQuestion 询问

**步骤 3: 解析 Figma URL**

```
https://www.figma.com/design/{file-key}/{title}?node-id={node-id}
https://www.figma.com/file/{file-key}/{title}?node-id={node-id}
```

- 提取 `file-key` (必需)
- 提取 `node-id` (可选，指定页面/帧)
- 无 `node-id` → 读取文件后列出页面，AskUserQuestion 选择

**步骤 4: 检测项目环境**

扫描项目，确定 UI 框架、组件库、命名规范。

```bash
# 确定项目根目录和模块
PROJECT_ROOT=$(git rev-parse --show-toplevel)
SETTINGS_GRADLE="$PROJECT_ROOT/settings.gradle"
SETTINGS_GRADLE_KTS="$PROJECT_ROOT/settings.gradle.kts"

# 列出所有模块
cat "$SETTINGS_GRADLE" "$SETTINGS_GRADLE_KTS" 2>/dev/null | grep "include"

# UI 框架检测 (扫描所有模块，不只 app/)
grep -rl "@Composable" "$PROJECT_ROOT" --include="*.kt" 2>/dev/null | head -5
find "$PROJECT_ROOT" -path "*/res/layout/*.xml" 2>/dev/null | head -5

# UI 库检测 (扫描所有 build.gradle)
grep -rl "com.google.android.material" "$PROJECT_ROOT" --include="*.gradle*" 2>/dev/null
grep -rl "io.github.aakira" "$PROJECT_ROOT" --include="*.gradle*" 2>/dev/null
grep -rl "coil" "$PROJECT_ROOT" --include="*.gradle*" 2>/dev/null
grep -rl "lottie" "$PROJECT_ROOT" --include="*.gradle*" 2>/dev/null
```

产出项目 UI 档案:
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

### Phase 1: 设计稿数据读取

**数据读取策略 (只有 2 个 MCP 工具，skill 需自行解析):**

```
步骤 1: get_figma_data(fileKey=<file-key>, nodeId=<node-id>)
  ↓ 获取简化后的设计数据 (YAML/JSON)
  ↓ 包含: 节点树、布局、样式、文本、图片引用、全局变量

步骤 2: skill 自行解析 get_figma_data 输出
  ↓ 从节点树中提取:
  ↓   - 颜色 (fill/stroke) → 整理为颜色 token 列表
  ↓   - 字体 (family/size/weight) → 整理为 typography 列表
  ↓   - 间距 (padding/margin/gap) → 整理为间距列表
  ↓   - 圆角 (corner radius) → 整理为 shape 列表
  ↓   - 阴影 (drop-shadow) → 整理为 elevation 列表
  ↓   - 图片/icon 引用 → 整理为资源导出清单
  ↓   - 组件 (component) → 整理为组件映射候选

步骤 3: download_figma_images(...)
  ↓ 导出图片/icon 到项目
  ↓ pngScale 设为 3 (用户要求默认 3 倍图)
  ↓ SVG 直接导出 (.svg)，PNG 指定 pngScale=3
```

**如果 get_figma_data 调用失败:** Phase 0 已确保工具可用，此处失败应重试一次。
**如果 download_figma_images 调用失败:** 跳过资源导出，标记 "资源导出失败"，不中断整体流程。

**提取内容映射:**

| 数据类型 | 来源 | 提取方式 |
|----------|------|----------|
| 组件树/图层结构 | get_figma_data.nodes | 直接使用节点树 |
| 颜色 (fill/stroke) | get_figma_data.nodes + globalVars | 解析节点 fill/stroke 属性 |
| 字体 (family/size/weight) | get_figma_data.nodes | 解析节点 style/字体属性 |
| 间距 (padding/margin/gap) | get_figma_data.nodes | 解析布局约束 (autoLayout) |
| 圆角 (corner radius) | get_figma_data.nodes | 解析节点 cornerRadius 属性 |
| 阴影 (drop-shadow) | get_figma_data.nodes | 解析节点 effects 属性 |
| 图片/icon 引用 | get_figma_data.nodes | 解析节点 imageRef/gifRef |
| 原型交互 | get_figma_data.nodes | 解析节点 prototype 相关属性 |
| 组件定义/变体 | get_figma_data.nodes | 解析 component/variant 属性 |

### Phase 2: 项目上下文分析

**步骤 1: 检测已有组件 (多模块扫描)**

```bash
# Compose 自定义组件
grep -rl "@Composable" "$PROJECT_ROOT" --include="*.kt" | grep -v test | head -20

# XML 自定义 View
grep -rl "extends.*View\|extends.*ViewGroup" "$PROJECT_ROOT" --include="*.kt" --include="*.java" | grep -v test | head -20
```

**步骤 2: 检测命名规范**

```bash
# 扫描所有模块的资源命名
find "$PROJECT_ROOT" -path "*/res/drawable*" -name "*.xml" 2>/dev/null | xargs -I{} basename {} | head -30
find "$PROJECT_ROOT" -path "*/res/drawable*" -name "*.webp" -o -name "*.png" 2>/dev/null | xargs -I{} basename {} | head -20
```

推断命名模式:
```
=== 资源命名规范 (推断) ===
Icon:     ic_xxx_24dp / ic_xxx (基于现有文件推断)
Image:    img_xxx / bg_xxx
Layout:   item_xxx / fragment_xxx / activity_xxx
Color:    colorPrimary / brand_xxx / xxx_500
Dimens:   spacing_xxx / margin_xxx / dp_xxx
```

**步骤 3: 检测主题系统**

```bash
# Material3 检测
grep -rl "MaterialTheme" "$PROJECT_ROOT" --include="*.kt" | head -5
grep -rl "Theme.Material3" "$PROJECT_ROOT" --include="*.xml" | head -5

# 深色模式检测
find "$PROJECT_ROOT" -path "*/values-night*" 2>/dev/null | head -5
```

**步骤 4: 检测已有状态组件**

```bash
# 搜索项目中已有的 loading/empty/error 组件
grep -ril "skeleton\|shimmer\|loading" "$PROJECT_ROOT" --include="*.kt" | grep -v test | head -5
grep -ril "empty.*view\|no.*data\|empty.*state" "$PROJECT_ROOT" --include="*.kt" --include="*.xml" | grep -v test | head -5
grep -ril "error.*view\|error.*state\|retry" "$PROJECT_ROOT" --include="*.kt" --include="*.xml" | grep -v test | head -5
```

### Phase 3: 设计审查 (六维度)

##### 维度 1: 设计还原度规划

将 Figma 设计数据映射为 Android 实现规格。

**映射规则:**

| Figma 属性 | Android 实现 | Compose | XML | 规则 |
|------------|-------------|---------|-----|------|
| 位置/尺寸 (px) | dp | `Modifier.size()` / `Modifier.padding()` | `layout_width/height` | 1:1 直接转换 |
| 颜色 (hex) | colors.xml / theme | `MaterialTheme.colorScheme.xxx` | `@color/xxx` | 先查已有 token，无则新建 |
| 字体大小 (px) | sp | `MaterialTheme.typography.xxx` | `TextAppearance.xxx` | 正文用 sp，固定尺寸元素 (badge) 用 dp |
| 字重 | FontWeight | `FontWeight.Bold` | `android:textStyle="bold"` | 100-900 映射 |
| 间距 (px) | dp | `Modifier.padding()` / `Arrangement.spacedBy()` | `padding/margin` | 检查是否符合 8dp 网格 |
| 圆角 (px) | dp | 项目圆角方案 | 项目圆角方案 | 不直接用 clip-path |
| 阴影 | elevation (dp) | `Modifier.shadow()` / elevation | `app:elevation` | 用项目已有方案 |
| 线性渐变 | Brush / GradientDrawable | `Brush.linearGradient()` | XML gradient | 检查角度映射 |

**Compose vs XML 关键差异:**

| 场景 | Compose | XML |
|------|---------|-----|
| 圆角 | `Modifier.clip(RoundedCornerShape())` | `app:cornerRadius` + ShapeableImageView |
| 背景 | `Modifier.background()` + Brush | `android:background` + drawable |
| 间距 | `Modifier.padding()` / `Arrangement` | `padding` / `margin` 属性 |
| 状态 | `mutableStateOf` + remember | ViewModel + LiveData/StateFlow |
| 列表 | `LazyColumn` | `RecyclerView` + Adapter |

**输出:** 每个设计元素的 Android 实现值 (含 Compose/XML 双路径)。

##### 维度 2: 项目框架一致性

**组件映射决策逻辑:**

```
对 Figma 中的每个 UI 元素:
1. 检查 Phase 2 检测到的项目已有组件列表
   → 匹配到已有组件 → 使用它 (标记 "✅ 已有")
2. 未匹配 → 检查 Figma 组件的 componentProperty / description
   → 如果 Figma 组件名含 "Button" → 映射到 Material Button / 项目 AppButton
   → 如果 Figma 组件名含 "Card" → 映射到 Material Card / 项目 AppCard
   → 如果 Figma 组件名含 "Input" / "TextField" → 映射到 Material TextField / 项目 AppTextField
3. 仍无法匹配 → AskUserQuestion 让用户指定映射
4. 全新组件 → 标记 "❌ 需新建"
```

**匹配策略:**
- **名称匹配:** Figma 组件名与项目文件名相似度 (忽略大小写、下划线/连字符差异)
- **语义匹配:** Figma 组件的 description 字段与项目组件的功能描述
- **视觉匹配:** 组件的外观特征 (有圆角、有阴影、有图标位)

**样式一致性规则:**
- 项目用自定义圆角库 → 新代码也用该库
- 项目用 Coil 加载图片 → 新代码也用 Coil，不用 Glide
- 项目用 Lottie 做动画 → 新动画也用 Lottie
- 项目用 Compose → 新 UI 用 Compose，不用 XML

##### 维度 3: 状态覆盖审查

**必查状态:**

| 状态 | 说明 | 审查方式 |
|------|------|----------|
| Success | 数据就绪 | 对照 Figma 设计稿验证 |
| Loading | 首次加载/刷新 | 检查项目 Skeleton 组件，沿用或标记需补充 |
| Empty | 无数据 | 检查项目 EmptyView，沿用或标记需补充 |
| Error | 网络/服务器/权限 | 检查项目 ErrorView，沿用或标记需补充 |
| Partial | 分页加载中 | 标记需补充 (Figma 很少画) |

**审查逻辑:**
1. 遍历 Figma 设计稿的所有 Frame/Page
2. 检查 Frame 名称是否包含状态关键词 (loading, empty, error, skeleton, no-data)
3. 未找到状态 Frame → 检查项目已有状态组件 (Phase 2 步骤 4)
4. 项目已有 → 标记 "沿用项目已有组件"
5. 项目没有 + Figma 没画 → 标记 "❌ 需要补充设计或沿用通用方案"

##### 维度 4: 平台适配

**审查项:**

1. **深色模式**
   - Figma 中是否有名为 "Dark" / "Dark mode" 的页面/组件变体?
   - 颜色是否通过 design tokens 定义 (可映射到 Material3 主题)?
   - 项目是否已有 `values-night/` 目录?
   - 产出: 深色模式适配方案

2. **多屏幕/响应式**
   - 设计稿基准宽度: 记录 (375px / 390px / 其他)
   - 布局是否使用 Auto Layout / ConstraintLayout (不是绝对定位)?
   - 项目是否需要支持横屏/平板/折叠屏?
   - 产出: 响应式适配建议

3. **无障碍**
   - Touch target < 48dp → 标记 (从节点尺寸数据中计算)
   - 对比度 < 4.5:1 → 标记 (从颜色和字体数据中计算)
   - 是否需要 ContentDescription → 标记 (从语义和角色推断)
   - 注意: MCP 没有内置无障碍检查工具，由 skill 根据 get_figma_data 输出自行计算

##### 维度 5: 资源导出计划

**导出规则:**

| 资源类型 | 格式 | 密度 | 命名 | 导出方式 |
|----------|------|------|------|----------|
| Icon (单色/简单) | VectorDrawable (XML) | — | ic_xxx_24dp | MCP 导出 SVG → 转换 |
| Icon (复杂路径/渐变) | WebP | 3x (xxhdpi) | ic_xxx | MCP download_figma_images |
| 插画/图片 | WebP | 2x (xhdpi) + 3x (xxhdpi) | img_xxx | MCP download_figma_images |
| 动图 | Lottie JSON | — | anim_xxx | 特殊处理 (非 MCP) |

**SVG → VectorDrawable 转换规则:**
- 简单路径 (线条、填充、无渐变) → 自动转换
- 复杂情况 (渐变、mask、clip-path、复杂路径) → 转换可能不精确，标记 "⚠️ 需人工验证"
- 转换完全失败 → 标记 "❌ SVG 导出失败"，提供 Figma 节点链接和目标路径

**不自动生成 SVG 代码。** 只使用 MCP 导出的原始数据。

**icon 导出默认 3 倍图:**
- 通过 `download_figma_images` 导出时，scale 参数默认 3
- 导出路径: `<module>/src/main/res/drawable-xxhdpi/`

**命名规范:**
- 遵循 Phase 2 检测到的项目命名模式
- 不使用 Figma 原始命名

##### 维度 6: 动效规格 (如果有)

**如果 Figma 原型包含交互/动画:**

| Figma 属性 | Compose | XML |
|------------|---------|-----|
| Smart Animate (进入) | AnimatedVisibility | MotionLayout |
| Smart Animate (退出) | AnimatedVisibility | MotionLayout |
| 页面转场 | SharedTransition + Nav动画 | Navigation animation |
| 按钮微交互 | `Modifier.composed { ... }` + Animatable | ViewPropertyAnimator |
| Loading 动画 | CircularProgressIndicator / Lottie | ProgressBar / Lottie |
| duration | 直接使用 (ms) | 直接使用 (ms) |
| easing (ease-in) | FastOutSlowInEasing | @animator/fast_out_slow_in |
| easing (ease-out) | LinearOutSlowInEasing | @animator/linear_out_slow_in |
| easing (ease-in-out) | FastOutLinearInEasing | @animator/fast_out_linear_in |
| easing (自定义 cubic-bezier) | CubicBezierEasing(x1,y1,x2,y2) | 需自定义 PathInterpolator |

**如果 Figma 没有动效:** 标记 "使用项目默认动画"，列出项目已有的动画配置。

### Phase 4: 产出

##### 产出物 1: 设计规格文档

写入 `docs/plans/<plan-slug>-design-spec.md`:

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

##### 产出物 2: 组件映射表

```markdown
## 组件映射

| Figma 组件 | Android 实现 | 项目组件 | 模块 | 备注 |
|------------|-------------|---------|------|------|
| Button / Primary | AppButton | ✅ 已有 | :feature:components | |
| Card / Container | AppCard | ✅ 已有 | :feature:components | |
| Input Field | AppTextField | ✅ 已有 | :feature:components | |
| Bottom Sheet | ModalBottomSheet | — | Material3 | 原生 |
| Status Badge | — | ❌ 需新建 | :feature:login | Figma 有，项目无 |
```

##### 产出物 3: 资源清单

```markdown
## 资源导出清单

### Icon (VectorDrawable)
| 名称 | Figma 节点 | 目标路径 | 状态 |
|------|-----------|----------|------|
| ic_back_24dp | Frame 123 | feature:login/.../drawable/ic_back_24dp.xml | ✅ 可导出 |
| ic_search_24dp | Frame 456 | core:ui/.../drawable/ic_search_24dp.xml | ⚠️ 需人工验证 |
| ic_settings_24dp | Frame 789 | core:common/.../drawable/ic_settings_24dp.xml | ❌ SVG 导出失败 |

### 图片 (WebP)
| 名称 | Figma 节点 | 目标路径 | 密度 | 状态 |
|------|-----------|----------|------|------|
| img_banner | Frame 111 | feature:login/.../drawable-xxhdpi/img_banner.webp | 3x | ✅ 可导出 |
```

##### 产出物 4: 状态覆盖 + 深色模式 + 无障碍

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
| 对比度不足 | Text 789 | 灰色文字 #999999 在白色背景上 | 中 |
```

##### 产出物 5: 注入 plan 文件 (被 autoplan 调用时)

**注入格式:** 在 plan 文件的相关任务步骤中添加 `<!-- DESIGN -->` 注释块。

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
Figma 未覆盖此状态，但项目已有组件可沿用:
- Loading: AppSkeleton
- Empty: AppEmptyView (文案: "暂无登录记录")
- Error: AppErrorView (含重试按钮)
-->
```

## 与 android-autoplan 的衔接

### 独立 skill，按需加载

android-design-review 是完全独立的 skill，不嵌入 autoplan。
android-autoplan 在执行阶段**询问用户**是否需要设计审查。

### android-autoplan Phase 3 改为:

```markdown
## Phase 3: Android Design Review (可选)

AskUserQuestion: "是否需要 Figma 设计审查?"
- A) 是，我有 Figma 设计稿
- B) 跳过，不需要设计审查

如果选 A:
1. 询问 Figma URL
2. 使用 Skill 工具调用 android-design-review，传入 Figma URL
3. 等待设计审查完成
4. 读取产出的设计规格文档
5. 将 <!-- DESIGN --> 注释块注入 plan 文件的相关任务
6. 为缺失的状态添加补充任务

如果选 B:
跳过此阶段，在 plan 中标注 "未做设计审查"
```

**为什么要按需加载:**
- 不是所有功能都有 Figma 设计稿
- 加载设计审查 skill 会消耗大量上下文 (Figma 设计数据很大)
- 用户明确需要时才加载，节省上下文空间

### 完整流程链路

**有设计稿时:**
```
功能需求
  ↓
android-autoplan Phase 1: 需求拆分 → 初版 plan
  ↓
android-autoplan Phase 2: CEO Review
  ↓
android-autoplan Phase 3: 询问用户 → 需要 → 调用 /android-design-review → 设计规格
  ↓
android-autoplan Phase 4: Eng Review (读取设计规格，纳入审查)
  ↓
android-autoplan Phase 5: DX Review
  ↓
最终审批 → 自动调用 /android-worktree-runner
```

**没有设计稿时:**
```
功能需求
  ↓
android-autoplan Phase 1: 需求拆分 → 初版 plan
  ↓
android-autoplan Phase 2: CEO Review
  ↓
android-autoplan Phase 3: 询问用户 → 跳过
  ↓
android-autoplan Phase 4: Eng Review
  ↓
android-autoplan Phase 5: DX Review
  ↓
最终审批 → 自动调用 /android-worktree-runner
```

**独立使用:**
```
/android-design-review <figma-url>  ← 不经过 autoplan，独立运行
```

## 零外部依赖

- Claude Code 原生工具 (Read、Write、Edit、Grep、Glob、Bash)
- Figma MCP 工具 (figma-developer-mcp / Framelink MCP for Figma)
  - `get_figma_data` — 读取设计数据
  - `download_figma_images` — 导出图片
- Agent 工具 (subagent 审查，可选)

**不依赖:** gstack 二进制、Codex、browse、design

## 异常情况处理

| 场景 | 处理方式 |
|------|----------|
| Figma MCP 工具不存在 | 中断，输出安装指引，不继续 |
| Figma API Token 失效 (403) | 中断，提示更新 token |
| Figma 文件无权限 | 提示检查 Figma 文件权限设置 |
| Figma URL 格式错误 | 提示正确格式，提供示例 |
| MCP 单个工具调用失败 | 跳过该步骤，标记缺失，不中断 |
| SVG 导出失败 | 列出失败资源 (含 Figma 节点链接)，让用户手动 |
| SVG 转换不精确 | 标记 "⚠️ 需人工验证"，不自动生成 |
| 多模块项目 | 扫描所有模块，新文件放到最合适的模块 |
| 设计稿版本过旧 | 提示用户确认是否为最新版本 |
