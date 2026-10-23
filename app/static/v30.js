(() => {
  const style=document.createElement('style');
  style.textContent=`
    .tpv-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-top:10px}.tpv-box{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:10px}.tpv-box small{display:block;color:var(--muted);font-size:11px}.tpv-box b{display:block;margin-top:4px;font-size:14px}.tpv-compare{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}.tpv-side{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:10px}.tpv-side h4{margin:0 0 8px}.tpv-row{display:flex;justify-content:space-between;gap:10px;padding:5px 0;border-bottom:1px solid rgba(148,163,184,.10);font-size:12px}.tpv-row:last-child{border-bottom:0}.tpv-holdout{margin-top:10px;padding:10px;border:1px solid rgba(96,165,250,.25);background:rgba(96,165,250,.06);border-radius:10px;font-size:12px}.tpv-note{margin-top:10px;padding:10px;border:1px solid rgba(245,158,11,.25);background:rgba(245,158,11,.06);border-radius:10px;font-size:12px}.tpv-good{border-color:rgba(34,197,94,.4)!important}.tpv-bad{border-color:rgba(239,68,68,.35)!important}
    @media(max-width:900px){.tpv-grid{grid-template-columns:1fr 1fr}.tpv-grid .tpv-box:nth-last-child(-n+2){grid-column:auto}.tpv-compare{grid-template-columns:1fr}}
  `;
  document.head.appendChild(style);

  const advisor=document.getElementById('historicalTargetAdvisorSection');
  const host=advisor||document.getElementById('learningSection');
  if(host){
    const section=document.createElement('section');section.id='targetPolicyValidationSection';section.className='card section-learning';
    section.innerHTML=`
      <div class="section-title-row"><div><div class="card-title">Target Policy Validation · هل الهدف التاريخي أفضل فعلًا؟</div><small class="muted">يقارن نفس مسار الصفقة: الهدف الحالي مقابل Historical Target Advisor بدون اختراع مستقبل غير مسجل</small></div><button id="refreshTargetPolicy" class="primary" type="button">تحديث</button></div>
      <div id="tpvSummary" class="tpv-grid"><div class="muted">بانتظار سجل صفقات قابل للمقارنة...</div></div>
      <div id="tpvCompare" class="tpv-compare"></div>
      <div id="tpvHoldout" class="tpv-holdout"></div>
      <div id="tpvNote" class="tpv-note">Validation only · لا يغيّر التنفيذ.</div>`;
    host.parentNode.insertBefore(section,host.nextSibling);
  }

  const n=(x,d=2)=>x==null?'—':Number(x).toLocaleString(undefined,{maximumFractionDigits:d});
  const statusLabel=s=>s==='JOURNAL_SHADOW_OUTPERFORMS'?'✅ Advisor أفضل على المسارات المحسومة':s==='NO_PROVEN_IMPROVEMENT'?'⛔ لا يوجد تحسن مثبت':'⏳ مسارات محسومة غير كافية';
  const side=(title,m,good=false)=>`<div class="tpv-side ${good?'tpv-good':''}"><h4>${title}</h4><div class="tpv-row"><span>Trades</span><b>${m?.trades||0}</b></div><div class="tpv-row"><span>Mean R</span><b>${n(m?.mean_r,3)}</b></div><div class="tpv-row"><span>Win rate</span><b>${n(m?.win_rate,1)}%</b></div><div class="tpv-row"><span>Profit Factor</span><b>${n(m?.profit_factor,2)}</b></div><div class="tpv-row"><span>Max DD</span><b>${n(m?.max_drawdown_r,2)}R</b></div></div>`;

  function render(r){
    const s=document.getElementById('tpvSummary'),c=document.getElementById('tpvCompare'),h=document.getElementById('tpvHoldout'),note=document.getElementById('tpvNote');if(!s||!c)return;
    const good=r.status==='JOURNAL_SHADOW_OUTPERFORMS';
    s.innerHTML=`
      <div class="tpv-box ${good?'tpv-good':r.status==='NO_PROVEN_IMPROVEMENT'?'tpv-bad':''}"><small>الحكم</small><b>${statusLabel(r.status)}</b></div>
      <div class="tpv-box"><small>Advisor eligible</small><b>${r.eligible_with_advisor||0}</b></div>
      <div class="tpv-box"><small>Resolved</small><b>${r.resolved_comparisons||0}</b></div>
      <div class="tpv-box"><small>Coverage</small><b>${n(r.resolution_coverage_pct,1)}%</b></div>
      <div class="tpv-box"><small>Δ Mean R</small><b>${n(r.delta_mean_r,3)}R</b></div>
      <div class="tpv-box"><small>DD ratio</small><b>${n(r.drawdown_ratio,2)}</b></div>`;
    c.innerHTML=side('Baseline · الهدف الحالي',r.baseline,false)+side('Historical Advisor',r.advisor,good);
    const ho=r.holdout||{};
    if(h)h.innerHTML=`🧪 <b>Holdout الأخير</b> · ${ho.trades||0} صفقة · Δ Mean R = <b>${n(ho.delta_mean_r,3)}R</b> · DD ratio = <b>${n(ho.drawdown_ratio,2)}</b> · Baseline PF ${n(ho.baseline?.profit_factor,2)} → Advisor PF ${n(ho.advisor?.profit_factor,2)}`;
    if(note){const limitations=(r.limitations||[]).map(x=>`<li>${x}</li>`).join('');note.innerHTML=`🔒 <b>Auto apply = ${r.auto_apply?'ON':'OFF'}</b> · Risk-engine weight ${n(r.weight_in_risk_engine,1)}<ul>${limitations}</ul><div>${r.next_stage||''}</div>`;}
  }

  async function refresh(){const b=document.getElementById('refreshTargetPolicy');if(b)b.disabled=true;try{const res=await fetch('/api/target-policy-validation'),r=await res.json();render(r);}catch(e){console.warn('Target policy validation failed',e);}finally{if(b)b.disabled=false;}}
  const b=document.getElementById('refreshTargetPolicy');if(b)b.addEventListener('click',refresh);
  refresh();setInterval(refresh,60000);
  fetch('/api/version').then(r=>r.json()).then(v=>{document.title=`${v.name} ${v.label}`;const el=document.querySelector('h1 span');if(el)el.textContent=v.label;}).catch(()=>{});
})();
