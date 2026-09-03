import os
import time
from openai import OpenAI, AuthenticationError as OpenAIAuthError
import anthropic

class ProviderUnavailable(Exception):
    pass

def complete(provider, model, prompt, temperature, max_tokens, seed=None) -> dict:
    retries = 5
    for attempt in range(retries + 1):
        try:
            if provider == "deepseek":
                client = OpenAI(
                    api_key=os.environ.get("DEEPSEEK_API_KEY"),
                    base_url="https://api.deepseek.com"
                )
                kwargs = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stop": ["\n"]
                }
                resp = client.chat.completions.create(**kwargs)
                ans = resp.choices[0].message.content.strip()
                return {
                    "text": ans,
                    "prompt_tokens": resp.usage.prompt_tokens,
                    "completion_tokens": resp.usage.completion_tokens
                }

            elif provider == "openai":
                client = OpenAI(
                    api_key=os.environ.get("OPENAI_API_KEY")
                )
                kwargs = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}]
                }
                if model.startswith("gpt-5.6") or model.startswith("o"):
                    # Use max_completion_tokens
                    kwargs["max_completion_tokens"] = max_tokens
                    # O1 style doesn't support temperature or stop easily sometimes, but let's pass if possible
                else:
                    kwargs["max_tokens"] = max_tokens
                    kwargs["temperature"] = temperature
                    kwargs["stop"] = ["\n"]
                
                if seed is not None:
                    kwargs["seed"] = seed
                resp = client.chat.completions.create(**kwargs)
                ans = resp.choices[0].message.content.strip()
                return {
                    "text": ans,
                    "prompt_tokens": resp.usage.prompt_tokens,
                    "completion_tokens": resp.usage.completion_tokens
                }

            elif provider == "anthropic":
                client = anthropic.Anthropic(
                    api_key=os.environ.get("ANTHROPIC_API_KEY")
                )
                resp = client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[{"role": "user", "content": prompt}],
                    stop_sequences=["\n"]
                )
                ans = resp.content[0].text.strip()
                return {
                    "text": ans,
                    "prompt_tokens": resp.usage.input_tokens,
                    "completion_tokens": resp.usage.output_tokens
                }
            else:
                raise ValueError(f"Unknown provider: {provider}")

        except OpenAIAuthError as e:
            raise ProviderUnavailable(f"Provider {provider} auth failed: {str(e)}")
        except anthropic.AuthenticationError as e:
            raise ProviderUnavailable(f"Provider {provider} auth failed: {str(e)}")
        except Exception as e:
            if "Authentication" in str(e) or "401" in str(e) or "anthropic-workspace-id" in str(e):
                raise ProviderUnavailable(f"Provider {provider} auth failed: {str(e)}")
            if attempt == retries:
                raise ProviderUnavailable(f"Provider {provider} model {model} failed after {retries} retries: {str(e)}")
            time.sleep(2 ** attempt)
