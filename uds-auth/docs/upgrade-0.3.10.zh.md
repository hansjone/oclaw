# 升级到 0.3.10

本版修复密码并发写入、Desktop 凭据附带范围、Gateway 全局接口遗漏、扫码浏览器绑定、任务授权注入和安全状态迁移。先备份 profile 中的安全状态及密钥，再替换插件并重启 Host；不要删除 roles/owners 文件。

## 登录和 Desktop

应急账号默认启用，账号为 `administrator`、密码为 `Admin@123`；首次登录后请尽快在「账号 / 权限」设置新密码，也可在此关闭应急账号。旧 roles 文件若没有应急账号状态会启用默认账号；显式关闭状态会保留。Local Admin 密封盒解锁保持独立，轮换或关闭应急密码不撤销密封盒会话。

Desktop 只把 bridge 附到 `dsh-app://app` 或 Host 启动时提供的 `__DSH_TRANSPORT__.streamBaseUrl` 对应 authority。启动信息缺失时绝不向其他本机端口外发凭据；需要支持提供这个正式 transport 字段的 DSH 版本。带 bridge 的 fetch 拒绝重定向，保留原 Request headers。一次性 WS ticket 只用于 GET `/api/remote.mux` 的真正 WebSocket upgrade；普通 HTTP、其他路径和重放均无效。构造 WebSocket 仍采用同步 XHR 取票，需真实 Desktop 验证该协议桥。

## 扫码协议变更

`qr-start` 返回 `browserBinding`，浏览器仅在内存中保存，轮询 `qr-proxy` 时通过 `X-UDS-QR-Binding` 发送。该秘密不出现在二维码、URL 或转发给 UAC 的 body 中。服务端固定发送挑战绑定的系统代码并计算 verifyCode。

当前明确支持的 UAC 契约是 outer `code.code=0000`、`bo.code=0000`，凭据来自 `other.account/empNo` 和 `other.token/authValue`；`4002` 保持等待，`1002` 表示过期。成功结果还必须通过严格工号匹配的用户资料校验。服务端在异步校验前原子预留成功兑换，直接返回 `auth` 本地会话；前端不再保存 SSO cookie，也不再依次调用 user-info 和 bridge/bind。无法识别的响应拒绝登录，不返回上游原文。外部 QR 客户端须同步适配此变更；真实 UAC 响应仍需现场核验。

## Skill、cron 和后台 shell

Host 加载 `shellEnv` 时自动注册 uds-auth contributor。每次 shell 执行根据真实 `execution.agent.session.header.id` 和服务端 owner 签发 capability，默认只有 `outbound` scope；仅当管理员显式开启 `allowRawAgentToken` 时增加 `credentials` scope，以供受信 skill 调用 `/agent-credentials`。默认 10 分钟，注入受保护的 `DSH_UDS_TASK_CAPABILITY` / `DSH_UDS_AUTH_BASE`。Python helper 优先读取这两个变量；兼容的手工 `UDS_TASK_CAPABILITY` / `UDS_AUTH_BASE` 仅在没有 Host 管理变量时使用。所有 base，包括旧 `DSH_WEB_URL`，都必须是 loopback HTTP(S)。不再猜测 8787 端口，也不允许 remote override 携带凭据。

普通执行结束或取消即撤销。官方 shell 交给 jobs 的 background/promoted 执行绑定该 job，停止、结算、移除或 TTL 到期撤销；不跨任务复用。账号停用、owner 改变和 scope 不符均拒绝代理调用。长于 10 分钟的后台进程不能自动续期；应拆为新的受控调用。前台/后台都不会向 shell 注入 UAC 原始 token。需要 raw credentials 的受信 Host 调用必须显式申请 scope，且仍受 `allowRawAgentToken` 开关控制。

配套 `dsh-ops-cron` 已把 owner 校验和盖章前移到 agents.create/followup 之前，使用 uds-auth 时 owner 缺失/停用/冲突会拒绝执行。单独无 uds-auth 的 cron 使用方式保持可用。请同时部署本次 cron 变更。

## Gateway、持久化与权限

统一 Gateway 检查覆盖实际 `prepareInvocation` 路径：包括 unary、HTTP RPC 和 WS stream；每帧复核会话有效性、账号状态及 owner。现有资源接口继续调用各自 ACL；带 agent/workspaceFileScope/sessionId 的接口校验目标会话；其余全局接口默认要求管理员（包括账户、插件管理和未知新接口）。session/control baseline 和增量按可见会话投影。普通用户需要新增全局功能时，应先审查接口，再显式加入策略。

Gateway 内置 `$events` 同样校验登录和每帧有效性，按 owner 过滤会话事件、goal、Agent 审批和问答；普通用户只接收显式允许的公共目录变更，其他全局事件要求管理员。`$events/result` 必须来自创建该事件流的同一个本地登录 session，且仍能访问目标 Agent，避免跨用户代答审批。

该统一检查依赖当前 DSH `0.2.0-rc.2` 的 Gateway 内部方法；不兼容时拒绝加载，不能静默略过。升级 Host 前须重跑真实 Loader/Gateway 集成检查和完整 inventory。

roles 全部运行时写入串行化，未提交的权限不对读者生效。密码 generation 落盘并在重启时恢复；失败事务恢复角色、状态、偏好及口令，不让后台计时器写回失败状态。运行时 scrypt 使用异步线程池，最多 2 个并发、8 个等待，超载返回错误。

迁移使用排他复制、不覆盖冲突状态；相同的中断副本可继续，失败清理本次已创建且仍与源相同的文件，成功 marker 原子落盘。原子写入失败清理临时文件。

Unix profile 目录/文件为 0700/0600。Windows profile 及已知安全状态文件 DACL 仅允许当前 Host 账号和 SYSTEM，关闭继承，并实际读取 ACL 验证；失败拒绝初始化。服务账号部署须使用该账号执行初始化；换账号前由授权运维迁移所有权和 ACL。此机制不限制管理员提升权限后的访问。临时目录 DACL 测试不等于完整的第二个 Windows 普通账号读取测试。

## 交付检查

仓库提供 `npm test`（自然退出）、`npm run pack:check`、`npm run sbom`；CI 覆盖 Windows/Linux、Node 22.19/24、重建二维码、包检查及含开发依赖的 npm audit。`docs/sbom.cdx.json` 精确记录实际 bundled qrcode/dijkstrajs 和源文件哈希；`THIRD-PARTY-NOTICES.txt` 保留其许可证。DSH/React/Electron 属于 Host 的独立供应链，须结合正式 Host SBOM 检查。CI 配置落地不代表远端任务已经运行。
