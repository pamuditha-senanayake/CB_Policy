import sys, re

with open('agent/harness.py', 'r') as f:
    content = f.read()

# I want to ensure `agent/harness.py` is in the desired state.
content = content.replace("with open('config/experiment.yaml', 'r') as f:\n    conf = yaml.safe_load(f)\n    config_seed = conf.get('data_seed', 0)\n    run_seeds = conf.get('run_seeds', [])", """with open('config/experiment.yaml', 'r') as f:
    conf = yaml.safe_load(f)
    config_seed = conf.get('data_seed', 0)
    run_seeds = conf.get('run_seeds', [])

with open('config/experiment.yaml', 'rb') as f:
    import hashlib
    config_hash = hashlib.sha256(f.read()).hexdigest()
""")

content = content.replace("""from dotenv import load_dotenv
load_dotenv()

import httpx2 as httpx
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
    http_client=httpx.Client(verify=False)
)""", """from dotenv import load_dotenv
load_dotenv()

from agent.providers import complete
provider = sys.argv[3] if len(sys.argv) > 3 else "deepseek"
MODEL = sys.argv[4] if len(sys.argv) > 4 else "deepseek-v4-flash"
""")

content = content.replace("MODEL = \"deepseek-chat\"", "")
content = content.replace("hash_str = f\"{MODEL}_{TEMP}_{run_seed}_{attempt_idx}_{prompt}\"", "hash_str = f\"{provider}_{MODEL}_{TEMP}_{run_seed}_{attempt_idx}_{prompt}\"")

# replace the try block in call_llm
old_try = """    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=TEMP,
            max_tokens=12,
            stop=["\\n"]
            # seed=run_seed - if supported, deepseek-chat might support it? I won't pass it if it causes errors, but openai API supports seed. Let's pass it.
        )
        ans = resp.choices[0].message.content.strip()
        usage = {
            "prompt_tokens": resp.usage.prompt_tokens,
            "completion_tokens": resp.usage.completion_tokens
        }
        res = {"answer": ans, "usage": usage}
        with open(cache_path, 'w') as f:
            json.dump(res, f)
        return res"""
new_try = """    try:
        raw_res = complete(provider, MODEL, prompt, TEMP, 12, seed=run_seed)
        ans = raw_res['text']
        usage = {
            "prompt_tokens": raw_res['prompt_tokens'],
            "completion_tokens": raw_res['completion_tokens']
        }
        res = {"answer": ans, "usage": usage}
        with open(cache_path, 'w') as f:
            json.dump(res, f)
        return res"""
content = content.replace(old_try, new_try)

# Update subprocess rescore.py
content = content.replace("str(config_seed), out_json]", "str(config_seed), out_json, provider, MODEL, config_hash]")
content = content.replace("str(config_seed), tmp_json]", "str(config_seed), tmp_json, provider, MODEL, config_hash]")

# Verify config hash in store if it exists
store_block = """    stores['bitemporal'] = BitemporalStore(f"runs/store_data{config_seed}.db")
    with open('data/manifest.json', 'r') as f:
        man_hash = hashlib.sha256(f.read().encode()).hexdigest()
    if stores['bitemporal'].get_meta('manifest_hash') != man_hash:
        print("ERROR: store_data DB manifest hash mismatch!")
        sys.exit(1)"""
store_new = """    stores['bitemporal'] = BitemporalStore(f"runs/store_data{config_seed}.db")
    with open('data/manifest.json', 'r') as f:
        man_hash = hashlib.sha256(f.read().encode()).hexdigest()
    if stores['bitemporal'].get_meta('manifest_hash') != man_hash:
        print("ERROR: store_data DB manifest hash mismatch!")
        sys.exit(1)
    # The requirement: "The harness must refuse to run if the config hash in the store metadata disagrees with the config on disk."
    db_config_hash = stores['bitemporal'].get_meta('config_hash')
    if db_config_hash and db_config_hash != config_hash:
        print("ERROR: store_data DB config hash mismatch!")
        sys.exit(1)"""
content = content.replace(store_block, store_new)

with open('agent/harness.py', 'w') as f:
    f.write(content)
