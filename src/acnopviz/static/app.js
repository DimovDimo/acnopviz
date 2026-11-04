/* acnopviz dashboard — no external runtime dependencies. */
"use strict";
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const state = { view: "overview", overview: null, recs: [], tx: { type: "all", search: "", offset: 0, limit: 25 }, scenario: null, importBundle: null };
const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const money2 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const pct = (x, d = 1) => `${(x * 100).toFixed(d)}%`;
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, options = {}) {
  const res = await fetch(path, { headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try { const body = await res.json(); detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail); } catch { /* ignore */ }
    throw new Error(detail);
  }
  return res.json();
}
function showAlert(err) { const el = $("#alert"); el.textContent = err.message || String(err); el.hidden = false; }
function toast(msg) { const el = $("#toast"); el.textContent = msg; el.hidden = false; clearTimeout(toast.t); toast.t = setTimeout(() => { el.hidden = true; }, 3000); }
function kindLabel(k) { return ({ collection: "Collections", duplicate: "Duplicate control", discount: "Payment terms", expense: "Expense drift", liquidity: "Liquidity" })[k] || k; }
function statusTag(s) { const cls = s === "accepted" ? "ok" : s === "dismissed" ? "danger" : "gray"; return `<span class="tag ${cls}">${esc(s)}</span>`; }

function lineChart(series, keys, labels, colors, height = 220) {
  const w = 720, h = height, pad = { l: 62, r: 16, t: 16, b: 34 };
  const vals = series.flatMap(d => keys.map(k => Number(d[k]) || 0));
  let min = Math.min(0, ...vals), max = Math.max(1, ...vals);
  if (max === min) max = min + 1;
  const x = i => pad.l + (series.length < 2 ? 0 : i * (w - pad.l - pad.r) / (series.length - 1));
  const y = v => pad.t + (max - v) * (h - pad.t - pad.b) / (max - min);
  let svg = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(labels.join(", "))} trend chart">`;
  for (let g = 0; g <= 4; g++) { const v = min + (max - min) * g / 4; const yy = y(v); svg += `<line x1="${pad.l}" y1="${yy}" x2="${w - pad.r}" y2="${yy}" stroke="#e5ebee"/><text x="${pad.l - 8}" y="${yy + 4}" text-anchor="end">${esc(money.format(v))}</text>`; }
  keys.forEach((k, ki) => { const pts = series.map((d, i) => `${x(i)},${y(Number(d[k]) || 0)}`).join(" "); svg += `<polyline points="${pts}" fill="none" stroke="${colors[ki]}" stroke-width="2.5"/>`; });
  const step = Math.max(1, Math.ceil(series.length / 6));
  series.forEach((d, i) => {
    if (i % step !== 0 && i !== series.length - 1) return;
    const last = i === series.length - 1, first = i === 0;
    const anchor = last ? "end" : first ? "start" : "middle";
    const tx = last ? w - 4 : first ? pad.l : x(i);
    svg += `<text x="${tx}" y="${h - 10}" text-anchor="${anchor}">${esc(d.month || d.label || i + 1)}</text>`;
  });
  return svg + "</svg>";
}
function bandChart(sim) {
  const base = sim.baseline, sc = sim.scenario, w = 720, h = 250, pad = { l: 64, r: 16, t: 16, b: 34 };
  const all = [...base.p10, ...base.p90, ...sc.p10, ...sc.p90, 0];
  const min = Math.min(...all), max = Math.max(...all) || 1;
  const x = i => pad.l + i * (w - pad.l - pad.r) / Math.max(1, base.months.length - 1);
  const y = v => pad.t + (max - v) * (h - pad.t - pad.b) / (max - min || 1);
  const path = arr => arr.map((v, i) => `${i ? "L" : "M"}${x(i)},${y(v)}`).join(" ");
  const band = (lo, hi) => `${path(hi)} ${[...lo].reverse().map((v, i) => `L${x(lo.length - 1 - i)},${y(v)}`).join(" ")} Z`;
  let svg = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Baseline and scenario cash balance quantiles"><line x1="${pad.l}" y1="${y(0)}" x2="${w - pad.r}" y2="${y(0)}" stroke="#94a3b8" stroke-dasharray="4 4"/>`;
  svg += `<path d="${band(sc.p10, sc.p90)}" fill="#ccfbf1" opacity="0.7"/><path d="${path(base.p50)}" fill="none" stroke="#94a3b8" stroke-width="2" stroke-dasharray="5 4"/><path d="${path(sc.p50)}" fill="none" stroke="#0f766e" stroke-width="3"/>`;
  base.months.forEach((m, i) => { const last = i === base.months.length - 1; svg += `<text x="${last ? w - 4 : x(i)}" y="${h - 10}" text-anchor="${last ? "end" : "middle"}">M${m}</text>`; });
  for (let g = 0; g <= 4; g++) { const v = min + (max - min) * g / 4; svg += `<text x="${pad.l - 8}" y="${y(v) + 4}" text-anchor="end">${esc(money.format(v))}</text>`; }
  return svg + "</svg>";
}
function agingBars(aging) {
  const entries = [["Current", aging.current], ["1–30 days", aging["1_30"]], ["31–60 days", aging["31_60"]], ["61–90 days", aging["61_90"]], ["90+ days", aging["90_plus"]]];
  const max = Math.max(1, ...entries.map(e => e[1]));
  return `<div class="bars">${entries.map(([label, val]) => `<div class="bar-row"><span>${label}</span><svg viewBox="0 0 300 14" class="chart" role="img" aria-label="${label}: ${esc(money2.format(val))}"><rect width="300" height="14" rx="7" fill="#eef2f4"/><rect width="${Math.max(2, val / max * 300)}" height="14" rx="7" fill="#0f766e"/></svg><span class="num">${esc(money.format(val))}</span></div>`).join("")}</div>`;
}

