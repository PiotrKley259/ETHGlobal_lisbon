import fs from "node:fs";
import { config } from "./config.js";
import { httpError } from "./hedera.js";

// state.json (gitignored) is the sidecar's memory: chain IDs from /setup plus
// the idempotency ledgers keyed by symbol/token_id (CONTRACTS §2). A testnet
// reset is handled by deleting the file and re-running /setup.
const EMPTY = { setup: null, series: {}, schedules: {}, settlements: {} };

export function loadState() {
  try {
    return { ...EMPTY, ...JSON.parse(fs.readFileSync(config.statePath, "utf8")) };
  } catch {
    return structuredClone(EMPTY);
  }
}

export function saveState(state) {
  const tmp = config.statePath + ".tmp";
  fs.writeFileSync(tmp, JSON.stringify(state, null, 2));
  fs.renameSync(tmp, config.statePath);
}

export function updateState(mutate) {
  const state = loadState();
  mutate(state);
  saveState(state);
  return state;
}

export function requireSetup() {
  const setup = loadState().setup;
  if (!setup) throw httpError(409, "setup not run", "POST /setup first");
  return setup;
}
