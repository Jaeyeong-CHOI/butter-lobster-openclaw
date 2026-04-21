const state = {
  selectedId: null,
  selectedCandidate: null,
  lastEventId: 0,
  candidates: [],
  overview: null,
  config: null,
  search: '',
  archivedOnly: false,
  treeFilter: 'root',
  selectedTreeNode: 'root',
  selectedGraphNode: null,
  selectedGraphEdge: null,
};

const summaryBar = document.getElementById('summaryBar');
const candidateList = document.getElementById('candidateList');
const strategyTreeStage = document.getElementById('strategyTreeStage');
const graphStage = document.getElementById('graphStage');
const focusCard = document.getElementById('focusCard');
const solverBenchMonitor = document.getElementById('solverBenchMonitor');
const metricGuide = document.getElementById('metricGuide');
const inspectorContent = document.getElementById('inspectorContent');
const benchmarkContent = document.getElementById('benchmarkContent');
const eventList = document.getElementById('eventList');
const eventStatus = document.getElementById('eventStatus');
const selectedHint = document.getElementById('selectedHint');
const searchInput = document.getElementById('searchInput');
const archivedOnlyInput = document.getElementById('archivedOnly');
const configHint = document.getElementById('configHint');
const settingsPreview = document.getElementById('settingsPreview');
const openSettingsBtn = document.getElementById('openSettingsBtn');
const closeSettingsBtn = document.getElementById('closeSettingsBtn');
const saveSettingsBtn = document.getElementById('saveSettingsBtn');
const settingsModal = document.getElementById('settingsModal');
const settingsBackdrop = document.getElementById('settingsBackdrop');
const startBtn = document.getElementById('startBtn');
const pauseBtn = document.getElementById('pauseBtn');
const stepBtn = document.getElementById('stepBtn');
const resetBtn = document.getElementById('resetBtn');

const openaiKeyInput = document.getElementById('openaiKeyInput');
const openaiKeyStatus = document.getElementById('openaiKeyStatus');
const openaiClearKeyBtn = document.getElementById('openaiClearKeyBtn');
const agentAModelSelect = document.getElementById('agentAModelSelect');
const agentAThinkingSelect = document.getElementById('agentAThinkingSelect');
const agentATemperatureInput = document.getElementById('agentATemperatureInput');
const solverModelChecklist = document.getElementById('solverModelChecklist');
const solverThinkingSelect = document.getElementById('solverThinkingSelect');
const solverTemperatureInput = document.getElementById('solverTemperatureInput');
const solverRepeatCountInput = document.getElementById('solverRepeatCountInput');
const solverParallelismInput = document.getElementById('solverParallelismInput');