async function loadOverview() {
  const o = await api("/api/overview"); state.overview = o;
  $("#as-of").textContent = `As of ${o.as_of}`;
  $("#nav-rec-count").textContent = o.recommendation_count;
  const netClass = o.last_month_net >= 0 ? "positive" : "negative";
  $("#view-overview").innerHTML = `
    <p class="section-intro">A transparent review queue for working-capital and cost signals. Every suggestion includes evidence, assumptions, and a human decision step.</p>
    <div class="grid kpis">
      <div class="card"><div class="kpi-label">Cash balance</div><div class="kpi-value">${money.format(o.cash)}</div><div class="kpi-foot">Opening cash + settled transactions</div></div>
      <div class="card"><div class="kpi-label">Overdue receivables</div><div class="kpi-value">${money.format(o.overdue_ar)}</div><div class="kpi-foot">${o.overdue_ar_count} open overdue invoices</div></div>
      <div class="card"><div class="kpi-label">Open payables</div><div class="kpi-value">${money.format(o.open_ap)}</div><div class="kpi-foot">${o.open_ap_count} unpaid bills · ${o.overdue_ap_count} overdue</div></div>
      <div class="card"><div class="kpi-label">Last month net cash</div><div class="kpi-value ${netClass}">${money.format(o.last_month_net)}</div><div class="kpi-foot">Receipts ${money.format(o.last_month_receipts)} · payments ${money.format(o.last_month_payments)}</div></div>
    </div>
    <div class="grid two mt16">
      <div class="card"><h2>Monthly operating cash flow</h2>${lineChart(o.monthly_series, ["receipts", "payments", "net"], ["Receipts", "Payments", "Net"], ["#0f766e", "#f59e0b", "#334155"])}<div class="legend"><span><i class="dot p50"></i>Receipts</span><span><i class="dot amber"></i>Payments</span><span><i class="dot base"></i>Net</span></div></div>
      <div class="card"><h2>Receivables aging</h2>${agingBars(o.aging)}<p class="muted">Open invoice balances by days past due. Aging is exposure, not expected credit loss.</p></div>
    </div>
    <div class="card mt16"><h2>Review queue</h2><p class="muted">${o.recommendation_count} suggestions · data quality: ${esc(o.data_quality)}. Open Recommendations to inspect evidence and record a decision.</p><button class="button" data-go="recommendations">Open recommendations</button></div>`;
  $("[data-go]", $("#view-overview")).addEventListener("click", () => switchView("recommendations"));
}

