const state = {
  selectedId: null,
  lastEventId: 0,
  candidates: [],
  overview: null,
  activeTab: 'overview',
  search: '',
  archivedOnly: false,
};

const metricGrid = document.getElementById('metricGrid');
const eventList = document.getElementById('eventList');
const candidateList = document.getElementById('candidateList');
const workspaceContent = document.getElementById('workspaceContent');
const eventStatus = document.getElementById('eventStatus');
const benchmarkContent = document.getElementById('benchmarkContent');
const selectedHint = document.getElementById('selectedHint');
const searchInput = document.getElementById('searchInput');
const archivedOnlyInput = document.getElementById('archivedOnly');

async function getJson(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function escapeHtml(text = '') {
  return String(text)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

function metricCard(label, value, sub = '') {
  return `<div class="metric-card"><div class="label">${label}</div><div class="value">${value}</div><div class="sub">${sub}</div></div>`;
}

function pill(text) {
  return `<span class="pill">${text}</span>`;
}

async function refreshOverview() {
  const data = await getJson('/api/overview');
  state.overview = data;
  const s = data.state || {};
  const hardest = data.hardest || {};
  metricGrid.innerHTML = [
    metricCard('Loop Status', (s.status || 'idle').toUpperCase(), s.note || ''),
    metricCard('Iteration', s.iteration ?? 0, 'completed rounds'),
    metricCard('Candidates', data.stats.total_candidates, 'generated total'),
    metricCard('Archived', data.stats.archived_candidates, 'hard-but-valid languages'),
    metricCard('Current Hardest', hardest.name || '—', hardest.failure_rate != null ? `failure ${(hardest.failure_rate * 100).toFixed(0)}%` : 'not available'),
  ].join('');
  renderBenchmark();
}

function renderBenchmark() {
  const benchmark = state.overview?.benchmark || { models: [], tasks: [], levels: [] };
  const modelCards = benchmark.models.map((m) => `
    <div class="summary-card">
      <h3>${m.model_name}</h3>
      <p>Pass rate ${(Number(m.pass_rate || 0) * 100).toFixed(0)}%</p>
      <div class="pills">${pill(`${m.n} evals`)}</div>
    </div>
  `).join('');
  const taskCards = benchmark.tasks.map((t) => `
    <div class="summary-card">
      <h3>${t.task_name}</h3>
      <p>Pass rate ${(Number(t.pass_rate || 0) * 100).toFixed(0)}%</p>
      <div class="pills">${pill(`${t.n} evals`)}</div>
    </div>
  `).join('');
  const levelCards = benchmark.levels.map((l) => `
    <div class="summary-card">
      <h3>${l.level}</h3>
      <p>Avg failure ${(Number(l.avg_failure || 0) * 100).toFixed(0)}%</p>
      <div class="pills">${pill(`${l.n} candidates`)} ${pill(`${l.archived_n || 0} archived`)}</div>
    </div>
  `).join('');

  benchmarkContent.innerHTML = `
    <div class="workspace-section">
      <div>
        <h3>By Model</h3>
        <div class="overview-grid">${modelCards || '<div class="summary-card"><p>No model data yet.</p></div>'}</div>
      </div>
      <div>
        <h3>By Task</h3>
        <div class="overview-grid">${taskCards || '<div class="summary-card"><p>No task data yet.</p></div>'}</div>
      </div>
      <div>
        <h3>By Language Level</h3>
        <div class="overview-grid">${levelCards || '<div class="summary-card"><p>No level data yet.</p></div>'}</div>
      </div>
    </div>
  `;
}

function filteredCandidates() {
  const q = state.search.trim().toLowerCase();
  return state.candidates.filter((c) => {
    if (state.archivedOnly && !c.archived) return false;
    if (!q) return true;
    const hay = `${c.name} ${c.level} ${c.mutation_summary}`.toLowerCase();
    return hay.includes(q);
  });
}

function candidateRow(c) {
  const active = c.id === state.selectedId ? 'active' : '';
  const archived = c.archived ? 'ARCHIVED' : c.status.toUpperCase();
  const meta = c.metadata || {};
  return `
    <div class="candidate-item ${active}" data-id="${c.id}">
      <div><strong>${c.name}</strong> <span class="candidate-meta">(${c.level})</span></div>
      <div class="candidate-meta">${c.mutation_summary}</div>
      <div class="pills">
        ${pill(`failure ${(c.failure_rate * 100).toFixed(0)}%`)}
        ${pill(`similarity ${(c.similarity_score * 100).toFixed(0)}%`)}
        ${pill(`conflict ${(c.conflict_score * 100).toFixed(0)}%`)}
        ${pill(`solvable ${(c.solvable_score * 100).toFixed(0)}%`)}
        ${pill(archived)}
        ${meta.python_near ? pill('python-near') : ''}
      </div>
    </div>
  `;
}

async function refreshCandidates() {
  const data = await getJson('/api/candidates?limit=60');
  state.candidates = data.items;
  const items = filteredCandidates();
  candidateList.innerHTML = items.map(candidateRow).join('') || '<div class="candidate-meta">No candidates match the current filter.</div>';
  candidateList.querySelectorAll('.candidate-item').forEach((el) => {
    el.addEventListener('click', () => selectCandidate(el.dataset.id));
  });
  if (!state.selectedId && items[0]) {
    await selectCandidate(items[0].id);
  }
}

function renderEvalTable(evals) {
  if (!evals.length) return '<div class="summary-card"><p>No evaluations yet.</p></div>';
  return `
    <table class="eval-table">
      <thead>
        <tr><th>Model</th><th>Task</th><th>Prompt</th><th>Result</th><th>Score</th><th>Notes</th></tr>
      </thead>
      <tbody>
        ${evals.map((e) => `
          <tr>
            <td>${e.model_name}</td>
            <td>${e.task_name}</td>
            <td>${e.prompt_mode}</td>
            <td class="${e.success ? 'success' : 'fail'}">${e.success ? 'PASS' : 'FAIL'}</td>
            <td>${(e.score * 100).toFixed(0)}%</td>
            <td>${e.notes || ''}</td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

function renderOverviewTab(c) {
  const meta = c.metadata || {};
  return `
    <div class="workspace-section">
      <div class="overview-grid">
        <div class="detail-box">
          <h3>${c.name}</h3>
          <p>${c.mutation_summary}</p>
        </div>
        <div class="detail-box">
          <h3>Interpreter Hint</h3>
          <p>${c.interpreter_hint}</p>
        </div>
        <div class="detail-box">
          <h3>Search Signals</h3>
          <p>Similarity ${(c.similarity_score * 100).toFixed(0)}% · Conflict ${(c.conflict_score * 100).toFixed(0)}% · Solvable ${(c.solvable_score * 100).toFixed(0)}% · Novelty ${(c.novelty_score * 100).toFixed(0)}%</p>
        </div>
        <div class="detail-box">
          <h3>Analyzer Output</h3>
          <p>Status: ${c.status} · Archived: ${c.archived ? 'yes' : 'no'} · Hardest models: ${(meta.hardest_models || []).join(', ') || '—'}</p>
        </div>
      </div>
      <div class="detail-box">
        <h3>Metadata</h3>
        <pre class="code-block compact">${escapeHtml(JSON.stringify(meta, null, 2))}</pre>
      </div>
    </div>
  `;
}

function renderPromptsTab(c) {
  const files = c.artifacts?.files || {};
  return `
    <div class="workspace-section two-col">
      <div class="artifact-card"><h3>Agent 1 — NewPL Searcher</h3><pre class="code-block">${escapeHtml(files['prompts/agent1_newpl.txt'] || '')}</pre></div>
      <div class="artifact-card"><h3>Agent 2 — Solver Bench</h3><pre class="code-block">${escapeHtml(files['prompts/agent2_solver.txt'] || '')}</pre></div>
      <div class="artifact-card"><h3>Agent 3 — Analyzer / Curator</h3><pre class="code-block">${escapeHtml(files['prompts/agent3_curator.txt'] || '')}</pre></div>
    </div>
  `;
}

function renderArtifactsTab(c) {
  const files = c.artifacts?.files || {};
  const manifest = c.artifacts?.manifest || [];
  return `
    <div class="workspace-section">
      <div class="detail-box">
        <h3>Artifact Manifest</h3>
        <ul class="manifest-list">${manifest.map((m) => `<li>${m}</li>`).join('')}</ul>
      </div>
      <div class="two-col">
        <div class="artifact-card"><h3>spec.md</h3><pre class="code-block">${escapeHtml(files['spec.md'] || '')}</pre></div>
        <div class="artifact-card"><h3>interpreter.py</h3><pre class="code-block">${escapeHtml(files['interpreter.py'] || '')}</pre></div>
      </div>
      <div class="artifact-card"><h3>tasks.json</h3><pre class="code-block">${escapeHtml(files['tasks.json'] || '')}</pre></div>
    </div>
  `;
}

function renderEvaluationsTab(c) {
  const files = c.artifacts?.files || {};
  return `
    <div class="workspace-section">
      <div class="detail-box">
        <h3>Evaluation Matrix</h3>
        ${renderEvalTable(c.evaluations || [])}
      </div>
      <div class="artifact-card">
        <h3>analysis.json</h3>
        <pre class="code-block compact">${escapeHtml(files['analysis.json'] || '')}</pre>
      </div>
    </div>
  `;
}

function renderRawTab(c) {
  const files = c.artifacts?.files || {};
  return `
    <div class="workspace-section two-col">
      <div class="artifact-card"><h3>candidate.json</h3><pre class="code-block">${escapeHtml(files['candidate.json'] || JSON.stringify(c, null, 2))}</pre></div>
      <div class="artifact-card"><h3>evaluations.json</h3><pre class="code-block">${escapeHtml(files['evaluations.json'] || '')}</pre></div>
    </div>
  `;
}

function renderWorkspaceTab(c) {
  switch (state.activeTab) {
    case 'prompts': return renderPromptsTab(c);
    case 'artifacts': return renderArtifactsTab(c);
    case 'evaluations': return renderEvaluationsTab(c);
    case 'raw': return renderRawTab(c);
    case 'overview':
    default:
      return renderOverviewTab(c);
  }
}

async function selectCandidate(id) {
  state.selectedId = id;
  const items = filteredCandidates();
  candidateList.innerHTML = items.map(candidateRow).join('');
  candidateList.querySelectorAll('.candidate-item').forEach((el) => {
    el.addEventListener('click', () => selectCandidate(el.dataset.id));
  });

  const c = await getJson(`/api/candidates/${id}`);
  selectedHint.textContent = `${c.name} · ${c.level}`;
  workspaceContent.classList.remove('empty');
  workspaceContent.innerHTML = renderWorkspaceTab(c);
}

function addEventItem(event) {
  const el = document.createElement('div');
  el.className = 'event-item';
  el.innerHTML = `
    <div class="kind">${event.kind}</div>
    <div class="candidate-meta">${new Date(event.created_at).toLocaleString()}</div>
    <div><pre class="code-block compact">${escapeHtml(JSON.stringify(event.payload, null, 2))}</pre></div>
  `;
  eventList.prepend(el);
}

async function preloadEvents() {
  const data = await getJson('/api/events?limit=40');
  eventList.innerHTML = '';
  data.items.forEach((e) => {
    state.lastEventId = Math.max(state.lastEventId, e.id);
    addEventItem(e);
  });
}

async function post(url) {
  await getJson(url, { method: 'POST' });
  await refreshOverview();
  await refreshCandidates();
  if (state.selectedId) await selectCandidate(state.selectedId);
}

document.getElementById('startBtn').addEventListener('click', () => post('/api/loop/start'));
document.getElementById('pauseBtn').addEventListener('click', () => post('/api/loop/pause'));
document.getElementById('stepBtn').addEventListener('click', () => post('/api/loop/step'));
document.getElementById('resetBtn').addEventListener('click', async () => {
  await post('/api/loop/reset');
  state.selectedId = null;
  workspaceContent.className = 'workspace empty';
  workspaceContent.textContent = 'Select a candidate to inspect prompts, generated files, and benchmark data.';
  selectedHint.textContent = 'Select a candidate';
});

searchInput.addEventListener('input', async (e) => {
  state.search = e.target.value;
  await refreshCandidates();
});
archivedOnlyInput.addEventListener('change', async (e) => {
  state.archivedOnly = e.target.checked;
  await refreshCandidates();
});

document.querySelectorAll('.tab').forEach((tab) => {
  tab.addEventListener('click', async () => {
    document.querySelectorAll('.tab').forEach((t) => t.classList.remove('active'));
    tab.classList.add('active');
    state.activeTab = tab.dataset.tab;
    if (state.selectedId) await selectCandidate(state.selectedId);
  });
});

function connectEvents() {
  const source = new EventSource('/api/events/stream');
  source.onopen = () => { eventStatus.textContent = 'live'; };
  source.onerror = () => { eventStatus.textContent = 'reconnecting…'; };
  source.onmessage = async (msg) => {
    const event = JSON.parse(msg.data);
    if (event.id <= state.lastEventId) return;
    state.lastEventId = event.id;
    addEventItem(event);
    await refreshOverview();
    await refreshCandidates();
    if (state.selectedId) await selectCandidate(state.selectedId);
  };
}

async function init() {
  await refreshOverview();
  await preloadEvents();
  await refreshCandidates();
  connectEvents();
}

init().catch((err) => {
  console.error(err);
  eventStatus.textContent = 'error';
});
