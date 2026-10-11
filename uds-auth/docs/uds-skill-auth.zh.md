# uds-skill-auth（随插件分发）

本公共 skill **在插件仓库内**，与 uds-auth 一起提交、一起给别人：

```text
uds-auth/skills/uds-skill-auth/
  SKILL.md
  scripts/uds_skill_auth.py
```

## 现场怎么用

1. 安装 uds-auth 插件  
2. 把 `uds-auth/skills/uds-skill-auth` 配进 Harness 的 skills 目录（或复制到工作区 `skills/uds-skill-auth`）  
3. 用户扫码登录（或由 Host 为 cron 注入 `UDS_TASK_CAPABILITY`）  
4. 业务 skill 通过 sibling / skills 根找到本 skill 的 `scripts/`

推荐：**优先** `request()` / outbound；原始 `resolve()` 依赖 `allowRawAgentToken`（默认关闭）。后台任务使用 `UDS_TASK_CAPABILITY`，不要依赖浏览器 Cookie。

## 业务 skill 引用

```python
from pathlib import Path
import sys

def load_uds_skill_auth():
    here = Path(__file__).resolve().parent
    candidate = here.parents[1] / "uds-skill-auth" / "scripts"
    if not (candidate / "uds_skill_auth.py").is_file():
        raise RuntimeError("请先安装插件自带的 uds-skill-auth skill")
    sys.path.insert(0, str(candidate))
    import uds_skill_auth
    return uds_skill_auth
```

| 函数 | 用途 |
|------|------|
| `resolve()` | 原始凭证（需显式开启 raw；可带 `UDS_TASK_CAPABILITY`） |
| `request(method, url, ...)` | `POST /uds-auth/outbound`（推荐；支持 task capability） |
| `UdsAuthError` | 未登录 / 连不上 Host 等 |

环境变量：`DSH_SESSION_ID`、`UDS_TASK_CAPABILITY`（Host `mintTaskCapability` 签发）。

完整契约：[skill-auth-standard.zh.md](./skill-auth-standard.zh.md)
