const NOTICE_LABELS = {
  '공개': '공개', '부분공개': '부분공개', '비공개': '비공개',
  '정보부존재': '정보부존재', '진정질의': '진정·질의', '종결': '종결',
};
const NOTICE_TONE = {
  '공개': 'normal', '부분공개': 'warning', '비공개': 'fault',
  '정보부존재': 'precursor', '진정질의': 'info', '종결': 'unknown',
};

function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.content : '';
}

function emptyState(icon, text, hint) {
  return `<div class="empty-state">
    <div class="empty-state-icon" aria-hidden="true">${icon}</div>
    <div class="empty-state-text">${text}</div>
    ${hint ? `<div class="empty-state-hint">${hint}</div>` : ''}
  </div>`;
}

function showToast(message, isError) {
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();
  const el = document.createElement('div');
  el.className = 'toast' + (isError ? ' error' : '');
  el.textContent = message;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

function noticePill(noticeType) {
  if (!noticeType) return '<span class="status-pill unknown">판단중</span>';
  const tone = NOTICE_TONE[noticeType] || 'unknown';
  const label = NOTICE_LABELS[noticeType] || noticeType;
  return `<span class="status-pill ${tone}">${label}</span>`;
}

function renderSummaryCards(summary) {
  const root = document.getElementById('summary-cards');
  if (!root) return;
  const counts = summary.notice_counts || {};
  const cards = [
    { key: '공개', tone: 'normal', icon: '✔' },
    { key: '부분공개', tone: 'warning', icon: '◐' },
    { key: '비공개', tone: 'fault', icon: '✖' },
    { key: '정보부존재', tone: 'precursor', icon: '❓' },
    { key: '진정질의', tone: 'info', icon: '📩' },
    { key: '종결', tone: 'unknown', icon: '⏹' },
  ];
  root.innerHTML = cards.map(c => `
    <div class="summary-card ${c.tone}">
      <div class="sc-label"><span aria-hidden="true">${c.icon}</span> ${NOTICE_LABELS[c.key]}</div>
      <div class="sc-value">${counts[c.key] || 0}</div>
    </div>`).join('');
}

function renderPendingList(rows) {
  const root = document.getElementById('pending-list');
  if (!root) return;
  const pending = rows.filter(r => r.status === '판단중');
  if (!pending.length) {
    root.innerHTML = emptyState('✅', '판단 대기 중인 청구가 없습니다.', '새 청구가 접수되면 여기에 표시됩니다.');
    return;
  }
  root.innerHTML = pending.map(r => `
    <a href="/requests/${r.id}" class="queue-link">
      <div class="log-row">
        <div class="log-time">${r.received_at || '-'}</div>
        <div class="log-server">#${r.id}</div>
        <div class="log-message">
          <div class="log-summary">${r.requester_name} · ${r.request_target || '식별 중'}
            ${r.deadline ? `<span class="status-pill ${r.deadline.tone} deadline-inline" title="${escapeHtml(r.deadline.label)}">${escapeHtml(r.deadline.short_label)}</span>` : ''}
          </div>
          <div class="log-sub">현재 단계: ${r.current_step || '-'}</div>
        </div>
      </div>
    </a>`).join('');
}

function renderRecentList(rows) {
  const root = document.getElementById('recent-list');
  if (!root) return;
  if (!rows.length) {
    root.innerHTML = emptyState('📄', '접수된 청구가 없습니다.', '청구 접수 메뉴에서 새 청구를 등록해보세요.');
    return;
  }
  root.innerHTML = rows.slice(0, 10).map(r => `
    <div class="ai-guide-card">
      <div class="ai-guide-head">
        <strong>#${r.id} ${r.requester_name}</strong>
        ${noticePill(r.final_notice_type)}
      </div>
      <div class="ai-guide-summary">${r.request_target || '요청대상 식별 중'}</div>
      <div class="log-sub">${r.received_at || '-'}</div>
    </div>`).join('');
}

async function loadDashboard() {
  if (!document.getElementById('summary-cards')) return;
  const [summary, requests] = await Promise.all([
    fetch('/api/summary').then(r => r.json()),
    fetch('/api/requests?limit=100').then(r => r.json()),
  ]);
  renderSummaryCards(summary);
  renderPendingList(requests);
  renderRecentList(requests);
  const unassignedBadge = document.getElementById('unassigned-badge');
  if (unassignedBadge) unassignedBadge.textContent = `배정 대기: ${summary.unassigned_count || 0}건`;

  const deadlineBadge = document.getElementById('deadline-badge');
  if (deadlineBadge) {
    const overdue = requests.filter(r => r.deadline && r.deadline.tone === 'fault').length;
    const urgent = requests.filter(r => r.deadline && r.deadline.tone === 'warning').length;
    deadlineBadge.textContent = `처리기한: 초과 ${overdue}건 · 임박 ${urgent}건`;
    deadlineBadge.className = 'badge' + (overdue ? ' warn' : '');
  }

  const lastScan = document.getElementById('last-scan-badge');
  if (lastScan) lastScan.textContent = `마지막 갱신: -`;
}

async function runScan() {
  const btn = document.getElementById('btn-scan');
  if (btn) { btn.classList.add('btn-loading'); btn.disabled = true; }
  try {
    const res = await fetch('/api/watch/scan', { method: 'POST', headers: { 'X-CSRF-Token': getCsrfToken() } });
    const data = await res.json();
    showToast(`감시 폴더 스캔 완료 — 신규 접수: ${data.new_requests}`);
    const badge = document.getElementById('last-scan-badge');
    if (badge) badge.textContent = `마지막 갱신: ${data.scanned_at}`;
    loadDashboard();
  } catch (e) {
    showToast('스캔 중 오류가 발생했습니다.', true);
  } finally {
    if (btn) { btn.classList.remove('btn-loading'); btn.disabled = false; }
  }
}

async function testAI(event) {
  event.preventDefault();
  const form = document.getElementById('ai-test-form');
  const output = document.getElementById('ai-test-result');
  const btn = form.querySelector('button[type="submit"]');
  const formData = new FormData(form);
  output.textContent = '테스트 요청 중...';
  if (btn) { btn.classList.add('btn-loading'); btn.disabled = true; }
  try {
    const res = await fetch('/settings/test-ai', { method: 'POST', body: formData });
    const data = await res.json();
    output.textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    output.textContent = '요청 실패: ' + e.message;
  } finally {
    if (btn) { btn.classList.remove('btn-loading'); btn.disabled = false; }
  }
  return false;
}

async function extendDeadline(requestId) {
  const reason = prompt('연장 사유를 입력해주세요 (선택 사항, 정보공개법 제11조 제2항 "부득이한 사유"):', '') || '';
  if (!confirm('처리기한을 10일 연장하시겠습니까? 한 청구당 한 번만 가능합니다.')) return;
  try {
    const res = await fetch(`/api/requests/${requestId}/extend-deadline`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
      body: JSON.stringify({ reason }),
    });
    const data = await res.json();
    if (!data.success) {
      showToast(data.message || '연장에 실패했습니다.', true);
      return;
    }
    showToast('처리기한을 10일 연장했습니다.');
    location.reload();
  } catch (e) {
    showToast('연장 처리 중 오류가 발생했습니다.', true);
  }
}

