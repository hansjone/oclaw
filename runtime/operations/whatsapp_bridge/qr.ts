import qrcode from "qrcode-terminal";

export function printQrToTerminal(qr: string): void {
  // Keep it simple and dependency-light for Windows terminals.
  qrcode.generate(qr, { small: true });
}

