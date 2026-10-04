from pathlib import Path
d = Path(__file__).parent
html = (d / "xau_template.html").read_text(encoding="utf-8")
data = (d / "xau_10d_features.json").read_text(encoding="utf-8")
(d / "xau_bar_features.html").write_text(html.replace("__DATA__", data), encoding="utf-8")
print("ok", len(html) + len(data))
