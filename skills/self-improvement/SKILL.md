# self-improvement — 自我改进 (Self-Improvement)

> 将纠错、错误与能力缺口写入 Wiki 以持续改进，形成"犯错→记录→不再犯"的闭环。
> 本技能完全基于 `memory_wiki_*` 工具，不依赖本地文件或外部脚本。

---

## 触发条件 (Triggers)

出现以下情况时启用：

1. 命令或操作出现非预期失败
2. 用户对回答进行纠正
3. 用户提出缺失能力需求
4. 同类问题再次复发
5. 发现更优且可复用的方法
6. 每轮对话结束时（强制三问反思）

## 必要流程 (Required Workflow)

```
1. memory_wiki_search → 检索 improvement/* 看是否已有记录
2. memory_wiki_get   → 读取目标文件上下文
3. memory_wiki_apply → 追加结构化条目 (action=append)
4. memory_wiki_lint  → 质量检查
5. lint 报错 → 立即修复
```

## 条目路由 (Entry Routing)

| 内容类型 | 目标文件 | 示例 |
|---------|---------|------|
| 纠错/洞见/最佳实践 | `improvement/learnings.md` | 用户纠正了某个认知错误 |
| 运行时/工具/API 失败 | `improvement/errors.md` | 某个工具调用报错 |
| 能力缺口/功能请求 | `improvement/feature-requests.md` | 用户问"你能做 X 吗？" |
| 长篇经验沉淀 (>300 字) | `improvement/learnings/<topic>.md` | 一次完整的技能安装流程 |

## 条目模板 (Entry Template)

```markdown
## [ID] 标题 (Title)
**Logged**: ISO-8601 时间戳 (Timestamp)
**Priority**: low | medium | high | critical
**Status**: pending | resolved | promoted_to_skill
**Area**: frontend | backend | infra | tests | docs | config

### 摘要 (Summary)
一句话摘要。

### 详情 (Details)
发生了什么、为什么重要、可执行改进建议。

### 元数据 (Metadata)
- Source: conversation | error | user_feedback | reflection
- Related Files: path/to/file.ext
- See Also: <optional-id>
```

### ID 格式 (ID Format)

- Learning: `LRN-YYYYMMDD-XXX`
- Error: `ERR-YYYYMMDD-XXX`
- Feature request: `FEAT-YYYYMMDD-XXX`

XXX = 当天序号，从 001 开始。

## 提升路径 (Promotion Path)

当某个条目被验证有广泛复用价值时：

| 到达条件 | 提升目标 |
|---------|---------|
| 可用作行为约定 | `core/principles.md` |
| 可用作维护规则 | `core/maintenance.md` |
| 可提炼为独立技能 | 使用 `skill-creator` 创建新技能 |
| 某个工具易错点 | 标注在 SKILL.md 或 REFERENCES.md |

## 会话结束三问 (End-of-Session Reflection)

每轮对话结束前执行：

1. **学到了什么？** → `improvement/learnings.md`
2. **有什么可优化？** → `improvement/feature-requests.md` 或 `core/principles.md`
3. **用户画像有更新吗？** → `users/current.md`

## 安全规则 (Security Rules)

- 不记录密钥、令牌、凭据或原始敏感信息
- 敏感输出使用脱敏摘要，不保留完整原文
- 未验证事实不得当作已确认规则持久化
- 涉及用户偏好写入时需有明确的对话证据，不推测
