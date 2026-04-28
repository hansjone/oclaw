---
name: session-bootstrap
description: 在智能体启动时注入会话唤醒上下文
metadata: {"oclaw":{"emoji":"🧭","events":["agent:bootstrap"]}}
---

# 会话唤醒 Hook

在 `agent:bootstrap` 事件触发时，注入一个虚拟 `SESSION_BOOTSTRAP.md` 文件，内容包含：

- 身份与行为参考（`SOUL.md`、`IDENTITY.md`）
- 最近会话记忆摘要
- 最新 Wiki 改进信号
- 一句话连续性欢迎语
