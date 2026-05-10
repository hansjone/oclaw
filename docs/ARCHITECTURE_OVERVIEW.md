# 架构总览（当前真相）

本文件用于描述当前仓库分层与目录职责，避免迁移后“认知滞后”。

## 顶层目录职责

- `runtime/`：运行时主域（agent、gateway 执行流、skills/hooks/extensions、operations）。
- `interfaces/`：对外接口层（HTTP、WS、Admin、Gateway method bridge）。
- `platform/`：通用平台能力（配置、存储、LLM transport、文件层）。
- `runtime/workspaces/_system/`：内置系统提示词 Markdown 树（原顶层 `prompts/`，与按角色分区的 `workspaces/<role>/` 并列）；`runtime/prompt_templates/` 为加载与 frontmatter 解析。
- `tests/`：测试代码（按你的要求保持顶层）。
- `docs/`：设计文档、运维说明、迁移记录。

## runtime 内部建议边界

- `runtime/core/`：可复用执行内核（如 agent 执行管线聚合入口）。
- `runtime/app/`：应用侧入口组织（面向外部流程的 runtime 编排）。
- `runtime/agents|chat|orchestration|workers`：领域能力模块。
- `skills/`、`runtime/hooks`、`runtime/extensions`：可扩展能力载体（技能包在仓库根 `skills/`）。
- `runtime/operations/scripts`：运维脚本与生成器。

## 路径规范

- 运行时资源路径统一通过 `platform/config/runtime_paths.py` 获取。
- 禁止新增硬编码目录字符串（如直接拼 `oclaw/runtime/...`）。

## 依赖方向（原则）

- `interfaces -> runtime -> platform`（尽量单向）。
- `runtime` 不反向依赖 `interfaces`（必要时通过协议/回调解耦）。
- `docs/tests` 可依赖任意层，但不应反向影响运行时代码设计。

