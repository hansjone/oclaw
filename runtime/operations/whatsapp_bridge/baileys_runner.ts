import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import dns from "node:dns/promises";

import makeWASocket, {
  Browsers,
  DisconnectReason,
  fetchLatestBaileysVersion,
  jidNormalizedUser,
  proto,
} from "@whiskeysockets/baileys";
import { HttpsProxyAgent } from "https-proxy-agent";

import { loadAuthState } from "./auth";
import { printQrToTerminal } from "./qr";

type Json = Record<string, unknown>;

const LOCAL_BASE_URL = (process.env.AIA_GATEWAY_BASE_URL || "http://127.0.0.1:8787").trim();
const ACCOUNT_ID = (process.env.AIA_WHATSAPP_ACCOUNT_ID || "wa-default").trim();
const STATE_DIR = (process.env.OCLAW_STATE_DIR || path.resolve(process.cwd(), "state")).trim();
const LOGIN_ONLY = process.argv.includes("--login") || String(process.env.AIA_WHATSAPP_LOGIN_ONLY || "").trim() === "1";
const VERBOSE = process.argv.includes("--verbose") || String(process.env.AIA_WHATSAPP_VERBOSE || "").trim() === "1";
const PROXY_URL = (
  process.env.AIA_WHATSAPP_PROXY_URL ||
  process.env.HTTPS_PROXY ||
  process.env.HTTP_PROXY ||
  process.env.https_proxy ||
  process.env.http_proxy ||
  ""
).trim();
function log(msg: string): void {
  process.stdout.write(`${new Date().toISOString()} [baileys-whatsapp] ${msg}\n`);
}

function ensureDir(dir: string): void {
  fs.mkdirSync(dir, { recursive: true });
}

function pickText(m: proto.IMessage | null | undefined): string {
  const u = unwrapMessage(m);
  if (!u) return "";
  const c = (u.conversation || "").trim();
  if (c) return c;
  const ext = (u.extendedTextMessage?.text || "").trim();
  if (ext) return ext;
  const imgCap = (u.imageMessage?.caption || "").trim();
  if (imgCap) return imgCap;
  const vidCap = (u.videoMessage?.caption || "").trim();
  if (vidCap) return vidCap;
  return "";
}

function unwrapMessage(m: proto.IMessage | null | undefined): proto.IMessage | null {
  if (!m) return null;
  const nested =
    m.ephemeralMessage?.message ||
    m.viewOnceMessage?.message ||
    m.viewOnceMessageV2?.message ||
    m.documentWithCaptionMessage?.message ||
    m.editedMessage?.message ||
    null;
  if (nested) return unwrapMessage(nested);
  return m;
}

function messageContextInfo(m: proto.IMessage | null | undefined): proto.IContextInfo | null | undefined {
  const u = unwrapMessage(m);
  if (!u) return null;
  const top = (u as proto.IMessage & { messageContextInfo?: proto.IMessageContextInfo }).messageContextInfo;
  const fromTop = top?.mentionedJid?.length ? top : null;
  return (
    (fromTop as unknown as proto.IContextInfo) ||
    u.extendedTextMessage?.contextInfo ||
    u.imageMessage?.contextInfo ||
    u.videoMessage?.contextInfo ||
    u.documentMessage?.contextInfo ||
    u.buttonsResponseMessage?.contextInfo ||
    u.listResponseMessage?.contextInfo ||
    u.templateButtonReplyMessage?.contextInfo ||
    null
  );
}

function extractMentionsFromUpsert(msg: proto.IWebMessageInfo): string[] {
  const fromBody = extractMentions(msg.message);
  const outer = (msg as proto.IWebMessageInfo & { messageContextInfo?: { mentionedJid?: string[] } })
    .messageContextInfo?.mentionedJid;
  const outerList = Array.isArray(outer) ? outer.map((j) => String(j || "").trim()).filter(Boolean) : [];
  const merged = [...fromBody, ...outerList];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const j of merged) {
    const key = jidPhone(j) || j;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(j);
  }
  return out;
}

function jidPhone(jid: string): string {
  const head = String(jid || "").split("@")[0]?.split(":")[0] || "";
  return head.replace(/\D/g, "");
}

function jidsSameUser(a: string, b: string): boolean {
  const na = jidNormalizedUser(String(a || "").trim());
  const nb = jidNormalizedUser(String(b || "").trim());
  if (na && nb && na === nb) return true;
  const pa = jidPhone(a);
  const pb = jidPhone(b);
  return pa.length >= 6 && pa === pb;
}

