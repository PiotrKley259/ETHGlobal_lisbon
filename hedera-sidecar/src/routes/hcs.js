import { Router } from "express";
import { TopicMessageSubmitTransaction } from "@hiero-ledger/sdk";
import { asyncRoute, getClient, httpError } from "../hedera.js";
import { requireSetup } from "../state.js";
import { txUrl, topicUrl } from "../hashscan.js";

const KINDS = new Set(["quote", "trade", "settlement"]);

// Shared by /hcs/log and /settlement/execute (settlement record).
export async function submitAuditMessage(client, topicId, kind, payload) {
  const message = JSON.stringify({ kind, ts: Math.floor(Date.now() / 1000), payload });
  if (Buffer.byteLength(message) > 1024) {
    throw httpError(422, "payload too large", `${Buffer.byteLength(message)} bytes > 1024 (single HCS chunk)`);
  }
  const tx = await new TopicMessageSubmitTransaction()
    .setTopicId(topicId)
    .setMessage(message)
    .execute(client);
  const receipt = await tx.getReceipt(client);
  return { tx, sequence_number: Number(receipt.topicSequenceNumber) };
}

export const hcsRouter = Router();

// POST /hcs/log — append {kind, payload} to the audit topic (CONTRACTS §2).
// Deliberately NOT idempotent: it's an append-only log; a duplicate record of
// one event beats a dedupe bug that drops one. ≤1024 bytes = single chunk.
hcsRouter.post(
  "/hcs/log",
  asyncRoute(async (req, res) => {
    const { kind, payload } = req.body ?? {};
    if (!KINDS.has(kind)) {
      throw httpError(422, "invalid kind", `kind must be one of ${[...KINDS].join("|")}`);
    }
    const setup = requireSetup();
    const client = getClient();
    const { tx, sequence_number } = await submitAuditMessage(client, setup.topic_id, kind, payload);

    res.json({
      topic_id: setup.topic_id,
      sequence_number,
      tx_id: tx.transactionId.toString(),
      hashscan_url: topicUrl(setup.topic_id),
      tx_url: txUrl(tx.transactionId.toString()),
    });
  })
);
