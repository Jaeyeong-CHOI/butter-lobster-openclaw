const state = {
  selectedId: null,
  selectedCandidate: null,
  lastEventId: 0,
  candidates: [],
  overview: null,
  search: '',
  archivedOnly: false,
};

const summaryBar = document.getElementById('summaryBar');
const candidateList = document.getElementById('candidateList');
const strategyTreeStage = document.getElementById('strategyTreeStage');
const graphStage = document.getElementById('graphStage');
const inspectorContent = document.getElementById('inspectorContent');
const benchmarkContent = document.getElementById('benchmarkContent');
const eventList = document.getElementById('eventList');
const eventStatus = document.getElementById('eventStatus');
const selectedHint = document.getElementById('selectedHint');
const searchInput = document.getElementById('searchInput');
const archivedOnlyInput = document.getElementById('archivedOnly');
const agent2ModelSelect = document.getElementById('agent2ModelSelect');
const openaiKeyInput = document.getElementById('openaiKeyInput');
const saveKeyBtn = document.getElementById('saveKeyBtn');
const clearKeyBtn = document.getElementById('clearKeyBtn');
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

function codeBlock(text = '') {
  return `<pre class="code-block">${escapeHtml(text)}</pre>`;
}

async function loadConfig() {
  const data = await getJson('/api/config');
  const current = data.settings?.agent2_model || 'gpt-5.4';
  const keyInfo = data.openai_api_key || { configured: false, masked: null };
  agent2ModelSelect.innerHTML = data.openai_models.map((name) => `<option value="${name}">${name}</option>`).join('');
  agent2ModelSelect.value = current;
  configHint.textContent = `Agent2: ${current} · OpenAI key: ${keyInfo.configured ? keyInfo.masked : 'not set'}`;
}

