const LANG_KEY = "ops_admin_lang";
const CHAT_REASONING_TOGGLE_KEY = "ops_chat_reasoning_toggle";
const ADMIN_CHAT_SHOW_TOOL_OUTPUT_DEFAULT = true;

let lang = "zh";
try {
  lang = String(localStorage.getItem(LANG_KEY) || "zh").toLowerCase();
} catch (_) {}
if (lang !== "zh" && lang !== "en") lang = "zh";

let showTool = ADMIN_CHAT_SHOW_TOOL_OUTPUT_DEFAULT;
try {
  const _rt = String(localStorage.getItem(CHAT_REASONING_TOGGLE_KEY) || "").trim().toLowerCase();
  if (_rt) showTool = ["1", "true", "yes", "on"].includes(_rt);
} catch (_) {}

export const state = {
  currentLang: lang,
  authSession: null,
  adminChatShowToolOutput: showTool,
  meProfile: null,
  statusReasonPairs: [],
  jobsBadgeEl: null,
  jobsBtnLabelEl: null,
  /** @type {null | (() => Promise<any>)} set by main.js to avoid circular imports */
  boot: null,
};
