(() => {
  const STORE_KEY = 'btc_ai_trader_v2_stable_results';
  const SESSION_KEY = 'btc_ai_trader_v2_session_started';
  const MAX_ARCHIVE = 120;
  let lastBundle = null;
  let refreshBusy = false;

  document.body.classList.add('stable-mode');

  const n = (v, d = 0) => {
    const x = Number(v);
    return Number.isFinite(x) ? x : d;
  };
  const money = v => `$${n(v).toLocaleString(undefined, {maximumFractionDigits: 2})}`;
  const pct = v => `${n(v).toFixed(2)}%`;
  const pnlClass = v => n(v) > 0 ? 'good' : n(v) < 0 ? 'bad' : '';
  const esc = x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function loadArchive() {
    try {
      const value = JSON.parse(localStorage.getItem(STORE_KEY) || '[]');
      return Array.isArray(value) ? value : [];
    } catch (_) { return []; }
  }
  function writeArchive(rows) {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(rows.slice(-MAX_ARCHIVE))); }
    catch (e) { console.warn('Local result archive unavailable', e); }
  }
  function sessionStarted() {
    let started = localStorage.getItem(SESSION_KEY);
    if (!started) {
      started = new Date().toISOString();
      localStorage.setItem(SESSION_KEY, started);
    }
    return started;
  }
  function resetSessionClock() {
    localStorage.setItem(SESSION_KEY, new Date().toISOString());
  }

  function injectStableShell() {
    const main = document.querySelector('main');
    const overview = document.getElementById('overview');
    if (!main || !overview || document.getElementById('stableExperimentSection')) return;

    const hero = document.createElement('section');
    hero.id = 'stableExperimentSection';
    hero.className = 'card stable-shell';
    hero.innerHTML = `
      <div class="stable-head">
        <div>
          <div class="stable-title"><h2>Stable Experiment Mode</h2><div class="stable-badges"><span class="stable-badge paper">PAPER ONLY</span><span class="stable-badge locked">REAL EXECUTION LOCKED</span><span id="stableConnBadge" class="stable-badge live">CONNECTING</span></div></div>
          <p class="stable-sub">نسخة قياس ثابتة: لا نغيّر منطق العقول أثناء التجربة. نراقب النتائج، نحفظ اللقطات على الهاتف، ونقارن الأداء عبر الزمن.</p>
        </div>
        <div class="stable-actions">
          <button id="stableSaveSnapshot" class="stable-btn primary" type="button">حفظ لقطة نتائج</button>
          <button id="stableExportResults" class="stable-btn" type="button">تصدير JSON</button>
          <button id="stableResearchToggle" class="stable-btn" type="button">إظهار المختبر</button>
        </div>
      </div>
      <div class="stable-kpis">
        <div class="stable-kpi"><small>رأس المال</small><b id="stableCapital">—</b></div>
        <div class="stable-kpi"><small>صافي P/L</small><b id="stableNetPnl">—</b></div>
        <div class="stable-kpi"><small>الصفقات المغلقة</small><b id="stableTrades">0</b></div>
        <div class="stable-kpi"><small>Win Rate</small><b id="stableWinRate">0%</b></div>
        <div class="stable-kpi"><small>Profit Factor</small><b id="stablePf">0</b></div>
        <div class="stable-kpi"><small>Max Drawdown</small><b id="stableDd">0%</b></div>
      </div>`;
    main.insertBefore(hero, overview);

    const results = document.createElement('section');
    results.id = 'stableResultsSection';
    results.className = 'card stable-results-card section-results';
    results.innerHTML = `
      <div class="stable-results-head"><div><h3>نتائج التجربة</h3><p>24 ساعة · 7 أيام · 30 يوم · أداء كل عقل · أرشيف محفوظ على هذا الجهاز</p></div><small id="stableSessionAge" class="muted">—</small></div>
      <div id="stablePeriodGrid" class="stable-period-grid"></div>
      <div id="stableBrainResults" class="stable-brain-results"></div>
      <div class="stable-archive-wrap"><div class="stable-archive-title"><b>أرشيف النتائج المحلي</b><small id="stableArchiveCount">0 لقطة</small></div><div id="stableArchive" class="stable-archive"></div></div>`;
    const trades = document.getElementById('tradesSection');
    main.insertBefore(results, trades || null);

    const labToggle = document.createElement('section');
    labToggle.id = 'stableLabToggle';
    labToggle.className = 'stable-lab-toggle';
    labToggle.innerHTML = `<div><b>مختبر البحث المتقدم</b><p>Cycle / Patterns / Edge / Walk-Forward / Readiness تبقى موجودة، لكنها مخفية افتراضيًا حتى تبقى شاشة التجربة نظيفة.</p></div><button id="stableLabButton" class="stable-btn" type="button">إظهار</button>`;
    main.insertBefore(labToggle, document.querySelector('.notice'));

    const nav = document.querySelector('.mobile-nav');
    if (nav) nav.innerHTML = `<a href="#stableExperimentSection" class="stable-active"><span>⌂</span><small>الرئيسية</small></a><a href="#brainsSection"><span>◉</span><small>العقول</small></a><a href="#chartSection"><span>⌁</span><small>الشارت</small></a><a href="#stableResultsSection"><span>▥</span><small>النتائج</small></a><a href="#stableLabToggle" id="stableNavLab"><span>⚗</span><small>المختبر</small></a>`;
  }

  function tagResearchPanels() {
    const keep = new Set(['stableExperimentSection','overview','activeSection','brainsSection','marketContextSection','chartSection','stableResultsSection','tradesSection','stableLabToggle']);
    document.querySelectorAll('main > section').forEach(el => {
      if (!keep.has(el.id)) el.classList.add('stable-research-panel');
    });
  }

  function setResearchVisible(show) {
    document.body.classList.toggle('stable-show-research', !!show);
    const label = show ? 'إخفاء المختبر' : 'إظهار المختبر';
    const a = document.getElementById('stableResearchToggle'); if (a) a.textContent = label;
    const b = document.getElementById('stableLabButton'); if (b) b.textContent = show ? 'إخفاء' : 'إظهار';
  }

  function closedTrades(trades) { return (Array.isArray(trades) ? trades : []).filter(t => t.status === 'CLOSED'); }
  function periodStats(trades, hours) {
    const cutoff = Date.now() - hours * 3600000;
    const rows = closedTrades(trades).filter(t => {
      const ts = Date.parse(t.closed_at || t.opened_at || '');
      return Number.isFinite(ts) && ts >= cutoff;
    });
    const pnls = rows.map(t => n(t.realized_pnl));
    const wins = pnls.filter(x => x > 0).length;
    const gw = pnls.filter(x => x > 0).reduce((a,b)=>a+b,0);
    const gl = Math.abs(pnls.filter(x => x < 0).reduce((a,b)=>a+b,0));
    return {trades: rows.length, pnl: pnls.reduce((a,b)=>a+b,0), winRate: rows.length ? wins / rows.length * 100 : 0, pf: gl ? gw/gl : (gw ? 999 : 0)};
  }
  function brainStats(trades) {
    const groups = {};
    closedTrades(trades).forEach(t => {
      const brain = t.brain || 'UNKNOWN';
      if (!groups[brain]) groups[brain] = [];
      groups[brain].push(t);
    });
    return ['SCALP','INTRADAY','SWING'].map(brain => {
      const rows = groups[brain] || [], pnls = rows.map(t => n(t.realized_pnl));
      const rValues = rows.map(t => n(t.risk_budget) > 0 ? n(t.realized_pnl) / n(t.risk_budget) : null).filter(Number.isFinite);
      return {brain, trades: rows.length, pnl: pnls.reduce((a,b)=>a+b,0), win: rows.length ? pnls.filter(x=>x>0).length/rows.length*100 : 0, meanR: rValues.length ? rValues.reduce((a,b)=>a+b,0)/rValues.length : 0};
    });
  }

  function summaryFrom(state, trades) {
    const s = state?.stats || {};
    return {
      captured_at: new Date().toISOString(),
      version: state?.app_version || '2.0.0',
      capital: n(s.capital, 1000), net_pnl: n(s.net_pnl), trades: n(s.trades), win_rate: n(s.win_rate), profit_factor: n(s.profit_factor), max_drawdown_pct: n(s.max_drawdown_pct),
      master_action: state?.master?.action || 'WAIT', winner_brain: state?.master?.winner?.brain || null,
      active_trade: state?.active_trade ? {brain:state.active_trade.brain,direction:state.active_trade.direction,entry:state.active_trade.entry,total_live_pnl:state.active_trade.total_live_pnl} : null,
      periods: {h24: periodStats(trades,24), d7: periodStats(trades,24*7), d30: periodStats(trades,24*30)},
      brains: brainStats(trades), session_started: sessionStarted(), reason: 'AUTO'
    };
  }

  function saveSnapshot(reason='MANUAL', force=false) {
    if (!lastBundle?.state) return;
    const snap = summaryFrom(lastBundle.state, lastBundle.trades); snap.reason = reason;
    const rows = loadArchive(), prev = rows.at(-1);
    const changed = !prev || prev.trades !== snap.trades || Math.abs(n(prev.net_pnl)-snap.net_pnl) > 0.005;
    const old = prev ? Date.parse(prev.captured_at || '') : 0;
    if (!force && !changed && Date.now() - old < 30*60*1000) return;
    rows.push(snap); writeArchive(rows); renderArchive();
  }

  function renderArchive() {
    const rows = loadArchive();
    const count = document.getElementById('stableArchiveCount'); if (count) count.textContent = `${rows.length} لقطة`;
    const box = document.getElementById('stableArchive'); if (!box) return;
    box.innerHTML = rows.slice(-8).reverse().map(r => `<div class="stable-snapshot"><div class="time">${new Date(r.captured_at).toLocaleString()}</div><div class="reason">${esc(r.reason || 'SNAPSHOT')}</div><div class="pnl ${pnlClass(r.net_pnl)}">${money(r.net_pnl)}</div><div class="meta">Capital ${money(r.capital)} · ${r.trades} trades · Win ${pct(r.win_rate)} · PF ${n(r.profit_factor).toFixed(2)}</div></div>`).join('') || '<div class="muted">لم يتم حفظ أي لقطة بعد.</div>';
  }

  function renderPeriod(name, x) {
    return `<div class="stable-period"><header><b>${name}</b><span>${x.trades} صفقة</span></header><strong class="${pnlClass(x.pnl)}">${money(x.pnl)}</strong><div class="mini"><span>Win rate</span><b>${pct(x.winRate)}</b><span>Profit factor</span><b>${n(x.pf).toFixed(2)}</b></div></div>`;
  }
  function renderBundle(state, trades) {
    const s = state?.stats || {}, set = (id,val,cls='') => { const el=document.getElementById(id); if(el){el.textContent=val;el.className=cls;} };
    set('stableCapital', money(s.capital)); set('stableNetPnl', money(s.net_pnl), pnlClass(s.net_pnl)); set('stableTrades', String(n(s.trades))); set('stableWinRate', pct(s.win_rate)); set('stablePf', n(s.profit_factor).toFixed(2)); set('stableDd', pct(s.max_drawdown_pct), n(s.max_drawdown_pct)>10?'bad':'');
    const badge = document.getElementById('stableConnBadge'); if (badge){badge.textContent = state?.connected ? 'MARKET CONNECTED' : 'MARKET OFFLINE'; badge.className=`stable-badge ${state?.connected?'live':'locked'}`;}
    const periods = document.getElementById('stablePeriodGrid'); if(periods) periods.innerHTML = renderPeriod('آخر 24 ساعة', periodStats(trades,24))+renderPeriod('آخر 7 أيام',periodStats(trades,168))+renderPeriod('آخر 30 يوم',periodStats(trades,720));
    const brains = document.getElementById('stableBrainResults'); if(brains) brains.innerHTML = brainStats(trades).map(x=>`<div class="stable-brain-stat"><div class="head"><b>${x.brain}</b><span>${x.trades} صفقة</span></div><div class="values"><div><small>P/L</small><strong class="${pnlClass(x.pnl)}">${money(x.pnl)}</strong></div><div><small>Win</small><strong>${pct(x.win)}</strong></div><div><small>Mean R</small><strong>${x.meanR.toFixed(2)}R</strong></div></div></div>`).join('');
    const age = document.getElementById('stableSessionAge'); if(age){const ms=Date.now()-Date.parse(sessionStarted());const h=Math.max(0,ms/3600000);age.textContent=`مدة التجربة ${h<48?h.toFixed(1)+' ساعة':(h/24).toFixed(1)+' يوم'}`;}
    renderArchive();
  }

  async function refreshStable() {
    if (refreshBusy) return; refreshBusy = true;
    try {
      const [state, trades] = await Promise.all([fetch('/api/state').then(r=>r.json()), fetch('/api/trades?limit=200').then(r=>r.json())]);
      lastBundle = {state, trades}; renderBundle(state, trades); saveSnapshot('AUTO', false);
    } catch (e) { console.warn('Stable dashboard refresh failed', e); }
    finally { refreshBusy = false; }
  }

  function exportResults() {
    const payload = {exported_at:new Date().toISOString(), mode:'BTC_AI_TRADER_V2_STABLE_EXPERIMENT', local_archive:loadArchive(), current:lastBundle ? summaryFrom(lastBundle.state,lastBundle.trades) : null, recent_trades:lastBundle?.trades || []};
    const blob = new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}); const url=URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url; a.download=`btc-ai-results-${new Date().toISOString().slice(0,10)}.json`; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
  }

  function bindActions() {
    document.getElementById('stableSaveSnapshot')?.addEventListener('click',()=>saveSnapshot('MANUAL',true));
    document.getElementById('stableExportResults')?.addEventListener('click',exportResults);
    const toggle=()=>setResearchVisible(!document.body.classList.contains('stable-show-research'));
    document.getElementById('stableResearchToggle')?.addEventListener('click',toggle); document.getElementById('stableLabButton')?.addEventListener('click',toggle);
    document.getElementById('stableNavLab')?.addEventListener('click',e=>{e.preventDefault();setResearchVisible(true);document.getElementById('stableLabToggle')?.scrollIntoView({behavior:'smooth'});});

    document.addEventListener('click', async e => {
      const btn = e.target.closest?.('#resetBtn'); if (!btn) return;
      e.preventDefault(); e.stopImmediatePropagation();
      if (!confirm('سيتم حفظ نتيجة التجربة الحالية على هذا الهاتف ثم تصفير المحاكاة. متابعة؟')) return;
      saveSnapshot('PRE_RESET', true); btn.disabled = true;
      try {
        const r = await fetch('/api/reset',{method:'POST'}); if(!r.ok){const t=await r.text();alert(`تعذر التصفير: ${t}`);return;}
        resetSessionClock(); location.reload();
      } catch(err){alert('تعذر الاتصال بالخادم. لم يتم حذف الأرشيف المحلي.');}
      finally{btn.disabled=false;}
    }, true);
  }

  injectStableShell(); bindActions(); renderArchive(); setResearchVisible(false);
  setTimeout(tagResearchPanels, 1200); setTimeout(tagResearchPanels, 3500);
  const observer = new MutationObserver(()=>tagResearchPanels()); const main=document.querySelector('main'); if(main) observer.observe(main,{childList:true});
  refreshStable(); setInterval(refreshStable, 15000);
})();
