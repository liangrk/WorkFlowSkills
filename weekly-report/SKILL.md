---
name: weekly-report
description: 生成周报 - 自动读取任务配置和多个仓库的 git log,生成结构化周报
---

# Weekly Report Generator

生成结构化周报,包含本周完成工作、进度情况和下周计划。

## 使用方式

### 1. 准备配置文件

在项目根目录或指定位置创建 `weekly-config.yaml`:

```yaml
# weekly-config.yaml - 周报配置模板

# 仓库列表 - 需要搜索 git log 的仓库路径
repositories:
  - name: 主项目
    path: ./main-project
  - name: 后端服务
    path: ../backend-service
  - name: 前端项目
    path: ../frontend-app

# 本周任务列表
tasks:
  - name: "用户登录功能"
    status: "completed"  # completed / in_progress / planned
    progress: 100        # 0-100
    description: "完成 OAuth2.0 登录集成"
    category: "feature"  # feature / bugfix / optimization / doc
  
  - name: "数据库优化"
    status: "in_progress"
    progress: 60
    description: "查询性能优化,添加索引"
    category: "optimization"
  
  - name: "API 文档更新"
    status: "planned"
    progress: 0
    description: "补充新增接口文档"
    category: "doc"

# 周报配置
config:
  # 周报名称
  title: "工作周报"
  
  # 是否显示 git log 详情
  show_git_details: true
  
  # 日志过滤 - 只显示包含这些关键词的 commit
  commit_filters:
    - feat
    - fix
    - refactor
    - docs
  
  # 排除的分支
  exclude_branches:
    - main
    - master
    - develop
```

### 2. 运行

```bash
# 使用默认配置文件
python scripts/generate-report.py

# 指定配置文件路径
python scripts/generate-report.py --config /path/to/weekly-config.yaml

# 指定报告周期(默认近7天)
python scripts/generate-report.py --days 5
```

## 输出格式

```
==================== 工作周报 ====================
报告周期: 2026-04-07 ~ 2026-04-13

【本周完成工作】
✅ 用户登录功能
   - 完成 OAuth2.0 登录集成
   - 修复 token 刷新问题

🔄 数据库优化 (60%)
   - 添加 users 表索引
   - 优化慢查询

【下周计划】
📋 API 文档更新
   - 补充新增接口文档

【进度总览】
完成: 1 | 进行中: 1 | 计划中: 1
==================================================
```

## 依赖

- Python 3.7+
- PyYAML (`pip install pyyaml`)

## 注意事项

1. 确保配置文件中的仓库路径存在且为有效的 git 仓库
2. 任务状态: completed(已完成), in_progress(进行中), planned(计划中)
3. 如仓库路径不存在,会跳过并警告
4. Commit 日志会自动按日期和仓库分组
