import io
p = "configs/formulas/market_ontology.yaml"
lines = io.open(p, encoding="utf-8").read().splitlines()
# find the node key line (4-space indent) and the sibling boundary
start = next(i for i, l in enumerate(lines) if l == "    mother_range_prior:")
end = next(i for i, l in enumerate(lines[start + 1:], start + 1)
           if l.startswith("  ") and not l.startswith("   ") and ":" in l and l.strip().startswith("crt_displacement_volume_participation"))
out = []
for i, l in enumerate(lines):
    if start <= i < end:
        if l.startswith("    "):
            l = l[2:]
        elif l.startswith("  "):
            l = l[2:]
        elif l.startswith(" "):
            l = l[1:]
    out.append(l)
io.open(p, "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
print("dedented lines", start, "to", end - 1)