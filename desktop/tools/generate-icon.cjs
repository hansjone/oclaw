const fs = require("node:fs");
const path = require("node:path");
const { Resvg } = require("@resvg/resvg-js");
const pngToIcoModule = require("png-to-ico");
const pngToIco = typeof pngToIcoModule === "function" ? pngToIcoModule : pngToIcoModule.default;

async function main() {
  const desktopRoot = path.resolve(__dirname, "..");
  const svgCandidates = [
    path.resolve(desktopRoot, "..", "_local", "branding", "logo.svg"),
    path.resolve(desktopRoot, "..", "interfaces", "admin", "static", "oliver.svg"),
  ];
  const svgPath = svgCandidates.find((p) => fs.existsSync(p)) || svgCandidates[svgCandidates.length - 1];
  const assetsDir = path.join(desktopRoot, "assets");
  const icoPath = path.join(assetsDir, "oclaw.ico");

  if (!fs.existsSync(svgPath)) {
    throw new Error(`logo not found: ${svgPath}`);
  }
  fs.mkdirSync(assetsDir, { recursive: true });
  const svg = fs.readFileSync(svgPath, "utf8");

  const sizes = [16, 24, 32, 48, 64, 128, 256];
  const pngBuffers = [];
  for (const size of sizes) {
    const resvg = new Resvg(svg, {
      fitTo: { mode: "width", value: size },
      background: "rgba(0,0,0,0)",
    });
    const pngData = resvg.render().asPng();
    pngBuffers.push(Buffer.from(pngData));
  }

  const ico = await pngToIco(pngBuffers);
  fs.writeFileSync(icoPath, ico);
  process.stdout.write(`Generated ${icoPath}\n`);
}

main().catch((err) => {
  process.stderr.write(`${String(err && err.message ? err.message : err)}\n`);
  process.exit(1);
});
