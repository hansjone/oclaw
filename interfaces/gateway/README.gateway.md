# gateway

`gateway` 是对 `vendor/oclaw/oclaw/gateway` 的 Python 重写目录。

## 当前状态
- 已重写核心挂载链路：
  - `server-plugins.ts` -> `server_plugins.py`
  - `server-startup-plugins.ts` -> `server_startup_plugins.py`
- 目标是保持网关启动期插件加载契约一致（加载插件、合并方法、返回 registry）。

## 迁移策略
- 由于上游 `gateway` 规模很大（数百个 TS 文件），采用分批迁移：
  1. 启动与挂载链路（已完成）
  2. server-methods 与 auth
  3. protocol / server 子模块
  4. 其余工具与测试配套

如果你确认，我会继续下一批，优先迁移 `server-methods` 目录。
