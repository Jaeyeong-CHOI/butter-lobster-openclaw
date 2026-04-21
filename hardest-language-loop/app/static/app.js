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
const openaiKeyInput = document.getElementById('openaiKeyInput');
const saveKeyBtn = document.getElementById('saveKeyBtn');
const clearKeyBtn = document.getElementById('clearKeyBtn');

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
  const keyInfo = data.openai_api_key || { configured: false, masked: null };
  configHint.textContent = `Current Agent 2: ${current} · OpenAI key: ${keyInfo.configured ? keyInfo.masked : 'not set'}`;
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
    const meta = c.metadata || {};
    const hay = `${c.name} ${c.level} ${c.mutation_summary} ${meta.strategy_family || ''} ${meta.strategy_leaf || ''}`.toLowerCase();
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
  const graph = JSON.parse(c.artifacts?.files?.['agent_graph.json'] || '{"nodes":[],"edges":[]}');
  const tree = JSON.parse(c.artifacts?.files?.['strategy_tree.json'] || '{"selected_path":[]}');
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
        <div class="detail-box">
          <h3>Node Graph</h3>
          <p>${graph.nodes?.length || 0} nodes · ${(graph.edges || []).length} edges</p>
        </div>
        <div class="detail-box">
          <h3>Selected Strategy Path</h3>
          <p>${(tree.selected_path || []).join(' → ') || 'not available'}</p>
        </div>
      </div>
      <div class="detail-box">
        <h3>Metadata</h3>
        <pre class="code-block compact">${escapeHtml(JSON.stringify(meta, null, 2))}</pre>
      </div>
    </div>
  `;
}

function graphNodeClass(kind, status) {
  return `graph-node ${kind || 'artifact'} ${status || ''}`;
}

function renderGraphTab(c) {
  const graph = JSON.parse(c.artifacts?.files?.['agent_graph.json'] || '{"nodes":[],"edges":[]}');
  const width = 1420;
  const height = 360;
  const nodeIndex = Object.fromEntries((graph.nodes || []).map((n) => [n.id, n]));
  const edgeSvg = (graph.edges || []).map(([src, dst]) => {
    const a = nodeIndex[src];
    const b = nodeIndex[dst];
    if (!a || !b) return '';
    return `<line x1="${a.x + 70}" y1="${a.y + 28}" x2="${b.x + 70}" y2="${b.y + 28}" class="graph-edge" marker-end="url(#arrow)" />`;
  }).join('');
  const targetTab = (nodeId) => ({
    'agent_a': 'agentA',
    'agent_b': 'agentB',
    'validator': 'validator',
    'interpreter': 'agentA',
    'schema': 'agentA',
    'tasks': 'agentB',
    'program': 'agentB',
    'result': 'validator',
  }[nodeId] || 'overview');
  const nodeSvg = (graph.nodes || []).map((n) => `
    <g transform="translate(${n.x},${n.y})" class="graph-node-group" data-target-tab="${targetTab(n.id)}" data-node-id="${n.id}">
      <rect rx="14" ry="14" width="140" height="56" class="${graphNodeClass(n.kind, n.status)}"></rect>
      <text x="70" y="24" text-anchor="middle" class="graph-label">${String(n.label).split('\n').map((line, idx) => `<tspan x="70" dy="${idx===0?0:16}">${escapeHtml(line)}</tspan>`).join('')}</text>
    </g>
  `).join('');
  return `
    <div class="workspace-section">
      <div class="detail-box">
        <h3>Agent / Artifact Graph</h3>
        <p>Visualizes the current loop as nodes: strategy root → Agent A → interpreter/schema/tasks → Agent B → JSON program → validator → result.</p>
      </div>
      <div class="graph-stage">
        <svg viewBox="0 0 ${width} ${height}" class="graph-svg" role="img" aria-label="Agent graph">
          <defs>
            <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">
              <path d="M0,0 L0,6 L9,3 z" class="graph-arrow"></path>
            </marker>
          </defs>
          ${edgeSvg}
          ${nodeSvg}
        </svg>
      </div>
      <div class="artifact-card"><h3>agent_graph.json</h3><pre class="code-block compact">${escapeHtml(c.artifacts?.files?.['agent_graph.json'] || '')}</pre></div>
    </div>
  `;
}

function renderTreeNode(nodeId, tree, depth = 0) {
  const node = tree.nodes?.[nodeId];
  if (!node) return '';
  const children = (tree.edges || [])
    .filter(([src]) => src === nodeId)
    .map(([, dst]) => dst);
  const filterValue = nodeId === 'root' ? '' : (node.label || nodeId);
  return `
    <li>
      <div class="tree-node ${node.kind || ''} ${node.status || ''}" data-strategy-filter="${escapeHtml(filterValue)}" data-node-id="${nodeId}">
        <div class="tree-title">${escapeHtml(node.label || nodeId)}</div>
        <div class="tree-meta">${node.kind || ''}${node.score != null ? ` · score ${node.score}` : ''}${node.note ? ` · ${escapeHtml(node.note)}` : ''}</div>
      </div>
      ${children.length ? `<ul>${children.map((child) => renderTreeNode(child, tree, depth + 1)).join('')}</ul>` : ''}
    </li>
  `;
}

function renderStrategyTab(c) {
  const tree = JSON.parse(c.artifacts?.files?.['strategy_tree.json'] || '{"nodes":{},"edges":[],"selected_path":[]}');
  return `
    <div class="workspace-section">
      <div class="detail-box">
        <h3>Strategy Tree Search</h3>
        <p>Agent A explores strategy families as a tree. The selected path represents the currently materialized interpreter candidate.</p>
        <div class="pills">${(tree.selected_path || []).map((x) => pill(x)).join('')}</div>
      </div>
      <div class="tree-stage">
        <div class="tree-root">
          <ul class="tree-list">
            ${renderTreeNode('root', tree)}
          </ul>
        </div>
      </div>
      <div class="artifact-card"><h3>strategy_tree.json</h3><pre class="code-block compact">${escapeHtml(c.artifacts?.files?.['strategy_tree.json'] || '')}</pre></div>
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
    case 'graph': return renderGraphTab(c);
    case 'strategy': return renderStrategyTab(c);
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
  bindWorkspaceInteractions(c);
}

