import { Router } from "express";
import {
  AccountId,
  TokenAssociateTransaction,
  TokenCreateTransaction,
  TokenType,
  TransferTransaction,
} from "@hiero-ledger/sdk";
import { asyncRoute, getClient, httpError, parsePrivateKey } from "../hedera.js";
import { loadState, requireSetup, updateState } from "../state.js";
import { tokenUrl, txUrl } from "../hashscan.js";

export const tokensRouter = Router();

// Token memo and HIP-646 metadata are each capped at 100 bytes → terse terms
// like {"t":"C","K":3600,"e":1753459200,"q":1,"s":"stg-abc123"}. Drop the
// strategy id first if the encoding would blow the cap.
export function terseTerms(option) {
  const terms = {
    t: option.type === "call" ? "C" : "P",
    K: option.strike,
    e: option.expiry_ts,
    q: option.qty,
    ...(option.strategy_id ? { s: option.strategy_id } : {}),
  };
  let json = JSON.stringify(terms);
  if (Buffer.byteLength(json) > 100 && terms.s) {
    delete terms.s;
    json = JSON.stringify(terms);
  }
  if (Buffer.byteLength(json) > 100) {
    throw httpError(422, "option terms exceed 100-byte memo cap", json);
  }
  return json;
}

// POST /tokens/mint-series — one fungible HTS token per option series
// (CONTRACTS §2). Idempotent per symbol: a retried mint can't create twins.
tokensRouter.post(
  "/tokens/mint-series",
  asyncRoute(async (req, res) => {
    const { symbol, name, option } = req.body ?? {};
    if (!symbol || !name || !option?.type || !option?.strike || !option?.expiry_ts) {
      throw httpError(422, "missing fields", "need symbol, name, option{type,strike,expiry_ts,qty}");
    }
    requireSetup();

    const existing = loadState().series[symbol];
    if (existing) return res.json({ ...existing, replayed: true });

    const client = getClient();
    const memo = terseTerms(option);
    const tx = new TokenCreateTransaction()
      .setTokenName(name)
      .setTokenSymbol(symbol)
      .setTokenType(TokenType.FungibleCommon)
      .setDecimals(0)
      .setInitialSupply(Math.max(1, Math.round(option.qty ?? 1)))
      .setTreasuryAccountId(client.operatorAccountId)
      .setTokenMemo(memo);
    if (typeof tx.setMetadata === "function") {
      tx.setMetadata(Buffer.from(memo)); // HIP-646 fungible metadata, same terse JSON
    }
    const submitted = await tx.execute(client);
    const receipt = await submitted.getReceipt(client);

    const record = {
      token_id: receipt.tokenId.toString(),
      tx_id: submitted.transactionId.toString(),
      hashscan_url: tokenUrl(receipt.tokenId.toString()),
      symbol,
      option,
    };
    updateState((s) => {
      s.series[symbol] = record;
    });
    res.json(record);
  })
);

// POST /tokens/transfer — treasury → customer, association-safe (CONTRACTS §2).
// The customer account has HIP-904 unlimited auto-association; if association
// still fails we associate explicitly with the stored customer key and retry.
tokensRouter.post(
  "/tokens/transfer",
  asyncRoute(async (req, res) => {
    const { token_id, to = "customer", qty = 1 } = req.body ?? {};
    if (!token_id) throw httpError(422, "missing fields", "need token_id");
    const setup = requireSetup();
    const client = getClient();

    const recipient =
      to === "customer" ? AccountId.fromString(setup.customer_id) : AccountId.fromString(to);

    const doTransfer = async () => {
      const tx = await new TransferTransaction()
        .addTokenTransfer(token_id, client.operatorAccountId, -qty)
        .addTokenTransfer(token_id, recipient, qty)
        .execute(client);
      await tx.getReceipt(client);
      return tx;
    };

    let tx;
    try {
      tx = await doTransfer();
    } catch (err) {
      if (!String(err.message).includes("TOKEN_NOT_ASSOCIATED_TO_ACCOUNT") || to !== "customer") {
        throw err;
      }
      if (!setup.customer_key) {
        // External customer (HEDERA_CUSTOMER_ID): we can't sign an associate
        // for an account whose key we don't hold — it must auto-associate.
        throw httpError(
          500,
          "customer not associated",
          `account ${setup.customer_id} rejected token ${token_id}; set maxAutomaticTokenAssociations=-1 on it (HIP-904)`
        );
      }
      const assoc = await (
        await new TokenAssociateTransaction()
          .setAccountId(recipient)
          .setTokenIds([token_id])
          .freezeWith(client)
          .sign(parsePrivateKey(setup.customer_key))
      ).execute(client);
      await assoc.getReceipt(client);
      tx = await doTransfer();
    }

    res.json({
      tx_id: tx.transactionId.toString(),
      hashscan_url: txUrl(tx.transactionId.toString()),
    });
  })
);
