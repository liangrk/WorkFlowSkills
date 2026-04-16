---
name: android-design-review
description: |
  Figma 设计稿审查。检查设计还原、组件映射、资源导出。
---

# Design Review

**调用:** `/android-design-review <figma-url>`

## Phase 0: Figma MCP 自动检测

### 检测与处理

```bash
SHARED_BIN=$(bash android-resolve-path 2>/dev/null || true)
[ -n "$SHARED_BIN" ] && export PATH="$SHARED_BIN/bin:$PATH"
FIGMA_STATUS=$(bash "$SHARED_BIN/bin/figma-mcp-check" --format json 2>/dev/null || echo '{"configured":false}')
```

**根据 FIGMA_STATUS 结果处理:**

| 状态 | 行为 |
|------|------|
| `configured: true` + `api_key_set: true` | 跳到 Phase 1 |
| `configured: true` + `api_key_set: false` | 提示更新 API Key，参考 `figma-mcp-setup` |
| `configured: false` | 提示安装配置，参考 `figma-mcp-setup` |

**需要配置时:** AskUserQuestion 提供选项，引导查看配置指引文档。
**配置后验证:** 尝试调用 `get_figma_data`，成功则继续，失败则重试或提示。

## Phase 1: 设计稿获取

若有 Figma URL: 通过 MCP 获取设计数据。
若无: 读取已有设计文档或截图。

## Phase 2: 六维度审查

| 维度 | 检查项 |
|------|--------|
| 设计还原 | 颜色/字体/间距/圆角/阴影是否 1:1 还原 |
| 组件映射 | Figma 组件 → Android 组件 (Compose/XML) 映射是否合理 |
| 资源导出 | icon/图片 是否 3 倍图导出, SVG 是否可用 |
| 状态覆盖 | 空状态/加载/错误/成功/禁用状态是否齐全 |
| 深色模式 | 颜色是否支持深色, 是否有深色设计稿 |
| 无障碍 | contentDescription / 触摸目标 / 对比度 |

## Phase 3: 产出

```
docs/reviews/<branch>-design-review.md:
  - 设计还原差异列表
  - 组件映射表
  - 资源导出清单
  - 缺失状态列表
  - 深色模式覆盖
  - 无障碍检查
```

AskUserQuestion: 是否注入到当前 plan?
- 是 → 写入 plan 文件的 `<!-- DESIGN -->` 注释块
- 否 → 仅保存报告
