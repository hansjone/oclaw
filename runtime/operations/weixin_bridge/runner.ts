// Legacy fallback bridge. The default startup path now uses `official_runner.ts`,
// which drives the official openclaw-weixin modules directly.
import fs from "node:fs";
import crypto from "node:crypto";
import os from "node:os";
import path from "node:path";

type Json = Record<string, unknown>;
type TokenMap = Record<string, string>;

const LOCAL_BASE_URL = (process.env.AIA_GATEWAY_BASE_URL || "http://127.0.0.1:8787").trim();
const STATE_DIR = (process.env.OCLAW_STATE_DIR || path.resolve(process.cwd(), "state")).trim();
const STATE_FILE = path.join(STATE_DIR, "bridge_state.json");
const POLL_TIMEOUT_MS = 5000;
const CHANNEL_VERSION = "2.1.10";
const ILINK_APP_ID = "bot";
const ILINK_APP_CLIENT_VERSION = "131338";

class RequestTimeoutError extends Error {
  endpoint: string;

  constructor(endpoint: string, timeoutMs: number) {
    super(`timeout endpoint=${endpoint} timeoutMs=${timeoutMs}`);
    this.name = "RequestTimeoutError";
    this.endpoint = endpoint;
  }
}

function log(msg: string): void {
  const ts = new Date().toISOString();
  process.stdout.write(`${ts} [bridge] ${msg}\n`);
}

function ensureDir(dir: string): void {
  fs.mkdirSync(dir, { recursive: true });
}

function readJsonFile<T>(p: string): T | null {
  try {
    return JSON.parse(fs.readFileSync(p, "utf8")) as T;
  } catch {
    return null;
  }
}

function writeJsonFile(p: string, obj: unknown): void {
  fs.writeFileSync(p, JSON.stringify(obj, null, 2) + "\n", "utf8");
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function homeOpenclawPath(...parts: string[]): string {
  return path.join(os.homedir(), ".openclaw", ...parts);
}

function resolveAccount(): { accountId: string; token: string; cloudBaseUrl: string } {
  const ids = readJsonFile<string[]>(homeOpenclawPath("openclaw-weixin", "accounts.json")) || [];
  const accountId = String(ids[0] || "").trim();
  if (!accountId) {
    throw new Error("no weixin account id found; run login first");
  }
  const account = readJsonFile<Json>(homeOpenclawPath("openclaw-weixin", "accounts", `${accountId}.json`)) || {};
  const token = String(account.token || "").trim();
  if (!token) {
    throw new Error(`missing token for account ${accountId}; run login again`);
  }
  const envCloud = String(process.env.OCLAW_WEIXIN_CLOUD_BASE_URL || "").trim();
  const cfgCloud = String(account.baseUrl || "").trim();
  const cloudBaseUrl = (envCloud || cfgCloud || "https://ilinkai.weixin.qq.com").trim();
  const low = cloudBaseUrl.toLowerCase();
  if (
    low.startsWith("http://127.0.0.1")
    || low.startsWith("http://localhost")
    || low.startsWith("https://127.0.0.1")
    || low.startsWith("https://localhost")
  ) {
    throw new Error(
      `invalid cloud baseUrl (${cloudBaseUrl}). It looks like the account file was overwritten. `
        + `Re-run: openclaw channels login --channel openclaw-weixin (QR scan) to restore the cloud baseUrl.`,
    );
  }
  return { accountId, token, cloudBaseUrl };
}

async function postJson(baseUrl: string, endpoint: string, body: Json, token: string, timeoutMs: number): Promise<Json> {
  const url = `${baseUrl.replace(/\/+$/, "")}/${endpoint.replace(/^\/+/, "")}`;
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  const wrapped: Json = { ...body, base_info: { channel_version: CHANNEL_VERSION } };
  const uin = Buffer.from(String(Math.floor(Math.random() * 0xffffffff)), "utf-8").toString("base64");
  try {
    let res: Response;
    try {
      res = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          AuthorizationType: "ilink_bot_token",
          Authorization: `Bearer ${token}`,
          "X-WECHAT-UIN": uin,
          "iLink-App-Id": ILINK_APP_ID,
          "iLink-App-ClientVersion": ILINK_APP_CLIENT_VERSION,
        },
        body: JSON.stringify(wrapped),
        signal: ctl.signal,
      });
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        throw new RequestTimeoutError(endpoint, timeoutMs);
      }
      throw err;
    }
    const text = await res.text();
    if (!res.ok) {
      throw new Error(`HTTP ${res.status} ${endpoint}: ${text.slice(0, 300)}`);
    }
    const parsed = text ? (JSON.parse(text) as Json) : {};
    if (Object.prototype.hasOwnProperty.call(parsed, "ret")) {
      const ret = Number((parsed as Json).ret ?? 0);
      if (Number.isFinite(ret) && ret !== 0) {
        const errcode = (parsed as Json).errcode;
        const errmsg = String((parsed as Json).errmsg || "");
        throw new Error(`ret=${ret} errcode=${String(errcode ?? "")} errmsg=${errmsg} endpoint=${endpoint}`);
      }
    }
    return parsed;
  } finally {
    clearTimeout(timer);
  }
}

