import path from "node:path";
import { fileURLToPath } from "node:url";
import dotenv from "dotenv";

const here = path.dirname(fileURLToPath(import.meta.url));

// Local hedera-sidecar/.env wins; repo-root .env is the shared fallback
// (CONTRACTS §5 — same var names either way).
dotenv.config({ path: path.join(here, "..", ".env"), quiet: true });
dotenv.config({ path: path.join(here, "..", "..", ".env"), quiet: true });

export const config = {
  network: process.env.HEDERA_NETWORK || "testnet",
  operatorId: process.env.HEDERA_OPERATOR_ID || "",
  operatorKey: process.env.HEDERA_OPERATOR_KEY || "",
  // Optional: use an existing account as the option buyer instead of creating
  // a fresh one at /setup. The account must auto-associate tokens (HIP-904
  // maxAutomaticTokenAssociations = -1) — the sidecar never holds its key.
  customerId: process.env.HEDERA_CUSTOMER_ID || "",
  port: Number(process.env.SIDECAR_PORT || 7070),
  statePath: path.join(here, "..", "state.json"),
};

export function operatorConfigured() {
  return Boolean(config.operatorId && config.operatorKey);
}
