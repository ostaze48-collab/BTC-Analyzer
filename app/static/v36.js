(() => {
  const style = document.createElement('style');
  style.textContent = `
    .epo-head{display:flex;justify-content:space-between;gap:10px;align-items:center}
    .epo-actions{display:flex;gap:7px;flex-wrap:wrap}.epo-summary{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-top:10px}
    .epo-box{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:10px}.epo-box small{display:block;color:var(--muted);font-size:11px}.epo-box b{display:block;margin-top:4px;font-size:14px}
    .epo-timeline{display:flex;gap:8px;overflow-x:auto;padding:8px 0;margin-top:7px;scroll-snap-type:x proximity}.epo-point{min-width:145px;scroll-snap-align:start;background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:9px;font-size:12px}.epo-point.pass{border-color:rgba(34,197,94,.35)}.epo-point.fail{border-color:rgba(239,68,68,.30)}
    .epo-gates{display:grid;gap:7px;margin-top:10px}.epo-gate{display:grid;grid-template-columns:.25fr 1fr 1.8fr;gap:8px;padding:9px;border:1px solid var(--line);border-radius:9px;background:var(--panel2);font-size:12px}.epo-gate.pass{border-color:rgba(34,197,94,.35)}.epo-gate.fail{border-color:rgba(239,68,68,.30)}
    .epo-note{margin-top:10px;padding:10px;border:1px solid rgba(245,158,11,.25);background:rgba(245,158,11,.06);border-radius:10px;font-size:12px}.epo-checkpoint{margin-top:8px;font-size:11px;color:var(--muted)}
    @media(max-width:900px){.epo-head{align-items:flex-start;flex-direction:column}.epo-summary{grid-template-columns:1fr 1fr}.epo-gate{grid-template-columns:.25fr 1fr}.epo-gate .req{grid-column:1/-1;color:var(--muted)}}
  `;
  document.head.appendChild(style);

  const anchor = document.getElementById('strictPaperReviewSection') || document.getElementById('learningSection');
  if (anchor) {
    const section = document.createElement('section');
    section.id = 'extendedPaperObservationSection';
    section.className = 'card section-learning';
    section.innerHTML = `
      <div class="epo-head">
        <div><div class="card-title">Extended Paper Observation</div><small class="muted">Persisted checkpoints كل ≥20 صفقة مؤهلة جديدة · الثبات عبر الزمن وليس نجاح لقطة واحدة</small></div>
        <div class="epo-actions"><button id="recordPaperCheckpoint" class="primary" type="button">حفظ Checkpoint</button><button id="refreshPaperObservation" type="button">تحديث</button></div>
      </div>
      <div id="epoSummary" class="epo-summary"><div class="muted">بانتظار سجل المراقبة...</div></div>
      <div id="epoCheckpoint" class="epo-checkpoint"></div>
      <div id="epoTimeline" class="epo-timeline"></div>
      <div id="epoGates" class="epo-gates"></div>
      <div id="epoNote" class="epo-note">Persistence evidence فقط؛ ليست OOS مستقلة ولا تسمح بتداول حقيقي.</div>`;
    anchor.parentNode.insertBefore(section, anchor.nextSibling);
  }

  const safe = x => x == null ? '—' : String(x);
  const fmt = (x, d = 1) => x == null ? '—' : Number(x).toLocaleString(undefined, {maximumFractionDigits: d});

  function render(r, checkpoint = null) {
    const summary = document.getElementById('epoSummary');
    const timeline = document.getElementById('epoTimeline');
    const gates = document.getElementById('epoGates');
    const note = document.getElementById('epoNote');
    const cp = document.getElementById('epoCheckpoint');
    if (!summary || !timeline || !gates) return;

    summary.innerHTML = `
      <div class="epo-box"><small>Status</small><b>${safe(r.status)}</b></div>
      <div class="epo-box"><small>Checkpoints</small><b>${fmt(r.checkpoint_count,0)} / ${fmt(r.required_checkpoints,0)}</b></div>
      <div class="epo-box"><small>Trade span</small><b>${fmt(r.trade_span,0)} / ${fmt(r.required_trade_span,0)}</b></div>
      <div class="epo-box"><small>Last 4 pass rate</small><b>${fmt(r.last_four_pass_rate_pct,1)}%</b></div>
      <div class="epo-box"><small>Next stage</small><b>${safe(r.next_stage)}</b></div>
      <div class="epo-box"><small>Real eligibility</small><b>${r.real_execution_eligibility ? '⛔ YES' : '🔒 NO'}</b></div>`;

    timeline.innerHTML = (r.timeline || []).map(p => {
      const pass = p.status === 'STRICT_PAPER_REVIEW_PASSED';
      return `<div class="epo-point ${pass ? 'pass' : 'fail'}"><b>${pass ? '✅' : '⛔'} #${safe(p.id)}</b><div>Samples: ${fmt(p.eligible_samples,0)}</div><div>30 Mean R: ${fmt(p.window30_mean_r,3)}</div><small>${safe(p.status)}</small></div>`;
    }).join('') || '<div class="muted">لا توجد checkpoints محفوظة بعد.</div>';

    gates.innerHTML = (r.gates || []).map(g => `<div class="epo-gate ${g.passed ? 'pass' : 'fail'}"><span>${g.passed ? '✅' : '⛔'}</span><b>${safe(g.id)}</b><span class="req">${safe(g.requirement)}</span></div>`).join('');

    if (cp && checkpoint) {
      cp.textContent = checkpoint.recorded ? `تم حفظ checkpoint عند ${checkpoint.eligible_samples} صفقة مؤهلة.` : `لم يُحفظ checkpoint: ${safe(checkpoint.reason)}${checkpoint.last_eligible_samples != null ? ` · آخر نقطة ${checkpoint.last_eligible_samples}` : ''}`;
    }
    if (note) note.innerHTML = `⚠️ ${safe(r.independence_warning)}<br><b>${safe(r.policy)}</b><br>Evidence type = ${safe(r.evidence_type)} · Auto target = ${r.target_auto_apply ? 'ON' : 'OFF'} · Live execution = ${r.live_execution_enabled ? 'ON' : 'OFF'}`;
  }

  async function refresh() {
    try {
      const res = await fetch('/api/extended-paper-observation');
      render(await res.json());
    } catch (e) {
      console.warn('Extended paper observation failed', e);
    }
  }

  async function checkpoint() {
    const b = document.getElementById('recordPaperCheckpoint');
    if (b) b.disabled = true;
    try {
      const res = await fetch('/api/extended-paper-observation/checkpoint', {method: 'POST'});
      const data = await res.json();
      render(data.observation || {}, data.checkpoint || {});
    } catch (e) {
      console.warn('Paper checkpoint failed', e);
    } finally {
      if (b) b.disabled = false;
    }
  }

  document.getElementById('refreshPaperObservation')?.addEventListener('click', refresh);
  document.getElementById('recordPaperCheckpoint')?.addEventListener('click', checkpoint);
  refresh();
  checkpoint();
  setInterval(refresh, 60000);
  setInterval(checkpoint, 300000);
  fetch('/api/version').then(r => r.json()).then(v => {
    document.title = `${v.name} ${v.label}`;
    const el = document.querySelector('h1 span');
    if (el) el.textContent = v.label;
  }).catch(() => {});
})();
