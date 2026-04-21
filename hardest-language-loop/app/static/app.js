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
const focusCard = document.getElementById('focusCard');
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
    summary: '이 후보 언어의 핵심 내용을 사람이 읽기 쉬운 마크다운 문서로 정리한 파일이다.',
    why: '후보의 수준, 부모, 변이 요약, 파이프라인 구조를 가장 빠르게 훑어볼 수 있는 입구다.',
  },
  'interpreter.ml': {
    title: '실행 가능한 언어 정의',
    summary: '후보 언어의 의미론을 실제로 실행 가능한 OCaml 인터프리터로 담아둔 파일이다.',
    why: '자연어 설명이 아니라 이 인터프리터가 언어의 최종 기준점이며, Validator도 이 정의를 따른다.',
  },
  'language_spec.json': {
    title: '후보 언어 구조 요약',
    summary: '점수, 변이 요약, 의미론 모드, 파이프라인 설정 같은 상위 메타데이터를 모아둔 파일이다.',
    why: '세부 프롬프트나 실행 결과를 보기 전에 후보의 성격을 빠르게 파악할 수 있다.',
  },
  'ast_schema.json': {
    title: 'AST 스키마 계약',
    summary: 'Agent B가 어떤 JSON 구조로 프로그램을 제출해야 하는지 정의한 계약서다.',
    why: '이 파일이 있어야 Solver 출력이 기계적으로 파싱되고, Validator가 AST로 복원할 수 있다.',
  },
  'tasks.json': {
    title: '벤치마크 태스크 묶음',
    summary: '후보 언어로 풀어야 할 문제 목록과 기대 동작을 담은 파일이다.',
    why: 'Agent B는 무엇을 풀지 여기서 읽고, Validator는 실제 실행 결과가 기대 동작과 맞는지 비교한다.',
  },
  'strategy_tree.json': {
    title: '전략 탐색 트리',
    summary: '이 후보가 어떤 전략 family와 leaf에서 나왔는지 구조적으로 기록한 파일이다.',
    why: '현재 후보가 전체 탐색 공간 안에서 어디에 위치하는지 설명해준다.',
  },
  'agent_graph.json': {
    title: '에이전트 그래프 데이터',
    summary: '노드, 엣지, 상태, 좌표, 정보 흐름을 프론트엔드가 그릴 수 있도록 담은 데이터다.',
    why: '그래프 UI는 이 파일을 읽어서 역할과 정보 흐름을 시각화한다.',
  },
  'program_attempts.json': {
    title: 'Solver 제출 결과 묶음',
    summary: 'Agent B가 만든 프로그램 시도들을 JSON AST 형태로 저장한 파일이다.',
    why: 'Validator는 바로 이 파일을 읽어 AST로 복원하고 인터프리터에 넣어 실행한다.',
  },
  'validator_result.json': {
    title: '결정론적 검증 결과',
    summary: '파싱 성공 여부, 실행 성공 여부, 출력 일치 여부 등 Validator의 최종 판정을 담은 파일이다.',
    why: '실험을 감상문이 아니라 재현 가능한 벤치마크 결과로 만드는 핵심 산출물이다.',
  },
  'candidate.json': {
    title: '원본 후보 레코드',
    summary: '데이터베이스에 저장된 후보의 원본 필드들을 그대로 덤프한 파일이다.',
    why: '가공 전 메타데이터를 확인할 때 기준점이 된다.',
  },
  'analysis.json': {
    title: '분석 요약',
    summary: 'failure rate 같은 후처리 분석 결과를 저장한 파일이다.',
    why: '후보 언어의 난이도와 특성을 실험 해석 관점에서 정리할 때 쓴다.',
  },
  'evaluations.json': {
    title: '개별 평가 결과',
    summary: '모델별·문제별 실행 결과를 한 줄씩 쌓아둔 평가 로그다.',
    why: '어떤 모델이 어떤 문제에서 실패했는지 세부 수준으로 추적할 수 있다.',
  },
  'prompts/agentA_interpreter_builder.txt': {
    title: 'Agent A 프롬프트',
    summary: '인터프리터를 생성하거나 변이하라고 지시하는 프롬프트다.',
    why: '언어 설계 공간을 어떤 방향으로 탐색할지 이 프롬프트가 정한다.',
  },
  'prompts/agentB_solver.txt': {
    title: 'Agent B 프롬프트',
    summary: '선택된 언어 의미론 아래에서 프로그램을 생성하라고 지시하는 프롬프트다.',
    why: '언어 정의와 실제 Solver 모델 사이를 연결하는 직접적인 인터페이스다.',
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

function percent(value, digits = 0) {
  return `${(Number(value || 0) * 100).toFixed(digits)}%`;
}

function pill(text, tone = '') {
  return `<span class="pill ${tone}">${escapeHtml(text)}</span>`;
}

function metricCard(label, value, sub = '') {
  return `
    <div class="metric-card">
      <div class="label">${escapeHtml(label)}</div>
      <div class="value">${escapeHtml(String(value))}</div>
      <div class="sub">${escapeHtml(sub)}</div>
    </div>
  `;
}

function codeBlock(text = '') {
  return `<pre class="code-block">${escapeHtml(text)}</pre>`;
}

function rawDetails(title, text = '') {
  return `
    <details class="raw-details">
      <summary>${escapeHtml(title)}</summary>
      ${codeBlock(text)}
    </details>
  `;
}

function inspectorCard(title, bodyHtml) {
  return `<div class="inspector-card"><h3>${escapeHtml(title)}</h3>${bodyHtml}</div>`;
}

function kv(label, value) {
  return `
    <div class="key-value">
      <div class="k">${escapeHtml(label)}</div>
      <div class="v">${escapeHtml(String(value))}</div>
    </div>
  `;
}

function panelEmpty(title, copy) {
  return `
    <div class="empty-state compact">
      <div class="empty-title">${escapeHtml(title)}</div>
      <div class="empty-copy">${escapeHtml(copy)}</div>
    </div>
  `;
}

function emptyInspectorHtml() {
  return `
    <div class="empty-state">
      <div class="empty-icon">◎</div>
      <div class="empty-title">후보, 노드, 또는 엣지를 선택해줘</div>
      <div class="empty-copy">오른쪽 인스펙터에는 프롬프트, JSON 계약, 태스크 정의, 실행 결과, 설명 카드가 표시된다.</div>
    </div>
  `;
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
      summary: '실행 과정에서 생성된 추가 산출물이다.',
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

function getArtifact(detail, path) {
  return detail?.artifacts?.files?.[path] || '';
}

function updateConfigHint(settings, keyInfo) {
  const modelName = settings?.agent2_model || 'gpt-5.4';
  const keyText = keyInfo?.configured ? keyInfo.masked : '설정 안 됨';
  configHint.textContent = `Agent2: ${modelName} · OpenAI key: ${keyText}`;
}

async function loadConfig() {
  const data = await getJson('/api/config');
  const current = data.settings?.agent2_model || 'gpt-5.4';
  agent2ModelSelect.innerHTML = data.openai_models.map((name) => `<option value="${name}">${name}</option>`).join('');
  agent2ModelSelect.value = current;
  updateConfigHint(data.settings, data.openai_api_key);
}

async function updateConfig(payload) {
  const data = await getJson('/api/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  updateConfigHint(data.settings, data.openai_api_key);
  openaiKeyInput.value = '';
  await refreshOverview();
  await refreshCandidates({ autoSelect: false });
  if (state.selectedId) {
    await selectCandidate(state.selectedId, { updateInspector: false });
  }
}

async function refreshOverview() {
  const data = await getJson('/api/overview');
  state.overview = data;
  const loopState = data.state || {};
  const hardest = data.hardest || {};
  const settings = data.settings || {};
  summaryBar.innerHTML = [
    metricCard('루프 상태', (loopState.status || 'idle').toUpperCase(), loopState.note || '실행 대기 중'),
    metricCard('Iteration', loopState.iteration ?? 0, '완료된 라운드 수'),
    metricCard('후보 수', data.stats.total_candidates, '생성된 candidate'),
    metricCard('Archive', data.stats.archived_candidates, 'hard-but-valid'),
    metricCard('Agent 2 모델', settings.agent2_model || 'gpt-5.4', '현재 solver'),
    metricCard('현재 hardest', hardest.name || '—', hardest.failure_rate != null ? `failure ${percent(hardest.failure_rate)}` : '아직 없음'),
  ].join('');
  renderBenchmark();
}

function renderBenchmark() {
  const benchmark = state.overview?.benchmark || { models: [], tasks: [], levels: [] };

  const makeSection = (title, rows, titleField, valueField, prefix, fallback) => {
    if (!rows?.length) {
      return `<div class="summary-card"><h3>${escapeHtml(title)}</h3><p>${escapeHtml(fallback)}</p></div>`;
    }
    return `
      <div class="summary-card">
        <h3>${escapeHtml(title)}</h3>
        <div class="summary-list">
          ${rows.slice(0, 4).map((row) => `
            <div class="summary-row">
              <div class="summary-row-head">
                <span>${escapeHtml(row[titleField])}</span>
                <strong>${escapeHtml(prefix)} ${escapeHtml(percent(row[valueField]))}</strong>
              </div>
              <div class="pills">
                ${'n' in row ? pill(`${row.n} samples`) : ''}
                ${'archived_n' in row ? pill(`${row.archived_n} archived`) : ''}
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  };

  benchmarkContent.innerHTML = [
    makeSection('모델별', benchmark.models, 'model_name', 'pass_rate', 'Pass', '아직 모델 결과가 없음'),
    makeSection('문제별', benchmark.tasks, 'task_name', 'pass_rate', 'Pass', '아직 태스크 결과가 없음'),
    makeSection('레벨별', benchmark.levels, 'level', 'avg_failure', 'Failure', '아직 레벨 결과가 없음'),
  ].join('');
}

function renderFocusCard() {
  const detail = state.selectedCandidate;
  if (!detail) {
    focusCard.innerHTML = panelEmpty('선택된 candidate가 없음', '왼쪽 후보 목록에서 하나를 고르면 여기에서 핵심 상태를 바로 볼 수 있다.');
    return;
  }

  const meta = detail.metadata || {};
  focusCard.innerHTML = `
    <div class="focus-hero">
      <div>
        <div class="focus-kicker">Selected candidate</div>
        <div class="focus-title">${escapeHtml(detail.name)}</div>
        <div class="focus-copy">${escapeHtml(detail.mutation_summary)}</div>
      </div>
      <div class="focus-pills">
        ${pill(detail.level, 'tone-neutral')}
        ${pill(`failure ${percent(detail.failure_rate)}`, 'tone-accent')}
        ${pill(meta.strategy_leaf || 'strategy n/a', 'tone-purple')}
        ${pill(detail.archived ? 'archived' : (detail.status || 'generated'), detail.archived ? 'tone-green' : 'tone-neutral')}
      </div>
    </div>
    <div class="focus-grid">
      ${kv('Parent', meta.agent1_parent || detail.parent_id || 'None')}
      ${kv('Agent 2 모델', meta.agent2_model || 'gpt-5.4')}
      ${kv('Similarity', detail.similarity_score ?? '—')}
      ${kv('Conflict', detail.conflict_score ?? '—')}
      ${kv('Solvable', detail.solvable_score ?? '—')}
      ${kv('Novelty', detail.novelty_score ?? '—')}
    </div>
  `;
}

function filteredCandidates() {
  const q = state.search.trim().toLowerCase();
  return state.candidates.filter((candidate) => {
    if (state.archivedOnly && !candidate.archived) return false;
    if (!q) return true;
    const meta = candidate.metadata || {};
    const hay = [
      candidate.name,
      candidate.level,
      candidate.mutation_summary,
      meta.strategy_family || '',
      meta.strategy_leaf || '',
      candidate.status || '',
    ].join(' ').toLowerCase();
    return hay.includes(q);
  });
}

function candidateRow(candidate) {
  const active = candidate.id === state.selectedId ? 'active' : '';
  const meta = candidate.metadata || {};
  return `
    <div class="candidate-item ${active}" data-id="${candidate.id}">
      <div class="candidate-topline">
        <div class="candidate-title">${escapeHtml(candidate.name)}</div>
        <div class="candidate-level">${escapeHtml(candidate.level)}</div>
      </div>
      <div class="candidate-meta candidate-summary">${escapeHtml(candidate.mutation_summary)}</div>
      <div class="pills">
        ${pill(`failure ${percent(candidate.failure_rate)}`)}
        ${pill(meta.strategy_leaf || 'strategy n/a')}
        ${pill(candidate.archived ? 'archived' : (candidate.status || 'generated'))}
      </div>
    </div>
  `;
}

function renderCandidateList() {
  const items = filteredCandidates();
  if (!items.length) {
    candidateList.innerHTML = '<div class="candidate-empty">조건에 맞는 후보가 아직 없음</div>';
    return;
  }
  candidateList.innerHTML = items.map(candidateRow).join('');
  candidateList.querySelectorAll('.candidate-item').forEach((el) => {
    el.addEventListener('click', () => selectCandidate(el.dataset.id));
  });
}

async function refreshCandidates({ autoSelect = true } = {}) {
  const data = await getJson('/api/candidates?limit=80');
  state.candidates = data.items;
  renderCandidateList();

  if (state.selectedId) {
    const stillExists = state.candidates.some((item) => item.id === state.selectedId);
    if (!stillExists) {
      clearSelection();
    }
  }

  const items = filteredCandidates();
  if (autoSelect && !state.selectedId && items[0]) {
    await selectCandidate(items[0].id, { updateInspector: true });
  }
}

function clearSelection() {
  state.selectedId = null;
  state.selectedCandidate = null;
  state.selectedTreeNode = 'root';
  state.selectedGraphNode = null;
  state.selectedGraphEdge = null;
  selectedHint.textContent = '후보를 선택해줘';
  renderFocusCard();
  strategyTreeStage.innerHTML = panelEmpty('전략 트리가 비어 있음', '후보를 선택하면 어떤 전략 family와 leaf에서 나왔는지 여기에 표시된다.');
  graphStage.innerHTML = panelEmpty('실행 그래프가 비어 있음', '후보를 선택하면 Agent A → Agent B → Validator 흐름이 여기 나타난다.');
  inspectorContent.className = 'inspector empty';
  inspectorContent.innerHTML = emptyInspectorHtml();
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
  if (!tree?.nodes || !Object.keys(tree.nodes).length) {
    strategyTreeStage.innerHTML = panelEmpty('전략 데이터가 없음', '이 candidate의 전략 트리 정보가 아직 생성되지 않았다.');
    return;
  }

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
        renderCandidateList();
      }
      showTreeInspector(nodeId, node, tree);
    });
  });
}

