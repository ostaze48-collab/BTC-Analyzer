(() => {
  const style=document.createElement('style');
  style.textContent=`
    .ftw-controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.ftw-controls select,.ftw-controls button{min-height:40px}.ftw-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-top:10px}.ftw-box{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:10px}.ftw-box small{display:block;color:var(--muted);font-size:11px}.ftw-box b{display:block;margin-top:4px;font-size:14px}.ftw-compare{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}.ftw-side{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:10px}.ftw-side.good{border-color:rgba(34,197,94,.42)}.ftw-row{display:flex;justify-content:space-between;gap:8px;padding:5px 0;border-bottom:1px solid rgba(148,163,184,.1);font-size:12px}.ftw-row:last-child{border-bottom:0}.ftw-regimes{display:grid;gap:6px;margin-top:10px}.ftw-regime{display:grid;grid-template-columns:1.2fr .5fr .8fr .8fr .8fr;gap:6px;padding:8px;background:var(--panel2);border:1px solid var(--line);border-radius:8px;font-size:11px}.ftw-note{margin-top:10px;padding:10px;border:1px solid rgba(96,165,250,.25);background:rgba(96,165,250,.06);border-radius:10px;font-size:12px}
    @media(max-width:900px){.ftw-grid{grid-template-columns:1fr 1fr}.ftw-compare{grid-template-columns:1fr}.ftw-regime{grid-template-columns:1fr 1fr}.ftw-regime b{grid-column:1/-1}.ftw-controls select{flex:1}}
  `;
  document.head.appendChild(style);

  const policy=document.getElementById('targetPolicyValidationSection');
  const host=policy||document.getElementById('historicalTargetAdvisorSection')||document.getElementById('learningSection');
  if(host){
    const section=document.createElement('section');section.id='fullTargetWalkforwardSection';section.className='card section-learning';
    section.innerHTML=`
      <div class="section-title-row"><div><div class="card-title">Full Historical Target Walk‑Forward</div><small class="muted">يعيد تشغيل العقول + MASTER على تاريخ عميق ويختار الهدف من الماضي فقط قبل قراءة Future Window</small></div></div>
      <div class="ftw-controls"><select id="ftwBrain"><option value="SCALP">SCALP</option><option value="INTRADAY" selected>INTRADAY</option><option value="SWING">SWING</option></select><button id="runFtw" class="primary" type="button">▶ تشغيل Walk‑Forward</button><button id="refreshFtw" type="button">تحديث</button></div>
      <div id="ftwStatus" class="muted" style="margin-top:8px">لم يتم تشغيل الاختبار بعد.</div>
      <div id="ftwSummary" class="ftw-grid"></div><div id="ftwCompare" class="ftw-compare"></div><div id="ftwRegimes" class="ftw-regimes"></div><div id="ftwNote" class="ftw-note">Full candle path · No lookahead · Auto apply OFF.</div>`;
    host.parentNode.insertBefore(section,host.nextSibling);
  }

  const n=(x,d=2)=>x==null?'—':Number(x).toLocaleString(undefined,{maximumFractionDigits:d});
  const metrics=(title,m,good=false)=>`<div class="ftw-side ${good?'good':''}"><b>${title}</b><div class="ftw-row"><span>Trades</span><strong>${m?.trades||0}</strong></div><div class="ftw-row"><span>Mean R</span><strong>${n(m?.mean_r,3)}</strong></div><div class="ftw-row"><span>Win rate</span><strong>${n(m?.win_rate,1)}%</strong></div><div class="ftw-row"><span>Profit Factor</span><strong>${n(m?.profit_factor,2)}</strong></div><div class="ftw-row"><span>Max DD</span><strong>${n(m?.max_drawdown_r,2)}R</strong></div></div>`;
  const label=s=>s==='FULL_WALKFORWARD_OUTPERFORMS'?'✅ Out-of-sample target edge':s==='NO_FULL_WALKFORWARD_EDGE'?'⛔ لا يوجد Edge كامل مثبت':s==='ARCHIVE_LOADING'?'⏳ تحميل التاريخ العميق':s==='RUNNING'?'⏳ الاختبار يعمل':s?.startsWith('INSUFFICIENT')?'⏳ عينة غير كافية':s||'NOT_RUN';

  function render(r){
    const st=document.getElementById('ftwStatus'),sum=document.getElementById('ftwSummary'),cmp=document.getElementById('ftwCompare'),regs=document.getElementById('ftwRegimes'),note=document.getElementById('ftwNote');
    if(st)st.innerHTML=`${label(r.status)} · <b>${r.brain||document.getElementById('ftwBrain')?.value||'—'}</b>${r.anchor?` · anchor ${r.anchor}`:''}`;
    if(r.status==='ARCHIVE_LOADING'||r.status==='RUNNING'||r.status==='NOT_RUN'){
      if(sum)sum.innerHTML=`<div class="ftw-box"><small>Archive</small><b>${r.archive?.status||r.status}</b></div>`;if(cmp)cmp.innerHTML='';if(regs)regs.innerHTML='';return;
    }
    const good=r.status==='FULL_WALKFORWARD_OUTPERFORMS';
    if(sum)sum.innerHTML=`<div class="ftw-box"><small>Status</small><b>${label(r.status)}</b></div><div class="ftw-box"><small>Engine-selected records</small><b>${r.engine_selected_records||0}</b></div><div class="ftw-box"><small>Validation rows</small><b>${r.validation_rows||0}</b></div><div class="ftw-box"><small>Advisor overrides</small><b>${r.advisor_overrides||0}</b></div><div class="ftw-box"><small>Override rate</small><b>${n(r.override_rate_pct,1)}%</b></div><div class="ftw-box"><small>Δ Mean R</small><b>${n(r.delta_mean_r,3)}R</b></div>`;
    if(cmp)cmp.innerHTML=metrics('Baseline Risk Engine',r.baseline,false)+metrics('Local Historical Target',r.advisor,good)+`<div class="ftw-side"><b>Final Holdout</b><div class="ftw-row"><span>Rows</span><strong>${r.holdout?.rows||0}</strong></div><div class="ftw-row"><span>Δ Mean R</span><strong>${n(r.holdout?.delta_mean_r,3)}R</strong></div><div class="ftw-row"><span>DD ratio</span><strong>${n(r.holdout?.drawdown_ratio,2)}</strong></div><div class="ftw-row"><span>Baseline PF</span><strong>${n(r.holdout?.baseline?.profit_factor,2)}</strong></div><div class="ftw-row"><span>Advisor PF</span><strong>${n(r.holdout?.advisor?.profit_factor,2)}</strong></div></div>`;
    const rr=r.by_regime||{};if(regs)regs.innerHTML=Object.entries(rr).map(([name,x])=>`<div class="ftw-regime"><b>${name}</b><span>n ${x.trades}</span><span>Base ${n(x.baseline_mean_r,2)}R</span><span>Advisor ${n(x.advisor_mean_r,2)}R</span><span>Δ ${n(x.delta_mean_r,2)}R</span></div>`).join('');
    if(note)note.innerHTML=`🔬 <b>No lookahead = ${r.no_lookahead?'YES':'—'}</b> · Auto apply ${r.auto_apply?'ON':'OFF'} · Risk-engine weight ${n(r.weight_in_risk_engine,1)}<br>${r.policy||''}<br>${r.next_stage||''}`;
  }

  async function refresh(){const brain=document.getElementById('ftwBrain')?.value||'INTRADAY';try{const res=await fetch(`/api/full-target-walkforward?brain=${encodeURIComponent(brain)}`),r=await res.json();render(r);}catch(e){console.warn('FTW refresh failed',e);}}
  async function run(){const b=document.getElementById('runFtw'),brain=document.getElementById('ftwBrain')?.value||'INTRADAY';if(b)b.disabled=true;try{let res=await fetch(`/api/full-target-walkforward?brain=${encodeURIComponent(brain)}&max_points=300`,{method:'POST'}),r=await res.json();render(r);if(r.status==='ARCHIVE_LOADING'){setTimeout(async()=>{if(b)b.disabled=true;try{const x=await fetch(`/api/full-target-walkforward?brain=${encodeURIComponent(brain)}&max_points=300`,{method:'POST'}),j=await x.json();render(j);}finally{if(b)b.disabled=false;}},5000);return;}}catch(e){console.warn('FTW run failed',e);}finally{if(b)b.disabled=false;}}
  document.getElementById('runFtw')?.addEventListener('click',run);document.getElementById('refreshFtw')?.addEventListener('click',refresh);document.getElementById('ftwBrain')?.addEventListener('change',refresh);refresh();
  fetch('/api/version').then(r=>r.json()).then(v=>{document.title=`${v.name} ${v.label}`;const el=document.querySelector('h1 span');if(el)el.textContent=v.label;}).catch(()=>{});
})();
