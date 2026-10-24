(() => {
  const LOCAL_KEY = 'btc_ai_trader_v2_stable_results';
  const VIEW_KEY = 'btc_ai_trader_v2_view';
  const MAX_LOCAL = 80;
  let bundle = null;
  let serverArchive = {archive:{ready:false,backend:'unknown',persistent_across_redeploys:false},runs:[]};
  let busy = false;

  document.body.classList.add('stable-mode');
  const n=(v,d=0)=>Number.isFinite(Number(v))?Number(v):d;
  const money=v=>`$${n(v).toLocaleString(undefined,{maximumFractionDigits:2})}`;
  const pct=v=>`${n(v).toFixed(2)}%`;
  const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const cls=v=>n(v)>0?'good':n(v)<0?'bad':'';

  function localRows(){try{const x=JSON.parse(localStorage.getItem(LOCAL_KEY)||'[]');return Array.isArray(x)?x:[];}catch(_){return[];}}
  function saveLocal(x){const rows=localRows();rows.push(x);try{localStorage.setItem(LOCAL_KEY,JSON.stringify(rows.slice(-MAX_LOCAL)));}catch(_){}}
  function toast(msg,type=''){let el=document.getElementById('stableToast');if(!el){el=document.createElement('div');el.id='stableToast';el.className='stable-toast';document.body.appendChild(el);}el.textContent=msg;el.className=`stable-toast ${type} show`;setTimeout(()=>el.classList.remove('show'),2600);}

  function injectShell(){
    const main=document.querySelector('main'),overview=document.getElementById('overview');
    if(!main||!overview||document.getElementById('stableExperimentSection'))return;
    const hero=document.createElement('section');hero.id='stableExperimentSection';hero.className='card stable-shell';hero.innerHTML=`
      <div class="stable-head"><div><div class="stable-title"><h2>Stable Experiment</h2><div class="stable-badges"><span class="stable-badge paper">PAPER ONLY</span><span class="stable-badge locked">REAL EXECUTION LOCKED</span><span id="stableStoreBadge" class="stable-badge">STORAGE CHECK</span></div></div><p class="stable-sub">نسخة ثابتة للقياس: نجمع النتائج بدون تغيير منطق التداول أثناء التجربة، ونحفظ كل تجربة للمقارنة.</p></div>
      <div class="stable-actions"><button id="stableSave" class="stable-btn primary">حفظ النتائج</button><button id="stableNew" class="stable-btn">تجربة جديدة</button><button id="stableExport" class="stable-btn">تصدير JSON</button></div></div>
      <div class="stable-kpis"><div class="stable-kpi"><small>رأس المال</small><b id="stableCapital">—</b></div><div class="stable-kpi"><small>صافي P/L</small><b id="stableNetPnl">—</b></div><div class="stable-kpi"><small>الصفقات</small><b id="stableTrades">0</b></div><div class="stable-kpi"><small>Win Rate</small><b id="stableWin">0%</b></div><div class="stable-kpi"><small>Profit Factor</small><b id="stablePf">0</b></div><div class="stable-kpi"><small>Max Drawdown</small><b id="stableDd">0%</b></div></div>`;
    main.insertBefore(hero,overview);

    const results=document.createElement('section');results.id='stableResultsSection';results.className='card stable-results-card';results.innerHTML=`
      <div class="stable-results-head"><div><h3>نتائج التجربة</h3><p>Equity Curve · الأداء حسب العقل · سجل التجارب المحفوظة</p></div><div id="stableStorageText" class="stable-storage"></div></div>
      <div class="stable-results-grid"><div class="stable-panel"><div class="stable-panel-title"><b>منحنى رأس المال</b><small id="stableDuration">—</small></div><div id="stableEquity" class="stable-equity"></div></div><div class="stable-panel"><div class="stable-panel-title"><b>أداء العقول</b><small>SCALP / INTRADAY / SWING</small></div><div id="stableBreakdown" class="stable-breakdown"></div></div></div>
      <div class="stable-archive-wrap"><div class="stable-archive-title"><b>التجارب السابقة</b><small id="stableArchiveCount">0 تجربة</small></div><div id="stableArchives" class="stable-archives"></div></div>`;
    const trades=document.getElementById('tradesSection');main.insertBefore(results,trades||null);

    const tabs=document.createElement('div');tabs.className='stable-tabs-wrap';tabs.innerHTML=`<div class="stable-tabs"><button class="stable-tab" data-view="home">الرئيسية<small>قرار وأداء حي</small></button><button class="stable-tab" data-view="chart">الشارت<small>تحليل ورسم</small></button><button class="stable-tab" data-view="results">النتائج<small>قياس ومقارنة</small></button><button class="stable-tab" data-view="research">البحث<small>الأدلة المتقدمة</small></button></div>`;document.querySelector('.app-header')?.after(tabs);
    const nav=document.querySelector('.mobile-nav');if(nav)nav.innerHTML=`<button data-view="home"><span>⌂</span><small>الرئيسية</small></button><button data-view="chart"><span>⌁</span><small>الشارت</small></button><button data-view="results"><span>▥</span><small>النتائج</small></button><button data-view="research"><span>⚗</span><small>البحث</small></button>`;
  }

  const groups={home:new Set(['stableExperimentSection','overview','activeSection','brainsSection','marketContextSection']),chart:new Set(['chartSection','patternsSection']),results:new Set(['stableResultsSection','tradesSection','learningSection','backtestSection'])};
  function classify(){document.querySelectorAll('main > section').forEach(s=>{s.dataset.stableView=[...Object.entries(groups)].find(([,ids])=>ids.has(s.id))?.[0]||'research';});}
  function setView(view){view=['home','chart','results','research'].includes(view)?view:'home';classify();document.querySelectorAll('main > section').forEach(s=>s.classList.toggle('stable-hidden',s.dataset.stableView!==view));document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===view));localStorage.setItem(VIEW_KEY,view);window.scrollTo({top:0,behavior:'smooth'});if(view==='chart')setTimeout(()=>window.dispatchEvent(new Event('resize')),80);if(view==='results')refresh();}

  function lineSvg(points){
    if(!points||points.length<2)return'<div class="stable-equity-empty">لا توجد صفقات مغلقة بعد.</div>';
    const vals=points.map(p=>n(p.equity)),min=Math.min(...vals),max=Math.max(...vals),range=Math.max(.01,max-min),w=800,h=220,pad=14;
    const coords=points.map((p,i)=>{const x=pad+(i/(points.length-1))*(w-pad*2),y=pad+(1-(n(p.equity)-min)/range)*(h-pad*2);return`${x.toFixed(1)},${y.toFixed(1)}`}).join(' ');
    const end=vals.at(-1),start=vals[0],positive=end>=start;
    return`<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="Equity curve"><defs><linearGradient id="stableFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${positive?'#34d399':'#fb7185'}" stop-opacity=".22"/><stop offset="1" stop-color="#38bdf8" stop-opacity=".01"/></linearGradient></defs><polyline points="${coords}" fill="none" stroke="${positive?'#34d399':'#fb7185'}" stroke-width="3" vector-effect="non-scaling-stroke"/><polygon points="${pad},${h-pad} ${coords} ${w-pad},${h-pad}" fill="url(#stableFill)"/></svg><span class="stable-equity-label start">Start ${money(start)}</span><span class="stable-equity-label end">Now ${money(end)}</span>`;
  }

  function breakdown(rows){return(rows||[]).map(x=>`<div class="stable-breakdown-row"><b>${esc(x.name)}</b><span>${n(x.trades)} trades</span><span class="${cls(x.net_pnl)}">${money(x.net_pnl)}</span><span>Win ${pct(x.win_rate)}</span><span>${n(x.avg_r).toFixed(2)}R</span></div>`).join('')||'<div class="stable-empty">لا توجد عينة كافية بعد.</div>';}
  function renderCurrent(cur){const m=cur?.metrics||{},set=(id,val,c='')=>{const e=document.getElementById(id);if(e){e.textContent=val;e.className=c;}};set('stableCapital',money(m.capital));set('stableNetPnl',money(m.net_pnl),cls(m.net_pnl));set('stableTrades',String(n(m.trades)));set('stableWin',pct(m.win_rate));set('stablePf',n(m.profit_factor).toFixed(2));set('stableDd',pct(m.max_drawdown_pct),n(m.max_drawdown_pct)>10?'bad':'');const eq=document.getElementById('stableEquity');if(eq)eq.innerHTML=lineSvg(cur?.equity_curve||[]);const bd=document.getElementById('stableBreakdown');if(bd)bd.innerHTML=breakdown(cur?.by_brain);const d=document.getElementById('stableDuration');if(d)d.textContent=n(cur?.duration_hours)<48?`${n(cur?.duration_hours).toFixed(1)} ساعة`:`${(n(cur?.duration_hours)/24).toFixed(1)} يوم`;}

  function renderArchives(){
    const runs=serverArchive?.runs||[],local=localRows();const count=document.getElementById('stableArchiveCount');if(count)count.textContent=`${runs.length} تجربة خادمية · ${local.length} نسخة محلية`;
    const box=document.getElementById('stableArchives');if(!box)return;
    box.innerHTML=runs.slice(0,12).map(r=>{const m=r.metrics||{};return`<details class="stable-archive"><summary><b>${esc(r.label||'Experiment')}</b><span class="${cls(m.net_pnl)}">${money(m.net_pnl)}</span><span>${n(m.trades)} trades</span><span>Win ${pct(m.win_rate)}</span><span>DD ${pct(m.max_drawdown_pct)}</span></summary><div class="stable-archive-body"><div class="stable-archive-meta">${new Date(r.created_at).toLocaleString()} · ${esc(r.app_version||'')}</div>${breakdown(r.by_brain)}</div></details>`}).join('')||'<div class="stable-empty">لم تحفظ تجربة على الخادم بعد. ستظهر هنا بعد الضغط على «حفظ النتائج» أو بدء تجربة جديدة.</div>';
    const info=serverArchive?.archive||{};const text=document.getElementById('stableStorageText');const badge=document.getElementById('stableStoreBadge');if(text)text.innerHTML=`<span class="stable-storage-pill ${info.ready?'ok':'warn'}">${info.ready?'Archive Ready':'Archive Offline'}</span><span>${info.backend==='postgres'?'Postgres':'Local SQLite'} · ${info.persistent_across_redeploys?'دائم عبر إعادة النشر':'مؤقت على الخادم'}</span>`;if(badge){badge.textContent=info.ready?(info.persistent_across_redeploys?'PERSISTENT RESULTS':'LOCAL RESULTS'):'STORAGE OFFLINE';badge.className=`stable-badge ${info.ready?'live':'locked'}`;}
  }

  function localBackup(reason){const c=bundle?.current;if(!c)return;saveLocal({captured_at:new Date().toISOString(),reason,metrics:c.metrics,by_brain:c.by_brain,equity_curve:c.equity_curve});}
  async function refresh(){if(busy)return;busy=true;try{const [state,trades,current,archives]=await Promise.all([fetch('/api/state').then(r=>r.json()),fetch('/api/trades?limit=200').then(r=>r.json()),fetch('/api/experiment/current').then(r=>r.json()),fetch('/api/experiments?limit=20').then(r=>r.json())]);bundle={state,trades,current};serverArchive=archives;renderCurrent(current);renderArchives();}catch(e){console.warn('Stable refresh failed',e);toast('تعذر تحديث لوحة النتائج','bad');}finally{busy=false;}}

  async function saveServer(){const label=prompt('اسم التجربة المحفوظة:','BTC Paper Experiment');if(label===null)return;localBackup('MANUAL_BACKUP');try{const r=await fetch(`/api/experiment/archive?label=${encodeURIComponent(label||'BTC Paper Experiment')}`,{method:'POST'});if(!r.ok)throw new Error(await r.text());toast('تم حفظ نتائج التجربة','good');await refresh();}catch(e){toast('تعذر الحفظ على الخادم؛ بقيت نسخة محلية','bad');}}
  async function newExperiment(){if(!confirm('سيتم حفظ التجربة الحالية ثم تصفير Paper Trading وبدء تجربة جديدة. المتابعة؟'))return;localBackup('PRE_RESET');const label=`Experiment ${new Date().toLocaleDateString()}`;try{const r=await fetch(`/api/experiment/new?label=${encodeURIComponent(label)}`,{method:'POST'});if(!r.ok)throw new Error(await r.text());toast('تم حفظ التجربة وبدء تجربة جديدة','good');setTimeout(()=>location.reload(),500);}catch(e){toast('تعذر بدء تجربة جديدة. لم نحذف النسخة المحلية.','bad');}}
  function exportJson(){const payload={exported_at:new Date().toISOString(),mode:'BTC_AI_TRADER_V2_STABLE',current:bundle?.current||null,server_archive:serverArchive,local_backup:localRows(),recent_trades:bundle?.trades||[]};const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`btc-ai-results-${new Date().toISOString().slice(0,10)}.json`;document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);}

  function bind(){document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>setView(b.dataset.view)));document.getElementById('stableSave')?.addEventListener('click',saveServer);document.getElementById('stableNew')?.addEventListener('click',newExperiment);document.getElementById('stableExport')?.addEventListener('click',exportJson);
    const old=document.getElementById('resetBtn');if(old){const clone=old.cloneNode(true);clone.textContent='حفظ وبدء تجربة جديدة';old.replaceWith(clone);clone.addEventListener('click',e=>{e.preventDefault();newExperiment();});}}

  injectShell();classify();bind();setView(localStorage.getItem(VIEW_KEY)||'home');
  const main=document.querySelector('main');if(main)new MutationObserver(()=>{classify();const view=localStorage.getItem(VIEW_KEY)||'home';document.querySelectorAll('main > section').forEach(s=>s.classList.toggle('stable-hidden',s.dataset.stableView!==view));}).observe(main,{childList:true});
  refresh();setInterval(refresh,20000);
})();
