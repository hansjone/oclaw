# oclaw skill 排障手册

本文档用于 oclaw skill 的安装、暴露、执行、回写等问题快速排查。

建议排查顺序：

1. 安装是否成功（manifest / 依赖 / 权限）
2. 是否进入可见工具清单
3. 执行阶段是否命中超时或参数错误
4. 结果回写与 trace 是否完整

常用定位关键词：

- `skill_install`
- `available_skills`
- `tool_result`
- `error_code`
