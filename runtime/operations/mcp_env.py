from __future__ import annotations

"""MCP 相关进程环境：默认 allowlist + 可选本地 env 文件（首选 `oclaw/_local/mcp_local.env`）。"""

import os
from pathlib import Path

from oclaw.platform.config.paths import PROJECT_ROOT, db_path

_DEFAULT_ALLOWLIST = (
    "BRAVE_API_KEY,GOOGLE_OAUTH_CREDENTIALS,GOOGLE_CALENDAR_MCP_TOKEN_PATH,"
    "GITHUB_PERSONAL_ACCESS_TOKEN,CONTEXT7_API_KEY,DASHSCOPE_API_KEY,"
    "TRILIUM_API_URL,TRILIUM_API_TOKEN,PERMISSIONS,VERBOSE"
)


def _split_csv_keys(raw: str) -> list[str]:
    return [x.strip() for x in str(raw or "").split(",") if x.strip()]


def _dedupe_preserve_order(keys: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def mcp_env_allowlist_keys() -> list[str]:
    """MCP 子进程可继承的环境变量名：主列表 + EXTRA 合并去重。

    - 未设置 ``AIA_MCP_ENV_ALLOWLIST``：主列表为内置默认（含常用 MCP 密钥名）。
    - 已设置：主列表仅为该项（完全替换默认），用于刻意缩小暴露面。
    - ``AIA_MCP_ENV_ALLOWLIST_EXTRA``（或兼容 ``OPS_MCP_ENV_ALLOWLIST_EXTRA``）：
      始终在主列表之后追加，避免为新增 MCP 手抄整份默认名单。
    """
    primary_raw = str(os.getenv("AIA_MCP_ENV_ALLOWLIST") or "").strip()
    primary = _split_csv_keys(primary_raw) if primary_raw else _split_csv_keys(_DEFAULT_ALLOWLIST)
    extra_raw = str(os.getenv("AIA_MCP_ENV_ALLOWLIST_EXTRA") or "").strip()
    if not extra_raw:
        extra_raw = str(os.getenv("OPS_MCP_ENV_ALLOWLIST_EXTRA") or "").strip()
    extra = _split_csv_keys(extra_raw)
    return _dedupe_preserve_order([*primary, *extra])


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k:
            out[k] = _expand_env_value(v)
    return out


def _expand_env_value(v: str) -> str:
    s = v.strip()
    if "${PROJECT_ROOT}" in s:
        rel = s.split("${PROJECT_ROOT}", 1)[1].lstrip("/\\")
        s = str((PROJECT_ROOT / rel).resolve())
    return os.path.expandvars(s)


def _mcp_local_env_paths_in_load_order() -> list[Path]:
    return [
        Path(db_path()).resolve().parent / "mcp_local.env",
        (PROJECT_ROOT / "_local" / "mcp_local.env").resolve(),
        (PROJECT_ROOT.parent / "_local" / "mcp_local.env").resolve(),
    ]


def mcp_local_env_merged() -> dict[str, str]:
    out: dict[str, str] = {}
    for p in _mcp_local_env_paths_in_load_order():
        if p.is_file():
            out.update(_parse_env_file(p))
    return out


def mcp_local_env_file_path() -> Path:
    return (PROJECT_ROOT / "_local" / "mcp_local.env").resolve()


def gateway_mcp_env_extras() -> dict[str, str]:
    extra: dict[str, str] = {}
    has_aia = str(os.getenv("AIA_MCP_ENV_ALLOWLIST") or "").strip()
    if not has_aia:
        extra["AIA_MCP_ENV_ALLOWLIST"] = _DEFAULT_ALLOWLIST
    file_vals = mcp_local_env_merged()
    for k, v in file_vals.items():
        if not v.strip():
            continue
        if not str(os.getenv(k) or "").strip():
            extra[k] = v
    return extra


def apply_gateway_mcp_env_to_os() -> None:
    for k, v in gateway_mcp_env_extras().items():
        os.environ[k] = v


__all__ = [
    "apply_gateway_mcp_env_to_os",
    "gateway_mcp_env_extras",
    "mcp_env_allowlist_keys",
    "mcp_local_env_file_path",
    "mcp_local_env_merged",
]