async function decideStep(requestId, stepKey, answer) {
  const wizard = document.getElementById('decision-wizard');
  const buttons = wizard ? wizard.querySelectorAll('button') : [];
  buttons.forEach(b => { b.classList.add('btn-loading'); b.disabled = true; });
  try {
    const res = await fetch(`/api/requests/${requestId}/decide`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
      body: JSON.stringify({ step: stepKey, answer }),
    });
    const data = await res.json();
    if (!data.success) {
      showToast(data.message || '판단 처리에 실패했습니다.', true);
      buttons.forEach(b => { b.classList.remove('btn-loading'); b.disabled = false; });
      return;
    }
    showToast(data.final_notice_type ? `최종 통지: ${NOTICE_LABELS[data.final_notice_type] || data.final_notice_type}` : '다음 단계로 진행합니다.');
    location.reload();
  } catch (e) {
    showToast('판단 처리 중 오류가 발생했습니다.', true);
    buttons.forEach(b => { b.classList.remove('btn-loading'); b.disabled = false; });
  }
}

async function assignRequestTo(requestId, assignedTo) {
  if (!assignedTo) { showToast('배정할 업무담당자를 선택하세요.', true); return; }
  try {
    const res = await fetch(`/api/requests/${requestId}/assign`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
      body: JSON.stringify({ assigned_to: assignedTo }),
    });
    const data = await res.json();
    if (!data.success) {
      showToast(data.message || '배정에 실패했습니다.', true);
      return;
    }
    showToast(`#${requestId} 청구를 ${assignedTo}님에게 배정했습니다.`);
    const row = document.getElementById(`dispatch-row-${requestId}`);
    if (row) { row.remove(); } else { location.reload(); }
  } catch (e) {
    showToast('배정 처리 중 오류가 발생했습니다.', true);
  }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text == null ? '' : String(text);
  return div.innerHTML;
}

