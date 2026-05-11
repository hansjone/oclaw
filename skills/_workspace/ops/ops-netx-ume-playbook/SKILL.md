---
name: ops-netx-ume-playbook
description: 面向 ops 专家的 netx UME 运维作业手册。覆盖告警查询/聚合/诊断、网元清单与单网元详情、raw 字段过滤与 UME 只读 SQL。
---

# Ops Netx UME 作业手册

## 强制使用范围

凡是涉及 netx/UME **告警**或 **网元信息** 的 ops 请求，必须优先加载并遵循本技能。

## 工具选择顺序

1. 基础视图（先看整体）：
   - `netx_query_ume_alarms`
   - `netx_aggregate_ume_alarms`
   - `netx_run_ume_diagnostics`
2. 字段感知深查（需要细节）：
   - `netx_list_ume_alarm_fields`
   - `netx_query_ume_alarms_raw`（优先使用 `select_fields` 控制返回字段）
3. 自定义聚合（非 SQL）：
   - `netx_aggregate_ume_alarms_raw`（`group_by`，可选 `group_by2`）
4. 高级分析（SQL）：
   - `netx_sql_query_ume`（仅 SELECT、仅 UME 表；重查询建议设置 `statement_timeout_ms`）
5. **网元（inventory，与 netx「网元清单」同源）**：
   - 列表/搜索：`netx_query_ume_ne_inventory`（`keyword` + 分页）
   - 单条详情（含 `raw_json`）：`netx_get_ume_ne`（`ne_id` = UUID）

## 快速决策树（强推荐）

- **只需要整体态势 / Top 风险 / 快速简报**：
  - 先 `netx_aggregate_ume_alarms` + `netx_run_ume_diagnostics`
  - 必要时再用 `netx_query_ume_alarms` 看前 1 页做样本核对
- **需要“可引用证据”的具体告警明细**：
  - 先 `netx_list_ume_alarm_fields`
  - 再 `netx_query_ume_alarms_raw`，并用 `select_fields` 只取必要字段
- **需要按任意字段做统计（但不想写 SQL）**：
  - `netx_aggregate_ume_alarms_raw`（`group_by` / `group_by2`）
- **需要复杂条件 / 自定义计算 / 多条件关联**：
  - `netx_sql_query_ume`（必须过滤 + `statement_timeout_ms`）
- **查网元是谁、IP/标签、在线状态、或核对告警里的 ne_id**：
  - 先 `netx_query_ume_ne_inventory`（`keyword` 可填名称片段或 UUID 片段）
  - 需要完整字段与 `raw_json` 时再 `netx_get_ume_ne`

## 约束与护栏

- 优先使用非 SQL 工具；仅当工具参数无法表达需求时再用 SQL。
- 默认过滤优先级（先收敛再扩展）：
  - 首选：`severity`（先把问题缩小到 critical/major 等）
  - 其次：`keyword`（网元名/标签/IP/对象名/告警关键字）
  - 再次：`time_from/time_to`（按 `last_seen_at` 限定时间窗）
  - 最后：`event_type` 或 `ne_id`（当你明确知道要锁定事件类型/网元时）
- 禁止“为了凑全量而无脑翻页”：
  - `netx_query_ume_alarms` 默认只看前 1 页（必要时最多 2 页）
  - 如需更多数据，必须先明确过滤条件（`severity/ne_id/keyword/time_from/time_to/event_type` 等）或改用聚合/SQL
- 控制响应体积：
  - 默认 `page_size=50`（除非明确需要更多，否则不要上来就拉满 500）
  - 动态聚合默认 `limit=200`
  - 合理设置 `page_size`
  - raw 查询尽量传 `select_fields`；或使用 `field_preset=brief/evidence/ne_debug`
  - 先加过滤条件，再增大分页范围
- 时间窗过滤默认基于 `last_seen_at` 语义，除非需求明确要求其它口径。
- 若数据新鲜度不明确，先查看 runtime 锚点状态，再下结论。
- SQL 使用规则（`netx_sql_query_ume`）：
  - 建议总是设置 `statement_timeout_ms`（例如 3000~10000）
  - 推荐默认从 `statement_timeout_ms=8000` 开始
  - 除非只是 `count(*)`，否则应包含过滤条件（至少时间窗或 `ne_id`/严重度过滤），避免全表扫描

## 输出约定

- 输出必须包含：
  - 简明结论
  - 证据依据（工具输出）
  - 可执行下一步
- 没有工具证据时，不得臆测告警事实。

## 推荐分析模式

- 高风险网元：`netx_aggregate_ume_alarms_raw` + `group_by=ne_user_label` + 严重度过滤。
- 严重度分布：`group_by=alarm_perceived_severity`。
- 事件趋势切片：raw 查询中组合 `time_from/time_to` + `event_type`。

## 参考模板

- 快速模板见：[reference.md](reference.md)