function extractTextItems(msg: Json): string {
  const list = Array.isArray(msg.item_list) ? msg.item_list : [];
  const parts: string[] = [];
  for (const item of list) {
    if (!item || typeof item !== "object") continue;
    const row = item as Json;
    const t = Number(row.type || 0);
    if (t !== 1) continue;
    const textItem = row.text_item;
    if (textItem && typeof textItem === "object") {
      const val = String((textItem as Json).text || "").trim();
      if (val) parts.push(val);
    }
  }
  return parts.join("\n").trim();
}

function toNumber(v: unknown, fallback = 0): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function generateClientId(): string {
  // Match the official openclaw-weixin plugin behavior (util/random.ts).
  // Format: `{prefix}:{timestamp}-{8-char hex}`
  return `openclaw-weixin:${Date.now()}-${crypto.randomBytes(4).toString("hex")}`;
}

function parseCursor(v: string): number {
  const n = Number(v);
  return Number.isFinite(n) ? Math.max(0, Math.floor(n)) : 0;
}

async function normalizeLocalCursor(args: {
  token: string;
  accountId: string;
  localCursor: string;
}): Promise<string> {
  const cursor = String(args.localCursor || "").trim();
  const currentInt = parseCursor(cursor);
  if (!cursor || currentInt <= 0) return cursor;

  const current = await postJson(
    LOCAL_BASE_URL,
    "ilink/bot/getupdates",
    {
      channel: "wechat",
      account_id: args.accountId,
      get_updates_buf: cursor,
      longpolling_timeout_ms: 1000,
      limit: 1,
    },
    args.token,
    8000,
  );
  const currentMsgs = Array.isArray(current.msgs) ? current.msgs : [];
  if (currentMsgs.length > 0) {
    return cursor;
  }

  const probe = await postJson(
    LOCAL_BASE_URL,
    "ilink/bot/getupdates",
    {
      channel: "wechat",
      account_id: args.accountId,
      get_updates_buf: "0",
      longpolling_timeout_ms: 1000,
      limit: 1,
    },
    args.token,
    8000,
  );
  const probeMsgs = Array.isArray(probe.msgs) ? probe.msgs : [];
  const probeCursor = parseCursor(String(probe.get_updates_buf || "0"));
  if (probeMsgs.length > 0 && probeCursor <= currentInt) {
    log(`local cursor looks stale after gateway restart; reset ${cursor} -> 0`);
    return "0";
  }
  return cursor;
}

async function forwardInboundToLocal(args: {
  token: string;
  accountId: string;
  msg: Json;
}): Promise<void> {
  const fromUser = String(args.msg.from_user_id || "").trim();
  const toUser = String(args.msg.to_user_id || "").trim();
  if (!fromUser) return;
  if (toUser && fromUser === toUser) return;
  if (toNumber(args.msg.message_type, 1) !== 1) return; // only user -> bot
  const text = extractTextItems(args.msg);
  if (!text) return;
  const contextToken = String(args.msg.context_token || "").trim();
  await postJson(
    LOCAL_BASE_URL,
    "ilink/bot/sendmessage",
    {
      channel: "wechat",
      account_id: args.accountId,
      user_id: fromUser,
      chat_id: fromUser,
      text,
      msg: args.msg,
      metadata: {
        context_token: contextToken,
      },
    },
    args.token,
    15000,
  );
  log(`inbound forwarded: from=${fromUser} textLen=${text.length}`);
}