function renderStaffResults(requestId, query) {
  const box = document.getElementById(`staff-results-${requestId}`);
  if (!box) return;
  const dir = window.STAFF_DIRECTORY || [];
  const q = (query || '').trim().toLowerCase();
  const filtered = !q ? dir : dir.filter(s =>
    [s.username, s.region, s.branch, s.department].filter(Boolean).join(' ').toLowerCase().includes(q)
  );
  if (!filtered.length) {
    box.innerHTML = `<div class="log-sub staff-search-empty">검색 결과가 없습니다.</div>`;
    return;
  }
  box.innerHTML = filtered.map(s => `
    <button type="button" class="staff-search-item" data-staff-username="${escapeHtml(s.username).replace(/"/g, '&quot;')}"
            onclick="assignRequestTo(${requestId}, this.dataset.staffUsername)">
      <strong>${escapeHtml(s.username)}</strong>
      <span class="log-sub">${escapeHtml(s.region || '-')} · ${escapeHtml(s.branch || '-')} · ${escapeHtml(s.department || '-')}</span>
    </button>`).join('');
}

function filterStaffSearch(requestId) {
  const input = document.querySelector(`.staff-search-input[data-request-id="${requestId}"]`);
  if (input && input.dataset.mode === 'reject') {
    renderRejectSearchResults(requestId, input.value);
  } else {
    renderStaffResults(requestId, input ? input.value : '');
  }
}

// ── 담당자 재배정 요청(거절) — 1~3명 다중 선택 ──────────────────────
window._rejectSelections = window._rejectSelections || {};

function renderRejectSearchResults(requestId, query) {
  const box = document.getElementById(`staff-results-${requestId}`);
  if (!box) return;
  const dir = window.STAFF_DIRECTORY || [];
  const q = (query || '').trim().toLowerCase();
  const filtered = !q ? dir : dir.filter(s =>
    [s.username, s.region, s.branch, s.department].filter(Boolean).join(' ').toLowerCase().includes(q)
  );
  if (!filtered.length) {
    box.innerHTML = `<div class="log-sub staff-search-empty">검색 결과가 없습니다.</div>`;
    return;
  }
  const selected = window._rejectSelections[requestId] || new Set();
  box.innerHTML = filtered.map(s => `
    <button type="button" class="staff-search-item" aria-pressed="${selected.has(s.username)}"
            data-staff-username="${escapeHtml(s.username).replace(/"/g, '&quot;')}"
            onclick="toggleRejectCandidate(${requestId}, this.dataset.staffUsername)">
      <span class="staff-choice-indicator" aria-hidden="true">${selected.has(s.username) ? '✓' : ''}</span>
      <span class="staff-choice-content">
        <strong>${escapeHtml(s.username)}</strong>
        <span class="log-sub">${escapeHtml(s.region || '-')} · ${escapeHtml(s.branch || '-')} · ${escapeHtml(s.department || '-')}</span>
      </span>
    </button>`).join('');
}

function toggleRejectCandidate(requestId, username) {
  const results = document.getElementById(`staff-results-${requestId}`);
  const restoreFocus = results && results.contains(document.activeElement);
  const selections = window._rejectSelections[requestId] || new Set();
  if (selections.has(username)) {
    selections.delete(username);
  } else if (selections.size >= 3) {
    showToast('최대 3명까지 선택할 수 있습니다.', true);
    return;
  } else {
    selections.add(username);
  }
  window._rejectSelections[requestId] = selections;

  const label = document.getElementById(`reject-selected-${requestId}`);
  if (label) label.textContent = selections.size ? Array.from(selections).join(', ') : '없음';
  const submitBtn = document.getElementById(`reject-submit-${requestId}`);
  if (submitBtn) submitBtn.disabled = selections.size < 1;

  const input = document.querySelector(`.staff-search-input[data-request-id="${requestId}"][data-mode="reject"]`);
  renderRejectSearchResults(requestId, input ? input.value : '');
  if (restoreFocus) {
    const selectedButton = Array.from(results.querySelectorAll('button[data-staff-username]'))
      .find(button => button.dataset.staffUsername === username);
    if (selectedButton) selectedButton.focus();
  }
}

