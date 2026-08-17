import fs from "node:fs";
import path from "node:path";
import qrcode from "qrcode-terminal";

export function printQrToTerminal(qr: string): void {
  // Keep it simple and dependency-light for Windows terminals.
  qrcode.generate(qr, { small: true });
}

export async function writeQrImage(stateDir: string, qr: string): Promise<{ pngPath: string; dataUrl: string }> {
  const pngPath = path.join(stateDir, "qr.png");
  try {
    // Optional dependency: installed by whatsapp_install.ps1 when available.
    const QRCode = await import("qrcode");
    await QRCode.toFile(pngPath, qr, { width: 320, margin: 1, errorCorrectionLevel: "M" });
    const dataUrl = await QRCode.toDataURL(qr, { width: 320, margin: 1, errorCorrectionLevel: "M" });
    return { pngPath, dataUrl: String(dataUrl || "") };
  } catch {
    try {
      if (fs.existsSync(pngPath)) fs.unlinkSync(pngPath);
    } catch {
      // ignore
    }
    return { pngPath: "", dataUrl: "" };
  }
}