function extractMentions(m: proto.IMessage | null | undefined): string[] {
  const ctx = messageContextInfo(m);
  const raw = ctx?.mentionedJid;
  if (!Array.isArray(raw)) return [];
  return raw.map((j) => String(j || "").trim()).filter(Boolean);
}

function extractQuoteContext(m: proto.IMessage | null | undefined): { participant: string; stanzaId: string } {
  const ctx = messageContextInfo(m);
  return {
    participant: String(ctx?.participant || "").trim(),
    stanzaId: String(ctx?.stanzaId || "").trim(),
  };
}

function resolveSenderJid(key: proto.IMessageKey): string {
  const participant = String(key.participant || "").trim();
  const participantAlt = String((key as any).participantAlt || "").trim();
  if (participantAlt && participant.toLowerCase().endsWith("@lid")) {
    return jidNormalizedUser(participantAlt);
  }
  if (participant) return jidNormalizedUser(participant);
  return "";
}

function jidBaseLocal(jid: string): string {
  const s = String(jid || "").trim().toLowerCase();
  if (!s) return "";
  return s.split("@")[0]?.split(":")[0] || "";
}

function mentionMatchesBotIdentity(mention: string, botId: string): boolean {
  const m = String(mention || "").trim();
  const b = String(botId || "").trim();
  if (!m || !b) return false;
  if (jidNormalizedUser(m) === jidNormalizedUser(b)) return true;
  const mLid = m.toLowerCase().endsWith("@lid");
  const bLid = b.toLowerCase().endsWith("@lid");
  if (mLid || bLid) {
    const ml = jidBaseLocal(m);
    const bl = jidBaseLocal(b);
    if (ml && bl && ml === bl && ml.replace(/\D/g, "").length >= 6) return true;
    return false;
  }
  const mp = jidPhone(m);
  const bp = jidPhone(b);
  return (
    mp.length >= 6 &&
    mp === bp &&
    m.toLowerCase().includes("@s.whatsapp") &&
    b.toLowerCase().includes("@s.whatsapp")
  );
}

function collectBotIdentityJids(
  sock: ReturnType<typeof makeWASocket> | null,
  botPn: string,
  authCreds?: { me?: { id?: string; lid?: string } | null } | null,
): string[] {
  const out = new Set<string>();
  const pn = String(botPn || "").trim();
  if (pn) {
    out.add(pn);
    out.add(jidNormalizedUser(pn));
    const base = jidBaseLocal(pn);
    if (base) out.add(`${base}@s.whatsapp.net`);
  }
  const user = (sock as any)?.user;
  if (user?.id) out.add(String(user.id).trim());
  if (user?.lid) out.add(String(user.lid).trim());
  const creds = authCreds || (sock as any)?.authState?.creds;
  const me = creds?.me;
  if (me?.id) out.add(String(me.id).trim());
  if (me?.lid) out.add(String(me.lid).trim());
  const lidMapping = (sock as any)?.signalRepository?.lidMapping;
  if (lidMapping && pn) {
    for (const variant of Array.from(out)) {
      if (!variant.includes("@s.whatsapp")) continue;
      try {
        if (typeof lidMapping.getLIDForPN === "function") {
          const lid = lidMapping.getLIDForPN(variant);
          if (lid) out.add(String(lid));
        }
      } catch {
        // ignore
      }
    }
  }
  return Array.from(out).filter(Boolean);
}

function pickBotLid(botIds: string[]): string {
  for (const id of botIds) {
    if (String(id || "").toLowerCase().includes("@lid")) return String(id);
  }
  return "";
}

function messageMentionsBot(
  sock: ReturnType<typeof makeWASocket> | null,
  mentions: string[],
  botPn: string,
  botIds?: string[],
  authCreds?: { me?: { id?: string; lid?: string } | null } | null,
): boolean {
  const ids = botIds?.length ? botIds : collectBotIdentityJids(sock, botPn, authCreds);
  if (!ids.length || !mentions.length) return false;
  for (const m of mentions) {
    const mention = String(m || "").trim();
    if (!mention) continue;
    for (const botId of ids) {
      if (mentionMatchesBotIdentity(mention, botId)) return true;
    }
  }
  return false;
}

function isStatusOrBroadcastJid(jid: string): boolean {
  const low = String(jid || "").toLowerCase();
  return low === "status@broadcast" || low.endsWith("@broadcast");
}

