# oclaw trace taxonomy

Trace events share a common `payload` shape across components. Prefer joining on `trace_id`, `pipeline`, and `oc_stage`.

## Stable keys

| Key | Meaning |
| --- | --- |
| `trace_id` | Correlates all events for one gateway turn |
| `pipeline` | Which subsystem emitted the event (`openclaw_gateway`, `openclaw_agent_core`, `openclaw_direct_loop`, `openclaw_skill_executor`) |
| `oc_stage` | Normalized lifecycle stage (see tables below) |
| `lang` | Request language when known |
| `run_id` | Agent core run UUID (retry container) |
| `attempt_no` | 1-based attempt index inside `run_id` |
| `openclaw_task_id` | Async worker task id when present |
| `openclaw_worker_id` | Worker thread id when present |

## Gateway (`pipeline=openclaw_gateway`)

| `event_type` | `oc_stage` |
| --- | --- |
| `gateway_received` | `ingress` |
| `gateway_normalized` | `normalize` |
| `skill_manifest` | `skills_manifest` |
| `memory_retrieval_started` | `memory_start` |
| `memory_retrieval_finished` | `memory_done` |
| `router_decision` | `route` |
| `task_enqueued` | `async_enqueue` |
| `runtime_config` | `runtime_config` |
| `response_sent` | `response` |

`gateway_received` payload now includes relay pointer stats:

- `relay_pointer_count`: number of direct pointer attachments on inbound message
- `relay_envelope_present`: whether `metadata.relay_share_envelope` exists
- `relay_envelope_pointer_count`: pointer count inside envelope manifest

## Agent core (`pipeline=openclaw_agent_core`)

| `event_type` | `oc_stage` |
| --- | --- |
| `run_started` | `run_start` |
| `attempt_started` | `attempt` |
| `attempt_finished` | `attempt_done` |
| `run_finished` | `run_done` |
| `run_compact` | `compact` |
| `run_retry` | `retry` |

## Direct loop (`pipeline=openclaw_direct_loop`)

| `event_type` | `oc_stage` |
| --- | --- |
| `tool_wire_filter` | `wire_filter` |
| `tool_result_context_guard` | `tool_context_guard` |

Both include `trace_id` and, when provided by the parent attempt, `run_id` and `attempt_no`.

## Skill executor (`pipeline=openclaw_skill_executor`)

| `event_type` | `oc_stage` |
| --- | --- |
| `skill_selected` | `skill_select` |
| `skill_executed` | `skill_done` |

The payload includes `run_id` and `attempt_no` when available, so skill execution can be joined back to `run_started/attempt_started`.

## Attempt memory hook (`pipeline=openclaw_agent_core`)

| `event_type` | `oc_stage` |
| --- | --- |
| `after_turn_memory` | `memory_done` |
