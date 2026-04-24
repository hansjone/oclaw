# WhatsApp 扩展（中文重写）

对应上游目录：`vendor/oclaw/extensions/whatsapp`

## 能力定位
- 作为 Oclaw 渠道插件接入 WhatsApp。
- 负责账号接入、消息目标标准化、群/目录策略、命令策略和运行时辅助能力。

## 关键入口
- `api.ts`：对外导出主要能力与工具函数（channel 插件、策略、target 规范化等）。
- `oclaw.plugin.json`：插件元信息（`id=whatsapp`，渠道声明、配置 schema）。
- `oclaw/`：具体实现（收发链路、访问控制、配置解析、运行时逻辑）。

## API 文件清单（根目录）
- `action-runtime-api.ts`
- `channel-config-api.ts`
- `channel-plugin-api.ts`
- `config-api.ts`
- `contract-api.ts`
- `directory-contract-api.ts`
- `doctor-contract-api.ts`
- `legacy-session-surface-api.ts`
- `legacy-state-migrations-api.ts`
- `light-runtime-api.ts`
- `login-qr-api.ts`
- `outbound-payload-test-api.ts`
- `runtime-api.ts`
- `secret-contract-api.ts`
- `security-contract-api.ts`
- `setup-plugin-api.ts`
- `test-api.ts`

## 运行关注点
- 群聊与私聊 target 的标准化与合法性判断。
- allowlist / group policy 等访问控制策略是否命中。
- 登录态与二维码链路是否稳定。
