---
name: self-improvement
description: 将纠错、错误与能力缺口写入 Wiki 以持续改进。适用于操作失败、用户反馈纠正、问题复发、或需要沉淀并推动的新能力需求场景。
metadata:
---

# 自我改进（仅 Wiki）

本技能仅使用 Wiki，不使用本地 `.learnings/` 文件。

## 存储路径

- `improvement/learnings.md`
- `improvement/errors.md`
- `improvement/feature-requests.md`

## 触发条件

出现以下情况时启用本技能：

1. 命令或操作出现非预期失败。
2. 用户对错误回答进行纠正。
3. 用户提出缺失能力需求。
4. 同类问题再次复发。
5. 发现更优且可复用的方法。

## 必要流程

每次触发都执行以下流程：

1. 用 `memory_wiki_search` 检索历史相关记录。
2. 用 `memory_wiki_get` 读取目标文件上下文。
3. 用 `memory_wiki_apply`（`action=append`）追加结构化条目。
4. 对目标文件执行 `memory_wiki_lint`。
5. 若 lint 报错，立即用 `memory_wiki_apply` 修复。

## 条目路由

- 纠错 / 洞见 / 最佳实践 -> `improvement/learnings.md`
- 运行时 / 工具 / API 失败 -> `improvement/errors.md`
- 能力请求 / 缺失功能 -> `improvement/feature-requests.md`

## 条目模板

```markdown
## [ID] <标题>
**Logged**: ISO-8601 时间戳
**Priority**: low | medium | high | critical
**Status**: pending
**Area**: frontend | backend | infra | tests | docs | config

### Summary
一句话摘要。

### Details
发生了什么、为什么重要、可执行改进建议。

### Metadata
- Source: conversation | error | user_feedback
- Related Files: path/to/file.ext
- See Also: <optional-id>
```

ID 格式：

- Learning: `LRN-YYYYMMDD-XXX`
- Error: `ERR-YYYYMMDD-XXX`
- Feature request: `FEAT-YYYYMMDD-XXX`

## 提升目标

当条目已具备广泛复用价值时，将精炼规则提升到：

- `AGENTS.md`（工作流模式）
- `SOUL.md`（行为模式）
- `TOOLS.md`（工具易错点）
- `.github/copilot-instructions.md`（共享编码约定）

## 安全规则

- 不记录密钥、令牌、凭据或原始敏感信息。
- 敏感输出使用脱敏摘要，不保留完整原文。
- 未验证事实不得当作已确认规则持久化。
