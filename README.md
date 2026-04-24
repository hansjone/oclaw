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

