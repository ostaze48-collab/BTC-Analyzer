(() => {
  const style=document.createElement('style');
  style.textContent=`
    .analog-summary{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-top:10px}.analog-box{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:10px}.analog-box small{display:block;color:var(--muted);font-size:11px}.analog-box b{display:block;margin-top:4px;font-size:15px}.analog-rates{display:grid;grid-template-columns:repeat(6,1fr);gap:6px;margin-top:10px}.analog-rate{padding:8px;background:var(--panel2);border:1px solid var(--line);border-radius:8px;text-align:center}.analog-rate small{display:block;color:var(--muted);font-size:10px}.analog-examples{display:grid;gap:6px;margin-top:10px}.analog-example{display:grid;grid-template-columns:1.2fr .7fr .7fr .7fr;gap:6px;padding:8px 9px;border:1px solid var(--line);background:var(--panel2);border-radius:8px;font-size:11px}.analog-note,.analog-validation{margin-top:10px;padding:10px;border-radius:9px;border:1px solid rgba(96,165,250,.24);background:rgba(96,165,250,.07);font-size:12px}.analog-validation.useful{border-color:rgba(34,197,94,.32);background:rgba(34,197,94,.07)}.analog-validation.mixed{border-color:rgba(245,158,11,.32);background:rgba(245,158,11,.07)}.analog-good{border-color:rgba(34,197,94,.32)!important}.analog-warn{border-color:rgba(245,158,11,.32)!important}
    @media(max-width:900px){.analog-summary{grid-template-columns:1fr 1fr}.analog-rates{grid-template-columns:repeat(3,1fr)}.analog-example{grid-template-columns:1fr 1fr}.analog-example .analog-date{grid-column:1/-1}}
  `;
  document.head.appendChild(style);

  const market=document.getElementById('marketContextSection');
  const host=market||document.getElementById('learningSection');
  if(host){
    const section=document.createElement('section');
    section.id='historicalAnalogSection';
    section.className='card section-context';
    section.innerHTML=`
      <div class="section-title-row"><div><div class="card-title">Historical Setup Memory · هل نجحت هذه الصفقة سابقًا؟</div><small class="muted">يقارن الصفقة المرشحة بحالات سابقة متعددة الفريمات ثم يقرأ ماذا حدث بعدها</small></div><button id="refreshAnalogs" class="primary" type="button">تحديث</button></div>
      <div id="analogSummary" class="analog-summary"><div class="muted">بانتظار صفقة مرشحة...</div></div>
      <div id="analogRates" class="analog-rates"></div>
      <div id="analogExamples" class="analog-examples"></div>
      <div id="analogValidation" class="analog-validation">بانتظار عينة Paper كافية لقياس هل الذاكرة التاريخية نفسها مفيدة خارج العينة.</div>
      <div id="analogNote" class="analog-note">Shadow evidence only · لا يؤثر على MASTER قبل اجتياز اختبار OOS مستقل.</div>`;
    host.parentNode.insertBefore(section,host.nextSibling);
  }

  const n=(x,d=2)=>x==null?'—':Number(x).toLocaleString(undefined,{maximumFractionDigits:d});
  const dt=(x)=>{if(!x)return'—';const d=new Date(Number(x)*1000);return Number.isNaN(d.getTime())?'—':d.toLocaleString('ar',{year:'numeric',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});};
  function qualityClass(q){return q==='STRONG'?'analog-good':q==='MODERATE'?'analog-warn':'';}

  function renderAnalog(a){
    const summary=document.getElementById('analogSummary'),rates=document.getElementById('analogRates'),examples=document.getElementById('analogExamples'),note=document.getElementById('analogNote');
    if(!summary||!rates||!examples)return;
    if(!a||a.status!=='READY'){
      summary.innerHTML=`<div class="analog-box" style="grid-column:1/-1"><small>Status</small><b>${a?.status||'WAITING'}</b><small>${a?.available_bars!=null?`Available bars ${a.available_bars}`:'سيبدأ التحليل عندما توجد صفقة مرشحة وتاريخ كافٍ.'}</small></div>`;
      rates.innerHTML='';examples.innerHTML='';
      if(note)note.innerHTML='🧭 لا توجد عينة تاريخية صالحة كافية لهذه الصفقة الآن. النظام لا يفترض نجاحًا بدون بيانات.';
      return;
    }
    summary.innerHTML=`
      <div class="analog-box ${qualityClass(a.quality)}"><small>Setup</small><b>${a.brain||'—'} · ${a.direction||'—'}</b><small>${a.anchor||'—'} anchor</small></div>
      <div class="analog-box"><small>Similar cases</small><b>${a.matches||0}</b><small>${a.history_bars_scanned||0} bars scanned</small></div>
      <div class="analog-box"><small>Quality</small><b>${a.quality||'—'}</b><small>${n(a.avg_similarity_pct,1)}% avg similarity</small></div>
      <div class="analog-box"><small>Stop first</small><b>${n(a.stop_before_1r_pct,1)}%</b><small>conservative path</small></div>
      <div class="analog-box"><small>Avg MFE</small><b>${n(a.avg_mfe_r,2)}R</b><small>best favorable excursion</small></div>
      <div class="analog-box"><small>Avg MAE</small><b>${n(a.avg_mae_r,2)}R</b><small>adverse excursion</small></div>`;
    rates.innerHTML=[1,2,3,4,5].map(r=>`<div class="analog-rate"><small>Reached ${r}R</small><b>${n(a[`hit_${r}r_pct`],1)}%</b></div>`).join('')+`<div class="analog-rate"><small>Risk distance</small><b>${n(a.risk_pct,2)}%</b></div>`;
    const rows=a.recent_examples||[];
    examples.innerHTML=rows.length?rows.map(x=>`<div class="analog-example"><span class="analog-date">${dt(x.time)}</span><span>Similarity <b>${n(Number(x.similarity||0)*100,1)}%</b></span><span>Max <b>${n(x.max_r,2)}R</b></span><span>${x.stopped?'SL first':'No SL first'} · ${x.regime||'—'}</span></div>`).join(''):'<div class="muted">لا توجد أمثلة قابلة للعرض.</div>';
    if(note)note.innerHTML=`📚 <b>Historical evidence الآن:</b> ${a.quality==='STRONG'||a.quality==='MODERATE'?'عينة مفيدة كسياق بحثي، لكنها ليست ضمانًا.':'العينة ضعيفة ولا تكفي للاعتماد.'} · MASTER weight = <b>${n(a.weight_in_master,1)}</b>.`;
  }

  function renderValidation(v){
    const box=document.getElementById('analogValidation');if(!box)return;
    box.className='analog-validation'+(v?.status==='USEFUL_OOS_EVIDENCE'?' useful':v?.status==='MIXED_EVIDENCE'?' mixed':'');
    if(!v||v.status==='INSUFFICIENT_DATA'){
      const need=Math.max(0,Number(v?.minimum_samples||45)-Number(v?.samples||0));
      box.innerHTML=`🧪 <b>هل البيانات السابقة مفيدة فعلًا؟ لم نثبت بعد.</b> لدينا ${v?.samples||0} صفقة صالحة، ونحتاج ${need} إضافية على الأقل لفصل Train/Test زمني.`;
      return;
    }
    const top=(v.metrics||[]).slice(0,3);
    const details=top.map(x=>`${x.metric}: OOS corr ${n(x.oos_oriented_corr,3)} · spread ${n(x.oos_quartile_spread_r,2)}R`).join(' | ');
    box.innerHTML=`🧪 <b>${v.status}</b> · Useful metrics ${v.useful_metric_count||0} · Train ${v.train_samples||0} / OOS ${v.test_samples||0}. ${details||''}<br><span class="muted">الوزن في MASTER يبقى ${n(v.weight_in_master,1)} حتى اجتياز Replay كامل وShadow confirmation.</span>`;
  }

  async function syncVersion(){
    try{const r=await fetch('/api/version'),v=await r.json();document.title=`${v.name} ${v.label}`;const el=document.querySelector('h1 span');if(el)el.textContent=v.label;}catch(e){document.title='BTC AI Trader V1.15';const el=document.querySelector('h1 span');if(el)el.textContent='V1.15';}
  }
  async function refresh(){
    const b=document.getElementById('refreshAnalogs');if(b)b.disabled=true;
    try{
      const [aRes,vRes]=await Promise.all([fetch('/api/historical-analogs'),fetch('/api/historical-validation')]);
      renderAnalog(await aRes.json());renderValidation(await vRes.json());
    }catch(e){console.warn('Historical evidence refresh failed',e);}finally{if(b)b.disabled=false;}
  }
  const b=document.getElementById('refreshAnalogs');if(b)b.addEventListener('click',refresh);
  syncVersion();refresh();setInterval(refresh,30000);setInterval(syncVersion,120000);
})();
