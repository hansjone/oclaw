import fs from "node:fs";
import path from "node:path";

export type BridgeStatus = {
  connection: "connecting" | "qr" | "open" | "close" | "logged_out" | "needs_rebind" | "stopped";
  me: string;
  phone: string;
  qr: string;
  qr_data_url: string;
  qr_png: string;
  last_disconnect_reason: string;
  last_disconnect_status: number | null;
  last_error: string;
  reconnect_attempt: number;
  login_only: boolean;
  updated_at: string;
};

const STATUS_FILE = "bridge_status.json";

function phoneFromMe(me: string): string {
  const head = String(me || "").split("@")[0]?.split(":")[0] || "";
  return head.replace(/\D/g, "");
}

export function statusPath(stateDir: string): string {
  return path.join(stateDir, STATUS_FILE);
}

export function writeBridgeStatus(stateDir: string, patch: Partial<BridgeStatus>): BridgeStatus {
  fs.mkdirSync(stateDir, { recursive: true });
  const p = statusPath(stateDir);
  let prev: Partial<BridgeStatus> = {};
  try {
    if (fs.existsSync(p)) {
      prev = JSON.parse(fs.readFileSync(p, "utf8")) as Partial<BridgeStatus>;
    }
  } catch {
    prev = {};
  }
  const me = String(patch.me ?? prev.me ?? "").trim();
  const next: BridgeStatus = {
    connection: (patch.connection || prev.connection || "connecting") as BridgeStatus["connection"],
    me,
    phone: String(patch.phone ?? prev.phone ?? phoneFromMe(me)).trim(),
    qr: String(patch.qr ?? prev.qr ?? ""),
    qr_data_url: String(patch.qr_data_url ?? prev.qr_data_url ?? ""),
    qr_png: String(patch.qr_png ?? prev.qr_png ?? ""),
    last_disconnect_reason: String(patch.last_disconnect_reason ?? prev.last_disconnect_reason ?? ""),
    last_disconnect_status:
      patch.last_disconnect_status === undefined
        ? (typeof prev.last_disconnect_status === "number" ? prev.last_disconnect_status : null)
        : patch.last_disconnect_status,
    last_error: String(patch.last_error ?? prev.last_error ?? ""),
    reconnect_attempt: Number(patch.reconnect_attempt ?? prev.reconnect_attempt ?? 0) || 0,
    login_only: Boolean(patch.login_only ?? prev.login_only ?? false),
    updated_at: new Date().toISOString(),
  };
  fs.writeFileSync(p, JSON.stringify(next, null, 2), "utf8");
  return next;
}
