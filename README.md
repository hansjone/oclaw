# Oclaw Architecture Root

This repository is fully consolidated under `oclaw/`.

## Layers
- `runtime/`: core execution loop, routing, skill runtime, hook runtime
- `interfaces/`: transport adapters (HTTP/WS)
- `gateway/`: method handlers and protocol bridging
- `application/`: use-cases and orchestration services
- `infrastructure/`: runtime-facing integrations/adapters
- `platform/`: shared platform capabilities (llm, persistence, config, files)
- `tools/`: tool registry, MCP adapters, public/system tools
- `skills/`: installable skills and runtime manifests

## Naming Rule
- Use `oclaw` consistently in paths, symbols, and docs.
- Avoid introducing legacy aliases or old naming variants.

## Attachment Replay Config
- Attachment-related limits are configured in `oclaw.json` under:
  - `plugins.entries.memory-wiki.auto.attachments.tabular`
- Replay limits:
  - `image_result_replay_cap_chars` (default `4000`, range `600..30000`)
  - `video_result_replay_cap_chars` (default `4000`, range `600..30000`)
  - Used to cap historical `query_image_attachment` / `query_video_attachment(task=transcript)` text replay in model context.
- Video transcript chunk defaults:
  - `video_transcript_chunk_size` (default `1600`)
  - `video_transcript_chunk_overlap` (default `200`)
- Unified archive budget defaults (zip/tar/tgz/gz):
  - `archive_max_depth` (default `2`)
  - `archive_max_file_count` (default `200`)
  - `archive_max_entry_bytes` (default `10485760`)
  - `archive_max_total_uncompressed_bytes` (default `52428800`)
  - Archive parse errors now expose stable `error_code` values (for UI mapping and retries).
- Effective priority for replay-cap values:
  - DB setting `AIA_IMAGE_TOOL_RESULT_REPLAY_CAP_CHARS`
  - DB setting `AIA_VIDEO_TOOL_RESULT_REPLAY_CAP_CHARS`
  - Environment variable `AIA_IMAGE_TOOL_RESULT_REPLAY_CAP_CHARS`
  - Environment variable `AIA_VIDEO_TOOL_RESULT_REPLAY_CAP_CHARS`
  - `oclaw.json` value
  - Built-in default

See `docs/ENVIRONMENT_VARIABLES.md` for full runtime variable reference.

