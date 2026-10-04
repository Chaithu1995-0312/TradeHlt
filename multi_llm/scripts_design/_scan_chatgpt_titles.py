import json, re
from pathlib import Path

pat = re.compile(r"ultron|jarvis|sherlock|saul|fail[-_ ]?closed|track a|track b|ecs|dry.?run|shadow", re.I)
want_titles = {
    "Ultron Logic Design",
    "Jarvis Trading Update",
    "Sherlock Trading Module",
    "Saul Goodman Prompt",
    "Jarvis vs Ultron Mindset",
    "Jarvis Phase 5 Implementation",
    "Jarvis Phase 9 Finalization",
    "Nexus in Jarvis System",
}

path = Path(r"D:\chatgptviewer\conversations.json")
data = json.loads(path.read_text(encoding="utf-8", errors="replace"))

def msg_texts(conv):
    out = []
    mapping = conv.get("mapping") or {}
    for node in mapping.values():
        if not isinstance(node, dict):
            continue
        msg = node.get("message") or {}
        role = ((msg.get("author") or {}).get("role")) or ""
        parts = ((msg.get("content") or {}).get("parts")) or []
        text = "\n".join(p for p in parts if isinstance(p, str))
        if text.strip():
            out.append((role, text))
    return out

for conv in data:
    if not isinstance(conv, dict):
        continue
    title = conv.get("title") or ""
    if title not in want_titles:
        continue
    print("\n==== TITLE:", title, "====")
    texts = msg_texts(conv)
    # prefer assistant/user chunks that match spine words, else first meaty user+assistant
    scored = []
    for role, text in texts:
        if pat.search(text):
            m = pat.search(text)
            i = max(0, m.start() - 100)
            snip = re.sub(r"\s+", " ", text[i:i+350])
            scored.append((role, snip))
    for role, snip in scored[:4]:
        snip = snip.encode("ascii", "replace").decode("ascii")
        print(f"[{role}] {snip}")
