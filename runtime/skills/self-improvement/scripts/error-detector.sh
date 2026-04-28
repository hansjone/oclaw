#!/bin/bash
# 自我改进错误检测 Hook
# 在 Bash 的 PostToolUse 触发，用于检测命令失败
# 读取 CLAUDE_TOOL_OUTPUT 环境变量

set -e

# 检查工具输出是否包含错误信号
# CLAUDE_TOOL_OUTPUT 为工具执行结果
OUTPUT="${CLAUDE_TOOL_OUTPUT:-}"

# 错误模式（大小写不敏感匹配）
ERROR_PATTERNS=(
    "error:"
    "Error:"
    "ERROR:"
    "failed"
    "FAILED"
    "command not found"
    "No such file"
    "Permission denied"
    "fatal:"
    "Exception"
    "Traceback"
    "npm ERR!"
    "ModuleNotFoundError"
    "SyntaxError"
    "TypeError"
    "exit code"
    "non-zero"
)

# 检查输出是否匹配任一错误模式
contains_error=false
for pattern in "${ERROR_PATTERNS[@]}"; do
    if [[ "$OUTPUT" == *"$pattern"* ]]; then
        contains_error=true
        break
    fi
done

# 仅在检测到错误时输出提醒
if [ "$contains_error" = true ]; then
    cat << 'EOF'
<error-detected>
检测到命令错误。若满足以下任一条件，请记录到 improvement/errors.md：
- 错误出乎预期或并不直观
- 需要排查才能解决
- 可能在相似场景复发
- 解决方案对后续会话有复用价值

记录时请使用 self-improvement 技能格式：[ERR-YYYYMMDD-XXX]
</error-detected>
EOF
fi
