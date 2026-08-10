---
name: ops-netx-managed-ne-playbook
description: 面向 ops 专家的 netx 纳管网元（网元管理）作业手册。覆盖设备清单、连通状态、经 netx 登录设备执行只读 CLI。
---

# Ops Netx 纳管网元作业手册

## 强制使用范围

凡是需要在 **netx 网元管理** 中已录入的设备上**登录并查询**（show/display/ping 等）时，必须加载并遵循本技能。

与 UME 网元清单（`ops-netx-ume-playbook`）不同：本手册针对 **SSH/Telnet 纳管设备**（含 ZTE/华为/思科跳板、Linux SSH 隧道、堡垒机协议代理），不是 UME REST 同步清单。

## 工具选择顺序

优先 **MCP**（`mcp__netx__*`）。legacy：`netx_list_managed_ne` 等（`OCLAW_NETX_BUILTIN_TOOLS=1`）。

1. **定位设备**
   - `mcp__netx__listManagedNe`：`keyword`、`connect_status=pass`（**首选定位**）
   - `mcp__netx__getManagedNe`：仅当需要单条 `connect_detail` 时调用；**入参必须是纳管 ne_id**（来自 listManagedNe / listCliTargets `source=managed`）
   - **禁止**把告警/UME 的 UUID 当 `getManagedNe` 的 `ne_id`；失败时跟返回 `hint`：改 `listManagedNe` / `getUmeNe` / `execManagedNe(ume_ne_id=...)`，禁止相同参数盲重试
   - **UME 清单（无需逐台纳管）**：`mcp__netx__listCliTargets`（`source=ume`）或 `queryUmeNeInventory` 取 `ne_id`，再用 `ume_ne_id` 执行 CLI（需先在 netx **UME → CLI 连接** 配置统一凭据/跳板）
2. **登录查信息**
   - `mcp__netx__execManagedNe`：`ne_id` **或** `ume_ne_id` + `commands`（默认最多 5 条，可由 `NETX_NE_EXEC_MAX_COMMANDS` 调高，硬上限 50）
   - **多台同命令（推荐）**：一次调用传 `ne_ids` / `ume_ne_ids`（或 `targets`）+ 共享 `commands`，服务端并发执行（默认 concurrency=4，最多 20 台）。禁止对同一 show 命令逐台循环 `execManagedNe`
   - **一次会话内**：`listCliTargets` 最多调用一次，缓存返回的 id；多条 show 合并进同一次 `commands`，禁止「list→exec→list→exec」循环
   - 超时：提高 `read_timeout_sec`（默认 60，慢命令 90–120）或减少命令条数，禁止对同一命令盲重试

## Field link recipes (WhatsApp EN)

### Capacity / optical power between two names

When user says **capacity**, **bandwidth between A and B**, or **optical power A <> B** (prod vocabulary):

1. Resolve nicknames → real `host_name` via inventory/wiki (`SEMBAWA` → e.g. `PLG-SMW-EN1-…`).
2. Find interconnect: `findTopologyPaths` and/or LLDP (`show lldp …` / vendor equivalent) — identify **both ports**.
3. Read optics on **both** ends with the correct vendor command (below). Summarize: interface, RX/TX power, threshold, whether link is up.
4. Do **not** answer with only UME bandwidth-usage-rate alarms unless the user asked for congestion alarms.

### ZTE optical CLI (prod corrections)

Try in order; **one failure → switch command, do not retry the same spelling**:

| Prefer | Fallback / notes |
|--------|------------------|
| `show opticalinfo brief` | Field-confirmed on ZXR10 (e.g. ANGKATAN / `PLG-A45-…`) |
| `show optical brief` | Some EN platforms |
| `show opticalinfo brief \| begin <if>` | Narrow to one interface after port known |

Cisco/Huawei: use `show interface transceiver` / `display optical-module` style allowlisted commands as applicable.

### Multi-NE same show

Prefer `execManagedNe(ume_ne_ids=[…], commands=[…])` once. Cap to the NEs on the asked path (usually 2).

## CLI 约束（服务端强制）

- 允许前缀：`show `、`display `、`ping `、`ping6 `、`traceroute `、`tracert `、`trace `、`trace6 `
- 管道：仅白名单过滤（`include`/`exclude`/`begin`/`section`/`count`/`match`/`grep`/`one-line`/`no-more`）；禁止 `redirect`/`append`/`tee`/`send`
- 禁止：`;`、换行拼接、改配置类（configure/write/copy/reload/delete 等）
- 示例：
  - 思科：`show version`、`show configuration | include hostname`
  - 华为：`display version`、`display current-configuration | include sysname`
  - ZTE：`show version`、`show interface`
  - 连通：`ping 192.168.0.1`、`ping6 2001::db8::1`、`traceroute 10.0.0.1`

## 排障流程

1. `connect_status` 为 `fail`：先 `netx_get_managed_ne` 阅读 `connect_detail`，勿反复盲 exec
2. 设备经跳板：详情中确认 `hop_enabled`、`hop_vendor`、模板是否正确
   - **堡垒机**（`hop_vendor=bastion`）：检查 `hop_host`、`hop_port`（常见 22 或 2222）、`hop_username`、用户名模板渲染是否为 `{堡垒机用户}@{目标用户}@{目标IP}@{堡垒机地址}`（例：`bastion-user@target-user@2.2.2.2@1.1.1.1`）；`hop_target_auth_mode=bastion_managed` 时目标密码在堡垒机侧，netx 可不存目标密码
3. 超时：对慢命令提高 `read_timeout_sec`（最大 120），或减少单次命令条数

## 输出约定

- 结论 + **工具返回 output 摘录**（勿编造 CLI 结果）
- 标明 `ip_address`、`name`、`ne_id`（对用户展示优先 name/IP，ne_id 作关联键）
- 英文会话：用户可见回复不得含汉字（CLI 原文可摘录但需说明为设备原文）