function activateTab(tabName) {
  state.activeTab = tabName;
  document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === tabName));
}

function bindWorkspaceInteractions(c) {
  workspaceContent.querySelectorAll('[data-target-tab]').forEach((el) => {
    el.style.cursor = 'pointer';
    el.addEventListener('click', async () => {
      activateTab(el.dataset.targetTab);
      if (state.selectedId) await selectCandidate(state.selectedId);
    });
  });
  workspaceContent.querySelectorAll('[data-strategy-filter]').forEach((el) => {
    el.addEventListener('click', async () => {
      const val = el.dataset.strategyFilter || '';
      state.search = val;
      searchInput.value = val;
      await refreshCandidates();
      if (state.selectedId) await selectCandidate(state.selectedId);
    });
  });
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
  const keyInfo = data.openai_api_key || { configured: false, masked: null };
  configHint.textContent = `Current Agent 2: ${current} · OpenAI key: ${keyInfo.configured ? keyInfo.masked : 'not set'}`;
  openaiKeyInput.value = '';
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
saveKeyBtn.addEventListener('click', async () => {
  const value = openaiKeyInput.value.trim();
  if (!value) return;
  await updateConfig({ openai_api_key: value });
});
clearKeyBtn.addEventListener('click', async () => {
  openaiKeyInput.value = '';
  await updateConfig({ clear_openai_api_key: true });
});

document.querySelectorAll('.tab').forEach((tab) => {
  tab.addEventListener('click', async () => {
    activateTab(tab.dataset.tab);
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
