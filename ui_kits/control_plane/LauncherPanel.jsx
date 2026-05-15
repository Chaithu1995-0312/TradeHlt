// LauncherPanel — supports positional args, applies_to filtering, shell-quote
// preview, file uploader on data/file-shaped args.

const { useState: useStateL, useEffect: useEffectL, useMemo: useMemoL } = React;

function shellQuote(s) {
  if (s === null || s === undefined) return "";
  const str = String(s);
  if (str === "") return "''";
  if (/^[A-Za-z0-9_@%+=:,./-]+$/.test(str)) return str;
  return "'" + str.replace(/'/g, "'\\''") + "'";
}

function LauncherPanel({ commands, categories, runs, search, setSearch, onRun, onStop, onInspect, selectedRunId, onCommandComplete }) {
  const [category, setCategory] = useStateL(categories[0] || "");
  const cmdsInCategory = commands.filter(c => c.category === category);
  const [commandId, setCommandId] = useStateL(cmdsInCategory[0]?.id);
  const cmd = commands.find(c => c.id === commandId) || cmdsInCategory[0];
  const [args, setArgs] = useStateL({});

  useEffectL(() => {
    const newCmds = commands.filter(c => c.category === category);
    if (!newCmds.find(c => c.id === commandId)) setCommandId(newCmds[0]?.id);
  }, [category]);

  useEffectL(() => {
    if (!cmd) return;
    const init = {};
    (cmd.args_schema || []).forEach(a => { init[a.key] = a.default; });
    setArgs(init);
  }, [commandId]);

  const setArg = (k, v) => setArgs(prev => ({ ...prev, [k]: v }));

  // Effective subcommand value (positional choice arg with key === "subcommand")
  const subArg = (cmd?.args_schema || []).find(a => a.key === "subcommand");
  const selectedSub = subArg ? (args.subcommand ?? subArg.default) : null;

  // Is this arg applicable given the current subcommand?
  const isApplicable = (a) => {
    if (!a.applies_to || a.applies_to.length === 0) return true;
    return selectedSub && a.applies_to.includes(selectedSub);
  };

  const preview = useMemoL(() => {
    if (!cmd) return "";
    const parts = [];
    parts.push("python");
    if (cmd.mode === "module") parts.push("-m", cmd.script);
    else parts.push(cmd.script);

    const schema = cmd.args_schema || [];
    const positionals = schema.filter(a => a.positional).slice().sort((a, b) => (a.positional_index ?? 0) - (b.positional_index ?? 0));
    for (const a of positionals) {
      if (!isApplicable(a)) continue;
      const v = args[a.key];
      if (v === undefined || v === null || v === "") continue;
      parts.push(shellQuote(v));
    }
    for (const a of schema) {
      if (a.positional) continue;
      if (!isApplicable(a)) continue;
      const v = args[a.key];
      if (v === undefined || v === null || v === "") continue;
      if (a.kind === "bool") { if (v) parts.push(a.flag); continue; }
      if (a.kind === "list") {
        const arr = Array.isArray(v) ? v : String(v).split(",").map(x => x.trim()).filter(Boolean);
        if (!arr.length) continue;
        parts.push(a.flag);
        for (const item of arr) parts.push(shellQuote(item));
        continue;
      }
      if (!a.flag) continue;
      parts.push(a.flag, shellQuote(v));
    }
    return parts.join(" ");
  }, [cmd, args, selectedSub]);

  const required = (cmd?.args_schema || [])
    .filter(a => a.required && isApplicable(a))
    .map(a => a.flag || a.key);

  const filteredRuns = runs.filter(r => {
    if (!search) return true;
    const q = search.toLowerCase();
    return r.run_id.includes(q) || r.command_id.toLowerCase().includes(q);
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14, minHeight: 0 }}>
      <Panel title="Command Launcher" id="launcherPanel">
        <Label>Category</Label>
        <Select value={category} onChange={e => setCategory(e.target.value)}>
          {categories.map(c => <option key={c} value={c}>{c}</option>)}
        </Select>
        <Label>Command</Label>
        <Select value={commandId} onChange={e => setCommandId(e.target.value)}>
          {cmdsInCategory.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}
        </Select>
        <div style={{ fontSize: 12, color: "#9fb0c8", marginTop: 6 }}>{cmd?.description}</div>
        <Helper title="When to run this">{cmd?.quickstart_notes?.[0] || "No quickstart note available."}</Helper>
        <Helper title="Minimum required fields">{required.length ? required.join(", ") : "No mandatory flags for default command mode."}</Helper>
        <Helper title="What artifacts to check next">{(cmd?.artifacts || []).join(", ") || "No explicit artifact pattern declared."}</Helper>

        {(cmd?.args_schema || []).length === 0 && (
          <div style={{ marginTop: 10, fontSize: 12, color: "#9fb0c8", fontStyle: "italic" }}>
            No arguments. Click Run Command to execute with defaults.
          </div>
        )}

        <div id="formArea" style={{ marginTop: 8 }}>
          {(cmd?.args_schema || []).map(a => {
            if (!isApplicable(a)) return null;
            const v = args[a.key];

            if (a.kind === "bool") {
              return (
                <Label key={a.key}>
                  <input type="checkbox" checked={!!v} onChange={e => setArg(a.key, e.target.checked)} style={{ marginRight: 6 }} />
                  {a.key}
                </Label>
              );
            }

            if (a.kind === "choice") {
              return (
                <React.Fragment key={a.key}>
                  <Label>
                    {a.positional ? <span style={{ color: "#0ea5a3" }}>● </span> : null}
                    {a.key}{a.required && <span style={{ color: "#ef4444" }}> *</span>}
                  </Label>
                  <Select value={v ?? ""} onChange={e => setArg(a.key, e.target.value)}>
                    {(a.choices || []).map(c => <option key={c} value={c}>{c}</option>)}
                  </Select>
                </React.Fragment>
              );
            }

            // Catalog-backed combobox: restrict to known options from data/ and
            // configs/production/. Falls through to free text + uploader otherwise.
            const k = (a.key || "").toLowerCase();
            const catalog = window.CATALOG || {};
            let comboOptions = null;
            let comboPlaceholder = "";
            if (k === "csv" || k === "data") {
              comboOptions = catalog.data_csv || [];
              comboPlaceholder = "Select a CSV from data/";
            } else if (k === "files") {
              comboOptions = catalog.data_all || [];
              comboPlaceholder = "Select one or more files from data/";
            } else if (k === "instrument") {
              comboOptions = catalog.instruments || [];
              comboPlaceholder = "Select an instrument";
            } else if (k === "instruments") {
              comboOptions = catalog.instruments || [];
              comboPlaceholder = "Select one or more instruments";
            } else if (k === "config" || k === "active_config") {
              comboOptions = catalog.prod_configs || [];
              comboPlaceholder = "Select a production config";
            } else if (k === "version") {
              comboOptions = catalog.prod_versions || [];
              comboPlaceholder = "Select a version";
            }

            if (comboOptions) {
              const isMulti = a.kind === "list";
              return (
                <React.Fragment key={a.key}>
                  <Label>
                    {a.positional ? <span style={{ color: "#0ea5a3" }}>● </span> : null}
                    {a.key}{a.required && <span style={{ color: "#ef4444" }}> *</span>}
                    <span style={{ color: "#6b7a93", fontSize: 11, marginLeft: 6, fontFamily: "ui-monospace,Menlo,monospace" }}>
                      ({comboOptions.length} {isMulti ? "options · multi" : "options"})
                    </span>
                  </Label>
                  <ComboBox
                    multi={isMulti}
                    options={comboOptions}
                    value={isMulti ? (Array.isArray(v) ? v : []) : (v ?? "")}
                    placeholder={comboPlaceholder}
                    onChange={(next) => setArg(a.key, next)}
                  />
                </React.Fragment>
              );
            }

            // Free-text fallback (with optional file uploader for path-like keys)
            const fileLike = /(data|csv|file|path|checkpoint|dataset|config|model|input|source|report|params|log|trades|bin|prompt|active)/.test(k);
            const isMulti = a.kind === "list";
            const accept = /(csv|data|trades)/.test(k) ? ".csv,.tsv,.json,.parquet,.xlsx,.xls"
                          : /(model|checkpoint|bin)/.test(k) ? ".pth,.pt,.json,.bin,.gguf"
                          : /(config|active|params|report)/.test(k) ? ".json,.yaml,.yml,.toml"
                          : /(log|prompt)/.test(k) ? ".jsonl,.log,.txt"
                          : "";

            return (
              <React.Fragment key={a.key}>
                <Label>
                  {a.positional ? <span style={{ color: "#0ea5a3" }}>● </span> : null}
                  {a.key}{a.required && <span style={{ color: "#ef4444" }}> *</span>}
                </Label>
                <Input
                  type={a.kind === "int" || a.kind === "float" ? "number" : "text"}
                  value={Array.isArray(v) ? v.join(",") : (v ?? "")}
                  placeholder={a.kind === "list" ? "comma,separated,values" : (a.default == null ? "" : String(a.default))}
                  onChange={e => {
                    const raw = e.target.value;
                    if (a.kind === "int") setArg(a.key, raw === "" ? "" : parseInt(raw, 10));
                    else if (a.kind === "float") setArg(a.key, raw === "" ? "" : parseFloat(raw));
                    else if (a.kind === "list") setArg(a.key, raw.split(",").map(x => x.trim()).filter(Boolean));
                    else setArg(a.key, raw);
                  }}
                />
                {fileLike && (
                  <FileUploader
                    multi={isMulti}
                    accept={accept}
                    onSelect={(names) => {
                      if (isMulti) setArg(a.key, names);
                      else setArg(a.key, names[0] || "");
                    }}
                  />
                )}
              </React.Fragment>
            );
          })}
        </div>
        <Label>Resolved CLI Preview</Label>
        <Pre id="preview">{preview}</Pre>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 10 }}>
          <Button onClick={() => { onRun(cmd, args, preview); onCommandComplete(cmd.id); }}>Run Command</Button>
          <Button onClick={onStop}>Stop Latest Run</Button>
        </div>
      </Panel>

      <Panel title="Run History" id="historyPanel">
        <Input placeholder="Search by run id / command / args" value={search} onChange={e => setSearch(e.target.value)} />
        <div style={{ maxHeight: 330, overflow: "auto", marginTop: 8 }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr><th style={th}>Run</th><th style={th}>Command</th><th style={th}>Status</th></tr>
            </thead>
            <tbody>
              {filteredRuns.map(r => (
                <tr key={r.run_id} onClick={() => onInspect(r.run_id)}
                    style={{ cursor: "pointer", background: r.run_id === selectedRunId ? "#0f1b2e" : "transparent" }}>
                  <td style={{ ...td, fontFamily: "ui-monospace,Menlo,monospace" }}>{r.run_id.slice(0, 8)}</td>
                  <td style={td}>{r.command_id}</td>
                  <td style={td}><StatusPill status={r.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

const th = { borderBottom: "1px solid #23364e", padding: "6px 4px", fontSize: 12, textAlign: "left", color: "#9fb0c8" };
const td = { borderBottom: "1px solid #23364e", padding: "6px 4px", fontSize: 12 };

window.LauncherPanel = LauncherPanel;
