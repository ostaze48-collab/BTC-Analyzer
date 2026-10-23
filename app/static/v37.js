(() => {
  const style = document.createElement('style');
  style.textContent = `
    .esw-summary{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-top:10px}
    .esw-box{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:10px}
    .esw-box small{display:block;color:var(--muted);font-size:11px}.esw-box b{display:block;margin-top:4px;font-size:14px}
    .esw-gates{display:grid;gap:7px;margin-top:10px}.esw-gate{display:grid;grid-template-columns:.25fr 1fr 1.7fr;gap:8px;padding:9px;border:1px solid var(--line);border-radius:9px;background:var(--panel2);font-size:12px}.esw-gate.pass{border-color:rgba(34,197,94,.35)}.esw-gate.fail{border-color:rgba(239,68,68,.30)}
    .esw-note{margin-top:10px;padding:10px;border:1px solid rgba(245,158,11,.25);background:rgba(245,158,11,.06);border-radius:10px;font-size:12px}
    @media(max-width:1000px){.esw-summary{grid-template-columns:repeat(3,1fr)}}
    @media(max-width:900px){.esw-summary{grid-template-columns:1fr 1fr}.esw-gate{grid-template-columns:.25fr 1fr}.esw-gate .req{grid-column:1/-1;color:var(--muted)}}
  `;
  document.head.appendChild(style);

  const anchor = document.getElementById('researchEvidenceHistorySection') || document.getElementById('strictPaperReviewSection') || document.getElementById('learningSection');
  if (anchor) {
    const section = document.createElement('section');
    section.id = 'evidenceStabilityWindowSection';
    section.className = 'card section-learning';
    section.innerHTML = `
      <div class="section-title-row">
        <div>
          <div class="card-title">Evidence Stability Window · V1.27</div>
          <small class="muted">24 ساعة فعلية + Snapshots كافية + صفقات Paper جديدة · يمنع الثبات الوهمي الناتج عن تكرار نفس الحالة</small>
        </div>
        <button id="refreshEvidenceStability" class="primary" type="button">تحديث</button>
      </div>
      <div id="eswSummary" class="esw-summary"><div class="muted">بانتظار نافذة الثبات...</div></div>
      <div id="eswGates" class="esw-gates"></div>
      <div id="eswNote" class="esw-note">Passing = ثبات بحثي/Paper فقط، وليس تصريح تداول حقيقي.</div>`;
    anchor.parentNode.insertBefore(section, anchor.nextSibling);
  }

  const fmt = (x, d = 1) => x == null ? '—' : Number(x).toLocaleString(undefined, {maximumFractionDigits:d});
  const safe = x => x == null ? '—' : String(x);

  function render(r) {
    const summary = document.getElementById('eswSummary');
    const gates = document.getElementById('eswGates');
    const note = document.getElementById('eswNote');
    if (!summary || !gates) return;
    const w = r.window || {};
    summary.innerHTML = `
      <div class="esw-box"><small>Status</small><b>${safe(r.status)}</b></div>
      <div class="esw-box"><small>Observed span</small><b>${fmt(w.total_history_span_hours)}h / ${fmt(w.hours_required,0)}h</b></div>
      <div class="esw-box"><small>Recent snapshots</small><b>${fmt(w.recent_snapshots,0)}</b></div>
      <div class="esw-box"><small>New Paper trades</small><b>${fmt(w.new_paper_trades,0)} · total ${fmt(w.total_paper_trades,0)}</b></div>
      <div class="esw-box"><small>Strict pass rate</small><b>${fmt(w.strict_pass_rate_pct)}%</b></div>
      <div class="esw-box"><small>Recent regressions</small><b>${fmt(w.regressions,0)}</b></div>`;

    gates.innerHTML = (r.gates || []).map(g => `
      <div class="esw-gate ${g.passed ? 'pass' : 'fail'}">
        <span>${g.passed ? '✅' : '⛔'}</span><b>${safe(g.id)}</b><span class="req">${safe(g.requirement)}</span>
      </div>`).join('') || '<div class="muted">لا توجد بيانات كافية بعد.</div>';

    if (note) note.innerHTML = `🔒 <b>Next stage: ${safe(r.next_stage)}</b><br>${safe(r.policy)}<br><span class="muted">Paper only = ${r.paper_only ? 'YES' : 'NO'} · Real eligibility = ${r.real_execution_eligibility ? 'YES' : 'NO'} · Live execution = ${r.live_execution_enabled ? 'ON' : 'OFF'} · Auto target = ${r.target_auto_apply ? 'ON' : 'OFF'}</span>`;
  }

  async function refresh() {
    const button = document.getElementById('refreshEvidenceStability');
    if (button) button.disabled = true;
    try {
      const response = await fetch('/api/evidence-stability?limit=1000');
      render(await response.json());
    } catch (error) {
      console.warn('Evidence stability failed', error);
    } finally {
      if (button) button.disabled = false;
    }
  }

  document.getElementById('refreshEvidenceStability')?.addEventListener('click', refresh);
  refresh();
  setInterval(refresh, 60000);
  fetch('/api/version').then(r => r.json()).then(v => {
    document.title = `${v.name} ${v.label}`;
    const el = document.querySelector('h1 span'); if (el) el.textContent = v.label;
  }).catch(() => {});
})();
