> Created: 2026-05-13 · Updated: 2026-05-13 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan: Restrict Control Plane UI to Valid Inputs

## Context

The CRT Control Plane UI (`src/control_plane/server.py`) currently generates free-text/number inputs without enforcing any bounds. `ArgSpec` in `types.py` has no `min_val`/`max_val` fields. As a result, users can enter out-of-range values (e.g., `workers=999`, `threshold=5.0`, `train_split=-3`) that will either crash downstream scripts or silently produce invalid results. The architecture defines precise valid ranges for every numeric argument (derived from `docs/CONFIG_REFERENCE.md`, `crt_engine_v2.py`, and the production config). This plan wires those constraints end-to-end: schema → server validation → UI rendering.

---

## Files to Modify

| File | Change |
|------|--------|
| `src/control_plane/types.py` | Add `min_val`, `max_val`, `help` to `ArgSpec` |
| `src/control_plane/registry.py` | (a) Populate `min_val`/`max_val`/`help` on every `ArgSpec`; (b) expose them in `command_spec_to_json`; (c) validate ranges in `merge_command_args` |
| `src/control_plane/server.py` | Update embedded JS: `argInputHtml` adds `min`/`max`/`step`, help text; `collectArgs` adds client-side range check with inline error |

---

## Step-by-Step Implementation

### Step 1 — `src/control_plane/types.py`

Add two optional numeric bounds and a `help` string to `ArgSpec`:

```python
@dataclass(frozen=True)
class ArgSpec:
    key: str
    flag: str | None = None
    kind: ArgKind = "str"
    required: bool = False
    default: Any = None
    choices: tuple[str, ...] = ()
    help: str = ""
    positional: bool = False
    positional_index: int = 0
    applies_to: tuple[str, ...] = ()
    min_val: float | None = None   # ADD
    max_val: float | None = None   # ADD
```

Backwards-compatible — all existing `ArgSpec` instantiations use keyword args, so no call sites break.

---

### Step 2 — `src/control_plane/registry.py`

#### 2a. Populate constraints on each `ArgSpec` in `core_command_specs()`

Apply the following bounds (derived from architecture docs and production config):

**`tuning.auto_tuner_multi` and `tuning.auto_tuner`:**
- `n_iter`: int, min=1, max=10000, help="Number of Bayesian search iterations"
- `seed`: int, min=0, max=2147483647, help="Random seed for reproducibility"
- `workers`: int, min=1, max=64, help="Parallel worker processes"
- `train_split`: float, min=0.1, max=1.0, help="Fraction of data used for training (0.1–1.0)"

**`backtest.v2`:**
- `htf`: int, min=1, max=100, help="Higher-timeframe lookback candles"
- `warmup`: int, min=10, max=1000, help="Candles to warm up indicators before scoring"
- `capital`: float, min=1000.0, max=10000000.0, help="Starting capital for simulation"
- `risk_pct`: float, min=0.01, max=5.0, help="Risk per trade as % of capital"
- `spread`: float, min=0.0, max=0.1, help="Simulated spread cost"
- `sweep_age`: int, min=5, max=100, help="Candles before sweep signal expires"
- `decay`: float, min=0.0, max=0.5, help="Score decay lambda per candle since retest"
- `threshold`: float, min=0.0, max=1.0, help="Minimum fusion score to open trade"

**`backtest.bitnet` and `replay.unified`:**
- `months`: int, min=1, max=60, help="Months of data to include (None=all)"

**`governance.orchestrator`:**
- `baseline_pnl`: float, min=-10000000.0, max=10000000.0, help="Baseline PnL from same dataset for comparison"

**`live.inout_runner`:**
- `cycles`: int, min=0, max=100000, help="Max cycles to run (0=unlimited)"

#### 2b. Expose in `command_spec_to_json`

```python
# In the args_schema list comprehension, add min_val and max_val:
{
    ...
    "min_val": a.min_val,
    "max_val": a.max_val,
    "help": a.help,
}
```

#### 2c. Add range validation in `merge_command_args`

After the existing choice-validation block:

```python
if arg.kind in ("int", "float") and value is not None:
    if arg.min_val is not None and value < arg.min_val:
        raise ValueError(f"{arg.key} must be >= {arg.min_val}, got {value}")
    if arg.max_val is not None and value > arg.max_val:
        raise ValueError(f"{arg.key} must be <= {arg.max_val}, got {value}")
```

---

### Step 3 — `src/control_plane/server.py` (embedded JS/HTML)

#### 3a. Update `argInputHtml()`

Current (line ~291–298):
```js
if(arg.kind==="int"||arg.kind==="float"){inputType="number";}
...
return `<label>${arg.key}</label><input id="${id}" type="${inputType}" value="${val}" ... />`;
```

