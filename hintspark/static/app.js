"use strict";

const $ = (id) => document.getElementById(id);
const state = {
  exercises: [], ex: null, result: null, ranCode: null, step: 0,
  hintLevel: 0, failedRuns: {}, passed: new Set(), marks: { current: null, wrong: null },
};

// ---------- session id (light per-browser convenience) --------------------
function newId() {
  return (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : String(Math.random()).slice(2);
}
let sessionId;
try {
  sessionId = localStorage.getItem("hs_session") || newId();
  localStorage.setItem("hs_session", sessionId);
} catch (e) { sessionId = newId(); }

// ---------- editor ----------------------------------------------------------
const cm = CodeMirror.fromTextArea($("editor"), {
  mode: "python", lineNumbers: true, indentUnit: 4, tabSize: 4,
  extraKeys: { Tab: (c) => c.replaceSelection("    ") },
});
cm.on("change", () => {
  if (state.result && cm.getValue() !== state.ranCode) {
    setStatus("", "You changed the code. Press Run & trace to see what it does now.");
  }
});

// ---------- helpers ---------------------------------------------------------
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;  // always textContent: never inject HTML
  return e;
}
async function api(path, body) {
  const res = await fetch(path, body ? {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  } : {});
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { const j = await res.json(); if (typeof j.detail === "string") msg = j.detail; } catch (e) {}
    throw new Error(msg);
  }
  return res.json();
}
let lastStepTrack = 0;
function track(event_type, extra = {}) {
  if (!state.ex) return;
  fetch("/api/event", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, exercise_id: state.ex.id, event_type, ...extra }),
  }).catch(() => {});
}
function setStatus(kind, text) {
  const s = $("status");
  s.className = "status" + (kind ? " " + kind : "");
  s.textContent = text;
}

// ---------- exercises -------------------------------------------------------
async function init() {
  try {
    state.exercises = await api("/api/exercises");
  } catch (e) { setStatus("bad", "Could not load exercises: " + e.message); return; }
  const nav = $("exercise-tabs");
  state.exercises.forEach((ex) => {
    const b = el("button", "tab", ex.title);
    b.dataset.id = ex.id;
    b.onclick = () => selectExercise(ex.id);
    nav.appendChild(b);
  });
  selectExercise(state.exercises[0].id);
}

function selectExercise(id) {
  state.ex = state.exercises.find((e) => e.id === id);
  document.querySelectorAll(".tab").forEach((b) => {
    b.classList.toggle("active", b.dataset.id === id);
    b.classList.toggle("done", state.passed.has(b.dataset.id));
  });
  $("goal").textContent = "Goal: " + state.ex.goal;
  cm.setValue(state.ex.starter);
  clearTrace();
  setStatus("", "Press Run & trace to see what this program really does.");
  track("open");
}

function clearTrace() {
  state.result = null; state.ranCode = null; state.step = 0; state.hintLevel = 0;
  clearMarks();
  ["tests", "vars", "compare", "explanation"].forEach((id) => { $(id).replaceChildren(); });
  $("output-so-far").textContent = "";
  $("step-label").textContent = "No trace yet.";
  $("jump").hidden = true;
  $("explain").disabled = true;
  updateControls();
}

// ---------- run -------------------------------------------------------------
async function run() {
  $("run").disabled = true;
  setStatus("", "Running your program step by step…");
  const code = cm.getValue();
  try {
    const r = await api("/api/run", { exercise_id: state.ex.id, code, session_id: sessionId });
    state.result = r; state.ranCode = code; state.hintLevel = 0;
    $("explanation").replaceChildren();
    $("explain").disabled = false;
    renderTests(); renderCompare(); markWrongLine();
    const id = state.ex.id;

    if (r.all_passed) {
      state.failedRuns[id] = 0; state.passed.add(id);
      document.querySelector(`.tab[data-id="${id}"]`).classList.add("done");
      setStatus("ok", "All tests pass 🎉 Step through to see how your program got there.");
      $("jump").hidden = true;
      goTo(0);
    } else {
      state.failedRuns[id] = (state.failedRuns[id] || 0) + 1;
      setStatus("bad", r.divergence ? r.divergence.message : "Not quite yet.");
      const hasStep = r.divergence && r.divergence.step !== null && r.divergence.step !== undefined;
      $("jump").hidden = !hasStep;
      goTo(hasStep ? r.divergence.step : 0);
      if (state.failedRuns[id] >= 3) showNudge();
    }
  } catch (e) {
    setStatus("bad", "Could not run: " + e.message);
  } finally {
    $("run").disabled = false;
  }
}

