# LLM provider/transport capability matrix (oclaw)

This project follows an **OpenClaw-style explicit provider/transport selection**:

- You select the transport via **LLM profile `mode`** (not by inferring from `base_url`).
- `base_url` can be the same unified gateway URL for all providers; the `mode` determines the wire protocol.

## Profile field mapping

- **`mode`**: transport selector (`openai`, `openai_responses`, `anthropic`, `google`, `ollama`, `rule`)
- **`model`**: model id/name passed to the provider transport
- **`base_url`**: gateway host URL (may be shared across providers)
- **`api_key`** (profile secret): primary credential source (reused across modes)

Transport selection happens in `oclaw/agents/factory.py`.

## Modes and transports

### `openai` (Chat Completions, OpenAI-compatible)
- **Transport**: `oclaw/platform/llm/transports/openai_chat_completions.py::OpenAIChatModel`
- **API**: `/v1/chat/completions` (streaming supported)
- **Tools**: OpenAI tool calling (`tools[]` / `tool_calls`)
- **Streaming**: token deltas via `on_token` → WS `chat.delta`
- **Key**: profile secret or `OPENAI_API_KEY`

### `openai_responses` (Responses API, OpenAI-compatible)
- **Transport**: `oclaw/platform/llm/transports/openai_responses.py::OpenAIResponsesModel`
- **API**: `/v1/responses` (streaming events)
- **Tools**: function call items parsed from response output
- **Streaming**: output text deltas via `on_token` → WS `chat.delta`
- **Key**: profile secret or `OPENAI_API_KEY`

### `anthropic` (Anthropic Messages streaming)
- **Transport**: `oclaw/platform/llm/transports/anthropic_messages.py::AnthropicMessagesModel`
- **API**: Anthropic `messages.stream` surface (gateway must provide Anthropic-compatible protocol)
- **Tools**: tool use blocks assembled into `LLMToolCall`
- **Streaming**: text deltas via `on_token` → WS `chat.delta`
- **Key**: profile secret or `ANTHROPIC_API_KEY` (fallback: `OPENAI_API_KEY` for unified gateways)

### `google` (Gemini native SSE)
- **Transport**: `oclaw/platform/llm/transports/google_gemini_sse.py::GoogleGeminiChatModel`
- **API**: `:streamGenerateContent?alt=sse` (Gemini native)
- **Tools**: `functionDeclarations` with `parametersJsonSchema`; parses `functionCall`
- **Streaming**: text deltas via `on_token` → WS `chat.delta`
- **Key**: profile secret or `GOOGLE_API_KEY`/`GEMINI_API_KEY` (fallback: `OPENAI_API_KEY` for unified gateways)
- **Thinking controls** (optional env):
  - `AIA_GEMINI_THINKING=on|off`
  - `AIA_GEMINI_THINKING_LEVEL=<string>`
  - `AIA_GEMINI_THINKING_BUDGET=<int>`

### `ollama` (local OpenAI-compatible)
- **Transport**: `OpenAIChatModel` with Ollama-compatible base url
- **API**: `/v1/chat/completions` (Ollama OpenAI-compat)
- **Key**: uses a dummy key (`ollama`) if needed by SDK

### `rule` (no remote LLM)
- **Transport**: `oclaw/platform/llm/transports/simple.py::RuleBasedChatModel`
- **Purpose**: deterministic tool routing/diagnostics without any model provider

## Streaming and UI contract

All transports stream assistant output through the same internal callback:

1. Transport calls `on_token(text_delta)`
2. WS gateway maps that to `event=chat payload.state=delta`
3. Final persisted assistant message is emitted as:
   - `event=chat payload.state=final` (with `message` payload for folding)
   - `event=session.message`
4. Tool UI signals from runtime are emitted as `event=session.tool`

## Adding the remaining models

For additional providers, follow this pattern:

1. Add a new transport class under `oclaw/platform/llm/transports/`
2. Extend `mode` selection in `oclaw/agents/factory.py`
3. Add an **offline stream parser test** under `tests/`
4. Add/verify WS contract tests (delta + final + session.tool)

