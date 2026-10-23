(() => {
  const style = document.createElement('style');
  style.textContent = `
    .urr-summary{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-top:10px}
    .urr-box{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:10px}
    .urr-box small{display:block;color:var(--muted);font-size:11px}.urr-box b{display:block;margin-top:4px;font-size:14px}
    .urr-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}
    .urr-list{display:grid;gap:7px}.urr-row{display:grid;grid-template-columns:.25fr 1fr 1.5fr;gap:8px;padding:9px;border:1px solid var(--line);border-radius:9px;background:var(--panel2);font-size:12px}
    .urr-row.pass{border-color:rgba(34,197,94,.35)}.urr-row.fail{border-color:rgba(239,68,68,.28)}
    .urr-note{margin-top:10px;padding:10px;border:1px solid rgba(245,158,11,.25);background:rgba(245,158,11,.06);border-radius:10px;font-size:12px}
    .urr-label{font-size:12px;font-weight:700;margin:2px 0 7px}.urr-muted{color:var(--muted);font-size:11px}
    @media(max-width:900px){.urr-summary{grid-template-columns:1fr 1fr}.urr-grid{grid-template-columns:1fr}.urr-row{grid-template-columns:.25fr 1fr}.urr-row .req{grid-column:1/-1;color:var(--muted)}}
  `;
  document.head.appendChild(style);

  const anchor = document.getElementById('targetEvidenceGateSection') || document.getElementById('learningSection');
  if (anchor) {
    const section = document.createElement('section');
    section.id = 'unifiedResearchReadinessSection';
    section.className = 'card section-learning';
    section.innerHTML = `
      <div class="section-title-row">
        <div>
          <div class="card-title">Unified Research Readiness</div>
          <small class="muted">حكم موحد يجمع Paper/OOS/Drawdown/Regime/Cycle + Target Evidence، ويعرض Feature Edge كدليل داعم لا كشرط يجبر النظام على overfitting</small>
        </div>
        <button id="refreshUnifiedReadiness" class="primary" type="button">تحديث</button>
      </div>
      <div id="urrSummary" class="urr-summary"><div class="muted">بانتظار الأدلة...</div></div>
      <div class="urr-grid">
        <div><div class="urr-label">Mandatory Gates</div><div id="urrMandatory" class="urr-list"></div></div>
        <div><div class="urr-label">Supporting Evidence</div><div id="urrSupporting" class="urr-list"></div></div>
      </div>
      <div id="urrNote" class="urr-note">Research Score للمقارنة فقط؛ لا يفعّل تداولًا ولا يتجاوز أي Hard Gate.</div>`;
    anchor.parentNode.insertBefore(section, anchor.nextSibling);
  }

  const fmt = (x, d = 1) => x == null ? '—' : Number(x).toLocaleString(undefined, {maximumFractionDigits: d});
  const safe = (x) => x == null ? '—' : String(x);

  function render(r) {
    const summary = document.getElementById('urrSummary');
    const mandatory = document.getElementById('urrMandatory');
    const supporting = document.getElementById('urrSupporting');
    const note = document.getElementById('urrNote');
    if (!summary || !mandatory || !supporting) return;

    const feature = r.feature_research || {};
    const target = r.target_evidence || {};
    const core = r.core_readiness || {};
    const failed = r.failed_mandatory_gates || [];

    summary.innerHTML = `
      <div class="urr-box"><small>Research Stage</small><b>${safe(r.status)}</b></div>
      <div class="urr-box"><small>Research Score</small><b>${fmt(r.research_score)} / 100</b></div>
      <div class="urr-box"><small>Core readiness</small><b>${safe(core.status)}</b></div>
      <div class="urr-box"><small>Target evidence</small><b>${target.all_gates_passed ? '✅ PASS' : '⛔ OPEN'}</b></div>
      <div class="urr-box"><small>Incremental Feature OOS</small><b>${feature.incremental_oos_evidence ? '✅ SUPPORT' : '—'}</b></div>
      <div class="urr-box"><small>Failed mandatory</small><b>${failed.length}</b></div>`;

    mandatory.innerHTML = (r.mandatory_gates || []).map(g => `
      <div class="urr-row ${g.passed ? 'pass' : 'fail'}">
        <span>${g.passed ? '✅' : '⛔'}</span>
        <b>${safe(g.id)}</b>
        <span class="req">${safe(g.requirement)}</span>
      </div>`).join('') || '<div class="urr-muted">لا توجد بيانات Mandatory بعد.</div>';

    supporting.innerHTML = (r.supporting_evidence || []).map(g => `
      <div class="urr-row ${g.passed ? 'pass' : 'fail'}">
        <span>${g.passed ? '✅' : '•'}</span>
        <b>${safe(g.id)}</b>
        <span class="req">${safe(g.meaning)}</span>
      </div>`).join('') || '<div class="urr-muted">لا توجد بيانات داعمة بعد.</div>';

    if (note) {
      note.innerHTML = `🔒 <b>Paper only = ${r.paper_only ? 'YES' : 'NO'}</b> · Strict Paper Review = ${r.strict_paper_review_allowed ? 'ALLOWED' : 'BLOCKED'} · Real execution eligibility = ${r.real_execution_eligibility ? 'YES' : 'NO'}<br>` +
        `<b>${safe(r.message)}</b><br><span class="urr-muted">Score authorization = ${r.score_is_authorization ? 'YES' : 'NO'} · Auto target apply = ${r.target_auto_apply ? 'ON' : 'OFF'} · ${safe(r.policy)}</span>`;
    }
  }

  async function refresh() {
    const button = document.getElementById('refreshUnifiedReadiness');
    if (button) button.disabled = true;
    try {
      const res = await fetch('/api/unified-readiness');
      render(await res.json());
    } catch (err) {
      console.warn('Unified readiness failed', err);
    } finally {
      if (button) button.disabled = false;
    }
  }

  document.getElementById('refreshUnifiedReadiness')?.addEventListener('click', refresh);
  refresh();
  setInterval(refresh, 60000);
  fetch('/api/version').then(r => r.json()).then(v => {
    document.title = `${v.name} ${v.label}`;
    const el = document.querySelector('h1 span');
    if (el) el.textContent = v.label;
  }).catch(() => {});
})();
