#!/usr/bin/env python3
"""A8 part two, agent side: adversarial tasks inside the mined-to-true band.

The benchmark generator almost never samples the band between the mined
threshold and the true one, so the measured cost of a mis-mined constraint is
zero by construction. This generates tasks whose parameter lands squarely in
that band and measures how often the agent, reading the mined rule, answers
against the current true policy.

Capped at DeepSeek, seed 11, one policy (shipping_upgrade).
"""
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../data"))

from dotenv import load_dotenv
load_dotenv()

from agent import spend                       # noqa: E402
from agent.providers import complete          # noqa: E402
from template import render_constraint        # noqa: E402

PROVIDER, MODEL, SEED = "deepseek", "deepseek-chat", 11
POLICY = "shipping_upgrade"
K = 4


def main():
    a8 = json.load(open("runs/a8_result.json"))
    row = next(r for r in a8["rows"] if r["seed"] == SEED and r["policy"] == POLICY)
    mined_c, true_c = row["enumerate"], row["true"]
    band = row["enumerate_band"]["band"]
    v0 = json.load(open(f"data/policies/{POLICY}_v0.json"))
    at, af = v0["action_true"], v0["action_false"]

    # Every integer in the band, plus a margin of controls on either side so
    # the in-band error rate can be read against out-of-band behaviour.
    MARGIN = 4
    in_band = set(range(band[0], band[1] + 1))
    values = sorted(in_band | set(range(band[0] - MARGIN, band[0])) |
                    set(range(band[1] + 1, band[1] + 1 + MARGIN)))
    mined_prose = render_constraint(mined_c, at, af)
    ctx = mined_prose + "\n\nSource: practice-mined, document pending"

    results = []
    for val in values:
        env = {mined_c.split(" ")[0]: val}
        truth = at if eval(true_c, {"__builtins__": {}}, dict(env)) else af
        mined_says = at if eval(mined_c, {"__builtins__": {}}, dict(env)) else af
        prompt = (f"Given the following policy document or context:\n{ctx}\n\n"
                  f"User request: My cart is ${val}. Do I get free upgraded shipping?\n\n"
                  f"What action should be taken? Reply with exactly one word: "
                  f"{at} or {af}\nAction:")
        for k in range(K):
            r = complete(PROVIDER, MODEL, prompt, 0.6, 32, seed=SEED)
            spend.record(PROVIDER, MODEL, r["prompt_tokens"], r["completion_tokens"])
            ans = r["text"].strip().lower()
            results.append({
                "cart_total": val, "in_band": val in in_band,
                "attempt": k, "response": r["text"],
                "true_action": truth, "mined_action": mined_says,
                "agent_matches_true": truth.lower() in ans,
                "agent_matches_mined": mined_says.lower() in ans,
            })

    n = len(results)
    wrong = sum(1 for r in results if not r["agent_matches_true"])
    follows_mined = sum(1 for r in results if r["agent_matches_mined"])
    ib = [r for r in results if r["in_band"]]
    ob = [r for r in results if not r["in_band"]]
    ib_wrong = sum(1 for r in ib if not r["agent_matches_true"])
    ob_wrong = sum(1 for r in ob if not r["agent_matches_true"])
    out = {"provider": PROVIDER, "model": MODEL, "seed": SEED, "policy": POLICY,
           "mined_constraint": mined_c, "true_constraint": true_c, "band": band,
           "n_calls": n, "n_values": len(values), "k_attempts": K,
           "agent_wrong_vs_true": wrong, "agent_wrong_rate": wrong / n if n else 0,
           "agent_follows_mined": follows_mined,
           "agent_follows_mined_rate": follows_mined / n if n else 0,
           "in_band": {"n": len(ib), "wrong": ib_wrong,
                       "rate": ib_wrong / len(ib) if ib else None},
           "out_of_band": {"n": len(ob), "wrong": ob_wrong,
                           "rate": ob_wrong / len(ob) if ob else None},
           "results": results}
    json.dump(out, open("runs/a8_agent_band.json", "w"), indent=2)
    print(f"band {band}  values {values}  calls {n}")
    print(f"agent wrong vs true policy: {wrong}/{n} ({wrong/n:.2f})")
    print(f"agent follows mined rule  : {follows_mined}/{n} ({follows_mined/n:.2f})")
    print(f"  in band     : {ib_wrong}/{len(ib)} wrong")
    print(f"  out of band : {ob_wrong}/{len(ob)} wrong")
    print(spend.summary())


if __name__ == "__main__":
    main()
