(() => {
  const style=document.createElement('style');
  style.textContent=`
    .lst-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-top:10px}.lst-box{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:10px}.lst-box small{display:block;color:var(--muted);font-size:11px}.lst-box b{display:block;margin-top:4px;font-size:14px}.lst-compare{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}.lst-side{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:10px}.lst-side.good{border-color:rgba(34,197,94,.42)}.lst-row{display:flex;justify-content:space-between;gap:8px;padding:5px 0;border-bottom:1px solid rgba(148,163,184,.1);font-size:12px}.lst-row:last-child{border-bottom:0}.lst-brains{display:grid;gap:6px;margin-top:10px}.lst-brain{display:grid;grid-template-columns:1fr .5fr .8fr .8fr .8fr;gap:6px;padding:8px;border:1px solid var(--line);background:var(--panel2);border-radius:8px;font-size:11px}.lst-holdout,.lst-note{margin-top:10px;padding:10px;border-radius:10px;font-size:12px}.lst-holdout{border:1px solid rgba(96,165,250,.25);background:rgba(96,165,250,.06)}.lst-note{border:1px solid rgba(245,158,11,.25);background:rgba(245,158,11,.06)}
    @media(max-width:900px){.lst-grid{grid-template-columns:1fr 1fr}.lst-compare{grid-template-columns:1fr}.lst-brain{grid-template-columns:1fr 1fr}.lst-brain b{grid-column:1/-1}}
  `;
  document.head.appendChild(style);

  const ftw=document.getElementById('fullTargetWalkforwardSection');
  const host=ftw||document.getElementById('targetPolicyValidationSection')||document.getElementById('learningSection');
  if(host){
    const section=document.createElement('section');section.id='liveShadowTargetSection';section.className='card section-learning';
    section.innerHTML=`
      <div class="section-title-row"><div><div class="card-title">Live Shadow Target · السوق الحالي</div><small class="muted">يعيد بناء قرار Advisor من Historical Analog المحفوظة وقت ENTRY، وليس من بيانات أحدث</small></div><button id="refreshLiveShadow" class="primary" type="button">تحديث</button></div>
      <div id="lstSummary" class="lst-grid"><div class="muted">بانتظار صفقات Paper مغلقة مع Historical Memory...</div></div>
      <div id="lstCompare" class="lst-compare"></div><div id="lstHoldout" class="lst-holdout"></div><div id="lstBrains" class="lst-brains"></div><div id="lstNote" class="lst-note">Frozen-entry evidence · Auto apply OFF.</div>`;
    host.parentNode.insertBefore(section,host.nextSibling);
  }

  const n=(x,d=2)=>x==null?'—':Number(x).toLocaleString(undefined,{maximumFractionDigits:d});
  const label=s=>s==='LIVE_SHADOW_OUTPERFORMS'?'✅ Shadow مستمر بالتفوق':s==='NO_LIVE_SHADOW_EDGE'?'⛔ لا يوجد Live Shadow Edge مثبت':'⏳ نحتاج صفقات حية أكثر';
  const metrics=(title,m,good=false)=>`<div class="lst-side ${good?'good':''}"><b>${title}</b><div class="lst-row"><span>Trades</span><strong>${m?.trades||0}</strong></div><div class="lst-row"><span>Mean R</span><strong>${n(m?.mean_r,3)}</strong></div><div class="lst-row"><span>Win rate</span><strong>${n(m?.win_rate,1)}%</strong></div><div class="lst-row"><span>Profit Factor</span><strong>${n(m?.profit_factor,2)}</strong></div><div class="lst-row"><span>Max DD</span><strong>${n(m?.max_drawdown_r,2)}R</strong></div></div>`;

  function render(r){
    const s=document.getElementById('lstSummary'),c=document.getElementById('lstCompare'),h=document.getElementById('lstHoldout'),brains=document.getElementById('lstBrains'),note=document.getElementById('lstNote');if(!s||!c)return;
    const good=r.status==='LIVE_SHADOW_OUTPERFORMS';
    s.innerHTML=`<div class="lst-box"><small>Status</small><b>${label(r.status)}</b></div><div class="lst-box"><small>Eligible</small><b>${r.eligible||0}</b></div><div class="lst-box"><small>Overrides</small><b>${r.advisor_overrides||0}</b></div><div class="lst-box"><small>Resolved</small><b>${r.resolved||0}</b></div><div class="lst-box"><small>Coverage</small><b>${n(r.resolution_coverage_pct,1)}%</b></div><div class="lst-box"><small>Δ Mean R</small><b>${n(r.delta_mean_r,3)}R</b></div>`;
    c.innerHTML=metrics('Baseline actual target',r.baseline,false)+metrics('Frozen-entry Shadow target',r.shadow,good);
    const ho=r.holdout||{};if(h)h.innerHTML=`🧪 <b>Latest holdout</b> · ${ho.trades||0} trades · Δ Mean R <b>${n(ho.delta_mean_r,3)}R</b> · DD ratio <b>${n(ho.drawdown_ratio,2)}</b> · PF ${n(ho.baseline?.profit_factor,2)} → ${n(ho.shadow?.profit_factor,2)}`;
    const bb=r.by_brain||{};if(brains)brains.innerHTML=Object.entries(bb).map(([name,x])=>`<div class="lst-brain"><b>${name}</b><span>n ${x.trades}</span><span>Base ${n(x.baseline_mean_r,2)}R</span><span>Shadow ${n(x.shadow_mean_r,2)}R</span><span>Δ ${n(x.delta_mean_r,2)}R</span></div>`).join('');
    if(note){const lim=(r.limitations||[]).map(x=>`<li>${x}</li>`).join('');note.innerHTML=`🔒 <b>Entry evidence frozen = ${r.entry_evidence_frozen?'YES':'NO'}</b> · Auto apply ${r.auto_apply?'ON':'OFF'} · Risk weight ${n(r.weight_in_risk_engine,1)}<ul>${lim}</ul><div>${r.next_stage||''}</div>`;}
  }
  async function refresh(){const b=document.getElementById('refreshLiveShadow');if(b)b.disabled=true;try{const res=await fetch('/api/live-shadow-target'),r=await res.json();render(r);}catch(e){console.warn('Live shadow target failed',e);}finally{if(b)b.disabled=false;}}
  document.getElementById('refreshLiveShadow')?.addEventListener('click',refresh);refresh();setInterval(refresh,60000);
  fetch('/api/version').then(r=>r.json()).then(v=>{document.title=`${v.name} ${v.label}`;const el=document.querySelector('h1 span');if(el)el.textContent=v.label;}).catch(()=>{});
})();