function buildInboundPayload(params: {
  chatId: string;
  userId: string;
  text: string;
  raw: unknown;
  isGroup: boolean;
  mentions: string[];
  groupName?: string;
  botJid?: string;
  botLid?: string;
  mentionsBot?: boolean;
}): Json {
  const metadata: Json = {
    source: "whatsapp_baileys",
    raw: params.raw,
    mentions_bot: params.mentionsBot === true,
  };
  if (params.groupName) metadata.group_name = params.groupName;
  if (params.botJid) metadata.bot_jid = params.botJid;
  if (params.botLid) metadata.bot_lid = params.botLid;
  if (params.mentions.length) metadata.mentioned_jids = params.mentions;
  return {
    channel: "whatsapp",
    account_id: ACCOUNT_ID,
    user_id: params.userId,
    chat_id: params.chatId,
    text: params.text,
    is_group: params.isGroup,
    mentions: params.mentions,
    metadata,
  };
}

function decodeBase64Payload(raw: string): { mime: string; data: Buffer } | null {
  const s = String(raw || "").trim();
  if (!s) return null;
  let mime = "application/octet-stream";
  let payload = s;
  const m = s.match(/^data:([^;,]+);base64,(.*)$/i);
  if (m) {
    mime = String(m[1] || mime).trim() || mime;
    payload = String(m[2] || "").trim();
  }
  try {
    const data = Buffer.from(payload.replace(/\s+/g, ""), "base64");
    if (!data.length) return null;
    return { mime, data };
  } catch {
    return null;
  }
}

function readReplyMetadata(reply: Json): Json {
  const meta = (reply as any).metadata;
  return meta && typeof meta === "object" ? (meta as Json) : {};
}

function readMentionJids(meta: Json): string[] {
  const raw = (meta as any).mention_jids ?? (meta as any).mentionJids;
  if (!Array.isArray(raw)) {
    const single = String((meta as any).reply_to_user_id || (meta as any).replyToUserId || "").trim();
    return single ? [single] : [];
  }
  return raw.map((j) => String(j || "").trim()).filter(Boolean);
}

function buildMentionPrefix(mentionJids: string[]): string {
  const tags = mentionJids
    .map((j) => {
      const user = String(j || "").split("@")[0]?.trim();
      return user ? `@${user}` : "";
    })
    .filter(Boolean);
  return tags.length ? `${tags.join(" ")} ` : "";
}

function buildQuotedMessage(params: {
  chatId: string;
  stanzaId: string;
  participant: string;
  quoteText: string;
}): proto.IWebMessageInfo | undefined {
  const stanzaId = String(params.stanzaId || "").trim();
  const chatId = String(params.chatId || "").trim();
  if (!stanzaId || !chatId) return undefined;
  const participant = String(params.participant || "").trim();
  const quoteText = String(params.quoteText || "").trim() || "...";
  return {
    key: {
      remoteJid: chatId,
      fromMe: false,
      id: stanzaId,
      ...(participant ? { participant } : {}),
    },
    message: {
      conversation: quoteText,
    },
  } as proto.IWebMessageInfo;
}

function buildTextSendOptions(params: {
  deliverTo: string;
  text: string;
  reply: Json;
}): { content: { text: string; mentions?: string[] }; quoted?: proto.IWebMessageInfo } {
  const meta = readReplyMetadata(params.reply);
  const mentionJids = readMentionJids(meta);
  const body = String(params.text || "").trim();
  const prefix = mentionJids.length ? buildMentionPrefix(mentionJids) : "";
  const content: { text: string; mentions?: string[] } = { text: prefix ? `${prefix}${body}` : body };
  if (mentionJids.length) content.mentions = mentionJids;

  const quoted = buildQuotedMessage({
    chatId: String((meta as any).quote_remote_jid || (meta as any).quoteRemoteJid || params.deliverTo).trim(),
    stanzaId: String((meta as any).quote_stanza_id || (meta as any).quoteStanzaId || "").trim(),
    participant: String((meta as any).quote_participant || (meta as any).quoteParticipant || "").trim(),
    quoteText: String((meta as any).quote_text || (meta as any).quoteText || "").trim(),
  });

  return quoted ? { content, quoted } : { content };
}

