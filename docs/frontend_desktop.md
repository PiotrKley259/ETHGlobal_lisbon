# OptoPuts frontend desktop baseline and responsiveness target

This document is the **desktop reference spec** for the frontend workstream.
It is intentionally tied to the current `deploy/live` behavior as a baseline,
then defines what to improve without regressing mobile.

---

## 1. Scope

- Frontend only (`frontend/src/`)
- No backend/API contract changes
- Keep SSE chat flow, panel updates, chain events, and `?key` behavior intact
- Keep current visual direction; improve desktop information architecture and layout stability

---

## 2. Baseline source of truth

Baseline is the UI behavior currently represented on `deploy/live` and described in the desktop snapshot text shared in session (three-region desk: chat left, pricing panel right-top, chain right-bottom).

Core baseline characteristics:

- Full viewport app shell (`height: 100vh`)
- Three-region desktop distribution:
  - chat as primary left column
  - pricing panel in right-top
  - chain activity in right-bottom
- Dense trading-terminal information model:
  - streaming chat with tool chips
  - pricing panel with spot/vol/regime/rate/quote/strategy
  - Greeks + hover definitions
  - payoff graph
  - chain log with status transitions

---

## 3. Responsiveness strategy

### Mobile (`<768px`)

- Preserve current mobile-first redesign behavior and aesthetics
- Chat first in flow
- No horizontal scrolling
- Tap targets at least 44px

### Tablet (`768px–1023px`)

- Transitional layout: chat remains dominant
- Right-side sections may stack, but remain readable and complete
- Avoid large dead space and over-compression

### Desktop (`>=1024px`)

- Restore/maintain the original information-dense distribution:
  - left column should clearly dominate as chat workspace
  - right rail should stably show panel + chain without missing critical blocks
- Ensure no critical content disappears/collapses under typical desktop widths

---

## 4. Required desktop outcomes

1. Original logo/wordmark is visibly present in desk/chat view.
2. Payoff graph is visible when quote/strategy payload includes payoff data.
3. Greeks row is visible with hoverable plain-language definitions.
4. Right rail blocks remain structurally stable (no broken collapse of key sections).
5. Chat has clear primary prominence vs right rail at desktop widths.

---

## 5. Explicit copy decisions

- Keep short hero sentence:
  - `Price and mint on-chain options from live market data in seconds.`
- Remove landing line:
  - `ETHGlobal Lisbon build · Hedera testnet — the money is fake, the receipts are real. Public demos may need an invite link (?key=…).`

---

## 6. Acceptance checklist

Validate manually at these widths: **390, 768, 1024, 1280, 1440**.

At each width:

1. No horizontal page scroll.
2. Chat input and send button remain usable.
3. Streaming messages/chips render correctly.
4. Pricing panel content remains legible.
5. Chain log remains readable and scrollable.

Desktop-only checks (`>=1024`):

1. Chat is visually primary.
2. Greeks + tooltips work.
3. Payoff chart renders when data exists.
4. No critical section appears missing due to layout constraints.

---

## 7. Change control

- This file is a design/implementation guardrail for desktop rebalance work.
- If desktop target layout strategy changes materially, update this document in the same PR.
