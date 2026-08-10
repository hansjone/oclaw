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

旧名 `netx_query_ume_alarms` 等仅在 `OCLAW_NETX_BUILTIN_TOOLS=1` 时可用；**优先 MCP**。

## 工具选择顺序

1. **新鲜度（先做）**：`runUmeDiagnostics` 或 `aggregateUmeAlarms` → 看 `meta.last_seen_min` / `last_seen_max`。  
   - 若最大值远早于「现在」，按 **快照数据** 处理：时间窗用数据范围内的日期，禁止套 `now()-30 minutes`。
2. 基础视图：`aggregateUmeAlarms` + `runUmeDiagnostics`；样本用 `queryUmeAlarms`（默认 1 页）。
3. 证据明细：`listUmeAlarmFields` → `queryUmeAlarmsRaw`（`field_preset=evidence` / `select_fields`）。
4. 自定义聚合：`aggregateUmeAlarmsRaw`（`group_by=alarm_host_name` 等）。
5. SQL：`sqlQueryUme`（仅 SELECT；设 `statement_timeout_ms`）。
6. **告警关联拓扑**：两台相关网元取 `ne_id` → `findTopologyPaths`（最短路径优先）。
7. **登设备查 CLI**：见 `ops-netx-managed-ne-playbook`（`listCliTargets` / `execManagedNe`）。

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

## WhatsApp 短指令配方（强制少工具）

群聊短句（中/英）优先走下列固定路径，**目标 ≤3 次工具调用**，不要先翻页/反复 listCliTargets。

| 用户说法（例） | 配方 |
|----------------|------|
| 断纤 / fiber cut / LOS / 光缆中断 | **优先** `ume_alarm_xlsx_report(mode=fiber_cut)`（一键 xlsx+投递）；或 `queryUmeAlarmsRaw` 后摘要 |
| 离线 / 单板离线 / offline NE | **优先** `ume_alarm_xlsx_report(mode=offline)` |
| Critical Top / 告警统计 | ① `aggregateUmeAlarms(severity=critical, top_ne=20)`；要文件：`ume_alarm_xlsx_report(mode=aggregate_by_host, severity=critical)` |
| 当前告警有多少 / tally | ① `runUmeDiagnostics` 或 `aggregateUmeAlarms`；② 直接报 by_severity + freshness |
| 导出 Excel / 发我表格 | `ume_alarm_xlsx_report` **或** `write_xlsx(..., deliverable=true)`；勿再拆成 3 步 |

交付约定：
- `ume_alarm_xlsx_report` 默认 `deliverable=true`，WhatsApp 可直接收文件。
- 通用表格：`write_xlsx(..., deliverable=true)` 可跳过 `save_deliverable_attachment`。
- 禁止用 `run_command`+openpyxl 造 xlsx。
- 确认类短句（YES / confirm / 继续）：承接上一任务继续，勿重新开查。

## 约束与护栏

- 优先非 SQL；参数表达不了再用 SQL。
- 过滤优先级：`severity` → `keyword`/`host_name` → `time_from/time_to` → `event_type`/`ne_id`。
- 禁止无脑翻页：列表默认 ≤2 页；扩大前必须先过滤。
- 体积：`page_size` 默认 50；聚合 `top_ne` 默认 50；raw 用 preset；动态聚合 `limit≤200`。
- **Top 网元**：默认忽略 `(host_name missing)`；结论中说明 missing 数量，勿把 UUID/`unknown`/空串当网元名。
- SQL：建议 `statement_timeout_ms=8000`；非 `count(*)` 应带过滤；时间窗相对 **数据新鲜度**，不是盲目 `now()`。
- `WITH` CTE 可用；**禁止** `WITH RECURSIVE`。

## 输出约定

- 结论 + 工具证据 + 可执行下一步。
- 无工具证据不得臆测告警事实。
- 英文提问：回复不得含汉字；工具中文字段须译成英文。

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
