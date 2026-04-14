# 周报生成 Skill

自动生成结构化工作周报,整合任务状态和多个仓库的 git 提交记录。

## 快速开始

### 1. 安装依赖

```bash
pip install pyyaml
```

### 2. 配置

复制并编辑配置文件:

```bash
cp weekly-config.yaml my-weekly-config.yaml
```

编辑 `my-weekly-config.yaml`:

```yaml
# 配置需要监控的仓库
repositories:
  - name: 主项目
    path: /path/to/your/main-project
  - name: 后端服务
    path: /path/to/backend-service

# 配置任务列表
tasks:
  - name: "用户登录功能"
    status: "completed"  # completed / in_progress / planned
    progress: 100
    description: "完成 OAuth2.0 登录集成"
    category: "feature"
  
  - name: "性能优化"
    status: "in_progress"
    progress: 60
    description: "数据库查询优化"
    category: "optimization"
  
  - name: "API 文档"
    status: "planned"
    progress: 0
    description: "补充接口文档"
    category: "doc"
```

### 3. 生成周报

```bash
# 使用默认配置
python scripts/generate-report.py

# 指定配置文件
python scripts/generate-report.py --config my-weekly-config.yaml

# 指定报告周期(5天)
python scripts/generate-report.py --days 5
```

## 配置说明

### repositories (仓库列表)

定义需要搜索 git log 的仓库路径。

- `name`: 仓库显示名称
- `path`: 仓库路径(相对或绝对路径)

### tasks (任务列表)

定义本周的任务状态。

- `name`: 任务名称
- `status`: 任务状态
  - `completed`: 已完成
  - `in_progress`: 进行中
  - `planned`: 计划中
- `progress`: 进度百分比 (0-100)
- `description`: 任务描述
- `category`: 任务分类 (feature/bugfix/optimization/doc/other)

### config (周报配置)

- `title`: 周报名称
- `show_git_details`: 是否显示 git 提交详情
- `commit_filters`: 提交消息过滤关键词(空=不过滤)
- `exclude_branches`: 排除的分支名

## 输出示例

```
==================== 工作周报 ====================
报告周期: 2026-04-07 ~ 2026-04-13

【本周完成工作】
✅ 用户登录功能 (100%)
   - 完成 OAuth2.0 登录集成
   Git 提交:
   [2026-04-12] feat: add OAuth2 login support (主项目)

【进行中任务】
🔄 性能优化 (60%)
   - 数据库查询优化
   Git 提交:
   [2026-04-10] perf: optimize user query (后端服务)

【下周计划】
📋 API 文档
   - 补充接口文档

【进度总览】
总计: 3 | 完成: 1 | 进行中: 1 | 计划中: 1
总体进度: 53.3%
==================================================
```

## 工作原理

1. 读取 YAML 配置文件
2. 遍历配置的仓库路径,检查是否为有效 git 仓库
3. 查询近 N 天(默认7天)的 git log
4. 根据任务名称关键词匹配相关提交
5. 按任务状态分组生成结构化报告
6. 输出到终端

## 高级用法

### 导出到文件

```bash
python scripts/generate-report.py > weekly-report-$(date +%Y%m%d).md
```

### 结合 cron 自动生成

```bash
# 每周五下午5点自动生成
0 17 * * 5 cd /path/to/WeeklyReportSkills/weekly-report && python scripts/generate-report.py --config /path/to/config.yaml > /path/to/reports/weekly-$(date +\%Y\%m\%d).md
```

## 故障排除

**问题**: `错误: 需要 PyYAML 库`
**解决**: `pip install pyyaml`

**问题**: `仓库路径不存在`
**解决**: 检查配置文件中的路径是否正确

**问题**: `无相关提交`
**解决**: 
- 确认仓库路径是有效的 git 仓库
- 检查日期范围是否有提交记录
- 检查 `commit_filters` 是否过滤掉了提交

## 文件结构

```
weekly-report/
├── SKILL.md                 # Skill 定义文件
├── weekly-config.yaml       # 默认配置模板
├── README.md                # 本文档
└── scripts/
    └── generate-report.py   # 周报生成脚本
```

## License

MIT