const artifactGlossary = {
  'spec.md': { title: '후보 언어 개요 문서', summary: '이 후보 언어의 핵심 내용을 사람이 읽기 쉬운 마크다운으로 요약한 문서다.', why: '후보의 방향과 변이 의도를 가장 빠르게 파악할 수 있다.' },
  'interpreter.ml': { title: '실행 가능한 언어 정의', summary: '후보 언어의 의미론을 직접 실행 가능한 OCaml 인터프리터로 담은 파일이다.', why: '이 파일이 언어의 최종 기준점이며, validator도 결국 이 정의를 따른다.' },
  'language_spec.json': { title: '후보 언어 구조 요약', summary: '후보의 점수, 파이프라인 설정, solver bench 설정 같은 상위 메타데이터를 담는다.', why: '세부 실행 아티팩트로 들어가기 전에 후보의 성격을 빠르게 파악할 수 있다.' },
  'ast_schema.json': { title: 'AST 스키마 계약', summary: 'Solver가 어떤 JSON AST 구조를 반환해야 하는지 정의한 계약서다.', why: 'JSON 출력이 기계적으로 파싱되고 validator가 AST로 복원될 수 있게 한다.' },
  'tasks.json': { title: '벤치마크 태스크 묶음', summary: '각 문제의 프롬프트, 기대 동작, 테스트 케이스를 정의한다.', why: '모델이 무엇을 풀어야 하는지와 validator가 무엇을 비교해야 하는지를 동시에 결정한다.' },
  'strategy_tree.json': { title: '전략 탐색 트리', summary: '이 candidate가 전체 탐색 트리에서 어느 family/leaf에 속하는지 담는다.', why: '현재 후보가 전체 탐색의 어느 지점에서 왔는지 설명한다.' },
  'agent_graph.json': { title: '에이전트 그래프 데이터', summary: '노드, 엣지, 상태, 정보 흐름을 프론트엔드가 그릴 수 있도록 구조화한 데이터다.', why: '그래프 UI는 이 파일을 기반으로 역할/정보 흐름을 시각화한다.' },
  'program_attempts.json': { title: 'Solver 제출 결과 묶음', summary: '모델별·문제별·반복별 JSON AST 제출 결과를 저장한다.', why: '이 파일이 실제 validator 입력이며, 모델이 낸 프로그램 자체를 보여준다.' },
  'validator_result.json': { title: '실행 기반 검증 결과', summary: 'JSON AST 파싱, OCaml AST 변환, interpreter 실행, 테스트케이스 비교 결과를 담는다.', why: '실험을 실제 실행 기반 벤치마크로 만드는 핵심 산출물이다.' },
  'candidate.json': { title: '원본 후보 레코드', summary: '후보의 원본 DB 레코드를 그대로 덤프한 파일이다.', why: '가공 전 메타데이터를 확인하는 기준점이 된다.' },
  'analysis.json': { title: '후처리 분석', summary: 'failure rate, hardest model, prior boundary 같은 후처리 분석 결과를 담는다.', why: '후보의 난이도와 특성을 정리하는 데 필요하다.' },
  'evaluations.json': { title: '개별 평가 로그', summary: '각 모델/문제/반복 시도에 대한 개별 결과를 쌓아둔 로그다.', why: '어느 모델이 어떤 문제에서 몇 번 성공했는지 세부 추적이 가능하다.' },
  'prompts/agentA_interpreter_builder.txt': { title: 'Agent A 프롬프트', summary: '인터프리터를 생성하거나 변이하라고 지시하는 프롬프트다.', why: '언어 설계 공간을 어떤 방향으로 탐색할지 결정한다.' },
  'prompts/agentB_solver.txt': { title: 'Agent B / Solver Bench 프롬프트', summary: '모델 풀 전체가 candidate language를 어떻게 풀어야 하는지 설명하는 프롬프트다.', why: '실제 solver 벤치가 interpreter와 task를 어떻게 읽는지 보여준다.' },
};

const metricGuideEntries = [
  ['Parent', '이 candidate가 어떤 부모 후보에서 파생됐는지 나타낸다.'],
  ['Similarity', 'Python-near 정도. 높을수록 표면 구조가 Python과 비슷하다.'],
  ['Conflict', 'Python prior와 충돌하는 정도. 높을수록 기존 습관을 깨뜨린다.'],
  ['Solvable', '규칙을 따르면 실제로 풀 수 있는지에 대한 추정치다.'],
  ['Novelty', '기존 후보와 얼마나 다른지에 대한 추정치다.'],
  ['Task Bank', '현재 후보를 평가할 문제 세트 목록이다.'],
  ['Agent A 설정', '언어를 생성/변이하는 모델과 파라미터다.'],
  ['Solver Bench 설정', '평가할 모델 풀, 반복 횟수, 병렬도, thinking, temperature를 의미한다.'],
  ['모델별 Pass', '각 모델이 모든 반복 시도 중 몇 번 성공했는지 / 전체 시도 수를 뜻한다.'],
  ['Failure rate', '전체 평가 중 실패 비율이다. 높을수록 어려운 언어다.'],
];

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

