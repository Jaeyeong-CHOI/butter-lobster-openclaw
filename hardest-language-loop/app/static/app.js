const state = {
  selectedId: null,
  lastEventId: 0,
  candidates: [],
};

const metricGrid = document.getElementById('metricGrid');
const eventList = document.getElementById('eventList');
const candidateList = document.getElementById('candidateList');
const candidateDetail = document.getElementById('candidateDetail');
const eventStatus = document.getElementById('eventStatus');

async function getJson(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function metricCard(label, value, sub = '') {
  return `<div class="metric-card"><div class="label">${label}</div><div class="value">${value}</div><div class="sub">${sub}</div></div>`;
}

async function refreshOverview() {
  const data = await getJson('/api/overview');
  const s = data.state || {};
  const hardest = data.hardest || {};
  metricGrid.innerHTML = [
    metricCard('Loop Status', (s.status || 'idle').toUpperCase(), s.note || ''),
    metricCard('Iteration', s.iteration ?? 0, 'completed rounds'),
    metricCard('Candidates', data.stats.total_candidates, 'generated total'),
    metricCard('Archived', data.stats.archived_candidates, 'hard-but-valid languages'),
    metricCard('Current Hardest', hardest.name || '—', hardest.failure_rate != null ? `failure ${(hardest.failure_rate * 100).toFixed(0)}%` : 'not available'),
  ].join('');
}

function candidateRow(c) {
  const active = c.id === state.selectedId ? 'active' : '';
  const archived = c.archived ? 'ARCHIVED' : c.status.toUpperCase();
  return `
    <div class="candidate-item ${active}" data-id="${c.id}">
      <div><strong>${c.name}</strong> <span class="candidate-meta">(${c.level})</span></div>
      <div class="candidate-meta">${c.mutation_summary}</div>
      <div class="pills">
        <span class="pill">failure ${(c.failure_rate * 100).toFixed(0)}%</span>
        <span class="pill">similarity ${(c.similarity_score * 100).toFixed(0)}%</span>
        <span class="pill">conflict ${(c.conflict_score * 100).toFixed(0)}%</span>
        <span class="pill">solvable ${(c.solvable_score * 100).toFixed(0)}%</span>
        <span class="pill">${archived}</span>
      </div>
    </div>
  `;
}

async function refreshCandidates() {
  const data = await getJson('/api/candidates?limit=40');
  state.candidates = data.items;
  candidateList.innerHTML = state.candidates.map(candidateRow).join('');
  candidateList.querySelectorAll('.candidate-item').forEach((el) => {
    el.addEventListener('click', () => selectCandidate(el.dataset.id));
  });
  if (!state.selectedId && state.candidates[0]) {
    await selectCandidate(state.candidates[0].id);
  }
}

function renderEvalTable(evals) {
  if (!evals.length) return '<div class="candidate-meta">No evaluations yet.</div>';
  return `
    <table class="eval-table">
      <thead>
        <tr><th>Model</th><th>Task</th><th>Result</th><th>Score</th><th>Notes</th></tr>
      </thead>
      <tbody>
        ${evals.map((e) => `
          <tr>
            <td>${e.model_name}</td>
            <td>${e.task_name}</td>
            <td class="${e.success ? 'success' : 'fail'}">${e.success ? 'PASS' : 'FAIL'}</td>
            <td>${(e.score * 100).toFixed(0)}%</td>
            <td>${e.notes || ''}</td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

async function selectCandidate(id) {
  state.selectedId = id;
  await refreshCandidates();
  const c = await getJson(`/api/candidates/${id}`);
  const meta = c.metadata || {};
  candidateDetail.classList.remove('empty');
  candidateDetail.innerHTML = `
    <div class="detail-grid">
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
    ${renderEvalTable(c.evaluations || [])}
  `;
}

function addEventItem(event) {
  const el = document.createElement('div');
  el.className = 'event-item';
  el.innerHTML = `
    <div class="kind">${event.kind}</div>
    <div class="candidate-meta">${new Date(event.created_at).toLocaleString()}</div>
    <div>${JSON.stringify(event.payload)}</div>
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
}

document.getElementById('startBtn').addEventListener('click', () => post('/api/loop/start'));
document.getElementById('pauseBtn').addEventListener('click', () => post('/api/loop/pause'));
document.getElementById('stepBtn').addEventListener('click', () => post('/api/loop/step'));
document.getElementById('resetBtn').addEventListener('click', async () => {
  await post('/api/loop/reset');
  candidateDetail.className = 'candidate-detail empty';
  candidateDetail.textContent = 'Select a candidate to inspect its evaluation matrix.';
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
    await refreshCandidates();
    if (state.selectedId) {
      await selectCandidate(state.selectedId);
    }
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
