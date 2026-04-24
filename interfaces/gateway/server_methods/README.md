# server_methods

这是 `vendor/oclaw/oclaw/gateway/server-methods` 的 Python 重写目录。

## 当前已迁移
- `connect.ts` -> `connect.py`
- `commands.ts` -> `commands.py`
- `config.ts` -> `config.py`
- `channels.ts` -> `channels.py`
- `health.ts` -> `health.py`
- `logs.ts` -> `logs.py`
- `image.ts` -> `image.py`
- `doctor.ts` -> `doctor.py`
- `sessions.ts` -> `sessions.py`
- `chat.ts` -> `chat.py`
- `agent.ts` -> `agent.py`
- `agents.ts` -> `agents.py`
- `send.ts` -> `send.py`
- `skills.ts` -> `skills.py`
- `system.ts` -> `system.py`
- `cron.ts` -> `cron.py`
- `devices.ts` -> `devices.py`
- `models.ts` -> `models.py`
- `models-auth-status.ts` -> `models_auth_status.py`
- `push.ts` -> `push.py`
- `update.ts` -> `update.py`
- `voicewake.ts` -> `voicewake.py`
- `wizard.ts` -> `wizard.py`
- `tts.ts` -> `tts.py`
- `web.ts` -> `web.py`
- `tools-catalog.ts` -> `tools_catalog.py`
- `tools-effective.ts` -> `tools_effective.py`
- `talk.ts` -> `talk.py`
- `usage.ts` -> `usage.py`
- `exec-approvals.ts` -> `exec_approvals.py`
- `nodes-pending.ts` -> `nodes_pending.py`
- `nodes.ts` -> `nodes.py`
- `base-hash.ts` -> `base_hash.py`
- `restart-request.ts` -> `restart_request.py`
- `record-shared.ts` -> `record_shared.py`
- `attachment-normalize.ts` -> `attachment_normalize.py`
- `shared-types.ts` -> `shared_types.py`
- `types.ts` -> `types.py`
- `validation.ts` -> `validation.py`

## 迁移策略
- 先迁移低耦合基础方法与类型层。
- 再迁移高耦合方法（`chat.ts`、`sessions.ts`、`nodes.ts`、`agent.ts` 等）。
- 每批迁移后执行语法与单测校验，保证可持续推进。
