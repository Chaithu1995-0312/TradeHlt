"""Before/after matrix of consumer-branch statuses (reads two consumer_registry.json files; read-only)."""
import csv
import json
import sys
from pathlib import Path

before = json.loads(Path(sys.argv[1]).read_text()); after = json.loads(Path(sys.argv[2]).read_text()); out = Path(sys.argv[3]); out.mkdir(parents=True, exist_ok=True)
B = {b["id"]: b for b in before["branches"]}; A = {b["id"]: b for b in after["branches"]}
rows = []
for i in list(B) + [k for k in A if k not in B]:
    b, a = B.get(i), A.get(i)
    if b is None:
        kind = "new branch"
    elif a is None:
        kind = "removed"
    elif b["status"] != a["status"]:
        kind = "STATUS CHANGED"
    elif b["contract_identity"] != a["contract_identity"] or b["parity_evidence"] != a["parity_evidence"]:
        kind = "identity/evidence updated, status unchanged"
    else:
        kind = "unchanged"
    rows.append(dict(id=i, tree=(a or b)["tree"], before=b["status"] if b else "-", after=a["status"] if a else "-", change=kind))
with open(out / "branch_status_matrix.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
md = ["| ID | Tree | Before | After | Change |", "|---|---|---|---|---|"] + [f"| {r['id']} | {r['tree']} | {r['before']} | {r['after']} | {r['change']} |" for r in rows]
cnt = lambda reg: {s: sum(1 for b in reg["branches"] if b["status"] == s) for s in ("verified", "mismatched", "broken", "unverified")}
detail = []
for r in rows:
    if r["change"] in ("STATUS CHANGED", "new branch"):
        a = A[r["id"]]
        detail.append(f"### {r['id']} ({r['change']}: {r['before']} -> {r['after']})\n- **Producer:** {a['producer']}\n- **Transformation:** {a['transformation']}\n- **Consumer:** {a['consumer']}\n"
                      f"- **Dependency path:** {[(p['edge'], p['present']) for p in a['dependency_path']]}\n- **Contract identity:** {a['contract_identity']}\n"
                      f"- **Test/execution evidence:** {a['parity_evidence']}\n- **Required tests:** {a['required_tests']}\n" + (f"- **Does not imply:** {a['does_not_imply']}\n" if a.get('does_not_imply') else ""))
(out / "BEFORE_AFTER.md").write_text(f"# Consumer-branch status: before vs after\n\nBaseline: results/consumer_graph (commit {before['git_commit'][:10]}). After: {sys.argv[2]}.\n\n"
                                    f"Counts before {cnt(before)}; after {cnt(after)}.\n\n" + "\n".join(md) + "\n\n## Changed or new branches\n\n" + "\n".join(detail))
print(cnt(before), cnt(after)); print("\n".join(md))
