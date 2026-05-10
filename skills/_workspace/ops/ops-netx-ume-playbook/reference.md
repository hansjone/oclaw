# Ops Netx UME 快速参考

## 1) 当前告警明细（轻量入口）

- 工具：`netx_query_ume_alarms`
- 常用参数：
  - `severity`, `ne_id`, `keyword`, `page`, `page_size`
- 建议：
  - 推荐 `page_size=50`
  - 默认只看前 1 页（必要时最多 2 页），不要无脑翻页拉全量

## 2) 原始明细（字段可控，推荐用于证据输出）

- 工具：`netx_query_ume_alarms_raw`
- 推荐流程：
  - 先调用 `netx_list_ume_alarm_fields` 获取字段清单
  - 再用 `select_fields` 控制返回字段，减少输出体积
- 字段集预设（推荐优先用 preset，避免手写字段列表）：
  - `field_preset=brief`：轻量概览（严重度/事件/最近时间/网元显示）
  - `field_preset=evidence`：证据输出（含 object/cause/时间/网元状态）
  - `field_preset=ne_debug`：定位网元信息缺失或状态异常
- `select_fields` 示例：
  - `alarm_alarm_key`
  - `alarm_perceived_severity`
  - `alarm_last_seen_at`
  - `ne_user_label`
  - `ne_ip_address`

## 3) 动态聚合（非 SQL）

- 工具：`netx_aggregate_ume_alarms_raw`
- 常用分组：
  - `group_by=alarm_perceived_severity`
  - `group_by=ne_user_label`
  - `group_by=alarm_event_type`
  - `group_by=ne_connection_status`
  - `group_by=alarm_perceived_severity, group_by2=ne_user_label`
- 建议：
  - 推荐 `limit=200`

## 4) 诊断摘要

- 工具：`netx_run_ume_diagnostics`
- 用途：在深挖前先快速形成“概览简报”（严重度、Top 网元、Top 事件类型等）

## 5) SQL 深度分析（受限）

- 工具：`netx_sql_query_ume`
- 约束：
  - 仅允许 SELECT
  - 仅允许表：`ume_alarms_current` / `ume_inventory_ne`
  - 重查询务必设置 `statement_timeout_ms`
  - 除非只是 `count(*)`，否则建议带时间窗（例如 `last_seen_at >= now() - interval '30 minutes'`）
- 示例（全量聚合，谨慎使用）：
```sql
select
  coalesce(ne.user_label, ne.ne_name, a.ne_id) as ne_display,
  count(*) as alarm_count
from ume_alarms_current a
left join ume_inventory_ne ne on ne.ne_id = a.ne_id
group by coalesce(ne.user_label, ne.ne_name, a.ne_id)
order by alarm_count desc
```

- 示例（推荐：带时间窗 + 超时）：
  - `statement_timeout_ms=8000`
```sql
select
  coalesce(ne.user_label, ne.ne_name, a.ne_id) as ne_display,
  count(*) as alarm_count
from ume_alarms_current a
left join ume_inventory_ne ne on ne.ne_id = a.ne_id
where a.last_seen_at >= now() - interval '30 minutes'
group by coalesce(ne.user_label, ne.ne_name, a.ne_id)
order by alarm_count desc
```

- 示例（推荐：带时间窗 + 严重度过滤，现场最常用）：
  - `statement_timeout_ms=8000`
```sql
select
  coalesce(ne.user_label, ne.ne_name, a.ne_id) as ne_display,
  count(*) as alarm_count
from ume_alarms_current a
left join ume_inventory_ne ne on ne.ne_id = a.ne_id
where a.last_seen_at >= now() - interval '30 minutes'
  and lower(coalesce(a.perceived_severity, '')) in ('critical','major')
group by coalesce(ne.user_label, ne.ne_name, a.ne_id)
order by alarm_count desc
```
