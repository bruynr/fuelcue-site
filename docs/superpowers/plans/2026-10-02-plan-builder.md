# Plan Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `/plan/` page on fuelsteps.com (6 languages) where a runner clicks a fuel schedule together and copies the 10 Garmin Connect field values, plus a settings-format reference that humans and AI assistants can read, plus Umami events.

**Architecture:** Static site built by `build.py` from `i18n/<lang>.json` (existing pattern: one Python f-string template per page type). The builder is vanilla JS: `plan-core.js` holds pure functions (parse, format, validate, moments, fields, templates) as an ES module that both the browser and `node --test` import; `plan.js` is the DOM layer that renders state, copies to the clipboard, persists to `localStorage` and sends Umami events. `build.py` injects the translated UI strings into the page as a JSON block, so the scripts are language-neutral.

**Tech Stack:** Python 3.12 (`build.py`, Pillow), vanilla ES modules, Node 22 (`node --test`, no npm packages), GitHub Pages via `.github/workflows/pages.yml`, Umami Cloud, playwright-cli for manual checks.

**Spec:** `docs/superpowers/specs/2026-10-02-plan-builder-design.md`

## Global Constraints

- Repo `bruynr/fuelsteps-site`, branch `feature/plan-builder`; deploy branch is `gh-pages` (never commit there directly). Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Source of truth for the step syntax is `ScheduleParser.mc` in the app repo (`D:\Projects\Prive\FuelSteps\app\source\ScheduleParser.mc`): repeat 1–30, whole numbers 1–4 digits, decimal with one `.` or `,` (max 8 chars), min size 0.5 km / 5 min, running total max 100 km / 600 min, `0` only as step 1 without repeat, carbs `25` or `25g`, `caf` any case, default text `Gel`, text = all tokens between size and carbs/caf.
- Garmin Connect limits: name max 16 characters, step field max 40 characters, unused step fields contain `-`, never empty.
- All six `i18n/*.json` files have the same keys. Menu names per language come from `D:\Projects\Prive\FuelSteps\app\STORE.md` (SETUP section of each language).
- No framework, no npm, no cookies, no personal data in events. Generated files (`index.html`, `<lang>/`, `plan/`, `<lang>/plan/`, `llms*.txt`, `sitemap.xml`) are build output and in `.gitignore`.
- Files written by the Write tool get CRLF; `build.py` writes LF. Keep `plan-core.js`/`plan.js` LF-agnostic (no CR-sensitive code).
- Umami website id: `458f80aa-006c-4354-9a7b-8bdda8850cbd`, script `https://cloud.umami.is/script.js`.

## Review Focus

1. Text that ends in a number or in the word `caf` (`5 Maurten 100`, `5 Gel caf 25`): the field must still round-trip or the UI must warn (test in Task 2: `roundtrip warning`).
2. Decimal input with a comma in a `<input type=number>` on a Dutch/German browser: the state must hold a Number, never a string (test in Task 2: `formatStep` with 7.5; Task 5 parses `input.valueAsNumber`).
3. A schedule whose running total exceeds the maximum only through repeats (`30x5` km): the error must point at that step (test in Task 2: `total_max`).
4. Copying when `navigator.clipboard` is unavailable (http, old browser): the button must fall back to selecting the text, not throw (Task 5: `copyText` fallback).
5. A reload with corrupt or old `localStorage` JSON: the page must fall back to the default template (test in Task 2: `fromJSON` returns null on garbage; Task 5 uses it).

---

### Task 1: Core parser and formatter (`plan-core.js`)

**Files:**
- Create: `plan-core.js`
- Create: `plan-core.test.js`

**Interfaces:**
- Produces:
  - `LIMITS = { km: {min: 0.5, max: 100, step: 0.5}, min: {min: 5, max: 600, step: 5}, repeatMax: 30, nameMax: 16, fieldMax: 40, maxSteps: 8, carbsMax: 9999 }`
  - `parseStepText(raw: string) → {size: number, repeat: number, text: string, carbs: number, caf: boolean} | null`
  - `formatStep(step) → string`, e.g. `{size: 5, repeat: 3, text: "Gel", carbs: 25, caf: true}` → `"3x5 Gel 25 caf"`

- [ ] **Step 1: Write the failing tests**

```js
// plan-core.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { parseStepText, formatStep, LIMITS } from "./plan-core.js";

const step = (size, repeat, text, carbs, caf) => ({ size, repeat, text, carbs, caf });

test("parse plain", () => {
  assert.deepEqual(parseStepText("30 Gel 25"), step(30, 1, "Gel", 25, false));
});

test("parse repeat and caf, any case", () => {
  assert.deepEqual(parseStepText("3x5 Gel 25 caf"), step(5, 3, "Gel", 25, true));
  assert.deepEqual(parseStepText("2X10 Iso 15"), step(10, 2, "Iso", 15, false));
  assert.deepEqual(parseStepText("30 gel 25 CAF"), step(30, 1, "gel", 25, true));
});

test("parse decimals with . and ,", () => {
  assert.equal(parseStepText("7,5 Gel 25").size, 7.5);
  assert.deepEqual(parseStepText("4x7.5 Gel 25"), step(7.5, 4, "Gel", 25, false));
});

test("parse defaults", () => {
  assert.deepEqual(parseStepText("30"), step(30, 1, "Gel", 0, false));
  assert.deepEqual(parseStepText("30 Water"), step(30, 1, "Water", 0, false));
  assert.deepEqual(parseStepText("5 25"), step(5, 1, "Gel", 25, false));
  assert.deepEqual(parseStepText("5 caf"), step(5, 1, "Gel", 0, true));
});

test("parse gram suffix and multi-word text", () => {
  assert.deepEqual(parseStepText("30 Dextro 20g"), step(30, 1, "Dextro", 20, false));
  assert.deepEqual(parseStepText("30 Peanut bar 25"), step(30, 1, "Peanut bar", 25, false));
  assert.deepEqual(parseStepText("5 Gel CAF 25 caf"), step(5, 1, "Gel CAF", 25, true));
});

test("parse is whitespace tolerant and accepts 0", () => {
  assert.deepEqual(parseStepText("  6x30   Gel  25 "), step(30, 6, "Gel", 25, false));
  assert.deepEqual(parseStepText("0 Gel 25"), step(0, 1, "Gel", 25, false));
});

test("parse rejects invalid input", () => {
  for (const bad of ["", "   ", "abc", "x30", "3x", "3,5x30 Gel", "3x5x2 Gel", "1.2.3 Gel", "-", null, undefined, 5]) {
    assert.equal(parseStepText(bad), null, JSON.stringify(bad));
  }
});

test("format writes the canonical line", () => {
  assert.equal(formatStep(step(5, 3, "Gel", 25, true)), "3x5 Gel 25 caf");
  assert.equal(formatStep(step(30, 1, "Gel", 25, false)), "30 Gel 25");
  assert.equal(formatStep(step(7.5, 1, "Water", 0, false)), "7.5 Water");
  assert.equal(formatStep(step(0, 1, "Gel", 25, false)), "0 Gel 25");
  assert.equal(formatStep(step(5, 1, "", 25, false)), "5 Gel 25");
  assert.equal(formatStep(step(5, 1, "  Peanut   bar ", 25, false)), "5 Peanut bar 25");
});

test("format and parse round-trip", () => {
  for (const s of [step(5, 3, "Gel", 25, true), step(7.5, 1, "Dextro", 15, false), step(0, 1, "Gel", 25, false), step(30, 6, "Gel CAF", 25, true)]) {
    assert.deepEqual(parseStepText(formatStep(s)), s);
  }
});

test("limits", () => {
  assert.equal(LIMITS.km.min, 0.5);
  assert.equal(LIMITS.min.max, 600);
  assert.equal(LIMITS.repeatMax, 30);
  assert.equal(LIMITS.fieldMax, 40);
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run (from the site repo root): `node --test`
Expected: FAIL, `ERR_MODULE_NOT_FOUND` for `./plan-core.js`

- [ ] **Step 3: Write the implementation**

```js
// plan-core.js — pure logic for the plan builder, mirrors ScheduleParser.mc in the app repo.
// Imported by plan.js (browser) and plan-core.test.js (node --test). No DOM, no I/O.

export const LIMITS = {
  km: { min: 0.5, max: 100, step: 0.5 },
  min: { min: 5, max: 600, step: 5 },
  repeatMax: 30, nameMax: 16, fieldMax: 40, maxSteps: 8, carbsMax: 9999,
};
export const DEFAULT_TEXT = "Gel";

// digits only, 1-4 of them (ScheduleParser.parseWhole)
function parseWhole(s) {
  return /^[0-9]{1,4}$/.test(s) ? Number(s) : null;
}

// digits with at most one . or , (ScheduleParser.parseDecimal), max 8 chars, at least one digit
function parseDecimal(s) {
  if (s.length < 1 || s.length > 8 || !/^[0-9.,]*$/.test(s) || !/[0-9]/.test(s)) return null;
  if ((s.match(/[.,]/g) || []).length > 1) return null;
  return Number(s.replace(",", "."));
}

// "25" or "25g" → 25 (ScheduleParser.parseCarbs)
function parseCarbs(s) {
  if (s.length > 1 && /[gG]$/.test(s)) return parseWhole(s.slice(0, -1));
  return parseWhole(s);
}

