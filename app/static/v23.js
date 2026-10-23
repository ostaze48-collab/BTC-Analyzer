(() => {
  document.title = "BTC AI Trader V1.13";
  const version=document.querySelector("h1 span");
  if(version) version.textContent="V1.13";

  const style=document.createElement("style");
  style.textContent=`
    .edge-summary{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:10px}.edge-box{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:10px}.edge-box small{display:block;color:var(--muted);font-size:11px}.edge-box b{display:block;margin-top:4px;font-size:15px}.edge-list{display:grid;gap:7px;margin-top:12px}.edge-row{display:grid;grid-template-columns:2fr .7fr .7fr .7fr .7fr;gap:8px;align-items:center;padding:9px 10px;background:var(--panel2);border:1px solid var(--line);border-radius:9px;font-size:12px}.edge-row.candidate{border-color:rgba(34,197,94,.32)}.edge-source{color:var(--muted);font-size:10px}.edge-policy{margin-top:10px;padding:10px;border-radius:9px;background:rgba(245,158,11,.07);border:1px solid rgba(245,158,11,.22);font-size:12px}.edge-progress{margin-top:8px;color:var(--muted);font-size:12px}
    @media(max-width:900px){.edge-summary{grid-template-columns:1fr 1fr}.edge-summary .edge-box:last-child{grid-column:1/-1}.edge-row{grid-template-columns:1fr 1fr;gap:5px}.edge-row .edge-name{grid-column:1/-1}.edge-row span:before{content:attr(data-label) ': ';color:var(--muted)}}
  `;
  document.head.appendChild(style);

  const learning=document.getElementById('learningSection');
  if(learning){
    const section=document.createElement('section');
    section.id='edgeLabSection';section.className='card section-learning';
    section.innerHTML=`
      <div class="section-title-row"><div><div class="card-title">Feature Edge Lab · مختبر فائدة المؤشرات</div><small class="muted">Chronological 70/30 · يقيس المئات من الخصائص ولا يعطيها وزنًا تلقائيًا</small></div><button id="refreshEdgeLab" class="primary" type="button">تحديث</button></div>
      <div id="edgeSummary" class="edge-summary"><div class="muted">بانتظار بيانات صفقات كافية...</div></div>
      <div id="edgeProgress" class="edge-progress"></div>
      <div id="edgeList" class="edge-list"></div>
      <div id="edgePolicy" class="edge-policy">Auto promotion = OFF. أي Feature جديد يجب أن يثبت Incremental OOS Edge قبل دخوله إلى MASTER.</div>`;
    learning.parentNode.insertBefore(section,learning.nextSibling);
  }

  const n=(x,d=2)=>x==null?'—':Number(x).toLocaleString(undefined,{maximumFractionDigits:d});
  function render(report){
    const summary=document.getElementById('edgeSummary'),progress=document.getElementById('edgeProgress'),list=document.getElementById('edgeList'),policy=document.getElementById('edgePolicy');
    if(!summary||!list)return;
    summary.innerHTML=`
      <div class="edge-box"><small>Closed samples</small><b>${report.samples||0}</b></div>
      <div class="edge-box"><small>Features tested</small><b>${report.features_tested||0}</b></div>
      <div class="edge-box"><small>OOS candidates</small><b>${report.candidate_count||0}</b></div>
      <div class="edge-box"><small>Diversified</small><b>${report.diversified_candidate_count||0}</b></div>
      <div class="edge-box"><small>Status</small><b>${report.status||'—'}</b></div>`;
    if(report.status==='INSUFFICIENT_DATA'){
      const need=Math.max(0,(report.minimum_samples||45)-(report.samples||0));
      progress.textContent=`نحتاج ${need} صفقة مغلقة إضافية على الأقل لبدء فصل Train/Test الزمني.`;
      list.innerHTML='';
    }else{
      progress.textContent=`Train ${report.train_samples||0} · Test/OOS ${report.test_samples||0} · Outcome = realized R after fees`;
      const rows=report.diversified_top||[];
      list.innerHTML=rows.length?rows.slice(0,15).map(r=>`<div class="edge-row candidate"><div class="edge-name"><b>${r.feature}</b><div class="edge-source">${r.source} · ${r.family}</div></div><span data-label="Score">${n(r.edge_score,1)}</span><span data-label="OOS corr">${n(r.test_corr,3)}</span><span data-label="Spread">${n(r.oos_quartile_spread_r,2)}R</span><span data-label="Regime stable">${n(r.regime_stability_pct,0)}%</span></div>`).join(''):`<div class="muted">لا توجد Features اجتازت شروط المرشح خارج العينة حتى الآن.</div>`;
    }
    if(policy)policy.innerHTML=`🧪 <b>Auto promotion = ${report.auto_promotion_enabled?'ON':'OFF'}</b> · ${report.promotion_policy||'لن يدخل أي مؤشر إلى MASTER تلقائيًا من هذه الشاشة.'}`;
  }

  async function refresh(){
    const btn=document.getElementById('refreshEdgeLab');if(btn)btn.disabled=true;
    try{const r=await fetch('/api/edge-lab'),data=await r.json();render(data);}catch(e){console.warn('Edge Lab failed',e);}finally{if(btn)btn.disabled=false;}
  }
  const btn=document.getElementById('refreshEdgeLab');if(btn)btn.addEventListener('click',refresh);
  refresh();setInterval(refresh,30000);
})();
