(() => {
  const LEVELS = [
    {id:'L1_24H',hours:24,minSnapshots:8,minNewTrades:20,minTotal:120,minDays:1,strictRate:75,mandatoryRate:75},
    {id:'L2_72H',hours:72,minSnapshots:18,minNewTrades:45,minTotal:150,minDays:3,strictRate:80,mandatoryRate:80},
    {id:'L3_168H',hours:168,minSnapshots:35,minNewTrades:90,minTotal:200,minDays:6,strictRate:85,mandatoryRate:85},
  ];

  const style = document.createElement('style');
  style.textContent = `
    .sld-levels{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:10px}
    .sld-level{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:12px}.sld-level.pass{border-color:rgba(34,197,94,.4)}.sld-level.fail{border-color:rgba(239,68,68,.28)}
    .sld-head{display:flex;justify-content:space-between;gap:8px;align-items:center}.sld-head b{font-size:14px}.sld-chip{font-size:11px;padding:3px 7px;border-radius:999px;border:1px solid var(--line)}
    .sld-metrics{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:9px;font-size:11px}.sld-metrics span{background:rgba(148,163,184,.06);padding:7px;border-radius:8px}
    .sld-fails{margin-top:8px;color:var(--muted);font-size:11px}.sld-note{margin-top:10px;padding:10px;border:1px solid rgba(99,102,241,.25);background:rgba(99,102,241,.06);border-radius:10px;font-size:12px}
    @media(max-width:900px){.sld-levels{grid-template-columns:1fr}}
  `;
  document.head.appendChild(style);

  const anchor = document.getElementById('evidenceStabilityWindowSection') || document.getElementById('researchEvidenceHistorySection') || document.getElementById('learningSection');
  if (anchor) {
    const section = document.createElement('section');
    section.id = 'multiDayStabilityLadderSection';
    section.className = 'card section-learning';
    section.innerHTML = `
      <div class="section-title-row">
        <div><div class="card-title">Multi‑Day Stability Ladder · V1.28</div><small class="muted">24H → 72H → 7D · يتطلب توزيع صفقات Paper على أيام فعلية، وليس دفعة واحدة</small></div>
        <button id="refreshStabilityLadder" class="primary" type="button">تحديث</button>
      </div>
      <div id="sldLevels" class="sld-levels"><div class="muted">بانتظار Research History...</div></div>
      <div id="sldNote" class="sld-note">حتى L3 = ثبات Paper/Research فقط؛ لا يفتح real execution ولا Auto Apply.</div>`;
    anchor.parentNode.insertBefore(section, anchor.nextSibling);
  }

  const dt = x => { try { return new Date(x); } catch (_) { return null; } };
  const n = x => Number(x || 0);
  const fullMandatory = r => n(r.mandatory_total) > 0 && n(r.mandatory_passed) >= n(r.mandatory_total);
  const rank = s => ({DATA_BUILDING:0,EVIDENCE_BUILDING:1,SHADOW_VALIDATED:2,STRICT_PAPER_REVIEW_CANDIDATE:3}[s] ?? -1);

  function activeDays(rows, baselineTrades) {
    const lastByDay = new Map();
    rows.forEach(r => {
      const d = dt(r.captured_at); if (!d || Number.isNaN(d.getTime())) return;
      const day = d.toISOString().slice(0,10);
      lastByDay.set(day, Math.max(lastByDay.get(day) || 0, n(r.paper_trades)));
    });
    let prev = baselineTrades, active = 0;
    [...lastByDay.keys()].sort().forEach(day => {
      const v = lastByDay.get(day); if (v > prev) active += 1; prev = Math.max(prev, v);
    });
    return active;
  }

  function evaluate(rows, cfg) {
    if (!rows.length) return {passed:false,metrics:{},fails:['history']};
    const end = dt(rows.at(-1).captured_at), first = dt(rows[0].captured_at);
    if (!end || !first) return {passed:false,metrics:{},fails:['timestamps']};
    const cutoff = new Date(end.getTime() - cfg.hours * 3600000);
    const windowRows = rows.filter(r => { const d=dt(r.captured_at); return d && d >= cutoff; });
    const before = rows.filter(r => { const d=dt(r.captured_at); return d && d <= cutoff; });
    const baseline = before.at(-1) || rows[0], current = rows.at(-1);
    const spanH = (end-first)/3600000;
    const newTrades = Math.max(0, n(current.paper_trades)-n(baseline.paper_trades));
    const strictRate = windowRows.length ? windowRows.filter(r=>r.strict_pass).length/windowRows.length*100 : 0;
    const mandatoryRate = windowRows.length ? windowRows.filter(fullMandatory).length/windowRows.length*100 : 0;
    let regressions = 0;
    for(let i=1;i<windowRows.length;i++){
      const a=windowRows[i-1], b=windowRows[i];
      if(rank(b.status)<rank(a.status) || (a.strict_pass && !b.strict_pass)) regressions++;
    }
    const days = activeDays(windowRows, n(baseline.paper_trades));
    const checks = {
      span: spanH >= cfg.hours,
      snapshots: windowRows.length >= cfg.minSnapshots,
      trades: newTrades >= cfg.minNewTrades && n(current.paper_trades) >= cfg.minTotal,
      active_days: days >= cfg.minDays,
      unified_now: current.status === 'STRICT_PAPER_REVIEW_CANDIDATE',
      strict_now: !!current.strict_pass,
      strict_rate: strictRate >= cfg.strictRate,
      mandatory_rate: mandatoryRate >= cfg.mandatoryRate,
      regressions: regressions === 0,
      interlock: windowRows.every(r=>!r.real_execution_eligibility),
    };
    return {
      passed:Object.values(checks).every(Boolean),
      fails:Object.entries(checks).filter(([,v])=>!v).map(([k])=>k),
      metrics:{spanH, snapshots:windowRows.length,newTrades,total:n(current.paper_trades),activeDays:days,strictRate,mandatoryRate,regressions}
    };
  }

  function render(payload) {
    const rows = [...(payload.snapshots || [])].sort((a,b)=>String(a.captured_at).localeCompare(String(b.captured_at)));
    const results = LEVELS.map(l=>({...l,...evaluate(rows,l)}));
    let highest=0;
    results.forEach((r,i)=>{ if(r.passed && highest===i) highest=i+1; });
    const el=document.getElementById('sldLevels'), note=document.getElementById('sldNote'); if(!el) return;
    el.innerHTML=results.map((r,i)=>`<div class="sld-level ${r.passed?'pass':'fail'}">
      <div class="sld-head"><b>${r.id.replace('L1_','').replace('L2_','').replace('L3_','')}</b><span class="sld-chip">${r.passed?'✅ PASS':'⛔ OPEN'}</span></div>
      <div class="sld-metrics"><span>Span ${r.metrics.spanH?.toFixed?.(1) ?? '—'}h</span><span>Snapshots ${r.metrics.snapshots ?? 0}</span><span>New trades ${r.metrics.newTrades ?? 0}</span><span>Active days ${r.metrics.activeDays ?? 0}</span><span>Strict ${r.metrics.strictRate?.toFixed?.(1) ?? '0'}%</span><span>Mandatory ${r.metrics.mandatoryRate?.toFixed?.(1) ?? '0'}%</span></div>
      <div class="sld-fails">${r.fails.length ? 'Open: '+r.fails.join(', ') : 'All level gates passed'}</div>
    </div>`).join('');
    const labels=['BLOCKED','24H CONFIRMED','72H CONFIRMED','7D CONFIRMED'];
    if(note) note.innerHTML=`🪜 <b>Highest sequential level: ${labels[highest]}</b><br><span class="muted">Ladder reads the same Research History. A higher historical level cannot skip a failed lower level. Paper only · Real execution eligibility = NO · Auto target = OFF.</span>`;
  }

  async function refresh(){
    const b=document.getElementById('refreshStabilityLadder'); if(b)b.disabled=true;
    try{const r=await fetch('/api/research-history?limit=1000');render(await r.json());}catch(e){console.warn('Stability ladder failed',e);}finally{if(b)b.disabled=false;}
  }
  document.getElementById('refreshStabilityLadder')?.addEventListener('click',refresh);
  refresh(); setInterval(refresh,60000);
  fetch('/api/version').then(r=>r.json()).then(v=>{document.title=`${v.name} ${v.label}`;const el=document.querySelector('h1 span');if(el)el.textContent=v.label;}).catch(()=>{});
})();