function showNudge() {
  const n = el("div", "nudge",
    "Stuck? That's normal - this is where learning happens. Press 🎯 Jump to where it went wrong, " +
    "step back one or two steps, and watch the variables. Then try 💡 Explain this step.");
  $("status").appendChild(n);
  track("nudge_shown");
}

// ---------- step navigation -------------------------------------------------
function steps() { return state.result ? state.result.trace.steps : []; }

function goTo(i) {
  const s = steps();
  if (!s.length) { renderEmptyTrace(); return; }
  state.step = Math.max(0, Math.min(i, s.length - 1));
  renderStep();
  const now = Date.now();
  if (now - lastStepTrack > 1500) { lastStepTrack = now; track("step_view", { step: state.step }); }
}

function updateControls() {
  const n = steps().length;
  $("slider").max = Math.max(n - 1, 0);
  $("slider").value = state.step;
  $("first").disabled = $("prev").disabled = !n || state.step === 0;
  $("last").disabled = $("next").disabled = !n || state.step >= n - 1;
  $("slider").disabled = !n;
}

function renderEmptyTrace() {
  updateControls();
  const err = state.result && state.result.trace.error;
  $("step-label").textContent = err ? `Your program could not start (${err.type}).` : "No steps recorded.";
  $("vars").replaceChildren(el("div", "empty", "No variables - the program did not run."));
  $("output-so-far").textContent = "";
}

function describe(step, i, total) {
  const prefix = `Step ${i} of ${total - 1}: `;
  if (step.event === "line") return prefix + `about to run line ${step.line}`;
  if (step.event === "return") {
    return step.func === "<module>" ? prefix + "program finished"
      : prefix + `${step.func}() is giving back ${step.return_value.repr}`;
  }
  return prefix + `error on line ${step.line} - ${step.exception}`;
}

function renderStep() {
  const s = steps(), step = s[state.step], prev = state.step > 0 ? s[state.step - 1] : null;
  updateControls();
  $("step-label").textContent = describe(step, state.step, s.length);
  highlightLine(step.line);
  renderVars(step, prev);
  $("output-so-far").textContent = state.result.trace.stdout.slice(0, step.stdout_len) || " ";
}

// ---------- editor highlights ----------------------------------------------
function clearMarks() {
  if (state.marks.current !== null) cm.removeLineClass(state.marks.current, "background", "hs-current");
  if (state.marks.wrong !== null) cm.removeLineClass(state.marks.wrong, "background", "hs-wrong");
  state.marks = { current: null, wrong: null };
}
function highlightLine(line) {
  if (state.marks.current !== null) cm.removeLineClass(state.marks.current, "background", "hs-current");
  if (line >= 1 && line <= cm.lineCount()) {
    state.marks.current = line - 1;
    cm.addLineClass(line - 1, "background", "hs-current");
    cm.scrollIntoView({ line: line - 1, ch: 0 }, 60);
  } else state.marks.current = null;
}
function markWrongLine() {
  if (state.marks.wrong !== null) cm.removeLineClass(state.marks.wrong, "background", "hs-wrong");
  state.marks.wrong = null;
  const d = state.result && state.result.divergence;
  if (d && d.line && d.line <= cm.lineCount()) {
    state.marks.wrong = d.line - 1;
    cm.addLineClass(d.line - 1, "background", "hs-wrong");
  }
}

// ---------- variables panel -------------------------------------------------
function frames(step) {
  const out = [{ title: "Program variables", vars: step.globals, key: "<module>" }];
  step.stack.forEach((f, i) => out.push({ title: `Inside ${f.func}()`, vars: f.locals, key: f.func + i }));
  return out;
}

function renderVars(step, prev) {
  const box = $("vars");
  box.replaceChildren();

  // Which names share the same list/dict? (aliasing - exercise 5)
  const idNames = {};
  frames(step).forEach((fr) => Object.entries(fr.vars).forEach(([k, v]) => {
    if (v.id !== undefined) (idNames[v.id] = idNames[v.id] || []).push(k);
  }));
  const prevRepr = {};
  if (prev) frames(prev).forEach((fr) => Object.entries(fr.vars).forEach(([k, v]) => { prevRepr[fr.key + ":" + k] = v.repr; }));

  frames(step).forEach((fr) => {
    box.appendChild(el("div", "frame-title", fr.title));
    const entries = Object.entries(fr.vars);
    if (!entries.length) { box.appendChild(el("div", "empty", "no variables yet")); return; }
    const table = el("table");
    const head = el("tr");
    ["name", "value", "type"].forEach((h) => head.appendChild(el("th", "", h)));
    table.appendChild(head);
    entries.forEach(([k, v]) => {
      const tr = el("tr");
      const before = prevRepr[fr.key + ":" + k];
      if (prev && before !== v.repr) tr.className = "changed";
      tr.appendChild(el("td", "", k));
      const val = el("td", "", v.repr);
      if (v.id !== undefined && idNames[v.id].length > 1) {
        const others = idNames[v.id].filter((n) => n !== k);
        val.appendChild(el("span", "badge", "same list as " + others.join(", ")));
      }
      if (prev && before !== undefined && before !== v.repr) val.title = "was " + before;
      tr.appendChild(val);
      tr.appendChild(el("td", "type", v.type));
      table.appendChild(tr);
    });
    box.appendChild(table);
  });

  if (step.event === "return" && step.func !== "<module>") {
    const r = el("div", "frame-title", `${step.func}() gives back: `);
    r.appendChild(el("span", "badge ret", step.return_value.repr));
    box.appendChild(r);
  }
}