function thinkingLabel(value) {
  return value || 'medium';
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

function getArtifact(detail, path) {
  return detail?.artifacts?.files?.[path] || '';
}

function renderMetricGuide() {
  metricGuide.innerHTML = metricGuideEntries.map(([title, copy]) => `
    <div class="metric-guide-card">
      <div class="metric-guide-title">${escapeHtml(title)}</div>
      <div class="metric-guide-copy">${escapeHtml(copy)}</div>
    </div>
  `).join('');
}

function keyStatusText(status) {
  if (!status?.configured) return '설정 안 됨';
  return `설정됨 (${status.masked})`;
}

function settingsPreviewText(config) {
  if (!config) return '설정을 불러오는 중…';
  const agentA = config.agent_a;
  const bench = config.solver_bench;
  return `A · ${agentA.model} · ${thinkingLabel(agentA.thinking)} · temp ${agentA.temperature}  |  Bench · ${bench.enabled_models.length} models · x${bench.repeat_count} · parallel ${bench.parallelism}`;
}

function configHintText(config) {
  if (!config) return '설정 불러오는 중…';
  const bench = config.solver_bench;
  return `A: ${config.agent_a.model} / ${thinkingLabel(config.agent_a.thinking)} / ${config.agent_a.temperature} · Bench: ${bench.enabled_models.length} models × ${bench.repeat_count}회 · parallel ${bench.parallelism}`;
}

function setActionState(button, { disabled = false, active = false } = {}) {
  button.disabled = disabled;
  button.classList.toggle('is-active', active);
}

function renderActionButtons(loopState = {}) {
  const status = loopState.status || 'idle';
  const running = status === 'running';
  const paused = status === 'paused';
  setActionState(openSettingsBtn, { disabled: false, active: false });
  setActionState(startBtn, { disabled: running, active: running });
  setActionState(pauseBtn, { disabled: !running, active: paused });
  setActionState(stepBtn, { disabled: running, active: false });
  setActionState(resetBtn, { disabled: false, active: false });
}

function populateConfigControls(payload) {
  if (!payload) return;
  const config = payload.config;
  const models = payload.openai_models || [];
  const thinkingOptions = payload.thinking_options || [];

  agentAModelSelect.innerHTML = models.map((name) => `<option value="${name}">${name}</option>`).join('');
  agentAModelSelect.value = config.agent_a.model;
  agentAThinkingSelect.innerHTML = thinkingOptions.map((value) => `<option value="${value}">${thinkingLabel(value)}</option>`).join('');
  agentAThinkingSelect.value = config.agent_a.thinking;
  agentATemperatureInput.value = config.agent_a.temperature;

  solverThinkingSelect.innerHTML = thinkingOptions.map((value) => `<option value="${value}">${thinkingLabel(value)}</option>`).join('');
  solverThinkingSelect.value = config.solver_bench.thinking;
  solverTemperatureInput.value = config.solver_bench.temperature;
  solverRepeatCountInput.value = config.solver_bench.repeat_count;
  solverParallelismInput.value = config.solver_bench.parallelism;

  const enabled = new Set(config.solver_bench.enabled_models || []);
  solverModelChecklist.innerHTML = models.map((name) => `
    <label class="model-check-item">
      <input type="checkbox" value="${name}" ${enabled.has(name) ? 'checked' : ''} />
      <span>${name}</span>
    </label>
  `).join('');

  openaiKeyInput.value = '';
  openaiKeyStatus.textContent = keyStatusText(config.providers?.openai?.api_key);
  settingsPreview.textContent = settingsPreviewText(config);
  configHint.textContent = configHintText(config);
}

async function loadConfig() {
  const data = await getJson('/api/config');
  state.config = data;
  populateConfigControls(data);
}

function openSettingsModal() {
  settingsModal.classList.remove('hidden');
  settingsModal.setAttribute('aria-hidden', 'false');
}

function closeSettingsModal() {
  settingsModal.classList.add('hidden');
  settingsModal.setAttribute('aria-hidden', 'true');
}

function selectedSolverModels() {
  return [...solverModelChecklist.querySelectorAll('input[type="checkbox"]:checked')].map((el) => el.value);
}

function buildConfigPayload() {
  const payload = {
    agent_a: {
      model: agentAModelSelect.value,
      thinking: agentAThinkingSelect.value,
      temperature: Number(agentATemperatureInput.value),
    },
    solver_bench: {
      enabled_models: selectedSolverModels(),
      thinking: solverThinkingSelect.value,
      temperature: Number(solverTemperatureInput.value),
      repeat_count: Number(solverRepeatCountInput.value),
      parallelism: Number(solverParallelismInput.value),
    },
  };
  const key = openaiKeyInput.value.trim();
  if (key) {
    payload.providers = { openai: { api_key: key } };
  }
  return payload;
}

async function updateConfig(payload) {
  const data = await getJson('/api/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  state.config = data;
  populateConfigControls(data);
  await refreshOverview();
  await refreshCandidates({ autoSelect: false });
  await refreshSelectedIfNeeded();
}

async function clearOpenAIKey() {
  await updateConfig({ providers: { openai: { clear_api_key: true } } });
}

function normalizedAgentSettingsFromCandidate(meta = {}) {
  return {
    agent_a: meta.agent_a_settings || {
      model: meta.agent_a_model || 'gpt-5.4',
      thinking: meta.agent_a_thinking || 'high',
      temperature: meta.agent_a_temperature ?? 0.7,
    },
    solver_bench: meta.solver_settings || {
      enabled_models: [meta.agent_b_model || 'gpt-5.4'],
      thinking: meta.agent_b_thinking || 'medium',
      temperature: meta.agent_b_temperature ?? 0.2,
      repeat_count: 1,
      parallelism: 1,
      provider: 'openai',
    },
  };
}

async function refreshOverview() {
  const data = await getJson('/api/overview');
  state.overview = data;
  const loopState = data.state || {};
  const hardest = data.hardest || {};
  const config = state.config?.config;

  summaryBar.innerHTML = [
    metricCard('루프 상태', (loopState.status || 'idle').toUpperCase(), loopState.note || '실행 대기 중'),
    metricCard('Iteration', loopState.iteration ?? 0, '완료된 라운드 수'),
    metricCard('후보 수', data.stats.total_candidates, '생성된 candidate'),
    metricCard('Archive', data.stats.archived_candidates, 'hard-but-valid'),
    metricCard('총 평가 수', data.stats.total_evaluations, '모델 × 문제 × 반복'),
    metricCard('Solver Bench', config ? `${config.solver_bench.enabled_models.length} models` : '—', config ? `x${config.solver_bench.repeat_count} · parallel ${config.solver_bench.parallelism}` : '설정 로딩 중'),
    metricCard('현재 hardest', hardest.name || '—', hardest.failure_rate != null ? `failure ${percent(hardest.failure_rate)}` : '아직 없음'),
  ].join('');

  renderActionButtons(loopState);
  renderStrategyTree();
  renderBenchmark();
}

function renderBenchmark() {
  const benchmark = state.overview?.benchmark || { models: [], tasks: [], levels: [] };

  const makeSection = (title, rows, titleField, valueField, fallback) => {
    if (!rows?.length) return `<div class="summary-card"><h3>${escapeHtml(title)}</h3><p>${escapeHtml(fallback)}</p></div>`;
    return `
      <div class="summary-card">
        <h3>${escapeHtml(title)}</h3>
        <div class="summary-list">
          ${rows.slice(0, 5).map((row) => `
            <div class="summary-row">
              <div class="summary-row-head">
                <span>${escapeHtml(row[titleField])}</span>
                <strong>${percent(row[valueField])}</strong>
              </div>
              <div class="pills">
                ${row.success_count != null ? pill(`${row.success_count}/${row.n} success`) : ''}
                ${row.archived_n != null ? pill(`${row.archived_n} archived`) : ''}
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  };

  benchmarkContent.innerHTML = [
    makeSection('모델별 성공률', benchmark.models, 'model_name', 'pass_rate', '아직 모델 결과가 없음'),
    makeSection('문제별 성공률', benchmark.tasks, 'task_name', 'pass_rate', '아직 태스크 결과가 없음'),
    makeSection('레벨별 평균 실패율', benchmark.levels, 'level', 'avg_failure', '아직 레벨 결과가 없음'),
  ].join('');
}

function renderFocusCard() {
  const detail = state.selectedCandidate;
  if (!detail) {
    focusCard.innerHTML = panelEmpty('선택된 candidate가 없음', '왼쪽 후보 목록에서 하나를 고르면 여기에서 핵심 상태를 바로 볼 수 있다.');
    return;
  }
  const meta = detail.metadata || {};
  const settings = normalizedAgentSettingsFromCandidate(meta);
  const totalExpected = settings.solver_bench.enabled_models.length * (meta.task_bank?.length || 0) * settings.solver_bench.repeat_count;
  const completed = detail.evaluations?.length || 0;
  const progressText = totalExpected ? `${completed}/${totalExpected}` : `${completed}`;

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
        ${pill(detail.status || 'generated', detail.archived ? 'tone-green' : 'tone-neutral')}
      </div>
    </div>
    <div class="focus-grid">
      ${kv('Parent', meta.agent1_parent || detail.parent_id || 'None')}
      ${kv('Similarity', detail.similarity_score ?? '—')}
      ${kv('Conflict', detail.conflict_score ?? '—')}
      ${kv('Solvable', detail.solvable_score ?? '—')}
      ${kv('Novelty', detail.novelty_score ?? '—')}
      ${kv('Task Bank', Array.isArray(meta.task_bank) ? meta.task_bank.join(', ') : '—')}
      ${kv('Agent A 모델', settings.agent_a.model)}
      ${kv('Agent A thinking', thinkingLabel(settings.agent_a.thinking))}
      ${kv('Agent A temp', settings.agent_a.temperature)}
      ${kv('Bench models', settings.solver_bench.enabled_models.length)}
      ${kv('반복 횟수', settings.solver_bench.repeat_count)}
      ${kv('병렬 요청', settings.solver_bench.parallelism)}
      ${kv('진행률', progressText)}
    </div>
  `;
}

function filteredCandidates() {
  const q = state.search.trim().toLowerCase();
  return state.candidates.filter((candidate) => {
    if (state.archivedOnly && !candidate.archived) return false;
    const meta = candidate.metadata || {};
    if (state.treeFilter && state.treeFilter !== 'root') {
      if (![meta.strategy_family, meta.strategy_leaf].includes(state.treeFilter)) return false;
    }
    if (!q) return true;
    const hay = [candidate.name, candidate.level, candidate.mutation_summary, meta.strategy_family || '', meta.strategy_leaf || '', candidate.status || ''].join(' ').toLowerCase();
    return hay.includes(q);
  });
}

function candidateRow(candidate) {
  const active = candidate.id === state.selectedId ? 'active' : '';
  const meta = candidate.metadata || {};
  const solverSettings = normalizedAgentSettingsFromCandidate(meta).solver_bench;
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
        ${pill(`${solverSettings.enabled_models.length} models`)}
        ${pill(`x${solverSettings.repeat_count}`)}
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
  candidateList.querySelectorAll('.candidate-item').forEach((el) => el.addEventListener('click', () => selectCandidate(el.dataset.id)));
}

async function refreshCandidates({ autoSelect = true } = {}) {
  const data = await getJson('/api/candidates?limit=500');
  state.candidates = data.items;
  renderCandidateList();
  renderStrategyTree();

  if (state.selectedId) {
    const stillExists = state.candidates.some((item) => item.id === state.selectedId);
    if (!stillExists) clearSelection();
  }

  const items = filteredCandidates();
  if (autoSelect && !state.selectedId && items[0]) await selectCandidate(items[0].id, { updateInspector: true });
}

function clearSelection() {
  state.selectedId = null;
  state.selectedCandidate = null;
  state.selectedTreeNode = 'root';
  state.selectedGraphNode = null;
  state.selectedGraphEdge = null;
  selectedHint.textContent = '후보를 선택해줘';
  renderFocusCard();
  renderSolverBenchMonitor();
  renderStrategyTree();
  graphStage.innerHTML = panelEmpty('실행 그래프가 비어 있음', '후보를 선택하면 Agent A → Solver Bench → Validator 흐름이 나타난다.');
  inspectorContent.className = 'inspector empty';
  inspectorContent.innerHTML = emptyInspectorHtml();
}

function selectedPathSet() {
  const meta = state.selectedCandidate?.metadata || {};
  return new Set(['root', meta.strategy_family, meta.strategy_leaf].filter(Boolean));
}

function renderTreeNode(nodeId, tree) {
  const node = tree.nodes?.[nodeId];
  if (!node) return '';
  const children = (tree.edges || []).filter(([src]) => src === nodeId).map(([, dst]) => dst);
  const selected = selectedPathSet().has(nodeId);
  const activeFilter = state.treeFilter === nodeId;
  return `
    <li>
      <div class="tree-node ${node.kind || ''} ${selected ? 'selected' : ''} ${activeFilter ? 'active' : ''}" data-node-id="${nodeId}">
        <div class="tree-title">${escapeHtml(node.label || nodeId)}</div>
        <div class="tree-meta">${node.count ?? 0} candidates · archived ${node.archived_count ?? 0} · avg failure ${percent(node.avg_failure || 0)}</div>
      </div>
      ${children.length ? `<ul>${children.map((child) => renderTreeNode(child, tree)).join('')}</ul>` : ''}
    </li>
  `;
}

function renderStrategyTree() {
  const tree = state.overview?.strategy_tree;
  if (!tree?.nodes || !Object.keys(tree.nodes).length) {
    strategyTreeStage.innerHTML = panelEmpty('전략 트리가 비어 있음', '아직 candidate가 없어서 root만 존재한다.');
    return;
  }
  strategyTreeStage.innerHTML = `<ul class="tree-list">${renderTreeNode('root', tree)}</ul>`;
  strategyTreeStage.querySelectorAll('[data-node-id]').forEach((el) => {
    el.addEventListener('click', (evt) => {
      evt.stopPropagation();
      const nodeId = el.dataset.nodeId;
      state.selectedTreeNode = nodeId;
      state.treeFilter = nodeId;
      if (nodeId === 'root') {
        state.search = '';
        searchInput.value = '';
      }
      renderCandidateList();
      renderStrategyTree();
      const node = tree.nodes?.[nodeId] || {};
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

  graphStage.querySelectorAll('.graph-node-group').forEach((el) => el.addEventListener('click', () => {
    state.selectedGraphNode = el.dataset.nodeId;
    state.selectedGraphEdge = null;
    renderAgentGraph(graph);
    showNodeInspector(byId[el.dataset.nodeId]);
  }));
  graphStage.querySelectorAll('.graph-edge-group').forEach((el) => el.addEventListener('click', () => {
    state.selectedGraphEdge = el.dataset.edgeId;
    state.selectedGraphNode = null;
    renderAgentGraph(graph);
    const edge = (graph.edges || []).find((item) => item.id === el.dataset.edgeId);
    showEdgeInspector(edge);
  }));
}

function renderSolverBenchMonitor() {
  const detail = state.selectedCandidate;
  if (!detail) {
    solverBenchMonitor.innerHTML = panelEmpty('선택된 candidate가 없음', '후보를 선택하면 모델별·문제별 성공 횟수를 여기에서 모니터링할 수 있다.');
    return;
  }

  const meta = detail.metadata || {};
  const settings = normalizedAgentSettingsFromCandidate(meta).solver_bench;
  const taskBank = meta.task_bank || [];
  const models = settings.enabled_models || [];
  const repeatCount = Number(settings.repeat_count || 1);
  const evaluations = detail.evaluations || [];
  const expectedTotal = models.length * taskBank.length * repeatCount;
  const completed = evaluations.length;
  const passed = evaluations.filter((row) => row.success).length;

  const cellMap = new Map();
  evaluations.forEach((row) => {
    const key = `${row.model_name}::${row.task_name}`;
    if (!cellMap.has(key)) cellMap.set(key, { success: 0, total: 0 });
    const bucket = cellMap.get(key);
    bucket.total += 1;
    if (row.success) bucket.success += 1;
  });

  const table = `
    <table class="solver-monitor-table">
      <thead>
        <tr>
          <th>Model</th>
          ${taskBank.map((task) => `<th>${escapeHtml(task)}</th>`).join('')}
          <th>Total</th>
        </tr>
      </thead>
      <tbody>
        ${models.map((modelName) => {
          let modelSuccess = 0;
          let modelTotal = 0;
          const taskCells = taskBank.map((task) => {
            const bucket = cellMap.get(`${modelName}::${task}`) || { success: 0, total: 0 };
            modelSuccess += bucket.success;
            modelTotal += bucket.total;
            const tone = bucket.total === 0 ? 'pending' : (bucket.success === bucket.total ? 'full' : (bucket.success > 0 ? 'partial' : 'empty'));
            return `<td><div class="solver-cell ${tone}"><strong>${bucket.success}/${repeatCount}</strong><span>${bucket.total}/${repeatCount} 완료</span></div></td>`;
          }).join('');
          return `
            <tr>
              <th>${escapeHtml(modelName)}</th>
              ${taskCells}
              <td><div class="solver-cell total"><strong>${modelSuccess}/${taskBank.length * repeatCount}</strong><span>${percent(modelTotal ? modelSuccess / modelTotal : 0)}</span></div></td>
            </tr>
          `;
        }).join('')}
      </tbody>
    </table>
  `;

  solverBenchMonitor.innerHTML = `
    <div class="solver-monitor-summary">
      ${kv('진행률', `${completed}/${expectedTotal}`)}
      ${kv('성공 수', `${passed}/${completed || expectedTotal || 0}`)}
      ${kv('반복 횟수', repeatCount)}
      ${kv('병렬 요청', settings.parallelism)}
      ${kv('Thinking', thinkingLabel(settings.thinking))}
      ${kv('Temperature', settings.temperature)}
    </div>
    ${table}
  `;
}

function artifactGuideCard(detail) {
  const files = Object.keys(detail?.artifacts?.files || {});
  if (!files.length) return '';
  return inspectorCard('아티팩트 전체 설명', `<div class="artifact-guide">${files.map((path) => {
    const entry = artifactGlossary[path] || { title: '보조 아티팩트', summary: '실행 과정에서 생성된 추가 산출물이다.' };
    return `
      <div class="artifact-row">
        <div class="artifact-path">${escapeHtml(path)}</div>
        <div class="artifact-title">${escapeHtml(entry.title)}</div>
        <div class="artifact-copy">${escapeHtml(entry.summary)}</div>
      </div>
    `;
  }).join('')}</div>`);
}

function showCandidateInspector(detail) {
  const meta = detail.metadata || {};
  const settings = normalizedAgentSettingsFromCandidate(meta);
  inspectorContent.classList.remove('empty');
  inspectorContent.innerHTML = `
    <div class="inspector-section">
      ${inspectorCard('후보 요약', `
        <p><strong>${escapeHtml(detail.name)}</strong> (${escapeHtml(detail.level)})<br>${escapeHtml(detail.mutation_summary)}</p>
        <div class="pills">
          ${pill(`failure ${percent(detail.failure_rate)}`, 'tone-accent')}
          ${pill(meta.strategy_leaf || 'strategy n/a', 'tone-purple')}
          ${pill(detail.status || 'generated', detail.archived ? 'tone-green' : 'tone-neutral')}
        </div>
      `)}
      ${inspectorCard('지표 해석', `
        <div class="inspector-grid">
          ${kv('Similarity', 'Python 표면과의 유사도')}
          ${kv('Conflict', 'Python prior와의 충돌 강도')}
          ${kv('Solvable', '규칙을 따르면 풀 수 있는 정도')}
          ${kv('Novelty', '기존 후보 대비 새로움')}
        </div>
      `)}
      ${inspectorCard('Solver Bench 설정', `
        <div class="inspector-grid">
          ${kv('Enabled models', settings.solver_bench.enabled_models.join(', '))}
          ${kv('Repeat count', settings.solver_bench.repeat_count)}
          ${kv('Parallelism', settings.solver_bench.parallelism)}
          ${kv('Thinking', thinkingLabel(settings.solver_bench.thinking))}
          ${kv('Temperature', settings.solver_bench.temperature)}
        </div>
      `)}
      ${artifactGuideCard(detail)}
      ${glossaryHtml('language_spec.json')}
      ${rawDetails('language_spec.json raw 보기', getArtifact(detail, 'language_spec.json'))}
    </div>
  `;
}

function showTreeInspector(nodeId, node, tree) {
  inspectorContent.classList.remove('empty');
  inspectorContent.innerHTML = `
    <div class="inspector-section">
      ${inspectorCard('전략 노드', `<p><strong>${escapeHtml(node.label || nodeId)}</strong><br>${node.count ?? 0} candidates · archived ${node.archived_count ?? 0}<br>avg failure ${percent(node.avg_failure || 0)}</p>`)}
      ${inspectorCard('트리 안내', `<p>전략 트리는 root에서 시작해 실제 생성된 후보가 생길 때마다 family와 leaf가 추가된다. 노드를 누르면 왼쪽 후보 목록이 해당 branch로 필터링된다.</p>`)}
      ${rawDetails('strategy tree raw 보기', JSON.stringify(tree, null, 2))}
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
  renderSolverBenchMonitor();
  renderCandidateList();
  renderStrategyTree();
  const graph = safeJsonParse(getArtifact(detail, 'agent_graph.json') || '{"nodes":[],"edges":[]}', { nodes: [], edges: [] });
  state.selectedGraphNode = null;
  state.selectedGraphEdge = null;
  renderAgentGraph(graph);
  if (updateInspector) showCandidateInspector(detail);
}

function eventSummary(event) {
  const payload = event.payload || {};
  switch (event.kind) {
    case 'bootstrap': return { title: '초기화 완료', summary: payload.note || payload.message || '빈 상태 부트스트랩 완료' };
    case 'loop_started': return { title: '루프 시작', summary: payload.message || '자동 탐색 시작' };
    case 'loop_paused': return { title: '루프 멈춤', summary: payload.message || '자동 탐색 일시정지' };
    case 'loop_reset': return { title: '기록 초기화', summary: payload.message || '후보/평가/이벤트가 초기화됨' };
    case 'candidate_generated': return { title: `${payload.name || payload.candidate_id || 'candidate'} 생성`, summary: `iteration ${payload.iteration || '-'} · level ${payload.level || '-'}${payload.parent ? ` · parent ${payload.parent}` : ''}` };
    case 'solver_bench_started': return { title: 'Solver Bench 시작', summary: `${payload.models?.length || 0} models · x${payload.repeat_count || 1} · parallel ${payload.parallelism || 1}` };
    case 'solver_progress': return { title: 'Solver 진행 중', summary: `${payload.completed || 0}/${payload.total || 0} · ${payload.model_name || ''} · ${payload.task_name || ''} · attempt ${payload.attempt_index || 0}` };
    case 'benchmark_completed': return { title: '벤치마크 완료', summary: `${payload.candidate_id || ''} · failure ${percent(payload.failure_rate)} · total evals ${payload.total_evals || 0}` };
    case 'archive_updated': return { title: 'Archive 업데이트', summary: payload.message || '새 hardest candidate가 archive에 추가됨' };
    case 'config_updated': {
      const changes = payload.changes || {};
      const parts = Object.entries(changes).map(([k, v]) => `${k}: ${(v || []).join(', ')}`);
      return { title: '설정 변경', summary: parts.join(' · ') || payload.message || '설정 갱신' };
    }
    default: return { title: event.kind, summary: payload.message || '세부 payload를 열어 확인할 수 있음' };
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

openSettingsBtn.addEventListener('click', openSettingsModal);
closeSettingsBtn.addEventListener('click', closeSettingsModal);
settingsBackdrop.addEventListener('click', closeSettingsModal);
openaiClearKeyBtn.addEventListener('click', async () => {
  await clearOpenAIKey();
});
saveSettingsBtn.addEventListener('click', async () => {
  const selected = selectedSolverModels();
  if (!selected.length) {
    alert('Solver Bench에는 최소 1개 이상의 모델을 선택해야 해.');
    return;
  }
  await updateConfig(buildConfigPayload());
  closeSettingsModal();
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && !settingsModal.classList.contains('hidden')) closeSettingsModal();
});

startBtn.addEventListener('click', () => post('/api/loop/start'));
pauseBtn.addEventListener('click', () => post('/api/loop/pause'));
stepBtn.addEventListener('click', () => post('/api/loop/step'));
resetBtn.addEventListener('click', async () => {
  const ok = confirm('후보, 평가, 이벤트 기록을 모두 초기화할까?');
  if (!ok) return;
  await post('/api/loop/reset');
  clearSelection();
  renderCandidateList();
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

    const alwaysRefreshOverview = new Set(['loop_started', 'loop_paused', 'loop_reset', 'candidate_generated', 'solver_bench_started', 'solver_progress', 'benchmark_completed', 'archive_updated', 'config_updated']);
    const refreshListEvents = new Set(['candidate_generated', 'benchmark_completed', 'archive_updated', 'loop_reset']);

    if (alwaysRefreshOverview.has(event.kind)) await refreshOverview();
    if (refreshListEvents.has(event.kind)) await refreshCandidates({ autoSelect: false });
    if (event.kind === 'config_updated') await loadConfig();
    if (event.kind === 'solver_progress' || event.kind === 'benchmark_completed') {
      if (event.payload?.candidate_id && event.payload.candidate_id === state.selectedId) {
        await refreshSelectedIfNeeded();
      }
    }
    if (event.kind === 'loop_reset') clearSelection();
  };
}

async function init() {
  inspectorContent.innerHTML = emptyInspectorHtml();
  renderMetricGuide();
  renderActionButtons({ status: 'idle' });
  renderFocusCard();
  renderSolverBenchMonitor();
  strategyTreeStage.innerHTML = panelEmpty('전략 트리가 비어 있음', '아직 candidate가 없어서 root만 존재한다.');
  graphStage.innerHTML = panelEmpty('실행 그래프가 비어 있음', '후보를 선택하면 Agent A → Solver Bench → Validator 흐름이 나타난다.');
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
