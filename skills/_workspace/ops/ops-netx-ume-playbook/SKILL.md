---
name: ops-netx-ume-playbook
description: 面向 ops 专家的 netx UME 运维作业手册。覆盖告警查询/聚合/诊断、网元清单与单网元详情、raw 字段过滤、UME 只读 SQL、以及告警关联拓扑路径。
---

# Ops Netx UME 作业手册

## 强制使用范围

凡是涉及 netx/UME **告警**或 **网元信息** 的 ops 请求，必须优先加载并遵循本技能。

## MCP 工具名（强制）

使用 Cursor / oclaw MCP 时，工具名为 **camelCase**（`server_id=netx`）：

| 用途 | MCP 工具 |
|------|----------|
| 告警列表 | `queryUmeAlarms` |
| 告警聚合 | `aggregateUmeAlarms` |
| 诊断摘要 | `runUmeDiagnostics` |
| 网元清单 | `queryUmeNeInventory` |
| 网元详情 | `getUmeNe` |
| 字段清单 | `listUmeAlarmFields` |
| 原始明细 | `queryUmeAlarmsRaw` |
| 动态聚合 | `aggregateUmeAlarmsRaw` |
| SQL | `sqlQueryUme` |
| 拓扑路径 | `findTopologyPaths` |
| 纳管/CLI（另册） | `listManagedNe` / `getManagedNe` / `execManagedNe` / `listCliTargets` |

使用 **MCP** 名称（`mcp__netx__*`）；勿使用已移除的旧 inline `netx_*` 工具名。

## 工具选择顺序

1. **新鲜度（先做）**：`runUmeDiagnostics` 或 `aggregateUmeAlarms` → 看 `meta.last_seen_min` / `last_seen_max`。  
   - 若最大值远早于「现在」，按 **快照数据** 处理：时间窗用数据范围内的日期，禁止套 `now()-30 minutes`。
2. 基础视图：`aggregateUmeAlarms` + `runUmeDiagnostics`；样本用 `queryUmeAlarms`（默认 1 页）。
3. 证据明细：`listUmeAlarmFields` → `queryUmeAlarmsRaw`（`field_preset=evidence` / `select_fields`）。
4. 自定义聚合：`aggregateUmeAlarmsRaw`（`group_by=alarm_host_name` 等）。
5. SQL：`sqlQueryUme`（仅 SELECT；设 `statement_timeout_ms`）。
6. **告警关联拓扑**：两台相关网元取 `ne_id` → `findTopologyPaths`（最短路径优先）。
7. **登设备查 CLI**：见 `ops-netx-managed-ne-playbook`（含对/错 JSON 示例）；多台必须 **一次** `execManagedNe` batch（同命令用 `ne_ids|ume_ne_ids`；每台命令不同用 `targets=[{ume_ne_id, commands},…]`）。同轮连发多次单台 `execManagedNe` **不会并行**（stdio 串行），禁止。
   - 例：`{"ume_ne_ids":["uuid-a","uuid-b"],"commands":["show version"]}`；混厂商用 `targets=[…]` 仍一次调用。

## 快速决策树

- **整体态势 / Top 风险**：`runUmeDiagnostics` + `aggregateUmeAlarms`（默认已排除 missing host；看 `by_ne_missing`）。
  - 高危 Top-N：`aggregateUmeAlarms(severity=critical, top_ne=10)`，勿只看总量 Top。
  - 按 host 自定义分组：`aggregateUmeAlarms(group_by=alarm_host_name, …)`（内部等同 Raw）或显式 `aggregateUmeAlarmsRaw`。
- **时间收敛**：`queryUmeAlarms` / `aggregateUmeAlarms` / raw 均支持 `time_from`/`time_to`（语义=`last_seen_at`）。先看 freshness，再填时间窗。
- **可引用证据**：`queryUmeAlarmsRaw` + `field_preset=evidence`。
- **任意字段统计**：`aggregateUmeAlarmsRaw`（按 host 分组时默认排除 missing；看 `by_ne_missing`）。
- **复杂条件**：`sqlQueryUme`。
- **critical 口类/光路类告警**：抽 1–2 个 `ne_id` → `findTopologyPaths`（默认 `detail=summary`，看 `paths[].label`）→ 再决定是否 CLI。
- **查网元身份**：`queryUmeNeInventory(keyword=host_name)`；完整 `raw_json` 用 `getUmeNe`。

