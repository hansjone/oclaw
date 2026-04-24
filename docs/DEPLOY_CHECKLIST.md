# 新机器部署检查清单（10 步）

用于从 0 到可用地复制一套环境，适合交付给同事或新服务器。

---

## 1) 基础环境

- [ ] 安装 Python（建议与现网一致版本）
- [ ] 安装 Node.js（MCP npm server 需要）
- [ ] 安装 Git（如需 github 类型安装）

---

## 2) 获取代码并安装依赖

- [ ] 拉取仓库代码
- [ ] 创建虚拟环境
- [ ] 执行 `pip install -r requirements.txt`

---

## 3) 设置关键环境变量

- [ ] `OPS_ASSISTANT_PASSWORD`
- [ ] （可选）`OPENAI_API_KEY`
- [ ] （可选）`OPS_ASSISTANT_DB_PATH`

---

## 4) 启动网关

- [ ] 执行 `powershell -ExecutionPolicy Bypass -File .\scripts\start_gateway.ps1`
- [ ] 访问 `http://127.0.0.1:8787/admin` 可打开

---

## 5) 管理台认证

- [ ] 调用 `/admin/api/auth/bootstrap`
- [ ] 使用管理员账号登录成功

---

## 6) MCP 基础依赖检查

- [ ] 在 MCP 页面确认依赖状态（git/node/npm/npx/python/pip）
- [ ] 缺失项先补齐再安装 MCP server

---

## 7) 导入 MCP 安装清单

- [ ] 使用 JSON 安装（单个或数组）
- [ ] 所有目标 server 处于可见状态

---

## 8) 逐个验活

每个 server 执行：

- [ ] `Health` 成功
- [ ] `Sync Tools` 成功
- [ ] 工具数 > 0

---

## 9) 批量体检

- [ ] 点击 `Check Installed`
- [ ] `error_count = 0`（或明确可接受的白名单错误）

---

## 10) 专家映射确认

- [ ] 在 `MCP specialists` 勾选目标专家
- [ ] 保存后验证对应专家可见 MCP 工具

---

## 验收标准（建议）

- 所有关键 MCP server：`health=ok` 且 `tools>0`
- 管理台与聊天页可正常访问
- 核心回归测试通过：

```bash
python -m pytest -q tests/test_mcp_runtime.py tests/test_mcp_admin_api.py tests/test_mcp_adapter.py
```

