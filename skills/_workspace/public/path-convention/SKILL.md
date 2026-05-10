---
name: path-convention
description: "Oclaw 项目路径规范。定义了项目根目录、用户数据区、技能目录、Wiki 记忆四者之间的路径关系。适用于：新建文件、读取文件、运行脚本、创建目录等所有涉及文件路径的操作之前。"
---

# 路径规范 —— Path Convention

## 根目录

项目根 = 当前仓库根目录（workspace root）

所有 `read_file`、`write_file`、`delete_file`、`move_file`、`mkdir` 等工具的 `path` 参数支持两种写法：
- 相对路径：相对于**项目根目录**（workspace root）解析，例如 `data/workspace/a.txt`
- 绝对路径：按系统绝对路径解析（Windows 如 `D:\...`，Linux/macOS 如 `/...`），但仍受工作区路径访问策略约束

## 核心目录

| 用途 | 路径 | 说明 |
|------|------|------|
| **用户数据** | `data/workspace/` | 所有用户生成的文件放这里：脚本、文档、工作流、图片生成产物、测试文件等 |
| **技能文件** | `skills/` | 系统技能和用户安装的技能 |
| **Wiki 记忆** | `data/wiki/` | 长期记忆、Learnings、用户偏好、项目背景 |
| **临时文件** | `data/workspace/tmp/` | 临时中间文件 |

## 注意事项

- `get_cwd()` 返回项目根目录（workspace root）
- `run_command` 未传 `cwd` 时默认在项目根目录执行；需要在子目录执行时请显式传 `cwd`
- 用户数据只放在 `data/workspace/` 下，不要直接散落在根目录
- `data/wiki/` 仅存放结构化记忆，不要放脚本或工作流文件
- 技能安装路径见 `skill_auto_install` 工具，勿手动写入 `skills/` 以外的技能目录
