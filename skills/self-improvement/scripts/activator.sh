#!/bin/bash
# 自我改进激活 Hook
# 在 UserPromptSubmit 触发，用于提醒记录学习沉淀
# 输出保持精简（约 50-100 tokens）以降低上下文负担

set -e

# 以系统上下文形式输出提醒
cat << 'EOF'
<self-improvement-reminder>
本任务完成后，请判断是否产出可沉淀知识：
- 是否通过排查得到非显而易见的解法？
- 是否形成了异常行为的可复用绕过方案？
- 是否识别出项目特有模式？
- 是否有需要调试才能解决的错误？

若是，请写入 Wiki：
- improvement/learnings.md
- improvement/errors.md
- improvement/feature-requests.md
若价值较高（复发、可广泛复用），请考虑提炼为独立技能。
</self-improvement-reminder>
EOF
