# OpenClaw Prompt Mapping

该目录作为 OpenClaw 风格提示词的唯一运行时来源（中文单份）。

## 设计目标
- 每个角色一个文件夹，便于独立维护和同步。
- 文件名与结构尽量稳定，后续可直接从上游模板搬运替换。
- 运行时不做 `zh/en` 分流，仅加载本目录中文文件。

## 目录约定
- `roles/manager/system.md`
- `roles/specialists/ops/system.md`
- `roles/specialists/generalist/system.md`
- `roles/specialists/image/system.md`
- `roles/specialists/memory_curator/system.md`
- `runtime/system_with_memory.md`
- `runtime/system_with_skills.md`
- `runtime/memory_context_block.md`
- `runtime/project_context_block.md`
- `shared/*`（复用片段）

## 同步规则
1. 以上游 OpenClaw 规范为准，优先替换同名文件。
2. 本地仅允许：
   - 路径适配（保持目录结构不变）
   - 变量名与渲染占位符适配（`{{var}}`）
3. 不在业务代码中硬编码提示词正文；只通过 loader 渲染。
