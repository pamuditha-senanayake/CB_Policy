import json, glob

conds = ['floor_static_v0', 'bitemporal_drift', 'oracle_expiry', 'latest_timestamp', 'plain_rag', 'full_history_brute']
prompt = 0
comp = 0
for cond in conds:
    for f in glob.glob(f"runs/raw/{cond}_rs11/*.json"):
        with open(f, 'r') as file:
            data = json.load(file)
            u = data.get('usage', {})
            prompt += u.get('prompt_tokens', 0)
            comp += u.get('completion_tokens', 0)
print(f"Prompt: {prompt}, Comp: {comp}")
print(f"DeepSeek Cost: ${(prompt/1_000_000)*0.14 + (comp/1_000_000)*0.28:.4f}")