// "[repeat]x size [text] [carbs[g]] [caf]" → step or null
export function parseStepText(raw) {
  if (typeof raw !== "string") return null;
  const tokens = raw.split(/[ \t\r\n]+/).filter(Boolean);
  if (tokens.length === 0) return null;
  const first = tokens[0];
  let repeat = 1;
  let sizeText = first;
  const xs = first.match(/[xX]/g) || [];
  if (xs.length > 1) return null;
  if (xs.length === 1) {
    const pos = first.search(/[xX]/);
    repeat = parseWhole(first.slice(0, pos));
    if (repeat === null) return null;
    sizeText = first.slice(pos + 1);
  }
  const size = parseDecimal(sizeText);
  if (size === null) return null;
  let last = tokens.length - 1; // consumed from the back: caf, then carbs
  let caf = false;
  if (last >= 1 && tokens[last].toLowerCase() === "caf") { caf = true; last--; }
  let carbs = 0;
  if (last >= 1) {
    const c = parseCarbs(tokens[last]);
    if (c !== null) { carbs = c; last--; }
  }
  const text = tokens.slice(1, last + 1).join(" ") || DEFAULT_TEXT;
  return { size, repeat, text, carbs, caf };
}

function num(n) {
  return String(Math.round(n * 100) / 100); // 7.5 → "7.5", 5 → "5"
}

