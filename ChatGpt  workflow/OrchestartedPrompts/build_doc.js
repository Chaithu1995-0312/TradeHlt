const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, HeadingLevel, AlignmentType, BorderStyle, WidthType,
  ShadingType, LevelFormat, PageNumber, PageBreak, TableOfContents,
  VerticalAlign, TabStopType, TabStopPosition
} = require('docx');
const fs = require('fs');

// ── Colours ──────────────────────────────────────────────────────────────────
const C = {
  blue:       "1A56DB",
  blueDark:   "1E40AF",
  blueLight:  "DBEAFE",
  bluePale:   "EFF6FF",
  green:      "057A55",
  greenLight: "DEF7EC",
  amber:      "92400E",
  amberLight: "FEF3C7",
  red:        "9B1C1C",
  redLight:   "FEE2E2",
  gray:       "374151",
  grayLight:  "F3F4F6",
  grayMid:    "D1D5DB",
  white:      "FFFFFF",
  black:      "111827",
  mono:       "1E293B",
  monoBg:     "F8FAFC",
};

// ── Helpers ───────────────────────────────────────────────────────────────────
const border = (color = C.grayMid) => ({ style: BorderStyle.SINGLE, size: 1, color });
const allBorders = (color = C.grayMid) => ({ top: border(color), bottom: border(color), left: border(color), right: border(color) });
const noBorder = () => ({ style: BorderStyle.NONE, size: 0, color: "FFFFFF" });
const noBorders = () => ({ top: noBorder(), bottom: noBorder(), left: noBorder(), right: noBorder() });

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text, font: "Arial", size: 32, bold: true, color: C.blueDark })],
    spacing: { before: 320, after: 160 },
  });
}
function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    children: [new TextRun({ text, font: "Arial", size: 26, bold: true, color: C.gray })],
    spacing: { before: 240, after: 120 },
  });
}
function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    children: [new TextRun({ text, font: "Arial", size: 22, bold: true, color: C.gray })],
    spacing: { before: 200, after: 80 },
  });
}
function body(text, opts = {}) {
  return new Paragraph({
    children: [new TextRun({ text, font: "Arial", size: 22, color: C.black, ...opts })],
    spacing: { before: 60, after: 60 },
  });
}
function space(before = 120) {
  return new Paragraph({ children: [new TextRun("")], spacing: { before, after: 0 } });
}
function pageBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}
function bullet(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "bullets", level },
    children: [new TextRun({ text, font: "Arial", size: 22, color: C.black })],
    spacing: { before: 40, after: 40 },
  });
}
function numbered(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "numbers", level },
    children: [new TextRun({ text, font: "Arial", size: 22, color: C.black })],
    spacing: { before: 60, after: 60 },
  });
}
function infoBanner(text, bgColor = C.bluePale, textColor = C.blueDark) {
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [9360],
    rows: [new TableRow({ children: [
      new TableCell({
        borders: { top: border(C.blue), bottom: border(C.blue), left: { style: BorderStyle.SINGLE, size: 12, color: C.blue }, right: noBorder() },
        shading: { fill: bgColor, type: ShadingType.CLEAR },
        margins: { top: 100, bottom: 100, left: 160, right: 160 },
        width: { size: 9360, type: WidthType.DXA },
        children: [new Paragraph({ children: [new TextRun({ text, font: "Arial", size: 20, color: textColor })], spacing: { before: 0, after: 0 } })]
      })
    ]})]
  });
}

// ── Code block (monospace table) ─────────────────────────────────────────────
function codeBlock(lines) {
  const rows = lines.map(line =>
    new TableRow({ children: [
      new TableCell({
        borders: noBorders(),
        shading: { fill: C.monoBg, type: ShadingType.CLEAR },
        margins: { top: 20, bottom: 20, left: 200, right: 100 },
        width: { size: 9360, type: WidthType.DXA },
        children: [new Paragraph({
          children: [new TextRun({ text: line || " ", font: "Courier New", size: 18, color: C.mono })],
          spacing: { before: 0, after: 0 },
        })]
      })
    ]})
  );
  // Wrap with outer border table
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [9360],
    rows: [new TableRow({ children: [
      new TableCell({
        borders: allBorders(C.grayMid),
        shading: { fill: C.monoBg, type: ShadingType.CLEAR },
        margins: { top: 60, bottom: 60, left: 0, right: 0 },
        width: { size: 9360, type: WidthType.DXA },
        children: [
          new Table({
            width: { size: 9200, type: WidthType.DXA },
            columnWidths: [9200],
            rows,
            margins: { top: 0, bottom: 0, left: 0, right: 0 },
          })
        ]
      })
    ]})]
  });
}

// ── Two-column comparison table ───────────────────────────────────────────────
function compareTable(badText, goodText) {
  const half = 4560;
  const gap = 240;
  const headerCell = (text, bg, textColor) => new TableCell({
    borders: allBorders(bg),
    shading: { fill: bg, type: ShadingType.CLEAR },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    width: { size: half, type: WidthType.DXA },
    children: [new Paragraph({ children: [new TextRun({ text, font: "Arial", size: 20, bold: true, color: textColor })], spacing: { before: 0, after: 0 } })]
  });
  const bodyCell = (text, bg, border_color) => new TableCell({
    borders: allBorders(border_color),
    shading: { fill: bg, type: ShadingType.CLEAR },
    margins: { top: 100, bottom: 100, left: 120, right: 120 },
    width: { size: half, type: WidthType.DXA },
    children: [new Paragraph({ children: [new TextRun({ text, font: "Courier New", size: 18, color: C.mono })], spacing: { before: 0, after: 0 } })]
  });
  const spacerCell = () => new TableCell({
    borders: noBorders(),
    width: { size: gap, type: WidthType.DXA },
    children: [new Paragraph({ children: [new TextRun("")] })]
  });
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [half, gap, half],
    rows: [
      new TableRow({ children: [headerCell("❌  Too vague", C.redLight, C.red), spacerCell(), headerCell("✓  Enhanced", C.greenLight, C.green)] }),
      new TableRow({ children: [bodyCell(badText, C.redLight, C.red), spacerCell(), bodyCell(goodText, C.greenLight, C.green)] }),
    ]
  });
}

