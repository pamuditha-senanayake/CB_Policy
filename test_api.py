from dotenv import load_dotenv
load_dotenv()
import os
from agent.providers import complete
try:
    print(complete('deepseek', 'deepseek-v4-flash', 'Hello', 0.6, 10))
    print('Deepseek OK')
except Exception as e:
    print('Deepseek FAIL:', e)
try:
    print(complete('anthropic', 'claude-sonnet-5', 'Hello', 0.6, 10))
    print('Anthropic OK')
except Exception as e:
    print('Anthropic FAIL:', e)
try:
    print(complete('openai', 'gpt-5.6-luna', 'Hello', 0.6, 10))
    print('OpenAI OK')
except Exception as e:
    print('OpenAI FAIL:', e)
