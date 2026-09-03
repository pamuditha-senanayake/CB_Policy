import os
for root, dirs, files in os.walk('.'):
    if 'conformance.py' in files:
        path = os.path.join(root, 'conformance.py')
        with open(path, 'r') as f:
            content = f.read()
        
        # We need to find the conformance calculation. It's likely a function returning 1.0 for len(trace) == 0.
        if "len(trace) == 0" in content:
            content = content.replace("return 1.0", "return None")
        
        with open(path, 'w') as f:
            f.write(content)
        print("Patched", path)
