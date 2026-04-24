from __future__ import annotations

from pathlib import Path

from oclaw.platform.config.runtime_paths import oclaw_root


_PS1_FORWARDERS: dict[str, str] = {
    "bootstrap_venv.ps1": "& $real @args",
    "start_web.ps1": "& $real @args",
    "status_all.ps1": "& $real @args",
    "status_ops.ps1": "& $real @args",
    "status_wiki_worker.ps1": "& $real @args",
    "stop_all.ps1": "& $real @args",
    "stop_desktop.ps1": "& $real @args",
    "stop_gateway.ps1": "& $real @args",
    "stop_ops.ps1": "& $real @args",
    "stop_web.ps1": "& $real @args",
    "stop_wiki_worker.ps1": "& $real @args",
}


def _ps1_template(name: str, invoke_line: str) -> str:
    return (
        "param()\n\n"
        "$ErrorActionPreference = \"Stop\"\n\n"
        f"$real = Join-Path $PSScriptRoot \"..\\\\runtime\\\\operations\\\\scripts\\\\{name}\"\n"
        "if (-not (Test-Path $real)) {\n"
        "    throw \"Forward script target not found: $real\"\n"
        "}\n\n"
        f"{invoke_line}\n"
    )


def _sh_template(name: str) -> str:
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n\n"
        f"REAL_PATH=\"$(cd \"$(dirname \"${{BASH_SOURCE[0]}}\")/../runtime/operations/scripts\" && pwd)/{name}\"\n"
        "if [[ ! -f \"$REAL_PATH\" ]]; then\n"
        "  echo \"[ERROR] Forward script target not found: $REAL_PATH\" >&2\n"
        "  exit 1\n"
        "fi\n\n"
        "exec bash \"$REAL_PATH\" \"$@\"\n"
    )


def generate_forwarders() -> list[Path]:
    out: list[Path] = []
    scripts_root = (oclaw_root() / "scripts").resolve()
    scripts_root.mkdir(parents=True, exist_ok=True)
    for name, invoke in _PS1_FORWARDERS.items():
        p = scripts_root / name
        p.write_text(_ps1_template(name, invoke), encoding="utf-8")
        out.append(p)

    for name in ("start_ops.sh", "status_ops.sh", "stop_ops.sh"):
        p = scripts_root / name
        p.write_text(_sh_template(name), encoding="utf-8")
        out.append(p)
    return out


def main() -> int:
    generated = generate_forwarders()
    print(f"generated_forwarders={len(generated)}")
    for p in generated:
        print(str(p))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