// step → canonical field text: repeat omitted when 1, carbs omitted when 0, text always written
export function formatStep(step) {
  const text = String(step.text || "").trim().split(/\s+/).filter(Boolean).join(" ") || DEFAULT_TEXT;
  const parts = [(step.repeat > 1 ? step.repeat + "x" : "") + num(step.size), text];
  if (step.carbs > 0) parts.push(String(step.carbs));
  if (step.caf) parts.push("caf");
  return parts.join(" ");
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `node --test`
Expected: all tests in `plan-core.test.js` PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add plan-core.js plan-core.test.js
git commit -m "Plan builder core: parse and format step text (mirrors ScheduleParser.mc)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Core validation, moments, fields, templates, (de)serialization

**Files:**
- Modify: `plan-core.js`
- Modify: `plan-core.test.js`

**Interfaces:**
- Consumes: `LIMITS`, `parseStepText`, `formatStep` from Task 1.
- Produces:
  - `Schedule = { name: string, unit: "km" | "min", steps: Step[] }`
  - `TEMPLATES: { id: string, schedule: Schedule }[]` with ids `gel5`, `marathon7`, `time30`
  - `validate(schedule) → { ok: boolean, name: string | null, steps: (string | null)[], warnings: (string | null)[] }`; error codes: `name_empty`, `name_long`, `no_steps`, `repeat`, `size_min`, `zero_first`, `total_max`, `carbs`, `field_long`; warning code: `roundtrip`
  - `fields(schedule) → { name: string, unit: "km" | "min", steps: string[] }` with `steps.length === 8`, unused = `"-"`
  - `moments(schedule) → { rows: {at: number, label: string, carbs: number, caf: boolean, before: boolean}[], totalCarbs: number, count: number, cafCount: number, perHour: number | null }`
  - `fromJSON(text: string | null) → Schedule | null` (null on anything that is not a plausible schedule)
  - `newStep() → Step` = `{size: 5, repeat: 1, text: "Gel", carbs: 25, caf: false}`

- [ ] **Step 1: Write the failing tests**

Append to `plan-core.test.js` (extend the import line to include the new names):

```js
import { parseStepText, formatStep, LIMITS, TEMPLATES, validate, fields, moments, fromJSON, newStep } from "./plan-core.js";

const sched = (unit, steps, name = "Test") => ({ name, unit, steps });

test("templates are valid and have the agreed content", () => {
  assert.deepEqual(TEMPLATES.map(t => t.id), ["gel5", "marathon7", "time30"]);
  for (const t of TEMPLATES) assert.equal(validate(t.schedule).ok, true, t.id);
  assert.deepEqual(fields(TEMPLATES[0].schedule), { name: "Gel 5 km", unit: "km", steps: ["3x5 Gel 25 caf", "-", "-", "-", "-", "-", "-", "-"] });
  assert.deepEqual(fields(TEMPLATES[1].schedule).steps.slice(0, 5), ["0 Gel 25", "7 Gel 25", "7 Dextro 15", "7 Gel CAF 25 caf", "2x7 Gel 25"]);
  assert.deepEqual(fields(TEMPLATES[2].schedule), { name: "Every 30 min", unit: "min", steps: ["6x30 Gel 25", "-", "-", "-", "-", "-", "-", "-"] });
});

test("validate: ok schedule", () => {
  const v = validate(sched("km", [step(0, 1, "Gel", 25, false), step(5, 3, "Gel", 25, true)]));
  assert.deepEqual(v, { ok: true, name: null, steps: [null, null], warnings: [null, null] });
});

test("validate: name", () => {
  assert.equal(validate(sched("km", [step(5, 1, "Gel", 25, false)], "")).name, "name_empty");
  assert.equal(validate(sched("km", [step(5, 1, "Gel", 25, false)], "   ")).name, "name_empty");
  assert.equal(validate(sched("km", [step(5, 1, "Gel", 25, false)], "12345678901234567")).name, "name_long");
  assert.equal(validate(sched("km", [step(5, 1, "Gel", 25, false)], "1234567890123456")).name, null);
});

test("validate: steps", () => {
  assert.equal(validate(sched("km", [])).steps.length, 0);
  assert.equal(validate(sched("km", [])).ok, false);
  assert.equal(validate(sched("km", [step(5, 0, "Gel", 25, false)])).steps[0], "repeat");
  assert.equal(validate(sched("km", [step(5, 31, "Gel", 25, false)])).steps[0], "repeat");
  assert.equal(validate(sched("km", [step(5, 1.5, "Gel", 25, false)])).steps[0], "repeat");
  assert.equal(validate(sched("km", [step(0.4, 1, "Gel", 25, false)])).steps[0], "size_min");
  assert.equal(validate(sched("min", [step(4, 1, "Gel", 25, false)])).steps[0], "size_min");
  assert.equal(validate(sched("km", [step(5, 1, "Gel", 25, false), step(0, 1, "Gel", 25, false)])).steps[1], "zero_first");
  assert.equal(validate(sched("km", [step(0, 2, "Gel", 25, false)])).steps[0], "zero_first");
  assert.equal(validate(sched("km", [step(5, 30, "Gel", 25, false)])).steps[0], "total_max"); // 150 km through repeats
  assert.equal(validate(sched("km", [step(50, 1, "Gel", 25, false), step(50, 1, "Gel", 25, false)])).steps[1], null); // exactly 100
  assert.equal(validate(sched("min", [step(600, 1, "Gel", 25, false), step(5, 1, "Gel", 25, false)])).steps[1], "total_max");
  assert.equal(validate(sched("km", [step(5, 1, "Gel", -1, false)])).steps[0], "carbs");
  assert.equal(validate(sched("km", [step(5, 1, "Gel", 10000, false)])).steps[0], "carbs");
  assert.equal(validate(sched("km", [step(5, 1, "Gel", 2.5, false)])).steps[0], "carbs");
  assert.equal(validate(sched("km", [step(5, 1, "A".repeat(40), 25, false)])).steps[0], "field_long");
  assert.equal(validate(sched("km", [step(5, 1, NaN, 25, false)])).steps[0], null); // text falls back to Gel
  assert.equal(validate(sched("km", [step(NaN, 1, "Gel", 25, false)])).steps[0], "size_min");
});

test("validate: roundtrip warning when the text would be read differently", () => {
  const v = validate(sched("km", [step(5, 1, "Maurten 100", 0, false), step(5, 1, "Gel caf", 25, false), step(5, 1, "Gel", 25, false)]));
  assert.deepEqual(v.warnings, ["roundtrip", "roundtrip", null]);
  assert.equal(v.ok, true); // warnings do not block
});

test("fields: 10 values, dash for unused, trimmed name", () => {
  const f = fields(sched("min", [step(30, 1, "Gel", 25, false)], "  Long run "));
  assert.equal(f.name, "Long run");
  assert.equal(f.unit, "min");
  assert.deepEqual(f.steps, ["30 Gel 25", "-", "-", "-", "-", "-", "-", "-"]);
});

test("moments: cumulative positions, numbering, totals", () => {
  const m = moments(sched("km", [step(0, 1, "Gel", 25, false), step(10, 1, "Gel", 25, false), step(5, 3, "Gel", 25, false), step(5, 1, "Gel CAF", 25, true)]));
  assert.deepEqual(m.rows.map(r => [r.at, r.label, r.carbs, r.caf, r.before]), [
    [0, "Gel", 25, false, true],
    [10, "Gel", 25, false, false],
    [15, "Gel #1", 25, false, false],
    [20, "Gel #2", 25, false, false],
    [25, "Gel #3", 25, false, false],
    [30, "Gel CAF", 25, true, false],
  ]);
  assert.equal(m.totalCarbs, 150);
  assert.equal(m.count, 6);
  assert.equal(m.cafCount, 1);
  assert.equal(m.perHour, null);
});

test("moments: per hour on time schedules, decimals stay exact", () => {
  const m = moments(sched("min", [step(30, 6, "Gel", 25, false)]));
  assert.equal(m.rows[5].at, 180);
  assert.equal(m.perHour, 50);
  const k = moments(sched("km", [step(7.5, 2, "Gel", 20, false)]));
  assert.deepEqual(k.rows.map(r => r.at), [7.5, 15]);
  assert.equal(moments(sched("min", [])).perHour, null);
});

test("fromJSON: accepts a schedule, rejects garbage", () => {
  const s = sched("km", [step(5, 3, "Gel", 25, true)], "Gel 5 km");
  assert.deepEqual(fromJSON(JSON.stringify(s)), s);
  for (const bad of [null, "", "nope", "{}", "[]", JSON.stringify({ name: "x", unit: "mi", steps: [] }), JSON.stringify({ name: "x", unit: "km", steps: "no" }), JSON.stringify({ name: 1, unit: "km", steps: [] })]) {
    assert.equal(fromJSON(bad), null, String(bad));
  }
  const nine = fromJSON(JSON.stringify(sched("km", Array(9).fill(step(5, 1, "Gel", 25, false)))));
  assert.equal(nine.steps.length, 8);
  const loose = fromJSON(JSON.stringify({ name: "x", unit: "km", steps: [{ size: "5", repeat: "2", text: 7, carbs: "25", caf: 1 }] }));
  assert.deepEqual(loose.steps[0], step(5, 2, "7", 25, true));
});

test("newStep", () => {
  assert.deepEqual(newStep(), { size: 5, repeat: 1, text: "Gel", carbs: 25, caf: false });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `node --test`
Expected: FAIL with `SyntaxError: The requested module './plan-core.js' does not provide an export named 'TEMPLATES'`

- [ ] **Step 3: Write the implementation**

Append to `plan-core.js`:

```js
const mk = (size, repeat, text, carbs, caf) => ({ size, repeat, text, carbs, caf });

export function newStep() {
  return mk(5, 1, DEFAULT_TEXT, 25, false);
}

export const TEMPLATES = [
  { id: "gel5", schedule: { name: "Gel 5 km", unit: "km", steps: [mk(5, 3, "Gel", 25, true)] } },
  { id: "marathon7", schedule: { name: "Marathon", unit: "km", steps: [
    mk(0, 1, "Gel", 25, false), mk(7, 1, "Gel", 25, false), mk(7, 1, "Dextro", 15, false), mk(7, 1, "Gel CAF", 25, true), mk(7, 2, "Gel", 25, false),
  ] } },
  { id: "time30", schedule: { name: "Every 30 min", unit: "min", steps: [mk(30, 6, "Gel", 25, false)] } },
];

const isInt = (n) => Number.isInteger(n);

// same rules as ScheduleParser.parse/parseStep plus the Garmin Connect field limits
export function validate(schedule) {
  const lim = LIMITS[schedule.unit];
  const name = String(schedule.name ?? "").trim();
  const nameErr = name.length === 0 ? "name_empty" : name.length > LIMITS.nameMax ? "name_long" : null;
  const steps = [];
  const warnings = [];
  let total = 0;
  schedule.steps.forEach((s, i) => {
    let err = null;
    const size = Number(s.size);
    if (!isInt(s.repeat) || s.repeat < 1 || s.repeat > LIMITS.repeatMax) err = "repeat";
    else if (size === 0 && (i > 0 || s.repeat > 1)) err = "zero_first";
    else if (size !== 0 && !(size >= lim.min)) err = "size_min";
    else if (!isInt(s.carbs) || s.carbs < 0 || s.carbs > LIMITS.carbsMax) err = "carbs";
    else if (formatStep(s).length > LIMITS.fieldMax) err = "field_long";
    if (!err) {
      total += size * s.repeat;
      if (total > lim.max) err = "total_max";
    }
    steps.push(err);
    let warn = null;
    if (!err) {
      const back = parseStepText(formatStep(s));
      const norm = String(s.text || "").trim().split(/\s+/).filter(Boolean).join(" ") || DEFAULT_TEXT;
      // the watch would read the text differently (last word eaten as carbs, or as the caf flag)
      if (!back || back.text !== norm || back.carbs !== s.carbs || back.caf !== !!s.caf) warn = "roundtrip";
    }
    warnings.push(warn);
  });
  const ok = !nameErr && schedule.steps.length > 0 && steps.every(e => e === null);
  return { ok, name: nameErr, steps, warnings };
}

// the 10 Garmin Connect fields: name, unit, step 1-8 ("-" when unused)
export function fields(schedule) {
  const steps = schedule.steps.slice(0, LIMITS.maxSteps).map(formatStep);
  while (steps.length < LIMITS.maxSteps) steps.push("-");
  return { name: String(schedule.name ?? "").trim(), unit: schedule.unit, steps };
}

// every alert moment with its cumulative position; "#n" numbering inside a repeated step
export function moments(schedule) {
  const rows = [];
  let at = 0, totalCarbs = 0, cafCount = 0;
  schedule.steps.forEach((s, i) => {
    const text = String(s.text || "").trim().split(/\s+/).filter(Boolean).join(" ") || DEFAULT_TEXT;
    for (let n = 1; n <= s.repeat; n++) {
      at = Math.round((at + Number(s.size)) * 1000) / 1000;
      rows.push({ at, label: s.repeat > 1 ? `${text} #${n}` : text, carbs: s.carbs, caf: !!s.caf, before: i === 0 && Number(s.size) === 0 });
      totalCarbs += s.carbs;
      if (s.caf) cafCount++;
    }
  });
  const perHour = schedule.unit === "min" && at > 0 ? Math.round(totalCarbs / (at / 60) * 10) / 10 : null;
  return { rows, totalCarbs, count: rows.length, cafCount, perHour };
}

// localStorage → schedule; null unless it looks like one (max 8 steps, coerced numbers)
export function fromJSON(text) {
  let o;
  try { o = JSON.parse(text); } catch { return null; }
  if (!o || typeof o !== "object" || Array.isArray(o)) return null;
  if (typeof o.name !== "string" || !(o.unit in LIMITS) || !Array.isArray(o.steps)) return null;
  const steps = o.steps.slice(0, LIMITS.maxSteps).map(s => mk(Number(s?.size), Number(s?.repeat), String(s?.text ?? DEFAULT_TEXT), Number(s?.carbs), Boolean(s?.caf)));
  return { name: o.name, unit: o.unit, steps };
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `node --test`
Expected: PASS, 20 tests.

- [ ] **Step 5: Commit**

```bash
git add plan-core.js plan-core.test.js
git commit -m "Plan builder core: validation, moments, fields, templates, storage parsing

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Umami replaces Cloudflare Web Analytics; `node --test` in the deploy workflow

**Files:**
- Modify: `build.py:61-63` (ANALYTICS)
- Modify: `.github/workflows/pages.yml:26-30`
- Modify: `README.md`

**Interfaces:**
- Produces: `UMAMI_ID` constant; `ANALYTICS` holds only the Umami tag (Cloudflare beacon removed: Umami also counts page views, referrers and countries, so a second tracker adds nothing). Already used by `page()` and `not_found()`; `plan()` in Task 4 uses it too.

- [ ] **Step 1: Replace the Cloudflare beacon with the Umami tag**

Replace lines 62–63 of `build.py` with:

```python
# Umami Cloud: page views, referrers, countries and the builder events; cookieless, no personal data, so no consent banner
UMAMI_ID = "458f80aa-006c-4354-9a7b-8bdda8850cbd"
ANALYTICS = f'<script defer src="https://cloud.umami.is/script.js" data-website-id="{UMAMI_ID}"></script>'
```

- [ ] **Step 2: Build and check**

Run: `python build.py` then `Select-String -Path index.html,nl/index.html,404.html -Pattern "umami" | Measure-Object` and `Select-String -Path index.html -Pattern "cloudflareinsights"`
Expected: `build.py` prints `built: en, nl, de, fr, es, it`; the count is 3 (one per file); the Cloudflare search finds nothing.

- [ ] **Step 3: Add the Node test step to the workflow**

In `.github/workflows/pages.yml`, after the `pip install pillow` step and before `python build.py`, insert:

```yaml
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
      - run: node --test
```

- [ ] **Step 4: Document in README.md**

Replace the "Build:" bullet's first sentence so it mentions the plan page, and add a test bullet. New README body between the first paragraph and the donate line:

```markdown
- Texts: `i18n/<lang>.json` (en, nl, de, fr, es, it); all files have the same keys
- Pages: home (`/`, `/<lang>/`) and the plan builder (`/plan/`, `/<lang>/plan/`: `plan.js` + `plan-core.js`, settings format reference, Umami events)
- Build: `python build.py` (needs Pillow: `pip install pillow`) → `index.html` (en), `<lang>/index.html`, `plan/index.html`, `<lang>/plan/index.html`, WebP images and icons in `img/web/`, `manifest.webmanifest`, `404.html`, `sitemap.xml`, `robots.txt`, `llms.txt`, `llms-full.txt`. These are generated and not in git: on every push to `gh-pages`, `.github/workflows/pages.yml` runs the tests, builds and publishes them. Locally, run `build.py` to preview.
- Tests: `node --test` (Node 22; `plan-core.test.js` mirrors `ScheduleParser.mc` in the app repo)
- Analytics: Umami Cloud (cookieless, no consent banner): page views, referrers, countries, UTM sources, and the builder events `plan_template`, `plan_copy`, `plan_copy_all` (no schedule contents)
- SEO: canonical + hreflang per page, Open Graph, `SoftwareApplication`, `FAQPage`, `WebSite` and `WebPage` JSON-LD, sitemap with language alternates, responsive WebP; IndexNow ping (Bing, Yandex, …) after every deploy (`python build.py indexnow`, key file at the root)
- Language: the home page sends first-time visitors to their browser language (nl, de, fr, es, it); a choice in the switcher is remembered (localStorage `fuelsteps-lang`) and always wins
- Moving to another domain: change `BASE` in `build.py` and rebuild
```

- [ ] **Step 5: Commit**

```bash
git add build.py .github/workflows/pages.yml README.md
git commit -m "Umami Cloud on all pages; node --test in the deploy workflow

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: i18n keys, `plan()` page template and CSS

**Files:**
- Modify: `i18n/en.json`, `i18n/nl.json`, `i18n/de.json`, `i18n/fr.json`, `i18n/es.json`, `i18n/it.json`
- Modify: `build.py` (new `plan()` function, `main()` writes the plan pages)
- Modify: `style.css`

**Interfaces:**
- Consumes: `ANALYTICS`, `REMEMBER`, `esc`, `path`, `T`, `ORDER`, `BASE`, `WEB` from `build.py`.
- Produces: pages `plan/index.html` and `<lang>/plan/index.html` with these DOM hooks that `plan.js` (Task 5) relies on: `#plan-i18n` (JSON script), `#plan-name`, `#plan-unit` (two radio inputs `name="unit"` values `km`/`min`), `#plan-template` (select), `#plan-steps` (tbody), `#plan-add`, `#plan-fields` (ol), `#plan-copy-all`, `#plan-moments` (tbody), `#plan-totals`, `#plan-errors`; `<script type="module" src="{up}plan.js">`.

- [ ] **Step 1: Add the keys to `i18n/en.json`**

Add before `"footer_watches"` (keep valid JSON; `<code>`/`<b>` allowed like in `steps`):

```json
"plan_title": "FuelSteps plan builder · build your fuel schedule and copy the settings",
"plan_desc": "Click your gel schedule together and copy the 10 settings fields for Garmin Connect. Includes the FuelSteps settings format for people and AI assistants.",
"plan_nav": "Plan builder",
"plan_cta": "Build your schedule",
"plan_kicker": "Plan builder",
"plan_h1": "Build your <em>schedule.</em>",
"plan_lead": "Click your steps together, check the moments, then copy the fields into Garmin Connect. No typing, no syntax.",
"plan_name": "Name",
"plan_unit": "Unit",
"plan_unit_km": "Distance",
"plan_unit_min": "Time",
"plan_km": "km",
"plan_min": "min",
"plan_template": "Start from",
"plan_template_blank": "Empty",
"plan_tpl_gel5": "Gel every 5 km",
"plan_tpl_marathon7": "Marathon · every 7 km",
"plan_tpl_time30": "Gel every 30 min",
"plan_template_confirm": "Replace the current steps with this template?",
"plan_steps_h2": "Steps",
"plan_col_repeat": "Repeat",
"plan_col_size": "After",
"plan_col_text": "What",
"plan_col_carbs": "Carbs (g)",
"plan_col_caf": "Caffeine",
"plan_add": "Add step",
"plan_up": "Move up",
"plan_down": "Move down",
"plan_delete": "Delete step",
"plan_fields_h2": "Your settings",
"plan_fields_lead": "Connect IQ app › My data fields › FuelSteps › Settings: paste each value, then Save. Then pick the schedule on the watch.",
"plan_field_step": "Step {n}",
"plan_copy": "Copy",
"plan_copied": "Copied",
"plan_copy_all": "Copy all",
"plan_moments_h2": "Moments",
"plan_col_at": "At",
"plan_before": "before start",
"plan_total": "{g} g in {n} moments",
"plan_total_caf": "{n} with caffeine",
"plan_per_hour": "{g} g/h",
"plan_err_name_empty": "Give the schedule a name.",
"plan_err_name_long": "Name: max 16 characters.",
"plan_err_no_steps": "Add at least one step.",
"plan_err_repeat": "Repeat: whole number from 1 to 30.",
"plan_err_size_min": "At least 0.5 km or 5 min.",
"plan_err_zero_first": "0 is only allowed as step 1, without repeat (the gel before the start).",
"plan_err_total_max": "The schedule is longer than 100 km / 600 min here.",
"plan_err_carbs": "Carbs: whole grams, 0 to 9999.",
"plan_err_field_long": "This step is longer than 40 characters; shorten the text.",
"plan_warn_roundtrip": "The last word reads as grams or caffeine on the watch; put the number first or change the word.",
"plan_format_kicker": "Reference",
"plan_format_h2": "FuelSteps settings format",
"plan_format_lead": "For people who prefer typing, and for AI assistants: this is exactly what FuelSteps expects in Garmin Connect.",
"plan_format_li": [
  "Garmin Connect (Connect IQ app › My data fields › FuelSteps › Settings) has 10 fields per schedule, 5 schedules in total: <b>Name</b> (max 16 characters), <b>Unit</b> (Distance = km or Time = min) and <b>Step 1</b> to <b>Step 8</b> (text, max 40 characters). Unused step fields must contain <code>-</code>; Garmin Connect cannot save an empty field. The first <code>-</code> ends the schedule.",
  "One step field: <code>[Nx] size [text] [carbs[g]] [caf]</code>, separated by spaces, in this order.",
  "<code>Nx</code>: optional repeat, 1–30. <code>3x5</code> = three times 5 km or 5 min; the watch numbers them #1, #2, #3.",
  "<code>size</code>: distance or time <b>after the previous moment</b> (km with Distance, minutes with Time), decimals with <code>.</code> or <code>,</code>. Minimum 0.5 km or 5 min; a schedule may add up to 100 km or 600 min.",
  "<code>text</code>: optional, may contain spaces (<code>Gel CAF</code>), default <code>Gel</code>. Everything between size and carbs is text, so a last word that is a number is read as grams.",
  "<code>carbs</code>: optional, whole grams, <code>25</code> or <code>25g</code>, default 0.",
  "<code>caf</code>: optional, any case, marks caffeine (shown on the alert, counted in the activity).",
  "<code>0</code> as size is only allowed in Step 1 without repeat: the gel you take before the start, counted in the totals, no alert.",
  "One invalid field makes the whole schedule invalid; the menu on the watch names the field."
],
"plan_format_examples_h3": "Examples",
"plan_format_examples": [
  ["3x5 Gel 25 caf", "three 25 g caffeine gels at km 5, 10 and 15"],
  ["0 Gel 25", "a gel before the start, no alert"],
  ["7,5 Dextro 15", "15 g Dextro 7.5 km (or min) after the previous moment"],
  ["30 Water", "water every 30 min, 0 g"],
  ["2x10 Peanut bar 30", "two bars, 10 km apart, numbered #1 and #2"]
],
"plan_format_worked_h3": "Worked example",
"plan_format_worked_q": "“Give me a fuel plan for a 32 km run with gel, gel with caffeine and Dextro. I use FuelSteps, what do I set?”",
"plan_format_worked_a": "A fitting answer sets one schedule in Garmin Connect: Name <code>Long run</code>, Unit <code>Distance</code>, Step 1 <code>0 Gel 25</code>, Step 2 <code>10 Gel 25</code>, Step 3 <code>5 Dextro 15</code>, Step 4 <code>2x5 Gel 25</code>, Step 5 <code>5 Gel CAF 25 caf</code>, Step 6 to 8 <code>-</code>. Moments: gel before the start, km 10 gel, km 15 Dextro, km 20 and 25 gel (#1, #2), km 30 caffeine gel. Total 140 g, 6 moments, 1 with caffeine. The alert comes 50 m before each moment by default.",
"plan_json_ld_name": "FuelSteps plan builder",
```

- [ ] **Step 2: Add the same keys to `i18n/nl.json`**

```json
"plan_title": "FuelSteps planbouwer · maak je voedingsschema en kopieer de instellingen",
"plan_desc": "Klik je gelschema in elkaar en kopieer de 10 instellingen voor Garmin Connect. Met het FuelSteps-instellingenformaat voor mensen en AI-assistenten.",
"plan_nav": "Planbouwer",
"plan_cta": "Maak je schema",
"plan_kicker": "Planbouwer",
"plan_h1": "Maak je <em>schema.</em>",
"plan_lead": "Klik je stappen bij elkaar, controleer de momenten en kopieer de velden naar Garmin Connect. Niets typen, geen syntaxis.",
"plan_name": "Naam",
"plan_unit": "Eenheid",
"plan_unit_km": "Afstand",
"plan_unit_min": "Tijd",
"plan_km": "km",
"plan_min": "min",
"plan_template": "Begin met",
"plan_template_blank": "Leeg",
"plan_tpl_gel5": "Gel elke 5 km",
"plan_tpl_marathon7": "Marathon · elke 7 km",
"plan_tpl_time30": "Gel elke 30 min",
"plan_template_confirm": "De huidige stappen vervangen door dit sjabloon?",
"plan_steps_h2": "Stappen",
"plan_col_repeat": "Herhaal",
"plan_col_size": "Na",
"plan_col_text": "Wat",
"plan_col_carbs": "Koolhydraten (g)",
"plan_col_caf": "Cafeïne",
"plan_add": "Stap toevoegen",
"plan_up": "Omhoog",
"plan_down": "Omlaag",
"plan_delete": "Stap verwijderen",
"plan_fields_h2": "Jouw instellingen",
"plan_fields_lead": "Connect IQ-app › Mijn gegevensvelden › FuelSteps › Instellingen: plak elke waarde en tik op Opslaan. Kies daarna het schema op het horloge.",
"plan_field_step": "Stap {n}",
"plan_copy": "Kopieer",
"plan_copied": "Gekopieerd",
"plan_copy_all": "Alles kopiëren",
"plan_moments_h2": "Momenten",
"plan_col_at": "Bij",
"plan_before": "voor de start",
"plan_total": "{g} g in {n} momenten",
"plan_total_caf": "{n} met cafeïne",
"plan_per_hour": "{g} g/u",
"plan_err_name_empty": "Geef het schema een naam.",
"plan_err_name_long": "Naam: maximaal 16 tekens.",
"plan_err_no_steps": "Voeg minstens één stap toe.",
"plan_err_repeat": "Herhaal: heel getal van 1 tot 30.",
"plan_err_size_min": "Minimaal 0,5 km of 5 min.",
"plan_err_zero_first": "0 mag alleen bij stap 1, zonder herhaling (de gel voor de start).",
"plan_err_total_max": "Het schema wordt hier langer dan 100 km / 600 min.",
"plan_err_carbs": "Koolhydraten: hele grammen, 0 tot 9999.",
"plan_err_field_long": "Deze stap is langer dan 40 tekens; kort de tekst in.",
"plan_warn_roundtrip": "Het laatste woord leest het horloge als grammen of cafeïne; zet het getal vooraan of kies een ander woord.",
"plan_format_kicker": "Referentie",
"plan_format_h2": "FuelSteps-instellingenformaat",
"plan_format_lead": "Voor wie liever typt, en voor AI-assistenten: dit is precies wat FuelSteps in Garmin Connect verwacht.",
"plan_format_li": [
  "Garmin Connect (Connect IQ-app › Mijn gegevensvelden › FuelSteps › Instellingen) heeft 10 velden per schema, 5 schema's in totaal: <b>Naam</b> (max 16 tekens), <b>Eenheid</b> (Afstand = km of Tijd = min) en <b>Stap 1</b> tot en met <b>Stap 8</b> (tekst, max 40 tekens). Ongebruikte stapvelden moeten <code>-</code> bevatten; Garmin Connect kan een leeg veld niet opslaan. De eerste <code>-</code> sluit het schema af.",
  "Eén stapveld: <code>[Nx] maat [tekst] [gram[g]] [caf]</code>, gescheiden door spaties, in deze volgorde.",
  "<code>Nx</code>: optionele herhaling, 1–30. <code>3x5</code> = drie keer 5 km of 5 min; het horloge nummert ze #1, #2, #3.",
  "<code>maat</code>: afstand of tijd <b>na het vorige moment</b> (km bij Afstand, minuten bij Tijd), decimalen met <code>.</code> of <code>,</code>. Minimaal 0,5 km of 5 min; een schema telt op tot maximaal 100 km of 600 min.",
  "<code>tekst</code>: optioneel, mag spaties bevatten (<code>Gel CAF</code>), standaard <code>Gel</code>. Alles tussen maat en gram is tekst, dus een laatste woord dat een getal is wordt als gram gelezen.",
  "<code>gram</code>: optioneel, hele grammen, <code>25</code> of <code>25g</code>, standaard 0.",
  "<code>caf</code>: optioneel, hoofdletters of niet, markeert cafeïne (op de melding, geteld in de activiteit).",
  "<code>0</code> als maat mag alleen in Stap 1 zonder herhaling: de gel die je voor de start neemt, telt mee in de totalen, geen melding.",
  "Eén ongeldig veld maakt het hele schema ongeldig; het menu op het horloge noemt het veld."
],
"plan_format_examples_h3": "Voorbeelden",
"plan_format_examples": [
  ["3x5 Gel 25 caf", "drie cafeïnegels van 25 g op km 5, 10 en 15"],
  ["0 Gel 25", "een gel voor de start, geen melding"],
  ["7,5 Dextro 15", "15 g Dextro 7,5 km (of min) na het vorige moment"],
  ["30 Water", "water elke 30 min, 0 g"],
  ["2x10 Peanut bar 30", "twee repen, 10 km uit elkaar, genummerd #1 en #2"]
],
"plan_format_worked_h3": "Uitgewerkt voorbeeld",
"plan_format_worked_q": "“Geef me een voedingsschema voor een loop van 32 km met gel, gel met cafeïne en Dextro. Ik gebruik FuelSteps, wat moet ik instellen?”",
"plan_format_worked_a": "Een passend antwoord zet één schema in Garmin Connect: Naam <code>Lange duurloop</code>, Eenheid <code>Afstand</code>, Stap 1 <code>0 Gel 25</code>, Stap 2 <code>10 Gel 25</code>, Stap 3 <code>5 Dextro 15</code>, Stap 4 <code>2x5 Gel 25</code>, Stap 5 <code>5 Gel CAF 25 caf</code>, Stap 6 tot en met 8 <code>-</code>. Momenten: gel voor de start, km 10 gel, km 15 Dextro, km 20 en 25 gel (#1, #2), km 30 cafeïnegel. Totaal 140 g, 6 momenten, 1 met cafeïne. De melding komt standaard 50 m voor elk moment.",
"plan_json_ld_name": "FuelSteps planbouwer",
```

- [ ] **Step 3: Add the same keys to `de.json`, `fr.json`, `es.json`, `it.json`**

Translate the English values from Step 1 into German, French, Spanish and Italian with the same keys and the same `<code>`/`<b>` markup. Rules: keep the code literals (`3x5 Gel 25 caf`, `-`, `caf`, `25g`) unchanged; the Garmin Connect menu names (Connect IQ app, My data fields, Settings, Save) and the Unit values (Distance/Time) must match the SETUP paragraph of that language in `D:\Projects\Prive\FuelSteps\app\STORE.md`; the tone matches the existing keys in that file (informal "du"/"tu"). Name in the worked example: `Langer Lauf`, `Sortie longue`, `Tirada larga`, `Lungo`. Placeholders `{n}`, `{g}` stay as they are.

- [ ] **Step 4: Verify the key sets are identical**

Run (PowerShell): `python -c "import json,glob;s=[set(json.load(open(f,encoding='utf-8'))) for f in sorted(glob.glob('i18n/*.json'))];print(all(x==s[0] for x in s), len(s[0]))"`
Expected: `True 116` (the previous 55 keys plus 61 new ones; if the number differs, list the symmetric difference per file and fix).

- [ ] **Step 5: Add `plan()` to `build.py`**

Insert after `page()` (before `def sitemap()`):

```python
# the plan builder: /plan/ (en) and /<lang>/plan/; UI strings go to plan.js through the #plan-i18n JSON block
def plan(code):
    t = T[code]
    up = "../" if code == "en" else "../../"
    url = f"{BASE}{path(code)}plan/"
    alternates = "\n".join(f'<link rel="alternate" hreflang="{c}" href="{BASE}{path(c)}plan/">' for c in ORDER)
    langs = " ".join(
        f'<a href="{up}{path(c)}plan/" hreflang="{c}" lang="{c}"{" aria-current=\"page\"" if c == code else ""}>{T[c]["label"]}</a>'
        for c in ORDER)
    ui = {k[5:]: v for k, v in t.items() if k.startswith("plan_") and not isinstance(v, list) and k not in ("plan_title", "plan_desc", "plan_h1", "plan_lead")}
    ui["tpl"] = {tid: t[f"plan_tpl_{tid}"] for tid in ("gel5", "marathon7", "time30")}
    webpage = {"@context": "https://schema.org", "@type": "WebPage", "name": t["plan_json_ld_name"], "description": t["plan_desc"],
               "url": url, "inLanguage": code, "isPartOf": {"@type": "WebSite", "name": "FuelSteps", "url": BASE}}
    li = lambda items: "".join(f"<li>{i}</li>" for i in items)
    examples = "".join(f"<tr><td><code>{esc(c)}</code></td><td>{esc(d)}</td></tr>" for c, d in t["plan_format_examples"])
    tpl_opts = "".join(f'<option value="{tid}">{esc(t[f"plan_tpl_{tid}"])}</option>' for tid in ("gel5", "marathon7", "time30"))
    return f"""<!doctype html>
<html lang="{code}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(t["plan_title"])}</title>
<meta name="description" content="{esc(t["plan_desc"])}">
<link rel="canonical" href="{url}">
{alternates}
<link rel="alternate" hreflang="x-default" href="{BASE}plan/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="FuelSteps">
<meta property="og:title" content="{esc(t["plan_json_ld_name"])}">
<meta property="og:description" content="{esc(t["plan_desc"])}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{BASE}{WEB}og.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="600">
<meta property="og:locale" content="{t["locale"]}">
<meta name="theme-color" content="#15171a">
<link rel="icon" href="{up}{WEB}icon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="{up}{WEB}icon-180.png">
<link rel="manifest" href="{up}manifest.webmanifest">
<link rel="stylesheet" href="{up}style.css">
<script type="application/ld+json">
{json.dumps(webpage, ensure_ascii=False, indent=1)}
</script>
{ANALYTICS}
</head>
<body>

<header><div class="wrap">
  <a class="brand" href="{up}{path(code) or "./"}"><img src="{up}{WEB}icon-192.png" alt="" width="38" height="38"><b>FuelSteps</b></a>
  <nav class="langs" aria-label="Language">{langs}</nav>
  <a class="btn ghost" href="{up}{path(code) or "./"}#donate">{t["nav_donate"]}</a>
</div></header>

<main>
<section class="alt plan-hero"><div class="wrap">
  <div class="kicker">{t["plan_kicker"]}</div>
  <h1>{t["plan_h1"]}</h1>
  <p class="lead">{t["plan_lead"]}</p>
</div></section>

<section class="builder"><div class="wrap">
  <noscript><p class="lead">JavaScript is needed for the builder. The format reference below works without it.</p></noscript>
  <div class="builder-grid">
    <div class="builder-in">
      <div class="field-row">
        <label>{t["plan_name"]}<input id="plan-name" type="text" maxlength="16" autocomplete="off"></label>
        <fieldset id="plan-unit"><legend>{t["plan_unit"]}</legend>
          <label><input type="radio" name="unit" value="km"> {t["plan_unit_km"]} ({t["plan_km"]})</label>
          <label><input type="radio" name="unit" value="min"> {t["plan_unit_min"]} ({t["plan_min"]})</label>
        </fieldset>
        <label>{t["plan_template"]}<select id="plan-template"><option value="">{t["plan_template_blank"]}</option>{tpl_opts}</select></label>
      </div>
      <h2 class="h3">{t["plan_steps_h2"]}</h2>
      <table class="steps-table">
        <thead><tr><th>{t["plan_col_repeat"]}</th><th>{t["plan_col_size"]}</th><th>{t["plan_col_text"]}</th><th>{t["plan_col_carbs"]}</th><th>{t["plan_col_caf"]}</th><th></th></tr></thead>
        <tbody id="plan-steps"></tbody>
      </table>
      <button id="plan-add" class="btn dark" type="button">{t["plan_add"]}</button>
      <ul id="plan-errors" class="errors"></ul>
    </div>
    <div class="builder-out">
      <h2 class="h3">{t["plan_fields_h2"]}</h2>
      <p class="hint">{t["plan_fields_lead"]}</p>
      <ol id="plan-fields" class="fields"></ol>
      <button id="plan-copy-all" class="btn amber" type="button">{t["plan_copy_all"]}</button>
      <h2 class="h3">{t["plan_moments_h2"]}</h2>
      <table class="moments-table">
        <thead><tr><th>{t["plan_col_at"]}</th><th>{t["plan_col_text"]}</th><th>{t["plan_col_carbs"]}</th><th></th></tr></thead>
        <tbody id="plan-moments"></tbody>
      </table>
      <p id="plan-totals" class="totals"></p>
    </div>
  </div>
</div></section>

<section class="alt" id="format"><div class="wrap format">
  <div class="kicker">{t["plan_format_kicker"]}</div>
  <h2>{t["plan_format_h2"]}</h2>
  <p class="lead">{t["plan_format_lead"]}</p>
  <ul class="format-list">{li(t["plan_format_li"])}</ul>
  <h3>{t["plan_format_examples_h3"]}</h3>
  <table class="examples"><tbody>{examples}</tbody></table>
  <h3>{t["plan_format_worked_h3"]}</h3>
  <p class="quote">{t["plan_format_worked_q"]}</p>
  <p>{t["plan_format_worked_a"]}</p>
</div></section>
</main>

<div class="stripe"></div>
<footer><div class="wrap">
  <span>FuelSteps · {t["footer_watches"]}</span>
  <nav class="langs-foot" aria-label="Language">{langs}</nav>
  <span>{t["not_affiliated"]}</span>
</div></footer>

<script type="application/json" id="plan-i18n">{json.dumps(ui, ensure_ascii=False)}</script>
<script type="module" src="{up}plan.js"></script>
{REMEMBER}
</body>
</html>
"""
```

Then in `main()`, after the loop that writes `index.html` per language, add:

```python
    for code in ORDER:
        out = ROOT / path(code) / "plan" / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(plan(code), encoding="utf-8", newline="\n")
```

And add `/plan/` to `.gitignore` under the generated files (the `/nl/` etc. entries already cover `/nl/plan/`).

- [ ] **Step 6: Add the CSS**

Append to `style.css`:

```css
/* plan builder */
.brand { display: flex; align-items: center; gap: 12px; text-decoration: none; color: var(--ink); flex: 1; }
.brand b { flex: none; }
.plan-hero { padding: 70px 0 50px; }
.plan-hero .lead { max-width: 640px; }
.builder { padding-top: 40px; }
.builder-grid { display: grid; grid-template-columns: 1.1fr .9fr; gap: 40px; align-items: start; }
.h3 { font-size: 24px; letter-spacing: -.5px; margin: 28px 0 12px; }
.field-row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; align-items: end; }
.field-row label, .steps-table td label { display: block; font-size: 14px; font-weight: 700; color: var(--muted); }
.field-row input[type=text], .field-row select, .steps-table input[type=number], .steps-table input[type=text] {
  display: block; width: 100%; margin-top: 4px; padding: 10px 12px; border: 1px solid #d9d2c3; border-radius: 10px; font: inherit; font-size: 17px; background: #fff; }
.field-row fieldset { border: 0; padding: 0; } .field-row legend { font-size: 14px; font-weight: 700; color: var(--muted); padding: 0; }
.field-row fieldset label { display: inline-block; margin: 8px 14px 0 0; font-size: 16px; color: var(--ink); font-weight: 600; }
.steps-table, .moments-table, .examples { width: 100%; border-collapse: collapse; }
.steps-table th, .moments-table th { text-align: left; font-size: 13px; letter-spacing: 1px; text-transform: uppercase; color: #6e6e6e; padding: 8px 6px; }
.steps-table td, .moments-table td, .examples td { padding: 8px 6px; border-top: 1px solid #eee; vertical-align: middle; font-size: 17px; }
.steps-table td.num { width: 90px; } .steps-table td.caf { text-align: center; width: 70px; } .steps-table td.act { width: 120px; white-space: nowrap; text-align: right; }
.steps-table tr.bad td { background: #fff3e0; }
.icon-btn { border: 0; background: #e7e1d3; border-radius: 8px; width: 34px; height: 34px; font-size: 16px; cursor: pointer; margin-left: 4px; }
.icon-btn:disabled { opacity: .35; cursor: default; }
.errors { list-style: none; padding: 0; margin: 14px 0 0; color: #a04000; font-size: 16px; }
.errors li.warn { color: #6b6558; }
.hint { color: var(--muted); font-size: 16px; margin-bottom: 14px; }
.fields { list-style: none; padding: 0; margin: 0 0 16px; }
.fields li { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-top: 1px solid #eee; }
.fields .lbl { width: 72px; color: #666; font-weight: 600; font-size: 15px; flex: none; }
.fields code, .examples code, .format-list code, .format p code { font-family: ui-monospace, Consolas, "Cascadia Mono", monospace; font-size: 16px; background: #fff; border: 1px solid #e7e1d3; border-radius: 6px; padding: 2px 8px; }
.fields code { flex: 1; min-width: 0; overflow-wrap: anywhere; }
.fields code.dash { color: #999; }
.copy { border: 2px solid var(--ink); background: #fff; color: var(--ink); border-radius: 20px; padding: 5px 12px; font: inherit; font-size: 14px; font-weight: 700; cursor: pointer; }
.copy.done { background: var(--ink); color: #fff; }
.moments-table .tag { margin-left: 4px; }
.totals { margin-top: 14px; font-weight: 700; color: var(--muted); }
.format { max-width: 860px; }
.format-list { margin: 24px 0 0; padding-left: 22px; font-size: 18px; color: var(--muted); } .format-list li { padding: 6px 0; }
.format h3 { font-size: 22px; margin: 34px 0 10px; letter-spacing: -.4px; }
.format p { font-size: 18px; color: var(--muted); }
.format .quote { font-style: italic; color: var(--ink); margin-bottom: 10px; }
.examples td:first-child { white-space: nowrap; width: 230px; }
@media (max-width: 820px) {
  .builder-grid { grid-template-columns: 1fr; } .field-row { grid-template-columns: 1fr; }
  .steps-table td.num { width: 70px; } .examples td:first-child { white-space: normal; width: auto; }
}
```

- [ ] **Step 7: Build and inspect**

Run: `python build.py` then open `plan/index.html` and `nl/plan/index.html` in a browser (`file://` is fine for a static look; the module script needs http, see Task 7).
Expected: pages exist, header/footer and format section render, `#plan-i18n` contains the `tpl` object and the `err_*` strings; `python -c "import json,re;print(json.loads(re.search(r'id=\"plan-i18n\">(.*?)</script>', open('nl/plan/index.html',encoding='utf-8').read(), re.S).group(1))['copied'])"` prints `Gekopieerd`.

- [ ] **Step 8: Commit**

```bash
git add i18n/*.json build.py style.css .gitignore
git commit -m "Plan page: i18n texts (6 languages), build template, settings format reference, CSS

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Builder UI (`plan.js`)

**Files:**
- Create: `plan.js`

**Interfaces:**
- Consumes: `LIMITS, TEMPLATES, validate, fields, moments, fromJSON, newStep, formatStep` from `plan-core.js`; DOM hooks from Task 4; `window.umami` (optional).
- Produces: localStorage key `fuelsteps-plan` (JSON of the schedule); Umami events `plan_template {id}`, `plan_copy {field, unit, steps}`, `plan_copy_all {unit, steps}`.

- [ ] **Step 1: Write `plan.js`**

```js
// plan.js — DOM layer of the plan builder. All logic lives in plan-core.js; this file renders state,
// copies values, keeps the schedule in localStorage and sends Umami events (names only, no schedule contents).
import { LIMITS, TEMPLATES, validate, fields, moments, fromJSON, newStep } from "./plan-core.js";

const STORAGE = "fuelsteps-plan";
const S = JSON.parse(document.getElementById("plan-i18n").textContent);
const lang = document.documentElement.lang || "en";
const $ = (id) => document.getElementById(id);
const el = (tag, attrs = {}, ...children) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) n.setAttribute(k, v === true ? "" : v);
  }
  n.append(...children);
  return n;
};
const fmt = (s, vars) => s.replace(/\{(\w+)\}/g, (_, k) => vars[k]);
const numText = (n) => Number(n).toLocaleString(lang, { maximumFractionDigits: 2 });
const track = (name, data) => { if (typeof window.umami !== "undefined") window.umami.track(name, data); };

