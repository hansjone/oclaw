---
name: channel-file-delivery
description: "在 WhatsApp/微信等渠道会话中，把生成的文件作为附件发回用户。区分：write_file 仅文本（csv/txt）；xlsx 等二进制用 run_command + save_deliverable_attachment。"
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

## 工具选择（文本 vs 二进制）

| 目标格式 | 用哪个工具 | 说明 |
|----------|------------|------|
| `.csv`、`.txt`、`.md`、`.json` 等纯文本 | `write_file` | 只能写文本内容，不能生成二进制 |
| `.xlsx`、`.xls` 等 Excel | `run_command` | 用 Python（`openpyxl` 已安装）在 workspace 里生成 |
| 其他需脚本/命令产出的文件 | `run_command` | 生成后再走 deliverable 流程 |

**不要声称没有 `run_command`。** 若用户要真 `.xlsx`，优先用 `run_command` 生成，不要只用 `write_file` 写 CSV 再说是「限制」。

## 推荐流程

**文本文件（CSV/TXT）：**

```text
1. write_file → data/workspace/tmp/report.csv
2. save_deliverable_attachment(path="data/workspace/tmp/report.csv", name="report.csv")
3. 文字回复：「已附上 report.csv…」
```

**Excel（xlsx）：**

```text
1. run_command → python 写入 data/workspace/tmp/report.xlsx
2. save_deliverable_attachment(path="data/workspace/tmp/report.xlsx", name="report.xlsx")
3. 文字回复：「已附上 report.xlsx…」
```

## Excel 示例

```text
用户：帮我把统计结果导出 Excel 发我

步骤：
1. run_command（示例）：
   python -c "from openpyxl import Workbook; wb=Workbook(); ws=wb.active; ws.append(['姓名','数量']); ws.append(['A',10]); wb.save('data/workspace/tmp/summary.xlsx')"
2. save_deliverable_attachment(path="data/workspace/tmp/summary.xlsx", name="summary.xlsx")
3. 回复摘要（行数、主要结论）
```

用户明确要 `.xlsx` 时，不要退化成只发 CSV，除非用户同意用 CSV 代替。

## 限制

- 每轮回复通常只发送**第一个**附件（约 8MB 上限）。
- 超大文件应压缩、抽样或只发摘要。
- 用户**上传**的文件不要用 `save_deliverable_attachment` 回传；那是分析输入，不是生成输出。

## 相关

- 路径规范见 `path-convention` skill（`data/workspace/`）。
- 分析用户上传的表格用 `query_tabular_attachment` 等读工具，与出站发送无关。