function isNodeEdgeRelated(nodeId, edge) {
  return edge.source === nodeId || edge.target === nodeId;
}

function renderAgentGraph(graph) {
  if (!graph?.nodes?.length) {
    graphStage.innerHTML = panelEmpty('그래프 데이터가 없음', '후보가 생성되면 에이전트와 아티팩트 흐름이 여기에 표시된다.');
    return;
  }

  const width = 1560;
  const height = 420;
  const boxW = 174;
  const boxH = 82;
  const byId = Object.fromEntries((graph.nodes || []).map((node) => [node.id, node]));
  const selectedEdge = (graph.edges || []).find((edge) => edge.id === state.selectedGraphEdge) || null;

  const edgeSvg = (graph.edges || []).map((edge) => {
    const source = byId[edge.source];
    const target = byId[edge.target];
    if (!source || !target) return '';
    const x1 = source.x + boxW / 2;
    const y1 = source.y + boxH / 2;
    const x2 = target.x + boxW / 2;
    const y2 = target.y + boxH / 2;
    const mx = (x1 + x2) / 2;
    const my = (y1 + y2) / 2 - 16;
    const labelWidth = Math.max(110, String(edge.label || '').length * 7 + 24);
    const active = state.selectedGraphEdge === edge.id ? 'active' : '';
    return `
      <g class="graph-edge-group ${active}" data-edge-id="${edge.id}">
        <line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" class="graph-edge-base" marker-end="url(#arrow)" />
        <line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" class="graph-edge-hit" />
        <rect x="${mx - labelWidth / 2}" y="${my - 15}" width="${labelWidth}" height="24" class="graph-edge-chip"></rect>
        <text x="${mx}" y="${my - 2}" text-anchor="middle" dominant-baseline="middle" class="graph-edge-label">${escapeHtml(edge.label || '')}</text>
      </g>
    `;
  }).join('');

  const nodeSvg = (graph.nodes || []).map((node) => {
    const active = state.selectedGraphNode === node.id;
    const dimmed = (state.selectedGraphNode && !active) || (selectedEdge && !isNodeEdgeRelated(node.id, selectedEdge));
    const className = ['graph-node-group', active ? 'active' : '', dimmed ? 'dimmed' : ''].filter(Boolean).join(' ');
    return `
      <g transform="translate(${node.x},${node.y})" class="${className}" data-node-id="${node.id}">
        <rect class="graph-node ${node.kind || ''} ${node.status || ''}" rx="20" ry="20" width="${boxW}" height="${boxH}"></rect>
        <text x="14" y="18" class="graph-node-kind">${escapeHtml(node.kind || 'node')}</text>
        <text x="${boxW / 2}" y="42" text-anchor="middle" class="graph-label">${String(node.label || '').split('\n').map((line, idx) => `<tspan x="${boxW / 2}" dy="${idx === 0 ? 0 : 18}">${escapeHtml(line)}</tspan>`).join('')}</text>
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
      showNodeInspector(byId[el.dataset.nodeId]);
    });
  });

  graphStage.querySelectorAll('.graph-edge-group').forEach((el) => {
    el.addEventListener('click', () => {
      state.selectedGraphEdge = el.dataset.edgeId;
      state.selectedGraphNode = null;
      renderAgentGraph(graph);
      const edge = (graph.edges || []).find((item) => item.id === el.dataset.edgeId);
      showEdgeInspector(edge);
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
          ${pill(`failure ${percent(detail.failure_rate)}`, 'tone-accent')}
          ${pill(meta.strategy_leaf || 'strategy n/a', 'tone-purple')}
          ${pill(detail.archived ? 'archived' : (detail.status || 'generated'), detail.archived ? 'tone-green' : '')}
        </div>
      `)}
      ${inspectorCard('파이프라인 한눈에 보기', `
        <div class="inspector-grid">
          ${kv('Agent A', '인터프리터 생성 / 변이')}
          ${kv('Agent B', 'JSON AST 프로그램 제출')}
          ${kv('Validator', 'JSON → AST → 실행')}
          ${kv('Format', '기계 검증 가능한 산출물')}
        </div>
      `)}
      ${inspectorCard('핵심 파일 두 개', `
        <div class="inspector-grid">
          ${kv('ast_schema.json', 'Solver가 따라야 하는 JSON AST 형식 계약')}
          ${kv('tasks.json', '문제 목록과 기대 동작 정의')}
        </div>
      `)}
      ${artifactGuideCard(detail)}
      ${glossaryHtml('language_spec.json')}
      ${rawDetails('language_spec.json raw 보기', getArtifact(detail, 'language_spec.json'))}
    </div>
  `;
}

function showTreeInspector(nodeId, node, tree) {
  const detail = state.selectedCandidate;
  inspectorContent.classList.remove('empty');
  inspectorContent.innerHTML = `
    <div class="inspector-section">
      ${inspectorCard('전략 노드', `<p><strong>${escapeHtml(node.label || nodeId)}</strong><br>kind: ${escapeHtml(node.kind || '')}<br>status: ${escapeHtml(node.status || '')}${node.score != null ? `<br>score: ${node.score}` : ''}${node.note ? `<br>${escapeHtml(node.note)}` : ''}</p>`)}
      ${inspectorCard('선택된 경로', `<p>${(tree.selected_path || []).map((item) => escapeHtml(item)).join(' → ')}</p>`)}
      ${detail ? inspectorCard('현재 후보의 전략 메타데이터', rawDetails('metadata raw 보기', JSON.stringify({ strategy_family: detail.metadata?.strategy_family, strategy_leaf: detail.metadata?.strategy_leaf }, null, 2))) : ''}
    </div>
  `;
}

function showNodeInspector(node) {
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
      ${rawDetails(`${file} raw 보기`, getArtifact(detail, file))}
    </div>
  `;
}

