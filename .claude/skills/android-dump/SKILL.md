---
name: android-dump
description: |
  Automated Android UI hierarchy dumper. Dumps complete view tree with resource IDs, text, layout properties. Generates interactive HTML visualization.
  Triggers: dump UI, view hierarchy, element IDs, screen inspection, run and verify UI, auto validate app interface, check current screen, analyze app layout, UI testing verification
---

# Android UI Dump Skill

全自动 Android UI 视图树抓取,一键生成可视化报告。

## Phase 1: 环境检查

```bash
adb version >/dev/null 2>&1 && echo "ADB: OK" || echo "ADB: MISSING"
_DEVICE=$(adb devices 2>/dev/null | grep -E "device$" | head -1 | awk '{print $1}')
[ -n "$_DEVICE" ] && echo "DEVICE: $_DEVICE" || echo "DEVICE: NONE"
```

如 ADB/设备缺失,提示用户后 STOP。

## Phase 2: 执行 Dump

### 2.1 检测前台 App

```bash
_FOREGROUND=$(adb shell dumpsys window windows 2>/dev/null | grep -E 'mCurrentFocus|mFocusedApp' | head -1)
_PACKAGE=$(echo "$_FOREGROUND" | grep -oP 'com\.[a-zA-Z0-9_.]+/' | head -1 | cut -d'/' -f1)
[ -n "$_PACKAGE" ] && echo "DETECTED: $_PACKAGE" || echo "DETECTED: NONE"
```

询问用户确认包名。

### 2.2 一键 Dump

```bash
_DUMP_DIR="./android-dumps/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$_DUMP_DIR"
python scripts/dump_android_ui.py --package $_PACKAGE --output "$_DUMP_DIR"
```

## Phase 3: 结果展示

```
✅ DUMP COMPLETE
📁 $_DUMP_DIR/
📊 文件: ui_hierarchy.xml, screenshot.png, analysis.json, tree_view.html, report.txt
```

根据 analysis.json 和 report.txt 进行 UI 分析。

## Phase 4: 快速分析

```bash
cat "$_DUMP_DIR/analysis.json" | python -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Views: {data['total_views']}\")
print(f\"Clickable: {data['clickable']}\")
print(f\"Text: {data['with_text']}\")
print(f\"IDs: {data['with_id']}\")
print('\nTop IDs:')
for id in data['resource_ids'][:10]: print(f'  - {id}')
"
```

## 错误处理

- ADB 缺失 → 指引安装
- 无设备 → 提示连接/启动模拟器
- Dump 失败 → 尝试备用方法 (dumpsys activity)
- 不可调试 → 提示添加 debuggable

## 与其他 Skill 的衔接

| 下游 Skill | 传递内容 | 调用时机 |
|-----------|---------|---------|
| android-design-review | UI 层次结构 + 元素列表 (`analysis.json`) | 涉及 UI 设计还原时 |
| android-qa | UI 元素列表用于功能验证参考 | QA 测试阶段 |
| android-worktree-runner | Dump 验证 (PRD 包含 UI 验收标准时) | worktree-runner 执行阶段 |

## Telemetry (可选)

```bash
echo '{"skill":"android-dump","package":"'$_PACKAGE'","ts":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' >> ~/.gstack/analytics/skill-usage.jsonl 2>/dev/null || true
```
