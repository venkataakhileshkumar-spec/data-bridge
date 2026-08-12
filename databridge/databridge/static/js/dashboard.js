/* DataBridge — dashboard client
   Fetches pipeline results from the Flask API and renders the flow
   diagram, KPIs, and record tables. No build step. */

async function getJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Request failed: ${path}`);
  return res.json();
}

function shortId(id) {
  return id ? id.slice(0, 8) : "";
}

async function loadFlow() {
  const f = await getJSON("/api/pipeline/flow");
  document.getElementById("flow-legacy").textContent = f.legacy_records.toLocaleString();
  document.getElementById("flow-portal").textContent = f.portal_records.toLocaleString();
  document.getElementById("flow-provider").textContent = f.provider_records.toLocaleString();
  document.getElementById("flow-members").textContent = f.canonical_members.toLocaleString();
  document.getElementById("flow-providers").textContent = f.canonical_providers.toLocaleString();
}

async function loadSummary() {
  const s = await getJSON("/api/pipeline/summary");
  document.getElementById("kpi-sources").textContent = s.sources_connected;
  document.getElementById("kpi-raw").textContent = s.raw_records_ingested.toLocaleString();
  document.getElementById("kpi-linked").textContent = s.linked_people.toLocaleString();
  document.getElementById("kpi-members").textContent = s.canonical_members.toLocaleString();
  document.getElementById("kpi-issues").textContent = s.quality_issues.toLocaleString();
}

async function loadCrosswalk() {
  const rows = await getJSON("/api/crosswalk");
  const body = document.getElementById("crosswalk-body");
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="4" class="empty">No cross-source matches found.</td></tr>`;
    return;
  }
  body.innerHTML = rows.map((r) => `
    <tr>
      <td class="canon-id">${shortId(r.canonical_id)}</td>
      <td>${r.source_system}</td>
      <td>${r.source_id}</td>
      <td><span class="match-tag match-${r.match_type === "fuzzy" ? "fuzzy" : "exact"}">${r.match_type === "fuzzy" ? "fuzzy" : "exact"}</span></td>
    </tr>
  `).join("");
}

async function loadQualityIssues() {
  const rows = await getJSON("/api/quality-issues");
  const body = document.getElementById("quality-body");
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="4" class="empty">No quality issues flagged.</td></tr>`;
    return;
  }
  body.innerHTML = rows.map((r) => `
    <tr>
      <td>${r.source_system}</td>
      <td>${r.source_id}</td>
      <td>${r.field}</td>
      <td style="font-family: var(--font-body);">${r.issue}</td>
    </tr>
  `).join("");
}

async function loadMembers() {
  const rows = await getJSON("/api/members");
  const body = document.getElementById("members-body");
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="6" class="empty">No members loaded.</td></tr>`;
    return;
  }
  body.innerHTML = rows.map((r) => `
    <tr>
      <td style="font-family: var(--font-body);">${r.first_name || ""} ${r.last_name || ""}</td>
      <td>${r.dob || "—"}</td>
      <td>${r.sex || "—"}</td>
      <td style="font-family: var(--font-body);">${r.plan_type || "—"}</td>
      <td style="font-family: var(--font-body);">${[r.city, r.state].filter(Boolean).join(", ") || "—"}</td>
      <td style="font-family: var(--font-body); font-size: 11px; color: var(--ink-soft);">${r.n_source_records > 1 ? r.source_systems.replace("|", " + ") : r.source_systems}</td>
    </tr>
  `).join("");
}

async function loadProviders() {
  const rows = await getJSON("/api/providers");
  const body = document.getElementById("providers-body");
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="5" class="empty">No providers loaded.</td></tr>`;
    return;
  }
  body.innerHTML = rows.map((r) => `
    <tr>
      <td style="font-family: var(--font-body);">${r.full_name}</td>
      <td style="font-family: var(--font-body);">${r.specialty}</td>
      <td style="font-family: var(--font-body);">${r.practice_name}</td>
      <td style="font-family: var(--font-body);">${[r.city, r.state].filter(Boolean).join(", ") || "—"}</td>
      <td><span class="${r.accepting_new_patients ? "bool-yes" : "bool-no"}">${r.accepting_new_patients ? "Yes" : "No"}</span></td>
    </tr>
  `).join("");
}

async function refreshAll() {
  await Promise.all([
    loadFlow(),
    loadSummary(),
    loadCrosswalk(),
    loadQualityIssues(),
    loadMembers(),
    loadProviders(),
  ]);
  document.getElementById("last-updated").textContent = "updated " + new Date().toLocaleTimeString();
}

document.getElementById("btn-run").addEventListener("click", async () => {
  const btn = document.getElementById("btn-run");
  const status = document.getElementById("run-status");
  btn.disabled = true;
  status.textContent = "running…";
  try {
    await fetch("/api/pipeline/run", { method: "POST" });
    await refreshAll();
    status.textContent = "done";
  } catch (e) {
    status.textContent = "failed — see console";
    console.error(e);
  } finally {
    btn.disabled = false;
  }
});

refreshAll();
