with open('agent/providers.py', 'r') as f:
    content = f.read()

content = content.replace('"max_tokens": max_tokens,', '"max_completion_tokens": max_tokens,')
content = content.replace('max_completion_tokens": max_tokens,\n                    "stop": ["\\n"]', 'max_completion_tokens": max_tokens')

with open('agent/providers.py', 'w') as f:
    f.write(content)
