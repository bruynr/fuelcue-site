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
    else if (k === "checked") n.checked = !!v;
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
  return [
    { key: "name", label: S.name, value: f.name },
    { key: "unit", label: S.unit, value: S["unit_" + f.unit] },
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
  // rebuild the table only when focus is outside it, so typing in a step keeps its input; otherwise refresh the row state
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
