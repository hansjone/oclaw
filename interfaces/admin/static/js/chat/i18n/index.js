import messagesZh from "./messages-zh.js";
import messagesEn from "./messages-en.js";
import { state } from "../state.js";

export const I18N = { zh: messagesZh, en: messagesEn };
export const LANG_KEY = "ops_admin_lang";

export function t(key, vars) {
  let s = (I18N[state.currentLang] && I18N[state.currentLang][key]) || (I18N.en && I18N.en[key]) || key;
  if (vars && typeof s === "string") {
    for (const [k, v] of Object.entries(vars)) {
      s = s.replace(new RegExp(`\\{${k}\\}`, "g"), String(v));
    }
  }
  return s;
}

export function applyI18nStatic() {
  document.documentElement.lang = state.currentLang === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    const key = node.getAttribute("data-i18n");
    node.textContent = t(key);
  });
}
