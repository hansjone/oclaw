---
name: ops-netx-managed-ne-playbook
description: 面向 ops 专家的 netx 纳管网元（网元管理）作业手册。覆盖设备清单、连通状态、经 netx 登录设备执行只读 CLI。
---

# Ops Netx 纳管网元作业手册

## 强制使用范围

凡是需要在 **netx 网元管理** 中已录入的设备上**登录并查询**（show/display/ping 等）时，必须加载并遵循本技能。

与 UME 网元清单（`ops-netx-ume-playbook`）不同：本手册针对 **SSH/Telnet 纳管设备**（含 ZTE/华为/思科跳板），不是 UME REST 同步清单。

## 工具选择顺序

优先 **MCP**（`mcp__netx__*`）。legacy：`netx_list_managed_ne` 等（`OCLAW_NETX_BUILTIN_TOOLS=1`）。

1. **定位设备**
   - `mcp__netx__listManagedNe`：`keyword`、`connect_status=pass`
   - `mcp__netx__getManagedNe`：单条详情、`connect_detail`
2. **登录查信息**
   - `mcp__netx__execManagedNe`：`ne_id` + `commands`（最多 5 条只读命令）

## CLI 约束（服务端强制）

- 允许前缀：`show `、`display `、`get `、`ping `、`traceroute `、`terminal length `、`?`
- 禁止：`|`、`;`、换行拼接、改配置类（configure/write/copy/reload/delete 等）
- 示例：
  - 思科：`show version`、`show configuration | include hostname` **不可**（含 `|`）→ 改用 `show configuration` 或连通测试已解析的 hostname
  - 华为：`display version`、`display interface brief`
  - ZTE：`show version`、`show interface`

## 排障流程

1. `connect_status` 为 `fail`：先 `netx_get_managed_ne` 阅读 `connect_detail`，勿反复盲 exec
2. 设备经跳板：详情中确认 `hop_enabled`、`hop_vendor`、模板是否正确
3. 超时：对慢命令提高 `read_timeout_sec`（最大 120），或减少单次命令条数

## 输出约定

- 结论 + **工具返回 output 摘录**（勿编造 CLI 结果）
- 标明 `ip_address`、`name`、`ne_id`（对用户展示优先 name/IP，ne_id 作关联键）
- 英文会话：用户可见回复不得含汉字（CLI 原文可摘录但需说明为设备原文）
