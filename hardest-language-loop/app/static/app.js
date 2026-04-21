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
  'spec.md': {
    title: '후보 언어 개요 문서',
    summary: '이 후보 언어의 핵심 정보를 사람이 읽기 쉬운 마크다운 문서로 정리한 파일이다.',
    why: '후보의 수준, 부모 후보, 변이 요약, 파이프라인 구조를 빠르게 훑어볼 때 가장 먼저 보는 요약본이다.',
  },
  'ast_schema.json': {
    title: 'AST 스키마 계약',
    summary: 'Agent B가 어떤 JSON 구조로 프로그램을 제출해야 하는지 정의한 계약서다. 노드 종류, 필드 이름, 중첩 규칙이 여기에 들어간다.',
    why: '이 파일이 없으면 Solver가 제멋대로 JSON을 만들 수 있고, Validator는 그것을 언어 AST로 안정적으로 복원할 수 없다.',
  },
  'tasks.json': {
    title: '벤치마크 태스크 묶음',
    summary: '후보 언어마다 풀어야 할 문제 목록을 담은 파일이다. 프롬프트, 카테고리, 기대 동작이 함께 들어간다.',
    why: 'Agent B는 이 파일을 보고 무엇을 풀어야 하는지 결정하고, Validator는 실제 실행 결과가 기대 동작과 맞는지 비교한다.',
  },
  'interpreter.ml': {
    title: '실행 가능한 언어 정의',
    summary: '후보 언어의 의미론을 실제로 실행 가능한 OCaml 인터프리터로 담아둔 파일이다.',
    why: '모호한 자연어 설명 대신, 이 파일이 언어의 최종 기준점이 된다. Validator도 결국 이 인터프리터를 기준으로 실행한다.',
  },
  'agent_graph.json': {
    title: '에이전트 그래프 데이터',
    summary: '노드와 엣지의 배치, 종류, 상태, 정보 흐름을 프론트엔드가 그릴 수 있도록 구조화한 파일이다.',
    why: '그래프 UI는 이 파일을 읽어서 어떤 에이전트가 어떤 artifact를 만들고, 어떤 정보가 어디로 흐르는지 시각화한다.',
  },
  'program_attempts.json': {
    title: 'Solver 제출 결과 묶음',
    summary: 'Agent B가 만든 프로그램 시도들을 JSON AST 형태로 저장한 파일이다. 재시도나 변형 버전도 함께 담을 수 있다.',
    why: 'Validator는 바로 이 파일의 내용을 읽어서 AST로 복원하고 인터프리터에 넣어 실행한다.',
  },
  'validator_result.json': {
    title: '결정론적 검증 결과',
    summary: '파싱 성공 여부, 실행 성공 여부, 출력 일치 여부 등 Validator의 최종 판정을 담은 파일이다.',
    why: '이 파일 덕분에 실험이 단순한 인상평이 아니라, 재현 가능한 벤치마크 결과로 남는다.',
  },
  'prompts/agentA_interpreter_builder.txt': {
    title: 'Agent A 프롬프트',
    summary: '인터프리터를 새로 만들거나 기존 것을 변형하라고 지시하는 프롬프트다.',
    why: '언어 설계 공간을 어떤 방향으로 탐색할지, 어떤 제약을 둘지 이 프롬프트가 정한다.',
  },
  'prompts/agentB_solver.txt': {
    title: 'Agent B 프롬프트',
    summary: '선택된 언어 의미론 아래에서 프로그램을 생성하라고 지시하는 프롬프트다.',
    why: '언어 정의와 실제 Solver 모델 사이를 이어주는 직접적인 인터페이스 역할을 한다.',
  },
  'language_spec.json': {
    title: '후보 언어 구조 요약',
    summary: '후보 점수, 변이 요약, 의미론 모드, 파이프라인 설정 같은 상위 메타데이터를 모아둔 파일이다.',
    why: '세부 프롬프트와 실행 결과를 보기 전에, 이 후보가 어떤 성격인지 빠르게 파악할 수 있다.',
  },
  'strategy_tree.json': {
    title: '전략 탐색 트리',
    summary: '이 후보가 어떤 전략 family와 leaf에서 나왔는지 구조적으로 기록한 파일이다.',
    why: '현재 후보가 전체 탐색 공간 안에서 어디에 위치하는지 설명해준다.',
  },
  'candidate.json': {
    title: '원본 후보 레코드',
    summary: '데이터베이스에 저장된 후보의 원본 필드들을 JSON으로 덤프한 파일이다.',
    why: '가공 전 원본 메타데이터를 그대로 보고 싶을 때 기준점이 된다.',
  },
  'analysis.json': {
    title: '분석 요약',
    summary: '실행 결과를 바탕으로 계산된 failure rate나 추가 분석값을 모아둔 파일이다.',
    why: '후보 언어의 난이도와 특성을 후처리 관점에서 해석할 때 필요하다.',
  },
  'evaluations.json': {
    title: '개별 평가 결과',
    summary: '모델별·문제별 실행 결과를 한 줄씩 쌓아둔 평가 로그다.',
    why: '어떤 모델이 어떤 문제에서 실패했는지 세부 레벨에서 추적할 수 있다.',
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

function artifactGuideCard(detail) {
  const files = Object.keys(detail?.artifacts?.files || {});
  if (!files.length) return '';
  const rows = files.map((path) => {
    const entry = artifactGlossary[path] || {
      title: '보조 아티팩트',
      summary: '이 파일은 현재 후보 실행 과정에서 생성된 추가 산출물이다.',
      why: '필요할 때 raw 내용을 직접 열어 세부 상태를 확인할 수 있다.',
    };
    return `
      <div class="artifact-row">
        <div class="artifact-path">${escapeHtml(path)}</div>
        <div class="artifact-title">${escapeHtml(entry.title)}</div>
        <div class="artifact-copy">${escapeHtml(entry.summary)}</div>
      </div>
    `;
  }).join('');
  return inspectorCard('아티팩트 전체 설명', `<div class="artifact-guide">${rows}</div>`);
}

function emptyInspectorHtml() {
  return `
    <div class="empty-state">
      <div class="empty-icon">◎</div>
      <div class="empty-title">후보, 노드, 또는 엣지를 선택해줘</div>
      <div class="empty-copy">Inspector에는 프롬프트, JSON 계약, 태스크 정의, 검증 결과 아티팩트가 표시된다.</div>
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
      ${inspectorCard('후보 요약', `
        <p><strong>${escapeHtml(detail.name)}</strong> (${escapeHtml(detail.level)})<br>${escapeHtml(detail.mutation_summary)}</p>
        <div class="pills">
          ${pill(`failure ${(Number(detail.failure_rate || 0) * 100).toFixed(0)}%`)}
          ${pill(`strategy ${meta.strategy_leaf || 'n/a'}`)}
          ${pill(detail.archived ? 'archived' : (detail.status || 'generated'))}
        </div>
      `)}
      ${inspectorCard('파이프라인 한눈에 보기', `
        <div class="inspector-grid">
          ${kv('Agent A', '인터프리터 생성 / 변이')}
          ${kv('Agent B', 'JSON AST 프로그램 제출')}
          ${kv('Validator', 'JSON → AST → 실행')}
          ${kv('Format', '기계 검증 가능한 아티팩트')}
        </div>
      `)}
      ${inspectorCard('ast_schema.json / tasks.json 이란?', `
        <div class="inspector-grid">
          ${kv('ast_schema.json', 'Solver가 따라야 하는 JSON AST 필드 계약')}
          ${kv('tasks.json', '벤치마크 문제 목록 + 기대 동작')}
        </div>
      `)}
      ${artifactGuideCard(detail)}
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
      ${inspectorCard('전략 노드', `<p><strong>${escapeHtml(node.label || nodeId)}</strong><br>kind: ${escapeHtml(node.kind || '')}<br>status: ${escapeHtml(node.status || '')}${node.score != null ? `<br>score: ${node.score}` : ''}${node.note ? `<br>${escapeHtml(node.note)}` : ''}</p>`)}
      ${inspectorCard('선택된 경로', `<p>${(tree.selected_path || []).map((x) => escapeHtml(x)).join(' → ')}</p>`)}
      ${detail ? inspectorCard('현재 후보의 전략 메타데이터', codeBlock(JSON.stringify({ strategy_family: detail.metadata?.strategy_family, strategy_leaf: detail.metadata?.strategy_leaf }, null, 2))) : ''}
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
      ${inspectorCard('선택한 노드', `<p><strong>${escapeHtml(node.label)}</strong><br>kind: ${escapeHtml(node.kind || '')}<br>status: ${escapeHtml(node.status || '')}</p>`)}
      ${glossaryHtml(file)}
      ${inspectorCard('연결된 아티팩트', `<p>${escapeHtml(file)}</p>${codeBlock(getArtifact(detail, file))}`)}
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
      ${inspectorCard('정보 교환 설명', `<p><strong>${escapeHtml(edge.label || edge.id)}</strong><br>${escapeHtml(edge.source)} → ${escapeHtml(edge.target)}<br>${escapeHtml(edge.exchange || '')}</p>`)}
      ${glossaryHtml(inspectPath)}
      ${inspectorCard('검사 중인 아티팩트', `<p>${escapeHtml(inspectPath)}</p>${codeBlock(preview)}`)}
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
