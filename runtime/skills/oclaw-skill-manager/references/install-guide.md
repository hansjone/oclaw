# Oclaw — Skill 安装详细指南

本文档仅描述 **Oclaw** 内的安装行为，替代旧版「多平台检测 + Cocoloop API」流程。

## 模型执行硬规则

- 仅允许 `skill_auto_install`。
- 安装失败时只允许“报告失败原因给用户”，禁止改走其它安装入口（market/install、install-registry、install、本地脚本解压落盘等）。
- 不得把未在规范中声明的环境变量/端口/服务状态当作安装前置条件。

## 1. 技能根目录

- 默认：`runtime/skills/`（或环境变量 `AIA_SKILLS_ROOT` 指向的目录）
- **主目录**：`<skills_root>/<name>/` — Admin 市场 / registry / 本地目录安装默认落点
- **智能体自写目录**：`<skills_root>/_workspace/<name>/` — `skill_auto_install` / `auto_install_skill_from_payload` 等

具体以安装接口返回的 `target_dir` 为准。

## 2. 安装入口对照（运维参考）

| 场景 | 方式 | HTTP（Admin） |
|------|------|----------------|
| ClawHub slug | 解析 `archive_url` 后安装 | `POST /admin/api/skills/market/install` |
| 已知归档 URL | 直接拉取 zip/tar | `POST /admin/api/skills/install-registry` |
| 本地已展开目录 | 目录内含 `SKILL.md` | `POST /admin/api/skills/install` |
| 从模板创建 | 生成新包 | `POST /admin/api/skills/create` |
| Workspace 模板 | 带 runtime 桩 | `POST /admin/api/skills/create-workspace` |

认证：Admin 路由需带网关要求的 `Authorization`（与现有 Admin 一致）。

## 3. 依赖与自检

安装成功后，安装器会尽量：

1. 处理 `requirements.txt`、`package.json`（`dependencies` 非空）
2. 扫描 `.py` 的 import，对缺失的第三方模块尝试 `pip install`

失败不一定会回滚整个目录，可能返回带 `installed_with_dependency_warnings` 的 `detail`。此时在 Admin 使用 **Repair deps** 或 **Repair all deps**。

## 4. 重试与覆盖

- 安装失败审计里若带 `retryable`，可用 `POST /admin/api/skills/retry-install`（见 Admin 实现）
- 覆盖安装：`overwrite: true`

## 5. 禁止项

- **不要**使用任何「第三方技能 CLI + install」作为安装路径（`run_command` 会拦截常见模式）
- **不要**把非本仓库契约的 HTTP 商店当作主源；技能发现以 **ClawHub 市场适配器**（`AIA_SKILL_MARKET_PROVIDER`）为准
- **模型侧不要**在 `skill_auto_install` 失败后切换到 Admin 安装 API 或脚本直装。

## 6. slug 与包名

ClawHub 返回的 **slug** 可能与解压后 `SKILL.md` frontmatter 里的 **name** 不同。卸载、启用、绑定角色时以 **`skill_list` / API 返回的 `name`** 为准。
