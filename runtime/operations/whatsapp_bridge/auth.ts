import path from "node:path";
import { useMultiFileAuthState } from "@whiskeysockets/baileys";

export type AuthState = Awaited<ReturnType<typeof useMultiFileAuthState>>;

export function resolveAuthDir(stateDir: string): string {
  return path.join(stateDir, "auth");
}

export async function loadAuthState(stateDir: string): Promise<AuthState> {
  return await useMultiFileAuthState(resolveAuthDir(stateDir));
}

