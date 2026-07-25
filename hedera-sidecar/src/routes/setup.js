import { Router } from "express";
import {
  AccountCreateTransaction,
  Hbar,
  PrivateKey,
  TokenCreateTransaction,
  TokenType,
  TopicCreateTransaction,
} from "@hiero-ledger/sdk";
import { asyncRoute, getClient, operatorKey } from "../hedera.js";
import { loadState, updateState } from "../state.js";
import { accountUrl, tokenUrl, topicUrl } from "../hashscan.js";
import { config } from "../config.js";

const STABLECOIN_SUPPLY = 50_000n * 1_000_000n; // 50,000 dUSDC, 6 decimals

export const setupRouter = Router();

// POST /setup — one-time bootstrap (CONTRACTS §2): demo stablecoin + HCS topic
// + customer account. Idempotent as a whole: if state.json already has the IDs
// they are returned untouched.
setupRouter.post(
  "/setup",
  asyncRoute(async (_req, res) => {
    const existing = loadState().setup;
    if (existing) return res.json({ ...respond(existing), replayed: true });

    const client = getClient();
    const opKey = operatorKey();

    const tokenRx = await (
      await new TokenCreateTransaction()
        .setTokenName("Demo USDC")
        .setTokenSymbol("dUSDC")
        .setTokenType(TokenType.FungibleCommon)
        .setDecimals(6)
        .setInitialSupply(STABLECOIN_SUPPLY)
        .setTreasuryAccountId(client.operatorAccountId)
        .setSupplyKey(opKey.publicKey)
        .setTokenMemo("OptoPuts demo settlement stablecoin")
        .execute(client)
    ).getReceipt(client);

    const topicRx = await (
      await new TopicCreateTransaction()
        .setTopicMemo("OptoPuts audit log: quotes, trades, settlements")
        .execute(client)
    ).getReceipt(client);

    // Customer = the option buyer. Preferred: a real account from
    // HEDERA_CUSTOMER_ID (must have HIP-904 unlimited auto-association — its
    // key never touches the sidecar). Fallback: create a throwaway demo
    // account with unlimited auto-association.
    let customer_id;
    let customer_key = null;
    if (config.customerId) {
      customer_id = config.customerId;
    } else {
      const customerKey = PrivateKey.generateED25519();
      const accountTx = new AccountCreateTransaction()
        .setMaxAutomaticTokenAssociations(-1)
        // 3 HBAR covers the customer's own demo-lifetime tx fees; keeping
        // this low matters because every backend redeploy re-funds a fresh
        // customer account from the treasury (ephemeral container fs).
        .setInitialBalance(new Hbar(3));
      if (typeof accountTx.setKeyWithoutAlias === "function") {
        accountTx.setKeyWithoutAlias(customerKey.publicKey);
      } else {
        accountTx.setKey(customerKey.publicKey);
      }
      const accountRx = await (await accountTx.execute(client)).getReceipt(client);
      customer_id = accountRx.accountId.toString();
      customer_key = customerKey.toStringDer(); // demo-only: lets /tokens/transfer sign an explicit associate fallback
    }

    const setup = {
      stablecoin_id: tokenRx.tokenId.toString(),
      topic_id: topicRx.topicId.toString(),
      customer_id,
      customer_key,
      network: config.network,
      created_at: Math.floor(Date.now() / 1000),
    };
    updateState((s) => {
      s.setup = setup;
    });
    console.log(
      `setup complete: stablecoin=${setup.stablecoin_id} topic=${setup.topic_id} customer=${setup.customer_id}`
    );
    res.json(respond(setup));
  })
);

function respond(setup) {
  return {
    stablecoin_id: setup.stablecoin_id,
    topic_id: setup.topic_id,
    customer_id: setup.customer_id,
    hashscan: {
      stablecoin: tokenUrl(setup.stablecoin_id),
      topic: topicUrl(setup.topic_id),
      customer: accountUrl(setup.customer_id),
    },
  };
}
