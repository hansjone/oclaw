---
name: oclaw-skill-manager
description: Oclaw 官方 Skill 生命周期手册：安装、更新、卸载、依赖与健康检查。仅使用本仓库 Admin API、安装器与内置工具；不提供也不推荐任何 shell「一键装技能」命令。
---

# Oclaw Skill 管理器（官方手册）

本技能是 **Oclaw 自有** 的 Skill 运维说明，用于指导模型与运维在**同一套契约**下管理仓库根 `skills/` 下的技能包。

## 系统强约束（模型必须遵守）

- 规范优先：安装决策只依据本文件，不依据临时推断或“经验性排障说法”。
- 路径约束：当任务目标是“为当前会话/用户安装 skill”时，**只允许**走 `skill_auto_install`（`_workspace` lane）。
- 禁止绕路：不得调用任何非 auto 安装路径（包括但不限于 `skill_market_install`、`skill_registry_install`、Admin 安装 API、手写下载/解压脚本落盘到仓库根 `skills/`）。
- 失败处理：`skill_auto_install` 失败后，**不得继续安装**；只报告 `error_code/detail` 与最小下一步，等待用户指示。
- 禁止臆测前置条件：未在本规范显式声明的环境变量/端口/服务状态，不得被表述为“安装必经条件”。

## 平台事实（无「原生安装命令」）

- Oclaw **不提供**任何官方 shell「一键装技能」命令（包括市场 CLI、`npx …` 拉 CLI 再 `install` 等模式）。
- 模型安装策略：默认仅使用 **`skill_auto_install`**；其他安装能力仅供管理员/后端运维链路使用。
- 在沙箱里执行 `run_command` 时，**外部技能 CLI 安装模式会被拦截**（见 `shell_tools`），请改用下文 API。

## 目录策略

| 场景 | 路径 |
|------|------|
| 人工 / Admin 市场或 registry 安装 | `<skills_root>/<manifest_name>/` |
| 智能体 payload 自动安装 | `<skills_root>/_workspace/<manifest_name>/` |

`<skills_root>` 默认仓库根 `skills/`，可被 **`AIA_SKILLS_ROOT`** 覆盖。

## 技能市场提供方（ClawHub + CocoLoop）

租户设置 **`AIA_SKILL_MARKET_PROVIDER`** 选择市场（网关 `get_market_adapter` 读取）：

| 取值 | 说明 |
|------|------|
| **`clawhub`**（默认） | [ClawHub](https://clawhub.ai) 公开技能注册表；HTTP 形态与官方 CLI 一致，见上游文档 [CLI / Registry](https://github.com/openclaw/clawhub/blob/main/docs/cli.md)（`/api/v1/search`、`/api/v1/skills/{slug}`、`/api/v1/download?slug=&version=`）。本仓库客户端：`runtime/tools/skills/clawhub_client.py`，环境变量 **`AIA_CLAWHUB_SITE` / `AIA_CLAWHUB_REGISTRY` / `AIA_CLAWHUB_TOKEN`**（或 `CLAWHUB_*`）与官方 `CLAWHUB_*` 对齐。 |
| **`cocoloop`** | [CocoLoop 技能商店](https://hub.cocoloop.cn) 开放列表接口：`GET {api}/api/v1/store/skills`（分页、`keyword`、`sort`），详情：`GET {api}/api/v1/store/skills/{id}`；列表项中的 **`download_url`** 为 zip 直链（常见域名 `dl.cocoloop.cn`）。实现：`runtime/tools/skills/cocoloop_client.py`；可选 **`AIA_COCOLOOP_API_BASE`**（默认 `https://api.cocoloop.com`）。别名：`cocoloop-cn`、`cocoloop_cn` 与 `cocoloop` 相同。 |

安装仍统一走 **`install_skill_from_registry_archive`**：对 ClawHub 与 CocoLoop 均为 **HTTPS zip 归档 URL**，无需在服务器上安装 `clawhub` / `cocoloop` CLI。

## 发现与安装（模型视角）

### 唯一安装路径（必须）

- **`skill_auto_install`**：仅写入 `_workspace` lane（见 `skill_installer.auto_install_skill_from_payload`）。
- **非前置条件澄清**：`AIA_INTERNAL_BASE_URL`、Admin `market/search`、本地 5173 服务都不是 `skill_auto_install` 的必需前置。
- 若安装失败，向用户返回：
  - `error_code`
  - `detail`
  - 建议下一步（例如补充 name/description、检查依赖、重试）
- 不允许改走其它安装入口完成同一目标。

## 列表、开关、卸载

- **`skill_list`**（若已绑定到当前专家）
- `GET /admin/api/skills`
- `POST /admin/api/skills/enable` / `disable`，`{ "name": "..." }`
- `POST /admin/api/skills/uninstall`，`{ "name": "..." }`

## 依赖与健康

- 安装后：`requirements.txt`、`package.json`（`dependencies`）、Python import 探测与补装（受 `AIA_SKILL_AUTO_INSTALL_DEPS_ENABLED` 控制）。
- Admin：**Repair deps** / **Repair all deps**
- `GET /admin/api/skills/self-check?include_execution=...`

## 更新

模型侧无独立 update 安装路径；如需更新，按用户指示走新的 `skill_auto_install` 版本草案或转人工管理员操作。

## 可选人工安全审查

- [references/safety-check-guide.md](references/safety-check-guide.md)
- [references/skill-safety-rubric.md](references/skill-safety-rubric.md)  
  均为**人工参考**，平台不自动执行远程认证。

## 子文档

- [references/install-guide.md](references/install-guide.md)
- [references/search-guide.md](references/search-guide.md)
- [references/uninstall-guide.md](references/uninstall-guide.md)

---

维护本技能时，请只增删 **Oclaw 已实现** 的行为，勿再引入第三方「技能 CLI」作为默认路径。
