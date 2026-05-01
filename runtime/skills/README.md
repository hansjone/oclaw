# skills 目录说明

本目录是项目内默认 Skills 根目录（中文优先）。

## 约定
- 每个技能建议独立子目录，目录内放 `SKILL.md`。
- `SKILL.md` 建议包含 frontmatter（`name`、`description`、`metadata`）。
- 技能说明正文请优先使用中文，便于团队统一维护。

## 示例结构
- `oclaw/runtime/skills/<skill_name>/SKILL.md`

## 目录分层（重要）
- **主目录**：`oclaw/runtime/skills/<skill_name>/`  
  用于官方/手工管理的稳定技能（安装、维护、评审都在这层）。
- **自写目录（扁平）**：`oclaw/runtime/skills/_workspace/<skill_name>/`  
  兼容旧行为；新装技能优先按角色分桶（见下）。
- **公共目录**：`oclaw/runtime/skills/_workspace/public/<skill_name>/`  
  与 **按专家/角色目录** `oclaw/runtime/skills/_workspace/<role>/<skill_name>/`（如 `generalist`、`ops`）**平级**；`public` 下技能默认全员可用，不需角色绑定。
- **遗留会话桶**：`oclaw/runtime/skills/_workspace/_agent/<segment>/` 仅用于无绑定角色时的回退（如旧会话 id），新逻辑不应依赖该层。

说明：
- `auto_install_skill_from_payload` 产物默认落在 `_workspace` 下。
- 这样可以把“生产稳定技能”和“实验/自写技能”分开治理，便于审计与回滚。

## 兼容说明
- 运行时优先读取 `oclaw/runtime/skills`。
- 若设置了环境变量 `AIA_SKILLS_ROOT`，以该变量为准。
- 为兼容旧工程，仍可回退读取旧路径 `oclaw/runtime/skills/`（如存在）。

## 技能市场（安装来源）

- 租户设置 **`AIA_SKILL_MARKET_PROVIDER`**：`clawhub`（默认）或 **`cocoloop`**，由 `runtime/skills_market.get_market_adapter` 选择适配器；Admin「市场搜索 / 按 slug 安装」共用同一套路由。
- ClawHub：见 `runtime/tools/skills/clawhub_client.py`（`AIA_CLAWHUB_*` / `CLAWHUB_*`）。公开 API 说明可参考 [openclaw/clawhub CLI 文档](https://github.com/openclaw/clawhub/blob/main/docs/cli.md)。
- CocoLoop：`runtime/tools/skills/cocoloop_client.py`，默认 API 基址 `https://api.cocoloop.com`，可用 **`AIA_COCOLOOP_API_BASE`** 覆盖。

## 推荐实用 Skills（workspace）

以下为当前已落地并可直接在 Admin `Test run` 使用的实用技能：

### 1) `incident_triage`
- **用途**：对报错/日志做故障归因（timeout、permission、network 等）并给出行动建议。
- **输入参数示例**：
```json
{
  "error": "TimeoutError: connection refused to upstream service"
}
```
- **典型输出**：`category`、`severity`、`summary`、`action_items`、`confidence`。

### 2) `release_checklist`
- **用途**：发版前门禁检查，输出是否可发版和阻塞项。
- **输入参数示例**：
```json
{
  "tests_passed": true,
  "lint_passed": true,
  "migration_reviewed": true,
  "rollback_plan_ready": true,
  "monitoring_ready": true
}
```
- **典型输出**：`release_ready`、`failed_checks`、`missing_required_inputs`、`action_items`。

### 3) `data_extract_summary`
- **用途**：从文本/日志中抽取重点、统计级别并生成摘要建议。
- **输入参数示例**：
```json
{
  "text": "INFO boot complete\nWARN cache miss\nERROR timeout connecting service",
  "max_lines": 8
}
```
- **典型输出**：`summary`、`line_count`、`level_counts`、`top_keywords`、`action_items`。