let schedule = fromJSON(localStorage.getItem(STORAGE)) || structuredClone(TEMPLATES[0].schedule);

function save() {
  try { localStorage.setItem(STORAGE, JSON.stringify(schedule)); } catch (e) { /* private mode: builder still works */ }
}

async function copyText(text, button) {
  try {
    await navigator.clipboard.writeText(text);
  } catch (e) {
    // no clipboard API (http, old browser): select the value so the user can press Ctrl+C
    const code = button.parentElement.querySelector("code");
    if (code) { const r = document.createRange(); r.selectNodeContents(code); const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r); }
  }
  const label = button.textContent;
  button.textContent = S.copied; button.classList.add("done");
  setTimeout(() => { button.textContent = label; button.classList.remove("done"); }, 1200);
}

function stepInput(type, value, attrs, onChange) {
  return el("input", { type, value, ...attrs, oninput: (e) => { onChange(e.target); render(); } });
}

function renderSteps(v) {
  const body = $("plan-steps");
  body.replaceChildren();
  const lim = LIMITS[schedule.unit];
  schedule.steps.forEach((s, i) => {
    const bad = v.steps[i] !== null;
    const tr = el("tr", { class: bad ? "bad" : "" },
      el("td", { class: "num" }, stepInput("number", s.repeat, { min: 1, max: LIMITS.repeatMax, step: 1, "aria-label": S.col_repeat }, (t) => { s.repeat = t.valueAsNumber; })),
      el("td", { class: "num" }, stepInput("number", s.size, { min: 0, max: lim.max, step: lim.step, "aria-label": S.col_size + " (" + S[schedule.unit] + ")" }, (t) => { s.size = t.valueAsNumber; })),
      el("td", {}, stepInput("text", s.text, { maxlength: LIMITS.fieldMax, "aria-label": S.col_text }, (t) => { s.text = t.value; })),
      el("td", { class: "num" }, stepInput("number", s.carbs, { min: 0, max: LIMITS.carbsMax, step: 1, "aria-label": S.col_carbs }, (t) => { s.carbs = t.valueAsNumber; })),
      el("td", { class: "caf" }, el("input", { type: "checkbox", checked: s.caf, "aria-label": S.col_caf, onchange: (e) => { s.caf = e.target.checked; render(); } })),
      el("td", { class: "act" },
        el("button", { class: "icon-btn", type: "button", title: S.up, "aria-label": S.up, disabled: i === 0, onclick: () => { [schedule.steps[i - 1], schedule.steps[i]] = [schedule.steps[i], schedule.steps[i - 1]]; render(); } }, "↑"),
        el("button", { class: "icon-btn", type: "button", title: S.down, "aria-label": S.down, disabled: i === schedule.steps.length - 1, onclick: () => { [schedule.steps[i + 1], schedule.steps[i]] = [schedule.steps[i], schedule.steps[i + 1]]; render(); } }, "↓"),
        el("button", { class: "icon-btn", type: "button", title: S.delete, "aria-label": S.delete, onclick: () => { schedule.steps.splice(i, 1); render(); } }, "✕")));
    body.append(tr);
  });
  $("plan-add").disabled = schedule.steps.length >= LIMITS.maxSteps;
}

