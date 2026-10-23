(() => {
  const style=document.createElement('style');
  style.textContent=`
    .analog-validation{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:10px}.av-box{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:10px}.av-box small{display:block;color:var(--muted);font-size:11px}.av-box b{display:block;margin-top:4px;font-size:14px}.av-list{display:grid;gap:7px;margin-top:10px}.av-row{padding:9px 10px;border:1px solid var(--line);background:var(--panel2);border-radius:9px;font-size:12px}.av-good{border-color:rgba(34,197,94,.35)!important}.av-warn{border-color:rgba(245,158,11,.32)!important}.av-note{margin-top:10px;padding:10px;border-radius:9px;background:rgba(96,165,250,.07);border:1px solid rgba(96,165,250,.24);font-size:12px}
    @media(max-width:900px){.analog-validation{grid-template-columns:1fr 1fr}.analog-validation .av-box:last-child{grid-column:1/-1}}
  `;
  document.head.appendChild(style);

  const analog=document.getElementById('historicalAnalogSection');
  const host=analog||document.getElementById('learningSection');
  if(host){
    const section=document.createElement('section');
    section.id='analogValidationSection';
    section.className='card section-learning';
    section.innerHTML=`
      <div class="section-title-row"><div><div class="card-title">Analog Edge Validation · هل السوابق مفيدة؟</div><small class="muted">يقيس Historical Memory نفسها داخل Train/Test وIncremental Walk-Forward</small></div><button id="refreshAnalogValidation" class="primary" type="button">تحديث</button></div>
      <div id="analogValidationSummary" class="analog-validation"><div class="muted">بانتظار عينة صفقات مغلقة...</div></div>
      <div id="analogValidationList" class="av-list"></div>
      <div id="analogValidationNote" class="av-note">النتيجة لا تغيّر MASTER تلقائيًا.</div>`;
    host.parentNode.insertBefore(section,host.nextSibling);
  }

  const n=(x,d=2)=>x==null?'—':Number(x).toLocaleString(undefined,{maximumFractionDigits:d});
  function label(status){
    if(status==='INCREMENTAL_EDGE_DETECTED')return'✅ Edge إضافي ظهر';
    if(status==='CORRELATION_ONLY')return'⚠️ ارتباط فقط';
    if(status==='NO_PROVEN_EDGE')return'⛔ لم يثبت Edge';
    return'⏳ بيانات غير كافية';
  }
  function render(r){
    const s=document.getElementById('analogValidationSummary'),list=document.getElementById('analogValidationList'),note=document.getElementById('analogValidationNote');
    if(!s||!list)return;
    const good=r.status==='INCREMENTAL_EDGE_DETECTED';
    s.innerHTML=`
      <div class="av-box ${good?'av-good':r.status==='CORRELATION_ONLY'?'av-warn':''}"><small>الحكم الحالي</small><b>${label(r.status)}</b></div>
      <div class="av-box"><small>Closed samples</small><b>${r.samples||0}</b></div>
      <div class="av-box"><small>Edge candidates</small><b>${(r.edge_candidates||[]).length}</b></div>
      <div class="av-box"><small>Incremental candidates</small><b>${(r.incremental_candidates||[]).length}</b></div>`;
    const rows=[...(r.incremental_candidates||[]).map(x=>({...x,stage:'WALK-FORWARD'})),...(r.edge_candidates||[]).map(x=>({...x,stage:'OOS CORRELATION'}))].slice(0,8);
    list.innerHTML=rows.length?rows.map(x=>`<div class="av-row ${x.stage==='WALK-FORWARD'?'av-good':'av-warn'}"><b>${x.feature||'analog feature'}</b> · ${x.stage}<br><span class="muted">${x.mean_delta_r!=null?`ΔR ${n(x.mean_delta_r,3)} · pass ${n(x.positive_fold_pct,0)}% folds`:`OOS corr ${n(x.test_corr,3)} · spread ${n(x.oos_quartile_spread_r,2)}R`}</span></div>`).join(''):`<div class="muted">لا يوجد دليل كافٍ حتى الآن أن ذاكرة السوابق تضيف Edge مستقلًا.</div>`;
    if(note)note.innerHTML=`🧪 <b>Historical Memory → MASTER weight = ${n(r.master_weight,1)}</b> · ${r.policy||''}`;
  }
  async function refresh(){const b=document.getElementById('refreshAnalogValidation');if(b)b.disabled=true;try{const res=await fetch('/api/analog-validation'),r=await res.json();render(r);}catch(e){console.warn('Analog validation failed',e);}finally{if(b)b.disabled=false;}}
  const b=document.getElementById('refreshAnalogValidation');if(b)b.addEventListener('click',refresh);
  refresh();setInterval(refresh,60000);
  fetch('/api/version').then(r=>r.json()).then(v=>{document.title=`${v.name} ${v.label}`;const el=document.querySelector('h1 span');if(el)el.textContent=v.label;}).catch(()=>{});
})();
