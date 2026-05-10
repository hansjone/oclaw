# Oclaw — Skill 卸载指南

## 路径

卸载逻辑会依次查找（存在则删除）：

1. `<skills_root>/<name>/`
2. `<skills_root>/_workspace/<name>/`

其中 `<skills_root>` 为 `AIA_SKILLS_ROOT` 或默认仓库根 `skills/`。

`<name>` 为 **`SKILL.md` frontmatter 中的 `name`**（与 `skill_list` 中 `name` 字段一致），不一定等于 ClawHub **slug**。

## Admin

- `POST /admin/api/skills/uninstall`  
  Body：`{ "name": "<skill manifest name>" }`

卸载前应在 UI 或对话中向用户确认；删除后不可恢复（除非有外部备份）。

## 启用状态

卸载实现中会尝试将技能从禁用列表恢复为可用状态（见 `skill_installer.uninstall_skill`）；若需保留禁用记录，请在产品中另行约定（当前以代码为准）。

## 批量卸载

对每个名称依次调用卸载接口，独立汇总结果。

## 与旧版差异

- ~~`rm -rf ~/.openclaw/skills/`~~ 等路径不适用于本仓库默认布局
- 不使用任何外部「技能卸载 CLI」；一律走 Admin `uninstall` 或安装器 API
