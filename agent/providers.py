"""Provider adapters with strict response extraction and per-model parameter negotiation.

Design notes (evidence-driven, see MULTIMODEL_RESULTS.md "Provider diagnostics"):

* Never return an empty string. An empty ``content`` is a failure, not a wrong
  answer, and is raised as :class:`EmptyResponse` so the caller can retry or
  record the task as unparseable.
* The empty responses observed in the aborted sweep were *token starvation*,
  not a missing extraction path: every empty record had ``completion_tokens``
  exactly equal to the ceiling (12 or 1000), i.e. the model spent its whole
  budget reasoning and never emitted an answer. So the primary remedy is to
  escalate ``max_tokens`` on a length-stop, not to scrape reasoning text.
* Model parameter support is discovered at runtime and cached, because the
  three providers disagree: ``claude-sonnet-5`` rejects ``temperature``,
  ``gpt-5.6-luna`` rejects ``temperature``/``stop``/``max_tokens``.
"""

import json
import os
import threading
import time

import anthropic
from openai import AuthenticationError as OpenAIAuthError
from openai import OpenAI


class ProviderUnavailable(Exception):
    """The provider cannot serve this request.

    `fatal` distinguishes a dead provider (auth, balance, unknown model) from a
    transient fault (connection reset, 5xx). Only a fatal fault should abandon
    the provider; a transient one must not throw away the whole sweep.
    """

    def __init__(self, msg, fatal=True):
        super().__init__(msg)
        self.fatal = fatal


class EmptyResponse(Exception):
    """The call succeeded but yielded no usable answer text."""


# Escalation ladder used when a model stops on `length` with empty content.
# 1024 is needed by claude-sonnet-5 on the full_history_brute long context:
# at 512 it still stops on `max_tokens` with no text for ~6% of calls, while
# at 1024 every previously-failing prompt returns an answer. Most calls never
# leave the first rung (median output is ~8 tokens).
_LADDER = [32, 128, 512, 1024]

_CAP_PATH = "runs/model_caps.json"
_cap_lock = threading.Lock()
_caps = None


def _load_caps():
    global _caps
    if _caps is None:
        try:
            with open(_CAP_PATH) as f:
                _caps = json.load(f)
        except Exception:
            _caps = {}
    return _caps


def _get_cap(key, default=None):
    with _cap_lock:
        return _load_caps().get(key, default)


def _set_cap(key, value):
    with _cap_lock:
        caps = _load_caps()
        caps[key] = value
        os.makedirs(os.path.dirname(_CAP_PATH), exist_ok=True)
        tmp = _CAP_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(caps, f, indent=2, sort_keys=True)
        os.replace(tmp, _CAP_PATH)


def _unsupported(err, *names):
    """True when the API rejected one of `names` as unsupported/deprecated."""
    s = str(err).lower()
    if not any(t in s for t in ("unsupported", "deprecated", "not supported", "does not support")):
        return False
    return any(n.lower() in s for n in names)


_clients = {}
_client_lock = threading.Lock()


def _build_client(provider):
    # max_retries=0: retry/backoff is handled in complete() so that an
    # exhausted output budget escalates instead of burning identical retries.
    if provider == "deepseek":
        return OpenAI(api_key=os.environ.get("DEEPSEEK_API_KEY"),
                      base_url="https://api.deepseek.com", max_retries=0)
    if provider == "openai":
        return OpenAI(api_key=os.environ.get("OPENAI_API_KEY"), max_retries=0)
    if provider == "anthropic":
        return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"),
                                   max_retries=0)
    raise ValueError(f"Unknown provider: {provider}")


def _client(provider):
    """One pooled client per provider.

    Building a client per call defeats HTTP connection pooling: with 30 worker
    threads that opens a new TCP+TLS connection every request and exhausts
    local sockets, which surfaces as spurious 'Connection error.' failures.
    """
    c = _clients.get(provider)
    if c is None:
        with _client_lock:
            c = _clients.get(provider)
            if c is None:
                c = _build_client(provider)
                _clients[provider] = c
    return c


def _is_output_limit_400(err):
    """OpenAI reports an exhausted output budget as a 400, not finish_reason.

    'Could not finish the message because max_tokens or model output limit was
    reached.' -- this is a truncation signal and must escalate the budget, not
    burn retries at the same ceiling.
    """
    s = str(err).lower()
    return ("max_tokens" in s or "output limit" in s) and "reached" in s


def _fatal(provider, err):
    """Classify errors that must not be retried."""
    s = str(err)
    if "Insufficient Balance" in s or "402" in s:
        return ProviderUnavailable(f"{provider}: insufficient balance -- {s}")
    if "Authentication" in s or "401" in s or "anthropic-workspace-id" in s:
        return ProviderUnavailable(f"{provider}: auth failed -- {s}")
    if "does not exist" in s or "404" in s or "model_not_found" in s:
        return ProviderUnavailable(f"{provider}: unknown model -- {s}")
    return None


