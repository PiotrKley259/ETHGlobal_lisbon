import { AccountId, Client, PrivateKey } from "@hiero-ledger/sdk";
import { config, operatorConfigured } from "./config.js";

// Portal keys arrive as DER hex, raw hex ECDSA, or raw hex ED25519 — accept all.
export function parsePrivateKey(str) {
  const attempts = [
    PrivateKey.fromStringDer,
    PrivateKey.fromStringECDSA,
    PrivateKey.fromStringED25519,
  ];
  for (const parse of attempts) {
    try {
      return parse.call(PrivateKey, str.trim());
    } catch {
      /* try next encoding */
    }
  }
  throw httpError(500, "invalid private key", "not DER, ECDSA or ED25519 hex");
}

let client = null;
export function getClient() {
  if (!operatorConfigured()) {
    throw httpError(
      503,
      "operator not configured",
      "set HEDERA_OPERATOR_ID / HEDERA_OPERATOR_KEY in .env (CONTRACTS §5)"
    );
  }
  if (!client) {
    client = Client.forName(config.network).setOperator(
      AccountId.fromString(config.operatorId),
      parsePrivateKey(config.operatorKey)
    );
  }
  return client;
}

export function operatorKey() {
  return parsePrivateKey(config.operatorKey);
}

export function httpError(status, message, detail) {
  const err = new Error(message);
  err.status = status;
  err.detail = detail;
  return err;
}

// express 5 propagates rejected promises to the error middleware, but keep a
// wrapper so route files stay declarative.
export const asyncRoute = (fn) => (req, res, next) => fn(req, res, next).catch(next);