function recCard(r) {
  return `<article class="rec" data-rec-id="${esc(r.id)}">
    <div class="rec-head"><div><h3>${esc(r.title)}</h3><div class="muted">${esc(r.entity)}</div>
      <div class="rec-meta"><span class="tag">${esc(kindLabel(r.kind))}</span><span class="tag warn">${esc(r.confidence)}</span>${statusTag(r.review_status)}</div></div>
      <div class="rec-value"><strong>${money2.format(r.estimated_value)}</strong><small>${esc(r.value_label)}</small></div></div>
    <p>${esc(r.summary)}</p><p><strong>Action:</strong> ${esc(r.action)}</p>
    <details><summary>Evidence, method & assumptions</summary><div class="evidence">
      <div><h3>Method</h3><p>${esc(r.method)}</p><h3>Assumptions</h3><ul>${r.assumptions.map(a => `<li>${esc(a)}</li>`).join("")}</ul></div>
      <div><h3>Evidence</h3><pre>${esc(JSON.stringify(r.evidence, null, 2))}</pre></div></div></details>
    <div class="review-row"><label>Status<select class="review-status"><option value="new" ${r.review_status === "new" ? "selected" : ""}>New</option><option value="accepted" ${r.review_status === "accepted" ? "selected" : ""}>Accepted</option><option value="dismissed" ${r.review_status === "dismissed" ? "selected" : ""}>Dismissed</option></select></label>
      <label class="review-note-label">Reviewer note<textarea class="review-note" maxlength="1000" placeholder="Context, decision rationale, follow-up…">${esc(r.review_note)}</textarea></label>
      <button class="button small save-review">Save review</button></div></article>`;
}
async function loadRecommendations() {
  const data = await api("/api/recommendations"); state.recs = data.items;
  const kinds = [...new Set(data.items.map(r => r.kind))];
  $("#view-recommendations").innerHTML = `<p class="section-intro">${esc(data.disclaimer)}</p>
    <div class="toolbar"><label>Kind<select id="rec-kind"><option value="all">All kinds</option>${kinds.map(k => `<option value="${k}">${esc(kindLabel(k))}</option>`).join("")}</select></label>
    <label>Status<select id="rec-status"><option value="all">All statuses</option><option value="new">New</option><option value="accepted">Accepted</option><option value="dismissed">Dismissed</option></select></label>
    <a class="button secondary" href="/api/export/recommendations.csv">Export CSV</a><span class="muted" id="rec-count"></span></div><div id="rec-list" class="rec-list"></div>`;
  $("#rec-kind").addEventListener("change", renderRecList); $("#rec-status").addEventListener("change", renderRecList);
  renderRecList();
}
function renderRecList() {
  const kind = $("#rec-kind").value, status = $("#rec-status").value;
  const items = state.recs.filter(r => (kind === "all" || r.kind === kind) && (status === "all" || r.review_status === status));
  $("#rec-count").textContent = `${items.length} shown`;
  $("#rec-list").innerHTML = items.length ? items.map(recCard).join("") : `<div class="card empty">No recommendations match these filters.</div>`;
  $$(".rec", $("#rec-list")).forEach(card => {
    $(".save-review", card).addEventListener("click", async () => {
      const id = card.dataset.recId;
      try {
        const updated = await api(`/api/recommendations/${encodeURIComponent(id)}/review`, { method: "PATCH", body: JSON.stringify({ status: $(".review-status", card).value, note: $(".review-note", card).value }) });
        const rec = state.recs.find(r => r.id === id); Object.assign(rec, { review_status: updated.status, review_note: updated.note, review_updated_at: updated.updated_at });
        toast("Review saved to audit trail"); renderRecList();
      } catch (e) { showAlert(e); }
    });
  });
}

