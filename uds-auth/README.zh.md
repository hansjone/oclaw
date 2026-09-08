# uds-auth

DeepSeek Harness 的 UDS 统一认证插件：右上角登录徽章 + 设置页用户管理。

## 安装

```bash
dsh plugin --profile web add -w "D:/project/chatgpt/oclaw/uds-auth"
```

安装后重启 Harness。登录徽章在 `shell.overlay`（右上角）；用户管理/部署配置在 **设置 → UDS 认证**（`settings.section`）。

## 配置

在 **设置 → UDS 认证** 或 `cordis.patch.yml` 中修改：

```yaml
uacBaseUrl: https://uac.zte.com.cn
userSearchUrl: https://icenterapi.zte.com.cn/zte-km-icenter-addresearch/user/plain/docs/search
loginSystemCode: '100000455558'
originSystemCode: ''
```

## 标准 DSH 插件结构

| 部分 | 路径 | 说明 |
|------|------|------|
| Host | `lib/index.js` | Cordis `apply`：HTTP `/uds-auth/*`、可选 schema 设置 |
| Client | `lib/client.js` | 右上角登录 + 设置页用户管理 |
| Bundle | `cordis.patch.yml` | `insert` 插件层（不含 client.entry） |
| Meta | `package.json` → `dsh.client` | `exports["./client"]` + slots inject |

## API

- `POST /uds-auth/qr-start` — 服务端生成扫码挑战
- `GET /uds-auth/qr?data=` — 二维码 SVG
- `POST /uds-auth/qr-proxy` — 代理 UAC 扫码校验
- `GET /uds-auth/api/me` — 当前用户
- `POST /uds-auth/api/logout` — 登出
- 用户管理 / 兜底管理员：见 `/uds-auth/api/users*`、`/uds-auth/api/fallback/*`
- **默认兜底账号**（扫码不可用时）：用户名 `administrator`，密码 `Admin@123`（首次启动自动启用；可在设置中改密或关闭）

## License

MIT