function showEdgeInspector(edge) {
  const detail = state.selectedCandidate;
  if (!detail || !edge) return;
  const inspectPath = edge.inspect === 'strategy' ? 'strategy_tree.json' : (edge.inspect || 'candidate.json');
  inspectorContent.classList.remove('empty');
  inspectorContent.innerHTML = `
    <div class="inspector-section">
      ${inspectorCard('정보 교환 설명', `<p><strong>${escapeHtml(edge.label || edge.id)}</strong><br>${escapeHtml(edge.source)} → ${escapeHtml(edge.target)}<br>${escapeHtml(edge.exchange || '')}</p>`)}
      ${glossaryHtml(inspectPath)}
      ${rawDetails(`${inspectPath} raw 보기`, getArtifact(detail, inspectPath))}
    </div>
  `;
}

async function selectCandidate(id, { updateInspector = true } = {}) {
  state.selectedId = id;
  const detail = await getJson(`/api/candidates/${id}`);
  state.selectedCandidate = detail;
  selectedHint.textContent = `${detail.name} · ${detail.level}`;
  renderFocusCard();

  const tree = safeJsonParse(getArtifact(detail, 'strategy_tree.json') || '{"nodes":{},"edges":[]}', { nodes: {}, edges: [] });
  const graph = safeJsonParse(getArtifact(detail, 'agent_graph.json') || '{"nodes":[],"edges":[]}', { nodes: [], edges: [] });

  state.selectedTreeNode = tree.selected_path?.[tree.selected_path.length - 1] || 'root';
  state.selectedGraphNode = null;
  state.selectedGraphEdge = null;

  renderCandidateList();
  renderStrategyTree(tree);
  renderAgentGraph(graph);

  if (updateInspector) {
    showCandidateInspector(detail);
  }
}

