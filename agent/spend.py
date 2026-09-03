"""Cumulative per-provider spend tracking with hard budget caps.

Written to runs/spend.json after every call so an aborted run still leaves an
accurate ledger. Prices are USD per 1M tokens.
"""

import json
import os
import threading

SPEND_PATH = "runs/spend.json"

PRICES = {
    ("anthropic", "claude-sonnet-5"): (2.0, 10.0),
    ("openai", "gpt-5.6-luna"): (1.25, 10.0),
    ("deepseek", "deepseek-v4-flash"): (0.28, 0.42),
    ("deepseek", "deepseek-chat"): (0.28, 0.42),
}
DEFAULT_PRICE = (1.0, 5.0)

# Hard abort thresholds, USD.
# User balance $15.98; full 6-condition x 3-seed sweep estimates ~$11.10
# from measured per-call tokens. Cap leaves ~$2 of headroom.
CAPS = {"anthropic": 14.00}


class BudgetExceeded(Exception):
    pass


_lock = threading.Lock()


def price_for(provider, model):
    return PRICES.get((provider, model), DEFAULT_PRICE)


def _load():
    try:
        with open(SPEND_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def cost_of(provider, model, prompt_tokens, completion_tokens):
    pin, pout = price_for(provider, model)
    return prompt_tokens / 1e6 * pin + completion_tokens / 1e6 * pout


def record(provider, model, prompt_tokens, completion_tokens):
    """Add usage to the ledger and return cumulative provider spend."""
    with _lock:
        data = _load()
        key = provider
        entry = data.setdefault(key, {"usd": 0.0, "prompt_tokens": 0,
                                      "completion_tokens": 0, "calls": 0,
                                      "by_model": {}})
        c = cost_of(provider, model, prompt_tokens, completion_tokens)
        entry["usd"] += c
        entry["prompt_tokens"] += prompt_tokens
        entry["completion_tokens"] += completion_tokens
        entry["calls"] += 1
        m = entry["by_model"].setdefault(model, {"usd": 0.0, "calls": 0})
        m["usd"] += c
        m["calls"] += 1
        os.makedirs("runs", exist_ok=True)
        tmp = SPEND_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        os.replace(tmp, SPEND_PATH)
        return entry["usd"]


def total(provider):
    return _load().get(provider, {}).get("usd", 0.0)


def check_cap(provider, headroom=0.0):
    """Raise BudgetExceeded if the provider is at or over its cap."""
    cap = CAPS.get(provider)
    if cap is None:
        return
    spent = total(provider)
    if spent + headroom >= cap:
        raise BudgetExceeded(
            f"{provider} spend ${spent:.2f} + est ${headroom:.2f} reaches cap ${cap:.2f}")


def summary():
    data = _load()
    lines = []
    for prov, e in sorted(data.items()):
        cap = CAPS.get(prov)
        capstr = f" / cap ${cap:.2f}" if cap else ""
        lines.append(f"  {prov:10} ${e['usd']:7.4f}{capstr}  "
                     f"({e['calls']} calls, {e['prompt_tokens']} in, "
                     f"{e['completion_tokens']} out)")
    return "\n".join(lines) or "  (no spend recorded)"