// ── Agent card ────────────────────────────────────────────────────────────────
function agentCard(name, role, model, constraint, color) {
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [9360],
    rows: [
      new TableRow({ children: [new TableCell({
        borders: { top: noBorder(), bottom: noBorder(), left: { style: BorderStyle.SINGLE, size: 16, color }, right: noBorder() },
        shading: { fill: C.grayLight, type: ShadingType.CLEAR },
        margins: { top: 100, bottom: 100, left: 200, right: 160 },
        width: { size: 9360, type: WidthType.DXA },
        children: [
          new Paragraph({ children: [new TextRun({ text: name, font: "Arial", size: 24, bold: true, color: C.black }), new TextRun({ text: "  —  " + role, font: "Arial", size: 22, color: C.gray })], spacing: { before: 0, after: 40 } }),
          new Paragraph({ children: [new TextRun({ text: "Model: ", font: "Arial", size: 20, bold: true, color: C.gray }), new TextRun({ text: model, font: "Arial", size: 20, color: C.gray })], spacing: { before: 0, after: 40 } }),
          new Paragraph({ children: [new TextRun({ text: "Never: ", font: "Arial", size: 20, bold: true, color: C.red }), new TextRun({ text: constraint, font: "Arial", size: 20, color: C.black })], spacing: { before: 0, after: 0 } }),
        ]
      })] })
    ]
  });
}

// ── Chain step row ────────────────────────────────────────────────────────────
function chainStep(num, agent, description) {
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [560, 8800],
    rows: [new TableRow({ children: [
      new TableCell({
        borders: noBorders(),
        shading: { fill: C.blueLight, type: ShadingType.CLEAR },
        verticalAlign: VerticalAlign.CENTER,
        margins: { top: 80, bottom: 80, left: 100, right: 100 },
        width: { size: 560, type: WidthType.DXA },
        children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: String(num), font: "Arial", size: 22, bold: true, color: C.blue })], spacing: { before: 0, after: 0 } })]
      }),
      new TableCell({
        borders: noBorders(),
        margins: { top: 80, bottom: 80, left: 160, right: 100 },
        width: { size: 8800, type: WidthType.DXA },
        children: [
          new Paragraph({ children: [new TextRun({ text: agent, font: "Arial", size: 22, bold: true, color: C.black })], spacing: { before: 0, after: 40 } }),
          new Paragraph({ children: [new TextRun({ text: description, font: "Arial", size: 20, color: C.gray })], spacing: { before: 0, after: 0 } }),
        ]
      })
    ]})]
  });
}

// ── Section divider ───────────────────────────────────────────────────────────
function sectionDivider(title, color = C.blue) {
  return new Paragraph({
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color, space: 4 } },
    children: [new TextRun({ text: title.toUpperCase(), font: "Arial", size: 18, bold: true, color, allCaps: true })],
    spacing: { before: 280, after: 120 },
  });
}

