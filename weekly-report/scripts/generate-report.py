#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
周报生成器 - 自动读取任务配置和多个仓库的 git log,生成结构化周报
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import yaml
except ImportError:
    print("错误: 需要 PyYAML 库,请运行: pip install pyyaml")
    sys.exit(1)


def get_current_week_range():
    """获取当前自然周的周一和周日(周一开始,周日结束)"""
    today = datetime.now()
    # weekday(): 0=周一, 6=周日
    weekday = today.weekday()
    # 本周一
    monday = today - timedelta(days=weekday)
    # 本周日
    sunday = monday + timedelta(days=6)
    return monday.replace(hour=0, minute=0, second=0, microsecond=0), sunday.replace(hour=23, minute=59, second=59, microsecond=999999)


class WeeklyReportGenerator:
    """周报生成器"""
    
    def __init__(self, config_path, use_natural_week=True):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        
        if use_natural_week:
            # 使用自然周(周一到周日)
            self.start_date, self.end_date = get_current_week_range()
        else:
            # 使用过去 N 天
            self.end_date = datetime.now()
            self.start_date = self.end_date - timedelta(days=7)
        
        self.git_logs = {}
        
    def _load_config(self):
        """加载 YAML 配置文件"""
        if not self.config_path.exists():
            print(f"错误: 配置文件不存在: {self.config_path}")
            sys.exit(1)
            
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            
        # 验证必要字段
        if 'tasks' not in config:
            print("错误: 配置文件中缺少 'tasks' 字段")
            sys.exit(1)
            
        if 'repositories' not in config:
            print("警告: 配置文件中缺少 'repositories' 字段,将跳过 git log 搜索")
            config['repositories'] = []
            
        if 'config' not in config:
            config['config'] = {}
            
        return config
    
    def _run_git_command(self, repo_path, command):
        """在指定仓库运行 git 命令"""
        try:
            import codecs
            
            # 创建环境变量副本,设置 git 使用 UTF-8
            env = os.environ.copy()
            env['GIT_TERMINAL_PROMPT'] = '0'
            env['LESSCHARSET'] = 'utf-8'
            
            result = subprocess.run(
                command,
                cwd=repo_path,
                capture_output=True,
                timeout=10,
                shell=True,
                env=env
            )
            if result.returncode == 0:
                # 优先尝试 UTF-8 和 GBK
                for encoding in ['utf-8', 'gbk']:
                    try:
                        return codecs.decode(result.stdout, encoding).strip()
                    except (UnicodeDecodeError, LookupError):
                        continue
                return codecs.decode(result.stdout, 'latin-1').strip()
            return None
        except Exception as e:
            print(f"  ⚠️  Git 命令执行失败: {e}")
            return None
    
    def _is_git_repo(self, path):
        """检查是否为有效的 git 仓库"""
        return self._run_git_command(path, "git rev-parse --git-dir") is not None
    
    def _get_git_log(self, repo_path, repo_name):
        """获取指定仓库的 git log"""
        if not Path(repo_path).exists():
            print(f"  ⚠️  仓库路径不存在: {repo_path}")
            return []
            
        if not self._is_git_repo(repo_path):
            print(f"  ⚠️  不是有效的 git 仓库: {repo_path}")
            return []
        
        # 获取当前分支
        branch = self._run_git_command(repo_path, "git branch --show-current")
        if not branch:
            branch = "unknown"
            
        # 检查是否在排除分支列表中
        exclude_branches = self.config.get('config', {}).get('exclude_branches', [])
        if exclude_branches and branch in exclude_branches:
            print(f"  ℹ️  跳过排除的分支: {branch} ({repo_name})")
            return []
        
        # 获取指定时间范围内的 log
        since_date = self.start_date.strftime('%Y-%m-%dT%H:%M:%S')
        log_format = "%H|%ad|%s"
        command = f'git log --since="{since_date}" --format="{log_format}" --date=iso'
        
        output = self._run_git_command(repo_path, command)
        if not output:
            return []
        
        logs = []
        for line in output.split('\n'):
            if not line.strip():
                continue
            parts = line.split('|', 2)
            if len(parts) == 3:
                commit_hash, date_str, message = parts
                if self._should_include_commit(message):
                    logs.append({
                        'hash': commit_hash[:7],
                        'date': date_str.split(' ')[0],
                        'message': message,
                        'repo': repo_name
                    })
        
        return logs
    
    def _should_include_commit(self, message):
        """判断 commit 是否应该被包含"""
        filters = self.config.get('config', {}).get('commit_filters', [])
        if not filters:
            return True
        
        message_lower = message.lower()
        return any(f.lower() in message_lower for f in filters)
    
    def collect_git_logs(self):
        """收集所有仓库的 git log"""
        print("📊 正在收集 git 提交记录...")
        
        for repo in self.config.get('repositories', []):
            repo_path = repo.get('path', '')
            repo_name = repo.get('name', repo_path)
            
            print(f"  🔍 搜索仓库: {repo_name}")
            logs = self._get_git_log(repo_path, repo_name)
            if logs:
                self.git_logs[repo_name] = logs
                print(f"     找到 {len(logs)} 条相关提交")
            else:
                print(f"     无相关提交")
        
        print()
    
    def _get_status_icon(self, status):
        """获取任务状态图标(已禁用)"""
        return ""
    
    def _extract_keywords(self, task_name):
        """从任务名提取关键词(带权重)"""
        keywords = []
        name = task_name.lower()
        
        # 完整名称(最高权重)
        keywords.append((name, 20))
        
        # 4-6字关键词(高权重)
        for length in range(4, min(7, len(name) + 1)):
            for i in range(len(name) - length + 1):
                keyword = name[i:i+length]
                if any(c.isalpha() or ord(c) > 127 for c in keyword):
                    keywords.append((keyword, 8))
        
        return keywords
    
    def _clean_commit_message(self, message):
        """清理 commit message,去掉 type 前缀"""
        prefixes = ['feat:', 'fix:', 'docs:', 'doc:', 'perf:', 'refactor:',
                    'chore:', 'style:', 'test:', 'build:', 'ci:']
        msg = message.strip()
        for prefix in prefixes:
            if msg.lower().startswith(prefix):
                msg = msg[len(prefix):].strip()
                break
        return msg
    
    def _format_git_logs_by_task(self):
        """将 git log 按任务分组(智能匹配)"""
        task_logs = {}

        for task in self.config.get('tasks', []):
            task_name = task.get('name', '')
            keywords = self._extract_keywords(task_name)
            matched_logs = []

            for repo_name, logs in self.git_logs.items():
                for log in logs:
                    message_lower = log['message'].lower()
                    # 计算匹配得分
                    best_score = 0
                    for keyword, weight in keywords[:10]:
                        if keyword in message_lower:
                            score = weight + len(keyword)
                            best_score = max(best_score, score)
                    
                    # 得分阈值过滤(需要完整名称匹配或长关键词)
                    if best_score >= 10:
                        matched_logs.append((log, best_score))
            
            # 按得分排序
            matched_logs.sort(key=lambda x: x[1], reverse=True)
            matched_logs = [log for log, _ in matched_logs]
            
            if matched_logs:
                task_logs[task['name']] = matched_logs

        return task_logs
    
    def generate_report(self):
        """生成周报"""
        self.collect_git_logs()
        task_logs = self._format_git_logs_by_task()
        
        report = []
        title = self.config.get('config', {}).get('title', '工作周报')
        
        # 标题
        width = 50
        report.append("=" * width)
        report.append(f"{title:^{width - 4}}")
        report.append(f"报告周期: {self.start_date.strftime('%Y-%m-%d')} ~ {self.end_date.strftime('%Y-%m-%d')}")
        report.append("=" * width)
        report.append("")
        
        # 本周完成工作
        report.append("【本周完成工作】")
        report.append("-" * width)

        completed_count = 0
        for task in self.config.get('tasks', []):
            if task.get('status') != 'completed':
                continue
                
            completed_count += 1
            icon = self._get_status_icon(task['status'])
            task_title = f"{icon} {task['name']}".strip()
            report.append(task_title)
            
            # 显示相关的 git 提交消息
            if task['name'] in task_logs and self.config.get('config', {}).get('show_git_details', True):
                for log in task_logs[task['name']]:
                    clean_msg = self._clean_commit_message(log['message'])
                    report.append(f"   - {clean_msg}")
            elif task.get('description'):
                report.append(f"   - {task['description']}")

            report.append("")

        if completed_count == 0:
            report.append("  (无)")
            report.append("")
        
        # 进行中任务
        in_progress_tasks = [t for t in self.config.get('tasks', []) if t.get('status') == 'in_progress']
        if in_progress_tasks:
            report.append("【进行中任务】")
            report.append("-" * width)
            
            for task in in_progress_tasks:
                icon = self._get_status_icon(task['status'])
                progress = task.get('progress', 0)
                task_title = f"{icon} {task['name']} ({progress}%)".strip()
                report.append(task_title)
                
                # 显示相关的 git 提交消息
                if task['name'] in task_logs and self.config.get('config', {}).get('show_git_details', True):
                    for log in task_logs[task['name']]:
                        clean_msg = self._clean_commit_message(log['message'])
                        report.append(f"   - {clean_msg}")
                elif task.get('description'):
                    report.append(f"   - {task['description']}")

                report.append("")
        
        # 下周计划
        planned_tasks = [t for t in self.config.get('tasks', []) if t.get('status') == 'planned']
        if planned_tasks:
            report.append("【下周计划】")
            report.append("-" * width)
            
            for task in planned_tasks:
                icon = self._get_status_icon(task['status'])
                task_title = f"{icon} {task['name']}".strip()
                report.append(task_title)
                if task.get('description'):
                    report.append(f"   {task['description']}")
                report.append("")
        
        # 进度总览
        report.append("【进度总览】")
        report.append("-" * width)
        
        completed = len([t for t in self.config.get('tasks', []) if t.get('status') == 'completed'])
        in_progress = len([t for t in self.config.get('tasks', []) if t.get('status') == 'in_progress'])
        planned = len([t for t in self.config.get('tasks', []) if t.get('status') == 'planned'])
        total = len(self.config.get('tasks', []))
        
        report.append(f"总计: {total} | 完成: {completed} | 进行中: {in_progress} | 计划中: {planned}")
        
        if total > 0:
            overall_progress = sum(
                t.get('progress', 0) if t.get('status') == 'in_progress' 
                else (100 if t.get('status') == 'completed' else 0) 
                for t in self.config.get('tasks', [])
            ) / total
            report.append(f"总体进度: {overall_progress:.1f}%")
        
        report.append("")
        report.append("=" * width)
        
        # 打印报告
        print("\n".join(report))
        return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description='生成工作周报')
    parser.add_argument(
        '--config', '-c',
        type=str,
        default='weekly-config.yaml',
        help='配置文件路径 (默认: weekly-config.yaml)'
    )
    parser.add_argument(
        '--last-days', '-d',
        action='store_true',
        help='使用过去 N 天模式 (默认使用自然周)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='过去 N 天的天数 (默认: 7, 仅在 --last-days 模式下生效)'
    )
    
    args = parser.parse_args()
    
    config_path = Path(args.config)
    if not config_path.is_absolute():
        if not config_path.exists():
            script_dir = Path(__file__).parent
            config_path = script_dir / args.config
    
    use_natural_week = not args.last_days
    generator = WeeklyReportGenerator(config_path, use_natural_week)
    generator.generate_report()


if __name__ == '__main__':
    main()
