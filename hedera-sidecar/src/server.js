import express from "express";
import { AccountBalanceQuery } from "@hiero-ledger/sdk";
import { config, operatorConfigured } from "./config.js";
import { asyncRoute, getClient } from "./hedera.js";
import { setupRouter } from "./routes/setup.js";
import { tokensRouter } from "./routes/tokens.js";

const app = express();
app.use(express.json());

// GET /health — CONTRACTS §2. ok:false (still 200) while operator keys are
// missing or testnet is unreachable, so the backend can poll without treating
// "not configured" as a crash.
app.get(
  "/health",
  asyncRoute(async (_req, res) => {
    if (!operatorConfigured()) {
      return res.json({
        ok: false,
        network: config.network,
        operator: null,
        detail: "HEDERA_OPERATOR_ID / HEDERA_OPERATOR_KEY not set (see .env.example)",
      });
    }
    try {
      const client = getClient();
      await new AccountBalanceQuery()
        .setAccountId(client.operatorAccountId)
        .execute(client);
      res.json({ ok: true, network: config.network, operator: config.operatorId });
    } catch (err) {
      res.json({
        ok: false,
        network: config.network,
        operator: config.operatorId,
        detail: `testnet unreachable: ${err.message}`,
      });
    }
  })
);

app.use(setupRouter);
app.use(tokensRouter);

// Errors: non-2xx with {"error", "detail"} per CONTRACTS §2.
app.use((err, _req, res, _next) => {
  res.status(err.status || 500).json({
    error: err.message || "internal error",
    detail: err.detail || String(err.stack || err),
  });
});

app.listen(config.port, () => {
  console.log(`hedera-sidecar listening on :${config.port} (${config.network})`);
});

export default app;
