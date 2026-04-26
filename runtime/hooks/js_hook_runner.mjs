/**
 * node js_hook_runner.mjs <absolute-handler> [exportName]
 * stdin: JSON { type, action, sessionKey, context, messages?, timestamp? }
 * stdout: JSON { "context"?: object }
 * Loads .mjs / .cjs (and ESM .js if passed) with dynamic import or createRequire.
 */
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { pathToFileURL } from "node:url";

const handlerPath = process.argv[2];
const exportName = (process.argv[3] || "default").trim();

if (!handlerPath) {
  console.error("oclaw: js_hook_runner: missing handler path");
  process.exit(2);
}

const abs = path.resolve(handlerPath);
const raw = readFileSync(0, "utf-8");
const data = JSON.parse(raw);
const event = {
  type: data.type,
  action: data.action,
  sessionKey: data.sessionKey,
  context: typeof data.context === "object" && data.context ? data.context : {},
  messages: Array.isArray(data.messages) ? data.messages : [],
  timestamp: data.timestamp,
};

const ext = path.extname(abs).toLowerCase();
let mod;
if (ext === ".cjs") {
  const require = createRequire(import.meta.url);
  mod = require(abs);
} else {
  mod = await import(pathToFileURL(abs).href);
}

const modRec = mod && typeof mod === "object" ? mod : {};
let fn;
if (exportName && exportName !== "default" && typeof modRec[exportName] === "function") {
  fn = modRec[exportName];
} else {
  fn = modRec.default ?? modRec.handle ?? modRec.handler;
}
if (typeof fn !== "function") {
  console.error("oclaw: js_hook_runner: no function export in", abs, "export", exportName);
  process.exit(3);
}
const r = fn(event);
if (r && typeof r.then === "function") {
  await r;
}
process.stdout.write(JSON.stringify({ context: event.context }));
