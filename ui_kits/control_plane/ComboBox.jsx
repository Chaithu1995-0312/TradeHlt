// ComboBox — strict, searchable single/multi select. Restricts input to a known
// list of options. Single mode shows a typeahead input + dropdown. Multi mode
// renders selected values as chips with a typeahead below.

const { useState: useStateC, useRef: useRefC, useEffect: useEffectC } = React;

function ComboBox({ value, options, multi, placeholder, onChange, allowFreeText }) {
  const [open, setOpen] = useStateC(false);
  const [query, setQuery] = useStateC("");
  const rootRef = useRefC(null);
  const inputRef = useRefC(null);

  useEffectC(() => {
    const onDocClick = (e) => { if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  const selected = multi
    ? (Array.isArray(value) ? value : (value ? [value] : []))
    : (value ?? "");

  const filtered = options.filter(o => o.toLowerCase().includes(query.toLowerCase()));

  const isInvalid = !allowFreeText && (
    multi
      ? selected.some(v => !options.includes(v))
      : (selected && !options.includes(selected))
  );

  const pickOne = (opt) => {
    if (multi) {
      const next = selected.includes(opt) ? selected.filter(v => v !== opt) : [...selected, opt];
      onChange(next);
      setQuery("");
      inputRef.current?.focus();
    } else {
      onChange(opt);
      setQuery("");
      setOpen(false);
    }
  };

  const removeChip = (opt) => onChange(selected.filter(v => v !== opt));

  const fieldStyle = {
    width: "100%", boxSizing: "border-box",
    background: "#0d1626",
    border: `1px solid ${isInvalid ? "#ef4444" : "#23364e"}`,
    borderRadius: 8, padding: multi ? "5px 6px" : "8px 10px",
    fontSize: 13, color: "#e6edf7",
    display: "flex", flexWrap: "wrap", gap: 4, alignItems: "center",
    cursor: "text", minHeight: 36,
  };

  return (
    <div ref={rootRef} style={{ position: "relative", width: "100%" }}>
      <div style={fieldStyle} onClick={() => { setOpen(true); inputRef.current?.focus(); }}>
        {multi && selected.map(v => (
          <span key={v} style={{
            display: "inline-flex", alignItems: "center", gap: 4,
            background: "#122033", border: `1px solid ${options.includes(v) ? "#23364e" : "#ef4444"}`,
            color: options.includes(v) ? "#0ea5a3" : "#ef4444",
            borderRadius: 16, padding: "1px 4px 1px 8px", fontSize: 11,
            fontFamily: "ui-monospace,Menlo,monospace",
          }}>
            {v}
            <span onClick={(e) => { e.stopPropagation(); removeChip(v); }}
                  style={{ cursor: "pointer", padding: "0 4px", color: "#9fb0c8" }}>×</span>
          </span>
        ))}
        <input
          ref={inputRef}
          type="text"
          value={open ? query : (multi ? "" : (selected || ""))}
          onFocus={() => setOpen(true)}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); if (!multi && allowFreeText) onChange(e.target.value); }}
          onKeyDown={(e) => {
            if (e.key === "Backspace" && multi && !query && selected.length) {
              onChange(selected.slice(0, -1));
            } else if (e.key === "Enter") {
              e.preventDefault();
              if (filtered.length) pickOne(filtered[0]);
              else if (allowFreeText && query) { if (multi) onChange([...selected, query]); else onChange(query); setQuery(""); setOpen(false); }
            } else if (e.key === "Escape") {
              setOpen(false);
            }
          }}
          placeholder={(multi && selected.length === 0) ? (placeholder || "Select…") : (!multi && !selected) ? (placeholder || "Select…") : ""}
          style={{
            flex: 1, minWidth: 80, border: "none", outline: "none",
            background: "transparent", color: "#e6edf7", fontSize: 13,
            fontFamily: "inherit", padding: multi ? "4px 6px" : 0,
          }}
        />
        <span style={{ color: "#9fb0c8", fontSize: 10, marginLeft: 4 }}>{open ? "▴" : "▾"}</span>
      </div>

      {open && (
        <div style={{
          position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0,
          background: "#091121", border: "1px solid #23364e", borderRadius: 8,
          maxHeight: 220, overflow: "auto", zIndex: 50,
          boxShadow: "0 8px 24px rgba(0,0,0,.4)",
        }}>
          {filtered.length === 0 && (
            <div style={{ padding: "8px 10px", fontSize: 12, color: "#9fb0c8" }}>
              {allowFreeText ? "No matches — press Enter to use as free text" : "No matches"}
            </div>
          )}
          {filtered.map(opt => {
            const isSel = multi ? selected.includes(opt) : selected === opt;
            return (
              <div
                key={opt}
                onClick={() => pickOne(opt)}
                style={{
                  padding: "6px 10px", fontSize: 12,
                  cursor: "pointer",
                  background: isSel ? "rgba(14,165,163,.08)" : "transparent",
                  color: isSel ? "#0ea5a3" : "#e6edf7",
                  fontFamily: "ui-monospace,Menlo,monospace",
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = "rgba(14,165,163,.06)"}
                onMouseLeave={(e) => e.currentTarget.style.background = isSel ? "rgba(14,165,163,.08)" : "transparent"}
              >
                <span>{opt}</span>
                {isSel && <span style={{ color: "#0ea5a3", fontSize: 11 }}>✓</span>}
              </div>
            );
          })}
        </div>
      )}

      {isInvalid && (
        <div style={{ marginTop: 4, fontSize: 11, color: "#ef4444" }}>
          Value not in allowed list.
        </div>
      )}
    </div>
  );
}

window.ComboBox = ComboBox;