## WhatsApp short-intent recipes (≤3 tools; English field primary)

Prefer these fixed paths for short group/DM asks (EN first; ZH aliases still work). **Target ≤3 tool calls** — do not paginate or re-list CLI targets.

| User says (examples) | Recipe |
|----------------------|--------|
| fiber cut / LOS / cable cut / 断纤 / sitelist | Prefer `ume_alarm_xlsx_report(mode=fiber_cut)` (defaults keyword=`LOS` → ETPI LOS; not optical-power threshold). For explicit **Fiber Break** rows also/instead `keyword=Fiber Break` or `queryUmeAlarmsRaw(keyword=Fiber Break)`. Reply with **host_name list** + counts |
| offline NE / board offline / unmanaged / 离线 | Prefer `ume_alarm_xlsx_report(mode=offline)` (defaults `BN EMS` / NE communication failure). Unmanaged ME list → same family + clarify BN EMS / unreachable |
| Critical Top / alarm tally | ① `aggregateUmeAlarms(severity=critical, top_ne=20)`; for file: `ume_alarm_xlsx_report(mode=aggregate_by_host, severity=critical)` |
| how many alarms / tally / 现网告警数量 | ① `runUmeDiagnostics` or `aggregateUmeAlarms`; ② report by_severity + freshness |
| export Excel / send spreadsheet | `ume_alarm_xlsx_report` **or** `write_xlsx(..., deliverable=true)`; never split into 3 steps |
| CRC in area PAD / ACH / … | `queryUmeAlarmsRaw(keyword=CRC)` then keep rows whose `alarm_host_name` / `ne_host_name` starts with area prefix (`PAD-`, `ACH-`, …). Optional xlsx via `write_xlsx(deliverable=true)` |
| bandwidth / congestion / usage rate (+ area) | keyword=`bandwidth` (matches *Send/Receive bandwidth usage rate threshold crossed*; do **not** require event_type). Filter hostname prefix for area; if CLI confirm: top 3–5 NEs in **one** batch |
| optical power **threshold** in area (BPP/PBR/PAL/…) | keyword=`optical power` (or `Input optical power`) + keep `AREA-` hosts. **Not** fiber_cut mode. Distinct from capacity A<>B CLI |
| BN EMS / dying gasp / unmanaged (+ area) | See **Dying gasp / BN EMS correlation** below — do not stop at one NE |
| power / temperature / fan / undervoltage / System Power off | keyword=`power` / `temperature` / `fan` / `undervoltage` / `Power off`; scope to host or area prefix. Optical *power(dBm)* ≠ board voltage |
| license | keyword=`License` (causes: *Permanent license abnormal*, *No enough license resource*) |
| BGP / OSPF / ISIS / LDP / PW / Tunnel on host | `queryUmeAlarmsRaw(host or keyword=BGP\|OSPF\|LDP\|…)` on named host(s); for peer correlation see below |
| Port down / ETPI / which segment cut? | keyword=`Port down` or `LOS` on the named host; use `object_name` + `findTopologyPaths` / LLDP to name the far end |
| alarm code NNNN | `queryUmeAlarmsRaw` / diagnostics `top_alarm_codes`; keyword or raw filter on code; return **host_name** list |
| alarm on **one hostname** (e.g. `MDN-PLSP`, `MKS-SWBP-EN1`) | `queryUmeAlarms` / `queryUmeAlarmsRaw` with `host_name` / keyword=hostname. **Never** start a scheduled License/daily playbook |
| alarm history / time range (e.g. `17.50-18.15`) | Resolve **WIB (UTC+7)** wall clock → `time_from`/`time_to` on `last_seen_at` / history fields; first check freshness; name hosts exactly (`MKS-KIM-CN1`) |
| is NE rebooted? / alarm history for NE | Host-scoped alarm history (reboot/reload/power related causes); answer yes/no + evidence times |

Delivery rules:
- `ume_alarm_xlsx_report` defaults `deliverable=true` so WhatsApp receives the file.
- Generic sheets: `write_xlsx(..., deliverable=true)` can skip `save_deliverable_attachment`.
- Do not build xlsx via `run_command` + openpyxl.
- Confirm short replies (`YES` / `confirm` / `继续` / `ya` / `yea`): continue the previous task; do not restart the query.

### Field vocabulary (prod-learned; enforce)

