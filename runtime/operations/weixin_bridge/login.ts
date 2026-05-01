import path from "node:path";
import { pathToFileURL } from "node:url";

const STATE_DIR = (process.env.OCLAW_STATE_DIR || path.resolve(process.cwd(), "state")).trim();

function resolvePluginRoot(): string {
  const configured = String(process.env.OCLAW_WEIXIN_PLUGIN_ROOT || "").trim();
  return configured || path.join(process.cwd(), "node_modules", "@tencent-weixin", "openclaw-weixin");
}

async function importFromPluginSrc(relativePath: string): Promise<any> {
  const pluginRoot = resolvePluginRoot();
  const srcRoot = path.join(pluginRoot, "src");
  const fullPath = path.join(srcRoot, relativePath);
  return import(pathToFileURL(fullPath).href);
}

async function run(): Promise<void> {
  // Force the plugin's state-dir resolver away from ~/.openclaw
  process.env.OPENCLAW_STATE_DIR = STATE_DIR;

  const loginQr = await importFromPluginSrc(path.join("auth", "login-qr.ts"));
  const accounts = await importFromPluginSrc(path.join("auth", "accounts.ts"));

  const startWeixinLoginWithQr = loginQr.startWeixinLoginWithQr as ((opts: any) => Promise<any>) | undefined;
  const waitForWeixinLogin = loginQr.waitForWeixinLogin as ((opts: any) => Promise<any>) | undefined;
  const displayQRCode = loginQr.displayQRCode as ((qrcodeUrl: string) => Promise<void>) | undefined;
  const registerWeixinAccountId = accounts.registerWeixinAccountId as ((accountId: string) => void) | undefined;
  const saveWeixinAccount = accounts.saveWeixinAccount as ((accountId: string, update: any) => void) | undefined;

  if (!startWeixinLoginWithQr || !waitForWeixinLogin || !displayQRCode) {
    throw new Error("weixin plugin login-qr module missing exports");
  }
  if (!registerWeixinAccountId || !saveWeixinAccount) {
    throw new Error("weixin plugin accounts module missing exports");
  }

  const apiBaseUrl = "https://ilinkai.weixin.qq.com";
  const botType = process.env.OCLAW_WEIXIN_BOT_TYPE?.trim();

  const start = await startWeixinLoginWithQr({
    apiBaseUrl,
    botType,
  });
  if (!start.qrcodeUrl) {
    throw new Error(start.message || "failed to start login");
  }

  process.stdout.write(`${start.message}\n`);
  await displayQRCode(start.qrcodeUrl);

  const result = await waitForWeixinLogin({
    sessionKey: start.sessionKey,
    apiBaseUrl,
    botType,
  });

  process.stdout.write(`${result.message}\n`);
  if (!result.connected || !result.accountId || !result.botToken) {
    process.exitCode = 1;
    return;
  }

  registerWeixinAccountId(result.accountId);
  saveWeixinAccount(result.accountId, {
    token: result.botToken,
    baseUrl: result.baseUrl,
    userId: result.userId,
  });
  process.stdout.write(`saved account=${result.accountId} into ${STATE_DIR}\n`);
}

void run().catch((err) => {
  process.stderr.write(`weixin login failed: ${String(err)}\n`);
  process.exitCode = 1;
});