async function flushLocalReplies(args: {
  token: string;
  accountId: string;
  localCursor: string;
  userContextTokens: TokenMap;
  cloudBaseUrl: string;
}): Promise<string> {
  let cursor = args.localCursor;
  for (let i = 0; i < 3; i += 1) {
    const out = await postJson(
      LOCAL_BASE_URL,
      "ilink/bot/getupdates",
      {
        channel: "wechat",
        account_id: args.accountId,
        get_updates_buf: cursor,
        longpolling_timeout_ms: 1000,
        limit: 20,
      },
      args.token,
      8000,
    );
    const msgs = Array.isArray(out.msgs) ? (out.msgs as Json[]) : [];
    const next = String(out.get_updates_buf || cursor || "").trim();
    const batchCursor = cursor;
    const nextCursor = next || cursor;
    if (!msgs.length) {
      break;
    }
    let allSucceeded = true;
    for (const r of msgs) {
      const toUser = String(r.chat_id || "").trim();
      const text = String(r.text || "").trim();
      if (!toUser || !text) continue;
      const contextToken = String(
        (r.context_token as string) || args.userContextTokens[toUser] || "",
      ).trim();
      if (!contextToken) {
        // Don't advance cursor when we can't produce a valid protocol reply.
        allSucceeded = false;
        log(`reply missing context_token; keep cursor. to=${toUser} textLen=${text.length}`);
        continue;
      }
      const msgBody: Json = {
        from_user_id: "",
        to_user_id: toUser,
        client_id: generateClientId(),
        message_type: 2,
        message_state: 2,
        item_list: [{ type: 1, text_item: { text } }],
        context_token: contextToken || undefined,
      };
      try {
        await postJson(
          args.cloudBaseUrl,
          "ilink/bot/sendmessage",
          {
            msg: msgBody,
          },
          args.token,
          12000,
        );
        log(`reply pushed: to=${toUser} textLen=${text.length}`);
      } catch (err) {
        log(`reply push failed: to=${toUser} err=${String(err)}`);
        allSucceeded = false;
      }
    }
    cursor = allSucceeded ? nextCursor : batchCursor;
  }
  return cursor;
}

async function main(): Promise<void> {
  ensureDir(STATE_DIR);
  const state = (readJsonFile<Json>(STATE_FILE) || {}) as Json;
  let cloudCursor = String(state.cloud_cursor || "").trim();
  let localCursor = String(state.local_cursor || "").trim();
  const userContextTokens: TokenMap =
    typeof state.user_context_tokens === "object" && state.user_context_tokens
      ? (state.user_context_tokens as TokenMap)
      : {};
  const { accountId, token, cloudBaseUrl } = resolveAccount();
  localCursor = await normalizeLocalCursor({ token, accountId, localCursor });
  log(`bridge started account=${accountId} cloud=${cloudBaseUrl} local=${LOCAL_BASE_URL}`);
  // Ensure local path is healthy before entering long poll.
  await postJson(
    LOCAL_BASE_URL,
    "ilink/bot/getupdates",
    {
      channel: "wechat",
      account_id: accountId,
      get_updates_buf: localCursor,
      longpolling_timeout_ms: 1000,
    },
    token,
    8000,
  );
  while (true) {
    try {
      localCursor = await flushLocalReplies({
        token,
        accountId,
        localCursor,
        userContextTokens,
        cloudBaseUrl,
      });
      const out = await postJson(
        cloudBaseUrl,
        "ilink/bot/getupdates",
        {
          get_updates_buf: cloudCursor,
          longpolling_timeout_ms: POLL_TIMEOUT_MS,
        },
        token,
        POLL_TIMEOUT_MS + 5000,
      );
      const msgs = Array.isArray(out.msgs) ? (out.msgs as Json[]) : [];
      const nextCloudCursor = String(out.get_updates_buf || cloudCursor || "").trim();
      if (nextCloudCursor) cloudCursor = nextCloudCursor;
      for (const msg of msgs) {
        const fromUser = String(msg.from_user_id || "").trim();
        const contextToken = String(msg.context_token || "").trim();
        if (fromUser && contextToken) userContextTokens[fromUser] = contextToken;
        await forwardInboundToLocal({ token, accountId, msg });
      }
      localCursor = await flushLocalReplies({
        token,
        accountId,
        localCursor,
        userContextTokens,
        cloudBaseUrl,
      });
      writeJsonFile(STATE_FILE, {
        cloud_cursor: cloudCursor,
        local_cursor: localCursor,
        user_context_tokens: userContextTokens,
        updated_at: new Date().toISOString(),
      });
    } catch (err) {
      if (err instanceof RequestTimeoutError && err.endpoint === "ilink/bot/getupdates") {
        continue;
      }
      log(`loop error: ${String(err)}`);
      await sleep(1200);
    }
  }
}

void main();
