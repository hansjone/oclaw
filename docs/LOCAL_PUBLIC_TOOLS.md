# Local Public Tools

This project exposes local atomic capabilities as shared `public` tools for all agents.

## Included P0 tools

- `local_run_command`
- `local_read_file`
- `local_write_file`
- `local_edit_file`

## Loading path

- Files live under `runtime/tools/public/`.
- They are auto-discovered by `runtime/tools/public_registry.py` (`*_tool` factory naming).
- Final exposure is controlled in `runtime/tools/catalog.py`.

## Risk gating

- `local_read_file` is `risk_level=low` and visible by default.
- `local_run_command`, `local_write_file`, `local_edit_file` are `risk_level=high`.
- High-risk public tools are hidden unless `AIA_PUBLIC_TOOLS_ALLOW_HIGH=1`.

## Local backend adapter

- Adapter path: `runtime/tools/local_sdk/adapter.py`.
- Uses a self-implemented local backend (cross-platform) with a stable tool contract.
