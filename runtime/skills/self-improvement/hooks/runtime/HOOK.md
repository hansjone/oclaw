---
name: self-improvement
description: "在智能体启动阶段注入自我改进提醒"
metadata: {"oclaw":{"emoji":"🧠","events":["agent:bootstrap"]}}
---

# 自我改进 Hook

在 `agent:bootstrap` 阶段注入“学习沉淀提醒”。

## 功能说明

- 在 `agent:bootstrap` 触发（工作区文件注入前）
- 注入提醒块，引导将学习写入 Wiki 路径
- 提示智能体记录纠错、错误与新发现

## 配置方式

无需额外配置，启用命令：

```bash
oclaw hooks enable self-improvement
```
