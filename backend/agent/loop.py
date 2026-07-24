"""Claude tool-use orchestration (PLAN task I1.1).

run_turn() is an async generator yielding CONTRACTS §3 event dicts
({"event": ..., "data": ...}); app.py serializes them to SSE. It mutates
the passed messages list in place so the caller owns conversation history.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

import anthropic

import config

from .tools import TOOLS, build_panel, chain_event, dispatch, summarize

MODEL = "claude-sonnet-5"
MAX_TOOL_ROUNDS = 8
MAX_TOKENS = 1500

SYSTEM_PROMPT = """\
You are the trader-facing agent of OptoPuts, a mini options desk for ETH.
The desk sells European cash-settled calls and puts (and multi-leg strategies)
on ETH, settled in a demo stablecoin on Hedera testnet.

HARD RULE - you compute nothing. Every number you state (spot, vol, price,
Greeks, breakevens, rates) MUST come from a tool result in this conversation.
Never estimate, extrapolate, or do arithmetic yourself; if you need a number,
call the tool. If a tool fails, say so plainly.

How to quote:
- Parse intent into strike K, expiry T_days, and call/put. "Protect my ETH
  below X" = put at K=X. "Just out of the money" = strike ~2-3% beyond spot
  (call get_spot first). Date phrases like "through Friday" -> days from now.
- For single options call price_option; for structures use resolve_strategy
  (or explicit legs) then price_strategy.
- Explain results in plain language for a non-expert: what they pay, what
  they get, where breakevens are, and WHY the price is what it is (which vol
  window priced it, what regime we're in). One short paragraph, not a lecture.

View-to-strategy mapping - watch direction carefully:
- "ETH stays flat and I want to PROFIT from the calm" -> SHORT straddle or
  short structures (collect premium, lose on a breakout).
- "ETH stays flat BUT protect me against big moves" -> LONG straddle or
  strangle (pay premium, profit on a breakout).
These are opposites. If the user's wording is ambiguous between profiting
from calm and protecting against a break, ask one short clarifying question
instead of keyword-matching.

Risk preferences: if the user redefines what counts as a stressed market,
call set_regime_bands and confirm the new thresholds.

Minting on Hedera: only after the user explicitly confirms a quoted trade.
The flow is mint_option (coverage is checked automatically and refusals are
final - relay the reason honestly) -> log_trade (kind=trade, compact payload
with symbol/strike/expiry/price) -> arm_settlement(token_id). For demos use
minutes-scale expiries (e.g. 3) so auto-settlement fires while the user
watches; at expiry the desk pays max(0, S-K) for calls / max(0, K-S) for
puts in demo stablecoin. For multi-leg strategies mint each leg with a
shared strategy_id. Be concise, concrete, and honest about limitations.
Never invent on-chain activity - only report what tool results contain."""

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


async def run_turn(messages: list[dict], state: dict) -> AsyncIterator[dict]:
    """Drive one user turn to completion, yielding token/tool_call/tool_result/
    panel events. `messages` must end with the new user message."""
    client = _get_client()

    for _round in range(MAX_TOOL_ROUNDS):
        async with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        ) as stream:
            async for event in stream:
                if (
                    event.type == "content_block_delta"
                    and event.delta.type == "text_delta"
                ):
                    yield {"event": "token", "data": {"delta": event.delta.text}}
            response = await stream.get_final_message()

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            return

        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            yield {"event": "tool_call", "data": {"name": block.name, "args": block.input}}
            try:
                result = dispatch(block.name, block.input, state)
                summary = summarize(block.name, result)
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })
                if (chain := chain_event(block.name, result)) is not None:
                    yield {"event": "chain", "data": chain}
            except Exception as exc:  # engine validation errors -> agent recovers
                summary = f"error: {exc}"
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(exc),
                    "is_error": True,
                })
            yield {"event": "tool_result", "data": {"name": block.name, "summary": summary}}

        messages.append({"role": "user", "content": results})
        # the demo beat: the panel refreshes the moment the numbers exist
        yield {"event": "panel", "data": build_panel(state)}

    yield {"event": "error", "data": {"message": "tool-round limit reached"}}
