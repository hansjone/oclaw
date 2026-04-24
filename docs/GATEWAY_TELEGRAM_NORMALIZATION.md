# Gateway Telegram Normalization

This document describes how gateway send-related handlers normalize Telegram transport targets.

## Scope

Normalization is applied in these handlers:

- `send`
- `chat.send`
- `sessions.send`

The shared implementation lives in `oclaw/interfaces/gateway/server_methods/telegram_send_normalize.py`.

## Input fields

When `channel == "telegram"`, the normalizer reads:

- `to`
- `threadId` (optional)
- `replyToId` (optional)

Supported `to` examples:

- `telegram:group:-100123:topic:42`
- `telegram:-100123:42`
- `@username`
- `https://t.me/username`

## Output fields

The normalizer returns:

- normalized `to`
- `target`:
  - `chatId`
  - `chatType` (`direct` | `group` | `unknown`)
  - `messageThreadId` (when present in target)
- `threadId` (normalized integer if present/resolved)
- `replyToMessageId` (normalized integer if present)

## Precedence

- `threadId` in request params overrides thread inferred from target suffix.
- `replyToId` is converted to `replyToMessageId` if numeric; otherwise omitted.

## Notes

- Non-Telegram channels pass through unchanged.
- Normalized fields are included in handler payloads and in forwarded params for `chat.send -> enqueue_chat_send`.
