# skills 目录说明

本目录是项目内默认 Skills 根目录（中文优先）。

## 约定
- 每个技能建议独立子目录，目录内放 `SKILL.md`。
- `SKILL.md` 建议包含 frontmatter（`name`、`description`、`metadata`）。
- 技能说明正文请优先使用中文，便于团队统一维护。

## 示例结构
- `oclaw/skills/<skill_name>/SKILL.md`

## 兼容说明
- 运行时优先读取 `oclaw/skills`。
- 若设置了环境变量 `AIA_SKILLS_ROOT`，以该变量为准。
- 为兼容旧工程，仍可回退读取仓库根目录下的 `skills/`。
