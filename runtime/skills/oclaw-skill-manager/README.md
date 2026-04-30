# oclaw-skill-manager

Oclaw **内置** Skill：说明如何在当前仓库中安装、更新、卸载技能，以及依赖与健康检查。

- 主文档：[SKILL.md](SKILL.md)
- 本包**不是**任何外部「技能市场 CLI」的封装；平台不提供官方 shell 一键安装命令。
- 模型安装策略：仅允许 `skill_auto_install`；失败时仅报告 `error_code/detail`，禁止绕路安装。
