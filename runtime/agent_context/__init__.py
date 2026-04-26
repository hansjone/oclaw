"""Role/system context builders.

These utilities build a role-specific system context from
`oclaw/runtime/workspaces/*`.
"""

from .loader import build_role_system_context

__all__ = ["build_role_system_context"]