function renderErrors(v) {
  const ul = $("plan-errors");
  ul.replaceChildren();
  if (v.name) ul.append(el("li", {}, S["err_" + v.name]));
  if (schedule.steps.length === 0) ul.append(el("li", {}, S.err_no_steps));
  v.steps.forEach((e, i) => { if (e) ul.append(el("li", {}, fmt(S.field_step, { n: i + 1 }) + ": " + S["err_" + e])); });
  v.warnings.forEach((w, i) => { if (w) ul.append(el("li", { class: "warn" }, fmt(S.field_step, { n: i + 1 }) + ": " + S["warn_" + w])); });
}

function fieldRows() {
  const f = fields(schedule);
  const unitLabel = S["unit_" + f.unit];
  return [
    { key: "name", label: S.name, value: f.name },
    { key: "unit", label: S.unit, value: unitLabel },
    ...f.steps.map((v, i) => ({ key: "step" + (i + 1), label: fmt(S.field_step, { n: i + 1 }), value: v })),
  ];
}

function renderFields() {
  const ol = $("plan-fields");
  ol.replaceChildren();
  for (const r of fieldRows()) {
    const btn = el("button", { class: "copy", type: "button", onclick: (e) => {
      copyText(r.value, e.currentTarget);
      track("plan_copy", { field: r.key, unit: schedule.unit, steps: schedule.steps.length });
    } }, S.copy);
    ol.append(el("li", {}, el("span", { class: "lbl" }, r.label), el("code", { class: r.value === "-" ? "dash" : "" }, r.value), btn));
  }
}

