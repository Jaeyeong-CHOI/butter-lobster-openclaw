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
const agent2ModelSelect = document.getElementById('agent2ModelSelect');
const configHint = document.getElementById('configHint');

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

async function loadConfig() {
  const data = await getJson('/api/config');
  const current = data.settings?.agent2_model || 'gpt-5.4';
  agent2ModelSelect.innerHTML = data.openai_models.map((name) => `<option value="${name}">${name}</option>`).join('');
  agent2ModelSelect.value = current;
  configHint.textContent = `Current Agent 2: ${current} · applies to new iterations`;
}

async function refreshOverview() {
  const data = await getJson('/api/overview');
  state.overview = data;
  const s = data.state || {};
  const hardest = data.hardest || {};
  const settings = data.settings || {};
  metricGrid.innerHTML = [
    metricCard('Loop Status', (s.status || 'idle').toUpperCase(), s.note || ''),
    metricCard('Iteration', s.iteration ?? 0, 'completed rounds'),
    metricCard('Candidates', data.stats.total_candidates, 'generated interpreters'),
    metricCard('Archived', data.stats.archived_candidates, 'hard-but-valid languages'),
    metricCard('Agent 2 Model', settings.agent2_model || 'gpt-5.4', 'current OpenAI solver'),
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
        ${pill(`solver ${meta.agent2_model || 'gpt-5.4'}`)}
        ${pill(archived)}
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
          <h3>Pipeline</h3>
          <p><strong>Agent A</strong> builds/mutates the interpreter.<br><strong>Agent B</strong> emits JSON AST programs.<br><strong>Validator</strong> executes via interpreter and compares outputs.</p>
        </div>
        <div class="detail-box">
          <h3>Current Candidate</h3>
          <p>${c.name} · ${c.level}<br>${c.mutation_summary}</p>
        </div>
        <div class="detail-box">
          <h3>Execution Signals</h3>
          <p>Similarity ${(c.similarity_score * 100).toFixed(0)}% · Conflict ${(c.conflict_score * 100).toFixed(0)}% · Solvable ${(c.solvable_score * 100).toFixed(0)}% · Failure ${(c.failure_rate * 100).toFixed(0)}%</p>
        </div>
        <div class="detail-box">
          <h3>Runtime Settings</h3>
          <p>Agent 2 model: ${meta.agent2_model || 'gpt-5.4'}<br>Submission: JSON AST<br>Validator: deterministic execution</p>
        </div>
      </div>
      <div class="detail-box">
        <h3>Metadata</h3>
        <pre class="code-block compact">${escapeHtml(JSON.stringify(meta, null, 2))}</pre>
      </div>
    </div>
  `;
}

function renderAgentATab(c) {
  const files = c.artifacts?.files || {};
  return `
    <div class="workspace-section">
      <div class="artifact-card"><h3>Agent A Prompt</h3><pre class="code-block compact">${escapeHtml(files['prompts/agentA_interpreter_builder.txt'] || '')}</pre></div>
      <div class="two-col">
        <div class="artifact-card"><h3>interpreter.ml</h3><pre class="code-block">${escapeHtml(files['interpreter.ml'] || '')}</pre></div>
        <div class="artifact-card"><h3>language_spec.json</h3><pre class="code-block">${escapeHtml(files['language_spec.json'] || '')}</pre></div>
      </div>
      <div class="artifact-card"><h3>ast_schema.json</h3><pre class="code-block">${escapeHtml(files['ast_schema.json'] || '')}</pre></div>
    </div>
  `;
}

function renderAgentBTab(c) {
  const files = c.artifacts?.files || {};
  return `
    <div class="workspace-section">
      <div class="artifact-card"><h3>Agent B Prompt</h3><pre class="code-block compact">${escapeHtml(files['prompts/agentB_solver.txt'] || '')}</pre></div>
      <div class="two-col">
        <div class="artifact-card"><h3>tasks.json</h3><pre class="code-block">${escapeHtml(files['tasks.json'] || '')}</pre></div>
        <div class="artifact-card"><h3>program_attempts.json</h3><pre class="code-block">${escapeHtml(files['program_attempts.json'] || '')}</pre></div>
      </div>
    </div>
  `;
}

function renderValidatorTab(c) {
  const files = c.artifacts?.files || {};
  return `
    <div class="workspace-section">
      <div class="detail-box">
        <h3>Validator Summary</h3>
        <p>The validator checks JSON schema conformity, reconstructs AST, executes the interpreter, and compares outputs against expected task results.</p>
      </div>
      <div class="artifact-card"><h3>validator_result.json</h3><pre class="code-block">${escapeHtml(files['validator_result.json'] || '')}</pre></div>
      <div class="detail-box">
        <h3>Execution Matrix</h3>
        ${renderEvalTable(c.evaluations || [])}
      </div>
    </div>
  `;
}

function renderDataTab(c) {
  const files = c.artifacts?.files || {};
  const manifest = c.artifacts?.manifest || [];
  return `
    <div class="workspace-section">
      <div class="detail-box">
        <h3>Data Bundle Manifest</h3>
        <ul class="manifest-list">${manifest.map((m) => `<li>${m}</li>`).join('')}</ul>
      </div>
      <div class="two-col">
        <div class="artifact-card"><h3>spec.md</h3><pre class="code-block">${escapeHtml(files['spec.md'] || '')}</pre></div>
        <div class="artifact-card"><h3>analysis.json</h3><pre class="code-block">${escapeHtml(files['analysis.json'] || '')}</pre></div>
      </div>
      <div class="artifact-card"><h3>candidate.json</h3><pre class="code-block">${escapeHtml(files['candidate.json'] || '')}</pre></div>
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
    case 'agentA': return renderAgentATab(c);
    case 'agentB': return renderAgentBTab(c);
    case 'validator': return renderValidatorTab(c);
    case 'data': return renderDataTab(c);
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

async function updateConfig(payload) {
  const data = await getJson('/api/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const current = data.settings?.agent2_model || 'gpt-5.4';
  configHint.textContent = `Current Agent 2: ${current} · reset loop for a clean benchmark history`;
  await refreshOverview();
  if (state.selectedId) await selectCandidate(state.selectedId);
}

document.getElementById('startBtn').addEventListener('click', () => post('/api/loop/start'));
document.getElementById('pauseBtn').addEventListener('click', () => post('/api/loop/pause'));
document.getElementById('stepBtn').addEventListener('click', () => post('/api/loop/step'));
document.getElementById('resetBtn').addEventListener('click', async () => {
  await post('/api/loop/reset');
  state.selectedId = null;
  workspaceContent.className = 'workspace empty';
  workspaceContent.textContent = 'Select a candidate to inspect interpreter, schema, program JSON, and validator outputs.';
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
agent2ModelSelect.addEventListener('change', async (e) => {
  await updateConfig({ agent2_model: e.target.value });
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
  await loadConfig();
  await refreshOverview();
  await preloadEvents();
  await refreshCandidates();
  connectEvents();
}

init().catch((err) => {
  console.error(err);
  eventStatus.textContent = 'error';
});