async function submitReject(requestId) {
  const selections = window._rejectSelections[requestId] || new Set();
  if (selections.size < 1 || selections.size > 3) {
    showToast('재배정할 담당자를 1명 이상 3명 이하로 선택해주세요.', true);
    return;
  }
  if (!confirm('선택한 담당자에게 재배정을 요청하시겠습니까? 이 청구는 본인 업무 목록에서 사라집니다.')) return;
  const btn = document.getElementById(`reject-submit-${requestId}`);
  if (btn) { btn.classList.add('btn-loading'); btn.disabled = true; }
  try {
    const res = await fetch(`/api/requests/${requestId}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
      body: JSON.stringify({ candidates: Array.from(selections) }),
    });
    const data = await res.json();
    if (!data.success) {
      showToast(data.message || '재배정 요청에 실패했습니다.', true);
      if (btn) { btn.classList.remove('btn-loading'); btn.disabled = false; }
      return;
    }
    showToast('재배정을 요청했습니다.');
    location.href = '/requests';
  } catch (e) {
    showToast('재배정 요청 중 오류가 발생했습니다.', true);
    if (btn) { btn.classList.remove('btn-loading'); btn.disabled = false; }
  }
}

function initAllStaffSearches() {
  document.querySelectorAll('.staff-search-input').forEach(input => {
    if (input.dataset.mode === 'reject') {
      renderRejectSearchResults(input.dataset.requestId, '');
    } else {
      renderStaffResults(input.dataset.requestId, '');
    }
  });
}

async function recommendStaff(requestId, btn) {
  if (btn) { btn.classList.add('btn-loading'); btn.disabled = true; }
  try {
    const res = await fetch(`/api/requests/${requestId}/recommend`, { method: 'POST', headers: { 'X-CSRF-Token': getCsrfToken() } });
    const data = await res.json();
    if (!data.success) {
      showToast(data.message || 'AI 판단에 실패했습니다.', true);
      return;
    }
    if (data.has_result) {
      renderRecommendations(requestId, data.recommendations || [], data.reason || '');
    } else {
      renderNoResult(requestId, data.message);
    }
  } catch (e) {
    showToast('AI 판단 중 오류가 발생했습니다.', true);
  } finally {
    if (btn) { btn.classList.remove('btn-loading'); btn.disabled = false; }
  }
}

function renderRecommendations(requestId, names, reason) {
  const box = document.getElementById(`ai-result-${requestId}`);
  if (!box) return;
  if (!names.length) {
    box.innerHTML = `<div class="log-sub">예시 결과 파일에서 유효한 업무담당자를 찾지 못했습니다.</div>`;
  } else {
    const primary = `<button type="button" class="rank-primary" onclick="assignRequestTo(${requestId}, '${names[0]}')">
      <span><span class="rank-badge">1순위</span>${names[0]}</span><span>→</span>
    </button>`;
    const rest = names.slice(1, 3);
    const secondaryRow = rest.length ? `<div class="rank-secondary-row">${rest.map((name, i) =>
      `<button type="button" class="rank-secondary" onclick="assignRequestTo(${requestId}, '${name}')">
        <span class="rank-badge">${i + 2}순위</span>${name}
      </button>`
    ).join('')}</div>` : '';
    const reasonHtml = reason ? `<div class="assign-reason">추천 사유: ${reason}</div>` : '';
    box.innerHTML = `<div class="assign-panel-hint">추천 담당자를 선택하면 바로 배정됩니다.</div>${primary}${secondaryRow}${reasonHtml}`;
  }
  box.style.display = 'block';
}

function renderNoResult(requestId, message) {
  const box = document.getElementById(`ai-result-${requestId}`);
  if (!box) return;
  box.innerHTML = `
    <div class="log-sub recommendation-message">${message || 'AI 판단 예시가 아직 준비되지 않았습니다.'}</div>
    <button type="button" class="btn-toggle" onclick="generateRecommendation(${requestId})">⚙ AI로 생성하기</button>
  `;
  box.style.display = 'block';
}

async function generateRecommendation(requestId) {
  const box = document.getElementById(`ai-result-${requestId}`);
  if (box) box.innerHTML = `<div class="log-sub">추천 생성 중...</div>`;
  try {
    const res = await fetch(`/api/requests/${requestId}/generate-recommendation`, { method: 'POST', headers: { 'X-CSRF-Token': getCsrfToken() } });
    const data = await res.json();
    if (!data.success) {
      showToast(data.message || '요청 처리에 실패했습니다.', true);
      if (box) renderNoResult(requestId, data.message);
      return;
    }
    renderEngineComparison(requestId, data.engines || {});
  } catch (e) {
    showToast('요청 처리 중 오류가 발생했습니다.', true);
  }
}

const RECOMMEND_ENGINE_LABELS = { gbm: '📊 GradientBoost 추천', llm: '🧠 LLM 추천' };
const RECOMMEND_ENGINE_ORDER = ['gbm', 'llm'];

function renderEngineComparison(requestId, engines) {
  const box = document.getElementById(`ai-result-${requestId}`);
  if (!box) return;
  const sections = RECOMMEND_ENGINE_ORDER
    .filter(key => engines[key])
    .map(key => {
      const engine = engines[key];
      const label = RECOMMEND_ENGINE_LABELS[key] || key;
      if (!engine.available) {
        return `<div class="engine-result">
          <div class="dispatch-label">${label}</div>
          <div class="log-sub">${escapeHtml(engine.message || '사용할 수 없습니다.')}</div>
        </div>`;
      }
      const buttons = engine.recommendations.map((name, i) => `
        <button type="button" class="rank-secondary" onclick="assignRequestTo(${requestId}, '${name}')">
          <span class="rank-badge">${i + 1}순위</span>${escapeHtml(name)}
        </button>`).join('');
      return `<div class="engine-result">
        <div class="dispatch-label">${label}</div>
        <div class="rank-secondary-row">${buttons}</div>
        ${engine.reason ? `<div class="assign-reason">${escapeHtml(engine.reason)}</div>` : ''}
      </div>`;
    });
  box.innerHTML = sections.join('') || `<div class="log-sub">추천 결과가 없습니다.</div>`;
  box.style.display = 'block';
  const recommendBtn = document.getElementById(`recommend-btn-${requestId}`);
  if (recommendBtn) recommendBtn.style.display = 'none';
}

function updateClock() {
  const root = document.getElementById('now-clock');
  if (!root) return;
  root.textContent = new Date().toLocaleString('ko-KR');
}

let _dashboardPollTimer = null;

function connectSSE() {
  if (!document.getElementById('summary-cards')) return;
  if (_dashboardPollTimer) clearInterval(_dashboardPollTimer);

  _dashboardPollTimer = setInterval(() => {
    if (!document.getElementById('summary-cards')) {
      clearInterval(_dashboardPollTimer);
      _dashboardPollTimer = null;
      return;
    }
    loadDashboard();
    const badge = document.getElementById('last-scan-badge');
    if (badge) badge.textContent = `마지막 갱신: ${new Date().toLocaleString('ko-KR')}`;
  }, 30000);
}

// ── 업무담당자 "내 업무" 새 배정 감지 (폴링) ────────────────────────
// 이 앱은 처음부터 웹소켓/SSE 없이 폴링만 쓰고 있어(위 connectSSE도 실은 setInterval),
// 같은 방식으로 업무담당자가 새로 배정받으면 토스트로 알려준다.
let _myQueuePollTimer = null;
let _myQueueKnownIds = null;

async function pollMyQueue() {
  try {
    const res = await fetch('/api/requests?limit=200');
    if (!res.ok) return;
    const rows = await res.json();
    const ids = new Set(rows.map(r => r.id));
    if (_myQueueKnownIds === null) {
      _myQueueKnownIds = ids;  // 최초 로드는 기준선만 세우고 알리지 않음
      return;
    }
    const newIds = [...ids].filter(id => !_myQueueKnownIds.has(id));
    _myQueueKnownIds = ids;
    if (newIds.length) {
      showToast(`새로 배정된 청구가 ${newIds.length}건 있습니다. 목록을 새로고침합니다.`);
      setTimeout(() => location.reload(), 1200);
    }
  } catch (e) {
    // 폴링 실패는 조용히 무시 — 다음 주기에 다시 시도
  }
}

function initMyQueuePolling() {
  if (!window.MY_QUEUE_POLL) return;
  pollMyQueue();
  if (_myQueuePollTimer) clearInterval(_myQueuePollTimer);
  _myQueuePollTimer = setInterval(pollMyQueue, 20000);
}

window.addEventListener('DOMContentLoaded', () => {
  updateClock();
  setInterval(updateClock, 1000);
  loadDashboard();
  connectSSE();
  initAllStaffSearches();
  initMyQueuePolling();
});