async function loadScenario() {
  $("#view-scenario").innerHTML = `<p class="section-intro">Stress-test liquidity with a seeded moving-block bootstrap. Scenario levers are illustrative assumptions, not forecasts or guaranteed savings.</p>
    <div class="card"><form id="scenario-form">
      <div class="range-row"><label for="financing_rate">Financing APR</label><input id="financing_rate" name="financing_rate" type="range" min="0" max="0.5" step="0.005" value="0.08"><output id="financing_rate_out">8.0%</output></div>
      <div class="range-row"><label for="recovery_uplift">One-time overdue recovery uplift</label><input id="recovery_uplift" name="recovery_uplift" type="range" min="0" max="0.5" step="0.01" value="0"><output id="recovery_uplift_out">0%</output></div>
      <div class="range-row"><label for="expense_reduction">Recurring expense reduction</label><input id="expense_reduction" name="expense_reduction" type="range" min="0" max="0.3" step="0.005" value="0"><output id="expense_reduction_out">0.0%</output></div>
      <div class="range-row"><label for="horizon">Horizon (months)</label><input id="horizon" name="horizon" type="range" min="1" max="12" step="1" value="6"><output id="horizon_out">6</output></div>
      <button class="button" type="submit">Run scenario</button></form></div><div id="scenario-result" class="scenario-result"></div>`;
  const form = $("#scenario-form");
  $$("input", form).forEach(input => input.addEventListener("input", () => { const out = $(`#${input.id}_out`); out.textContent = input.id === "horizon" ? input.value : pct(Number(input.value), input.id === "recovery_uplift" ? 0 : 1); }));
  form.addEventListener("submit", e => { e.preventDefault(); runScenario().catch(showAlert); });
  await runScenario();
}
async function runScenario() {
  const form = $("#scenario-form");
  const body = { financing_rate: Number(form.financing_rate.value), recovery_uplift: Number(form.recovery_uplift.value), expense_reduction: Number(form.expense_reduction.value), horizon: Number(form.horizon.value) };
  const sim = await api("/api/scenario", { method: "POST", body: JSON.stringify(body) }); state.scenario = sim;
  const b = sim.baseline, s = sim.scenario;
  $("#scenario-result").innerHTML = `<div class="grid kpis">
    <div class="card"><div class="kpi-label">Baseline P(negative)</div><div class="kpi-value">${pct(b.prob_negative)}</div><div class="kpi-foot">Any month-end below zero</div></div>
    <div class="card"><div class="kpi-label">Scenario P(negative)</div><div class="kpi-value">${pct(s.prob_negative)}</div><div class="kpi-foot">With selected levers</div></div>
    <div class="card"><div class="kpi-label">Scenario median ending cash</div><div class="kpi-value">${money.format(s.median_ending_cash)}</div><div class="kpi-foot">Baseline ${money.format(b.median_ending_cash)}</div></div>
    <div class="card"><div class="kpi-label">Scenario reserve (90% paths)</div><div class="kpi-value">${money.format(s.reserve_for_90pct_paths)}</div><div class="kpi-foot">Additional buffer illustration</div></div></div>
    <div class="card mt16"><h2>Cash balance quantiles</h2>${bandChart(sim)}<div class="legend"><span><i class="dot base"></i>Baseline median</span><span><i class="dot p50"></i>Scenario median</span><span><i class="dot p90"></i>Scenario P10–P90 band</span></div></div>
    <div class="card mt16"><h2>Assumptions</h2><ul>${sim.assumptions.map(a => `<li>${esc(a)}</li>`).join("")}</ul><p class="muted">${s.paths.toLocaleString()} paths · block length ${s.block} months · seed ${s.seed} · ${s.observations} historical months.</p></div>`;
}

