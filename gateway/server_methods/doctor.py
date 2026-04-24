from __future__ import annotations

from typing import Any

from .shared_types import GatewayRequestHandlers
from .validation import error_shape


def _ok(respond, payload: Any) -> None:
    if callable(respond):
        respond(True, payload, None, None)


def _unavailable(respond, message: str) -> None:
    if callable(respond):
        respond(False, None, error_shape("UNAVAILABLE", message), None)


def _doctor_memory_status_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    context = opts.get("context")
    hook = context.get("doctor_memory_status") if isinstance(context, dict) else None
    if callable(hook):
        try:
            payload = hook()
            _ok(respond, payload if isinstance(payload, dict) else {})
            return
        except Exception as exc:
            _unavailable(respond, str(exc))
            return

    # Staging fallback shape (compatible with dashboard expectations).
    _ok(
        respond,
        {
            "agentId": "main",
            "provider": None,
            "embedding": {"ok": True},
            "dreaming": {
                "enabled": False,
                "verboseLogging": False,
                "storageMode": "inline",
                "separateReports": False,
                "shortTermCount": 0,
                "recallSignalCount": 0,
                "dailySignalCount": 0,
                "groundedSignalCount": 0,
                "totalSignalCount": 0,
                "phaseSignalCount": 0,
                "lightPhaseHitCount": 0,
                "remPhaseHitCount": 0,
                "promotedTotal": 0,
                "promotedToday": 0,
                "shortTermEntries": [],
                "signalEntries": [],
                "promotedEntries": [],
                "phases": {
                    "light": {"enabled": False, "cron": "", "managedCronPresent": False, "lookbackDays": 0, "limit": 0},
                    "deep": {
                        "enabled": False,
                        "cron": "",
                        "managedCronPresent": False,
                        "minScore": 0,
                        "minRecallCount": 0,
                        "minUniqueQueries": 0,
                        "recencyHalfLifeDays": 0,
                        "limit": 0,
                    },
                    "rem": {
                        "enabled": False,
                        "cron": "",
                        "managedCronPresent": False,
                        "lookbackDays": 0,
                        "limit": 0,
                        "minPatternStrength": 0,
                    },
                },
            },
        },
    )


doctor_handlers: GatewayRequestHandlers = {
    "doctor.memory.status": _doctor_memory_status_handler,
}

