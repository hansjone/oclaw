"""WebSocket interface adapters."""

from .entrypoint import ws_gateway_loop
from .runtime import OclawWsGatewayConnection

__all__ = ["ws_gateway_loop", "OclawWsGatewayConnection"]