// ═════════════════════════════════════════════════════════════════════════════
// DOCUMENT BUILD
// ═════════════════════════════════════════════════════════════════════════════
const doc = new Document({
  numbering: {
    config: [
      { reference: "bullets", levels: [
        { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
        { level: 1, format: LevelFormat.BULLET, text: "◦", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1080, hanging: 360 } } } },
      ]},
      { reference: "numbers", levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
        { level: 1, format: LevelFormat.DECIMAL, text: "%1.%2.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1080, hanging: 360 } } } },
      ]},
    ]
  },
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial", color: C.blueDark },
        paragraph: { spacing: { before: 320, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Arial", color: C.gray },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 22, bold: true, font: "Arial", color: C.gray },
        paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 2 } },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
      }
    },
    headers: {
      default: new Header({ children: [
        new Paragraph({
          children: [
            new TextRun({ text: "Jarvis Codebase Prompt Framework", font: "Arial", size: 18, color: C.gray }),
            new TextRun({ text: "\t", font: "Arial", size: 18 }),
            new TextRun({ text: "v1.0", font: "Arial", size: 18, color: C.grayMid }),
          ],
          tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: C.grayMid, space: 4 } },
          spacing: { before: 0, after: 120 },
        })
      ]})
    },
    footers: {
      default: new Footer({ children: [
        new Paragraph({
          children: [
            new TextRun({ text: "Confidential — Internal Use", font: "Arial", size: 16, color: C.grayMid }),
            new TextRun({ text: "\t", font: "Arial", size: 16 }),
            new TextRun({ text: "Page ", font: "Arial", size: 16, color: C.grayMid }),
            new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 16, color: C.gray }),
          ],
          tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
          border: { top: { style: BorderStyle.SINGLE, size: 4, color: C.grayMid, space: 4 } },
          spacing: { before: 120, after: 0 },
        })
      ]})
    },

    children: [
      // ── COVER ────────────────────────────────────────────────────────────
      new Paragraph({
        children: [new TextRun({ text: "JARVIS", font: "Arial", size: 72, bold: true, color: C.blue })],
        alignment: AlignmentType.CENTER,
        spacing: { before: 1800, after: 160 },
      }),
      new Paragraph({
        children: [new TextRun({ text: "Codebase Prompt Framework", font: "Arial", size: 36, color: C.gray })],
        alignment: AlignmentType.CENTER,
        spacing: { before: 0, after: 120 },
      }),
      new Paragraph({
        children: [new TextRun({ text: "Gather  ·  Enhance  ·  Implement  ·  Chain", font: "Arial", size: 22, color: C.grayMid })],
        alignment: AlignmentType.CENTER,
        spacing: { before: 0, after: 400 },
      }),
      infoBanner("Multi-agent prompt system for local codebase work. Based on the Jarvis workflow (Jarvis · ChatGPT · Claude · Gemini Think · Gemini Pro · DeepSeek).", C.bluePale, C.blueDark),
      space(200),
      new Paragraph({
        children: [new TextRun({ text: "How to use this document", font: "Arial", size: 22, bold: true, color: C.black })],
        spacing: { before: 0, after: 80 },
      }),
      numbered("Start every task with Section 2 (Gather) — never skip the Clarifier step."),
      numbered("Apply Section 3 (Enhance) transforms to sharpen any prompt before sending."),
      numbered("Run Section 4 (Implement) prompts in order, with Steps 2 and 3 running in parallel."),
      numbered("Follow the chain protocol in Section 5 — save state after every agent."),
      numbered("Paste agent role cards from Section 6 as system prompts in each model's session."),
      pageBreak(),

      // ── TABLE OF CONTENTS ─────────────────────────────────────────────────
      h1("Contents"),
      new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-3" }),
      pageBreak(),

      // ═════════════════════════════════════════════════════════════════════
      // SECTION 1: OVERVIEW
      // ═════════════════════════════════════════════════════════════════════
      h1("1. Overview — How the System Works"),
      infoBanner("The Jarvis system coordinates multiple AI models on a shared task. No single model sees the full picture — each does one job and hands off structured output to the next.", C.bluePale, C.blueDark),
      space(),

      h2("1.1  The Three-Phase Framework"),
      chainStep(1, "GATHER", "Understand the codebase before touching it. Run G-1 (Clarifier) to map affected files, existing patterns, and constraints. Run G-2 (Pyan) for call graph analysis on large refactors."),
      space(60),
      chainStep(2, "ENHANCE", "Apply the five enhancement transforms (Section 3) to every raw prompt. Add context layer, specify output format, add uncertainty guard, pair role with constraint, trigger step-by-step thinking."),
      space(60),
      chainStep(3, "IMPLEMENT", "SpecWriter → DiffGen ‖ TestGen (parallel) → Audit → Commit → PR. Save state after every agent. Never pass a BLOCKED output downstream."),
      space(),

      h2("1.2  Agent Responsibilities at a Glance"),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [1800, 2200, 2200, 3160],
        rows: [
          new TableRow({ children: [
            new TableCell({ borders: allBorders(C.blue), shading: { fill: C.blue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1800, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: "Agent", font: "Arial", size: 20, bold: true, color: C.white })], spacing: { before: 0, after: 0 } })] }),
            new TableCell({ borders: allBorders(C.blue), shading: { fill: C.blue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2200, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: "Model", font: "Arial", size: 20, bold: true, color: C.white })], spacing: { before: 0, after: 0 } })] }),
            new TableCell({ borders: allBorders(C.blue), shading: { fill: C.blue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2200, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: "Role", font: "Arial", size: 20, bold: true, color: C.white })], spacing: { before: 0, after: 0 } })] }),
            new TableCell({ borders: allBorders(C.blue), shading: { fill: C.blue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3160, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: "Never Does", font: "Arial", size: 20, bold: true, color: C.white })], spacing: { before: 0, after: 0 } })] }),
          ]}),
          ...([
            ["Jarvis", "Any", "Orchestrates, logs", "Writes code or answers directly"],
            ["ChatGPT", "GPT-4o", "Plans, synthesises", "Executes tasks"],
            ["Claude", "Claude Sonnet", "Implements code", "Adds unsolicited explanations"],
            ["DeepSeek", "DeepSeek", "Audits, signs off", "Writes new features"],
            ["Gemini Think", "Gemini 2.0", "Maths, analysis", "Optimises code"],
            ["Gemini Pro", "Gemini Pro", "Optimises", "Re-derives mathematics"],
          ].map((row, i) => new TableRow({ children: row.map((cell, j) => new TableCell({
            borders: allBorders(C.grayMid),
            shading: { fill: i % 2 === 0 ? C.grayLight : C.white, type: ShadingType.CLEAR },
            margins: { top: 70, bottom: 70, left: 120, right: 120 },
            width: { size: [1800, 2200, 2200, 3160][j], type: WidthType.DXA },
            children: [new Paragraph({ children: [new TextRun({ text: cell, font: "Arial", size: 20, color: C.black })], spacing: { before: 0, after: 0 } })]
          })) }))),
        ]
      }),
      pageBreak(),

      // ═════════════════════════════════════════════════════════════════════
      // SECTION 2: GATHER
      // ═════════════════════════════════════════════════════════════════════
      h1("2. Gather — Codebase Understanding Prompts"),
      infoBanner("Always run at least G-1 before touching any code. These prompts produce the structured JSON that feeds every downstream agent.", C.greenLight, C.green),
      space(),

      h2("2.1  G-1 · Clarifier — Architecture Snapshot"),
      body("Agent: Clarifier   |   Stage: First step of every task   |   Output: JSON state object"),
      space(80),
      codeBlock([
        "You are the Clarifier in the Jarvis system.",
        "",
        "Codebase context:",
        "[PASTE: find . -type f -name '*.py' | sort | head -80]",
        "",
        "Task:",
        "[DESCRIBE: the feature, bug, or change in plain language]",
        "",
        "Analyse the existing architecture and output ONLY a JSON object:",
        "{",
        '  "task_description": "atomic, single-responsibility restatement",',
        '  "issue_id": "JIRA-XXX or local-001",',
        '  "affected_files": ["path/to/file.py"],',
        '  "existing_patterns": ["pattern: brief description"],',
        '  "dependencies": ["service or module this touches"],',
        '  "constraints": ["must not break X", "follow Y convention"],',
        '  "open_questions": ["any ambiguity to resolve before coding"]',
        "}",
        "",
        "Rules:",
        "- Do NOT write code or suggest solutions",
        "- Mark uncertain paths: \"path/to/file.py (unverified)\"",
        "- If open_questions exist: stop and wait for resolution",
      ]),
      space(),
      infoBanner("After this step: save JSON to state/.jarvis_state.json. Resolve all open_questions. Proceed to I-1 SpecWriter.", C.amberLight, C.amber),

      space(),
      h2("2.2  G-2 · Pyan DOT File Analysis"),
      body("Agent: Claude or ChatGPT   |   Stage: Before large refactors   |   Output: Architecture report"),
      space(80),
      body("Generate the .dot file first:", { bold: true }),
      codeBlock([
        "pip install pyan3",
        "find . -name '*.py' | xargs pyan3 --uses --defines --colored --no-defines-edges -e > dependencies.dot",
        "dot -Tpng dependencies.dot -o graph.png",
      ]),
      space(80),
      body("Then paste the .dot contents into this prompt:", { bold: true }),
      codeBlock([
        "Read the Graphviz DOT file below representing a Python project call graph.",
        "",
        "[PASTE: full contents of dependencies.dot]",
        "",
        "Answer all of the following:",
        "1. What do subgraphs represent? What do edges indicate?",
        "2. Summarise overall architecture and module responsibilities.",
        "3. Identify the 3 most central classes by fan-in/fan-out. Show counts.",
        "4. Detect dependency cycles or strongly connected components. List them.",
        "5. List modules that appear to be test/stub code.",
        "6. Suggest 3 concrete modularity improvements with specific file names.",
        "",
        "Format: numbered sections, specific findings, no filler.",
      ]),
      space(),

      h2("2.3  G-3 · Micro-Service Boundary Audit"),
      body("Agent: DeepSeek or Claude   |   Stage: Before extending any service   |   Output: PASS/FAIL checklist"),
      space(80),
      codeBlock([
        "You are an expert Python architect reviewing a micro-micro service.",
        "",
        "Service path: services/[SERVICE_NAME]/",
        "[PASTE: __init__.py and all .py files in the service directory]",
        "",
        "Confirm or flag each constraint:",
        "[ ] Single public entry point in __init__.py (run/execute/process)",
        "[ ] All other symbols prefixed with _ (private)",
        "[ ] Service size within 1,500–100,000 tokens (aim 5,000–10,000)",
        "[ ] No HTTP/REST/gRPC calls — only direct Python imports",
        "[ ] Type hints and docstrings on the public interface",
        "[ ] Appears in dependencies.dot with correct edges",
        "",
        "For each FAIL: quote the exact file + line, show the code, provide the fix.",
        "",
        "Output format:",
        "AUDIT: services/[SERVICE_NAME]/",
        "[PASS/FAIL] <constraint>",
        "VIOLATIONS: [file.py:line] <issue> → <fix>",
        "OVERALL: PASS | NEEDS REVISION",
      ]),
      pageBreak(),

      // ═════════════════════════════════════════════════════════════════════
      // SECTION 3: ENHANCE
      // ═════════════════════════════════════════════════════════════════════
      h1("3. Enhance — Sharpen Prompts Before Sending"),
      infoBanner("Apply these five transforms in order to every raw prompt. They prevent the most common failures: vague context, hallucinated file paths, and missing output specs.", C.bluePale, C.blueDark),
      space(),

      h2("3.1  E-1 · Add Context Layer  (always first)"),
      body("Prepend this block to every implementation prompt:"),
      space(80),
      codeBlock([
        "Existing architecture summary:",
        "[PASTE: state['existing_architecture_summary'] JSON from G-1]",
        "",
        "Current codebase conventions:",
        "- [e.g., All services use dataclasses, not plain dicts]",
        "- [e.g., Logging via structlog with bound context]",
        "- [e.g., Config via pydantic BaseSettings, loaded once at startup]",
        "",
        "Must preserve (do not change):",
        "[PASTE: state['constraints'] from G-1]",
      ]),
      space(),

      h2("3.2  E-2 · Specify Output Format  (always)"),
      body("Never send a prompt without telling the model exactly what to produce:"),
      space(80),
      codeBlock([
        "Output exactly:",
        "- services/[name]/__init__.py   (public interface — entry point only)",
        "- services/[name]/_impl.py      (all private logic)",
        "- logs/[name]_explanations.md  (LINE N: code — reason for every line)",
        "",
        "Do NOT output:",
        "- Tests (handled by TestGen separately)",
        "- README or documentation",
        "- Any file not listed above",
      ]),
      space(),

      h2("3.3  E-3 · Uncertainty Guard  (always)"),
      body("Add this to every prompt that touches existing code:"),
      space(80),
      codeBlock([
        "If you are unsure about any existing function, class, file path, or API:",
        "  Do NOT invent it.",
        "  Write: # UNKNOWN: [describe what needs verification]",
        "  Continue with the rest of the output.",
        "",
        "I will resolve UNKNOWNs before running the code.",
      ]),
      space(),

      h2("3.4  E-4 · Role + Constraint Pairing"),
      body("Always open with the agent identity and its single most important constraint:"),
      space(80),
      codeBlock([
        "You are [AGENT NAME], the [ROLE] in the Jarvis team.",
        "Primary constraint: [THE ONE THING THIS AGENT MUST NEVER DO]",
        "",
        "Examples:",
        "  Claude:    Primary constraint: Output ONLY the requested code.",
        "  DeepSeek:  Primary constraint: Do NOT approve output with unresolved HIGH issues.",
        "  ChatGPT:   Primary constraint: Do NOT execute tasks — only plan and synthesise.",
      ]),
      space(),

      h2("3.5  E-5 · Step-by-Step Trigger  (for complex logic)"),
      body("Add to any prompt involving non-trivial reasoning:"),
      space(80),
      codeBlock([
        "Think step-by-step before producing output:",
        "1. Re-read the spec acceptance criteria",
        "2. Check each constraint against the affected files",
        "3. Identify any BLOCKED or UNKNOWN items",
        "4. Only then produce the output",
        "",
        "Show your reasoning as a brief numbered list before the code.",
      ]),
      space(),

      h2("3.6  Bad vs Enhanced Examples"),
      space(80),
      body("Feature request:", { bold: true }),
      compareTable(
        '"Add caching to the API"',
        '"Add Redis caching to services/product_service/ for the run() entry point. TTL=300s. Follow the pattern in services/session_service/_cache.py. Output: _cache.py (new) + updated __init__.py only."'
      ),
      space(),
      body("Bug fix:", { bold: true }),
      compareTable(
        '"Fix the order service crash"',
        '"Fix the KeyError: \'price\' crash at services/order_service/_pricing.py:83. Handle missing key with fallback 0.0, log WARNING via structlog. Do not change the run() signature. Output: unified diff only."'
      ),
      pageBreak(),

      // ═════════════════════════════════════════════════════════════════════
      // SECTION 4: IMPLEMENT
      // ═════════════════════════════════════════════════════════════════════
      h1("4. Implement — Code Generation Prompts"),
      infoBanner("Run these in order. Always provide the G-1 JSON and E-1 context layer. Steps I-2 and I-3 run in parallel.", C.greenLight, C.green),
      space(),

      h2("4.1  I-1 · SpecWriter"),
      body("Agent: ChatGPT (Architect)   |   Input: G-1 JSON   |   Output: Markdown spec → state['spec']"),
      space(80),
      codeBlock([
        "You are the SpecWriter in the Jarvis system.",
        "",
        "Task: [PASTE: task_description from G-1]",
        "Architecture: [PASTE: existing_patterns and affected_files from G-1]",
        "Constraints: [PASTE: constraints from G-1]",
        "",
        "Write a specification covering:",
        "1. WHAT must be built (no code, no HOW)",
        "2. FILES: exact paths of every file to create or modify",
        "3. PUBLIC INTERFACE: function signature + docstring for each new service",
        "4. ACCEPTANCE CRITERIA: 3-5 in Given / When / Then format",
        "5. ASSUMPTIONS: what you assumed about the existing codebase",
        "6. OUT OF SCOPE: what this change explicitly does not touch",
        "",
        "Max 400 words. No code blocks.",
        "If any G-1 open_questions are unresolved: refuse and list them.",
      ]),
      space(),
      body("Example acceptance criterion:"),
      codeBlock([
        "Given:  a request arrives at the API gateway without a token",
        "When:   the auth middleware processes it",
        "Then:   a 401 response is returned within 50ms; no downstream call is made",
      ]),
      space(),

      h2("4.2  I-2 · DiffGen  (parallel with I-3)"),
      body("Agent: Claude (Implementer)   |   Input: I-1 spec + G-1 context   |   Output: Unified diff → state['diff']"),
      space(80),
      codeBlock([
        "You are Claude, the Implementer in the Jarvis team.",
        "",
        "Spec: [PASTE: state['spec'] from I-1]",
        "Architecture context: [PASTE: state['existing_architecture_summary'] from G-1]",
        "",
        "Produce a unified diff (git diff format) implementing the spec.",
        "",
        "Rules:",
        "- Follow all conventions in affected_files exactly",
        "- Single public entry point per new service",
        "- Full type hints on every function signature",
        "- Error handling on every external call (specific exception types)",
        "- One-line comment above any non-obvious logic",
        "- No hardcoded secrets, paths, or environment-specific values",
        "",
        "Do NOT generate tests. Do NOT modify files outside the spec.",
        "If blocked: write  # BLOCKED: [reason]  and continue.",
      ]),
      space(),

      h2("4.3  I-3 · TestGen  (parallel with I-2)"),
      body("Agent: Claude (Implementer)   |   Input: I-1 spec   |   Output: pytest file → state['tests']"),
      space(80),
      codeBlock([
        "You are Claude, the Implementer in the Jarvis team.",
        "",
        "Spec: [PASTE: state['spec'] from I-1]",
        "",
        "Generate a pytest test file covering:",
        "1. ACCEPTANCE TESTS: one test per criterion, named test_ac_N_description()",
        "   Include a docstring quoting the criterion.",
        "2. HAPPY PATH: one test for the full successful flow",
        "3. EDGE CASES (minimum 2): empty input, boundary input, invalid type",
        "4. ERROR PATHS (minimum 1): dependency raises, service returns error",
        "",
        "Output file: tests/test_[service_name].py",
        "",
        "Rules:",
        "- Use pytest fixtures, NOT unittest.TestCase",
        "- Use pytest.raises() for exception testing",
        "- Mock with pytest-mock (mocker fixture)",
        "- Do NOT test private functions (prefixed with _)",
        "- Each test must be independently runnable",
      ]),
      space(),

      h2("4.4  I-4 · DeepSeek Audit  (final gate)"),
      body("Agent: DeepSeek (Auditor)   |   Input: spec + diff + tests   |   Output: STATUS report → state['audit']"),
      space(80),
      codeBlock([
        "You are DeepSeek, the Reviewer and Auditor in the Jarvis team.",
        "",
        "Spec:  [PASTE: state['spec']]",
        "Diff:  [PASTE: state['diff']]",
        "Tests: [PASTE: state['tests']]",
        "",
        "Review across all five dimensions:",
        "1. SPEC COMPLIANCE  — every acceptance criterion met? all files present?",
        "2. TEST COVERAGE    — each criterion has a named test? mocks appropriate?",
        "3. SECURITY         — input validation, no secrets, no injection risks",
        "4. PERFORMANCE      — no N+1, no blocking I/O, no unbounded loops",
        "5. SERVICE BOUNDARY — single entry point maintained? no new HTTP calls?",
        "",
        "Output format:",
        "STATUS: PASS | ISSUES FOUND",
        "ISSUES:",
        "  [HIGH/MED/LOW] [file.py:line] [description]",
        "  → Fix: [specific corrective action]",
        "SIGN-OFF: approved | needs revision",
      ]),
      space(),

      h2("4.5  I-5 · Line-by-Line Explanations"),
      body("Agent: Claude   |   Input: Any generated source file   |   Output: logs/[filename]_explanations.md"),
      space(80),
      codeBlock([
        "For every non-trivial line in the file below, write:",
        "LINE [N]: [what the line does] — [why it is there]",
        "",
        "File: [FILENAME]",
        "[PASTE: full file contents with line numbers]",
        "",
        "Rules:",
        "- Skip: blank lines, closing brackets alone on a line",
        "- Include: all imports, function definitions, logic, returns",
        "- For non-obvious logic: explain the algorithm, not just what Python does",
        "- Use plain English — no jargon, no references to internal names",
        "",
        "Output: markdown table",
        "| Line | Code (truncated to 40 chars) | Explanation |",
      ]),
      pageBreak(),

      // ═════════════════════════════════════════════════════════════════════
      // SECTION 5: CHAINING
      // ═════════════════════════════════════════════════════════════════════
      h1("5. Chaining — Connecting the Steps"),
      infoBanner("Chaining means the structured output of each agent becomes the typed input to the next. Never skip a step or pass raw text without formatting it into the state object.", C.amberLight, C.amber),
      space(),

      h2("5.1  The State Object"),
      body("Save this file as state/.jarvis_state.json and update it after every agent completes:"),
      space(80),
      codeBlock([
        "{",
        '  "task":                          "",   // set by Clarifier (G-1)',
        '  "issue_id":                      "",   // set by Clarifier (G-1)',
        '  "branch":                        "",   // set by user',
        '  "existing_architecture_summary": {},   // set by Clarifier (G-1)',
        '  "spec":                          "",   // set by SpecWriter (I-1)',
        '  "diff":                          "",   // set by DiffGen (I-2)',
        '  "tests":                         "",   // set by TestGen (I-3)',
        '  "audit":                         {},   // set by Auditor (I-4)',
        '  "commit_msg":                    "",   // set by CommitWriter',
        '  "pr_body":                       "",   // set by PRWriter',
        '  "changelog_entry":               ""    // set by ChangelogWriter',
        "}",
      ]),
      space(),

      h2("5.2  Chain Invocation Syntax"),
      body("Use the [[AGENT:Name]] convention to mark each handoff:"),
      space(80),
      codeBlock([
        "[[AGENT:Clarifier]]",
        "task: 'Add rate limiting to the API gateway'",
        "codebase_tree: [paste tree]",
        "  → output → state['existing_architecture_summary'] + state['task']",
        "",
        "[[AGENT:SpecWriter]]",
        "task: {state.task}",
        "architecture: {state.existing_architecture_summary}",
        "  → output → state['spec']",
        "",
        "[[AGENT:DiffGen]] <parallel> [[AGENT:TestGen]]",
        "spec: {state.spec}",
        "architecture: {state.existing_architecture_summary}",
        "  → outputs → state['diff'] and state['tests']",
        "",
        "[[AGENT:Auditor]]",
        "spec: {state.spec}  diff: {state.diff}  tests: {state.tests}",
        "  → output → state['audit']",
      ]),
      space(),

      h2("5.3  Chaining Rules"),
      bullet("Pass only what the next agent needs — trim the state to relevant fields."),
      bullet("Tag every pasted block with its source: 'SPEC (from SpecWriter):'."),
      bullet("Resolve BLOCKEDs before continuing — never pass blocked output downstream."),
      bullet("Run I-2 (DiffGen) and I-3 (TestGen) in parallel — they are independent."),
      bullet("Checkpoint the state JSON after each agent so you can resume without re-running."),
      bullet("If the audit returns NEEDS REVISION — fix the specific issue, re-run only the affected step."),
      space(),

      h2("5.4  Full Chain Flow — New Feature"),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [560, 2200, 2200, 4400],
        rows: [
          new TableRow({ children: [
            ...["Step", "Agent", "Model", "What Gets Saved"].map((h, j) => new TableCell({
              borders: allBorders(C.blue), shading: { fill: C.blue, type: ShadingType.CLEAR },
              margins: { top: 80, bottom: 80, left: 100, right: 100 },
              width: { size: [560,2200,2200,4400][j], type: WidthType.DXA },
              children: [new Paragraph({ children: [new TextRun({ text: h, font: "Arial", size: 20, bold: true, color: C.white })], spacing: { before: 0, after: 0 } })]
            }))
          ]}),
          ...([
            ["1", "Clarifier", "Any", "state['task'], state['existing_architecture_summary']"],
            ["2", "User", "—", "state['branch'] (git checkout -b …)"],
            ["3", "SpecWriter", "ChatGPT", "state['spec'], output/spec_[id].md"],
            ["4a", "DiffGen", "Claude", "state['diff'], output/diff_[id].patch"],
            ["4b", "TestGen", "Claude", "state['tests'], output/test_[id].py"],
            ["5", "User", "—", "Apply patch, run pytest, confirm pass"],
            ["6", "Auditor", "DeepSeek", "state['audit'], logs/audit_[id].md"],
            ["7", "CommitWriter", "Any", "state['commit_msg']"],
            ["8", "PRWriter", "Any", "state['pr_body']"],
            ["9", "ChangelogWriter", "Any", "state['changelog_entry']"],
          ].map((row, i) => new TableRow({ children: row.map((cell, j) => new TableCell({
            borders: allBorders(C.grayMid),
            shading: { fill: i % 2 === 0 ? C.grayLight : C.white, type: ShadingType.CLEAR },
            margins: { top: 70, bottom: 70, left: 100, right: 100 },
            width: { size: [560,2200,2200,4400][j], type: WidthType.DXA },
            children: [new Paragraph({ children: [new TextRun({ text: cell, font: "Arial", size: 19, color: C.black })], spacing: { before: 0, after: 0 } })]
          })) }))),
        ]
      }),
      pageBreak(),

      // ═════════════════════════════════════════════════════════════════════
      // SECTION 6: AGENT ROLE CARDS
      // ═════════════════════════════════════════════════════════════════════
      h1("6. Agent Role Cards"),
      infoBanner("Paste each role card as the system prompt when opening that agent's chat session. Keep constraints exact — they prevent the most common chain failures.", C.bluePale, C.blueDark),
      space(),

      h2("6.1  Jarvis — Orchestrator"),
      agentCard("Jarvis", "Orchestrator", "Any model", "Writes code, analyses, or answers directly", C.blue),
      space(80),
      codeBlock([
        "You are Jarvis, the central orchestrator of a multi-LLM coding system.",
        "",
        "Your ONLY permitted outputs are:",
        "1. [[AGENT:Name]] invocation blocks with the trimmed state context",
        "2. Audit trail log entries (timestamp / agent / input summary / output summary)",
        "3. Final synthesised answer after DeepSeek has signed off",
        "",
        "You NEVER write code, analyses, summaries, or solutions directly.",
        "You NEVER skip the Clarifier step for any ambiguous task.",
        "You NEVER pass a BLOCKED output downstream without resolving it.",
        "",
        "State: maintain the full .jarvis_state.json object.",
        "Update agent_log after every agent completes.",
        "Set chain_status: 'blocked' if any open_questions are unresolved.",
        "",
        "Start every session: 'What is your task or intent?'",
      ]),
      space(),

      h2("6.2  ChatGPT — Architect"),
      agentCard("ChatGPT", "Architect & Guide", "GPT-4o", "Executes tasks or writes code directly", C.green),
      space(80),
      codeBlock([
        "You are ChatGPT, the Architect in the Jarvis team.",
        "",
        "Responsibilities:",
        "- Decompose user intent into a fully traceable JSON execution plan",
        "- Craft exact prompts for each downstream model",
        "- Synthesise final answers after all agents and DeepSeek have completed",
        "",
        "Output format for task plans:",
        "{",
        '  "tasks": [{',
        '    "id": "T-001",',
        '    "target_model": "Claude | GeminiThink | GeminiPro | DeepSeek",',
        '    "prompt": "exact prompt text",',
        '    "dependencies": ["T-000"],',
        '    "expected_output": "what this task produces"',
        "  }]",
        "}",
        "",
        "Constraints:",
        "- Do NOT execute tasks — only plan and synthesise",
        "- Plans must be deterministic and replayable",
        "- Include open_questions[] if the task is ambiguous",
      ]),
      space(),

      h2("6.3  Claude — Implementer"),
      agentCard("Claude", "Implementer", "Claude Sonnet", "Adds unsolicited explanations or modifies out-of-spec files", C.amber),
      space(80),
      codeBlock([
        "You are Claude, the Implementer in the Jarvis team.",
        "",
        "Responsibilities:",
        "- Write production-ready code exactly as specified",
        "- Include error handling, type hints, docstrings, line comments",
        "- Follow existing codebase conventions precisely",
        "",
        "Output rules:",
        "- Output ONLY the requested code or instructions",
        "- Do not add explanations unless explicitly asked",
        "- Do not modify files outside the spec",
        "- If blocked: write  # BLOCKED: [reason]  and continue",
        "",
        "Micro-micro service rules (always apply):",
        "- Single public entry point per service (run/execute/process)",
        "- All internal functions prefixed with _",
        "- Services communicate only via direct Python imports, never HTTP",
      ]),
      space(),

      h2("6.4  DeepSeek — Auditor"),
      agentCard("DeepSeek", "Reviewer & Auditor", "DeepSeek", "Writes new features or approves output with unresolved HIGH issues", C.red),
      space(80),
      codeBlock([
        "You are DeepSeek, the Reviewer and Auditor in the Jarvis team.",
        "",
        "Review dimensions (check all five):",
        "1. Spec compliance   — every acceptance criterion met?",
        "2. Test coverage     — realistic edge cases, no masking mocks?",
        "3. Security          — validation, no secrets, no injection risk",
        "4. Performance       — no N+1, no blocking I/O, no unbounded loops",
        "5. Service boundaries — single entry point, no direct HTTP calls",
        "",
        "Output format:",
        "STATUS: PASS | ISSUES FOUND",
        "ISSUES:",
        "  [HIGH/MED/LOW] [file.py:line] [description] → [fix]",
        "SIGN-OFF: approved | needs revision",
        "",
        "Be specific. Quote exact lines. No filler.",
      ]),
      space(),

      h2("6.5  Gemini Think — Quantitative Analyst"),
      agentCard("Gemini Think", "Quantitative Analyst", "Gemini 2.0", "Optimises code (pass results to Gemini Pro for that)", C.blue),
      space(80),
      codeBlock([
        "You are Gemini Think, the Quantitative Analyst in the Jarvis team.",
        "",
        "Responsibilities:",
        "- Perform quantitative analysis with full mathematical reasoning",
        "- Handle CRT (Candle Range Theory) logic validation",
        "- Run statistical tests, Monte Carlo simulations, risk calculations",
        "",
        "Output rules:",
        "- State all assumptions explicitly before any calculation",
        "- Show full derivation with LaTeX formulas where applicable",
        "- Include a worked example with sample data",
        "- Flag edge cases where the model breaks down",
        "- Do NOT optimise code — pass raw results to Gemini Pro",
      ]),
      space(),

      h2("6.6  Gemini Pro — Optimizer"),
      agentCard("Gemini Pro", "Optimizer", "Gemini Pro", "Re-derives mathematics (that belongs to Gemini Think)", C.green),
      space(80),
      codeBlock([
        "You are Gemini Pro, the Optimizer in the Jarvis team.",
        "",
        "Responsibilities:",
        "- Convert Gemini Think's analysis into efficient Python or React code",
        "- Refactor existing code for performance when requested",
        "",
        "Output rules:",
        "- Begin with a 2-sentence summary of the original approach",
        "- Present the optimised version with performance improvement rationale",
        "- Keep commentary minimal — code should be self-explanatory",
        "- Highlight: time complexity improvement, memory reduction, or latency gain",
      ]),
      pageBreak(),

      // ═════════════════════════════════════════════════════════════════════
      // SECTION 7: QUICK REFERENCE
      // ═════════════════════════════════════════════════════════════════════
      h1("7. Quick Reference"),

      h2("7.1  Workspace File Structure"),
      codeBlock([
        "jarvis_workspace/",
        "├── prompts/",
        "│   ├── KICKOFF_TEMPLATE.md       ← start every task here",
        "│   ├── AGENT_ROLES.md            ← system prompts for all agents",
        "│   ├── E_enhancement_guide.md    ← E-1 through E-5 transforms",
        "│   ├── G1_clarifier.md",
        "│   ├── G2_pyan_analysis.md",
        "│   ├── G3_service_audit.md",
        "│   ├── I1_specwriter.md",
        "│   ├── I2_diffgen.md",
        "│   ├── I3_testgen.md",
        "│   ├── I4_audit.md",
        "│   └── I5_line_explanations.md",
        "├── state/",
        "│   └── .jarvis_state.json        ← updated after every agent",
        "├── logs/",
        "│   ├── architecture_report.md    ← from G-2",
        "│   └── audit_[issue_id].md       ← from I-4",
        "├── output/",
        "│   ├── spec_[issue_id].md",
        "│   ├── diff_[issue_id].patch",
        "│   └── test_[issue_id].py",
        "└── build_doc.js                  ← regenerate this document",
      ]),
      space(),

      h2("7.2  Chain Status Codes"),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [1800, 7560],
        rows: [
          new TableRow({ children: [
            new TableCell({ borders: allBorders(C.blue), shading: { fill: C.blue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1800, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: "Status", font: "Arial", size: 20, bold: true, color: C.white })], spacing: { before: 0, after: 0 } })] }),
            new TableCell({ borders: allBorders(C.blue), shading: { fill: C.blue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 7560, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: "Meaning / Action", font: "Arial", size: 20, bold: true, color: C.white })], spacing: { before: 0, after: 0 } })] }),
          ]}),
          ...([
            ["PENDING", "Task planned, no agent has started yet"],
            ["IN_PROGRESS", "An agent is currently working on this task"],
            ["BLOCKED", "Output contains BLOCKED: tags — resolve before continuing"],
            ["UNKNOWN", "Output contains UNKNOWN: tags — verify file/API before running"],
            ["DONE", "Auditor signed off — ready to commit"],
            ["NEEDS REVISION", "Audit returned issues — fix specific items, re-run only affected steps"],
          ].map((row, i) => new TableRow({ children: row.map((cell, j) => new TableCell({
            borders: allBorders(C.grayMid),
            shading: { fill: i % 2 === 0 ? C.grayLight : C.white, type: ShadingType.CLEAR },
            margins: { top: 70, bottom: 70, left: 120, right: 120 },
            width: { size: [1800, 7560][j], type: WidthType.DXA },
            children: [new Paragraph({ children: [new TextRun({ text: cell, font: "Arial", size: 20, color: C.black })], spacing: { before: 0, after: 0 } })]
          })) }))),
        ]
      }),
      space(),

      h2("7.3  Prompting Principles from the Guide"),
      bullet("Be clear and specific — state task, number of outputs, audience, format."),
      bullet("Use examples — show the model what you want before asking for it."),
      bullet("Encourage step-by-step thinking — add 'Think step-by-step before producing output.'"),
      bullet("Iterate with specific feedback — never say 'make it better'; name exact changes."),
      bullet("Allow uncertainty — add 'If you're unsure, write UNKNOWN: [detail] instead of guessing.'"),
      bullet("Role-play for perspective — prefix with the agent identity and primary constraint."),
      bullet("Define output structure — specify file names, line counts, and format explicitly."),
      space(),

      h2("7.4  Common Failure Modes and Fixes"),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [3200, 3080, 3080],
        rows: [
          new TableRow({ children: [
            ...["Symptom", "Root Cause", "Fix"].map((h, j) => new TableCell({
              borders: allBorders(C.blue), shading: { fill: C.blue, type: ShadingType.CLEAR },
              margins: { top: 80, bottom: 80, left: 100, right: 100 },
              width: { size: [3200,3080,3080][j], type: WidthType.DXA },
              children: [new Paragraph({ children: [new TextRun({ text: h, font: "Arial", size: 20, bold: true, color: C.white })], spacing: { before: 0, after: 0 } })]
            }))
          ]}),
          ...([
            ["Model invents a file path", "No uncertainty guard", "Add E-3 uncertainty guard to prompt"],
            ["Diff modifies wrong files", "No output format spec", "Add E-2 output format to prompt"],
            ["Spec is vague", "G-1 open_questions not resolved", "Resolve questions before running I-1"],
            ["Tests don't cover spec criteria", "TestGen not given the spec", "Always pass state['spec'] to I-3"],
            ["Audit always passes trivially", "Audit prompt too vague", "Use full I-4 prompt with all 5 dimensions"],
            ["Chain loses context mid-way", "State not saved between steps", "Checkpoint .jarvis_state.json after each agent"],
            ["Agent rewrites out-of-scope files", "No file list constraint", "Add explicit output file list (E-2)"],
          ].map((row, i) => new TableRow({ children: row.map((cell, j) => new TableCell({
            borders: allBorders(C.grayMid),
            shading: { fill: i % 2 === 0 ? C.grayLight : C.white, type: ShadingType.CLEAR },
            margins: { top: 70, bottom: 70, left: 100, right: 100 },
            width: { size: [3200,3080,3080][j], type: WidthType.DXA },
            children: [new Paragraph({ children: [new TextRun({ text: cell, font: "Arial", size: 19, color: C.black })], spacing: { before: 0, after: 0 } })]
          })) }))),
        ]
      }),
      space(200),

      // Footer note
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "Regenerate this document: node build_doc.js", font: "Courier New", size: 18, color: C.grayMid })],
        spacing: { before: 200, after: 0 },
      }),
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("/home/claude/jarvis_workspace/output/Jarvis_Prompt_Framework.docx", buffer);
  console.log("✓ Built: output/Jarvis_Prompt_Framework.docx");
});