- **Area** = hostname **prefix** before first `-`: `MDN-`, `LPG-`, `MKS-`, `PLG-`, `BJM-`, `PTK-`, `ACH-`, `PBR-`, `MDO-`, `SMD-`, `PAD-`, `BTM-`, `PLK-`, `BPP-`, `BKL-`, `JBI-`, `KND-`, `PAL-`, `GRO-`, `JAP-`, … Case-insensitive starts-with.
- **Capacity / bandwidth between A and B** / `A <> B` / site nicknames (SEMBAWA, ANGKATAN_EP): means **SFP/optical link** on the interconnect — **not** UME *bandwidth usage rate* alarms alone. Resolve both NEs → ports (`findTopologyPaths` / LLDP) → optic CLI. See `ops-netx-managed-ne-playbook`.
- **Optical power threshold crossed** (area list): UME cause *Input/Output optical power(dBm) threshold crossed* — keyword=`optical power`; **not** `mode=fiber_cut`.
- **Fiber cut / LOS sitelist**: causes *Ethernet physical (ETPI) LOS*, *Fiber Break*, *Missing laser module* — report `mode=fiber_cut` (LOS-biased) and/or `keyword=Fiber Break`.
- **Site nicknames**: resolve via inventory/wiki/`queryUmeNeInventory(keyword=…)` **before** CLI; never invent hostnames.
- **Local clock phrases** (`17.50`, `today`, `yesterday`): treat as **Asia/Jakarta (WIB, UTC+7)** unless user says otherwise.

### Field cause cheat-sheet (2026-08 snapshot vocabulary)

Use these as `keyword` / evidence labels (exact strings appear in `native_probable_cause`):

| Intent | Typical cause substrings |
|--------|---------------------------|
| Fiber / LOS | `ETPI) LOS`, `Fiber Break`, `Missing laser module` |
| Optical threshold | `Input optical power(dBm) threshold crossed`, `Output optical power` |
| Congestion | `Send bandwidth usage rate`, `Receive bandwidth usage rate` |
| CRC | `Receive CRC error frames`, `Received CRC error packet` |
| Offline / unmanaged | `BN EMS alarm NE communication failure` |
| Dying gasp | `Remote dying gasp event` |
| License | `Permanent license abnormal`, `No enough license resource` |
| Power / env | `System Power off`, `Input undervoltage`, `temperature`, `Fan module` |
| Control-plane (noisy) | `BGP Neighbour down`, `OSPF Neighbour`, `ISIS Neighbour`, `LDP Neighbour`, `State of PW in L2VPN`, `Tunnel down`, `NTP server` |

Do **not** treat PW/BGP volume leaders as “fiber cut” unless the user asked for those families.

### Dying gasp / BN EMS correlation (field-mandated)

When user mentions **dying gasp** (or correlates BN EMS with a port):

1. On the named NE: `queryUmeAlarmsRaw` with keyword=`dying gasp` (and/or host_name) — note `object_name` / slot-port and `last_seen_at`.
2. Find peer: `findTopologyPaths` and/or LLDP/CLI on that port; identify far-end `host_name`.
3. On the **peer**: look for **BN EMS** / `NE communication failure` (and related offline) with **near timestamp** (± window from step 1).
4. Reply with both sides + times + whether correlation holds. Save this as the default dying-gasp playbook — do not answer only one NE.

### Peer / protocol correlation (BGP·OSPF·LDP)

Field pattern: alarms on `HOST-A` with peer IP → confirm on `HOST-B` (or peer from topology).

1. Query both hosts (or keyword + both host filters) for the protocol family.
2. Align **occurrence / clear** times when asked.
3. Peer match: prefer exact peer / router-id; if user says so, also match **identical 3rd+4th octet** of the peer address from the alarm text.
4. Keep answers scoped to the named link (`A <> B`); do not dump unrelated area noise.

### Anti-patterns seen in field (do not repeat)

