---
name: session-bootstrap
description: 在新会话开始时自动完成身份唤醒、近期记忆加载与 Wiki 知识回填。适用于会话启动、用户要求连续性、或回答前需要恢复项目/用户上下文的场景。
---

# 会话唤醒

本技能用于让新会话具备连续性，避免“从零开始”。

## 目标

在会话开始时，先重建最小可用上下文，再进入正常执行：

1. 我是谁、应如何行动（`SOUL.md`、`IDENTITY.md`）
2. 最近发生了什么（`memory/` 最新记录）
3. 最近学到了什么（Wiki `improvement/*.md`）
4. 现在该如何衔接（简短唤醒摘要）

## 必须遵循的读取顺序

启用本技能时，严格按以下顺序：

1. 读取 `SOUL.md`
2. 读取 `IDENTITY.md`
3. 读取 `memory/` 下最新文件
4. 读取 Wiki 改进记录：
   - `improvement/learnings.md`
   - `improvement/errors.md`
   - `improvement/feature-requests.md`
5. 在深入任务前先输出一句连续性衔接语

## 连续性衔接语格式

使用固定句式：

`欢迎回来，[开发者]。上次我们聊了[主题]，我学到了[知识点]。`

若字段缺失，保留句式并使用保守占位词。

## 自动记忆规则

当当前轮次出现稳定且可复用事实时：

- 使用 Wiki 工具持久化（`memory_wiki_apply`）
- 使用 `memory_wiki_lint` 校验质量

在高置信度且明显可复用时，不必等待显式“记住这条”指令。

## 附加资源

- 核心身份与行为准则：[SOUL.md](SOUL.md)
- 关系定位与使命：[IDENTITY.md](IDENTITY.md)