function eventSummary(event) {
  const payload = event.payload || {};
  switch (event.kind) {
    case 'bootstrap':
      return {
        title: '초기화 완료',
        summary: payload.note || payload.message || '빈 상태 부트스트랩이 완료됨',
      };
    case 'loop_started':
      return {
        title: '루프 시작',
        summary: payload.message || 'Agent loop가 시작됨',
      };
    case 'loop_paused':
      return {
        title: '루프 일시정지',
        summary: payload.message || 'Agent loop가 멈춤',
      };
    case 'loop_reset':
      return {
        title: '루프 리셋',
        summary: payload.message || '상태와 후보가 모두 초기화됨',
      };
    case 'candidate_generated':
      return {
        title: `${payload.name || payload.candidate_id || 'candidate'} 생성`,
        summary: `iteration ${payload.iteration || '-'} · level ${payload.level || '-'}${payload.parent ? ` · parent ${payload.parent}` : ''}`,
      };
    case 'benchmark_completed':
      return {
        title: '벤치마크 완료',
        summary: `${payload.candidate_id || ''} · failure ${percent(payload.failure_rate)}${payload.archived ? ' · archive 진입' : ''}`,
      };
    case 'archive_updated':
      return {
        title: 'Archive 업데이트',
        summary: payload.message || '새 hardest candidate가 archive에 추가됨',
      };
    case 'config_updated':
      return {
        title: '설정 변경',
        summary: payload.message || '설정이 갱신됨',
      };
    default:
      return {
        title: event.kind,
        summary: payload.message || '세부 payload를 열어 확인할 수 있음',
      };
  }
}

