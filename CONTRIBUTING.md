# 参与贡献

感谢你有兴趣改进本项目。下面是从 Fork 到合并的最常见路径；本地环境与命令仍以仓库根目录 `README.md`、`docs/RUNBOOK.md` 为准。

## 协作方式

- 本仓库**默认不**对陌生人开放直接 `push` 权限。外部贡献请走 **Fork → 新建分支 → 打开 Pull Request（PR）**。
- 维护者审阅、CI 通过后合并到主分支；你在本机用 `git pull` 即可同步。

## 建议流程

1. **Fork** 本仓库到你自己的 GitHub 账号下。
2. 克隆你的 Fork，并添加上游（便于同步）：

   ```text
   git remote add upstream https://github.com/hansjone/oclaw.git
   ```

3. 从 `main` 拉最新，并创建功能分支（命名清晰，如 `fix/...`、`feat/...`）：

   ```text
   git fetch upstream
   git checkout -b feat/your-topic upstream/main
   ```

4. 修改后提交；推送 **到你的 Fork**：

   ```text
   git push -u origin feat/your-topic
   ```

5. 在 GitHub 上从你的 Fork 向原仓库发起 **Pull Request**，说明动机、变更范围；有关联 Issue 可在描述里写 `Fixes #123`。

## 合并前自检

- 尽量保持改动聚焦单一主题，避免无关格式化或大范围重命名。
- 仓库根目录已配置 CI（`.github/workflows/ci.yml`）；请在本地尽量跑通相关测试或 lint，减少往返。
- **切勿**提交密钥、令牌、个人 `_local/system.env`、数据库路径等敏感内容；环境请以 `_local/system.env.example` 为模板本地自建。

## 文档与风格

- 环境变量登记规则见 `_local/system.env.example` 头部说明；相关文档需同步 `docs/ENVIRONMENT_VARIABLES.md`（如适用）。
- 提示词与工作区约定见 `docs/PROMPT_STYLE_GUIDE.md`、`docs/ARCHITECTURE_OVERVIEW.md`（按改动类型选读）。

## 问题反馈

- 使用 GitHub **Issues**（见仓库内 Issue 模板）。尽量写清复现步骤、环境（OS、Python 版本、相关配置是否改）与预期/实际行为。

若仅作内部使用、暂不接受外部 PR，可在仓库说明中注明；本文件仍可作为团队内协作参考。
