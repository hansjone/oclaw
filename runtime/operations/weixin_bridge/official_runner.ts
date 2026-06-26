import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

type Json = Record<string, unknown>;
type TokenMap = Record<string, string>;

const LOCAL_BASE_URL = (process.env.AIA_GATEWAY_BASE_URL || "http://127.0.0.1:8787").trim();
const STATE_DIR = (process.env.OCLAW_STATE_DIR || path.resolve(process.cwd(), "state")).trim();
const STATE_FILE = path.join(STATE_DIR, "official_bridge_state.json");
const LOG_FILE = String(process.env.OCLAW_WEIXIN_LOG_FILE || "").trim();
const POLL_TIMEOUT_MS = 35_000;
const DEFAULT_CDN_BASE_URL = "https://novac2c.cdn.weixin.qq.com/c2c";

type OfficialModules = {
  getUpdates: (params: {
    baseUrl: string;
    token?: string;
    get_updates_buf?: string;
    timeoutMs?: number;
  }) => Promise<Json>;
  setContextToken: (accountId: string, userId: string, token: string) => void;
  getContextToken: (accountId: string, userId: string) => string | undefined;
  restoreContextTokens: (accountId: string) => void;
  weixinMessageToMsgContext: (msg: Json, accountId: string, opts?: Json) => Json;
  downloadMediaFromItem: (
    item: Json,
    deps: {
      cdnBaseUrl: string;
      saveMedia: (
        buffer: Buffer,
        contentType?: string,
        subdir?: string,
        maxBytes?: number,
        originalFilename?: string,
      ) => Promise<{ path: string }>;
      log: (msg: string) => void;
      errLog: (msg: string) => void;
      label: string;
    },
  ) => Promise<Json>;
  sendMessageWeixin: (params: {
    to: string;
    text: string;
    opts: { baseUrl: string; token?: string; contextToken?: string };
  }) => Promise<{ messageId: string }>;
  sendWeixinMediaFile: (params: {
    filePath: string;
    to: string;
    text: string;
    opts: { baseUrl: string; token?: string; contextToken?: string };
    cdnBaseUrl: string;
  }) => Promise<{ messageId: string }>;
};

let officialModulesPromise: Promise<OfficialModules> | null = null;

class HttpStatusError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "HttpStatusError";
    this.status = status;
  }
}