function addEventItem(event) {
  const info = eventSummary(event);
  const el = document.createElement('div');
  el.className = 'event-item';
  el.innerHTML = `
    <div class="event-head">
      <div>
        <div class="kind">${escapeHtml(info.title)}</div>
        <div class="event-summary">${escapeHtml(info.summary)}</div>
      </div>
      <div class="candidate-meta">${new Date(event.created_at).toLocaleString()}</div>
    </div>
    ${rawDetails('payload raw 보기', JSON.stringify(event.payload, null, 2))}
  `;
  eventList.prepend(el);
}

async function preloadEvents() {
  const data = await getJson('/api/events?limit=40');
  eventList.innerHTML = '';
  data.items.forEach((event) => {
    state.lastEventId = Math.max(state.lastEventId, event.id);
    addEventItem(event);
  });
}

async function refreshSelectedIfNeeded() {
  if (!state.selectedId) return;
  const exists = state.candidates.some((item) => item.id === state.selectedId);
  if (!exists) {
    clearSelection();
    return;
  }
  await selectCandidate(state.selectedId, { updateInspector: false });
}

async function post(url) {
  await getJson(url, { method: 'POST' });
  await refreshOverview();
  await refreshCandidates({ autoSelect: false });
  await refreshSelectedIfNeeded();
}

