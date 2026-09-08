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
3. 用户扫码登录  
4. 业务 skill 通过 sibling / skills 根找到本 skill 的 `scripts/`

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
| `resolve()` | `POST /uds-auth/agent-credentials` → empNo+token |
| `request(method, url, ...)` | `POST /uds-auth/outbound` 出站代贴鉴权 |
| `UdsAuthError` | 未登录 / 连不上 Host 等 |

完整契约：[skill-auth-standard.zh.md](./skill-auth-standard.zh.md)
