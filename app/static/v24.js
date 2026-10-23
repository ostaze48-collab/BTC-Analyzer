(() => {
  document.title='BTC AI Trader V1.14';
  const version=document.querySelector('h1 span');if(version)version.textContent='V1.14';
  const style=document.createElement('style');
  style.textContent=`
    .iwf-summary{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:10px}.iwf-box{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:10px}.iwf-box small{display:block;color:var(--muted);font-size:11px}.iwf-box b{display:block;margin-top:4px;font-size:15px}.iwf-list{display:grid;gap:7px;margin-top:12px}.iwf-row{display:grid;grid-template-columns:2fr .7fr .7fr .7fr .7fr;gap:8px;align-items:center;padding:9px 10px;background:var(--panel2);border:1px solid rgba(34,197,94,.28);border-radius:9px;font-size:12px}.iwf-note{margin-top:10px;padding:10px;border-radius:9px;border:1px solid rgba(96,165,250,.25);background:rgba(96,165,250,.07);font-size:12px}
    @media(max-width:900px){.iwf-summary{grid-template-columns:1fr 1fr}.iwf-summary .iwf-box:last-child{grid-column:1/-1}.iwf-row{grid-template-columns:1fr 1fr}.iwf-row .iwf-name{grid-column:1/-1}.iwf-row span:before{content:attr(data-label) ': ';color:var(--muted)}}`;
  document.head.appendChild(style);

  const edge=document.getElementById('edgeLabSection');
  if(edge){
    const section=document.createElement('section');section.id='incrementalEdgeSection';section.className='card section-learning';
    section.innerHTML=`<div class="section-title-row"><div><div class="card-title">Incremental Edge Walk-Forward</div><small class="muted">Baseline vs Baseline+Feature filter عبر نوافذ زمنية لاحقة</small></div><button id="refreshIncremental" class="primary" type="button">تحديث</button></div><div id="iwfSummary" class="iwf-summary"><div class="muted">بانتظار عينة كافية...</div></div><div id="iwfList" class="iwf-list"></div><div id="iwfNote" class="iwf-note">Research only · MASTER لم يتغير.</div>`;
    edge.parentNode.insertBefore(section,edge.nextSibling);
  }
  const n=(x,d=2)=>x==null?'—':Number(x).toLocaleString(undefined,{maximumFractionDigits:d});
  function render(r){
    const s=document.getElementById('iwfSummary'),list=document.getElementById('iwfList'),note=document.getElementById('iwfNote');if(!s||!list)return;
    s.innerHTML=`<div class="iwf-box"><small>Samples</small><b>${r.samples||0}</b></div><div class="iwf-box"><small>Features evaluated</small><b>${r.features_evaluated||0}</b></div><div class="iwf-box"><small>Eligible</small><b>${r.eligible_count||0}</b></div><div class="iwf-box"><small>Mode</small><b>${r.mode||'—'}</b></div><div class="iwf-box"><small>Status</small><b>${r.status||'—'}</b></div>`;
    const rows=r.diversified_top||[];
    list.innerHTML=rows.length?rows.slice(0,15).map(x=>`<div class="iwf-row"><div class="iwf-name"><b>${x.feature}</b><div class="edge-source">${x.source} · ${x.family} · ${x.folds} folds</div></div><span data-label="Pass folds">${n(x.positive_fold_pct,0)}%</span><span data-label="Δ Mean R">${n(x.mean_delta_r,3)}</span><span data-label="Δ PF">${n(x.mean_delta_profit_factor,3)}</span><span data-label="DD ratio">${n(x.mean_drawdown_ratio,2)}</span></div>`).join(''):`<div class="muted">${r.status==='INSUFFICIENT_DATA'?`نحتاج على الأقل ${r.minimum_samples||90} صفقة ذات Feature Vector صالح.`:'لا يوجد Feature حافظ على تحسن مستقر عبر Walk-Forward حتى الآن.'}</div>`;
    if(note)note.innerHTML=`🔬 <b>Auto apply = ${r.auto_apply?'ON':'OFF'}</b> · ${r.next_stage||'حتى المرشح الناجح يدخل Shadow Trial أولًا ولا يغيّر MASTER مباشرة.'}`;
  }
  async function refresh(){const b=document.getElementById('refreshIncremental');if(b)b.disabled=true;try{const res=await fetch('/api/incremental-edge'),data=await res.json();render(data);}catch(e){console.warn('Incremental edge failed',e);}finally{if(b)b.disabled=false;}}
  const b=document.getElementById('refreshIncremental');if(b)b.addEventListener('click',refresh);refresh();setInterval(refresh,60000);
})();
