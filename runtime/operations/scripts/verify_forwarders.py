from __future__ import annotations

from pathlib import Path

from oclaw.platform.config.runtime_paths import oclaw_root, runtime_operations_scripts_root


def verify_forwarders() -> tuple[bool, list[str]]:
    root_scripts = (oclaw_root() / "scripts").resolve()
    real_scripts = runtime_operations_scripts_root()
    errors: list[str] = []
    required = [
        "start_all.ps1",
        "start_gateway.ps1",
        "start_desktop.ps1",
        "start_ops.ps1",
        "start_ops.sh",
        "status_ops.sh",
        "stop_ops.sh",
    ]
    for name in required:
        rp = root_scripts / name
        if not rp.exists():
            errors.append(f"missing forwarder: {rp}")
            continue
        tp = real_scripts / name
        if not tp.exists():
            errors.append(f"missing target: {tp}")
            continue
        text = rp.read_text(encoding="utf-8", errors="ignore")
        normalized = text.replace("\\", "/")
        while "//" in normalized:
            normalized = normalized.replace("//", "/")
        marker_exact = f"runtime/operations/scripts/{name}".replace("\\", "/")
        marker_base = "runtime/operations/scripts"
        if name.endswith(".sh"):
            ok = (marker_base in normalized) and (f"/{name}" in normalized)
        else:
            ok = marker_exact in normalized
        if not ok:
            errors.append(f"forwarder target mismatch: {rp}")
    return (len(errors) == 0), errors


def main() -> int:
    ok, errors = verify_forwarders()
    if ok:
        print("forwarders_ok=1")
        return 0
    print("forwarders_ok=0")
    for err in errors:
        print(err)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

