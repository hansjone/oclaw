# OpenClaw Architecture Root

This directory is the new architecture root for ongoing refactors.

## Layers
- `interfaces/`: transport adapters (HTTP/WS/gateway handlers)
- `application/`: use-cases and orchestration services
- `domain/`: business rules and domain primitives
- `infrastructure/`: integrations and runtime adapters
- `shared/`: shared utilities/types

## Migration Rule
New business logic should be implemented in `oclaw/`.
`oclaw/` modules remain as compatibility bridges during migration.