async function loadTransactions() {
  const t = state.tx;
  const data = await api(`/api/transactions?type=${t.type}&search=${encodeURIComponent(t.search)}&limit=${t.limit}&offset=${t.offset}`);
  $("#view-transactions").innerHTML = `<p class="section-intro">Browse the synthetic AR, AP, and cash ledger. Amounts are signed for cash; AP documents are shown as negative exposure.</p>
    <div class="toolbar"><label>Type<select id="tx-type"><option value="all">All</option><option value="ar">AR invoices</option><option value="ap">AP bills</option><option value="cash">Cash</option></select></label>
    <label>Search<input id="tx-search" type="search" maxlength="100" placeholder="ID, party, description…" value="${esc(t.search)}"></label>
    <button class="button secondary" id="tx-apply">Apply</button><a class="button secondary" href="/api/export/transactions.csv">Export CSV</a><span class="muted">${data.total} rows</span></div>
    <div class="table-wrap"><table><thead><tr><th>ID</th><th>Type</th><th>Date</th><th>Party</th><th>Description</th><th class="num">Amount</th><th>Status</th></tr></thead><tbody>
    ${data.items.map(r => `<tr><td>${esc(r.id)}</td><td>${esc(r.type)}</td><td>${esc(r.date)}</td><td>${esc(r.party)}</td><td>${esc(r.description)}</td><td class="num ${r.amount < 0 ? "negative" : ""}">${money2.format(r.amount)}</td><td>${esc(r.status)}</td></tr>`).join("") || `<tr><td colspan="7" class="empty">No rows.</td></tr>`}</tbody></table></div>
    <div class="pagination"><button class="button secondary small" id="tx-prev" ${t.offset === 0 ? "disabled" : ""}>Previous</button><span class="muted">${data.total ? t.offset + 1 : 0}–${Math.min(t.offset + t.limit, data.total)} of ${data.total}</span><button class="button secondary small" id="tx-next" ${t.offset + t.limit >= data.total ? "disabled" : ""}>Next</button></div>`;
  $("#tx-type").value = t.type;
  $("#tx-apply").addEventListener("click", () => { state.tx.type = $("#tx-type").value; state.tx.search = $("#tx-search").value; state.tx.offset = 0; loadTransactions().catch(showAlert); });
  $("#tx-search").addEventListener("keydown", e => { if (e.key === "Enter") $("#tx-apply").click(); });
  $("#tx-prev").addEventListener("click", () => { state.tx.offset = Math.max(0, t.offset - t.limit); loadTransactions().catch(showAlert); });
  $("#tx-next").addEventListener("click", () => { state.tx.offset = t.offset + t.limit; loadTransactions().catch(showAlert); });
}

async function loadQuality() {
  const [q, m] = await Promise.all([api("/api/data-quality"), api("/api/dataset/manifest")]);
  $("#view-quality").innerHTML = `<p class="section-intro">Automated integrity checks plus intentionally planted review candidates. A warning is not a failed ledger reconciliation.</p>
    <div class="grid two"><div class="card"><h2>Checks (${q.passed} pass · ${q.warnings} warn · ${q.failed} fail)</h2>${q.checks.map(c => `<div class="check"><span class="check-icon ${c.status}">${c.status === "pass" ? "✓" : c.status === "warn" ? "!" : "✕"}</span><div><strong>${esc(c.name)}</strong><div class="muted">${esc(c.detail)}</div></div></div>`).join("")}</div>
    <div class="card"><h2>Synthetic manifest</h2><pre class="formula">${esc(JSON.stringify(m, null, 2))}</pre><p class="muted">Regenerate with <code>acnopviz seed --replace</code>. The seed and as-of date make the dataset reproducible.</p></div></div>`;
}
async function loadAudit() {
  const data = await api("/api/audit");
  const detailText = (a) => {
    const d = a.detail || {};
    if (a.event_type === "recommendation.review") return `Status: ${esc(d.status ?? "unknown")}${d.note ? ` · Note: ${esc(d.note)}` : ""}`;
    if (a.event_type === "dataset.import") return `As of ${esc(d.as_of ?? "unknown")} · Fingerprint ${esc(d.fingerprint ?? a.entity_id)} · Rows ${esc(JSON.stringify(d.counts ?? {}))}`;
    return esc(JSON.stringify(d));
  };
  $("#view-audit").innerHTML = `<p class="section-intro">Local review decisions and dataset imports are persisted in SQLite and appended to an audit trail. This is a demo audit log, not a tamper-proof compliance archive.</p><div class="card">${data.items.length ? data.items.map(a => `<div class="audit-item"><time>${esc(a.created_at)}</time><div><strong>${esc(a.event_type)}</strong> · ${esc(a.entity_id)}</div><div class="muted">${detailText(a)}</div></div>`).join("") : `<div class="empty">No audit events yet.</div>`}</div>`;
}
function loadMethod() {
  $("#view-method").innerHTML = `<p class="section-intro">Statistical signals are separated from deterministic controls. None of these methods proves fraud, default, or achievable savings.</p>
  <div class="method-grid">
    <div class="card"><h3>Collections — Wilson interval</h3><p>Late-payment proportion per customer on matured invoices, with a 95% Wilson score interval. Flag when the lower bound exceeds the portfolio baseline and overdue exposure exists.</p><div class="formula">p̂ = late / matured; Wilson 95% CI; compare lower bound with baseline</div></div>
    <div class="card"><h3>Duplicates — exact control match</h3><p>Vendor + normalized invoice number + amount, with issue dates within 14 days. Candidates require source-document review.</p><div class="formula">key = (vendor, normalize(number), amount_cents)</div></div>
    <div class="card"><h3>Payment terms — discount yield</h3><p>Compare simple annualized discount yield with financing APR and compute dollar net benefit after financing cost and cash-buffer check.</p><div class="formula">yield = d/(1-d) × 365/(net_days − discount_days)</div></div>
    <div class="card"><h3>Expense drift — robust trend</h3><p>Theil–Sen slope with 95% CI, two-sided Kendall tau, Holm adjustment across categories, and a minimum 15% relative drift.</p><div class="formula">flag: slope &gt; 0, CI low &gt; 0, Holm p &lt; .05, relative drift ≥ 15%</div></div>
    <div class="card"><h3>Liquidity — moving-block bootstrap</h3><p>Resample 3-month blocks of historical net operating cash flow. Report probability of any negative month-end balance and reserve for the 10th-percentile minimum balance.</p><div class="formula">paths = 2,000; block = 3; quantiles = P10/P50/P90</div></div>
    <div class="card"><h3>Governance</h3><p>Human review only; no automatic payments or journal entries. Synthetic data, fixed as-of date, reproducible seed, and explicit assumptions. Production use requires real-data validation and accounting policy review.</p></div>
  </div>`;
}


