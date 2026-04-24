"""Role/system context builders.

These utilities build a role-specific system context from the runtime asset
workspaces under `oclaw/runtime/assets/agent_workspaces/*`.
"""

from .loader import build_role_system_context

__all__ = ["build_role_system_context"]

