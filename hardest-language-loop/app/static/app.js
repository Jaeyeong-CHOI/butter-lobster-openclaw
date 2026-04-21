const state = {
  selectedId: null,
  selectedCandidate: null,
  lastEventId: 0,
  candidates: [],
  overview: null,
  search: '',
  archivedOnly: false,
  selectedTreeNode: 'root',
  selectedGraphNode: null,
  selectedGraphEdge: null,
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

const artifactGlossary = {
  'ast_schema.json': {
    title: 'AST contract',
    summary: 'Defines the JSON shape Agent B must submit. It is the machine-readable grammar for nodes, fields, and nesting rules.',
    why: 'Without this, the solver could emit arbitrary JSON that the validator cannot reconstruct into the language AST.',
  },
  'tasks.json': {
    title: 'Task bank',
    summary: 'Lists benchmark tasks, prompts, categories, and expected behavior for each candidate language.',
    why: 'This is the workload Agent B tries to solve and the validator uses to judge whether execution matched the requested behavior.',
  },
  'interpreter.ml': {
    title: 'Executable language definition',
    summary: 'The OCaml interpreter is the ground-truth semantics of the candidate language.',
    why: 'It replaces vague natural-language descriptions with an executable source of truth for evaluation.',
  },
  'program_attempts.json': {
    title: 'Solver output bundle',
    summary: 'Stores Agent B program submissions in JSON AST form, often with retries or variants.',
    why: 'This is what gets parsed, reconstructed into AST, and executed by the validator.',
  },
  'validator_result.json': {
    title: 'Deterministic verdict',
    summary: 'Contains parse status, execution outcome, and whether the produced outputs matched the expected task behavior.',
    why: 'This file turns the experiment into a measurable benchmark instead of a subjective prompt-reading exercise.',
  },
  'prompts/agentA_interpreter_builder.txt': {
    title: 'Agent A prompt',
    summary: 'Instruction set for mutating or building interpreters.',
    why: 'This prompt controls how the language design space is explored.',
  },
  'prompts/agentB_solver.txt': {
    title: 'Agent B prompt',
    summary: 'Instruction set for producing a candidate program under the selected language semantics.',
    why: 'This is the exact interface between the language definition and the solver model.',
  },
  'language_spec.json': {
    title: 'Candidate summary',
    summary: 'High-level metadata about the candidate: scores, mutation summary, semantics mode, and pipeline settings.',
    why: 'Useful quick reference before diving into raw prompt and artifact files.',
  },
  'strategy_tree.json': {
    title: 'Search trace',
    summary: 'Encodes the strategy family and leaf selected for this candidate.',
    why: 'It explains how this candidate sits inside the broader strategy exploration tree.',
  },
};

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

function safeJsonParse(text, fallback) {
  try {
    return JSON.parse(text);
  } catch {
    return fallback;
  }
}

function metricCard(label, value, sub = '') {
  return `<div class="metric-card"><div class="label">${label}</div><div class="value">${value}</div><div class="sub">${sub}</div></div>`;
}

function pill(text) {
  return `<span class="pill">${escapeHtml(text)}</span>`;
}

function codeBlock(text = '') {
  return `<pre class="code-block">${escapeHtml(text)}</pre>`;
}

function inspectorCard(title, bodyHtml) {
  return `<div class="inspector-card"><h3>${escapeHtml(title)}</h3>${bodyHtml}</div>`;
}

function kv(label, value) {
  return `<div class="key-value"><div class="k">${escapeHtml(label)}</div><div class="v">${escapeHtml(value)}</div></div>`;
}

function benchmarkSection(title, content) {
  return `<div class="summary-card"><h3>${escapeHtml(title)}</h3>${content}</div>`;
}

function glossaryHtml(path) {
  const entry = artifactGlossary[path];
  if (!entry) return '';
  return inspectorCard(entry.title, `<p>${escapeHtml(entry.summary)}<br><br>${escapeHtml(entry.why)}</p>`);
}

function emptyInspectorHtml() {
  return `
    <div class="empty-state">
      <div class="empty-icon">◎</div>
      <div class="empty-title">Select a candidate, node, or edge</div>
      <div class="empty-copy">The inspector will show prompts, JSON contracts, task definitions, and validator artifacts.</div>
    </div>
  `;
}

function getArtifact(detail, path) {
  return detail?.artifacts?.files?.[path] || '';
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
    metricCard('Loop Status', (s.status || 'idle').toUpperCase(), s.note || 'waiting for execution'),
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

  const block = (rows, titleField, valueField, suffix, fallback) => {
    if (!rows?.length) return `<p>${fallback}</p>`;
    return rows.map((r) => `
      <div class="key-value">
        <div class="k">${escapeHtml(r[titleField])}</div>
        <div class="v">${suffix} ${(Number(r[valueField] || 0) * 100).toFixed(0)}%</div>
        <div class="pills">${'n' in r ? pill(`${r.n} samples`) : ''}${'archived_n' in r ? pill(`${r.archived_n} archived`) : ''}</div>
      </div>
    `).join('');
  };

  benchmarkContent.innerHTML = [
    benchmarkSection('Models', block(benchmark.models, 'model_name', 'pass_rate', 'Pass', 'No model results yet.')),
    benchmarkSection('Tasks', block(benchmark.tasks, 'task_name', 'pass_rate', 'Pass', 'No task results yet.')),
    benchmarkSection('Levels', block(benchmark.levels, 'level', 'avg_failure', 'Failure', 'No level results yet.')),
  ].join('');
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
      <div class="candidate-topline">
        <div class="candidate-title">${escapeHtml(c.name)}</div>
        <div class="candidate-level">${escapeHtml(c.level)}</div>
      </div>
      <div class="candidate-meta candidate-summary">${escapeHtml(c.mutation_summary)}</div>
      <div class="pills">
        ${pill(`failure ${(Number(c.failure_rate || 0) * 100).toFixed(0)}%`)}
        ${pill(`strategy ${meta.strategy_leaf || 'n/a'}`)}
        ${pill(c.archived ? 'archived' : (c.status || 'generated'))}
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
  const activeClass = state.selectedTreeNode === nodeId ? 'active' : '';
  return `
    <li>
      <div class="tree-node ${node.kind || ''} ${node.status || ''} ${activeClass}" data-node-id="${nodeId}">
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
      state.selectedTreeNode = nodeId;
      renderStrategyTree(tree);
      if (node.kind === 'family' || node.kind === 'strategy') {
        state.search = nodeId;
        searchInput.value = nodeId;
        refreshCandidates();
      }
      showTreeInspector(nodeId, node, tree);
    });
  });
}

function isNodeEdgeRelated(nodeId, edge) {
  return edge.source === nodeId || edge.target === nodeId;
}

function renderAgentGraph(graph) {
  const width = 1520;
  const height = 390;
  const boxW = 156;
  const boxH = 68;
  const byId = Object.fromEntries((graph.nodes || []).map((n) => [n.id, n]));
  const selectedEdge = (graph.edges || []).find((e) => e.id === state.selectedGraphEdge) || null;

  const edgeSvg = (graph.edges || []).map((e) => {
    const a = byId[e.source];
    const b = byId[e.target];
    if (!a || !b) return '';
    const x1 = a.x + boxW / 2;
    const y1 = a.y + boxH / 2;
    const x2 = b.x + boxW / 2;
    const y2 = b.y + boxH / 2;
    const mx = (x1 + x2) / 2;
    const my = (y1 + y2) / 2 - 12;
    const labelWidth = Math.max(88, (String(e.label || '').length * 7) + 18);
    const active = state.selectedGraphEdge === e.id ? 'active' : '';
    return `
      <g class="graph-edge-group ${active}" data-edge-id="${e.id}">
        <line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" class="graph-edge-base" marker-end="url(#arrow)" />
        <line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" class="graph-edge-hit" />
        <rect x="${mx - labelWidth / 2}" y="${my - 15}" width="${labelWidth}" height="22" class="graph-edge-chip"></rect>
        <text x="${mx}" y="${my}" text-anchor="middle" dominant-baseline="middle" class="graph-edge-label">${escapeHtml(e.label || '')}</text>
      </g>
    `;
  }).join('');

  const nodeSvg = (graph.nodes || []).map((n) => {
    const active = state.selectedGraphNode === n.id;
    const dimmed = (state.selectedGraphNode && !active) || (selectedEdge && !isNodeEdgeRelated(n.id, selectedEdge));
    const groupClass = ['graph-node-group', active ? 'active' : '', dimmed ? 'dimmed' : ''].filter(Boolean).join(' ');
    return `
      <g transform="translate(${n.x},${n.y})" class="${groupClass}" data-node-id="${n.id}">
        <rect class="graph-node ${n.kind || ''} ${n.status || ''}" rx="18" ry="18" width="${boxW}" height="${boxH}"></rect>
        <text x="14" y="16" class="graph-node-kind">${escapeHtml(n.kind || 'node')}</text>
        <text x="${boxW / 2}" y="38" text-anchor="middle" class="graph-label">${String(n.label).split('\n').map((line, idx) => `<tspan x="${boxW / 2}" dy="${idx === 0 ? 0 : 17}">${escapeHtml(line)}</tspan>`).join('')}</text>
      </g>
    `;
  }).join('');

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
      state.selectedGraphNode = el.dataset.nodeId;
      state.selectedGraphEdge = null;
      renderAgentGraph(graph);
      const node = byId[el.dataset.nodeId];
      showNodeInspector(node, graph);
    });
  });
  graphStage.querySelectorAll('.graph-edge-group').forEach((el) => {
    el.addEventListener('click', () => {
      state.selectedGraphEdge = el.dataset.edgeId;
      state.selectedGraphNode = null;
      renderAgentGraph(graph);
      const edge = (graph.edges || []).find((e) => e.id === el.dataset.edgeId);
      showEdgeInspector(edge, graph);
    });
  });
}

function showCandidateInspector(detail) {
  const meta = detail.metadata || {};
  inspectorContent.classList.remove('empty');
  inspectorContent.innerHTML = `
    <div class="inspector-section">
      ${inspectorCard('Candidate Summary', `
        <p><strong>${escapeHtml(detail.name)}</strong> (${escapeHtml(detail.level)})<br>${escapeHtml(detail.mutation_summary)}</p>
        <div class="pills">
          ${pill(`failure ${(Number(detail.failure_rate || 0) * 100).toFixed(0)}%`)}
          ${pill(`strategy ${meta.strategy_leaf || 'n/a'}`)}
          ${pill(detail.archived ? 'archived' : (detail.status || 'generated'))}
        </div>
      `)}
      ${inspectorCard('Pipeline at a glance', `
        <div class="inspector-grid">
          ${kv('Agent A', 'build / mutate interpreter')}
          ${kv('Agent B', 'submit JSON AST program')}
          ${kv('Validator', 'JSON → AST → execute')}
          ${kv('Format', 'machine-checkable artifacts')}
        </div>
      `)}
      ${inspectorCard('What are ast_schema.json and tasks.json?', `
        <div class="inspector-grid">
          ${kv('ast_schema.json', 'JSON AST field contract for the solver')}
          ${kv('tasks.json', 'benchmark task list + expected behavior')}
        </div>
      `)}
      ${glossaryHtml('language_spec.json')}
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
      ${detail ? inspectorCard('Current Candidate Strategy Metadata', codeBlock(JSON.stringify({ strategy_family: detail.metadata?.strategy_family, strategy_leaf: detail.metadata?.strategy_leaf }, null, 2))) : ''}
    </div>
  `;
}

function showNodeInspector(node, graph) {
  const detail = state.selectedCandidate;
  if (!detail || !node) return;
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
      ${glossaryHtml(file)}
      ${inspectorCard('Relevant Artifact', `<p>${escapeHtml(file)}</p>${codeBlock(getArtifact(detail, file))}`)}
    </div>
  `;
}

function showEdgeInspector(edge, graph) {
  const detail = state.selectedCandidate;
  if (!detail || !edge) return;
  const inspectPath = edge.inspect === 'strategy' ? 'strategy_tree.json' : (edge.inspect || 'candidate.json');
  const preview = getArtifact(detail, inspectPath);
  inspectorContent.classList.remove('empty');
  inspectorContent.innerHTML = `
    <div class="inspector-section">
      ${inspectorCard('Information Exchange', `<p><strong>${escapeHtml(edge.label || edge.id)}</strong><br>${escapeHtml(edge.source)} → ${escapeHtml(edge.target)}<br>${escapeHtml(edge.exchange || '')}</p>`)}
      ${glossaryHtml(inspectPath)}
      ${inspectorCard('Inspected Artifact', `<p>${escapeHtml(inspectPath)}</p>${codeBlock(preview)}`)}
    </div>
  `;
}

async function selectCandidate(id, updateInspector = true) {
  state.selectedId = id;
  const detail = await getJson(`/api/candidates/${id}`);
  state.selectedCandidate = detail;
  selectedHint.textContent = `${detail.name} · ${detail.level}`;

  const tree = safeJsonParse(getArtifact(detail, 'strategy_tree.json') || '{"nodes":{},"edges":[]}', { nodes: {}, edges: [] });
  const graph = safeJsonParse(getArtifact(detail, 'agent_graph.json') || '{"nodes":[],"edges":[]}', { nodes: [], edges: [] });
  state.selectedTreeNode = tree.selected_path?.[tree.selected_path.length - 1] || 'root';
  state.selectedGraphNode = null;
  state.selectedGraphEdge = null;
  renderStrategyTree(tree);
  renderAgentGraph(graph);
  if (updateInspector) showCandidateInspector(detail);
  await refreshCandidates();
}

function addEventItem(event) {
  const el = document.createElement('div');
  el.className = 'event-item';
  el.innerHTML = `
    <div class="kind">${escapeHtml(event.kind)}</div>
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
  state.selectedTreeNode = 'root';
  state.selectedGraphNode = null;
  state.selectedGraphEdge = null;
  selectedHint.textContent = 'Select a candidate';
  strategyTreeStage.innerHTML = '';
  graphStage.innerHTML = '';
  inspectorContent.className = 'inspector empty';
  inspectorContent.innerHTML = emptyInspectorHtml();
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
  inspectorContent.innerHTML = emptyInspectorHtml();
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