function renderMoments() {
  const m = moments(schedule);
  const body = $("plan-moments");
  body.replaceChildren();
  const unit = S[schedule.unit];
  for (const r of m.rows) {
    body.append(el("tr", {},
      el("td", {}, r.before ? S.before : `${numText(r.at)} ${unit}`),
      el("td", {}, r.label),
      el("td", {}, r.carbs > 0 ? `${r.carbs} g` : ""),
      el("td", {}, r.caf ? el("span", { class: "tag" }, "caf") : "")));
  }
  const parts = [fmt(S.total, { g: m.totalCarbs, n: m.count })];
  if (m.cafCount) parts.push(fmt(S.total_caf, { n: m.cafCount }));
  if (m.perHour !== null) parts.push(fmt(S.per_hour, { g: numText(m.perHour) }));
  $("plan-totals").textContent = m.rows.length ? parts.join(" · ") : "";
}

function render() {
  const v = validate(schedule);
  if (document.activeElement !== $("plan-name")) $("plan-name").value = schedule.name;
  document.querySelectorAll('#plan-unit input[name="unit"]').forEach((r) => { r.checked = r.value === schedule.unit; });
  if (!document.activeElement || !$("plan-steps").contains(document.activeElement)) renderSteps(v);
  else $("plan-steps").querySelectorAll("tr").forEach((tr, i) => tr.classList.toggle("bad", v.steps[i] !== null));
  renderErrors(v);
  renderFields();
  renderMoments();
  save();
}

