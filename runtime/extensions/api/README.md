# API 总览（extensions）

本文是 `vendor/oclaw/extensions` 的 API 视角重写，中文优先。

## extension API 是什么
- 每个 extension 是一个插件单元，通常通过 `oclaw.plugin.json` 声明 `id`、`name`、`configSchema`。
- 代码入口一般通过 `index.ts` 注册插件行为（如路由注册、事件处理、任务绑定）。
- `api.ts` 常用于统一导出插件 SDK 类型或对外公开接口。

## 统一接入链路
1. 读取插件配置（含 schema 校验）。
2. 插件注册阶段挂载能力（HTTP 路由、channel 能力、provider 能力等）。
3. 运行时把入站事件转换为 TaskFlow 或 channel 消息处理。
4. 输出日志、错误码、可观测事件用于排障。

## 当前重点扩展
- `whatsapp`：渠道接入、目标规范化、目录/群策略、登录二维码等。
- `webhooks`：认证入站 webhook，绑定到指定会话 TaskFlow。

## 维护建议
- 业务侧只改本目录说明，不直接改 vendor 源码。
- 真正改行为时，先在主工程实现适配层，再决定是否回写上游。
