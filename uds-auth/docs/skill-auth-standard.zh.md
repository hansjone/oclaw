# Skill 认证标准（uds-auth）

面向 DeepSeekHarness：现场安装 **uds-auth 插件**（内含 skill `uds-skill-auth`）后，第三方 / 自研 skill 按本标准取凭证或出站调用。

**转发给改造方时**：发整个 `uds-auth` 插件即可；公共 skill 在 [`skills/uds-skill-auth/`](../skills/uds-skill-auth/)，说明见 [uds-skill-auth.zh.md](./uds-skill-auth.zh.md)。

## 现场形态

```text
安装 uds-auth 插件（内含 skills/uds-skill-auth）
  → 将 uds-skill-auth 加入 skills 路径（或复制到工作区 skills/）
  → 用户扫码登录
  → 安装/加载业务 skill
  → 可用
```

无需再配全局 `coclaw_token` / `AUTH_VALUE`。

**认证公共库随插件分发**：路径 `uds-auth/skills/uds-skill-auth/`。

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

Python（先把 `uds-skill-auth/scripts` 加入 `sys.path`）：

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

Helpers 来源：插件内 skill `uds-auth/skills/uds-skill-auth/scripts/`（装到 skills 路径后，或环境变量 `UDS_AUTH_HELPERS`）。

## 改造现有 Skill 清单

1. 现场确保已从插件安装 `uds-skill-auth`（`uds-auth/skills/uds-skill-auth`）  
2. 业务脚本定位 sibling：`.../skills/uds-skill-auth/scripts` → `import uds_skill_auth`  
3. 替换原来的 `coclaw_*` / `EMP_NO`/`AUTH_VALUE` 手工读环境：改用 `resolve()` 或 `request()`  
4. SKILL.md 只写「需已 UDS 登录，并已安装 uds-skill-auth」，不写 token 变量名  
5. JSON stdout；日志脱敏  

定位示例：

```python
from pathlib import Path
import sys

def load_uds_skill_auth():
    here = Path(__file__).resolve().parent
    candidate = here.parents[1] / "uds-skill-auth" / "scripts"
    if not (candidate / "uds_skill_auth.py").is_file():
        raise RuntimeError("请先安装 uds-skill-auth skill")
    sys.path.insert(0, str(candidate))
    import uds_skill_auth
    return uds_skill_auth
```

## 禁止项

- 全局共享 token / 把 token 注入 `shellEnv`  
- SKILL 教打印环境变量中的密钥  
- 无白名单的开放代理  
- 用 UI `sessionStore` 的 30min TTL 冒充 skill 长凭证  
- 业务 skill 硬编码插件源码路径（应用 `uds-skill-auth` skill）  

## 验收

- UI 登录/退出与改前一致  
- 默认配置下 UI 退出后 skill/cron 仍可用  
- `retainSkillCredentialsOnLogout=false` 时退出后取证失败  
- 未安装 `uds-skill-auth` 时业务 skill 报错清晰  
- 两会话不串号；未登录错误可理解且无 token 泄露  
