import { config } from "./config.js";

const BASE = () => `https://hashscan.io/${config.network}`;

// SDK tx IDs are `0.0.X@ssss.nnnnnnnnn`; Hashscan URLs want `0.0.X-ssss-nnnnnnnnn`.
export function txUrl(txId) {
  const id = String(txId).replace("@", "-").replace(/\.(\d+)$/, "-$1");
  return `${BASE()}/transaction/${id}`;
}

export const tokenUrl = (id) => `${BASE()}/token/${id}`;
export const topicUrl = (id) => `${BASE()}/topic/${id}`;
export const scheduleUrl = (id) => `${BASE()}/schedule/${id}`;
export const accountUrl = (id) => `${BASE()}/account/${id}`;
