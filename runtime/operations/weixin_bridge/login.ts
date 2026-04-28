import { spawn } from "node:child_process";
import path from "node:path";

function resolveLocalOpenclawBin(): string {
  // Prefer local openclaw installed in the sidecar runtime (no global CLI required).
  // Windows: node_modules/.bin/openclaw.cmd
  return path.join(process.cwd(), "node_modules", ".bin", process.platform === "win32" ? "openclaw.cmd" : "openclaw");
}

function run(): Promise<number> {
  return new Promise((resolve, reject) => {
    const openclawBin = resolveLocalOpenclawBin();
    const child = spawn(openclawBin, ["channels", "login", "--channel", "openclaw-weixin"], {
      stdio: "inherit",
      shell: true,
    });
    child.on("error", reject);
    child.on("exit", (code) => resolve(code ?? 1));
  });
}

void run().then((code) => {
  process.exitCode = code;
});
