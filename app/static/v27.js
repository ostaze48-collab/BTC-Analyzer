(() => {
  const style=document.createElement('style');
  style.textContent=`
    .archive-brains{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:10px}.archive-card{background:var(--panel2);border:1px solid var(--line);border-radius:11px;padding:11px}.archive-card.ready{border-color:rgba(34,197,94,.32)}.archive-card.loading{border-color:rgba(59,130,246,.32)}.archive-card.partial{border-color:rgba(245,158,11,.32)}.archive-title{display:flex;justify-content:space-between;gap:8px;align-items:center}.archive-title b{font-size:14px}.archive-status{font-size:10px;padding:3px 7px;border-radius:999px;border:1px solid var(--line);color:var(--muted)}.archive-metrics{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:9px}.archive-metric{padding:7px;border-radius:8px;background:rgba(255,255,255,.025)}.archive-metric small{display:block;color:var(--muted);font-size:10px}.archive-metric b{font-size:13px}.archive-coverage{display:flex;gap:6px;overflow-x:auto;margin-top:8px;padding-bottom:3px}.archive-chip{min-width:92px;padding:7px;border:1px solid var(--line);border-radius:8px;font-size:10px}.archive-chip b,.archive-chip span{display:block}.archive-chip span{color:var(--muted);margin-top:2px}.archive-note{margin-top:10px;padding:10px;border-radius:9px;background:rgba(139,92,246,.07);border:1px solid rgba(139,92,246,.24);font-size:12px}
    @media(max-width:900px){.archive-brains{grid-template-columns:1fr}.archive-card{padding:10px}.archive-coverage{scroll-snap-type:x proximity}.archive-chip{scroll-snap-align:start}}
  `;
  document.head.appendChild(style);

  const analog=document.getElementById('historicalAnalogSection');
  const host=analog||document.getElementById('marketContextSection')||document.getElementById('learningSection');
  if(host){
    const section=document.createElement('section');
    section.id='historicalArchiveSection';section.className='card section-context';
    section.innerHTML=`
      <div class="section-title-row"><div><div class="card-title">Long Historical Replay Memory · الذاكرة التاريخية الطويلة</div><small class="muted">تحميل Lazy حسب العقل المرشح · لا يوقف السوق ولا يغيّر MASTER مباشرة</small></div><button id="refreshArchive" class="primary" type="button">تحديث</button></div>
      <div id="archiveBrains" class="archive-brains"><div class="muted">بانتظار حالة الذاكرة...</div></div>
      <div id="archiveNote" class="archive-note">الذاكرة الطويلة توسّع عينة Historical Analog فقط. Weight in MASTER = 0 حتى التحقق خارج العينة.</div>`;
    host.parentNode.insertBefore(section,host.nextSibling);
  }

  const fmtDate=(unix)=>{if(!unix)return'—';const d=new Date(Number(unix)*1000);return Number.isNaN(d.getTime())?'—':d.toLocaleDateString('ar',{year:'numeric',month:'short',day:'numeric'});};
  function cls(status){return status==='READY'?'ready':status==='LOADING'?'loading':status==='PARTIAL'?'partial':'';}
  function renderBrain(name,s){
    s=s||{};const cov=s.coverage||{};const entries=Object.entries(cov);
    const chips=entries.length?entries.map(([tf,c])=>`<div class="archive-chip"><b>${tf} · ${Number(c.bars||0).toLocaleString()} bars</b><span>هدف ${Number(c.target_days||0).toLocaleString()} يوم</span><span>${c.first_time?fmtDate(c.first_time):'—'} → ${c.last_time?fmtDate(c.last_time):'—'}</span></div>`).join(''):`<div class="muted">سيُحمّل عند ترشيح هذا العقل.</div>`;
    return `<article class="archive-card ${cls(s.status)}"><div class="archive-title"><b>${name}</b><span class="archive-status">${s.status||'NOT_LOADED'}</span></div><div class="archive-metrics"><div class="archive-metric"><small>Bars loaded</small><b>${Number(s.bars_loaded||0).toLocaleString()}</b></div><div class="archive-metric"><small>Timeframes</small><b>${s.loaded_timeframes||0}</b></div></div><div class="archive-coverage">${chips}</div>${(s.errors||[]).length?`<div class="muted" style="margin-top:7px">${(s.errors||[]).join(' | ')}</div>`:''}</article>`;
  }
  function render(data){
    const box=document.getElementById('archiveBrains'),note=document.getElementById('archiveNote');if(!box)return;
    const brains=data?.brains||{};box.innerHTML=['SCALP','INTRADAY','SWING'].map(b=>renderBrain(b,brains[b])).join('');
    const cur=data?.current||{};
    if(note)note.innerHTML=`🧠 Current memory: <b>${cur.brain||'—'} · ${cur.status||'IDLE'}</b> · ${Number(cur.bars_loaded||0).toLocaleString()} bars · Mode <b>${data?.mode||'LAZY_SHADOW_ONLY'}</b> · MASTER weight = <b>${data?.weight_in_master??0}</b>.`;
  }
  async function refresh(){const b=document.getElementById('refreshArchive');if(b)b.disabled=true;try{const r=await fetch('/api/historical-archive'),d=await r.json();render(d);}catch(e){console.warn('Historical archive failed',e);}finally{if(b)b.disabled=false;}}
  const b=document.getElementById('refreshArchive');if(b)b.addEventListener('click',refresh);
  refresh();setInterval(refresh,15000);
  fetch('/api/version').then(r=>r.json()).then(v=>{document.title=`${v.name} ${v.label}`;const el=document.querySelector('h1 span');if(el)el.textContent=v.label;}).catch(()=>{});
})();
