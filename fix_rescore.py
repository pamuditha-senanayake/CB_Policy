with open('extract/rescore.py', 'r') as f:
    content = f.read()

content = content.replace("expected_json_path = sys.argv[5]", """expected_json_path = sys.argv[5]
provider = sys.argv[6] if len(sys.argv) > 6 else "deepseek"
model = sys.argv[7] if len(sys.argv) > 7 else "deepseek-chat"
config_hash = sys.argv[8] if len(sys.argv) > 8 else ""
""")

content = content.replace("    \"data_seed\": config_seed,", """    "data_seed": config_seed,
    "run_seed": run_seed,
    "provider": provider,
    "model": model,
    "config_hash": config_hash,""")

with open('extract/rescore.py', 'w') as f:
    f.write(content)
