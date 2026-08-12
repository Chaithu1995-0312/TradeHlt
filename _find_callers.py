import os, re

root = '.'
patterns = [r'crt_engine\.compute', r'crt_compute', r'compute_scores']
matches = []

for dirpath, dirnames, filenames in os.walk(root):
    # skip hidden dirs and __pycache__
    dirnames[:] = [d for d in dirnames if not d.startswith('__') and not d.startswith('.')]
    for fn in filenames:
        if not fn.endswith('.py'):
            continue
        fp = os.path.join(dirpath, fn)
        try:
            with open(fp, encoding='utf-8', errors='ignore') as f:
                content = f.read()
            for pat in patterns:
                if re.search(pat, content):
                    matches.append((fp, pat))
                    break
        except Exception:
            pass

for fp, pat in sorted(matches):
    print(f"{pat:40s} {fp}")
print(f"\nTotal: {len(matches)}")