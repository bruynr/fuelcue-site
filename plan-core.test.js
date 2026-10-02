// plan-core.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { parseStepText, formatStep, LIMITS, TEMPLATES, validate, fields, moments, fromJSON, newStep } from "./plan-core.js";

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
  const v = validate(sched("km", [step(5, 1, "Maurten 100", 0, false), step(5, 1, "Gel caf", 0, false), step(5, 1, "Gel", 25, false)]));
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

test("moments and fields ignore steps the watch would reject (unbounded repeat, empty size)", () => {
  const huge = moments(sched("km", [step(5, 3000000, "Gel", 25, false), step(5, 1, "Gel", 25, false)]));
  assert.deepEqual(huge.rows.map(r => r.at), [5]); // the invalid step adds no rows, the valid one still counts from 0
  const empty = moments(sched("km", [step(NaN, 1, "Gel", 25, false), step(5, 2, "Gel", 25, false)]));
  assert.deepEqual(empty.rows.map(r => r.at), [5, 10]);
  assert.equal(moments(sched("km", [step(5, 1.5, "Gel", 25, false)])).rows.length, 0);
  assert.equal(formatStep(step(NaN, 1, "Gel", 25, false)), "? Gel 25"); // shown while a field is empty, never a valid line
});