Replace with:
```js
function argInputHtml(arg){
  const id = "arg_" + arg.key;
  const helpHtml = arg.help ? `<div class="small" style="color:var(--muted);margin-top:2px">${arg.help}</div>` : "";
  const errHtml = `<div id="err_${id}" class="small" style="color:var(--bad);display:none"></div>`;

  if(arg.kind === "bool"){
    return `<label><input id="${id}" type="checkbox" ${arg.default?"checked":""}/> ${arg.key}</label>${helpHtml}`;
  }
  if(arg.kind === "choice"){
    const opts = (arg.choices||[]).map(c=>`<option value="${c}" ${arg.default===c?"selected":""}>${c}</option>`).join("");
    return `<label>${arg.key}${arg.required?' <span style="color:var(--bad)">*</span>':''}</label><select id="${id}">${opts}</select>${helpHtml}`;
  }

  const val = (arg.default===null||arg.default===undefined) ? "" : String(arg.default);
  if(arg.kind === "int" || arg.kind === "float"){
    const minAttr = arg.min_val !== null && arg.min_val !== undefined ? ` min="${arg.min_val}"` : "";
    const maxAttr = arg.max_val !== null && arg.max_val !== undefined ? ` max="${arg.max_val}"` : "";
    const stepAttr = arg.kind === "float" ? ` step="any"` : ` step="1"`;
    const rangePlaceholder = (arg.min_val !== null && arg.max_val !== null)
      ? `${arg.min_val} – ${arg.max_val}` : "";
    const req = arg.required ? ' <span style="color:var(--bad)">*</span>' : '';
    return `<label>${arg.key}${req}</label><input id="${id}" type="number" value="${val}"${minAttr}${maxAttr}${stepAttr} placeholder="${rangePlaceholder}" oninput="validateArg('${id}',${arg.min_val},${arg.max_val})" />${helpHtml}${errHtml}`;
  }

  // str / list
  const req = arg.required ? ' <span style="color:var(--bad)">*</span>' : '';
  return `<label>${arg.key}${req}</label><input id="${id}" type="text" value="${val}" placeholder="${arg.kind==='list'?'comma,separated,values':''}" />${helpHtml}`;
}
```

#### 3b. Add `validateArg()` JS helper

Insert near the top of the `<script>` block:
```js
function validateArg(id, minVal, maxVal){
  const node = el(id);
  const errNode = el("err_" + id);
  if(!node || !errNode){ return true; }
  const v = parseFloat(node.value);
  if(node.value.trim() === ""){ errNode.style.display="none"; return true; }
  if(isNaN(v)){
    errNode.textContent = "Must be a number"; errNode.style.display="";
    node.style.borderColor = "var(--bad)"; return false;
  }
  if(minVal !== null && minVal !== undefined && v < minVal){
    errNode.textContent = `Min value: ${minVal}`; errNode.style.display="";
    node.style.borderColor = "var(--bad)"; return false;
  }
  if(maxVal !== null && maxVal !== undefined && v > maxVal){
    errNode.textContent = `Max value: ${maxVal}`; errNode.style.display="";
    node.style.borderColor = "var(--bad)"; return false;
  }
  errNode.style.display = "none";
  node.style.borderColor = "";
  return true;
}
```

#### 3c. Guard `runCommand()` with client-side validation

Before the fetch in `runCommand()`, validate all numeric fields:
```js
async function runCommand(){
  const cmd = selectedCommand();
  // Validate required fields and numeric ranges
  let valid = true;
  (cmd.args_schema||[]).forEach(arg => {
    if((arg.kind==="int"||arg.kind==="float") && (arg.min_val!==null||arg.max_val!==null)){
      if(!validateArg("arg_"+arg.key, arg.min_val, arg.max_val)){ valid = false; }
    }
    if(arg.required){
      const node = el("arg_"+arg.key);
      if(node && !node.value.trim()){
        const errNode = el("err_arg_"+arg.key);
        if(errNode){ errNode.textContent="Required"; errNode.style.display=""; }
        node.style.borderColor = "var(--bad)";
        valid = false;
      }
    }
  });
  if(!valid){ return; }
  // ... existing fetch code ...
}
```

---

## Scope Boundaries

- **No changes** to any engine, backtest, or config files — this is purely a UI + registry schema change.
- **No new dependencies** — pure stdlib HTML/JS/Python.
- `ArgSpec` is `frozen=True`; the new fields use `None` defaults so all existing instantiations remain valid.
- Server-side validation in `merge_command_args` acts as the authoritative gate; client-side is UX only.

---

## Verification

1. Start the control plane: `python src/control_plane/server.py`
2. Open `http://localhost:8787`
3. Select **Backtest v2** → set `threshold=2.0` → click Run → should show "Max value: 1.0" inline error and block submission.
4. Set `threshold=0.75` → error clears, Run proceeds.
5. Select **Auto Tuner (Multi)** → verify `workers` input shows `min=1 max=64` attributes in browser inspector.
6. POST directly: `curl -X POST http://localhost:8787/commands/backtest.v2/runs -d '{"args":{"csv":"x.csv","threshold":5.0}}'` → should return 400 with "must be <= 1.0" message.
7. Confirm `choices` dropdowns still work (e.g., `backtest.bitnet` gate_mode).