// ---------- tests & comparison ---------------------------------------------
function renderTests() {
  const ul = el("ul");
  state.result.tests.forEach((t, i) => {
    const li = el("li", t.passed ? "pass" : "fail",
      `${t.passed ? "✓" : "✗"} Test ${i + 1}` + (t.stdin ? ` (input: ${t.stdin})` : ""));
    ul.appendChild(li);
  });
  $("tests").replaceChildren(ul);
}

function renderCompare() {
  const r = state.result, t = r.tests[r.focus_test];
  const split = (s) => { s = (s || "").replace(/\s+$/, ""); return s ? s.split("\n") : []; };
  const exp = split(t.expected), act = split(t.actual);
  const table = el("table");
  const head = el("tr");
  ["#", "expected", "your program"].forEach((h) => head.appendChild(el("th", "", h)));
  table.appendChild(head);
  for (let i = 0; i < Math.max(exp.length, act.length); i++) {
    const e = exp[i], a = act[i];
    const tr = el("tr", (e || "").trimEnd() !== (a || "").trimEnd() ? "mismatch" : "");
    tr.appendChild(el("td", "", String(i + 1)));
    tr.appendChild(el("td", "", e === undefined ? "(nothing)" : e));
    tr.appendChild(el("td", "", a === undefined ? "(nothing)" : a));
    table.appendChild(tr);
  }
  if (t.error) {
    const tr = el("tr", "mismatch");
    tr.appendChild(el("td", "", "!"));
    tr.appendChild(el("td", "", "(no error)"));
    tr.appendChild(el("td", "", `${t.error.type}: ${t.error.message}`));
    table.appendChild(tr);
  }
  const wrap = el("div");
  if (t.stdin) wrap.appendChild(el("div", "type", `Test ${r.focus_test + 1} - input given: ${t.stdin}`));
  wrap.appendChild(table);
  $("compare").replaceChildren(wrap);
}

// ---------- AI explanation --------------------------------------------------
async function explainStep() {
  if (cm.getValue() !== state.ranCode) await run();
  if (!state.result) return;
  $("explain").disabled = true;
  $("explanation").replaceChildren(el("div", "card", "Reading the trace…"));
  try {
    const r = await api("/api/explain", {
      exercise_id: state.ex.id, code: state.ranCode, session_id: sessionId,
      step: steps().length ? state.step : null, hint_level: state.hintLevel,
    });
    state.hintLevel++;
    const card = el("div", "card", r.explanation);
    const span = r.grounded_steps.length ? `steps ${r.grounded_steps[0]}-${r.grounded_steps[1]}` : "your program";
    const src = r.source === "nvidia" ? "AI tutor (NVIDIA)" : "built-in hint";
    card.appendChild(el("div", "meta", `Based on ${span} of the trace · ${src}`));
    $("explanation").replaceChildren(card);
  } catch (e) {
    $("explanation").replaceChildren(el("div", "card", "Could not get an explanation: " + e.message));
  } finally {
    $("explain").disabled = false;
  }
}

// ---------- wiring ----------------------------------------------------------
$("run").onclick = run;
$("reset").onclick = () => { cm.setValue(state.ex.starter); clearTrace(); setStatus("", "Code reset."); track("reset"); };
$("first").onclick = () => goTo(0);
$("prev").onclick = () => goTo(state.step - 1);
$("next").onclick = () => goTo(state.step + 1);
$("last").onclick = () => goTo(steps().length - 1);
$("slider").oninput = (e) => goTo(Number(e.target.value));
$("jump").onclick = () => {
  const d = state.result && state.result.divergence;
  if (d && d.step !== null) { goTo(d.step); track("jump_to_divergence", { step: d.step }); }
};
$("explain").onclick = explainStep;
document.addEventListener("keydown", (e) => {
  if (e.target.closest && (e.target.closest(".CodeMirror") || e.target.tagName === "INPUT")) return;
  if (e.key === "ArrowRight") goTo(state.step + 1);
  if (e.key === "ArrowLeft") goTo(state.step - 1);
});

init();
