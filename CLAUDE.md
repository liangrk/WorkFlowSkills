# Android Development Skills

## Skill Routing

When the user's request matches an available skill, invoke it using the Skill tool as FIRST action.

| User Intent | Skill | Trigger |
|------------|-------|---------|
| 全局状态、仪表盘、查看进展 | `android-status` | "状态"、"全局状态"、"仪表盘"、"dashboard"、"当前状态" |
| 需求分析、头脑风暴、方案探索 | `android-brainstorm` | "头脑风暴"、"分析需求"、"探索方案" |
| 计划拆分、任务规划、review plan | `android-autoplan` | "拆分任务"、"做计划"、"autoplan"、"review plan" |
| 测试先行、TDD、写测试 | `android-tdd` | "TDD"、"测试先行"、"写测试" |
| 执行 plan、运行任务 | `android-worktree-runner` | "执行 plan"、"运行任务"、"worktree" |
| 代码审查、review 代码 | `android-code-review` | "代码审查"、"review 代码"、"检查代码质量" |
| QA 测试、功能验证 | `android-qa` | "QA"、"测试"、"功能验证"、"smoke test" |
| 覆盖率、补测试、夜间测试 | `android-coverage` | "覆盖率"、"coverage"、"补测试"、"夜间测试" |
| 性能测试、benchmark、启动优化 | `android-benchmark` | "benchmark"、"性能测试"、"启动速度"、"帧率"、"内存分析" |
| 性能分析、ANR、内存泄漏、卡顿 | `android-performance` | "性能分析"、"ANR"、"内存泄漏"、"启动慢"、"卡顿"、"耗电" |
| Bug 排查、调试、crash 分析 | `android-investigate` | "排查 bug"、"调试"、"crash"、"为什么报错" |
| 保存进度、恢复状态 | `android-checkpoint` | "保存进度"、"恢复"、"checkpoint" |
| Figma 设计审查 | `android-design-review` | "设计审查"、"Figma"、"设计稿" |
| 文档更新 | `android-document-release` | "更新文档"、"文档同步" |
| 提交、push、创建 PR | `android-ship` | "提交"、"push"、"创建 PR"、"ship" |
| 学习记录、知识管理 | `android-learn` | "学习记录"、"知识"、"learnings" |

## Conventions

- All skill outputs are in Chinese unless the user explicitly uses English
- Plan files go to `docs/plans/`
- Review/QA reports go to `docs/reviews/`
- Learning data is stored in `~/.android-skills/projects/<slug>/learnings.jsonl`
