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
