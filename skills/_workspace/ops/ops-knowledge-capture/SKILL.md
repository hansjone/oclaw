---
name: ops-knowledge-capture
description: WhatsApp/现场短会话下的知识沉淀手册。识别用户强调的通用约定，按层写入 Wiki / IP KB / playbook；不做对话记忆。
---

# Ops 知识捕获（非对话记忆）

## 定位

现场多数是 **WhatsApp、有效对话 ≤10 轮**。本技能**不**追求记住整段对话；**核心义务**是：用户给出的**通用知识必须写入记忆（Wiki/KB）**，不能只口头应承。

实时告警/CLI/网元状态 → 永远用 netx 取证，**禁止**当记忆存。

## 强制触发（命中即本轮必须写回）

出现任一情况时加载本技能，并在**本轮**完成 `memory_wiki_search` →（确认若需要）→ `memory_wiki_apply`（或按路由写 IP KB）：

- 用户说「以后 / 每次 / 记住 / 别再 / 标准是 / always / prefer / from now on / don't … again」
- 纠正绰号、区域前缀、报告格式、CLI 命令偏好（**即使没说“记住”**，纠正本身就是通用知识）
- 同类现场纠偏出现 **≥2 次**
- 排障闭环后需要沉淀案例（用户明确要求或你主动建议）

**硬规则**：只说 “Noted / 记住了” 而不调用写工具 = 失败。终稿可照常 Result/Evidence；写 Wiki 是后台必做步骤。

**不触发**：纯查告警、纯跑 CLI、一次性工单过程、群闲聊。

## 强调词 → 写入层（路由表）

| 用户强调的内容 | 写入层 | 路径 / 动作 | 置信度 |
|----------------|--------|-------------|--------|
| 站点/区域绰号 → `host_name` | **Wiki** | `experts/ops/site-aliases.md` | 原话即规则 → 直接写；含糊 → 一句确认 |
| 报告/语言/终稿格式约定 | **Wiki** | `experts/ops/report-conventions.md` | 同上 |
| 厂商 CLI 纠正（命令顺序、可用 show） | **Wiki** | `experts/ops/field-cli-corrections.md` | 现场验证过 → 直接写 |
| 复发工具流程（batch、配方误用） | **Skill** | 改对应 playbook（ume / managed-ne） | 仅用户要求改 skill，或稳定复现 ≥2 次后提议 |
| 协议排障规律、配置基线、教材化案例 | **IP KB** | `docs/ip-knowledge-base/zte/01`–`06` | 勿擅自大改；用户要求或提炼自多案例 |
| 单次真实故障闭环 | **IP KB** | `docs/ip-knowledge-base/zte/07_现场真实案例库/`（先 `draft`） | 须用户同意写入；`reviewed` 才可作依据 |
| 密钥、密码、整段 CLI dump、当轮告警表 | **不写** | — | — |

## 读路径（答前）

涉及绰号、区域叫法、CLI「应该敲什么」、报告格式时：

1. `memory_wiki_search`（关键词：绰号 / host / optical / 区域码；`limit=5~8`）
2. 命中则 `memory_wiki_get` 取 `experts/ops/*.md`
3. 协议/案例类仍走 `ops-ip-knowledge-playbook`（KB + netx 验证）
4. **无命中不编造**；用 inventory/`queryUmeNeInventory` 解析，并标记为潜在新知识

## 写路径（捕获 — 强制）

1. **识别**：是否「稳定数天 + 影响后续决策」？否 → 不写。是 → **必须写**，不可拖到下轮。
2. **分流**：查上表；先 `memory_wiki_search` 防重复（已有则更新 `Last-Confirmed` / 增量 append）。
3. **写入 Wiki**（`memory_wiki_apply` append/write）：

```markdown
## [Knowledge] <短标题>
- Confidence: high | medium
- Source: user_direct | repeated_field_correction | confirmed
- First-Seen: YYYY-MM-DD
- Last-Confirmed: YYYY-MM-DD
- Applies-To: <范围，如 PLG area / ZTE EN / WhatsApp en>

<一句事实>

### Notes
<可选：来源对话要点，脱敏>
```

4. **中低置信**：用户可见一句短确认（英文现场用英文），确认后再 `apply`。
5. **案例**：按 `07_现场真实案例库/_TEMPLATE.md`；状态 `draft`，不得当正式依据。
6. **禁止**：把当轮 UME 结果/CLI 全文塞进 Wiki；禁止存凭据。

## WhatsApp 行为约束

- 捕获是**后台动作**：终稿仍用 Result/Evidence 壳；不要写成「我已记住」长篇。
- 可选一行：`Next: saved alias SEMBAWA→… to wiki`（仅在确实写入后）。
- 群聊默认不写向量记忆；Wiki 只写**通用约定**，不写发言人私聊八卦。
- 英文会话：Wiki 条目可用中英对照标题，但对用户回复仍零汉字。

## 与其它技能关系

| 技能 | 关系 |
|------|------|
| `ops-netx-ume-playbook` / `ops-netx-managed-ne-playbook` | 干活；本技能只在强调/纠偏时叠加 |
| `ops-ip-knowledge-playbook` | 协议/案例读写；本技能负责把「该进 KB」的强调导过去 |
| `wiki-first-autonomy` | 通用 Wiki 习惯；ops 以本技能路由表为准 |

## 成功标准

- 短会话不堆对话记忆，但绰号/CLI 纠偏跨会话可搜到
- 用户少重复「我说过以后…」
- Wiki 条目短、原子、可检索；IP KB 与 playbook 不被聊天噪声污染