function log(msg: string): void {
  const line = `${new Date().toISOString()} [official-weixin] ${msg}\n`;
  // When started via Start-Process -RedirectStandardOutput, Node may block-buffer stdout;
  // append directly so operators see poll/inbound lines in weixin_sidecar.log immediately.
  if (LOG_FILE) {
    try {
      fs.appendFileSync(LOG_FILE, line, "utf8");
    } catch {
      // ignore
    }
  }
  try {
    process.stdout.write(line);
  } catch {
    // ignore
  }
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

async function withTimeout<T>(promise: Promise<T>, ms: number, label: string): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new Error(`${label} timeout after ${ms}ms`)), ms);
  });
  try {
    return await Promise.race([promise, timeout]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

function resolvePluginRoot(): string {
  const configured = String(process.env.OCLAW_WEIXIN_PLUGIN_ROOT || "").trim();
  return configured || path.join(process.cwd(), "node_modules", "@tencent-weixin", "openclaw-weixin");
}

async function loadOfficialModules(): Promise<OfficialModules> {
  if (officialModulesPromise) {
    return officialModulesPromise;
  }
  officialModulesPromise = (async () => {
    const pluginRoot = resolvePluginRoot();
    const srcRoot = path.join(pluginRoot, "src");
    const importTs = async (relativePath: string): Promise<any> => {
      const fullPath = path.join(srcRoot, relativePath);
      return import(pathToFileURL(fullPath).href);
    };
    const [apiMod, inboundMod, mediaMod, sendMod, sendMediaMod] = await Promise.all([
      importTs(path.join("api", "api.ts")),
      importTs(path.join("messaging", "inbound.ts")),
      importTs(path.join("media", "media-download.ts")),
      importTs(path.join("messaging", "send.ts")),
      importTs(path.join("messaging", "send-media.ts")),
    ]);
    return {
      getUpdates: apiMod.getUpdates,
      setContextToken: inboundMod.setContextToken,
      getContextToken: inboundMod.getContextToken,
      restoreContextTokens: inboundMod.restoreContextTokens,
      weixinMessageToMsgContext: inboundMod.weixinMessageToMsgContext,
      downloadMediaFromItem: mediaMod.downloadMediaFromItem,
      sendMessageWeixin: sendMod.sendMessageWeixin,
      sendWeixinMediaFile: sendMediaMod.sendWeixinMediaFile,
    } satisfies OfficialModules;
  })();
  return officialModulesPromise;
}

async function resolveAccount(): Promise<{ accountId: string; token: string; cloudBaseUrl: string }> {
  if (!String(process.env.OPENCLAW_STATE_DIR || "").trim()) {
    process.env.OPENCLAW_STATE_DIR = STATE_DIR;
  }
  const pluginRoot = resolvePluginRoot();
  const srcRoot = path.join(pluginRoot, "src");
  const importTs = async (relativePath: string): Promise<any> => {
    const fullPath = path.join(srcRoot, relativePath);
    return import(pathToFileURL(fullPath).href);
  };
  const accountsMod = await importTs(path.join("auth", "accounts.ts"));
  const listIds = accountsMod.listIndexedWeixinAccountIds as (() => string[]) | undefined;
  const loadAcc = accountsMod.loadWeixinAccount as ((accountId: string) => any) | undefined;
  if (!listIds || !loadAcc) {
    throw new Error("weixin plugin accounts module missing exports");
  }
  const ids = listIds() || [];
  const accountId = String(ids[0] || "").trim();
  if (!accountId) {
    throw new Error("no weixin account id found; run login first");
  }
  const data = loadAcc(accountId) || {};
  const token = String(data.token || "").trim();
  if (!token) {
    throw new Error(`missing token for account ${accountId}; run login again`);
  }
  const envCloud = String(process.env.OCLAW_WEIXIN_CLOUD_BASE_URL || "").trim();
  const cfgCloud = String(data.baseUrl || "").trim();
  const cloudBaseUrl = (envCloud || cfgCloud || "https://ilinkai.weixin.qq.com").trim();
  return { accountId, token, cloudBaseUrl };
}

function resolveHeaders(token: string): Record<string, string> {
  return {
    "Content-Type": "application/json",
    AuthorizationType: "ilink_bot_token",
    Authorization: `Bearer ${token}`,
  };
}

async function postLocalJson(token: string, route: string, body: Json, timeoutMs = 8000): Promise<Json> {
  const url = `${LOCAL_BASE_URL.replace(/\/+$/, "")}/${route.replace(/^\/+/, "")}`;
  const res = await fetch(url, {
    method: "POST",
    headers: resolveHeaders(token),
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(timeoutMs),
  });
  const text = await res.text();
  if (!res.ok) {
    throw new HttpStatusError(res.status, `${route} ${res.status}: ${text.slice(0, 300)}`);
  }
  return text ? (JSON.parse(text) as Json) : {};
}

async function getLocalJson(token: string, route: string, timeoutMs = 8000): Promise<Json> {
  const url = `${LOCAL_BASE_URL.replace(/\/+$/, "")}/${route.replace(/^\/+/, "")}`;
  const res = await fetch(url, {
    method: "GET",
    headers: resolveHeaders(token),
    signal: AbortSignal.timeout(timeoutMs),
  });
  const text = await res.text();
  if (!res.ok) {
    throw new HttpStatusError(res.status, `${route} ${res.status}: ${text.slice(0, 300)}`);
  }
  return text ? (JSON.parse(text) as Json) : {};
}

async function flushWeixinDbOutbound(args: {
  modules: OfficialModules;
  token: string;
  accountId: string;
  cloudBaseUrl: string;
  userContextTokens: TokenMap;
}): Promise<void> {
  const q = encodeURIComponent(args.accountId);
  const out = await getLocalJson(args.token, `weixin/outbound/pending?account_id=${q}&limit=20`, 8000);
  const items = Array.isArray(out.items) ? (out.items as Json[]) : [];
  for (const item of items) {
    const toUser = String(item.chat_id || "").trim();
    const text = String(item.text || "").trim();
    const msgId = String(item.id || "").trim();
    if (!toUser || !text || !msgId) continue;
    const contextToken = String(
      (item.context_token as string) ||
        args.modules.getContextToken(args.accountId, toUser) ||
        args.userContextTokens[toUser] ||
        "",
    ).trim();
    if (!contextToken) {
      log(`db proactive reply missing context_token; keep pending. id=${msgId} to=${toUser}`);
      continue;
    }
    try {
      await args.modules.sendMessageWeixin({
        to: toUser,
        text,
        opts: {
          baseUrl: args.cloudBaseUrl,
          token: args.token,
          contextToken,
        },
      });
      await postLocalJson(args.token, "weixin/outbound/ack", { id: msgId, ok: true }, 8000);
      log(`db proactive reply sent: id=${msgId} to=${toUser} textLen=${text.length}`);
    } catch (err) {
      try {
        await postLocalJson(
          args.token,
          "weixin/outbound/ack",
          { id: msgId, ok: false, error: String(err) },
          8000,
        );
      } catch (_) {
        // ignore ack failure
      }
      log(`db proactive reply failed: id=${msgId} to=${toUser} err=${String(err)}`);
    }
  }
}

async function flushLocalProactiveReplies(args: {
  modules: OfficialModules;
  token: string;
  accountId: string;
  cloudBaseUrl: string;
  localCursor: string;
  userContextTokens: TokenMap;
}): Promise<string> {
  let cursor = args.localCursor;
  for (let i = 0; i < 3; i += 1) {
    const out = await postLocalJson(
      args.token,
      "ilink/bot/getupdates",
      {
        channel: "wechat",
        account_id: args.accountId,
        get_updates_buf: cursor,
        longpolling_timeout_ms: 1000,
        limit: 20,
      },
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
        (r.context_token as string) ||
          args.modules.getContextToken(args.accountId, toUser) ||
          args.userContextTokens[toUser] ||
          "",
      ).trim();
      if (!contextToken) {
        allSucceeded = false;
        log(`proactive reply missing context_token; keep cursor. to=${toUser} textLen=${text.length}`);
        continue;
      }
      try {
        await args.modules.sendMessageWeixin({
          to: toUser,
          text,
          opts: {
            baseUrl: args.cloudBaseUrl,
            token: args.token,
            contextToken,
          },
        });
        log(`proactive reply sent: to=${toUser} textLen=${text.length}`);
      } catch (err) {
        log(`proactive reply failed: to=${toUser} err=${String(err)}`);
        allSucceeded = false;
      }
    }
    cursor = allSucceeded ? nextCursor : batchCursor;
  }
  return cursor;
}

async function postNativeReply(token: string, body: Json): Promise<Json> {
  const url = `${LOCAL_BASE_URL.replace(/\/+$/, "")}/weixin/native/reply`;
  const timeoutMs = Number(process.env.OCLAW_WEIXIN_NATIVE_REPLY_TIMEOUT_MS || "100000") || 100000;
  const res = await fetch(url, {
    method: "POST",
    headers: resolveHeaders(token),
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(timeoutMs),
  });
  const text = await res.text();
  if (!res.ok) {
    throw new HttpStatusError(res.status, `native reply ${res.status}: ${text.slice(0, 300)}`);
  }
  return text ? (JSON.parse(text) as Json) : {};
}

async function safeSendNativeFailureNotice(modules: OfficialModules, params: {
  to: string;
  cloudBaseUrl: string;
  token: string;
  contextToken?: string;
  err: unknown;
}): Promise<void> {
  const msg = `[weixin] native reply failed: ${String(params.err)}`.slice(0, 3500);
  try {
    await modules.sendMessageWeixin({
      to: params.to,
      text: msg,
      opts: {
        baseUrl: params.cloudBaseUrl,
        token: params.token,
        contextToken: params.contextToken,
      },
    });
  } catch {
    // best-effort
  }
}

function inferExtension(contentType: string, originalFilename: string): string {
  const explicit = path.extname(originalFilename || "").trim();
  if (explicit) {
    return explicit;
  }
  const low = (contentType || "").toLowerCase();
  if (low.includes("jpeg")) return ".jpg";
  if (low.includes("png")) return ".png";
  if (low.includes("gif")) return ".gif";
  if (low.includes("webp")) return ".webp";
  if (low.includes("mp4")) return ".mp4";
  if (low.includes("wav")) return ".wav";
  if (low.includes("pdf")) return ".pdf";
  if (low.includes("text/plain")) return ".txt";
  return ".bin";
}

async function saveMediaBuffer(
  buffer: Buffer,
  contentType?: string,
  subdir?: string,
  maxBytes?: number,
  originalFilename?: string,
): Promise<{ path: string }> {
  if (typeof maxBytes === "number" && maxBytes > 0 && buffer.length > maxBytes) {
    throw new Error(`media exceeds max bytes: ${buffer.length} > ${maxBytes}`);
  }
  const dir = path.join(STATE_DIR, "media", subdir || "inbound");
  ensureDir(dir);
  const filePath = path.join(
    dir,
    `${Date.now()}-${Math.random().toString(16).slice(2, 10)}${inferExtension(contentType || "", originalFilename || "")}`,
  );
  await fs.promises.writeFile(filePath, buffer);
  return { path: filePath };
}

function pickDownloadableMedia(msg: Json): Json | null {
  const items = Array.isArray(msg.item_list) ? (msg.item_list as Json[]) : [];
  const hasDownloadableMedia = (item: Json, kind: string): boolean => {
    const media = item[kind] && typeof item[kind] === "object" ? (item[kind] as Json).media : null;
    if (!media || typeof media !== "object") return false;
    return Boolean((media as Json).encrypt_query_param || (media as Json).full_url);
  };
  const direct =
    items.find((item) => Number(item.type || 0) === 3 && hasDownloadableMedia(item, "image_item")) ||
    items.find((item) => Number(item.type || 0) === 4 && hasDownloadableMedia(item, "video_item")) ||
    items.find((item) => Number(item.type || 0) === 5 && hasDownloadableMedia(item, "file_item")) ||
    items.find((item) => Number(item.type || 0) === 2 && hasDownloadableMedia(item, "voice_item"));
  if (direct) {
    return direct;
  }
  for (const item of items) {
    if (Number(item.type || 0) !== 1) continue;
    const refMsg = item.ref_msg;
    if (!refMsg || typeof refMsg !== "object") continue;
    const messageItem = (refMsg as Json).message_item;
    if (!messageItem || typeof messageItem !== "object") continue;
    const ref = messageItem as Json;
    if (
      (Number(ref.type || 0) === 3 && hasDownloadableMedia(ref, "image_item")) ||
      (Number(ref.type || 0) === 4 && hasDownloadableMedia(ref, "video_item")) ||
      (Number(ref.type || 0) === 5 && hasDownloadableMedia(ref, "file_item")) ||
      (Number(ref.type || 0) === 2 && hasDownloadableMedia(ref, "voice_item"))
    ) {
      return ref;
    }
  }
  return null;
}

function buildAttachmentsFromMedia(mediaOpts: Json): Json[] {
  const out: Json[] = [];
  const pushIf = (key: string, mimeKey: string, kind: string): void => {
    const filePath = String(mediaOpts[key] || "").trim();
    if (!filePath) return;
    out.push({
      kind,
      local_path: filePath,
      media_type: String(mediaOpts[mimeKey] || "").trim(),
    });
  };
  pushIf("decryptedPicPath", "", "image");
  pushIf("decryptedVideoPath", "", "video");
  pushIf("decryptedFilePath", "fileMediaType", "file");
  pushIf("decryptedVoicePath", "voiceMediaType", "voice");
  return out;
}

function _decodeReplyBase64Attachment(att: Json): { filePath: string; mime: string } | null {
  const b64Raw = String(
    att.data_base64 || att.media_base64 || att.image_base64 || att.video_base64 || att.audio_base64 || att.data || "",
  ).trim();
  if (!b64Raw) return null;
  let mime = String(att.media_type || att.mime_type || att.mime || "application/octet-stream").trim();
  let payload = b64Raw;
  const m = b64Raw.match(/^data:([^;,]+);base64,(.*)$/i);
  if (m) {
    mime = String(m[1] || mime).trim() || mime;
    payload = String(m[2] || "").trim();
  }
  try {
    const buf = Buffer.from(payload.replace(/\s+/g, ""), "base64");
    if (!buf.length) return null;
    const dir = path.join(STATE_DIR, "media", "outbound");
    ensureDir(dir);
    const ext = inferExtension(mime || "application/octet-stream", String(att.name || att.filename || "").trim());
    const filePath = path.join(dir, `${Date.now()}-${Math.random().toString(16).slice(2, 10)}${ext}`);
    fs.writeFileSync(filePath, buf);
    return { filePath, mime };
  } catch {
    return null;
  }
}

async function handleInboundMessage(
  modules: OfficialModules,
  params: {
    token: string;
    accountId: string;
    cloudBaseUrl: string;
    full: Json;
    userContextTokens: TokenMap;
    localCursor: string;
  },
): Promise<string> {
  const fromUser = String(params.full.from_user_id || "").trim();
  const toUser = String(params.full.to_user_id || "").trim();
  if (!fromUser) {
    log(`skip inbound: missing from_user_id`);
    return params.localCursor;
  }
  if (toUser && toUser === fromUser) {
    log(`skip inbound: self-message from=${fromUser}`);
    return params.localCursor;
  }
  if (Number(params.full.message_type || 1) !== 1) {
    log(`skip inbound: message_type=${String(params.full.message_type ?? "")} from=${fromUser}`);
    return params.localCursor;
  }
  log(`inbound from=${fromUser} to=${toUser || "-"}`);

  const contextToken = String(params.full.context_token || "").trim();
  if (contextToken) {
    params.userContextTokens[fromUser] = contextToken;
    modules.setContextToken(params.accountId, fromUser, contextToken);
  }

  const mediaItem = pickDownloadableMedia(params.full);
  let mediaOpts: Json = {};
  if (mediaItem) {
    log("media download start");
    try {
      mediaOpts = await withTimeout(
        modules.downloadMediaFromItem(mediaItem, {
          cdnBaseUrl: DEFAULT_CDN_BASE_URL,
          saveMedia: saveMediaBuffer,
          log: (msg: string) => log(`media ${msg}`),
          errLog: (msg: string) => log(`media-error ${msg}`),
          label: "inbound",
        }),
        Number(process.env.OCLAW_WEIXIN_MEDIA_TIMEOUT_MS || "90000") || 90000,
        "media download",
      );
      log("media download done");
    } catch (err) {
      log(`media download failed err=${String(err)}`);
      mediaOpts = {};
    }
  }
  const ctx = modules.weixinMessageToMsgContext(params.full, params.accountId, mediaOpts);
  const bodyText = String((ctx as Json).Body || "").trim();
  const attachCount = buildAttachmentsFromMedia(mediaOpts).length;
  log(`native call bodyLen=${bodyText.length} attachments=${attachCount}`);
  let replies: Json[] = [];
  const tNative0 = Date.now();
  try {
    const native = await postNativeReply(params.token, {
      channel: "wechat",
      account_id: params.accountId,
      ctx,
      attachments: buildAttachmentsFromMedia(mediaOpts),
      metadata: {
        source: "weixin_official_native",
        raw: {
          msg: params.full,
        },
      },
    });
    replies = Array.isArray(native.replies) ? (native.replies as Json[]) : [];
    const firstText = replies.length ? String((replies[0] as Json).text || "").trim() : "";
    log(`native done ms=${Date.now() - tNative0} replies=${replies.length} firstTextLen=${firstText.length}`);
    if (!replies.length) {
      log("native returned 0 replies (empty inbound, gateway suppress, or LLM produced no text)");
    }
  } catch (err) {
    log(`native reply failed; no fallback enabled err=${String(err)}`);
    await safeSendNativeFailureNotice(modules, {
      to: fromUser,
      cloudBaseUrl: params.cloudBaseUrl,
      token: params.token,
      contextToken: contextToken || undefined,
      err,
    });
    return params.localCursor;
  }
  for (const reply of replies) {
    const text = String(reply.text || "").trim();
    const mediaPath = String(reply.media_path || reply.mediaPath || "").trim();
    const mediaUrl = String(reply.media_url || reply.mediaUrl || "").trim();
    const deliverTo = String(reply.chat_id || reply.to || fromUser).trim() || fromUser;
    const replyContextToken = String(
      reply.context_token || modules.getContextToken(params.accountId, deliverTo) || contextToken || "",
    ).trim();
    const replyAtts = Array.isArray(reply.attachments) ? (reply.attachments as Json[]) : [];
    let inlineMediaPath = "";
    for (const att of replyAtts) {
      if (!att || typeof att !== "object") continue;
      const decoded = _decodeReplyBase64Attachment(att);
      if (decoded?.filePath) {
        inlineMediaPath = decoded.filePath;
        break;
      }
    }
    if (mediaPath || mediaUrl || inlineMediaPath) {
      const filePath = mediaPath || mediaUrl || inlineMediaPath;
      await modules.sendWeixinMediaFile({
        filePath,
        to: deliverTo,
        text,
        opts: {
          baseUrl: params.cloudBaseUrl,
          token: params.token,
          contextToken: replyContextToken || undefined,
        },
        cdnBaseUrl: DEFAULT_CDN_BASE_URL,
      });
      log(`reply media sent to=${deliverTo} textLen=${text.length}`);
      continue;
    }
    if (!text) continue;
    await modules.sendMessageWeixin({
      to: deliverTo,
      text,
      opts: {
        baseUrl: params.cloudBaseUrl,
        token: params.token,
        contextToken: replyContextToken || undefined,
      },
    });
    log(`reply text sent to=${deliverTo} textLen=${text.length}`);
  }
  return params.localCursor;
}

async function main(): Promise<void> {
  ensureDir(STATE_DIR);
  const state = (readJsonFile<Json>(STATE_FILE) || {}) as Json;
  let cloudCursor = String(state.cloud_cursor || "").trim();
  let localCursor = String(state.local_cursor || "").trim();
  const userContextTokens: TokenMap =
    state.user_context_tokens && typeof state.user_context_tokens === "object"
      ? (state.user_context_tokens as TokenMap)
      : {};
  const { accountId, token, cloudBaseUrl } = await resolveAccount();
  const modules = await loadOfficialModules();
  modules.restoreContextTokens(accountId);
  log(`official runner started account=${accountId} cloud=${cloudBaseUrl} local=${LOCAL_BASE_URL}`);
  while (true) {
    try {
      try {
        await flushWeixinDbOutbound({
          modules,
          token,
          accountId,
          cloudBaseUrl,
          userContextTokens,
        });
      } catch (err) {
        log(`db proactive flush error: ${String(err)}`);
      }
      localCursor = await flushLocalProactiveReplies({
        modules,
        token,
        accountId,
        cloudBaseUrl,
        localCursor,
        userContextTokens,
      });
      const out = await modules.getUpdates({
        baseUrl: cloudBaseUrl,
        token,
        get_updates_buf: cloudCursor,
        timeoutMs: POLL_TIMEOUT_MS + 5000,
      });
      const msgs = Array.isArray(out.msgs) ? (out.msgs as Json[]) : [];
      const ret = Number(out.ret ?? 0);
      const errcode = out.errcode;
      if (ret !== 0 || errcode != null) {
        log(`poll ret=${ret} errcode=${String(errcode ?? "")} errmsg=${String(out.errmsg ?? "")}`);
      } else if (msgs.length > 0) {
        log(`poll batch=${msgs.length}`);
      }
      const nextCloudCursor = String(out.get_updates_buf || cloudCursor || "").trim();
      if (nextCloudCursor) {
        cloudCursor = nextCloudCursor;
      }
      for (const full of msgs) {
        await handleInboundMessage(modules, {
          token,
          accountId,
          cloudBaseUrl,
          full,
          userContextTokens,
          localCursor: "0",
        });
      }
      writeJsonFile(STATE_FILE, {
        cloud_cursor: cloudCursor,
        local_cursor: localCursor,
        user_context_tokens: userContextTokens,
        updated_at: new Date().toISOString(),
      });
    } catch (err) {
      log(`loop error: ${String(err)}`);
      await sleep(1500);
    }
  }
}

void main();