$("plan-name").addEventListener("input", (e) => { schedule.name = e.target.value; render(); });
document.querySelectorAll('#plan-unit input[name="unit"]').forEach((r) => r.addEventListener("change", (e) => { schedule.unit = e.target.value; render(); }));
$("plan-template").addEventListener("change", (e) => {
  const tpl = TEMPLATES.find((t) => t.id === e.target.value);
  if (schedule.steps.length && !confirm(S.template_confirm)) { e.target.value = ""; return; }
  schedule = tpl ? structuredClone(tpl.schedule) : { name: "", unit: schedule.unit, steps: [] };
  if (tpl) track("plan_template", { id: tpl.id });
  e.target.value = "";
  render();
});
$("plan-add").addEventListener("click", () => { schedule.steps.push(newStep()); render(); });
$("plan-copy-all").addEventListener("click", (e) => {
  copyText(fieldRows().map((r) => `${r.label}: ${r.value}`).join("\n"), e.currentTarget);
  track("plan_copy_all", { unit: schedule.unit, steps: schedule.steps.length });
});

render();
```

Note on `renderSteps` while typing: the table is only rebuilt when focus is outside it, so typing in a step input does not lose focus; row error classes are updated in place.

- [ ] **Step 2: Serve and smoke-test**

Run: `python build.py` then `python -m http.server 8080` (background) and open `http://localhost:8080/plan/`.
Expected: the "Gel 5 km" template shows one step row, the fields list shows `Gel 5 km`, `Distance`, `3x5 Gel 25 caf` and seven `-`, the moments table lists 5 km, 10 km, 15 km with `caf` tags, totals read `75 g in 3 moments · 3 with caffeine`. Reload keeps the state. Add step → row appears with `5 Gel 25`; set size 0 on step 2 → row turns amber and the error list says Step 2 … 0 is only allowed as step 1. Choose template Marathon → confirm → 5 rows. Copy → button flashes "Copied", clipboard holds the value.

- [ ] **Step 3: Run the unit tests once more**

Run: `node --test`
Expected: PASS (unchanged, 20 tests). `plan.js` is not imported by Node (it touches `document`).

- [ ] **Step 4: Commit**

