# Skill 认证标准（uds-auth）

面向 DeepSeekHarness：现场安装 **uds-auth** 后，第三方 / 自研 skill 按本标准取凭证或出站调用。官方样板：[skills/uds-icenter](../../skills/uds-icenter)。

## 现场形态

```text
安装 uds-auth 插件 → 用户扫码登录 → 加载 skill → 可用
```

无需再配全局 `coclaw_token` / `AUTH_VALUE`。

## 双轨模型

| 轨道 | 用途 | 行为 |
|------|------|------|
| UI | Cookie + `sessionStore` + `/api/me` | **保持原样**；logout 仍清 cookie 并 `sessionStore.delete` |
| Skill | `skillCredentialCache`（`skill-credentials.json`） | 登录成功时写入/刷新；供 agent / cron |

配置项：

- `retainSkillCredentialsOnLogout`（默认 `true`）：UI 退出时是否保留 skill token  
- `skillCredentialTtlSeconds`（默认 `604800` = 7 天）  
- `outboundAllowedHosts`：出站白名单（逗号分隔）

管理员删除用户会同时清掉该用户的 skill 凭证。

## Agent 环境

Shell 已注入（非密钥）：

- `DSH_SESSION_ID` — 当前 agent 会话  
- `DSH_WEB_URL` — 可选，用于拼 Host 地址  

Host 在 `session/created` 时会 `stampSessionOwner(sessionId, empNo)`。Cron 可按 `ownerEmpNo` 解析。

## 两种合法模式

### Mode Outbound（推荐新 skill）

```http
POST /uds-auth/outbound
X-DSH-Session-Id: <DSH_SESSION_ID>
{ "url": "https://icenterapi.zte.com.cn/...", "method": "POST", "headers": {...}, "body": {...} }
```

- 仅 **loopback**  
- Host 注入 `X-Emp-No` / `X-Auth-Value`  
- 剥离客户端自带鉴权头  
- host 必须在白名单内  

Python：

```python
from uds_skill_auth import request
out = request("POST", url, headers={...}, body={...})
# out["statusCode"], out["json"], out["body"]
```

### Mode Creds（必须自管 HTTP 时）

```http
POST /uds-auth/agent-credentials
X-DSH-Session-Id: <DSH_SESSION_ID>
```

返回 `{ empNo, token }`。可设进程内 `EMP_NO` / `AUTH_VALUE` 别名，**禁止**写进 SKILL.md 教模型 `printenv`。

```python
from uds_skill_auth import resolve
creds = resolve()  # empNo + token；默认写入 EMP_NO/AUTH_VALUE
```

Helpers 路径：`uds-auth/skill-helpers/python/`（或环境变量 `UDS_AUTH_HELPERS`）。

## 自研 Skill 清单

1. 建目录：`SKILL.md` + `scripts/`  
2. 引用 helpers（见样板 `lib_uds.py`）  
3. 默认走 `request()` outbound；发信等桌面端口可用 `resolve()` 贴头  
4. SKILL 只写「需已 UDS 登录」，不写 token 变量名  
5. JSON stdout；日志脱敏  

## 禁止项

- 全局共享 token / 把 token 注入 `shellEnv`  
- SKILL 教打印环境变量中的密钥  
- 无白名单的开放代理  
- 用 UI `sessionStore` 的 30min TTL 冒充 skill 长凭证  

## 验收

- UI 登录/退出与改前一致  
- 默认配置下 UI 退出后 skill/cron 仍可用  
- `retainSkillCredentialsOnLogout=false` 时退出后取证失败  
- 两会话不串号；未登录错误可理解且无 token 泄露  

## 样板走读

| 文件 | 作用 |
|------|------|
| `skills/uds-icenter/SKILL.md` | 给模型的用法 |
| `scripts/lib_uds.py` | 定位 helpers |
| `scripts/contacts.py` | 搜人/搜群/群成员（outbound） |
| `scripts/messaging.py` | 本机发信 + resolve 贴头 |
| `scripts/cli.py` | 统一入口 |
