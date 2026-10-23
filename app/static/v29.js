(() => {
  const style=document.createElement('style');
  style.textContent=`
    .target-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:10px}.target-box{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:10px}.target-box small{display:block;color:var(--muted);font-size:11px}.target-box b{display:block;margin-top:4px;font-size:15px}.target-table{display:grid;gap:7px;margin-top:10px}.target-row{display:grid;grid-template-columns:.6fr 1fr 1fr 1fr;gap:8px;align-items:center;padding:9px 10px;border:1px solid var(--line);background:var(--panel2);border-radius:9px;font-size:12px}.target-row.best{border-color:rgba(34,197,94,.45);background:rgba(34,197,94,.06)}.target-note{margin-top:10px;padding:10px;border-radius:9px;background:rgba(245,158,11,.07);border:1px solid rgba(245,158,11,.24);font-size:12px}
    @media(max-width:900px){.target-grid{grid-template-columns:1fr 1fr}.target-grid .target-box:last-child{grid-column:1/-1}.target-row{grid-template-columns:1fr 1fr}.target-row b{grid-column:1/-1}.target-row span:before{content:attr(data-label) ': ';color:var(--muted)}}
  `;
  document.head.appendChild(style);

  const sig=document.getElementById('signatureCacheSection');
  const analog=document.getElementById('historicalAnalogSection');
  const host=sig||analog||document.getElementById('learningSection');
  if(host){
    const section=document.createElement('section');section.id='historicalTargetAdvisorSection';section.className='card section-context';
    section.innerHTML=`
      <div class="section-title-row"><div><div class="card-title">Historical Target Advisor · 1R → 5R</div><small class="muted">يقرأ نتائج الحالات المشابهة ويقدّر أي هدف كان أفضل تاريخيًا لهذا الإعداد</small></div><button id="refreshTargetAdvisor" class="primary" type="button">تحديث</button></div>
      <div id="targetAdvisorSummary" class="target-grid"><div class="muted">بانتظار Historical Memory...</div></div>
      <div id="targetAdvisorTable" class="target-table"></div>
      <div id="targetAdvisorNote" class="target-note">Shadow only · لا يغيّر هدف الصفقة الحالية.</div>`;
    host.parentNode.insertBefore(section,host.nextSibling);
  }

  const n=(x,d=2)=>x==null?'—':Number(x).toLocaleString(undefined,{maximumFractionDigits:d});
  const statusLabel=s=>s==='POSITIVE_SHADOW_EDGE'?'✅ هدف تاريخي مرشح':s==='NO_POSITIVE_SHADOW_EDGE'?'⛔ لا يوجد هدف ذو EV محافظ موجب':'⏳ بيانات غير كافية';

  function render(r){
    const summary=document.getElementById('targetAdvisorSummary'),table=document.getElementById('targetAdvisorTable'),note=document.getElementById('targetAdvisorNote');
    if(!summary||!table)return;
    summary.innerHTML=`
      <div class="target-box"><small>الحكم</small><b>${statusLabel(r.status)}</b></div>
      <div class="target-box"><small>Historical matches</small><b>${r.matches||0}</b></div>
      <div class="target-box"><small>Recommended target</small><b>${r.recommended_r==null?'—':n(r.recommended_r,1)+'R'}</b></div>
      <div class="target-box"><small>Best conservative EV</small><b>${r.best_conservative_ev_r==null?'—':n(r.best_conservative_ev_r,3)+'R'}</b></div>
      <div class="target-box"><small>Evidence</small><b>${r.evidence_strength||r.quality||'—'}</b></div>`;
    const rows=r.targets||[];
    table.innerHTML=rows.length?rows.map(x=>`<div class="target-row ${Number(x.target_r)===Number(r.recommended_r)?'best':''}"><b>${n(x.target_r,0)}R</b><span data-label="Hit">${n(x.hit_pct,1)}%</span><span data-label="Conservative EV">${n(x.conservative_ev_r,3)}R</span><span data-label="Assumption">${x.assumption==='ALL_NON_HITS_ARE_-1R'?'non-hit = -1R':'path based'}</span></div>`).join(''):`<div class="muted">لا توجد عينة كافية بعد لتقدير هدف تاريخي.</div>`;
    if(note)note.innerHTML=`🎯 <b>Risk-engine weight = ${n(r.weight_in_risk_engine,1)}</b> · ${r.policy||'Research only.'}`;
  }

  async function refresh(){
    const b=document.getElementById('refreshTargetAdvisor');if(b)b.disabled=true;
    try{const res=await fetch('/api/historical-target-advisor'),r=await res.json();render(r);}catch(e){console.warn('Target advisor failed',e);}finally{if(b)b.disabled=false;}
  }
  const b=document.getElementById('refreshTargetAdvisor');if(b)b.addEventListener('click',refresh);
  refresh();setInterval(refresh,15000);
  fetch('/api/version').then(r=>r.json()).then(v=>{document.title=`${v.name} ${v.label}`;const el=document.querySelector('h1 span');if(el)el.textContent=v.label;}).catch(()=>{});
})();
