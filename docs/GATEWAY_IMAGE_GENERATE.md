# Gateway `image.generate` Contract

This document describes the Python gateway method `image.generate`.

## Method

- Name: `image.generate`
- Handler: `oclaw/interfaces/gateway/server_methods/image.py`

## Input Params

- `prompt` (required, non-empty string)
- `provider` (optional, non-empty string)
- `size` (optional, non-empty string)
- `quality` (optional, non-empty string)
- `idempotencyKey` (optional, non-empty string; used as `requestId` when provided)

## Behavior

1. If `context.image_generate` exists, it is used as the primary backend hook.
2. Otherwise, the handler falls back to `extensions/image-generation-core/api.py::generate_image`.
3. Provider resolution uses:
   - `context.image_generation_providers` first
   - then `context.get_runtime_snapshot()["image_generation_providers"]` (if available)
4. Provider selection order:
   - explicit `provider` param
   - `context.config.image.defaultProvider`
   - first matched entry in `context.config.image.providerPriority`
   - first available capable provider
5. Capability filter:
   - providers are considered image-capable when any of the following is true:
     - `capabilities.image_generation == true`
     - `capabilities` list contains `image` / `image_generation`
     - `kind` is `image` / `image_generation`
     - provider exposes callable `generate`

## Error Semantics

- `INVALID_REQUEST`:
  - missing/blank `prompt`
  - invalid optional parameter types/empty strings
- `NOT_FOUND`:
  - explicit `provider` is not registered
- `UNAVAILABLE`:
  - runtime/image backend failure

## Success Payload (normalized)

Success responses include normalized fields:

- `ok: true`
- `status: "succeeded"`
- `requestId: string`
- `provider: string`
- `model: string | null`
- `prompt: string`

Provider-specific fields are preserved and merged into the payload.

