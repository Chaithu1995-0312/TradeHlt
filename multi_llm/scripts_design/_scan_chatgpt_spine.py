import json, re, sys
from pathlib import Path

paths = [
    Path(r"D:\chatgptviewer\conversations.json"),
    Path(r"D:\chatgptviewer\chatdata.json"),
]
# Prefer smaller structure walk
pat = re.compile(r"ultron|jarvis|sherlock|saul|fail[-_ ]?closed|control plane|lambda_control|track a|track b|ecs fargate|dry.?run|shadow", re.I)

def walk_messages(obj, title=""):
    hits = []
    if isinstance(obj, dict):
        t = obj.get("title") or obj.get("name") or title
        # chatgpt export shape: mapping -> message -> content -> parts
        if "mapping" in obj and isinstance(obj["mapping"], dict):
            for node in obj["mapping"].values():
                if not isinstance(node, dict):
                    continue
                msg = node.get("message") or {}
                content = (msg.get("content") or {})
                parts = content.get("parts") or []
                text = "\n".join(p for p in parts if isinstance(p, str))
                if text and pat.search(text):
                    # snippet around first match
                    m = pat.search(text)
                    i = max(0, m.start()-80)
                    snippet = re.sub(r"\s+", " ", text[i:i+220])
                    hits.append((t, snippet[:220]))
        else:
            for v in obj.values():
                hits.extend(walk_messages(v, t))
    elif isinstance(obj, list):
        for it in obj:
            hits.extend(walk_messages(it, title))
    return hits

# conversations.json is often a list of convos
p = Path(r"D:\chatgptviewer\conversations.json")
print("loading", p, "MB", round(p.stat().st_size/1e6,1))
with p.open(encoding="utf-8", errors="replace") as f:
    data = json.load(f)
print("top_type", type(data).__name__, "len", (len(data) if hasattr(data,"__len__") else "?"))

# collect title hits first (cheap)
title_hits = []
if isinstance(data, list):
    for conv in data:
        if not isinstance(conv, dict):
            continue
        title = conv.get("title") or ""
        if pat.search(title or ""):
            title_hits.append(title)
print("title_hits", len(title_hits))
for t in title_hits[:30]:
    print("TITLE:", t)

# sample message hits — cap
msg_hits = []
if isinstance(data, list):
    for conv in data:
        if len(msg_hits) >= 25:
            break
        if not isinstance(conv, dict):
            continue
        title = conv.get("title") or "(untitled)"
        found = walk_messages(conv, title)
        for t, snip in found:
            msg_hits.append((t, snip))
            if len(msg_hits) >= 25:
                break
print("msg_hit_samples", len(msg_hits))
for t, s in msg_hits[:20]:
    print("---", t)
    print(s)