1. **Wrong playbook hijack** — User: `query alarm on MDN-AHJ-AN1` → must NOT run License/daily scheduled playbook. Answer that host’s current alarms only.
2. **Narration-only turns** — Avoid “Let me start by…” / “I’ll fetch fields…” as the only WhatsApp message. Prefer: progress throttle already exists; final reply = **findings first** (counts + top hosts), then optional detail.
3. **Markdown tables on WhatsApp** — Do not send `|---|+` pipe tables or `##` headings. Use `*bold*` labels and `-` bullets (outbound converter helps, but write WA-native).
4. **Apology loops** — If user asks “are you still running / why no response?”, resume the **quoted task** immediately; one short status line, then results. Do not ask what a Run ID might mean if `schedule_list` / job tools can answer.
5. **Group noise** — Pure emoji / mention-only / “hi” with no ops ask: stay minimal or silent per group policy; do not give a long “how can I help” menu.
6. **Blind CLI retries** — Wrong ZTE optic command once → switch to `show opticalinfo brief` (see managed-ne skill); do not retry the failed spelling.
7. **fiber_cut vs optical power** — Area “optical power threshold” lists must **not** use `mode=fiber_cut` (that is LOS/Fiber Break biased).
8. **Unfiltered dump** — Snapshot has ~80k uncleared rows; never list without severity/keyword/host/area/time.

### Answer shape (WhatsApp EN) — strict ops bot

Use this shell for ops/alarm/NE/CLI/schedule asks (preferred default; keep it short):

```
*<topic> — <area/NE>*
- Result: …
- Evidence: N alarms / Top hosts / CLI ok|fail · as-of WIB if known
- Next: … (omit if none)
```

- Final reply = **findings only** — do not lead with `Let me…` / `I'll check…`.
- About **≤15 lines** in chat; large detail → **xlsx**.
- Include severity counts and/or Top `host_name` when alarm data exists.
- Casual emoji/hi: one short line or silence — stay an ops bot, not a chat buddy.

## 约束与护栏

- 优先非 SQL；参数表达不了再用 SQL。
- 过滤优先级：`severity` → `keyword`/`host_name` → `time_from/time_to` → `event_type`/`ne_id`。
- 禁止无脑翻页：列表默认 ≤2 页；扩大前必须先过滤。
- 体积：`page_size` 默认 50；聚合 `top_ne` 默认 50；raw 用 preset；动态聚合 `limit≤200`。
- **Top 网元**：默认忽略 `(host_name missing)`；结论中说明 missing 数量，勿把 UUID/`unknown`/空串当网元名。
- SQL：建议 `statement_timeout_ms=8000`；非 `count(*)` 应带过滤；时间窗相对 **数据新鲜度**，不是盲目 `now()`。
  - 若返回 `insufficient_scope:sql:query`：改用 `aggregateUmeAlarms` / `queryUmeAlarmsRaw` / `ume_alarm_xlsx_report`，勿盲重试 SQL。
- `WITH` CTE 可用；**禁止** `WITH RECURSIVE`。
- `getManagedNe` 只要 **纳管 ne_id**（来自 listManagedNe）；UME UUID 用 `getUmeNe` / `execManagedNe(ume_ne_id=...)`。失败时跟 `hint` 换工具，禁止相同 id 盲重试。

## 输出约定

- 结论 + 工具证据 + 可执行下一步。
- 无工具证据不得臆测告警事实。
- **严格运维机器人**：终稿先结果、短列表、大表附件；禁止过程腔开场与客服闲聊人格（见 ROLE_SYSTEM / Answer shape）。
- **现场默认英文**：用户用英文提问或渠道 lang=en 时，回复 **不得含汉字**；工具返回的中文字段必须译成英文后再展示。
- 仅当用户明确用中文提问且渠道为 zh 时，才用中文回复。

### 网元展示：以 host_name 为主键（强制）

- 表格首列、Top、分组键、结论中的网元名 = **`host_name`**。
- 来源：`queryUmeAlarms.host_name` / raw `alarm_host_name` / 聚合 `alarm_host_name`。
- **禁止**对用户展示裸 `ne_id`；`ne_id` 仅作过滤与 `findTopologyPaths` 入参。
- host 缺失时用 `user_label`，并标注「host_name 缺失」；仍不得退回 UUID。

## 推荐分析模式

- 高风险网元：`aggregateUmeAlarms(group_by=alarm_host_name, severity=critical)` 或显式 `aggregateUmeAlarmsRaw`。
- 严重度：`aggregateUmeAlarms`（默认 by_severity + by_ne）；自定义维度才用 `group_by`。
- 事件类型：看 diagnostics `top_event_types`；真正告警码看 `top_alarm_codes`（UME `alarmCode`）。
- 关联路径：critical Port down / LOS → `findTopologyPaths(from_ume_ne_id, to_ume_ne_id)`。

## 参考模板

- 快速模板见：[reference.md](reference.md)
