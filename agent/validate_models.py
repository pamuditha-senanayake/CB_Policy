#!/usr/bin/env python3
"""Pre-flight validation: prove every model returns parseable answers before spending.

Issues N real task prompts (default 20) per configured model and reports empty
rate, unparseable rate, mean output tokens and the parameters the model
accepted. A model PASSES only with 0% empty and <2% unparseable.

Results are written to runs/model_validation.json; agent/harness.py refuses to
start for any model whose PASS is missing or older than --max-age seconds
(default 3600).

Usage:
    python3 agent/validate_models.py                      # validate config models
    python3 agent/validate_models.py --models deepseek/deepseek-v4-flash anthropic/claude-sonnet-5
"""

import argparse
import json
import os
import re
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from agent import spend  # noqa: E402
from agent.providers import EmptyResponse, ProviderUnavailable, complete  # noqa: E402

VALIDATION_PATH = "runs/model_validation.json"
DEFAULT_MAX_AGE = 3600
PASS_EMPTY_MAX = 0.0
PASS_UNPARSE_MAX = 0.02


def normalize_action(s):
    s = str(s or "").strip().lower()
    s = re.sub(r"[\'\"`\[\]:\.]", "", s)
    return s.strip()


def build_prompts(n):
    """Real prompts, built exactly as agent/harness.py builds them."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "cond", "agent/conditions/floor_static_v0.py")
    cond = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cond)

    tasks = json.load(open("data/tasks/tasks.json"))
    policy_actions = {}
    for t in tasks:
        p = t["policy_id"]
        if p in policy_actions:
            continue
        try:
            v0 = json.load(open(f"data/policies/{p}_v0.json"))
            policy_actions[p] = [v0["action_true"], v0["action_false"]]
        except Exception:
            pass

    out = []
    # Spread across policies rather than taking the first n contiguous tasks.
    step = max(1, len(tasks) // n)
    for t in tasks[::step][:n]:
        actions = policy_actions.get(t["policy_id"], ["approve_refund", "deny_refund"])
        ctx = cond.build_context(t, {})
        prompt = (f"Given the following policy document or context:\n{ctx}\n\n"
                  f"User request: {t['user_msg']}\n\n"
                  f"What action should be taken? Reply with exactly one word: "
                  f"{actions[0]} or {actions[1]}\nAction:")
        out.append((prompt, [normalize_action(a) for a in actions]))
    return out


def validate_model(provider, model, prompts, max_tokens, temperature, seed):
    empty = unparse = 0
    out_tokens = []
    samples = []
    salvaged = 0
    escalated = 0
    error = None

    for prompt, valid in prompts:
        try:
            r = complete(provider, model, prompt, temperature, max_tokens, seed=seed)
        except ProviderUnavailable as e:
            error = str(e)[:160]
            break
        except EmptyResponse:
            empty += 1
            continue
        text = r["text"]
        spend.record(provider, model, r["prompt_tokens"], r["completion_tokens"])
        out_tokens.append(r["completion_tokens"])
        salvaged += bool(r.get("salvaged_from_reasoning"))
        escalated += bool(r.get("escalated"))
        if not text.strip():
            empty += 1
            continue
        norm = normalize_action(text)
        if not any(v == norm or v in norm for v in valid):
            unparse += 1
        if len(samples) < 3:
            samples.append(text[:120])

    n = len(prompts)
    done = len(out_tokens) + empty
    caps = {}
    try:
        caps = json.load(open("runs/model_caps.json")).get(f"{provider}/{model}", {})
    except Exception:
        pass
    accepts = "max_completion_tokens" if caps.get("token_param") == "max_completion_tokens" else "max_tokens"
    if caps.get("temperature") is False:
        accepts += ", no-temp"

    empty_rate = empty / done if done else 1.0
    unparse_rate = unparse / done if done else 1.0
    verdict = "FAIL"
    if error:
        verdict = "UNAVAILABLE"
    elif done == n and empty_rate <= PASS_EMPTY_MAX and unparse_rate < PASS_UNPARSE_MAX:
        verdict = "PASS"

    return {
        "provider": provider, "model": model, "n": n, "completed": done,
        "empty_n": empty, "empty_rate": empty_rate,
        "unparseable_n": unparse, "unparseable_rate": unparse_rate,
        "mean_out_tokens": sum(out_tokens) / len(out_tokens) if out_tokens else 0.0,
        "salvaged_n": salvaged, "escalated_n": escalated,
        "accepts": accepts, "max_tokens": max_tokens,
        "verdict": verdict, "error": error,
        "samples": samples, "ts": time.time(),
    }


def load_validation():
    try:
        return json.load(open(VALIDATION_PATH))
    except Exception:
        return {}


def is_validated(provider, model, max_age=DEFAULT_MAX_AGE):
    """Used by agent/harness.py to refuse unvalidated models."""
    rec = load_validation().get(f"{provider}/{model}")
    if not rec or rec.get("verdict") != "PASS":
        return False, f"{provider}/{model} has no PASS validation record"
    age = time.time() - rec.get("ts", 0)
    if age > max_age:
        return False, (f"{provider}/{model} validation is {age/60:.0f} min old "
                       f"(max {max_age/60:.0f} min) -- re-run agent/validate_models.py")
    return True, f"validated {age/60:.0f} min ago"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=None,
                    help="provider/model pairs; default reads config/experiment.yaml")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--max-tokens", type=int, default=32)
    ap.add_argument("--temperature", type=float, default=0.6)
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args()

    if args.models:
        pairs = [tuple(m.split("/", 1)) for m in args.models]
    else:
        import yaml
        conf = yaml.safe_load(open("config/experiment.yaml"))
        pairs = [(m["provider"], m["model"]) for m in conf.get("models", [])]

    prompts = build_prompts(args.n)
    print(f"Validating {len(pairs)} model(s) with {len(prompts)} real task prompts "
          f"at max_tokens={args.max_tokens}\n")

    results = load_validation()
    rows = []
    for provider, model in pairs:
        r = validate_model(provider, model, prompts, args.max_tokens,
                           args.temperature, args.seed)
        results[f"{provider}/{model}"] = r
        rows.append(r)

    os.makedirs("runs", exist_ok=True)
    with open(VALIDATION_PATH, "w") as f:
        json.dump(results, f, indent=2, sort_keys=True)

    hdr = (f"{'provider':10} {'model':22} {'empty%':>7} {'unparse%':>9} "
           f"{'mean_out':>9}  {'accepts':22} verdict")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r['provider']:10} {r['model']:22} {r['empty_rate']*100:6.1f}% "
              f"{r['unparseable_rate']*100:8.1f}% {r['mean_out_tokens']:9.2f}  "
              f"{r['accepts']:22} {r['verdict']}")
    print()
    for r in rows:
        print(f"--- {r['provider']}/{r['model']} samples")
        if r["error"]:
            print(f"    ERROR: {r['error']}")
        for s in r["samples"] or ["(none)"]:
            print(f"    {s!r}")
        if r["salvaged_n"] or r["escalated_n"]:
            print(f"    escalated={r['escalated_n']} salvaged_from_reasoning={r['salvaged_n']}")
    print(f"\nWrote {VALIDATION_PATH}")
    print(f"Spend ledger:\n{spend.summary()}")
    return 0 if all(r["verdict"] == "PASS" for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
