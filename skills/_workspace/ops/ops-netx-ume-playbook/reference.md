# Ops Netx UME 快速参考

## 0) 数据新鲜度（必做）

- `runUmeDiagnostics` / `aggregateUmeAlarms` → `meta.last_seen_min` / `last_seen_max`
- 快照数据：时间窗落在 min~max 内；**不要**默认 `now()-30 minutes`

## 1) 当前告警明细（轻量）

- 工具：`queryUmeAlarms`
- 参数：`severity`, `host_name`, `ne_id`(仅过滤), `keyword`, `time_from`, `time_to`, `page`, `page_size`
- 建议：`page_size=50`；默认最多 2 页

## 2) 原始明细（证据）

- 工具：`queryUmeAlarmsRaw`
- 先 `listUmeAlarmFields`（可选）
- `field_preset`：`brief` / `evidence` / `ne_debug`
- 展示主键：`alarm_host_name`（首列）

## 3) 聚合

- `aggregateUmeAlarms`：`severity`(可选，如 critical)、`top_ne`(默认50)、`exclude_missing_host`(默认true)、`time_from`/`time_to`
  - 高危 Top：`severity=critical`；看 `by_ne_missing`；Top 默认不含 missing
  - **也可传 `group_by=alarm_host_name`**：自动走动态聚合（等同 `aggregateUmeAlarmsRaw`）
- `aggregateUmeAlarmsRaw`：`group_by=alarm_host_name` 等；按 host 分组时默认排除 missing（`by_ne_missing`）

## 3b) WhatsApp 最短路径

| 意图 | 调用 |
|------|------|
| Critical Top | `aggregateUmeAlarms(severity=critical, top_ne=20)` |
| 按 host 统计+Excel | `ume_alarm_xlsx_report(mode=aggregate_by_host, severity=critical)` |
| 断纤/离线清单+Excel | `ume_alarm_xlsx_report(mode=fiber_cut\|offline)` |
| 发 Excel（已有表数据） | `write_xlsx(..., deliverable=true)` |

## 4) 诊断

- `runUmeDiagnostics`
- `top_event_types`：事件类型
- `top_alarm_codes`：UME `alarmCode`（有则）
- `top_ne`：已排除 missing host
- `meta.last_seen_*`：新鲜度

## 4b) 网元清单

- `queryUmeNeInventory(keyword=…)`
- `getUmeNe(ne_id=UUID)` — 仅内部关联 / raw_json

## 4c) 拓扑路径（告警关联）

- `findTopologyPaths`
  - `from_ume_ne_id` + `to_ume_ne_id`（来自告警 `ne_id`）
  - 或 managed 侧 `from_managed_ne_id` / `to_managed_ne_id`
  - 默认 `detail=summary`：看 `paths[].label`（含端口）与精简 nodes/edges；需要 attrs 时再 `detail=full`
- 返回最短路径优先；0 条路径也要说明，再考虑 CLI

## 5) SQL

- `sqlQueryUme`；表：`ume_alarms_current` / `ume_inventory_ne`
- `statement_timeout_ms=8000`
- 时间窗相对 `meta.last_seen_max`，示例：
```sql
select coalesce(nullif(trim(a.host_name), ''), '(host_name missing)') as host_name,
       count(*) as alarm_count
from ume_alarms_current a
where a.last_seen_at >= timestamp '2026-08-07 00:00:00'
  and lower(coalesce(a.perceived_severity, '')) in ('critical','major')
group by 1
order by alarm_count desc
limit 50
```

## 6) 登设备

- 见 `ops-netx-managed-ne-playbook`
- UME `ne_id` → `listCliTargets` / `execManagedNe(ume_ne_id=…)`（需已配 UME→CLI）
