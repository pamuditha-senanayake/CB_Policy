import json, glob

prices = {
    'deepseek-v4-flash': (0.22, 0.66),
    'claude-sonnet-5': (2.00, 10.00),
    'gpt-5.6-luna': (0.20, 1.20)
}

usage = {}

for f in glob.glob(f"runs/raw/*/*.json"):
    with open(f, 'r') as file:
        data = json.load(file)
        m = data.get('model')
        if not m: continue
        if m not in usage: usage[m] = {'prompt': 0, 'comp': 0}
        u = data.get('usage', {})
        usage[m]['prompt'] += u.get('prompt_tokens', 0)
        usage[m]['comp'] += u.get('completion_tokens', 0)

for m, v in usage.items():
    if m in prices:
        cost = (v['prompt']/1000000) * prices[m][0] + (v['comp']/1000000) * prices[m][1]
        print(f"{m}: Prompt {v['prompt']}, Comp {v['comp']}, Cost: ${cost:.2f}")