async function updateConfig(payload) {
  const data = await getJson('/api/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const current = data.settings?.agent2_model || 'gpt-5.4';
  const keyInfo = data.openai_api_key || { configured: false, masked: null };
  configHint.textContent = `Agent2: ${current} · OpenAI key: ${keyInfo.configured ? keyInfo.masked : 'not set'}`;
  openaiKeyInput.value = '';
  await refreshOverview();
  if (state.selectedId) await selectCandidate(state.selectedId, false);
}

async function refreshOverview() {
  const data = await getJson('/api/overview');
  state.overview = data;
  const s = data.state || {};
  const hardest = data.hardest || {};
  const settings = data.settings || {};
  summaryBar.innerHTML = [
    metricCard('Loop Status', (s.status || 'idle').toUpperCase(), s.note || ''),
    metricCard('Iteration', s.iteration ?? 0, 'completed rounds'),
    metricCard('Candidates', data.stats.total_candidates, 'generated candidates'),
    metricCard('Archived', data.stats.archived_candidates, 'hard-but-valid'),
    metricCard('Agent 2 Model', settings.agent2_model || 'gpt-5.4', 'current solver'),
    metricCard('Current Hardest', hardest.name || '—', hardest.failure_rate != null ? `failure ${(hardest.failure_rate * 100).toFixed(0)}%` : 'not available'),
  ].join('');
  renderBenchmark();
}

function renderBenchmark() {
  const benchmark = state.overview?.benchmark || { models: [], tasks: [], levels: [] };
  const makeCards = (rows, titleField, valueField, suffix) => rows.map((r) => `
    <div class="summary-card">
      <h3>${r[titleField]}</h3>
      <p>${suffix} ${(Number(r[valueField] || 0) * 100).toFixed(0)}%</p>
      <div class="pills">${'n' in r ? pill(`${r.n} samples`) : ''}${'archived_n' in r ? ' ' + pill(`${r.archived_n} archived`) : ''}</div>
    </div>
  `).join('');
  benchmarkContent.innerHTML = `
    ${makeCards(benchmark.models || [], 'model_name', 'pass_rate', 'Pass rate') || '<div class="summary-card"><p>No model data yet.</p></div>'}
    ${makeCards(benchmark.tasks || [], 'task_name', 'pass_rate', 'Pass rate') || '<div class="summary-card"><p>No task data yet.</p></div>'}
    ${makeCards(benchmark.levels || [], 'level', 'avg_failure', 'Avg failure') || '<div class="summary-card"><p>No level data yet.</p></div>'}
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
  const meta = c.metadata || {};
  return `
    <div class="candidate-item ${active}" data-id="${c.id}">
      <div><strong>${c.name}</strong> <span class="candidate-meta">(${c.level})</span></div>
      <div class="candidate-meta">${c.mutation_summary}</div>
      <div class="pills">
        ${pill(`failure ${(c.failure_rate * 100).toFixed(0)}%`)}
        ${pill(`strategy ${meta.strategy_leaf || 'n/a'}`)}
        ${c.archived ? pill('archived') : pill(c.status)}
      </div>
    </div>
  `;
}

async function refreshCandidates() {
  const data = await getJson('/api/candidates?limit=80');
  state.candidates = data.items;
  const items = filteredCandidates();
  candidateList.innerHTML = items.map(candidateRow).join('') || '<div class="candidate-meta">No candidates match this filter.</div>';
  candidateList.querySelectorAll('.candidate-item').forEach((el) => {
    el.addEventListener('click', () => selectCandidate(el.dataset.id, true));
  });
  if (!state.selectedId && items[0]) {
    await selectCandidate(items[0].id, true);
  }
}

function renderTreeNode(nodeId, tree) {
  const node = tree.nodes?.[nodeId];
  if (!node) return '';
  const children = (tree.edges || []).filter(([src]) => src === nodeId).map(([, dst]) => dst);
  return `
    <li>
      <div class="tree-node ${node.kind || ''} ${node.status || ''}" data-node-id="${nodeId}">
        <div class="tree-title">${escapeHtml(node.label || nodeId)}</div>
        <div class="tree-meta">${escapeHtml(node.kind || '')}${node.score != null ? ` · score ${node.score}` : ''}${node.note ? ` · ${escapeHtml(node.note)}` : ''}</div>
      </div>
      ${children.length ? `<ul>${children.map((child) => renderTreeNode(child, tree)).join('')}</ul>` : ''}
    </li>
  `;
}

function renderStrategyTree(tree) {
  strategyTreeStage.innerHTML = `<ul class="tree-list">${renderTreeNode('root', tree)}</ul>`;
  strategyTreeStage.querySelectorAll('[data-node-id]').forEach((el) => {
    el.addEventListener('click', (evt) => {
      evt.stopPropagation();
      const nodeId = el.dataset.nodeId;
      const node = tree.nodes?.[nodeId] || {};
      if (node.kind === 'family' || node.kind === 'strategy') {
        state.search = nodeId;
        searchInput.value = nodeId;
        refreshCandidates();
      }
      showTreeInspector(nodeId, node, tree);
    });
  });
}

function renderAgentGraph(graph) {
  const width = 1460;
  const height = 360;
  const byId = Object.fromEntries((graph.nodes || []).map((n) => [n.id, n]));
  const edgeSvg = (graph.edges || []).map((e) => {
    const a = byId[e.source];
    const b = byId[e.target];
    if (!a || !b) return '';
    const x1 = a.x + 70;
    const y1 = a.y + 28;
    const x2 = b.x + 70;
    const y2 = b.y + 28;
    const mx = (x1 + x2) / 2;
    const my = (y1 + y2) / 2 - 10;
    return `
      <g class="graph-edge-group" data-edge-id="${e.id}">
        <line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" class="graph-edge-base" marker-end="url(#arrow)" />
        <line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" class="graph-edge-hit" />
        <text x="${mx}" y="${my}" text-anchor="middle" class="graph-edge-label">${escapeHtml(e.label || '')}</text>
      </g>
    `;
  }).join('');
  const nodeSvg = (graph.nodes || []).map((n) => `
    <g transform="translate(${n.x},${n.y})" class="graph-node-group" data-node-id="${n.id}">
      <rect class="graph-node ${n.kind || ''} ${n.status || ''}" rx="14" ry="14" width="140" height="56"></rect>
      <text x="70" y="24" text-anchor="middle" class="graph-label">${String(n.label).split('\n').map((line, idx) => `<tspan x="70" dy="${idx===0?0:16}">${escapeHtml(line)}</tspan>`).join('')}</text>
    </g>
  `).join('');
  graphStage.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" class="graph-svg" role="img" aria-label="Agent exchange graph">
      <defs>
        <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">
          <path d="M0,0 L0,6 L9,3 z" class="graph-arrow"></path>
        </marker>
      </defs>
      ${edgeSvg}
      ${nodeSvg}
    </svg>
  `;
  graphStage.querySelectorAll('.graph-node-group').forEach((el) => {
    el.addEventListener('click', () => {
      const node = byId[el.dataset.nodeId];
      showNodeInspector(node, graph);
    });
  });
  graphStage.querySelectorAll('.graph-edge-group').forEach((el) => {
    el.addEventListener('click', () => {
      const edge = (graph.edges || []).find((e) => e.id === el.dataset.edgeId);
      showEdgeInspector(edge, graph);
    });
  });
}

function inspectorCard(title, bodyHtml) {
  return `<div class="inspector-card"><h3>${title}</h3>${bodyHtml}</div>`;
}

function getArtifact(detail, path) {
  return detail?.artifacts?.files?.[path] || '';
}

function showCandidateInspector(detail) {
  const meta = detail.metadata || {};
  inspectorContent.classList.remove('empty');
  inspectorContent.innerHTML = `
    <div class="inspector-section">
      ${inspectorCard('Candidate Summary', `<p><strong>${detail.name}</strong> (${detail.level})<br>${escapeHtml(detail.mutation_summary)}</p><div class="pills">${pill(`failure ${(detail.failure_rate * 100).toFixed(0)}%`)} ${pill(`strategy ${meta.strategy_leaf || 'n/a'}`)} ${detail.archived ? pill('archived') : pill(detail.status)}</div>`)}
      ${inspectorCard('Execution Contract', `<p>Agent A produces an OCaml interpreter and JSON AST schema. Agent B returns machine-parseable JSON AST. Validator reconstructs AST and executes the interpreter.</p>`)}
      ${inspectorCard('language_spec.json', codeBlock(getArtifact(detail, 'language_spec.json')))}
    </div>
  `;
}

function showTreeInspector(nodeId, node, tree) {
  const detail = state.selectedCandidate;
  inspectorContent.classList.remove('empty');
  inspectorContent.innerHTML = `
    <div class="inspector-section">
      ${inspectorCard('Strategy Node', `<p><strong>${escapeHtml(node.label || nodeId)}</strong><br>kind: ${escapeHtml(node.kind || '')}<br>status: ${escapeHtml(node.status || '')}${node.score != null ? `<br>score: ${node.score}` : ''}${node.note ? `<br>${escapeHtml(node.note)}` : ''}</p>`)}
      ${inspectorCard('Selected Path', `<p>${(tree.selected_path || []).map((x) => escapeHtml(x)).join(' → ')}</p>`)}
      ${detail ? inspectorCard('Current Candidate Strategy Metadata', codeBlock(JSON.stringify({strategy_family: detail.metadata?.strategy_family, strategy_leaf: detail.metadata?.strategy_leaf}, null, 2))) : ''}
    </div>
  `;
}

function showNodeInspector(node, graph) {
  const detail = state.selectedCandidate;
  if (!detail) return;
  const pathMap = {
    strategy_root: 'strategy_tree.json',
    agent_a: 'prompts/agentA_interpreter_builder.txt',
    interpreter: 'interpreter.ml',
    schema: 'ast_schema.json',
    tasks: 'tasks.json',
    agent_b: 'prompts/agentB_solver.txt',
    program: 'program_attempts.json',
    validator: 'validator_result.json',
    result: 'validator_result.json',
  };
  const file = pathMap[node.id] || 'candidate.json';
  inspectorContent.classList.remove('empty');
  inspectorContent.innerHTML = `
    <div class="inspector-section">
      ${inspectorCard('Selected Node', `<p><strong>${escapeHtml(node.label)}</strong><br>kind: ${escapeHtml(node.kind || '')}<br>status: ${escapeHtml(node.status || '')}</p>`)}
      ${inspectorCard('Relevant Artifact', `<p>${escapeHtml(file)}</p>${codeBlock(getArtifact(detail, file))}`)}
    </div>
  `;
}

function showEdgeInspector(edge, graph) {
  const detail = state.selectedCandidate;
  if (!detail || !edge) return;
  const preview = getArtifact(detail, edge.inspect || 'candidate.json');
  inspectorContent.classList.remove('empty');
  inspectorContent.innerHTML = `
    <div class="inspector-section">
      ${inspectorCard('Information Exchange', `<p><strong>${escapeHtml(edge.label || edge.id)}</strong><br>${escapeHtml(edge.source)} → ${escapeHtml(edge.target)}<br>${escapeHtml(edge.exchange || '')}</p>`)}
      ${inspectorCard('Inspected Artifact', `<p>${escapeHtml(edge.inspect || 'candidate.json')}</p>${codeBlock(preview)}`)}
    </div>
  `;
}

async function selectCandidate(id, updateInspector = true) {
  state.selectedId = id;
  const detail = await getJson(`/api/candidates/${id}`);
  state.selectedCandidate = detail;
  selectedHint.textContent = `${detail.name} · ${detail.level}`;
  renderStrategyTree(JSON.parse(getArtifact(detail, 'strategy_tree.json') || '{"nodes":{},"edges":[]}'));
  renderAgentGraph(JSON.parse(getArtifact(detail, 'agent_graph.json') || '{"nodes":[],"edges":[]}'));
  if (updateInspector) showCandidateInspector(detail);
  await refreshCandidates();
}

function addEventItem(event) {
  const el = document.createElement('div');
  el.className = 'event-item';
  el.innerHTML = `
    <div class="kind">${event.kind}</div>
    <div class="candidate-meta">${new Date(event.created_at).toLocaleString()}</div>
    ${codeBlock(JSON.stringify(event.payload, null, 2))}
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
  if (state.selectedId) await selectCandidate(state.selectedId, false);
}

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
document.getElementById('startBtn').addEventListener('click', () => post('/api/loop/start'));
document.getElementById('pauseBtn').addEventListener('click', () => post('/api/loop/pause'));
document.getElementById('stepBtn').addEventListener('click', () => post('/api/loop/step'));
document.getElementById('resetBtn').addEventListener('click', async () => {
  await post('/api/loop/reset');
  state.selectedId = null;
  state.selectedCandidate = null;
  selectedHint.textContent = 'Select a candidate';
  strategyTreeStage.innerHTML = '';
  graphStage.innerHTML = '';
  inspectorContent.className = 'inspector empty';
  inspectorContent.textContent = 'Click a candidate, graph node, or graph edge to inspect details.';
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
    if (state.selectedId) await selectCandidate(state.selectedId, false);
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
