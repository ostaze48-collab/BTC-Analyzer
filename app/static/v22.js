(() => {
  const style=document.createElement("style");
  style.textContent=`
    .risk-strip{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-top:10px}
    .risk-box{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:10px}
    .risk-box small{display:block;color:var(--muted);font-size:11px}.risk-box b{display:block;margin-top:4px;font-size:14px}
    .risk-guard{margin-top:10px;padding:10px;border-radius:9px;border:1px solid rgba(34,197,94,.24);background:rgba(34,197,94,.07);font-size:12px}
    .risk-guard.warn{border-color:rgba(245,158,11,.3);background:rgba(245,158,11,.08)}
    .risk-guard.stop{border-color:rgba(239,68,68,.35);background:rgba(239,68,68,.08)}
    @media(max-width:900px){.risk-strip{grid-template-columns:1fr 1fr}}
  `;
  document.head.appendChild(style);

  const active=document.getElementById("activeSection");
  if(active){
    const section=document.createElement("section");
    section.id="riskSection";
    section.className="card section-active";
    section.innerHTML=`<div class="section-title-row"><div><div class="card-title">Adaptive Position & Leverage Engine</div><small class="muted">النظام يختار حجم الصفقة والرافعة والهدف حسب الأمان والـEV والتقلب · Paper فقط</small></div></div><div id="riskStats" class="risk-strip"><div class="muted">تحميل إدارة المخاطر...</div></div><div id="riskGuard" class="risk-guard">Capital protection active</div></section>`;
    active.parentNode.insertBefore(section,active.nextSibling);
  }

  const money=(x)=>x==null?'—':`$${Number(x).toLocaleString(undefined,{maximumFractionDigits:2})}`;
  const val=(x,d=2)=>x==null?'—':Number(x).toLocaleString(undefined,{maximumFractionDigits:d});

  function render(state){
    const box=document.getElementById("riskStats"),guard=document.getElementById("riskGuard");
    if(!box||!guard)return;
    const r=state?.risk_engine||{}, t=state?.active_trade||{}, st=state?.stats||{};
    const lev=t.leverage?`${t.leverage}x`:`≤ ${r.max_paper_leverage||5}x`;
    box.innerHTML=`
      <div class="risk-box"><small>Direction / Leverage</small><b>${t.direction||'AUTO'} · ${lev}</b></div>
      <div class="risk-box"><small>Position Notional</small><b>${t.notional?money(t.notional):'AUTO'}</b></div>
      <div class="risk-box"><small>Margin Used</small><b>${t.margin_used?money(t.margin_used):'AUTO'}</b></div>
      <div class="risk-box"><small>Planned Stop Risk</small><b>${t.risk_budget?money(t.risk_budget):`≤ ${val(r.max_risk_per_trade_pct,2)}%`}</b></div>
      <div class="risk-box"><small>Adaptive Target</small><b>${t.target_r?`${val(t.target_r,1)}R`:'1R → 5R'}</b></div>
      <div class="risk-box"><small>Drawdown</small><b>${val(st.drawdown_from_start_pct||0,2)}% / ${val(r.max_total_drawdown_pct||25,0)}%</b></div>`;

    const dd=Number(st.drawdown_from_start_pct||0), soft=Number(r.soft_pause_drawdown_pct||23), hard=Number(r.max_total_drawdown_pct||25);
    guard.className='risk-guard'+(dd>=hard?' stop':dd>=soft?' warn':'');
    if(dd>=hard) guard.innerHTML=`🛑 <b>HARD LOSS LIMIT</b> · لا صفقات جديدة. Kill switch عند ${val(hard,0)}% في نموذج Paper.`;
    else if(dd>=soft) guard.innerHTML=`⚠️ <b>CAPITAL PRESERVATION PAUSE</b> · توقف فتح صفقات جديدة عند ${val(soft,0)}% قبل حد ${val(hard,0)}%.`;
    else guard.innerHTML=`🛡️ الحد الصلب للخسارة = <b>${val(hard,0)}%</b> من رأس المال الابتدائي · الوقف الوقائي لصفقات جديدة عند ${val(soft,0)}% · الرافعة القصوى Paper = <b>${r.max_paper_leverage||5}x</b>.`;
    if(r.last_execution_block?.reason) guard.innerHTML += ` <span class="muted">آخر منع: ${r.last_execution_block.reason}</span>`;
  }

  async function refresh(){
    try{const res=await fetch('/api/state'),state=await res.json();render(state);}catch(e){console.warn('Risk panel refresh failed',e);}
  }
  refresh();setInterval(refresh,5000);
})();