function shouldSendOutboundText(text: string): boolean {
  const t = String(text || "").trim();
  if (!t) return false;
  const normalized = t.toLowerCase().replace(/（/g, "(").replace(/）/g, ")");
  if (normalized === "(silent)" || normalized === "[silent]" || normalized === "no_reply" || normalized === "no reply" || normalized === "静默") {
    return false;
  }
  return true;
}

async function sendReplyWithAttachments(params: {
  sock: ReturnType<typeof makeWASocket> | null;
  deliverTo: string;
  text: string;
  reply: Json;
}): Promise<void> {
  const s = params.sock;
  if (!s) return;
  const reply = params.reply || {};
  const outText = String(params.text || "").trim();
  const mediaPath = String((reply as any).media_path || (reply as any).mediaPath || "").trim();
  const mediaUrl = String((reply as any).media_url || (reply as any).mediaUrl || "").trim();
  const attachments = Array.isArray((reply as any).attachments) ? ((reply as any).attachments as Json[]) : [];
  const textOpts = buildTextSendOptions({ deliverTo: params.deliverTo, text: outText, reply });

  const sendMediaRef = async (source: string): Promise<boolean> => {
    if (!source) return false;
    const msg: Json = { document: source as any };
    if (outText) (msg as any).caption = textOpts.content.text;
    await s.sendMessage(params.deliverTo, msg as any, textOpts.quoted ? { quoted: textOpts.quoted } : undefined);
    return true;
  };

  if (await sendMediaRef(mediaPath || mediaUrl)) return;

  for (const att of attachments) {
    if (!att || typeof att !== "object") continue;
    const raw = String(
      (att as any).data_base64 || (att as any).media_base64 || (att as any).image_base64 || (att as any).data || "",
    ).trim();
    if (!raw) continue;
    const decoded = decodeBase64Payload(raw);
    if (!decoded) continue;
    const msg: Json = {
      document: decoded.data as any,
      mimetype: decoded.mime,
      fileName: String((att as any).name || (att as any).filename || "attachment.bin"),
    };
    if (outText) (msg as any).caption = textOpts.content.text;
    await s.sendMessage(params.deliverTo, msg as any, textOpts.quoted ? { quoted: textOpts.quoted } : undefined);
    return;
  }

  if (outText) {
    try {
      await s.sendMessage(
        params.deliverTo,
        textOpts.content as any,
        textOpts.quoted ? { quoted: textOpts.quoted } : undefined,
      );
    } catch (err) {
      log(`send reply failed (${String(err)}); retry plain text`);
      await s.sendMessage(params.deliverTo, { text: outText });
    }
  }
}

async function postInbound(payload: Json): Promise<Json> {
  const url = `${LOCAL_BASE_URL.replace(/\/+$/, "")}/inbound/whatsapp`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`inbound ${res.status}: ${text.slice(0, 300)}`);
  }
  return text ? (JSON.parse(text) as Json) : {};
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

function _ipLooksHijackedOrUnroutable(ip: string): boolean {
  const s = String(ip || "").trim();
  if (!s) return false;
  if (s.startsWith("198.18.") || s.startsWith("198.19.")) return true; // reserved benchmark range
  if (s.startsWith("0.") || s.startsWith("127.") || s.startsWith("10.")) return true;
  if (s.startsWith("192.168.") || s.startsWith("169.254.")) return true;
  if (/^172\.(1[6-9]|2\d|3[0-1])\./.test(s)) return true;
  return false;
}

async function logNetworkHints(): Promise<void> {
  try {
    const a = await dns.resolve4("web.whatsapp.com").catch(() => []);
    const aaaa = await dns.resolve6("web.whatsapp.com").catch(() => []);
    const sample = [...a, ...aaaa].slice(0, 6);
    if (sample.length > 0) {
      log(`dns web.whatsapp.com => ${sample.join(", ")}`);
      const bad = sample.find(_ipLooksHijackedOrUnroutable);
      if (bad) {
        log(
          `WARNING: DNS looks suspicious (e.g. ${bad}). This often causes WhatsApp Web handshake failures. Try switching system DNS (1.1.1.1/8.8.8.8) or check proxy/hosts rules.`,
        );
      }
    }
  } catch {
    // best-effort
  }
  const httpProxy = process.env.HTTP_PROXY || process.env.http_proxy || "";
  const httpsProxy = process.env.HTTPS_PROXY || process.env.https_proxy || "";
  if (httpProxy || httpsProxy) {
    log(`proxy env detected HTTP_PROXY=${httpProxy ? "set" : "unset"} HTTPS_PROXY=${httpsProxy ? "set" : "unset"}`);
  }
  if (PROXY_URL) {
    log(`proxy configured for Baileys via PROXY_URL=${PROXY_URL}`);
  }
}

