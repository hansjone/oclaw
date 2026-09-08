# uds-skill-auth（给他人传递用）

把**本文 + 同仓库 skill 目录**发给改造方即可。业务 skill 必须依赖本公共 skill，不能只装插件。

## 仓库位置（可直接拷贝整目录）

```text
skills/uds-skill-auth/
  SKILL.md
  scripts/uds_skill_auth.py
```

现场：拷到对方 `skills/` 下，与业务 skill **同级**。

## 依赖链

```text
uds-auth 插件（Host）
  → skill「uds-skill-auth」（公共库，本页）
  → 用户扫码登录
  → 业务 skill
```

完整契约：[skill-auth-standard.zh.md](./skill-auth-standard.zh.md)

## SKILL.md（安装后目录内同名文件）

```markdown
---
name: uds-skill-auth
description: UDS 技能认证公共库。其它依赖 UDS 登录的 skill 必须安装本 skill，通过其 scripts/uds_skill_auth.py 取凭证或出站调用。需现场已安装 uds-auth 插件且用户已扫码登录。
---

# uds-skill-auth（认证公共 Skill）

本 skill **不是业务能力**，而是给其它 skill 用的公共库。

## 现场依赖

1. 安装并启用 uds-auth 插件
2. 安装本 skill（uds-skill-auth）到 skills 目录
3. 用户扫码登录
4. 再安装/使用业务 skill

## 给其它 Skill 用

业务 skill 的 Python 把本 skill 的 scripts/ 加入 sys.path 后：

from uds_skill_auth import resolve, request, UdsAuthError
creds = resolve()
out = request("POST", url, headers={...}, body={...})
```

## 业务 skill 如何引用（复制这段即可）

```python
from pathlib import Path
import sys

def load_uds_skill_auth():
    here = Path(__file__).resolve().parent
    # .../skills/<业务>/scripts → .../skills/uds-skill-auth/scripts
    candidate = here.parents[1] / "uds-skill-auth" / "scripts"
    if not (candidate / "uds_skill_auth.py").is_file():
        raise RuntimeError("请先安装 uds-skill-auth skill（与业务 skill 同级）")
    sys.path.insert(0, str(candidate))
    import uds_skill_auth
    return uds_skill_auth
```

或设置环境变量 `UDS_AUTH_HELPERS` = 本 skill 的 `scripts` 绝对路径。

## API 摘要

| 函数 | 用途 |
|------|------|
| `resolve(apply_env_aliases=True)` | 向 Host `POST /uds-auth/agent-credentials` 取 `empNo`+`token`；默认写入进程内 `EMP_NO`/`AUTH_VALUE`/`coclaw_*` |
| `request(method, url, headers=..., body=...)` | 向 Host `POST /uds-auth/outbound` 出站；Host 注入鉴权头 |
| `UdsAuthError` | 未登录 / 连不上 Host / 白名单拒绝等 |

Agent 环境（已注入，勿在 SKILL 里教打印密钥）：`DSH_SESSION_ID`、`DSH_WEB_URL`。

## 改造现有 skill 时给 AI 的最短说明

1. 现场已装 uds-auth + 本 skill `uds-skill-auth`  
2. 删掉读全局 `coclaw_token`/`AUTH_VALUE` 的逻辑  
3. 用上面的 `load_uds_skill_auth()` + `resolve()` 或 `request()`  
4. SKILL.md 写明依赖 `uds-skill-auth`，禁止教 printenv token  

实现源码见：`skills/uds-skill-auth/scripts/uds_skill_auth.py`。