searchInput.addEventListener('input', (e) => {
  state.search = e.target.value;
  renderCandidateList();
});

archivedOnlyInput.addEventListener('change', (e) => {
  state.archivedOnly = e.target.checked;
  renderCandidateList();
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
  clearSelection();
  renderCandidateList();
});

function connectEvents() {
  const source = new EventSource('/api/events/stream');
  source.onopen = () => {
    eventStatus.textContent = 'live';
  };
  source.onerror = () => {
    eventStatus.textContent = 'reconnecting…';
  };
  source.onmessage = async (msg) => {
    const event = JSON.parse(msg.data);
    if (event.id <= state.lastEventId) return;
    state.lastEventId = event.id;
    addEventItem(event);
    await refreshOverview();
    await refreshCandidates({ autoSelect: false });
    await refreshSelectedIfNeeded();
  };
}

async function init() {
  inspectorContent.innerHTML = emptyInspectorHtml();
  renderFocusCard();
  strategyTreeStage.innerHTML = panelEmpty('전략 트리가 비어 있음', '후보를 선택하면 여기에 전략 탐색 구조가 나타난다.');
  graphStage.innerHTML = panelEmpty('실행 그래프가 비어 있음', '후보를 선택하면 Agent A → Agent B → Validator 흐름이 나타난다.');
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
