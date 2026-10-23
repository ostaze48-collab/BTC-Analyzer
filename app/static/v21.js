(() => {
  document.title = "BTC AI Trader V1.11";
  const version = document.querySelector("h1 span");
  if(version) version.textContent = "V1.11";

  const style=document.createElement("style");
  style.textContent=`
    .deriv-strip{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-top:10px}
    .deriv-box{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:10px}
    .deriv-box small{display:block;color:var(--muted);font-size:11px}.deriv-box b{display:block;margin-top:4px;font-size:14px}
    .deriv-warning{margin-top:10px;padding:9px 10px;border-radius:9px;background:rgba(59,130,246,.08);border:1px solid rgba(59,130,246,.24);font-size:12px}
    .deriv-errors{margin-top:8px;font-size:11px;color:var(--muted)}
    @media(max-width:900px){.deriv-strip{grid-template-columns:1fr 1fr}.deriv-box:last-child:nth-child(odd){grid-column:1/-1}}
  `;
  document.head.appendChild(style);

  const network=document.getElementById("networkSection") || document.getElementById("cycleSection");
  if(network){
    const section=document.createElement("section");
    section.id="derivativesSection";
    section.className="card section-context";
    section.innerHTML=`<div class="section-title-row"><div><div class="card-title">BTC Derivatives Intelligence</div><small class="muted">Funding · Basis · Open Interest · Positioning · Taker Flow</small></div><button id="refreshDerivatives" class="primary" type="button">تحديث</button></div><div id="derivativesStats" class="deriv-strip"><div class="muted">تحميل بيانات المشتقات...</div></div><div id="derivativesShadow" class="deriv-warning">Shadow Mode · Weight in MASTER = 0</div><div id="derivativesErrors" class="deriv-errors"></div>`;
    network.parentNode.insertBefore(section,network.nextSibling);
  }

  const val=(x,d=3)=>x==null?"—":num(x,d);
  const pctFunding=(x)=>x==null?"—":`${num(Number(x)*100,4)}%`;
  function renderDerivatives(d){
    const stats=document.getElementById("derivativesStats"),shadow=document.getElementById("derivativesShadow"),errors=document.getElementById("derivativesErrors");
    if(!stats)return;
    const p=d?.premium||{}, oi=d?.open_interest||{}, pos=d?.positioning||{}, flow=d?.flow||{};
    stats.innerHTML=`
      <div class="deriv-box"><small>Funding</small><b>${pctFunding(p.current_funding_rate)}</b><small>avg ${pctFunding(p.avg_recent_funding_rate)}</small></div>
      <div class="deriv-box"><small>Basis</small><b>${val(p.basis_bps,2)} bps</b><small>Mark vs Index</small></div>
      <div class="deriv-box"><small>Open Interest</small><b>${oi.current==null?"—":Number(oi.current).toLocaleString()}</b><small>Δ ${val(oi.history_change_pct,2)}%</small></div>
      <div class="deriv-box"><small>Global L/S</small><b>${val(pos.global_long_short_ratio,3)}</b><small>Top Acct ${val(pos.top_account_long_short_ratio,3)}</small></div>
      <div class="deriv-box"><small>Top Position L/S</small><b>${val(pos.top_position_long_short_ratio,3)}</b><small>crowding context</small></div>
      <div class="deriv-box"><small>Taker Buy/Sell</small><b>${val(flow.taker_buy_sell_ratio,3)}</b><small>&gt;1 buy pressure</small></div>`;
    const s=d?.shadow||{};
    if(shadow)shadow.innerHTML=`🧪 <b>SHADOW ONLY</b> · Research Bias ${val(s.bias,3)} · Weight in MASTER = <b>${val(s.weight_in_master,1)}</b>. تُحفظ مع نتائج الصفقة، لكنها لا تغيّر قرار الدخول أو الثقة قبل إثبات Incremental OOS Edge.`;
    if(errors)errors.textContent=(d?.errors||[]).length?`مصادر غير متاحة جزئيًا: ${(d.errors||[]).join(" | ")}`:"مصادر المشتقات المتاحة تم تحديثها بنجاح.";
  }

  async function refresh(force=false){
    try{const r=await fetch(`/api/derivatives${force?'?refresh=true':''}`),data=await r.json();renderDerivatives(data);}catch(e){console.warn("Derivatives intelligence failed",e);}
  }
  const btn=document.getElementById("refreshDerivatives");if(btn)btn.addEventListener("click",async()=>{btn.disabled=true;await refresh(true);btn.disabled=false;});
  refresh(false);setInterval(()=>refresh(false),60000);

  const next=document.createElement('script');
  next.src='/static/v22.js';
  next.defer=true;
  document.body.appendChild(next);
})();
