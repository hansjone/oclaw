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
  if (!m) return "";
  const c = (m.conversation || "").trim();
  if (c) return c;
  const ext = (m.extendedTextMessage?.text || "").trim();
  if (ext) return ext;
  const imgCap = (m.imageMessage?.caption || "").trim();
  if (imgCap) return imgCap;
  const vidCap = (m.videoMessage?.caption || "").trim();
  if (vidCap) return vidCap;
  return "";
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
}): Json {
  return {
    channel: "whatsapp",
    account_id: ACCOUNT_ID,
    user_id: params.userId,
    chat_id: params.chatId,
    text: params.text,
    metadata: {
      source: "whatsapp_baileys",
      raw: params.raw,
    },
  };
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
  const wsAgent = PROXY_URL ? new HttpsProxyAgent(PROXY_URL) : undefined;

  const connectOnce = async () => {
    sock = makeWASocket({
      auth: state,
      browser: Browsers.windows("oclaw"),
      version,
      agent: wsAgent as any,
      printQRInTerminal: false,
      generateHighQualityLinkPreview: false,
    });

    sock.ev.on("creds.update", saveCreds);

    sock.ev.on("connection.update", async (update) => {
      if (update.qr) {
        log("QR received. Scan it from WhatsApp -> Linked devices.");
        printQrToTerminal(update.qr);
      }
      if (update.connection === "open") {
        reconnectAttempt = 0;
        const me = sock?.user?.id ? jidNormalizedUser(sock.user.id) : "";
        log(`connected. me=${me || "unknown"} loginOnly=${LOGIN_ONLY}`);
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
          const from = isGroup ? String(key.participant || "").trim() : remoteJid;
          const userId = from ? jidNormalizedUser(from) : jidNormalizedUser(remoteJid);
          const chatId = jidNormalizedUser(remoteJid);

          const raw = {
            id,
            remoteJid,
            participant: key.participant || null,
            pushName: (msg as any).pushName || null,
            messageTimestamp: (msg as any).messageTimestamp || null,
          };

          const inbound = buildInboundPayload({ chatId, userId, text, raw });
          if (VERBOSE) log(`inbound posting chat=${chatId} user=${userId} textLen=${text.length}`);
          const out = await postInbound(inbound);
          const replies = Array.isArray(out.replies) ? (out.replies as Json[]) : [];
          if (VERBOSE) log(`inbound ok replies=${replies.length}`);
          for (const r of replies) {
            const outText = String((r as any).text || "").trim();
            if (!outText) continue;
            const deliverTo = String((r as any).chat_id || chatId).trim() || chatId;
            await sock?.sendMessage(deliverTo, { text: outText });
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

