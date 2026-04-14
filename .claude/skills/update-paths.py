#!/usr/bin/env python3
"""批量更新 WorkFlowSkills 的 SKILL.md 路径配置"""
import re
from pathlib import Path

SKILLS_DIR = Path("E:/ldmnq_project/selfp/WorkFlowSkills/.claude/skills")

REPLACEMENTS = [
    (r'_R=".*git worktree list.*"', 'SHARED_BIN=$(bash android-resolve-path 2>/dev/null || true)'),
    (r'SHARED_BIN="\$_R/\.claude/skills/android-shared/bin"', '# SHARED_BIN resolved dynamically'),
    (r'\[ ! -d "\$SHARED_BIN" \] && SHARED_BIN="\$HOME/\.claude/skills/android-shared/bin"', '# fallback handled'),
    (r'bash "\$SHARED_BIN/', 'bash "$SHARED_BIN/bin/'),
]

for skill_dir in SKILLS_DIR.iterdir():
    if not skill_dir.is_dir() or not skill_dir.name.startswith('android-'):
        continue
    
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.exists():
        continue
    
    content = skill_file.read_text(encoding='utf-8')
    original = content
    
    for pattern, replacement in REPLACEMENTS:
        content = re.sub(pattern, replacement, content)
    
    if content != original:
        skill_file.write_text(content, encoding='utf-8')
        print(f"✓ Updated: {skill_dir.name}")
    else:
        print(f"- Skipped: {skill_dir.name}")

print("\nDone!")
