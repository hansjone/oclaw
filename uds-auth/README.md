# uds-auth

0.3.10: [升级与协议变更说明](docs/upgrade-0.3.10.zh.md) · [SBOM](docs/sbom.cdx.json) · [第三方许可证](docs/THIRD-PARTY-NOTICES.txt)

UDS authentication plugin for DeepSeek Harness (**trusted single-instance** access control — **not** strong multi-tenant isolation).

See `package.json` for the current 0.3.x version (breaking auth protocol vs 0.2.x — re-login required).

## Support boundary

| Item | Notes |
|------|--------|
| Runtime | Node `^22.19.0 \|\| >=24` (aligned with DSH Host) |
| Mode | Single Host, trusted enterprise users, controlled skills |
| Out of scope | Untrusted multi-tenant execution isolation; multi-instance without shared session store |

## Install

```bash
dsh plugin --profile web add -w "<abs>/oclaw/uds-auth"
# or clean tarball
dsh plugin add -w "<abs>/uds-auth-0.3.9.tgz"
```

Empty roles table requires `UDS_AUTH_INITIAL_ADMIN` or `initialAdminEmpNo`. Restart Harness after install.

`ctx.get('udsAuth').runAsHost(cb)` — Host background ALS.  
`ctx.get('udsAuth').mintTaskCapability({ empNo, dshSessionId, scopes, ttlSeconds })` — inject `UDS_TASK_CAPABILITY` for cron/skill.

## Config

```yaml
uacBaseUrl: https://uac.zte.com.cn   # HTTPS required at startup/merge
userSearchUrl: https://icenterapi.zte.com.cn/...
loginSystemCode: '100000455558'
initialAdminEmpNo: ''
allowOpenRegistration: true
allowRawAgentToken: false
outboundAllowedHosts: icenterapi.zte.com.cn,icentermsg.dt.zte.com.cn
trustedHosts: ''               # empty = loopback Host only; proxies must set allowlist
retainSkillCredentialsOnLogout: true
skillCredentialTtlSeconds: 604800
sessionIdleTimeoutHours: 0     # 0 = never auto sign out; 0.5–168h idle timeout; editable in Settings
```

Durable state defaults to `~/.uds-auth/` (roles / owners / credentials / bridge / sessions / `config.runtime.json`; override with `UDS_AUTH_DATA_DIR`). Security toggles take effect on the next request after Settings save. Empty outbound allowlist denies all.

## Sessions

- **Lifetime**: by default (`sessionIdleTimeoutHours: 0`) sessions never sign out on their own — only a manual sign-out ends them, so running conversations and night-time scheduled tasks are never cut off. Setting 0.5–168 hours in Settings enables an idle timeout that slides on activity (HTTP requests and Desktop WS calls) with a 7-day absolute cap. The browser cookie and the Desktop bridge token slide with the session.
- **UAC token check**: every 2 hours (and 1 minute after start) each QR session's UAC token is re-checked against the icenterapi department profile. A rejected token (401/403, business error code, employee not visible/mismatched) never signs out: the client shows a QR prompt, and the scan writes the new token into every live session of that account in place — no new session, no reload. Network errors, 5xx and malformed responses keep the previous verdict.
- **Client probe**: `GET /uds-auth/session-status` (never slides the TTL) runs every minute and on window focus. It returns `alive` and `tokenValid`; a gone session signs the UI out, a rejected token opens the refresh QR once.
- **Survives restarts**: the default in-memory store is persisted to `~/.uds-auth/sessions.json` and restored on Host start (emergency admins have no SSO re-login, so they depend on this).
  - Only the SHA-256 hash of each session token is stored; user data (may include the UAC token) is AES-256-GCM encrypted with the plugin key `.uds-auth-secret-key`.
  - Expired, undecryptable or tampered rows are dropped on load; disabled-account and emergency-password rotation checks still run on every request.
  - **Delete `sessions.json` and restart to sign everyone out.** If the key file is unavailable, sessions are simply not persisted.
- Not used when a Redis session store is configured.

## Admin / emergency

- `super_admin` / `admin` / `fallback_admin` share the same admin-class permissions (identity labels, not stronger isolation).
- The emergency account is enabled by default: username `administrator`, password `Admin@123`. Change it in Settings after first sign-in. Admins can also disable it. Older roles files without an explicit emergency-account state receive this default; an explicitly disabled account stays disabled. Historical SHA-256 hashes of `Admin@123` migrate to scrypt.
- Local unlock: `node scripts/seal-local-admin.mjs` (interactive / `--stdin` — **no argv passphrase**) → `UDS_AUTH_LOCAL_ADMIN_BOX`.
- Removing a user disables the account by default (open registration cannot auto-revive).

## DSH compatibility

Verified on **DeepSeek Harness Desktop 0.2.0-rc.2**. The plugin relies on DSH internals that are not a public API; after a DSH upgrade run `npm test` and check login, workspaces and Settings → Models on a real install:

- Gateway `prepareInvocation` / `resolveDescriptor` / `openRemoteEvents` / `receiveRemoteEventResult` (if missing, the ACL refuses to install instead of failing open);
- the client `connection/reset` event (emitted after login so boot-time caches such as the settings mirror re-read);
- endpoint names `workspace/follow`, `workspace/initializeDefault`, and the Desktop welcome reads `settings/describe`, `llm/listConfigurableProviders`, `credentials/describe`, `account/getState`.

Desktop opens its connection anonymously at boot and reconnects after login. The plugin therefore:
- parks anonymous stream calls (e.g. account state) without data instead of failing them (a failure is terminal for DSH and shows "sign-in failed / add API key");
- answers anonymous `workspace/follow` with an empty list and anonymous `workspace/initializeDefault` with "nothing created";
- holds `/api/*` requests for up to 15 s while the gateway ACL is still installing, instead of returning 403.

## Skill / cron

Prefer Host-minted `UDS_TASK_CAPABILITY` + `DSH_SESSION_ID` with `/uds-auth/outbound`. Raw `/agent-credentials` stays off unless explicitly enabled. Python helper: `skill-helpers/python/uds_skill_auth.py`.

Chinese docs: [README.zh.md](README.zh.md), [docs/skill-auth-standard.zh.md](docs/skill-auth-standard.zh.md).

## License

MIT