async function loadCalendar() {
  $("#view-calendar").innerHTML = `<p class="section-intro">Committed runoff calendar: schedules open AR/AP and resamples only unlinked recurring cash flows. It does not create new sales or purchases.</p>
    <div class="toolbar"><label>Horizon<select id="cal-horizon">${[3,6,9,12].map(h=>`<option value="${h}" ${h===6?"selected":""}>${h} months</option>`).join("")}</select></label><button class="button" id="cal-run">Refresh</button></div><div id="cal-result"><div class="loading">Loading…</div></div>`;
  $("#cal-run").addEventListener("click", () => runCalendar().catch(showAlert)); $("#cal-horizon").addEventListener("change", () => runCalendar().catch(showAlert));
  await runCalendar();
}
async function runCalendar() {
  const h = Number($("#cal-horizon").value);
  const c = await api(`/api/cash-calendar?horizon=${h}`);
  $("#cal-result").innerHTML = `<div class="grid kpis">
    <div class="card"><div class="kpi-label">P(negative month-end)</div><div class="kpi-value">${pct(c.prob_negative)}</div><div class="kpi-foot">${c.paths.toLocaleString()} seeded paths</div></div>
    <div class="card"><div class="kpi-label">Reserve (90% paths)</div><div class="kpi-value">${money.format(c.reserve_for_90pct_paths)}</div><div class="kpi-foot">Additional buffer illustration</div></div>
    <div class="card"><div class="kpi-label">Open AR scheduled</div><div class="kpi-value">${money.format(c.totals.ar_scheduled)}</div><div class="kpi-foot">Total open ${money.format(c.totals.open_ar)}</div></div>
    <div class="card"><div class="kpi-label">Open AP scheduled</div><div class="kpi-value">${money.format(c.totals.ap_scheduled)}</div><div class="kpi-foot">Total open ${money.format(c.totals.open_ap)}</div></div></div>
    <div class="card mt16"><h2>Ending cash quantiles</h2>${lineChart(c.months, ["p10_ending_cash","p50_ending_cash","p90_ending_cash"], ["P10","P50","P90"], ["#99f6e4","#0f766e","#ccfbf1"], 240)}</div>
    <div class="table-wrap mt16"><table><thead><tr><th>Month</th><th class="num">AR receipts</th><th class="num">AP payments</th><th class="num">Recurring net</th><th class="num">Expected net</th><th class="num">Expected ending</th><th class="num">P10 ending</th><th class="num">P90 ending</th></tr></thead><tbody>
    ${c.months.map(m=>`<tr><td>${esc(m.month)}</td><td class="num">${money.format(m.ar_receipts)}</td><td class="num">${money.format(m.ap_payments)}</td><td class="num">${money.format(m.recurring_net)}</td><td class="num">${money.format(m.expected_net)}</td><td class="num">${money.format(m.expected_ending_cash)}</td><td class="num">${money.format(m.p10_ending_cash)}</td><td class="num">${money.format(m.p90_ending_cash)}</td></tr>`).join("")}</tbody></table></div>
    <div class="card mt16"><h2>Assumptions</h2><ul>${c.assumptions.map(a=>`<li>${esc(a)}</li>`).join("")}</ul></div>`;
}
async function loadBacktest() {
  $("#view-backtest").innerHTML = `<p class="section-intro">Expanding-window walk-forward validation of the historical monthly liquidity model. Synthetic-only; overlapping folds are not independent.</p>
    <div class="toolbar"><label>Horizon<select id="bt-horizon">${[1,2,3,6].map(h=>`<option value="${h}" ${h===3?"selected":""}>${h} months</option>`).join("")}</select></label>
    <label>Min train months<input id="bt-min" type="number" min="6" max="36" value="9"></label><button class="button" id="bt-run">Run backtest</button></div><div id="bt-result"><div class="loading">Loading…</div></div>`;
  $("#bt-run").addEventListener("click", () => runBacktest().catch(showAlert)); await runBacktest();
}
async function runBacktest() {
  const h = Number($("#bt-horizon").value), min = Number($("#bt-min").value);
  const b = await api(`/api/backtest?horizon=${h}&min_train=${min}`);
  if (b.status !== "ok") { $("#bt-result").innerHTML = `<div class="card empty">Insufficient history for these settings.</div>`; return; }
  $("#bt-result").innerHTML = `<div class="grid kpis">
    <div class="card"><div class="kpi-label">Bootstrap MAE</div><div class="kpi-value">${money.format(b.bootstrap.mae)}</div><div class="kpi-foot">Naive last ${money.format(b.naive_last.mae)}</div></div>
    <div class="card"><div class="kpi-label">P10–P90 coverage</div><div class="kpi-value">${pct(b.bootstrap.coverage_p10_p90)}</div><div class="kpi-foot">Target 80% · ${b.fold_count} folds</div></div>
    <div class="card"><div class="kpi-label">Bias</div><div class="kpi-value">${money.format(b.bootstrap.bias)}</div><div class="kpi-foot">Predicted minus actual cumulative net</div></div>
    <div class="card"><div class="kpi-label">Lower MAE</div><div class="kpi-value">${esc(b.lower_mae_model)}</div><div class="kpi-foot">RMSE ${money.format(b.bootstrap.rmse)}</div></div></div>
    <div class="table-wrap mt16"><table><thead><tr><th>Origin</th><th>Train months</th><th>Test months</th><th class="num">Bootstrap MAE</th><th class="num">Naive MAE</th><th class="num">Coverage</th></tr></thead><tbody>
    ${b.folds.map(f=>`<tr><td>${esc(f.origin_month)}</td><td>${f.train_months}</td><td>${esc(f.test_months.join(", "))}</td><td class="num">${money.format(f.bootstrap_metrics.mae)}</td><td class="num">${money.format(f.naive_metrics.mae)}</td><td class="num">${pct(f.bootstrap_metrics.coverage_p10_p90)}</td></tr>`).join("")}</tbody></table></div>
    <div class="card mt16"><h2>Limitations</h2><ul>${b.limitations.map(l=>`<li>${esc(l)}</li>`).join("")}</ul></div>`;
}
function loadImport() {
  const tables = ["customers","vendors","invoices","bills","cash_transactions"];
  $("#view-import").innerHTML = `<p class="section-intro">Replace the demo ledger with a validated synthetic CSV bundle. Validation is read-only; commit requires confirmation and replaces ledger/review state atomically.</p>
    <div class="card"><div class="toolbar"><button class="button secondary" id="imp-template">Download template</button></div>
    <div class="grid two"><label>manifest.json<input id="imp-manifest" type="file" accept=".json,application/json"></label>
    ${tables.map(t=>`<label>${t}.csv<input id="imp-${t}" type="file" accept=".csv,text/csv" data-table="${t}"></label>`).join("")}</div>
    <div class="toolbar mt16"><button class="button" id="imp-validate">Validate bundle</button><label class="check"><input id="imp-confirm" type="checkbox"> I understand this replaces the ledger and clears reviews</label><button class="button danger" id="imp-commit" disabled>Commit replace</button></div></div>
    <div id="imp-result" class="mt16"></div>`;
  const invalidateImport = () => { state.importBundle = null; $("#imp-commit").disabled = true; $("#imp-result").innerHTML = `<div class="card muted">Bundle changed. Validate again before committing.</div>`; };
  $$('input[type="file"]', $("#view-import")).forEach(input => input.addEventListener("change", invalidateImport));
  $("#imp-template").addEventListener("click", async () => { try { const t = await api("/api/import/template"); const blob = new Blob([JSON.stringify(t, null, 2)], {type:"application/json"}); const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "acnopviz-import-template.json"; a.click(); URL.revokeObjectURL(a.href); } catch(e){ showAlert(e); } });
  $("#imp-validate").addEventListener("click", async () => {
    try {
      const manifestFile = $("#imp-manifest").files[0]; if (!manifestFile) throw new Error("Choose manifest.json");
      const manifest = JSON.parse(await manifestFile.text()); const files = {};
      for (const t of tables) { const f = $(`#imp-${t}`).files[0]; if (!f) throw new Error(`Choose ${t}.csv`); files[t] = await f.text(); }
      const report = await api("/api/import/validate", {method:"POST", body: JSON.stringify({manifest, files})});
      state.importBundle = {manifest, files, report};
      $("#imp-commit").disabled = !report.ok;
      $("#imp-result").innerHTML = report.ok ? `<div class="card"><h2>Valid bundle</h2><p>Fingerprint <code>${esc(report.fingerprint)}</code></p><pre class="formula">${esc(JSON.stringify(report.counts,null,2))}</pre></div>` : `<div class="card"><h2>Validation errors</h2><div class="table-wrap"><table><thead><tr><th>Table</th><th>Row</th><th>Field</th><th>Message</th></tr></thead><tbody>${report.errors.map(e=>`<tr><td>${esc(e.table)}</td><td>${esc(e.row??"")}</td><td>${esc(e.field??"")}</td><td>${esc(e.message)}</td></tr>`).join("")}</tbody></table></div></div>`;
    } catch(e){ showAlert(e); }
  });
  $("#imp-commit").addEventListener("click", async () => {
    try {
      if (!$("#imp-confirm").checked) throw new Error("Confirm replacement first");
      const b = state.importBundle; if (!b?.report?.ok) throw new Error("Validate a bundle first");
      const res = await api("/api/import/commit", {method:"POST", body: JSON.stringify({manifest:b.manifest, files:b.files, confirm:"REPLACE", fingerprint:b.report.fingerprint})});
      toast("Ledger replaced"); state.importBundle = null; $("#imp-commit").disabled = true;
      $("#imp-result").innerHTML = `<div class="card"><h2>Import committed</h2><pre class="formula">${esc(JSON.stringify(res,null,2))}</pre></div>`;
    } catch(e){ showAlert(e); }
  });
}

