import { spawn } from "node:child_process";

function run(): Promise<number> {
  return new Promise((resolve, reject) => {
    const child = spawn("openclaw", ["channels", "login", "--channel", "openclaw-weixin"], {
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
