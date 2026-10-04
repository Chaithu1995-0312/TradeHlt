// File-uploader primitive: drag-or-click target for single or multi file picks.
// Uses File API only (no upload to backend in this kit) — captures filenames
// (with size) and surfaces them as the value for the associated arg.

function FileUploader({ multi, accept, onSelect }) {
  const inputRef = React.useRef(null);
  const [files, setFiles] = React.useState([]);
  const [drag, setDrag] = React.useState(false);

  const handleFiles = (fileList) => {
    const arr = Array.from(fileList || []);
    if (!arr.length) return;
    const next = multi ? arr : [arr[0]];
    setFiles(next);
    onSelect(next.map(f => f.name));
  };

  const remove = (idx) => {
    const next = files.filter((_, i) => i !== idx);
    setFiles(next);
    onSelect(next.map(f => f.name));
  };

  const fmtSize = (n) => {
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
    return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`;
  };

  return (
    <div style={{ marginTop: 6 }}>
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); handleFiles(e.dataTransfer.files); }}
        style={{
          cursor: "pointer",
          border: `1px dashed ${drag ? "#0ea5a3" : "#23364e"}`,
          background: drag ? "rgba(14,165,163,.06)" : "#0d1626",
          borderRadius: 8,
          padding: "10px 12px",
          fontSize: 12,
          color: "#9fb0c8",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 8,
        }}
      >
        <span>
          <span style={{ color: "#0ea5a3", fontWeight: 600 }}>{multi ? "Upload files" : "Upload file"}</span>
          {" "}or drop {multi ? "files" : "a file"} here
          {accept && <span style={{ color: "#6b7a93" }}> · {accept}</span>}
        </span>
        <span style={{ fontSize: 11, color: "#6b7a93", fontFamily: "ui-monospace,Menlo,monospace" }}>
          {multi ? "multi" : "single"}
        </span>
      </div>
      <input
        ref={inputRef}
        type="file"
        multiple={!!multi}
        accept={accept || undefined}
        onChange={(e) => handleFiles(e.target.files)}
        style={{ display: "none" }}
      />
      {files.length > 0 && (
        <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 4 }}>
          {files.map((f, i) => (
            <div key={i} style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              gap: 8, fontSize: 11, padding: "4px 8px",
              background: "#091121", border: "1px solid #23364e", borderRadius: 6,
              fontFamily: "ui-monospace,Menlo,monospace",
            }}>
              <span style={{ color: "#e6edf7", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.name}</span>
              <span style={{ display: "flex", gap: 8, alignItems: "center", flexShrink: 0 }}>
                <span style={{ color: "#9fb0c8" }}>{fmtSize(f.size)}</span>
                <span onClick={(e) => { e.stopPropagation(); remove(i); }}
                      style={{ cursor: "pointer", color: "#ef4444" }}>×</span>
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

window.FileUploader = FileUploader;
