/* polytess mobile mirror — vanilla JS, no build step. */
(function () {
  "use strict";
  const BASE = "__BASE__";
  const COLUMN = { pending: "backlog", stale: "backlog", failed: "backlog",
                   queued: "progress", active: "progress", done: "done" };
  const COLUMN_TITLE = { backlog: "Backlog", progress: "In Progress", done: "Done" };
  const STATUS_LABEL = { pending: "Backlog", queued: "Queued", active: "Running",
                         done: "Done", failed: "Failed", stale: "Outdated" };

  const $ = (id) => document.getElementById(id);
  let state = { flow: null, cards: [], summary: null, control: false };
  let logs = {};
  let selected = null;
  let ws = null, retry = 1000;
  let pendingChoice = null;

  // ---- helpers ------------------------------------------------------------ //
  function duration(s) {
    s = Math.max(0, Math.round(s || 0));
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
    if (h) return `${h} h ${String(m).padStart(2, "0")} min`;
    if (m) return `${m} min ${String(r).padStart(2, "0")} s`;
    return `${r} s`;
  }
  function card(guid) { return state.cards.find((c) => c.guid === guid); }
  function banner(text, bad) {
    const el = $("banner");
    el.textContent = text; el.className = "banner" + (bad ? " bad" : ""); el.hidden = false;
    clearTimeout(banner.t); banner.t = setTimeout(() => (el.hidden = true), 4000);
  }
  function buzz(bad) {
    try { if (navigator.vibrate) navigator.vibrate(bad ? [120, 80, 120] : [60]); } catch (e) {}
    try {
      const ctx = buzz.ctx || (buzz.ctx = new (window.AudioContext || window.webkitAudioContext)());
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.frequency.value = bad ? 220 : 660; g.gain.value = 0.04;
      o.connect(g); g.connect(ctx.destination); o.start(); o.stop(ctx.currentTime + 0.15);
    } catch (e) {}
  }
  async function post(path, body) {
    const r = await fetch(BASE + path, { method: "POST", headers: { "Content-Type": "application/json" },
                                         body: JSON.stringify(body || {}) });
    if (r.status === 403) { banner("Control from phone is off in the Viewer", true); return null; }
    if (!r.ok) { banner("Request failed: " + r.status, true); return null; }
    return r.json();
  }

  // ---- rendering ------------------------------------------------------------- //
  function render() {
    $("flow-name").textContent = state.flow || "No process open";
    $("empty").hidden = !!state.flow;
    $("overview").hidden = !state.flow;
    const board = $("board");
    board.innerHTML = "";
    if (!state.flow) return;
    const groups = { backlog: [], progress: [], done: [] };
    state.cards.forEach((c) => groups[COLUMN[c.status] || "backlog"].push(c));
    ["progress", "backlog", "done"].forEach((col) => {
      const h = document.createElement("h3");
      h.className = "column"; h.textContent = `${COLUMN_TITLE[col]} · ${groups[col].length}`;
      board.appendChild(h);
      groups[col].sort((a, b) => a.level - b.level || a.title.localeCompare(b.title))
        .forEach((c) => board.appendChild(cardEl(c)));
    });
    renderSummary();
    $("global-actions").hidden = !state.control;
    if (selected) renderDetail();
  }
  function cardEl(c) {
    const el = document.createElement("div");
    el.className = "card"; el.dataset.guid = c.guid;
    el.style.setProperty("--stripe", `var(--${c.status})`);
    let foot = "";
    if (c.status === "done" && c.duration) foot = "✔ " + duration(c.duration);
    else if (c.status === "failed") foot = "✖ " + (c.error || "failed");
    else if (c.status === "stale") foot = "inputs changed — run again";
    else if (c.status === "queued") foot = "waiting for predecessors…";
    else if (c.status === "active") foot = c.step || "running…";
    else if (c.blocked_by && c.blocked_by.length) foot = "after: " + c.blocked_by.join(", ");
    el.innerHTML = `<div class="row"><div class="title"></div><div class="pill">${STATUS_LABEL[c.status]}</div></div>
      <p class="desc"></p>${c.status === "active" ? `<div class="progress"><i style="width:${Math.round((c.progress || 0) * 100)}%"></i></div>` : ""}
      <div class="foot${c.status === "failed" ? " bad" : ""}"></div>`;
    el.querySelector(".title").textContent = c.title;
    el.querySelector(".desc").textContent = c.description || "";
    el.querySelector(".foot").textContent = foot;
    el.addEventListener("click", () => { selected = c.guid; openDetail(); });
    return el;
  }
  function renderSummary() {
    const s = state.summary; if (!s) return;
    const done = s.counts.done, total = s.total;
    const bar = $("ring-bar");
    bar.style.strokeDashoffset = String(264 - 264 * (total ? done / total : 0));
    bar.classList.toggle("full", total && done === total);
    $("ring-text").textContent = `${done} / ${total}`;
    $("f-done").textContent = done;
    $("f-active").textContent = s.counts.active + s.counts.queued;
    $("f-backlog").textContent = s.counts.pending + s.counts.stale;
    $("f-failed").textContent = s.counts.failed;
    $("f-remaining").textContent = s.estimated_remaining ? duration(s.estimated_remaining)
      : (total && done === total ? "nothing left" : "no data yet");
    $("f-streak").textContent = s.streak ? `${s.streak} without failure` : "–";
  }

  // ---- detail sheet ------------------------------------------------------------ //
  async function openDetail() {
    $("detail").hidden = false;
    if (!logs[selected]) {
      try { const r = await fetch(`${BASE}/api/log/${selected}`); logs[selected] = (await r.json()).lines; }
      catch (e) { logs[selected] = []; }
    }
    renderDetail();
  }
  function renderDetail() {
    const c = card(selected); if (!c) { closeDetail(); return; }
    $("d-title").textContent = c.title;
    const pill = $("d-status"); pill.textContent = STATUS_LABEL[c.status];
    pill.style.setProperty("--stripe", `var(--${c.status})`);
    $("d-desc").textContent = c.description || "";
    const meta = [];
    if (c.predecessors.length) meta.push("After: " + c.predecessors.join(", "));
    if (c.status === "active") meta.push("Current step: " + (c.step || "…"));
    if (c.duration && c.status === "done") meta.push("Last run " + duration(c.duration));
    if (c.error) meta.push("Error: " + c.error);
    $("d-meta").textContent = meta.join(" · ");
    const actions = $("d-actions"); actions.innerHTML = "";
    if (state.control) {
      if (["pending", "stale", "failed", "done"].includes(c.status)) {
        const b = document.createElement("button"); b.className = "primary";
        b.textContent = c.status === "done" ? "Run again" : "Start";
        b.onclick = () => startCard(c.guid, null); actions.appendChild(b);
      }
      if (c.status === "active" || c.status === "queued") {
        const b = document.createElement("button"); b.className = "danger"; b.textContent = "Stop";
        b.onclick = () => post(`/api/cards/${c.guid}/stop`); actions.appendChild(b);
      }
    }
    const log = $("d-log");
    const lines = logs[selected] || [];
    log.innerHTML = lines.slice(-80).map((l) =>
      `<span class="t">${l.t}</span> <span class="${l.level}">${esc(l.text)}</span>`).join("\n")
      || "<span class='t'>no log yet</span>";
    log.scrollTop = log.scrollHeight;
  }
  function esc(s) { return String(s).replace(/[&<>]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[ch])); }
  function closeDetail() { $("detail").hidden = true; selected = null; }

  async function startCard(guid, mode) {
    const result = await post(`/api/cards/${guid}/start`, { mode });
    if (!result) return;
    if (result.needs_choice) {
      pendingChoice = guid;
      $("choice-text").textContent = "Before this step, these must run first: " + result.needs_choice.join(", ");
      $("choice").hidden = false;
      return;
    }
    if (result.ok) closeDetail();
  }

  // ---- events ------------------------------------------------------------------ //
  function apply(msg) {
    if (msg.type === "flow") {
      state = { flow: msg.flow, cards: msg.cards || [], summary: msg.summary, control: !!msg.control };
      logs = {}; render(); return;
    }
    if (msg.type === "control") { state.control = msg.control; render(); return; }
    const c = card(msg.guid);
    if (msg.type === "card") {
      const was = c ? c.status : null;
      if (c) { c.status = msg.status; c.duration = msg.duration; c.error = msg.error;
               if (msg.status !== "active") { c.progress = 0; c.step = ""; } }
      state.cards.forEach((k) => { if (msg.blocked && msg.blocked[k.guid]) k.blocked_by = msg.blocked[k.guid]; });
      state.summary = msg.summary || state.summary;
      render();
      if (c && was !== msg.status) {
        if (msg.status === "done") {
          banner(`${c.title} finished · ${duration(msg.duration)}`); buzz(false);
          const el = document.querySelector(`.card[data-guid="${c.guid}"]`); if (el) el.classList.add("flash");
          if (state.summary && state.summary.counts.done === state.summary.total)
            setTimeout(() => banner(`${state.flow}: everything done 🎉`), 1200);
        } else if (msg.status === "failed") { banner(`${c.title} failed`, true); buzz(true); }
      }
      return;
    }
    if (msg.type === "progress" && c) {
      c.progress = msg.progress; c.step = msg.step;
      const el = document.querySelector(`.card[data-guid="${c.guid}"] .progress i`);
      if (el) el.style.width = Math.round(msg.progress * 100) + "%";
      const foot = document.querySelector(`.card[data-guid="${c.guid}"] .foot`);
      if (foot && c.status === "active") foot.textContent = msg.step || "running…";
      if (selected === c.guid) renderDetail();
      return;
    }
    if (msg.type === "log") {
      (logs[msg.guid] = logs[msg.guid] || []).push({ t: msg.t, level: msg.level, text: msg.text });
      if (logs[msg.guid].length > 200) logs[msg.guid].shift();
      if (selected === msg.guid) renderDetail();
    }
  }
  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}${BASE}/api/events`);
    ws.onopen = () => { $("conn").classList.add("on"); retry = 1000; };
    ws.onmessage = (e) => { try { apply(JSON.parse(e.data)); } catch (err) { console.error(err); } };
    ws.onclose = () => { $("conn").classList.remove("on"); setTimeout(connect, retry); retry = Math.min(retry * 2, 10000); };
    ws.onerror = () => ws.close();
  }

  // ---- wiring ---------------------------------------------------------------- //
  $("d-close").onclick = closeDetail;
  $("detail").addEventListener("click", (e) => { if (e.target === $("detail")) closeDetail(); });
  $("run-all").onclick = () => post("/api/run-all");
  $("choice-order").onclick = () => { $("choice").hidden = true; startCard(pendingChoice, "in_order"); };
  $("choice-only").onclick = () => { $("choice").hidden = true; startCard(pendingChoice, "only"); };
  $("choice-cancel").onclick = () => { $("choice").hidden = true; pendingChoice = null; };
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && (!ws || ws.readyState > 1)) connect();
  });
  fetch(`${BASE}/api/board`).then((r) => r.json()).then((d) => apply({ type: "flow", ...d })).catch(() => {});
  connect();
})();
