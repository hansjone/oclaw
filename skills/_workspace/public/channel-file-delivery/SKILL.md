---
name: channel-file-delivery
description: "在 WhatsApp/微信等渠道会话中，把生成的文件作为附件发回用户的流程。适用于：导出 Excel/CSV/TXT、run_command 生成报告后需要让用户在聊天里收到文件。"
---

# 渠道文件发送 — Channel File Delivery

## 何时使用

用户在 **WhatsApp / 微信** 等渠道对话中，要求你生成并**把文件发给他**（不仅是文字说明路径）。

## 关键规则

1. **`write_file` / `run_command` 不会自动发送附件**  
   文件只会落在 workspace 磁盘上，渠道出站看不到。

2. **必须调用 `save_deliverable_attachment`**  
   在文件生成完成后，用该工具把 workspace 文件注册到 attachment store，并标记 `deliverable`。

3. **再用简短文字回复**  
   说明文件名与要点；系统会把标记为 deliverable 的附件随本条回复发到渠道。

## 推荐流程

```text
1. run_command 或 write_file → 生成 data/workspace/tmp/report.xlsx
2. save_deliverable_attachment(path="data/workspace/tmp/report.xlsx", name="report.xlsx")
3. 文字回复：「已附上 report.xlsx，共 N 行…」
```

## Excel 示例

```text
用户：帮我把统计结果导出 Excel 发我

步骤：
1. run_command：用 pandas 写入 data/workspace/tmp/summary.xlsx
2. save_deliverable_attachment(path="data/workspace/tmp/summary.xlsx")
3. 回复摘要（行数、主要结论）
```

## 限制

- 每轮回复通常只发送**第一个**附件（约 8MB 上限）。
- 超大文件应压缩、抽样或只发摘要。
- 用户**上传**的文件不要用 `save_deliverable_attachment` 回传；那是分析输入，不是生成输出。

## 相关

- 路径规范见 `path-convention` skill（`data/workspace/`）。
- 分析用户上传的表格用 `query_tabular_attachment` 等读工具，与出站发送无关。
