import { Router } from "express";
import {
  AccountBalanceQuery,
  ScheduleCreateTransaction,
  Timestamp,
  TransferTransaction,
} from "@hiero-ledger/sdk";
import { asyncRoute, getClient, httpError } from "../hedera.js";
import { submitAuditMessage } from "./hcs.js";
import { loadState, requireSetup, updateState } from "../state.js";
import { scheduleUrl, txUrl } from "../hashscan.js";

const MAX_FUTURE_DAYS = 62; // HIP-423 cap on scheduled-tx expiration

export const settlementRouter = Router();

// POST /settlement/schedule — arm the on-chain settlement commitment
// (CONTRACTS §2). A scheduled tx's inner transfer amount is immutable at
// creation, so it cannot carry the real payoff max(0, S−K). We therefore
// schedule a 1-unit (0.000001 dUSDC) marker transfer treasury → customer —
// fully signed at create, setWaitForExpiry(true), max_payout_usd recorded in
// the schedule memo — as the visible on-chain commitment that fires at expiry.
// All real money moves exactly-once through /settlement/execute. Idempotent
// per token_id: one schedule per series.
settlementRouter.post(
  "/settlement/schedule",
  asyncRoute(async (req, res) => {
    const { token_id, expiry_ts, max_payout_usd } = req.body ?? {};
    if (!token_id || !expiry_ts || max_payout_usd == null) {
      throw httpError(422, "missing fields", "need token_id, expiry_ts, max_payout_usd");
    }
    const now = Date.now() / 1000;
    if (expiry_ts <= now) throw httpError(422, "expiry in the past", `expiry_ts=${expiry_ts}`);
    if (expiry_ts > now + MAX_FUTURE_DAYS * 86400) {
      throw httpError(422, "expiry too far out", `scheduled tx max ${MAX_FUTURE_DAYS} days (HIP-423)`);
    }
    const setup = requireSetup();

    const existing = loadState().schedules[token_id];
    if (existing) return res.json({ ...existing, replayed: true });

    const client = getClient();
    const marker = new TransferTransaction()
      .addTokenTransfer(setup.stablecoin_id, client.operatorAccountId, -1)
      .addTokenTransfer(setup.stablecoin_id, setup.customer_id, 1);

    // Operator signs as ScheduleCreate payer — that signature counts toward
    // the inner transfer, so the schedule is fully signed and cannot expire
    // under-signed (risk register).
    const tx = await new ScheduleCreateTransaction()
      .setScheduledTransaction(marker)
      .setScheduleMemo(`OptoPuts settle ${token_id} max $${max_payout_usd}`)
      .setExpirationTime(Timestamp.fromDate(new Date(expiry_ts * 1000)))
      .setWaitForExpiry(true)
      .execute(client);
    const receipt = await tx.getReceipt(client);

    const record = {
      schedule_id: receipt.scheduleId.toString(),
      status: "armed",
      hashscan_url: scheduleUrl(receipt.scheduleId.toString()),
      token_id,
      expiry_ts,
      max_payout_usd,
    };
    updateState((s) => {
      s.schedules[token_id] = record;
    });
    res.json(record);
  })
);

// POST /settlement/execute — the exactly-once boundary for payoff money
// (CONTRACTS §2 idempotency box). Write order: mark settling → transfer →
// record → respond. A crash between transfer and record is the accepted
// residual window (README limitations).
settlementRouter.post(
  "/settlement/execute",
  asyncRoute(async (req, res) => {
    const { token_id, payout_usd, spot_at_expiry } = req.body ?? {};
    if (!token_id || payout_usd == null || spot_at_expiry == null) {
      throw httpError(422, "missing fields", "need token_id, payout_usd, spot_at_expiry");
    }
    const setup = requireSetup();

    const settled = loadState().settlements[token_id];
    if (settled?.response) return res.json({ ...settled.response, replayed: true });

    const client = getClient();
    updateState((s) => {
      s.settlements[token_id] = { status: "settling", ts: Math.floor(Date.now() / 1000) };
    });

    const units = Math.round(payout_usd * 1e6);
    let transferTx = null;
    if (units > 0) {
      transferTx = await new TransferTransaction()
        .addTokenTransfer(setup.stablecoin_id, client.operatorAccountId, -units)
        .addTokenTransfer(setup.stablecoin_id, setup.customer_id, units)
        .execute(client);
      await transferTx.getReceipt(client);
    }

    const { tx: hcsTx } = await submitAuditMessage(client, setup.topic_id, "settlement", {
      token_id,
      payout_usd,
      spot_at_expiry,
      transfer_tx_id: transferTx ? transferTx.transactionId.toString() : null,
    });

    const txId = (transferTx ?? hcsTx).transactionId.toString();
    const response = { tx_id: txId, hashscan_url: txUrl(txId), paid_usd: payout_usd };
    updateState((s) => {
      s.settlements[token_id] = {
        status: "settled",
        ts: Math.floor(Date.now() / 1000),
        response,
      };
      if (s.schedules[token_id]) s.schedules[token_id].status = "paid";
    });
    res.json(response);
  })
);

// GET /treasury/balances — CONTRACTS §2; the backend risk gate reads this.
settlementRouter.get(
  "/treasury/balances",
  asyncRoute(async (_req, res) => {
    const client = getClient();
    const balance = await new AccountBalanceQuery()
      .setAccountId(client.operatorAccountId)
      .execute(client);

    const setup = loadState().setup;
    let stablecoinUsd = null;
    if (setup) {
      const units = balance.tokens?.get(setup.stablecoin_id);
      stablecoinUsd = units != null ? Number(units) / 1e6 : 0;
    }
    res.json({ hbar: Number(balance.hbars.toBigNumber()), stablecoin_usd: stablecoinUsd });
  })
);
