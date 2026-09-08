# uds-auth

UDS authentication plugin for DeepSeek Harness: fixed sidebar login badge + host session/role APIs.

## Install

```bash
dsh plugin --profile web add -w "D:/project/chatgpt/oclaw/uds-auth"
```

Restart Harness after install. The badge mounts on `sidebar.footer.action` (root scope).

## Config

```yaml
uacBaseUrl: https://uac.zte.com.cn
userSearchUrl: https://icenterapi.zte.com.cn/zte-km-icenter-addresearch/user/plain/docs/search
loginSystemCode: '100000455558'
originSystemCode: ''
retainSkillCredentialsOnLogout: true
skillCredentialTtlSeconds: 604800
outboundAllowedHosts: icenterapi.zte.com.cn,icentermsg.dt.zte.com.cn
```

Skill auth standard (Chinese): [docs/skill-auth-standard.zh.md](docs/skill-auth-standard.zh.md). Sample skill: `../skills/uds-icenter`.

Loopback agent APIs: `GET|POST /uds-auth/agent-credentials`, `POST /uds-auth/outbound`.

## Layout

| Piece | Path | Role |
|-------|------|------|
| Host | `lib/index.js` | Cordis `apply`: settings, RPC, `/uds-auth/*` |
| Client | `lib/client.js` | ModuleLoader + React footer login card |
| Bundle | `cordis.patch.yml` | layer `insert` only |
| Meta | `package.json` `dsh.client` | `./client` + slots inject |

The login panel uses `position: fixed` with a measured trigger anchor (same pattern as CordisPanel) so the sidebar overflow clip cannot hide it.

## License

MIT
