const LANG_KEY = "ops_admin_lang";
let lang = "zh";
try {
  lang = String(localStorage.getItem(LANG_KEY) || "zh").toLowerCase();
} catch (_) {
  lang = "zh";
}
if (lang !== "zh" && lang !== "en") lang = "zh";

export const state = {
  currentLang: lang,
  authSession: null,
  /** @type {null | (() => any)} */
  reauthHandler: null,
  /** @type {null | (() => any)} */
  navigate: null,
};
