(() => {
  document.title = "BTC AI Trader V1.10";
  const version = document.querySelector("h1 span");
  if(version) version.textContent = "V1.10";

  const style=document.createElement("style");
  style.textContent=`
    .network-strip{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:10px}.network-box{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:10px}.network-box small{display:block;color:var(--muted);font-size:11px}.network-box b{display:block;margin-top:4px;font-size:14px}.shadow-warning{margin-top:10px;padding:9px 10px;border-radius:9px;background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.25);font-size:12px}.network-errors{margin-top:8px;font-size:11px;color:var(--muted)}
    @media(max-width:900px){.network-strip{grid-template-columns:1fr 1fr}.network-box:last-child{grid-column:1/-1}}
  `;
  document.head.appendChild(style);

  const cycle=document.getElementById("cycleSection");
  if(cycle){
    const section=document.createElement("section");
    section.id="networkSection";
    section.className="card section-context";
    section.innerHTML=`<div class="section-title-row"><div><div class="card-title">Bitcoin Network Intelligence</div><small class="muted">mempool · fees · hashrate · difficulty · network activity</small></div><button id="refreshNetwork" class="primary" type="button">تحديث</button></div><div id="networkStats" class="network-strip"><div class="muted">تحميل بيانات الشبكة...</div></div><div id="networkShadow" class="shadow-warning">Shadow Mode · Weight in MASTER = 0</div><div id="networkErrors" class="network-errors"></div>`;
    cycle.parentNode.insertBefore(section,cycle.nextSibling);
  }

  const val=(x,d=2)=>x==null?"—":num(x,d);
  function renderNetwork(net){
    const stats=document.getElementById("networkStats"),shadow=document.getElementById("networkShadow"),errors=document.getElementById("networkErrors");
    if(!stats)return;
    const mp=net?.mempool?.mempool||{}, mining=net?.mempool?.mining||{}, fees=net?.mempool?.fees||{}, cm=net?.coinmetrics?.metrics||{};
    stats.innerHTML=`
      <div class="network-box"><small>Mempool</small><b>${Number(mp.tx_count||0).toLocaleString()} tx</b><small>${val(mp.vsize_mb,1)} vMB</small></div>
      <div class="network-box"><small>Fast fee</small><b>${val(fees.fastestFee,1)} sat/vB</b><small>Hour ${val(fees.hourFee,1)}</small></div>
      <div class="network-box"><small>Hashrate Δ</small><b>${val(mining.hashrate_vs_30d_mean_pct,2)}%</b><small>vs 30d mean</small></div>
      <div class="network-box"><small>Active Addresses</small><b>${cm.AdrActCnt?.value?Number(cm.AdrActCnt.value).toLocaleString():"—"}</b><small>30d ${val(cm.AdrActCnt?.change_30d_pct,2)}%</small></div>
      <div class="network-box"><small>Transactions</small><b>${cm.TxCnt?.value?Number(cm.TxCnt.value).toLocaleString():"—"}</b><small>30d ${val(cm.TxCnt?.change_30d_pct,2)}%</small></div>`;
    const s=net?.shadow||{};
    if(shadow)shadow.innerHTML=`⚠️ <b>SHADOW ONLY</b> · Research Bias ${val(s.bias,3)} · Weight in MASTER = <b>${val(s.weight_in_master,1)}</b>. هذه البيانات تُسجّل مع النتائج أولًا ولا تغيّر الصفقة الحالية.`;
    if(errors)errors.textContent=(net?.errors||[]).length?`مصادر غير متاحة جزئيًا: ${(net.errors||[]).join(" | ")}`:"المصادر المتاحة تم تحديثها بنجاح.";
  }

  async function refresh(force=false){
    try{const r=await fetch(`/api/network${force?'?refresh=true':''}`),data=await r.json();renderNetwork(data);}catch(e){console.warn("Network intelligence failed",e);}
  }
  const btn=document.getElementById("refreshNetwork");if(btn)btn.addEventListener("click",async()=>{btn.disabled=true;await refresh(true);btn.disabled=false;});
  refresh(false);setInterval(()=>refresh(false),60000);
})();