def _chat_once(provider, model, prompt, temperature, max_tokens, seed):
    """One OpenAI-shaped call, negotiating parameter support and caching it."""
    client = _client(provider)
    ckey = f"{provider}/{model}"
    caps = _get_cap(ckey) or {}

    while True:
        kwargs = {"model": model, "messages": [{"role": "user", "content": prompt}]}
        tok_param = caps.get("token_param", "max_tokens")
        kwargs[tok_param] = max_tokens
        if caps.get("temperature", True) and temperature is not None:
            kwargs["temperature"] = temperature
        if caps.get("seed", True) and seed is not None:
            kwargs["seed"] = seed
        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception as e:
            fatal = _fatal(provider, e)
            if fatal:
                raise fatal
            changed = False
            if _unsupported(e, "max_tokens") and tok_param == "max_tokens":
                caps["token_param"] = "max_completion_tokens"; changed = True
            elif _unsupported(e, "temperature") and caps.get("temperature", True):
                caps["temperature"] = False; changed = True
            elif _unsupported(e, "seed") and caps.get("seed", True):
                caps["seed"] = False; changed = True
            if not changed:
                raise
            _set_cap(ckey, caps)
            continue
        if caps != (_get_cap(ckey) or {}):
            _set_cap(ckey, caps)
        elif not _get_cap(ckey):
            _set_cap(ckey, caps)

        msg = resp.choices[0].message
        finish = resp.choices[0].finish_reason
        text = (getattr(msg, "content", None) or "").strip()
        return {
            "text": text,
            "finish_reason": finish,
            "reasoning": (getattr(msg, "reasoning_content", None) or "").strip(),
            "prompt_tokens": resp.usage.prompt_tokens,
            "completion_tokens": resp.usage.completion_tokens,
        }


def _anthropic_once(provider, model, prompt, temperature, max_tokens):
    client = _client(provider)
    ckey = f"{provider}/{model}"
    caps = _get_cap(ckey) or {}

    while True:
        kwargs = {"model": model, "max_tokens": max_tokens,
                  "messages": [{"role": "user", "content": prompt}]}
        if caps.get("temperature", True) and temperature is not None:
            kwargs["temperature"] = temperature
        try:
            resp = client.messages.create(**kwargs)
        except Exception as e:
            fatal = _fatal(provider, e)
            if fatal:
                raise fatal
            if _unsupported(e, "temperature") and caps.get("temperature", True):
                caps["temperature"] = False
                _set_cap(ckey, caps)
                continue
            raise
        if not _get_cap(ckey) or caps != _get_cap(ckey):
            _set_cap(ckey, caps)

        # Never index content[0]: a thinking block can occupy position zero.
        parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
        return {
            "text": " ".join(parts).strip(),
            "finish_reason": resp.stop_reason,
            "reasoning": "",
            "prompt_tokens": resp.usage.input_tokens,
            "completion_tokens": resp.usage.output_tokens,
        }


def complete(provider, model, prompt, temperature, max_tokens, seed=None,
             allow_reasoning_salvage=True) -> dict:
    """Return {'text', 'prompt_tokens', 'completion_tokens', ...} or raise.

    Raises ProviderUnavailable for unrecoverable provider faults and
    EmptyResponse when no answer text could be obtained after escalation.
    """
    ladder = [t for t in _LADDER if t >= max_tokens] or [max_tokens]
    transport_retries = 6
    total_prompt = total_completion = 0
    last_reasoning = ""
    last_text = ""
    escalated_to = None

    for budget in ladder:
        for attempt in range(transport_retries + 1):
            try:
                if provider == "anthropic":
                    r = _anthropic_once(provider, model, prompt, temperature, budget)
                elif provider in ("deepseek", "openai"):
                    r = _chat_once(provider, model, prompt, temperature, budget, seed)
                else:
                    raise ValueError(f"Unknown provider: {provider}")
            except ProviderUnavailable:
                raise
            except OpenAIAuthError as e:
                raise ProviderUnavailable(f"{provider}: auth failed -- {e}")
            except anthropic.AuthenticationError as e:
                raise ProviderUnavailable(f"{provider}: auth failed -- {e}")
            except Exception as e:
                # Re-classify: a fatal fault must stay fatal even if it reaches
                # this generic handler rather than the per-call one.
                fatal = _fatal(provider, e)
                if fatal:
                    raise fatal
                if _is_output_limit_400(e):
                    # Treat exactly like a truncated response: escalate budget.
                    escalated_to = budget
                    break
                if attempt == transport_retries:
                    raise ProviderUnavailable(
                        f"{provider}/{model} failed after {transport_retries} "
                        f"retries: {e}", fatal=False)
                time.sleep(2 ** attempt)
                continue

            total_prompt += r["prompt_tokens"]
            total_completion += r["completion_tokens"]
            if r["reasoning"]:
                last_reasoning = r["reasoning"]

            # A `length` stop means the answer was cut mid-word ('up',
            # 'approve_ex'). That is not a wrong answer, it is an under-budgeted
            # one, so escalate rather than scoring the fragment.
            truncated = r["finish_reason"] in ("length", "max_tokens")
            if r["text"] and not (truncated and budget != ladder[-1]):
                return {
                    "text": r["text"],
                    "prompt_tokens": total_prompt,
                    "completion_tokens": total_completion,
                    "max_tokens_used": budget,
                    "escalated": budget != ladder[0],
                    "salvaged_from_reasoning": False,
                }
            # Empty, or truncated with budget left: escalate instead of retrying.
            escalated_to = budget
            if r["text"]:
                last_text = r["text"]
            break

    if last_text:
        return {
            "text": last_text,
            "prompt_tokens": total_prompt,
            "completion_tokens": total_completion,
            "max_tokens_used": escalated_to,
            "escalated": True,
            "salvaged_from_reasoning": False,
            "truncated": True,
        }

    if allow_reasoning_salvage and last_reasoning:
        return {
            "text": last_reasoning,
            "prompt_tokens": total_prompt,
            "completion_tokens": total_completion,
            "max_tokens_used": escalated_to,
            "escalated": True,
            "salvaged_from_reasoning": True,
        }

    raise EmptyResponse(
        f"{provider}/{model}: no text in content"
        f"{' or reasoning_content' if provider == 'deepseek' else ''} "
        f"after escalating max_tokens to {escalated_to}")
