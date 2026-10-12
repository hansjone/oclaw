# uds-auth

0.3.10: [升级与协议变更说明](docs/upgrade-0.3.10.zh.md) · [SBOM](docs/sbom.cdx.json) · [第三方许可证](docs/THIRD-PARTY-NOTICES.txt)

DeepSeek Harness 的 UDS 统一认证插件（**受信任单实例**访问控制增强，**不支持**互不信任多租户 / 任意代码执行隔离）。

当前包版本见 `package.json`（0.3.x 起为安全协议破坏性变更：须重新登录）。

## 支持范围

| 项 | 说明 |
|----|------|
| 运行时 | Node `^22.19.0 \|\| >=24`（与 DSH Host engines 对齐） |
| 部署 | 单 Host、受信任企业用户、受控 skill |
| 不支持 | 不可信多租户、用户自上传任意代码的强隔离、多实例未共享 session store 时的会话一致性 |

## 安装

```bash
# 开发树
dsh plugin --profile web add -w "<绝对路径>/oclaw/uds-auth"

# 或干净 tgz
dsh plugin add -w "<绝对路径>/uds-auth-0.3.9.tgz"
```

首次空角色表须设置初始超管：环境变量 `UDS_AUTH_INITIAL_ADMIN=<工号>` 或配置 `initialAdminEmpNo`。

安装后重启 Harness。登录徽章在 `shell.overlay`；用户管理在 **设置 → UDS 认证**。

`ctx.get('udsAuth').runAsHost(callback)`：Host 后台上下文。`mintTaskCapability({ empNo, dshSessionId, scopes, ttlSeconds })` 为 cron/skill 签发短期能力令牌（注入 `UDS_TASK_CAPABILITY`）。

## 配置

```yaml
uacBaseUrl: https://uac.zte.com.cn   # 启动/合并时强制 HTTPS
userSearchUrl: https://icenterapi.zte.com.cn/...
loginSystemCode: '100000455558'
initialAdminEmpNo: ''          # 或环境变量 UDS_AUTH_INITIAL_ADMIN
allowOpenRegistration: true    # false 时禁止未知用户自动注册
allowRawAgentToken: false      # 原始 agent-credentials 默认关闭
outboundAllowedHosts: icenterapi.zte.com.cn,icentermsg.dt.zte.com.cn
trustedHosts: ''               # 精确 Host 白名单；空=仅 loopback Host
retainSkillCredentialsOnLogout: true
skillCredentialTtlSeconds: 604800
```

状态文件默认在 `~/.uds-auth/`（roles / owners / credentials / bridge / sessions / `config.runtime.json`）。可用环境变量 `UDS_AUTH_DATA_DIR` 覆盖。从安装目录升级时，若新数据目录为空且安装根仍有旧 `roles.json` 等，启动会一次性迁移（幂等、不覆盖已有目标文件）。公网或反代必须配置 `trustedHosts`。默认目录为**用户级**共享路径，不是按 DSH profile 隔离；单实例部署须知悉该边界。

安全开关经设置保存后**立即生效**（无需重启）。空 `outboundAllowedHosts` 表示拒绝全部出站。

## 会话

- **有效期**：30 分钟无操作过期，有操作自动续期；从登录起最长 7 天。Desktop 的 bridge 令牌随会话一起续期。
- **重启不掉线**：默认内存会话会写入 `~/.uds-auth/sessions.json`，Host / Harness 重启后自动恢复（应急账号没有 SSO 自动重登，尤其依赖这一点）。
  - 文件只保存会话令牌的 SHA-256 哈希，不保存令牌本身；用户信息（可能含 UAC token）用插件密钥 `.uds-auth-secret-key` 做 AES-256-GCM 加密。
  - 加载时丢弃已过期、解密失败或被篡改的记录；停用账号、应急口令轮换等检查仍在每次请求时执行。
  - **删除 `sessions.json` 并重启 = 让所有人重新登录**。密钥文件丢失时会话不再持久化（不影响插件启动）。
- 配置 Redis 会话存储时不使用该文件。

## 管理员与应急

- **三类管理员同权**（`super_admin` / `admin` / `fallback_admin`）：用户管理、设置、建工作区；标签不是更强隔离。
- **应急账号默认开启**：账号 `administrator`，密码 `Admin@123`。首次登录后建议立即在设置中修改；管理员也可关闭该账号。旧 roles 文件未记录应急账号状态时会启用此默认账号；已明确关闭的状态会保留。历史 `Admin@123` SHA-256 hash 会迁移为 scrypt hash。
- **本机密钥解锁**：`node scripts/seal-local-admin.mjs`（交互输入，勿把口令放 argv）→ 设置 `UDS_AUTH_LOCAL_ADMIN_BOX` → 登录面板解密。
- **停用账号**：删除用户默认写入 disabled 状态，不会因开放注册自动复活。

## Skill / cron

1. 标准说明：`docs/skill-auth-standard.zh.md`、`docs/uds-skill-auth.zh.md`
2. Python helper：`skill-helpers/python/uds_skill_auth.py`（与 `skills/...` 同源）
3. 推荐：Host 在任务创建时 `mintTaskCapability`，注入 `UDS_TASK_CAPABILITY` + `DSH_SESSION_ID`，调用 `outbound`；不要依赖浏览器长会话。
4. `resolve(apply_env_aliases=False)` 默认不写环境变量。

## DSH 兼容性

已在 **DeepSeek Harness Desktop 0.2.0-rc.2** 上验证。插件依赖以下 DSH 内部行为（非公开 API），升级 DSH 后请先跑 `npm test` 并实机检查登录、工作区、设置 → 模型：

- Gateway 的 `prepareInvocation` / `resolveDescriptor` / `openRemoteEvents` / `receiveRemoteEventResult`（缺失时插件拒绝启动 ACL，不会静默放行）；
- 客户端 `connection/reset` 事件（登录后用它让设置缓存等重新读取）；
- 端点名 `workspace/follow`、`workspace/initializeDefault`，以及 Desktop 欢迎页使用的 `settings/describe`、`llm/listConfigurableProviders`、`credentials/describe`、`account/getState`。

Desktop 启动时连接会先以匿名身份建立，登录后再重连。插件对此的处理：
- 匿名的数据流请求（如账号状态）挂起等待，不返回错误（否则 DSH 会把账号永久标记为失败，弹出「登录失败 / 添加 API Key」）；
- 匿名的工作区订阅返回空列表，匿名的「创建默认工作区」返回空结果（不报「无法创建默认工作区」，也不会真的创建）；
- Gateway ACL 尚未就绪时，`/api/*` 请求最多等待 15 秒，而不是直接 403。

## 升级注意

- 旧 USER/UI Cookie、旧 bridge 失效，须重新扫码/登录。
- 回滚到 0.2.x **不能**作为安全方案。
- `npm run pack:check` / `npm test` 发布前必跑。

## License

MIT