function makeDeduper(params: { ttlMs: number; max: number }) {
  const seen = new Map<string, number>();
  const prune = (now: number): void => {
    for (const [k, ts] of seen) {
      if (now - ts > params.ttlMs) {
        seen.delete(k);
      }
    }
    if (seen.size <= params.max) return;
    const ordered = Array.from(seen.entries()).sort((a, b) => a[1] - b[1]);
    const drop = ordered.slice(0, Math.max(0, ordered.length - params.max));
    for (const [k] of drop) seen.delete(k);
  };
  return {
    has: (id: string): boolean => {
      const now = Date.now();
      prune(now);
      const ts = seen.get(id);
      return typeof ts === "number" && now - ts <= params.ttlMs;
    },
    add: (id: string): void => {
      const now = Date.now();
      seen.set(id, now);
      prune(now);
    },
  };
}

async function main(): Promise<void> {
  ensureDir(STATE_DIR);
  const { state, saveCreds } = await loadAuthState(STATE_DIR);
  const { version } = await fetchLatestBaileysVersion();
  const dedupe = makeDeduper({ ttlMs: 10 * 60 * 1000, max: 20_000 });

  let reconnectAttempt = 0;
  let sock: ReturnType<typeof makeWASocket> | null = null;
  let cachedBotIdentityJids: string[] = [];
  const wsAgent = PROXY_URL ? new HttpsProxyAgent(PROXY_URL) : undefined;
  const groupNameCache = new Map<string, { name: string; ts: number }>();
  const GROUP_NAME_TTL_MS = 10 * 60 * 1000;

  const resolveGroupName = async (chatId: string): Promise<string> => {
    const key = String(chatId || "").trim();
    if (!key) return "";
    const cached = groupNameCache.get(key);
    const now = Date.now();
    if (cached && now - cached.ts < GROUP_NAME_TTL_MS) return cached.name;
    const s = sock;
    if (!s) return cached?.name || "";
    try {
      const meta = await s.groupMetadata(key);
      const name = String(meta?.subject || "").trim();
      groupNameCache.set(key, { name, ts: now });
      return name;
    } catch {
      return cached?.name || "";
    }
  };

  const connectOnce = async () => {
    sock = makeWASocket({
      auth: state,
      browser: Browsers.windows("oclaw"),
      version,
      agent: wsAgent as any,
      printQRInTerminal: false,
      generateHighQualityLinkPreview: false,
    });

    sock.ev.on("creds.update", async () => {
      await saveCreds();
      const meId = sock?.user?.id ? String(sock.user.id) : "";
      const ids = collectBotIdentityJids(sock, meId, state.creds);
      if (ids.length) cachedBotIdentityJids = ids;
    });

    sock.ev.on("connection.update", async (update) => {
      if (update.qr) {
        log("QR received. Scan it from WhatsApp -> Linked devices.");
        printQrToTerminal(update.qr);
      }
      if (update.connection === "open") {
        reconnectAttempt = 0;
        const me = sock?.user?.id ? jidNormalizedUser(sock.user.id) : "";
        const botIds = collectBotIdentityJids(sock, sock?.user?.id ? String(sock.user.id) : "", state.creds);
        cachedBotIdentityJids = botIds;
        log(`connected. me=${me || "unknown"} botIds=${botIds.join(",") || "none"} loginOnly=${LOGIN_ONLY}`);
        if (LOGIN_ONLY) {
          log("login-only mode: exiting after successful link.");
          process.exit(0);
        }
      }
      if (update.connection === "close") {
        const statusCode = (update.lastDisconnect?.error as any)?.output?.statusCode as number | undefined;
        const reason = statusCode ? (DisconnectReason as any)[statusCode] || String(statusCode) : "unknown";
        const errText = String(update.lastDisconnect?.error || "").slice(0, 200);
        log(`disconnected reason=${reason} statusCode=${String(statusCode || "")} err=${errText}`);
        if (statusCode === DisconnectReason.loggedOut) {
          log("logged out: delete data/channel_sidecar/whatsapp/state/auth to re-link.");
          return;
        }
        reconnectAttempt += 1;
        const base = Math.min(30_000, 1000 * Math.pow(2, Math.min(6, reconnectAttempt)));
        const jitter = Math.floor(Math.random() * 500);
        const delay = base + jitter;
        log(`reconnecting in ${delay}ms attempt=${reconnectAttempt}`);
        await sleep(delay);
        await connectOnce();
      }
    });

    sock.ev.on("messages.upsert", async (upsert) => {
      const msgs = Array.isArray(upsert.messages) ? upsert.messages : [];
      for (const msg of msgs) {
        try {
          const key = msg.key;
          const id = String(key.id || "").trim();
          const remoteJid = String(key.remoteJid || "").trim();
          if (!id || !remoteJid) continue;
          if (isStatusOrBroadcastJid(remoteJid)) continue;
          if (key.fromMe) continue;
          if (dedupe.has(id)) continue;
          dedupe.add(id);

          const text = pickText(msg.message);
          if (!text) continue;

          const isGroup = remoteJid.endsWith("@g.us");
          const participantRaw = String(key.participant || "").trim();
          const participantAlt = String((key as any).participantAlt || "").trim();
          const userId = isGroup
            ? resolveSenderJid(key) || jidNormalizedUser(remoteJid)
            : jidNormalizedUser(remoteJid);
          const chatId = jidNormalizedUser(remoteJid);
          const mentions = extractMentionsFromUpsert(msg);
          const quote = extractQuoteContext(msg.message);
          const botJidRaw = sock?.user?.id ? String(sock.user.id).trim() : "";
          const botJid = botJidRaw ? jidNormalizedUser(botJidRaw) : "";
          const botIdentityJids = Array.from(
            new Set([...cachedBotIdentityJids, ...collectBotIdentityJids(sock, botJidRaw, state.creds)]),
          );
          if (botIdentityJids.length > cachedBotIdentityJids.length) {
            cachedBotIdentityJids = botIdentityJids;
          }
          const botLid = pickBotLid(botIdentityJids);
          const mentionsBot = messageMentionsBot(sock, mentions, botJidRaw, botIdentityJids);
          const isReplyToBot = Boolean(
            botJidRaw &&
              quote.participant &&
              !mentions.length &&
              botIdentityJids.some((botId) => mentionMatchesBotIdentity(quote.participant, botId)),
          );

          const groupName = isGroup ? await resolveGroupName(chatId) : "";

          const raw = {
            id,
            remoteJid,
            participant: participantRaw || null,
            participantAlt: participantAlt || null,
            pushName: (msg as any).pushName || null,
            messageTimestamp: (msg as any).messageTimestamp || null,
            quotedParticipant: quote.participant || null,
            quotedStanzaId: quote.stanzaId || null,
            isReplyToBot,
            mentionsBot,
            mentionedJids: mentions,
            botLid: botLid || null,
          };

          const inbound = buildInboundPayload({
            chatId,
            userId,
            text,
            raw,
            isGroup,
            mentions,
            groupName: groupName || undefined,
            botJid: botJidRaw || botJid || undefined,
            botLid: botLid || undefined,
            mentionsBot,
          });
          if (VERBOSE || isGroup) {
            log(
              `inbound group=${isGroup} chat=${chatId} user=${userId} mentions=${mentions.length} mentionsBot=${mentionsBot} replyToBot=${isReplyToBot} textLen=${text.length} mention0=${mentions[0] || ""} botLid=${botLid || ""}`,
            );
          } else if (VERBOSE) {
            log(`inbound posting chat=${chatId} user=${userId} textLen=${text.length}`);
          }
          const out = await postInbound(inbound);
          const replies = Array.isArray(out.replies) ? (out.replies as Json[]) : [];
          if (isGroup || VERBOSE) log(`inbound ok chat=${chatId} replies=${replies.length}`);
          for (const r of replies) {
            const outText = String((r as any).text || "").trim();
            if (!shouldSendOutboundText(outText) && !(Array.isArray((r as any).attachments) && (r as any).attachments.length)) {
              if (VERBOSE) log(`skip outbound reply chat=${chatId} (nonsend text)`);
              continue;
            }
            const deliverTo = String((r as any).chat_id || chatId).trim() || chatId;
            await sendReplyWithAttachments({ sock, deliverTo, text: outText, reply: r });
          }
        } catch (err) {
          log(`handle message error: ${String(err)}`);
        }
      }
    });
  };

  log(`runner started local=${LOCAL_BASE_URL} stateDir=${STATE_DIR} verbose=${VERBOSE} node=${process.version}`);
  await logNetworkHints();
  await connectOnce();
}

void main();

