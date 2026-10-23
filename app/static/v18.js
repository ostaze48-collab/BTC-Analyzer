(() => {
  const EXT_TFS = ["1M","3M","6M","1y"];
  const EXT_LABELS = {"1M":"شهري","3M":"3 أشهر","6M":"6 أشهر","1y":"سنوي"};

  function renderExtendedTimeframes(state){
    const box = document.getElementById("marketContext");
    if(!box) return;
    box.querySelectorAll("[data-v18-ext]").forEach(x=>x.remove());
    const snaps = state?.snapshots || {};
    for(const key of EXT_TFS){
      const s = snaps[key];
      const el = document.createElement("div");
      el.className = "context-item";
      el.dataset.v18Ext = "1";
      if(!s){
        el.innerHTML = `<b>${EXT_LABELS[key]}</b><span>بانتظار البيانات</span>`;
      }else{
        const cls=s.trend==="BULLISH"?"good":s.trend==="BEARISH"?"bad":"neutral";
        const summary=s.feature_summary||{};
        el.innerHTML = `<div class="context-head"><b>${EXT_LABELS[key]}</b><span class="${cls}">${trendLabel(s.trend)}</span></div>
          <div class="context-line"><span>الهيكل</span><b>${structureLabel(s.structure)}</b></div>
          <div class="context-line"><span>RSI</span><b>${num(s.rsi14,1)}</b></div>
          <div class="context-line"><span>التقلب</span><b>${num(s.volatility_pct,2)}%</b></div>
          <div class="context-line"><span>Feature Bias</span><b>${num(summary.bias,3)}</b></div>
          <div class="context-line"><span>العينة</span><b>${s.sample_count||0} شمعة</b></div>`;
      }
      box.appendChild(el);
    }
  }

  function modelCard(name, title, model){
    if(!model) return `<div class="context-item"><b>${title}</b><span>غير متاح بعد</span></div>`;
    let rows="";
    if(model.fair_price!=null) rows += `<div class="context-line"><span>Fair</span><b>${money(model.fair_price)}</b></div>`;
    if(model.deviation_pct!=null) rows += `<div class="context-line"><span>Deviation</span><b>${num(model.deviation_pct,1)}%</b></div>`;
    if(model.value!=null) rows += `<div class="context-line"><span>Value</span><b>${num(model.value,3)}</b></div>`;
    if(model.multiple!=null) rows += `<div class="context-line"><span>Multiple</span><b>${num(model.multiple,3)}</b></div>`;
    if(model.ratio!=null) rows += `<div class="context-line"><span>Ratio</span><b>${num(model.ratio,3)}</b></div>`;
    if(model.crossed!=null) rows += `<div class="context-line"><span>Top Cross</span><b>${model.crossed?"⚠️ نعم":"لا"}</b></div>`;
    const bias=Number(model.bias||0),cls=bias>0.05?"good":bias<-0.05?"bad":"neutral";
    return `<div class="context-item"><div class="context-head"><b>${title}</b><span class="${cls}">Bias ${num(bias,3)}</span></div>${rows}</div>`;
  }

  function renderCycle(state){
    const box=document.getElementById("cycleModels");
    if(!box)return;
    const cycle=state?.cycle_models||{};
    const models=cycle.models||{};
    box.innerHTML = [
      modelCard("power_law","Power Law",models.power_law),
      modelCard("hpr","HPR / Rainbow",models.hpr_rainbow),
      modelCard("mayer","Mayer Multiple",models.mayer_multiple),
      modelCard("pi","Pi Cycle Top",models.pi_cycle_top),
      modelCard("4y","4-Year SMA",models.four_year_sma),
    ].join("");
    const fe=document.getElementById("featureEngine"), info=state?.feature_engine||{};
    if(fe) fe.innerHTML = `Feature Factory بالخلفية: <b>${Number(info.total_background_features||0).toLocaleString()}</b> خاصية رقمية عبر الفريمات. لا تُعامل كأصوات مستقلة؛ تُجمع بعائلات وتخضع لاحقًا لاختيار Walk-Forward لمنع التضخم والـoverfitting.`;
  }

  const originalRenderState = renderState;
  renderState = function(state){
    originalRenderState(state);
    renderExtendedTimeframes(state);
    renderCycle(state);
  };
})();
