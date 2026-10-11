# 0.3.11：原版 Desktop 启动兼容修复

无需修改、重新打包或替换 DSH。修复全部在 uds-auth npm 包内。

0.3.10 的 Gateway 默认权限策略阻止了 Desktop 原生欢迎页在 UDS 登录前读取 `settings/describe`，宿主将业务拒绝当作启动失败，显示 `desktop welcome: Web RPC failed`。

0.3.11 对四个已有的、非流式 RPC 提供最小启动投影：

- `settings/describe`：仅语言偏好和虚拟启动命名空间，声明不可写且无本地文档。
- `llm/listConfigurableProviders`：仅虚拟启动条目，不枚举实际供应商配置。
- `credentials/describe`：仅接受固定虚拟引用 `UDS_AUTH_DESKTOP_PROVIDER_CONFIGURED`，返回“是否配置过供应商密钥”的合并布尔值，永远不可写。其他引用拒绝。
- `account/getState`：仅 Host 平台凭据是否存在的状态，登录尝试为 null，链接固定为公开平台页面。

这些投影不构造 UDS 身份，不赋予角色，不开放设置写入、凭据读写、会话或 WS 流。经过登录的管理员和可信 Host 调用仍获得原始权限对应的结果；普通用户只有投影，已撤销的登录身份仍拒绝。

如果 Host 还没有任何供应商凭据，原版 Desktop 可能仍显示自身的欢迎页；点击 Skip/跳过进入工作区后由 UDS 登录界面接管。原生欢迎页的账户登录和密钥写入仍须管理权限；请通过 UDS 管理员登录后的设置配置供应商。

安装 0.3.11 后重启 Desktop。请保持 0.3.10 的安全配置和角色数据，不要通过停用 uds-auth 或放行整个设置命名空间绕过此问题。
