---
name: uds-skill-auth
description: UDS 技能认证公共库。其它依赖 UDS 登录的 skill 必须安装本 skill，通过其 scripts/uds_skill_auth.py 取凭证或出站调用。需现场已安装 uds-auth 插件且用户已扫码登录。本 skill 随 uds-auth 插件一同分发。
---

# uds-skill-auth（认证公共 Skill）

本 skill **不是业务能力**，而是给其它 skill 用的公共库。**随 uds-auth 插件一起提供**，目录在插件内：

```text
uds-auth/skills/uds-skill-auth/
```

## 现场依赖

```text
1. 安装并启用 uds-auth 插件
2. 将本目录（插件内 skills/uds-skill-auth）加入 Harness skills 路径，
   或复制到工作区 skills/ 下与业务 skill 同级
3. 用户扫码登录
4. 再安装/使用业务 skill
```

## 给其它 Skill 用

业务 skill 的 Python 脚本里，把本 skill 的 `scripts/` 加入 `sys.path` 后：

```python
from uds_skill_auth import resolve, request, UdsAuthError

creds = resolve()
out = request("POST", "https://icenterapi.zte.com.cn/...", headers={...}, body={...})
```

定位本 skill（与业务 skill 同级，或已加入 skills 根）：

```python
from pathlib import Path
import sys

def load_uds_skill_auth():
    here = Path(__file__).resolve().parent
    for skills_root in [here.parents[1], *here.parents]:
        candidate = skills_root / "uds-skill-auth" / "scripts"
        if (candidate / "uds_skill_auth.py").is_file():
            sys.path.insert(0, str(candidate))
            import uds_skill_auth
            return uds_skill_auth
    raise RuntimeError("未找到 uds-skill-auth，请从 uds-auth 插件 skills/ 安装该 skill")
```

也可设置 `UDS_AUTH_HELPERS` 指向本 skill 的 `scripts` 绝对路径。

## 环境变量（Agent 已注入，勿教模型打印密钥）

- `DSH_SESSION_ID`
- `DSH_WEB_URL`

## 标准文档

见插件内 `docs/skill-auth-standard.zh.md` 与 `docs/uds-skill-auth.zh.md`。
