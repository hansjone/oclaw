/**
 * One-shot ilink getUpdates probe (diagnose "sidecar started but no messages").
 * Run from repo: runtime/operations/scripts/weixin_poll_diag.ps1
 */
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const STATE_DIR = (process.env.OCLAW_STATE_DIR || path.resolve(process.cwd(), "state")).trim();
const STATE_FILE = path.join(STATE_DIR, "official_bridge_state.json");

function resolvePluginRoot(): string {
  const configured = String(process.env.OCLAW_WEIXIN_PLUGIN_ROOT || "").trim();
  return configured || path.join(process.cwd(), "node_modules", "@tencent-weixin", "openclaw-weixin");
}

async function resolveAccount(): Promise<{ accountId: string; token: string; cloudBaseUrl: string }> {
  if (!String(process.env.OPENCLAW_STATE_DIR || "").trim()) {
    process.env.OPENCLAW_STATE_DIR = STATE_DIR;
  }
  const pluginRoot = resolvePluginRoot();
  const srcRoot = path.join(pluginRoot, "src");
  const importTs = async (relativePath: string) => import(pathToFileURL(path.join(srcRoot, relativePath)).href);
  const accountsMod = await importTs(path.join("auth", "accounts.ts"));
  const listIds = accountsMod.listIndexedWeixinAccountIds as () => string[];
  const loadAcc = accountsMod.loadWeixinAccount as (id: string) => Record<string, unknown>;
  const accountId = String((listIds() || [])[0] || "").trim();
  if (!accountId) throw new Error("no weixin account; run weixin_login.ps1");
  const data = loadAcc(accountId) || {};
  const token = String(data.token || "").trim();
  if (!token) throw new Error(`missing token for ${accountId}; run weixin_login.ps1`);
  const envCloud = String(process.env.OCLAW_WEIXIN_CLOUD_BASE_URL || "").trim();
  const cfgCloud = String(data.baseUrl || "").trim();
  const cloudBaseUrl = (envCloud || cfgCloud || "https://ilinkai.weixin.qq.com").trim();
  return { accountId, token, cloudBaseUrl };
}

async function main(): Promise<void> {
  const reset = process.argv.includes("--reset-cursor");
  const stateRaw = (() => {
    try {
      return JSON.parse(fs.readFileSync(STATE_FILE, "utf8")) as Record<string, unknown>;
    } catch {
      return {};
    }
  })();
  let cursor = reset ? "" : String(stateRaw.cloud_cursor || "").trim();
  const { accountId, token, cloudBaseUrl } = await resolveAccount();
  const pluginRoot = resolvePluginRoot();
  const apiMod = await import(pathToFileURL(path.join(pluginRoot, "src", "api", "api.ts")).href);
  const getUpdates = apiMod.getUpdates as (p: Record<string, unknown>) => Promise<Record<string, unknown>>;

  console.log(
    JSON.stringify(
      {
        accountId,
        cloudBaseUrl,
        cursorPrefix: cursor.slice(0, 48),
        resetCursor: reset,
      },
      null,
      2,
    ),
  );

  const out = await getUpdates({
    baseUrl: cloudBaseUrl,
    token,
    get_updates_buf: cursor,
    timeoutMs: 15_000,
  });
  const msgs = Array.isArray(out.msgs) ? out.msgs : [];
  console.log(
    JSON.stringify(
      {
        ret: out.ret,
        errcode: out.errcode,
        errmsg: out.errmsg,
        msgCount: msgs.length,
        nextCursorPrefix: String(out.get_updates_buf || "").slice(0, 48),
      },
      null,
      2,
    ),
  );
  if (msgs.length > 0) {
    const m = msgs[0] as Record<string, unknown>;
    console.log(
      "first_msg",
      JSON.stringify(
        {
          from_user_id: m.from_user_id,
          to_user_id: m.to_user_id,
          message_type: m.message_type,
          has_text: Boolean(m.text || (m as { content?: unknown }).content),
        },
        null,
        2,
      ),
    );
  } else {
    console.log("hint=send a NEW text message to the bot now, then re-run this script within 30s");
  }
}

void main().catch((err) => {
  console.error("poll_diag_failed", err);
  process.exit(1);
});
