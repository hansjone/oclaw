---
name: scheduled-workflows
description: "把复杂/多步工作固化成定时 Workflow Recipe：先 schedule_propose 出草稿给用户确认，再 schedule_create。Recipe 必须自包含——到点执行时没有原对话，LLM 仅凭 recipe 仍能正确完成任务。"
---

# 定时工作流 — Scheduled Workflows

## 何时使用

用户想把**刚才引导完成的多步任务**做成周期执行（例如「做成每周一 9 点的定时」「按刚才那套流程每天跑」），或创建会产出文件/报告的定时任务。

简单一句提醒（「每三小时提醒我喝水」）**不要**用本流程，直接 `schedule_create` + 短 `prompt_text` 即可。

## 最重要：自包含（无上下文仍可执行）

到点触发时，worker **不会**把「当时那通聊天」当成任务说明。LLM 几乎只看到 `recipe` 编译出的内部指令（外加可能截断的会话噪声）。

因此写入的 recipe / 步骤文案必须满足：

> **一个陌生的 LLM 在没有原对话、没有「刚才」「那个」指代的情况下，仍能正确理解并完成任务。**

### 禁止写入（指代 / 依赖上文）

- 「继续刚才那个」「按上面流程」「和上次一样」
- 「用用户给的那个文件」「那个模板」——却不写清路径/文件名/字段
- 「参考本会话里刚生成的报告」——却不把关键结论、参数、路径抄进 recipe
- 步骤短到只有动词：「处理数据」「发一下」

### 必须写入（自包含要素）

- **做什么**：具体目标与交付物（文件类型、发给谁、消息长什么样）
- **怎么做**：可逐步执行的步骤（工具/命令/数据源/命名规则）
- **用什么**：路径、URL、表名、模板内容或固定参数 → 放进 `inputs.constants`
- **边界**：不要动什么、失败怎么处理 → `constraints`
- **怎样算完成**：可检查的成功标准 → `success_criteria`

写完后自检一句：**「若只有这份 recipe、清空聊天记录，新模型能否一次做对？」** 不能则补字段，禁止提交。

## 任务模板（标准样例，照此展开）

新建复杂定时任务时，**按下面模板填满**再 `schedule_propose`。括号内是说明，写入时换成真实内容。

```json
{
  "version": 1,
  "goal": "【一句话完整目标】例如：每周一 09:00 汇总上一自然周值班告警，生成 PDF 发到当前 WhatsApp 群并 @值班人",
  "steps": [
    "【步骤1·取数】说明数据从哪来：接口/命令/文件路径、时间范围如何算（上周一 00:00 至周日 23:59，时区 Asia/Shanghai）",
    "【步骤2·处理】说明过滤规则、分组字段、统计口径；需要生成的中间文件路径（如 data/workspace/tmp/duty_weekly.csv）",
    "【步骤3·产出】说明最终交付物格式与路径（如 data/workspace/tmp/duty_weekly_YYYYMMDD.pdf）；标题/章节结构写清",
    "【步骤4·投递】调用 save_deliverable_attachment 发送 PDF；渠道消息须含：周期范围、总数、Top3 风险、是否需人工跟进；若需 @人写清展示名与用途"
  ],
  "constraints": [
    "【边界】只读该数据源，不修改生产配置/历史文件",
    "【失败】取数失败则渠道只发失败原因摘要，不假装成功、不发空 PDF"
  ],
  "success_criteria": [
    "群内收到本周 PDF 附件",
    "消息正文含统计周期与至少一条结论或风险点",
    "无未说明的错误/半成品路径糊弄用户"
  ],
  "inputs": {
    "constants": {
      "timezone": "Asia/Shanghai",
      "data_source": "【写死：命令、API、或 workspace 固定路径】",
      "output_dir": "data/workspace/tmp",
      "report_title_template": "值班周报 {week_range}"
    },
    "from_context": []
  },
  "output": {
    "style": "channel_update",
    "need_attachments": true
  }
}
```

说明：

- `from_context` 默认保持 `[]`。凡是执行要用的信息，**尽量写进 `constants` 或 steps 正文**，不要指望「到点还能翻到建任务时那通聊天」。
- `goal` 也可作为 `prompt_text` 短摘要，但**不能只有 goal、steps 仍含糊**。

### 反例 → 正例

| 反例（依赖上下文） | 正例（自包含） |
|-------------------|----------------|
| 步骤：生成报告并发群 | 用 `data/workspace/templates/duty.md` 模板，把上周告警按 NE 聚合，写 PDF 到 `data/workspace/tmp/duty_weekly.pdf`，再 `save_deliverable_attachment` 发当前渠道 |
| constants: `{}`，口头说「用刚才那个 CSV」 | `"source_csv": "data/workspace/uploads/alarms_export.csv"`（或写入导出口径与再拉取命令） |
| success: 搞定 | 渠道出现 PDF；正文含「告警总数 / 严重占比」 |

## 标准流程（必须遵守）

1. **`schedule_propose`**（只草稿，不落库）  
   按上方**任务模板**从对话整理自包含 `recipe`（禁止原样塞「继续刚才」）。
2. **把 `preview_markdown` 发给用户**，并口头强调：到点不会带着本次聊天，请核对步骤是否自包含。
3. 用户确认后 **`schedule_create`**，带上同一份 `recipe` + 时间字段。  
   `prompt_text` = `recipe.goal`（完整句，不要用「同上」）。

禁止：复杂任务直接 `schedule_create(prompt_text="继续刚才那个")`。

## 与渠道附件

若周期任务会生成文件，设 `"output": {"need_attachments": true}`，步骤里写明 `save_deliverable_attachment`（见 **channel-file-delivery**）。

## 简单 vs 复杂

| 类型 | 做法 |
|------|------|
| 喝水/开会提醒 | `schedule_create`，仅短 `prompt_text`（本身已自包含） |
| 多步流程 /「刚才那件事」 | 套用**任务模板** → `schedule_propose` → 确认 → `schedule_create(recipe=...)` |

## 修改已有任务

用 `schedule_update` 更新 `recipe`。改完仍做自检：无上下文能否执行；必要时 `schedule_run_now` 验一次。
