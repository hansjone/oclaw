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
3. 应遵循什么共享行为准则（Wiki `core/*.md`）
4. 当前专家的角色规则（Wiki `experts/<role>/*.md`，如存在）
5. 最近学到了什么（Wiki `improvement/*.md`）
6. 现在该如何衔接（简短唤醒摘要）

## 必须遵循的读取顺序

启用本技能时，严格按以下顺序：

1. 读取 `SOUL.md`
2. 读取 `IDENTITY.md`
3. 读取 `memory/` 下最新文件
4. 读取 Wiki 行为准则（按文件名排序）：
   - `core/*.md`（示例：`core/principles.md`、`core/behavior.md`）
5. 读取 Wiki 角色规则（按当前专家角色，若目录存在）：
   - `experts/<role>/*.md`（示例：`experts/generalist/style.md`）
6. 读取 Wiki 改进记录：
   - `improvement/learnings.md`
   - `improvement/errors.md`
   - `improvement/feature-requests.md`
7. 在深入任务前先输出一句连续性衔接语

## 连续性衔接语格式

使用固定句式：

`欢迎回来，[开发者]。上次我们聊了[主题]，我学到了[知识点]。`

若字段缺失，保留句式并使用保守占位词。

## 自动记忆规则

当当前轮次出现稳定且可复用事实时：

- 使用 Wiki 工具持久化（`memory_wiki_apply`）
- 使用 `memory_wiki_lint` 校验质量

在高置信度且明显可复用时，不必等待显式“记住这条”指令。

## 开源扩展约定（供他人新增）

- 将长期行为规则放在 `data/wiki/core/`，每个主题一个 `.md` 文件。
- 命名建议小写短横线，例如：`principles.md`、`tone-style.md`、`safety-boundary.md`。
- `session-bootstrap` 会自动读取 `core/*.md` 并注入启动上下文，无需改代码。
- 如需专家个性化规则，放在 `data/wiki/experts/<role>/`（如 `experts/ops/`、`experts/generalist/`）。
- 建议每个文件保持“原则 + 可执行规则 + 更新条件”三段结构，便于复用与审阅。

## 附加资源

- 核心身份与行为准则：[SOUL.md](SOUL.md)
- 关系定位与使命：[IDENTITY.md](IDENTITY.md)

## 当前状态（已打通）

`session-bootstrap` 已接入 Oclaw hooks 运行链路，可在会话启动时自动生效：

- 事件：`agent:bootstrap`
- Hook 名称：`session-bootstrap`
- 加载状态：`enabled_by_config=true`、`eligible=true`、`loadable=true`

## 生效流程（端到端）

1. 启动时，hooks 发现器会扫描技能目录下的 `hooks` 子目录。
2. 读取 `hooks/runtime/HOOK.md`，注册 `agent:bootstrap` 事件到 `handler.py`。
3. 会话进入 bootstrap 阶段后触发事件，执行 `handle(event)`。
4. `handler.py` 生成虚拟文件 `SESSION_BOOTSTRAP.md`，写入 `event.context.bootstrapFiles`。
5. 主控在启动上下文中读取该虚拟文件，完成身份唤醒与记忆衔接。

## 自检方式

可用以下命令检查是否处于可加载状态：

`python -m oclaw.runtime.operations hooks info session-bootstrap --workspace "." --json`
