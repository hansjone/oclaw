---
name: background-jobs
description: "长时间任务（数分钟到数小时）用 start_job/get_job；同轮不要干等；断线后任务可继续，靠 job_id 恢复或 notify 通知。"
---

# 后台长任务 — Background Jobs

## 核心事实

1. **同轮等不了两小时**（也不该等）。`sleep` 最多 120 秒。
2. `start_job` 立刻返回 `job_id`；**agent 断线 / 本轮结束，进程仍可继续跑**（gateway 进程在的前提下）。
3. 正确姿势是 **交作业 → 告知用户 job_id → 结束本轮**；以后再查，或靠完成通知。

## 推荐流程（1–2 小时任务）

```text
1. write_file 写自包含脚本（输入/输出路径写死）
2. start_job(command=..., timeout_s=7200, name=..., notify={...可选})
3. 回复用户：已提交后台任务，job_id=...，跑完会通知 / 请稍后问「查任务 job_xxx」
4. 结束本轮（不要 sleep 循环两小时）
5. 之后任意一轮：get_job(job_id) 或 list_jobs → 读产出 → 需要时 save_deliverable_attachment
```

## 断线后会怎样

| 情况 | 行为 |
|------|------|
| 本轮对话结束 / 用户离开 | 任务继续；磁盘有 `data/jobs/<job_id>/` |
| 用户过一会再问 | `get_job` / `list_jobs` 恢复状态 |
| Gateway 重启但子进程还在 | 后台 reaper（约 15s）按超时/pid 对账回收；Chat 徽章也会刷新 |
| Gateway 整机挂掉 | 子进程可能被系统清掉；下次 reaper/`get_job` 标失败/超时 |

## notify（可选，推荐渠道场景）

`start_job` 可带：

```json
"notify": {
  "channel": "whatsapp",
  "chat_id": "<群或会话 id>",
  "account_id": "wa-default",
  "message": "可选自定义文案"
}
```

任务结束（成功/失败/超时/取消）后会往该渠道塞一条出站提醒（含 `job_id`）。  
微信需额外 `context_token`（与现有 weixin 出站一致）。

**WebChat**：没有渠道 notify 时，靠用户稍后再问 + `list_jobs`。

## 工具

| 工具 | 作用 |
|------|------|
| `start_job` | 后台启动，返回 `job_id`（默认 2h，最大 3h） |
| `get_job` | 查状态与日志尾；`done=true` 表示结束 |
| `list_jobs` | 近期任务 |
| `cancel_job` | 取消 |
| `sleep` | 仅短轮询间隙（≤120s），不是长等 |

与 `run_command` 同一开关：`AIA_ENABLE_RUN_COMMAND`。

## Chat 可视化

Chat 左侧导航底部 **「后台任务」**（用户区上方）右侧数字徽章持续显示运行中数量（约每 4 秒刷新，无需点开面板）；用户菜单也有入口：
- 有任务时按钮高亮，右侧数字徽章变红
- 点开后可：列表 / **终止** / **全部终止** / **清除记录** / 日志
- 面板打开时约每 4 秒自动刷新列表

## 不要做

- 同轮 `sleep`/`get_job` 死循环拖两小时
- 用 `run_command` 跑多小时脚本
- 不告诉用户 `job_id` 就结束（断线后难找回，除非用户记得或去 Chat「后台任务」/ `list_jobs`）
