# Wiki 优先自治：示例

## 示例 1：首次捕获用户偏好

用户说：

"以后给我回复都简短一点，先给结论再给细节。"

智能体行为：

1. 识别高记忆价值偏好（风格 + 回复顺序）。
2. 如有必要，做一次确认：
   - "我会按‘先结论后细节、整体简短’执行，后续都默认这样，可以吗？"
3. 使用 `memory_wiki_apply` 写入 Wiki，归类为 L3 Identity。
4. 使用 `memory_wiki_lint` 校验更新后的记录。
5. 后续回复默认自动应用该偏好。

预期记录片段：

```markdown
## [Memory] 回复风格偏好
- Tier: L3 Identity
- Confidence: high
- Source: user_direct
- First-Seen: 2026-04-29
- Last-Confirmed: 2026-04-29
- Applies-To: all coding and ops responses

用户偏好简洁回复，并采用结论优先结构。

### 影响说明
提升回复可用性，减少来回确认成本。
```

## 示例 2：跨会话唤醒

已有记忆：

- 用户运行环境为 Windows + PowerShell
- 用户偏好中文提交信息

新会话中用户说：

"提交吧。"

智能体行为：

1. 运行 `memory_wiki_search` 检索用户/工具偏好。
2. 对命中项运行 `memory_wiki_get`。
3. 不再重复询问，直接应用既有约定：
   - 使用 PowerShell 兼容提交流程
   - 使用中文提交信息
4. 若仍有效，完成后更新 `Last-Confirmed`。

预期的用户可见连续性：

- "按你之前的习惯，我用中文提交信息并走 PowerShell 兼容命令提交。"

## 示例 3：复发问题沉淀升级

近期任务中观察到两次：

- sidecar 停启竞争导致 PID 陈旧与噪声报错。

智能体行为：

1. 检测到复发次数 >= 2。
2. 通过 `memory_wiki_apply` 创建/更新专题区：
   - `topics/auto-ops.md` 或独立稳定性页面。
3. 记录稳定化处理清单。
4. 在后续同类任务中主动复用该清单。

预期记录片段：

```markdown
## [Memory] Sidecar 陈旧 PID 清理模式
- Tier: L2 Project
- Confidence: high
- Source: repeated_behavior
- First-Seen: 2026-04-28
- Last-Confirmed: 2026-04-29
- Applies-To: weixin/whatsapp sidecar lifecycle scripts

在 start/stop 前优先执行 PID+端口双清理，并抑制可预期的 kill 噪声输出。

### 影响说明
可减少重复重启失败并降低运维误判。
```

## 最小决策准则

写入记忆前，快速判断：

- 稳定性：7 天后仍可能有用吗？
- 可执行性：会改变后续行为吗？
- 可复用性：不是一次性细节吗？

满足 2 项及以上时，写入 Wiki。

