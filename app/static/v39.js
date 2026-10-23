(() => {
  const style = document.createElement('style');
  style.textContent = `
    .rbm-summary{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-top:10px}
    .rbm-box{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:10px}.rbm-box small{display:block;color:var(--muted);font-size:11px}.rbm-box b{display:block;margin-top:4px;font-size:14px}
    .rbm-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-top:10px}.rbm-cell{padding:10px;border:1px solid var(--line);border-radius:10px;background:var(--panel2);font-size:11px}.rbm-cell.robust{border-color:rgba(34,197,94,.35)}.rbm-cell.weak{border-color:rgba(239,68,68,.28)}
    .rbm-head{display:flex;justify-content:space-between;gap:6px}.rbm-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:5px;margin-top:7px}.rbm-stats span{padding:5px;background:rgba(148,163,184,.06);border-radius:7px;text-align:center}
    .rbm-gates{display:grid;gap:6px;margin-top:10px}.rbm-gate{display:flex;gap:8px;align-items:flex-start;padding:8px;border:1px solid var(--line);border-radius:8px;font-size:11px}.rbm-note{margin-top:10px;padding:10px;border:1px solid rgba(14,165,233,.25);background:rgba(14,165,233,.05);border-radius:10px;font-size:12px}
    @media(max-width:1000px){.rbm-summary{grid-template-columns:repeat(3,1fr)}}
    @media(max-width:900px){.rbm-summary{grid-template-columns:1fr 1fr}.rbm-grid{grid-template-columns:1fr}.rbm-stats{grid-template-columns:1fr 1fr}}
  `;
  document.head.appendChild(style);

  const anchor = document.getElementById('multiDayStabilityLadderSection') || document.getElementById('evidenceStabilityWindowSection') || document.getElementById('learningSection');
  if (anchor) {
    const section = document.createElement('section');
    section.id = 'robustnessMatrixSection';
    section.className = 'card section-learning';
    section.innerHTML = `
      <div class="section-title-row"><div><div class="card-title">Brain × Regime Robustness Matrix · V1.29</div><small class="muted">هل الـEdge موزعة طبيعيًا على أكثر من عقل وحالة سوق، أم تعتمد على خلية واحدة فقط؟</small></div><button id="refreshRobustnessMatrix" class="primary" type="button">تحديث</button></div>
      <div id="rbmSummary" class="rbm-summary"><div class="muted">بانتظار بيانات الصفقات...</div></div>
      <div id="rbmGates" class="rbm-gates"></div>
      <div id="rbmGrid" class="rbm-grid"></div>
      <div id="rbmNote" class="rbm-note">هذه طبقة تشخيصية فقط؛ لا تجبر النظام على التداول في Regime ضعيف للحصول على تغطية.</div>`;
    anchor.parentNode.insertBefore(section, anchor.nextSibling);
  }

  const n = x => Number(x || 0);
  const fmt = (x,d=2)=>Number.isFinite(Number(x))?Number(x).toLocaleString(undefined,{maximumFractionDigits:d}):'—';
  const esc=x=>x==null?'—':String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const rank=s=>({DATA_BUILDING:0,EVIDENCE_BUILDING:1,SHADOW_VALIDATED:2,STRICT_PAPER_REVIEW_CANDIDATE:3}[s]??-1);

  function levelPass(rows,cfg){
    if(!rows.length)return false; const end=new Date(rows.at(-1).captured_at), first=new Date(rows[0].captured_at); if(!Number.isFinite(end.getTime())||!Number.isFinite(first.getTime()))return false;
    const cutoff=new Date(end.getTime()-cfg.hours*3600000); const w=rows.filter(r=>new Date(r.captured_at)>=cutoff); const before=rows.filter(r=>new Date(r.captured_at)<=cutoff); const base=before.at(-1)||rows[0], cur=rows.at(-1);
    const strict=w.length?w.filter(r=>r.strict_pass).length/w.length*100:0; const mandatory=w.length?w.filter(r=>n(r.mandatory_total)>0&&n(r.mandatory_passed)>=n(r.mandatory_total)).length/w.length*100:0;
    let regress=0; for(let i=1;i<w.length;i++){if(rank(w[i].status)<rank(w[i-1].status)||(w[i-1].strict_pass&&!w[i].strict_pass))regress++;}
    const dayLast=new Map(); w.forEach(r=>{const d=new Date(r.captured_at); if(!Number.isFinite(d.getTime()))return; const key=d.toISOString().slice(0,10); dayLast.set(key,Math.max(dayLast.get(key)||0,n(r.paper_trades)));}); let active=0, prev=n(base.paper_trades); [...dayLast.keys()].sort().forEach(k=>{const v=dayLast.get(k);if(v>prev)active++;prev=Math.max(prev,v);});
    return (end-first)/3600000>=cfg.hours && w.length>=cfg.minSnapshots && n(cur.paper_trades)-n(base.paper_trades)>=cfg.minNew && n(cur.paper_trades)>=cfg.minTotal && active>=cfg.minDays && cur.status==='STRICT_PAPER_REVIEW_CANDIDATE' && !!cur.strict_pass && strict>=cfg.strictRate && mandatory>=cfg.mandatoryRate && regress===0 && w.every(r=>!r.real_execution_eligibility);
  }

  function sevenDayConfirmed(history){
    const rows=[...(history.snapshots||[])].sort((a,b)=>String(a.captured_at).localeCompare(String(b.captured_at)));
    const configs=[
      {hours:24,minSnapshots:8,minNew:20,minTotal:120,minDays:1,strictRate:75,mandatoryRate:75},
      {hours:72,minSnapshots:18,minNew:45,minTotal:150,minDays:3,strictRate:80,mandatoryRate:80},
      {hours:168,minSnapshots:35,minNew:90,minTotal:200,minDays:6,strictRate:85,mandatoryRate:85},
    ];
    return configs.every(c=>levelPass(rows,c));
  }

  function tradeR(t){const risk=n(t.risk_budget);if(risk<=0)return null;return Math.max(-10,Math.min(10,n(t.realized_pnl)/risk));}
  function metrics(rs){if(!rs.length)return{trades:0,meanR:0,netR:0,pf:0,win:0};const wins=rs.filter(x=>x>0),loss=rs.filter(x=>x<0),gw=wins.reduce((a,b)=>a+b,0),gl=Math.abs(loss.reduce((a,b)=>a+b,0));return{trades:rs.length,meanR:rs.reduce((a,b)=>a+b,0)/rs.length,netR:rs.reduce((a,b)=>a+b,0),pf:gl?gw/gl:(gw?999:0),win:wins.length/rs.length*100};}

  function evaluate(history,trades){
    const valid=(trades||[]).filter(t=>t.status==='CLOSED').map(t=>({...t,r:tradeR(t)})).filter(t=>t.r!=null).slice(0,200);
    const brainCount={},regimeCount={},groups={}; valid.forEach(t=>{const b=t.brain||'UNKNOWN',r=t.market_regime||'UNKNOWN';if(b!=='UNKNOWN')brainCount[b]=(brainCount[b]||0)+1;if(r!=='UNKNOWN')regimeCount[r]=(regimeCount[r]||0)+1;if(b!=='UNKNOWN'&&r!=='UNKNOWN'){const k=`${b}||${r}`;(groups[k] ||= []).push(t.r);}});
    const total=valid.length, qBrains=Object.fromEntries(Object.entries(brainCount).filter(([,v])=>v>=20)),qRegimes=Object.fromEntries(Object.entries(regimeCount).filter(([,v])=>v>=20));
    const maxBrain=Math.max(100,...Object.values(brainCount).map(v=>v/Math.max(1,total)*100)),maxRegime=Math.max(100,...Object.values(regimeCount).map(v=>v/Math.max(1,total)*100));
    const cells=Object.entries(groups).map(([k,rs])=>{const [brain,regime]=k.split('||'),m=metrics(rs);return{brain,regime,...m,mature:rs.length>=15,robust:rs.length>=15&&m.meanR>0&&m.pf>=1.05};});
    const mature=cells.filter(c=>c.mature),robust=mature.filter(c=>c.robust),robustRate=mature.length?robust.length/mature.length*100:0,worst=mature.length?Math.min(...mature.map(c=>c.meanR)):-999,pos=mature.filter(c=>c.netR>0),sumPos=pos.reduce((a,c)=>a+c.netR,0),concentration=sumPos>0?Math.max(...pos.map(c=>c.netR))/sumPos*100:100;
    const checks={seven_day_stability:sevenDayConfirmed(history),valid_r_sample:total>=150,brain_coverage:Object.keys(qBrains).length>=2,brain_concentration:maxBrain<=80,regime_coverage:Object.keys(qRegimes).length>=2,regime_concentration:maxRegime<=85,mature_cells:mature.length>=4,robust_cell_rate:mature.length>=4&&robustRate>=60,no_severely_negative_mature_cell:mature.length>0&&worst>=-0.20,positive_edge_concentration:pos.length>=2&&concentration<=70};
    return{passed:Object.values(checks).every(Boolean),checks,total,qBrains,qRegimes,maxBrain,maxRegime,cells,mature:mature.length,robust:robust.length,robustRate,concentration};
  }

  function render(r){const s=document.getElementById('rbmSummary'),g=document.getElementById('rbmGates'),grid=document.getElementById('rbmGrid'),note=document.getElementById('rbmNote');if(!s||!g||!grid)return;
    s.innerHTML=`<div class="rbm-box"><small>Status</small><b>${r.passed?'✅ ROBUSTNESS PASSED':'⛔ BLOCKED'}</b></div><div class="rbm-box"><small>Valid R trades</small><b>${r.total}</b></div><div class="rbm-box"><small>Brains ≥20</small><b>${Object.keys(r.qBrains).length}</b></div><div class="rbm-box"><small>Regimes ≥20</small><b>${Object.keys(r.qRegimes).length}</b></div><div class="rbm-box"><small>Mature / Robust cells</small><b>${r.mature} / ${r.robust}</b></div><div class="rbm-box"><small>Top +R cell concentration</small><b>${fmt(r.concentration,1)}%</b></div>`;
    g.innerHTML=Object.entries(r.checks).map(([k,v])=>`<div class="rbm-gate"><span>${v?'✅':'⛔'}</span><b>${esc(k)}</b></div>`).join('');
    grid.innerHTML=r.cells.length?r.cells.sort((a,b)=>b.trades-a.trades).map(c=>`<div class="rbm-cell ${c.robust?'robust':(c.mature?'weak':'')}"><div class="rbm-head"><b>${esc(c.brain)} × ${esc(c.regime)}</b><span>${c.mature?(c.robust?'✅ ROBUST':'⚠ MATURE'):'• LEARNING'}</span></div><div class="rbm-stats"><span>${c.trades} trades</span><span>Mean R ${fmt(c.meanR,3)}</span><span>PF ${fmt(c.pf,2)}</span><span>Win ${fmt(c.win,1)}%</span></div></div>`).join(''):'<div class="muted">لا توجد خلايا كافية بعد.</div>';
    if(note)note.innerHTML=`🧩 <b>Natural diversity only.</b> لا يتم فتح صفقات فقط لإكمال Brain أو Regime ناقص. Passing يبقى Paper-only، Real execution eligibility = NO.`;
  }

  async function refresh(){const b=document.getElementById('refreshRobustnessMatrix');if(b)b.disabled=true;try{const [h,t]=await Promise.all([fetch('/api/research-history?limit=1000').then(r=>r.json()),fetch('/api/trades?limit=200').then(r=>r.json())]);render(evaluate(h,t));}catch(e){console.warn('Robustness matrix failed',e);}finally{if(b)b.disabled=false;}}
  document.getElementById('refreshRobustnessMatrix')?.addEventListener('click',refresh);refresh();setInterval(refresh,60000);
  fetch('/api/version').then(r=>r.json()).then(v=>{document.title=`${v.name} ${v.label}`;const el=document.querySelector('h1 span');if(el)el.textContent=v.label;}).catch(()=>{});
})();
