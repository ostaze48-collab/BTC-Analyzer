(() => {
  const style = document.createElement('style');
  style.textContent = `
    .spr-head{display:flex;justify-content:space-between;gap:10px;align-items:center}
    .spr-summary{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:10px}
    .spr-box{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:10px}
    .spr-box small{display:block;color:var(--muted);font-size:11px}.spr-box b{display:block;margin-top:4px;font-size:14px}
    .spr-windows{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:10px}
    .spr-window{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:10px}.spr-window.pass{border-color:rgba(34,197,94,.35)}.spr-window.fail{border-color:rgba(239,68,68,.30)}
    .spr-window h4{margin:0 0 7px;font-size:13px}.spr-metrics{display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:12px}.spr-metrics span{color:var(--muted)}
    .spr-gates{display:grid;gap:7px;margin-top:10px}.spr-gate{display:grid;grid-template-columns:.25fr 1fr 1.8fr;gap:8px;padding:9px;border:1px solid var(--line);border-radius:9px;background:var(--panel2);font-size:12px}.spr-gate.pass{border-color:rgba(34,197,94,.35)}.spr-gate.fail{border-color:rgba(239,68,68,.30)}
    .spr-note{margin-top:10px;padding:10px;border:1px solid rgba(245,158,11,.25);background:rgba(245,158,11,.06);border-radius:10px;font-size:12px}
    .spr-conc{margin-top:10px;font-size:12px;color:var(--muted)}
    @media(max-width:900px){.spr-summary{grid-template-columns:1fr 1fr}.spr-summary .spr-box:last-child{grid-column:1/-1}.spr-windows{grid-template-columns:1fr}.spr-gate{grid-template-columns:.25fr 1fr}.spr-gate .req{grid-column:1/-1;color:var(--muted)}}
  `;
  document.head.appendChild(style);

  const anchor = document.getElementById('unifiedResearchReadinessSection') || document.getElementById('learningSection');
  if (anchor) {
    const section = document.createElement('section');
    section.id = 'strictPaperReviewSection';
    section.className = 'card section-learning';
    section.innerHTML = `
      <div class="spr-head">
        <div><div class="card-title">Strict Paper Review Protocol</div><small class="muted">ثبات آخر 30 / 60 / 100 صفقة Paper · تشخيص تدهور فقط، وليس OOS مستقل</small></div>
        <button id="refreshStrictPaper" class="primary" type="button">تحديث</button>
      </div>
      <div id="sprSummary" class="spr-summary"><div class="muted">بانتظار بيانات Paper...</div></div>
      <div id="sprWindows" class="spr-windows"></div>
      <div id="sprGates" class="spr-gates"></div>
      <div id="sprConcentration" class="spr-conc"></div>
      <div id="sprNote" class="spr-note">هذه المرحلة Paper فقط.</div>`;
    anchor.parentNode.insertBefore(section, anchor.nextSibling);
  }

  const fmt = (x, d = 2) => x == null ? '—' : Number(x).toLocaleString(undefined, {maximumFractionDigits: d});
  const safe = x => x == null ? '—' : String(x);

  function render(r) {
    const summary = document.getElementById('sprSummary');
    const windows = document.getElementById('sprWindows');
    const gates = document.getElementById('sprGates');
    const conc = document.getElementById('sprConcentration');
    const note = document.getElementById('sprNote');
    if (!summary || !windows || !gates) return;

    summary.innerHTML = `
      <div class="spr-box"><small>Status</small><b>${safe(r.status)}</b></div>
      <div class="spr-box"><small>Eligible samples</small><b>${fmt(r.eligible_samples,0)} / ${fmt(r.minimum_samples,0)}</b></div>
      <div class="spr-box"><small>Next stage</small><b>${safe(r.next_stage)}</b></div>
      <div class="spr-box"><small>Paper only</small><b>${r.paper_only ? '✅ YES' : '⛔ NO'}</b></div>
      <div class="spr-box"><small>Real execution eligibility</small><b>${r.real_execution_eligibility ? '⛔ YES' : '🔒 NO'}</b></div>`;

    windows.innerHTML = ['30','60','100'].map(key => {
      const w = (r.windows || {})[key] || {};
      return `<div class="spr-window ${w.passed ? 'pass' : 'fail'}"><h4>${w.passed ? '✅' : '⛔'} آخر ${key} صفقة</h4><div class="spr-metrics"><span>Mean R</span><b>${fmt(w.mean_r,3)}</b><span>Profit Factor</span><b>${fmt(w.profit_factor,3)}</b><span>Max DD</span><b>${fmt(w.max_drawdown_r,2)}R</b><span>Net R</span><b>${fmt(w.net_r,2)}R</b><span>Win rate</span><b>${fmt(w.win_rate_pct,1)}%</b><span>Available</span><b>${w.available ? 'YES' : 'NO'}</b></div></div>`;
    }).join('');

    gates.innerHTML = (r.gates || []).map(g => `<div class="spr-gate ${g.passed ? 'pass' : 'fail'}"><span>${g.passed ? '✅' : '⛔'}</span><b>${safe(g.id)}</b><span class="req">${safe(g.requirement)}</span></div>`).join('');

    const c = r.concentration || {};
    if (conc) conc.innerHTML = `Brain share (last 100): ${Object.entries(c.brain_share_pct || {}).map(([k,v]) => `${k} ${fmt(v,1)}%`).join(' · ') || '—'}<br>Regime share: ${Object.entries(c.regime_share_pct || {}).map(([k,v]) => `${k} ${fmt(v,1)}%`).join(' · ') || '—'}`;

    if (note) note.innerHTML = `⚠️ ${safe(r.independence_warning)}<br><b>${safe(r.policy)}</b><br>Auto target apply = ${r.target_auto_apply ? 'ON' : 'OFF'} · Live execution = ${r.live_execution_enabled ? 'ON' : 'OFF'}`;
  }

  async function refresh() {
    const b = document.getElementById('refreshStrictPaper');
    if (b) b.disabled = true;
    try {
      const res = await fetch('/api/strict-paper-review');
      render(await res.json());
    } catch (e) {
      console.warn('Strict paper review failed', e);
    } finally {
      if (b) b.disabled = false;
    }
  }

  document.getElementById('refreshStrictPaper')?.addEventListener('click', refresh);
  refresh();
  setInterval(refresh, 60000);
  fetch('/api/version').then(r => r.json()).then(v => {
    document.title = `${v.name} ${v.label}`;
    const el = document.querySelector('h1 span');
    if (el) el.textContent = v.label;
  }).catch(() => {});
})();
