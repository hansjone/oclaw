from __future__ import annotations

from .shared_types import GatewayRequestHandlers
from .validation import error_shape


def _connect_handler(opts):
    respond = opts.get("respond")
    if callable(respond):
        respond(
            False,
            None,
            error_shape("INVALID_REQUEST", "connect is only valid as the first request"),
            None,
        )


connect_handlers: GatewayRequestHandlers = {
    "connect": _connect_handler,
}
