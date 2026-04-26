/**
 * Invoked as: npx --yes tsx ts_hook_runner.ts <absolute-handler.ts> [exportName]
 * stdin: JSON { type, action, sessionKey, context, messages?, timestamp? }
 * stdout: JSON { "context"?: object } merged into the hook event in Python
 */
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const handlerPath = process.argv[2];
const exportName = (process.argv[3] || "default").trim();

if (!handlerPath) {
  console.error("oclaw: ts_hook_runner: missing handler path");
  process.exit(2);
}

const raw = readFileSync(0, "utf-8");
const data = JSON.parse(raw) as Record<string, unknown>;
const event = {
  type: data.type,
  action: data.action,
  sessionKey: data.sessionKey,
  context: (typeof data.context === "object" && data.context) ? (data.context as Record<string, unknown>) : {},
  messages: Array.isArray(data.messages) ? data.messages : [],
  timestamp: data.timestamp,
};

const mod: Record<string, unknown> = (await import(pathToFileURL(handlerPath).href)) as Record<string, unknown>;
let fn: ((ev: unknown) => unknown) | undefined;
if (exportName && exportName !== "default" && mod[exportName] && typeof mod[exportName] === "function") {
  fn = mod[exportName] as (ev: unknown) => unknown;
} else {
  fn = (mod.default ?? mod.handle ?? mod.handler) as (ev: unknown) => unknown;
}
if (typeof fn !== "function") {
  console.error("oclaw: ts_hook_runner: no function export in", handlerPath, "export", exportName);
  process.exit(3);
}
const r = fn(event);
if (r && typeof (r as { then?: unknown }).then === "function") {
  await (r as Promise<unknown>);
}
process.stdout.write(
  JSON.stringify({ context: event.context }, (_k, v) => (typeof v === "bigint" ? v.toString() : v), 0),
);
