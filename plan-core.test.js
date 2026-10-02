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