const titles = { overview: ["Overview", "Statistically-based accounting optimization suggestions"], recommendations: ["Recommendations", "Evidence-backed review queue"], scenario: ["Scenario lab", "Liquidity stress testing"], calendar: ["Cash calendar", "Committed AR/AP runoff forecast"], backtest: ["Model validation", "Walk-forward backtest"], import: ["Import data", "Validated synthetic CSV bundle"], transactions: ["Transactions", "Synthetic ledger browser"], quality: ["Data quality", "Integrity checks and manifest"], audit: ["Review audit", "Persisted human decisions"], method: ["Methodology", "Methods, assumptions, and limits"] };
async function switchView(view) {
  state.view = view;
  $$(".nav-item").forEach(b => { const active = b.dataset.view === view; b.classList.toggle("active", active); if (active) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current"); });
  $$(".view").forEach(s => { s.hidden = s.id !== `view-${view}`; });
  $("#view-title").textContent = titles[view][0]; $("#view-subtitle").textContent = titles[view][1]; $("#alert").hidden = true;
  const loaders = { overview: loadOverview, recommendations: loadRecommendations, scenario: loadScenario, calendar: loadCalendar, backtest: loadBacktest, import: loadImport, transactions: loadTransactions, quality: loadQuality, audit: loadAudit, method: loadMethod };
  try { await loaders[view](); } catch (e) { showAlert(e); }
}
$$(".nav-item").forEach(b => b.addEventListener("click", () => switchView(b.dataset.view)));
switchView("overview");
