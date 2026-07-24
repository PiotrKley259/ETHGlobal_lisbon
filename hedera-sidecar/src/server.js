import express from "express";
import { config, operatorConfigured } from "./config.js";

const app = express();
app.use(express.json());

// GET /health — CONTRACTS §2. ok:false (still 200) while operator keys are
// missing so the backend can poll without treating "not configured" as a crash.
app.get("/health", (_req, res) => {
  if (!operatorConfigured()) {
    return res.json({
      ok: false,
      network: config.network,
      operator: null,
      detail: "HEDERA_OPERATOR_ID / HEDERA_OPERATOR_KEY not set (see .env.example)",
    });
  }
  res.json({ ok: true, network: config.network, operator: config.operatorId });
});

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