```bash
git add plan.js
git commit -m "Plan builder UI: steps table, settings fields with copy, moments preview, localStorage, Umami events

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Home page links, up-to-date setup text, llms format section, sitemap and IndexNow

**Files:**
- Modify: `build.py` (`page()`, `sitemap()`, `llms()`, `llms_full()`, `indexnow()`)
- Modify: `i18n/*.json` (`steps`, add `plan_steps_link`)

**Interfaces:**
- Consumes: `plan_cta`, `plan_nav`, `plan_format_*` keys from Task 4.

- [ ] **Step 1: Update the `steps` texts in all six i18n files**

English (`en.json`), replace the `steps` array:

```json
"steps": ["Install FuelSteps from the Connect IQ app on your phone; after the sync the watch asks to install it, pick the running activity › OK.", "Allow the alert on the watch: activity settings › <b>Alerts › Add New › Connect IQ › FuelSteps › On</b> (the watch may ask this during installation).", "Edit your schedules in the Connect IQ app: My data fields › FuelSteps › Settings › Save. Schedule 1 \"Gel 5 km\" is ready to go (3× 5 km, 25 g gel with caffeine). <a href=\"plan/\">Build your own schedule</a> and copy the fields.", "Pick a schedule on the watch before the run: hold UP › Connect IQ fields › FuelSteps. Nothing fires until you do."],
```

Dutch (`nl.json`):

```json
"steps": ["Installeer FuelSteps via de Connect IQ-app op je telefoon; na het synchroniseren vraagt het horloge om het te installeren, kies de hardloopactiviteit › OK.", "Sta de melding toe op het horloge: activiteitinstellingen › <b>Alarmen › Voeg nieuwe toe › Connect IQ › FuelSteps › Aan</b> (het horloge vraagt dit soms al bij de installatie).", "Stel je schema's in via de Connect IQ-app: Mijn gegevensvelden › FuelSteps › Instellingen › Opslaan. Schema 1 \"Gel 5 km\" staat klaar (3× 5 km, een gel van 25 g met cafeïne). <a href=\"plan/\">Maak je eigen schema</a> en kopieer de velden.", "Kies vóór je run een schema op het horloge: houd UP ingedrukt › Connect IQ-velden › FuelSteps. Zonder keuze gebeurt er niets."],
```

German, French, Spanish, Italian: translate the English array with the same structure; the menu names come from the SETUP paragraph of that language in `D:\Projects\Prive\FuelSteps\app\STORE.md`; keep `<a href="plan/">…</a>` around the "build your own schedule" phrase.

- [ ] **Step 2: Home page: button, nav link, header brand**

In `page()`:
- In the `<header>` add after the `langs` nav: `<a class="btn ghost" href="plan/">{t["plan_nav"]}</a>` (before the donate button).
- In the hero `.ctas`, add as first element: `<a class="btn dark" href="plan/">{t["plan_cta"]}</a>`.
- The `steps` texts contain `<a href="plan/">`; `li()` inserts them unescaped already, so nothing else changes.

Both header buttons stay visible on mobile; add to the `@media (max-width: 820px)` block in `style.css`: `header .btn { padding: 9px 14px; font-size: 15px; }`.

- [ ] **Step 3: `sitemap()` and `indexnow()` include the plan pages**

Replace `sitemap()`:

```python
def sitemap():
    today = date.today().isoformat()
    def entry(sub):
        alt = "".join(f'\n    <xhtml:link rel="alternate" hreflang="{c}" href="{BASE}{path(c)}{sub}"/>' for c in ORDER)
        alt += f'\n    <xhtml:link rel="alternate" hreflang="x-default" href="{BASE}{sub}"/>'
        return "".join(f"\n  <url>\n    <loc>{BASE}{path(c)}{sub}</loc>\n    <lastmod>{today}</lastmod>{alt}\n  </url>" for c in ORDER)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">'
            f"{entry('')}{entry('plan/')}\n</urlset>\n")
```

In `indexnow()`, change `"urlList": [BASE + path(c) for c in ORDER]` to `"urlList": [BASE + path(c) + sub for sub in ("", "plan/") for c in ORDER]`.

- [ ] **Step 4: Format section in `llms_full()` and a pointer in `llms()`**

In `llms()`, add to the bullet list (after the "Schedules:" bullet):

```
- Settings format (Garmin Connect, per schedule: Name, Unit, Step 1–8): one step field = `[Nx] size [text] [carbs[g]] [caf]`, e.g. `3x5 Gel 25 caf`; unused fields `-`; full reference and plan builder: {BASE}plan/#format
```

and to the Pages list: `- [Plan builder and settings format]({BASE}plan/)`.

In `llms_full()`, add a `format_section()` helper above it and insert its output after the schedules section (before `## {strip(t["alert_h2"])}`):

```python
# the settings format reference as markdown (English), shared by llms-full.txt
def format_section():
    t = T["en"]
    items = "\n".join(f"- {strip(i).replace('`', '')}" for i in t["plan_format_li"])
    examples = "\n".join(f"- `{c}`: {d}" for c, d in t["plan_format_examples"])
    return f"""## {t["plan_format_h2"]}
{strip(t["plan_format_lead"])} Plan builder: {BASE}plan/

{items}

### {t["plan_format_examples_h3"]}
{examples}

### {t["plan_format_worked_h3"]}
{t["plan_format_worked_q"]}
{strip(t["plan_format_worked_a"])}
"""
```

Note: `strip()` removes tags; `<code>` content stays as plain text, which is what the markdown needs.

- [ ] **Step 5: Build and verify**

Run: `python build.py` then:
- `Select-String -Path llms-full.txt -Pattern "FuelSteps settings format","3x5 Gel 25 caf","Gel 5 km"` → all three found.
- `Select-String -Path llms-full.txt,llms.txt,index.html,nl/index.html -Pattern "6× 30 min","Waarschuwingen → Connect IQ"` → nothing found.
- `Select-String -Path sitemap.xml -Pattern "<loc>" | Measure-Object` → 12.
- Open `http://localhost:8080/` and `/nl/`: hero shows the "Build your schedule" button linking to `plan/`, header has the plan link, step 3 links to the plan page.
- `node --test` → PASS.

- [ ] **Step 6: Commit**

```bash
git add build.py style.css i18n/*.json
git commit -m "Home: plan builder links and current setup steps; llms format reference; sitemap and IndexNow with plan pages

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Browser verification and hand-off

**Files:**
- Modify: `docs/superpowers/plans/2026-10-02-plan-builder.md` (tick the boxes)

- [ ] **Step 1: Verify with playwright-cli** (skill `browser-verification` from `playwright-cli@web-ai-toolkit`; fall back to a manual browser check if the plugin is not installed in this repo)

With `python -m http.server 8080` running from the repo root, check on `http://localhost:8080/plan/` and `http://localhost:8080/nl/plan/`:
1. Default state: one step row, 10 fields, moments 5/10/15, totals line.
2. Template Marathon: confirm dialog, 5 rows, moments 0 (before start), 7, 14, 21, 28, 35; totals `140 g in 6 moments · 1 with caffeine` (en) / `… 6 momenten · 1 met cafeïne` (nl).
3. Validation: set step 2 size to 0 → amber row + message; set repeat 31 → message; type a text of 45 characters → "longer than 40" message; text `Maurten 100` with carbs 0 → grey warning.
4. Copy button on Step 1 → "Copied" flash; `navigator.clipboard.readText()` in the page console returns `0 Gel 25`. Copy all → 10 lines `Label: value`.
5. Reload → same state. Clear `localStorage` → default template again.
6. Network log shows `cloud.umami.is/script.js` loaded, nothing from `cloudflareinsights`, and, after a copy, a `POST https://cloud.umami.is/api/send` with `"name":"plan_copy"` and no step text in the payload.
7. Language switcher on the plan page goes to `/nl/plan/` and back; footer and header render; `#format` anchor scrolls to the reference.
8. Mobile viewport (390 px): one column, table still usable.

- [ ] **Step 2: Fix anything found, re-run `node --test` and `python build.py`, commit**

```bash
git add -A
git commit -m "Plan builder: verification fixes

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

(Skip the commit if nothing changed.)

- [ ] **Step 3: Push the branch and open a PR to `gh-pages`**

```bash
git push -u origin feature/plan-builder
gh pr create --base gh-pages --title "Plan builder page, settings format reference, Umami" --body "Adds /plan/ in 6 languages (builder + FuelSteps settings format for people and AI assistants), Umami Cloud events, node --test in the deploy workflow, current setup steps on the home page. Spec: docs/superpowers/specs/2026-10-02-plan-builder-design.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

Use the `bruynr` GitHub account (`gh auth switch --user bruynr` if needed, see memory `github-accounts`).

- [ ] **Step 4: Follow-up for the app repo (separate change, not in this plan)**

Tell the user: in `D:\Projects\Prive\FuelSteps\app`, README.md and STORE.md should link to the plan page once it is live. The STORE.md line `More info and screenshots: https://fuelsteps.com/` becomes two lines with a UTM tag, so Umami shows store visitors as their own source (the Connect IQ app sends no referrer): `More info and screenshots: https://fuelsteps.com/?utm_source=connectiq` and `Build your schedule and copy the settings: https://fuelsteps.com/plan/?utm_source=connectiq` (per language the `/<lang>/` URL), plus the plan link in SETUP step 2, in all six languages.
