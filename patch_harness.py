import sys, re

with open('agent/harness.py', 'r') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if "from dotenv import load_dotenv" in line:
        # We will insert new argument parsing and config hash logic here
        new_lines.append("provider = sys.argv[3] if len(sys.argv) > 3 else 'deepseek'\n")
        new_lines.append("MODEL = sys.argv[4] if len(sys.argv) > 4 else 'deepseek-chat'\n")
        new_lines.append("with open('config/experiment.yaml', 'rb') as f_conf:\n")
        new_lines.append("    config_hash = hashlib.sha256(f_conf.read()).hexdigest()\n")
        new_lines.append(line)
        continue

    if "import httpx2" in line or "verify=False" in line or "client = OpenAI" in line or "base_url=" in line or "api_key=" in line or "http_client=" in line:
        if "client = OpenAI" in line: skip = True
        if skip and ")" in line: 
            skip = False
            new_lines.append("from agent.providers import complete\n")
            continue
        if skip: continue
        if "httpx2" in line: continue
        if "client = OpenAI(" in line: skip = True; continue

    if "MODEL = \"deepseek-chat\"" in line:
        continue # Removed, handled at top

    if "hash_str = f\"{MODEL}_{TEMP}_{run_seed}_{attempt_idx}_{prompt}\"" in line:
        new_lines.append("    hash_str = f\"{provider}|{MODEL}|{TEMP}|{run_seed}|{attempt_idx}|{prompt}\"\n")
        continue

    if "try:" in line and i > 130 and i < 155 and "client.chat.completions.create" in lines[i+1]:
        # we found the call_llm try block
        new_lines.append("    try:\n")
        new_lines.append("        res = complete(provider, MODEL, prompt, TEMP, 12, seed=run_seed)\n")
        new_lines.append("        ans = res['text']\n")
        new_lines.append("        usage = {'prompt_tokens': res['prompt_tokens'], 'completion_tokens': res['completion_tokens']}\n")
        new_lines.append("        res_dict = {'answer': ans, 'usage': usage}\n")
        new_lines.append("        with open(cache_path, 'w') as f:\n")
        new_lines.append("            json.dump(res_dict, f)\n")
        new_lines.append("        return res_dict\n")
        # now we need to skip the rest of the original try block until except
        skip = True
        continue
    
    if skip and "except Exception as e:" in line:
        skip = False
        new_lines.append(line)
        continue
        
    if "subprocess.run([sys.executable, \"extract/rescore.py\"" in line:
        line = line.replace("str(config_seed), out_json]", "str(config_seed), out_json, provider, MODEL, config_hash]")
        line = line.replace("str(config_seed), tmp_json]", "str(config_seed), tmp_json, provider, MODEL, config_hash]")

    if skip:
        continue

    new_lines.append(line)

# Add the config hash check right after stores['bitemporal'] is loaded
final_lines = []
for line in new_lines:
    final_lines.append(line)
    if "stores['bitemporal'] = BitemporalStore(f\"runs/store_data{config_seed}.db\")" in line:
        final_lines.append("    store_config_hash = stores['bitemporal'].get_meta('config_hash')\n")
        final_lines.append("    if store_config_hash and store_config_hash != config_hash:\n")
        final_lines.append("        print('ERROR: store_data DB config hash mismatch!')\n")
        final_lines.append("        sys.exit(1)\n")

with open('agent/harness.py', 'w') as f:
    f.writelines(final_lines)

