# Webhooks 扩展（中文重写）

对应上游目录：`vendor/openclaw/extensions/webhooks`

## 能力定位
- 提供“认证后的入站 webhook”，把外部自动化请求绑定到 OpenClaw TaskFlow。
- 支持多 route 配置，每个 route 对应 path/session/secret/controller。

## 关键入口
- `openclaw.plugin.json`：声明插件 `id=webhooks` 及配置 schema。
- `index.ts`：读取 routes 配置并注册 HTTP 路由。
- `api.ts`：导出插件 SDK 类型入口。
- `runtime-api.ts`：运行时相关公共接口。

## 配置核心（来自 schema）
- `routes.<routeId>.enabled`：是否启用。
- `routes.<routeId>.path`：Webhook 路径。
- `routes.<routeId>.sessionKey`：绑定会话键。
- `routes.<routeId>.secret`：密钥（字符串或 secretRef）。
- `routes.<routeId>.controllerId`：默认控制器标识。
- `routes.<routeId>.description`：可选说明。

## secret 支持类型
- 直接字符串密钥。
- `secretRef` 对象：`source`（env/file/exec）+ `provider` + `id`。

## 运行关注点
- 路由是否注册成功并与 `sessionKey` 对齐。
- secret 解析是否正确（配置路径与 provider 可用性）。
- 外部系统调用失败时的日志可观测性（routeId/path/sessionKey）。
