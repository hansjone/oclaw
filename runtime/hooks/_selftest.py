from __future__ import annotations

import asyncio
from pathlib import Path
import sys

HOOKS_PY_DIR = Path(__file__).resolve().parent
OCLAW_DIR = HOOKS_PY_DIR.parent
if str(OCLAW_DIR) not in sys.path:
    sys.path.insert(0, str(OCLAW_DIR))

from runtime.hooks.internal_hooks import create_hook_event, trigger_hook  # noqa: E402
from runtime.hooks.loader import load_internal_hooks  # noqa: E402


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    bundled = repo_root / "runtime" / "hooks" / "bundled"
    ws_dir = repo_root / "_hooks_selftest_workspace"
    ws_dir.mkdir(parents=True, exist_ok=True)
    (ws_dir / "memory").mkdir(parents=True, exist_ok=True)

    cfg = {
        "hooks": {
            "internal": {
                "enabled": True,
                "entries": {
                    "bootstrap-extra-files": {
                        "enabled": True,
                        "paths": ["**/AGENTS.md"],
                    },
                    "session-memory": {
                        "enabled": True,
                        "messages": 15,
                    },
                },
            }
        }
    }

    # Use repo root as a fake "workspace dir" for this self-test.
    loaded = load_internal_hooks(cfg, workspace_dir=str(ws_dir), bundled_hooks_dir=str(bundled))
    print(f"loaded_hooks={loaded}")

    async def run() -> None:
        # gateway:startup
        ev0 = create_hook_event(
            "gateway",
            "startup",
            "agent:main:main",
            context={"cfg": cfg, "workspaceDir": str(ws_dir)},
        )
        await trigger_hook(ev0)

        # agent:bootstrap (inject extra files)
        # prepare a fake AGENTS.md to match **/AGENTS.md
        (ws_dir / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
        ctx = {"cfg": cfg, "workspaceDir": str(ws_dir), "bootstrapFiles": []}
        ev1 = create_hook_event("agent", "bootstrap", "agent:main:main", context=ctx)
        await trigger_hook(ev1)
        print(f"bootstrapFiles_after={len(ctx.get('bootstrapFiles') or [])}")

        # command:new and command:reset (writes memory markdown; also command-logger runs on command)
        ev = create_hook_event(
            "command",
            "new",
            "agent:main:main",
            context={
                "senderId": "selftest",
                "commandSource": "local",
                "cfg": cfg,
                "workspaceDir": str(ws_dir),
            },
        )
        await trigger_hook(ev)
        ev2 = create_hook_event(
            "command",
            "reset",
            "agent:main:main",
            context={
                "senderId": "selftest",
                "commandSource": "local",
                "cfg": cfg,
                "workspaceDir": str(ws_dir),
            },
        )
        await trigger_hook(ev2)

    asyncio.run(run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

