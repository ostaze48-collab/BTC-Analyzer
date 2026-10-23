(() => {
  const style = document.createElement('style');
  style.textContent = `
    .reh-summary{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-top:10px}
    .reh-box{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:10px}
    .reh-box small{display:block;color:var(--muted);font-size:11px}.reh-box b{display:block;margin-top:4px;font-size:14px}
    .reh-timeline{display:grid;gap:7px;margin-top:10px;max-height:460px;overflow:auto}
    .reh-row{display:grid;grid-template-columns:1.05fr 1.2fr .75fr .8fr .7fr .7fr;gap:8px;align-items:center;padding:9px;border:1px solid var(--line);border-radius:9px;background:var(--panel2);font-size:11px}
    .reh-score{height:7px;background:rgba(148,163,184,.18);border-radius:999px;overflow:hidden;margin-top:4px}.reh-score span{display:block;height:100%;background:currentColor;border-radius:999px}
    .reh-note{margin-top:10px;padding:10px;border:1px solid rgba(59,130,246,.25);background:rgba(59,130,246,.06);border-radius:10px;font-size:12px}
    @media(max-width:900px){.reh-summary{grid-template-columns:1fr 1fr}.reh-row{grid-template-columns:1fr 1fr 1fr}.reh-row .wide{grid-column:span 2}}
  `;
  document.head.appendChild(style);

  const anchor = document.getElementById('unifiedResearchReadinessSection') || document.getElementById('learningSection');
  if (anchor) {
    const section = document.createElement('section');
    section.id = 'researchEvidenceHistorySection';
    section.className = 'card section-learning';
    section.innerHTML = `
      <div class="section-title-row">
        <div>
          <div class="card-title">Research Evidence History · سجل تطور الأدلة</div>
          <small class="muted">يتابع تطور Unified Readiness عبر الزمن ويكشف التحسن أو التراجع بدل الاعتماد على لقطة واحدة</small>
        </div>
        <button id="refreshResearchHistory" class="primary" type="button">تحديث</button>
      </div>
      <div id="rehSummary" class="reh-summary"><div class="muted">بانتظار سجل الأدلة...</div></div>
      <div id="rehTimeline" class="reh-timeline"></div>
      <div id="rehNote" class="reh-note">Trend = اتجاه قوة الأدلة البحثية فقط، وليس إشارة تداول.</div>`;
    anchor.parentNode.insertBefore(section, anchor.nextSibling);
  }

  const num = (x, d = 1) => x == null ? '—' : Number(x).toLocaleString(undefined, {maximumFractionDigits: d});
  const esc = (x) => x == null ? '—' : String(x).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const when = (x) => { try { return new Date(x).toLocaleString(); } catch (_) { return esc(x); } };
  const trendLabel = (t) => ({IMPROVING:'📈 IMPROVING',REGRESSING:'📉 REGRESSING',STABLE:'➡ STABLE',INSUFFICIENT_HISTORY:'⏳ NEED MORE HISTORY'}[t] || esc(t));

  function render(payload) {
    const summary = payload.summary || {};
    const rows = payload.snapshots || [];
    const s = document.getElementById('rehSummary');
    const list = document.getElementById('rehTimeline');
    const note = document.getElementById('rehNote');
    if (!s || !list) return;

    s.innerHTML = `
      <div class="reh-box"><small>Evidence Trend</small><b>${trendLabel(summary.trend)}</b></div>
      <div class="reh-box"><small>Current Stage</small><b>${esc(summary.current_stage)}</b></div>
      <div class="reh-box"><small>Snapshots</small><b>${num(summary.snapshots,0)}</b></div>
      <div class="reh-box"><small>Score Δ from first</small><b>${num(summary.research_score_delta_from_first)} pts</b></div>
      <div class="reh-box"><small>Mandatory Gates</small><b>${num(summary.mandatory_passed_current,0)} / ${num(summary.mandatory_total_current,0)}</b></div>
      <div class="reh-box"><small>Paper Trades</small><b>${num(summary.paper_trades_current,0)}</b></div>`;

    const recent = rows.slice(-16).reverse();
    list.innerHTML = recent.length ? recent.map(r => {
      const score = Math.max(0, Math.min(100, Number(r.research_score || 0)));
      return `<div class="reh-row">
        <span class="wide">${when(r.captured_at)}</span>
        <b class="wide">${esc(r.status)}</b>
        <span>Score ${num(score)}<div class="reh-score"><span style="width:${score}%"></span></div></span>
        <span>Gates ${num(r.mandatory_passed,0)}/${num(r.mandatory_total,0)}</span>
        <span>${r.target_pass ? '✅ Target' : '• Target'}</span>
        <span>${r.feature_incremental_oos ? '✅ Feature' : '• Feature'}</span>
      </div>`;
    }).join('') : '<div class="muted">لا توجد Snapshots كافية بعد. سيتم إنشاء السجل تلقائيًا مع تشغيل النظام.</div>';

    if (note) note.innerHTML = `🧭 <b>${trendLabel(summary.trend)}</b> · Best stage: ${esc(summary.best_stage)} · Stage regressions: ${num(summary.stage_regressions,0)}<br><span class="muted">${esc(summary.message)} · Real execution eligibility = ${payload.real_execution_eligibility ? 'YES' : 'NO'}</span>`;
  }

  async function refresh() {
    const button = document.getElementById('refreshResearchHistory');
    if (button) button.disabled = true;
    try {
      const response = await fetch('/api/research-history?limit=240');
      render(await response.json());
    } catch (error) {
      console.warn('Research history failed', error);
    } finally {
      if (button) button.disabled = false;
    }
  }

  document.getElementById('refreshResearchHistory')?.addEventListener('click', refresh);
  refresh();
  setInterval(refresh, 60000);
  fetch('/api/version').then(r => r.json()).then(v => {
    document.title = `${v.name} ${v.label}`;
    const el = document.querySelector('h1 span');
    if (el) el.textContent = v.label;
  }).catch(() => {});
})();
