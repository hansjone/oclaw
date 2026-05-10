#!/bin/bash
# Skill Extraction Helper
# Creates a new skill from a learning entry
# 用法: ./extract-skill.sh <skill-name> [--dry-run]

set -e

# Configuration
SKILLS_DIR="./skills"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

usage() {
    cat << EOF
用法: $(basename "$0") <skill-name> [options]

根据学习条目创建新技能。

参数:
  skill-name     技能名称（小写，空格使用连字符）

选项:
  --dry-run      仅预览将创建的内容，不落盘
  --output-dir   当前路径下的相对输出目录（默认: ./skills）
  -h, --help     显示帮助信息

示例:
  $(basename "$0") docker-m1-fixes
  $(basename "$0") api-timeout-patterns --dry-run
  $(basename "$0") pnpm-setup --output-dir ./skills/custom

技能将创建在: \$SKILLS_DIR/<skill-name>/
EOF
}

log_info() {
    echo -e "${GREEN}[信息]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[警告]${NC} $1"
}

log_error() {
    echo -e "${RED}[错误]${NC} $1" >&2
}

# Parse arguments
SKILL_NAME=""
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --output-dir)
            if [ -z "${2:-}" ] || [[ "${2:-}" == -* ]]; then
            log_error "--output-dir 需要提供相对路径参数"
                usage
                exit 1
            fi
            SKILLS_DIR="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            log_error "未知选项: $1"
            usage
            exit 1
            ;;
        *)
            if [ -z "$SKILL_NAME" ]; then
                SKILL_NAME="$1"
            else
                log_error "意外参数: $1"
                usage
                exit 1
            fi
            shift
            ;;
    esac
done

# Validate skill name
if [ -z "$SKILL_NAME" ]; then
    log_error "必须提供技能名称"
    usage
    exit 1
fi

# Validate skill name format (lowercase, hyphens, no spaces)
if ! [[ "$SKILL_NAME" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
    log_error "技能名称格式无效。仅允许小写字母、数字和连字符。"
    log_error "示例: 'docker-fixes', 'api-patterns', 'pnpm-setup'"
    exit 1
fi

# Validate output path to avoid writes outside current workspace.
if [[ "$SKILLS_DIR" = /* ]]; then
    log_error "输出目录必须是当前目录下的相对路径。"
    exit 1
fi

if [[ "$SKILLS_DIR" =~ (^|/)\.\.(/|$) ]]; then
    log_error "输出目录不能包含 '..' 路径段。"
    exit 1
fi

SKILLS_DIR="${SKILLS_DIR#./}"
SKILLS_DIR="./$SKILLS_DIR"

SKILL_PATH="$SKILLS_DIR/$SKILL_NAME"

# Check if skill already exists
if [ -d "$SKILL_PATH" ] && [ "$DRY_RUN" = false ]; then
    log_error "技能已存在: $SKILL_PATH"
    log_error "请更换名称或先删除已有技能目录。"
    exit 1
fi

# Dry run output
if [ "$DRY_RUN" = true ]; then
    log_info "预览模式 - 将会创建："
    echo "  $SKILL_PATH/"
    echo "  $SKILL_PATH/SKILL.md"
    echo ""
    echo "模板内容预览："
    echo "---"
    cat << TEMPLATE
name: $SKILL_NAME
description: "[TODO: 用一句话说明技能作用与触发场景]"
---

# $(echo "$SKILL_NAME" | sed 's/-/ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) tolower(substr($i,2))}1')

[TODO: 简要说明技能目的]

## Quick Reference

| Situation | Action |
|-----------|--------|
| [触发条件] | [执行动作] |

## Usage

[TODO: 详细使用说明]

## Examples

[TODO: 补充具体示例]

## Source Learning

本技能由学习条目提炼生成。
- Learning ID: [TODO: 填写原始学习条目 ID]
- Original File: improvement/learnings.md
TEMPLATE
    echo "---"
    exit 0
fi

# Create skill directory structure
log_info "正在创建技能: $SKILL_NAME"

mkdir -p "$SKILL_PATH"

# Create SKILL.md from template
cat > "$SKILL_PATH/SKILL.md" << TEMPLATE
---
name: $SKILL_NAME
description: "[TODO: 用一句话说明技能作用与触发场景]"
---

# $(echo "$SKILL_NAME" | sed 's/-/ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) tolower(substr($i,2))}1')

[TODO: 简要说明技能目的]

## Quick Reference

| Situation | Action |
|-----------|--------|
| [触发条件] | [执行动作] |

## Usage

[TODO: 详细使用说明]

## Examples

[TODO: 补充具体示例]

## Source Learning

本技能由学习条目提炼生成。
- Learning ID: [TODO: 填写原始学习条目 ID]
- Original File: improvement/learnings.md
TEMPLATE

log_info "已创建: $SKILL_PATH/SKILL.md"

# Suggest next steps
echo ""
log_info "技能脚手架创建成功！"
echo ""
echo "下一步建议："
echo "  1. 编辑 $SKILL_PATH/SKILL.md"
echo "  2. 用你的学习内容填写 TODO 区块"
echo "  3. 若有详细文档，新增 references/ 目录"
echo "  4. 若有可执行脚本，新增 scripts/ 目录"
echo "  5. 在原学习条目中更新："
echo "     **Status**: promoted_to_skill"
echo "     **Skill-Path**: skills/$SKILL_NAME"
