# Local Public Tools

This project exposes local atomic capabilities as shared `public` tools for all agents.

## Included P0 tools

- `run_command`
- `read_file`
- `write_file`
- `edit_file`

## Included P1/P2/P3 tools

- `list_directory`
- `move_file`
- `delete_file`
- `mkdir`
- `search_files`
- `get_cwd`
- `cd`
- `get_env`
- `set_env`
- `list_processes`
- `kill_process`

## Loading path

- Files live under `runtime/tools/public/`.
- They are auto-discovered by `runtime/tools/public_registry.py` (`*_tool` factory naming).
- Final exposure is controlled in `runtime/tools/catalog.py`.

## Risk gating

- `read_file` is `risk_level=low` and visible by default.
- `run_command`, `write_file`, `edit_file` are `risk_level=high`.
- High-risk public tools are hidden unless `AIA_PUBLIC_TOOLS_ALLOW_HIGH=1`.

## Local backend adapter

- Adapter path: `runtime/tools/local_sdk/adapter.py`.
- Uses a self-implemented local backend (cross-platform) with a stable tool contract.

## Path behavior defaults

- `run_command`: when `cwd` is omitted, it runs in `data/workspace`.
- `write_file`: absolute path is used directly; relative path is written under `data/workspace`.
