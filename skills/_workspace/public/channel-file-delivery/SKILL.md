---
name: channel-file-delivery
description: "在 WhatsApp/微信等渠道会话中，把生成的附件发回用户。所有类型（文档/图片/视频）均需 save_deliverable_attachment（path 或 attachment_id）。"
---

# 渠道文件发送 — Channel File Delivery

## 何时使用

用户在 **WhatsApp / 微信（wechat/weixin）** 等渠道对话中，要求你生成并**把附件发给他**（文档、图片、视频等，不仅是文字说明路径）。渠道附件规则在系统提示中已注入，无需在每轮用户消息里重复。

## 关键规则（统一）

1. **生成工具不会自动发送附件**  
   `write_xlsx`、`write_file`、`run_command`、`cloudflare_image_generate` 等只产生内容，渠道出站看不到。

2. **必须调用 `save_deliverable_attachment`**  
   生成完成后用该工具标记 `deliverable`，系统才会随回复发送。

3. **再用简短文字回复**  
   说明文件名或要点。

| 生成方式 | `save_deliverable_attachment` 参数 |
|----------|--------------------------------------|
| `write_xlsx` / 生图等（已有 attachment_id） | `attachment_id="..."` |
| workspace 文件（csv/txt 等） | `path="data/workspace/..."` |

**用户上传的文件不要回传**；那是分析输入，不是生成输出。

## 工具选择（文本 vs Excel vs 二进制）

| 目标格式 | 用哪个工具 | 说明 |
|----------|------------|------|
| `.xlsx` Excel | **`write_xlsx`** | 传 sheets/headers/rows；返回 `attachment_id`；**禁止**再用 `run_command`+openpyxl |
| `.csv`、`.txt`、`.md`、`.json` 等纯文本 | `write_file` | 只能写文本内容 |
| 图片 | `cloudflare_image_generate` 等 | 生成后用 `attachment_id` 标记 |
| 视频 | 对应生成工具 | 生成后用 `attachment_id` 标记 |

**不要声称没有 `write_xlsx`。** 用户要真 `.xlsx` 时必须用 `write_xlsx`，不要只写 CSV 代替。

## 推荐流程

**Excel（xlsx）— 优先：**

```text
1. write_xlsx(sheets=[...], name="report.xlsx") → 得到 attachment_id
2. 若用户要求发文件：save_deliverable_attachment(attachment_id="...")
3. 文字回复摘要
```

**文本文件（CSV/TXT）：**

```text
1. write_file → data/workspace/tmp/report.csv
2. save_deliverable_attachment(path="data/workspace/tmp/report.csv", name="report.csv")
3. 文字回复
```

**图片：**

```text
1. cloudflare_image_generate → 得到 attachment_id
2. save_deliverable_attachment(attachment_id="...")
3. 文字回复
```

## Excel 示例

```text
用户：帮我把统计结果导出 Excel 发我

步骤：
1. write_xlsx:
   name="summary.xlsx"
   sheets=[{
     "name": "汇总",
     "headers": ["姓名", "数量"],
     "rows": [["A", 10], ["B", 3]]
   }]
2. save_deliverable_attachment(attachment_id=<上一步返回的 attachment_id>)
3. 回复摘要
```

若只需在 workspace 留一份副本（不投递），可额外传 `path="data/workspace/tmp/summary.xlsx"`；**是否发给渠道仍由你决定是否调用 save_deliverable_attachment**。

## 限制

- 每轮回复通常只发送**第一个** deliverable 附件（约 8MB 上限）。
- 超大文件应压缩、抽样或只发摘要。

## 相关

- 路径规范见 `path-convention` skill（`data/workspace/`）。
- 分析用户上传的表格用 `query_tabular_attachment` 等读工具，与出站发送无关。
