(() => {
  document.title = "BTC AI Trader V1.9";
  const version = document.querySelector("h1 span");
  if(version) version.textContent = "V1.9";

  const style = document.createElement("style");
  style.textContent = `
    .readiness-grid{display:grid;grid-template-columns:1fr 2fr;gap:12px;margin-top:12px}
    .readiness-score{display:flex;flex-direction:column;align-items:center;justify-content:center;background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:14px;text-align:center}
    .readiness-score strong{font-size:34px}.readiness-status{font-weight:900;margin-top:5px}.readiness-status.NOT_READY{color:var(--red)}.readiness-status.SHADOW_READY{color:var(--yellow)}.readiness-status.LIVE_CANDIDATE{color:var(--green)}
    .gate-list{display:grid;gap:7px}.gate{display:flex;justify-content:space-between;gap:10px;padding:9px 10px;background:var(--panel2);border:1px solid var(--line);border-radius:9px;font-size:12px}.gate.pass{border-color:rgba(34,197,94,.35)}.gate.fail{border-color:rgba(239,68,68,.30)}
    .validation-controls{display:flex;gap:8px;align-items:center;margin-top:12px}.validation-controls select{background:var(--panel2);color:var(--text);border:1px solid var(--line);border-radius:9px;padding:9px;min-height:44px}.validation-controls button{min-height:44px}
    .cycle-validation-summary{margin-top:10px;display:grid;grid-template-columns:repeat(4,1fr);gap:7px}
    @media(max-width:900px){.readiness-grid{grid-template-columns:1fr}.gate{align-items:flex-start}.validation-controls{width:100%}.validation-controls select,.validation-controls button{flex:1}.cycle-validation-summary{grid-template-columns:1fr 1fr}}
  `;
  document.head.appendChild(style);

  const backtest = document.getElementById("backtestSection");
  if(backtest){
    const section = document.createElement("section");
    section.id = "readinessSection";
    section.className = "card section-learning";
    section.innerHTML = `
      <div class="section-title-row"><div><div class="card-title">Real-Trade Readiness Gate</div><small class="muted">الانتقال الحقيقي لا يعتمد على الانطباع؛ يجب اجتياز جميع بوابات الدليل.</small></div></div>
      <div class="readiness-grid"><div id="readinessScore" class="readiness-score"><span class="muted">Readiness</span><strong>—</strong><div class="readiness-status NOT_READY">NOT READY</div></div><div id="readinessGates" class="gate-list"><div class="muted">تحميل الأدلة...</div></div></div>
      <div class="validation-controls"><select id="cycleYears"><option value="3">3 سنوات</option><option value="4">4 سنوات</option><option value="5">5 سنوات</option><option value="6" selected>6 سنوات</option><option value="7">7 سنوات</option><option value="8">8 سنوات</option><option value="9">9 سنوات</option></select><button id="runCycleValidation" class="primary">اختبار Cycle OOS</button></div>
      <div id="cycleValidationStatus" class="muted backtest-status">لم يتم تشغيل التحقق متعدد السنوات بعد.</div><div id="cycleValidationResult"></div>
      <div class="learning-note">حتى LIVE_CANDIDATE لا يفعّل التداول الحقيقي تلقائيًا؛ يسمح فقط بمناقشة Pilot صغير منفصل. لا يوجد ضمان ربح.</div>`;
    backtest.parentNode.insertBefore(section, backtest);
  }

  const fmtValue = (v) => {
    if(v == null) return "—";
    if(typeof v === "object") return Object.entries(v).map(([k,x])=>`${k}: ${typeof x==='number'?num(x,3):x}`).join(" · ");
    return typeof v === "number" ? num(v,3) : String(v);
  };

  function renderReadiness(report){
    const score = document.getElementById("readinessScore"), gates=document.getElementById("readinessGates");
    if(!score||!gates)return;
    const status=report?.status||"NOT_READY";
    score.innerHTML=`<span class="muted">Readiness</span><strong>${num(report?.score||0,1)}%</strong><div class="readiness-status ${status}">${status}</div><small class="muted">${report?.passed||0}/${report?.total||0} Gates</small>`;
    gates.innerHTML=(report?.hard_gates||[]).map(g=>`<div class="gate ${g.passed?'pass':'fail'}"><span>${g.passed?'✅':'⛔'} ${g.label}</span><b>${fmtValue(g.value)}</b></div>`).join("")||`<div class="muted">لا توجد بيانات كافية بعد.</div>`;
  }

  function renderCycleValidation(data){
    const box=document.getElementById("cycleValidationResult");if(!box)return;
    const p=data?.primary||{};
    box.innerHTML=`<div class="cycle-validation-summary"><div class="trade-box"><small>نوع التحقق</small><b>Holdout</b></div><div class="trade-box"><small>90d Samples</small><b>${p.samples||0}</b></div><div class="trade-box"><small>Directional Accuracy</small><b>${num(p.directional_accuracy_pct,2)}%</b></div><div class="trade-box"><small>Mean Signed Return</small><b>${num((p.mean_signed_return||0)*100,3)}%</b></div></div>`;
  }

  async function refreshReadiness(){
    try{
      const r=await fetch("/api/readiness"),data=await r.json();
      renderReadiness(data);
      if(data.cycle_validation){renderCycleValidation(data.cycle_validation);const s=document.getElementById("cycleValidationStatus");if(s)s.textContent=`آخر تحقق: ${data.cycle_validation.years_requested} سنوات · ${data.cycle_validation.validation_type}`;}
    }catch(e){console.warn("Readiness refresh failed",e);}
  }

  const run=document.getElementById("runCycleValidation");
  if(run) run.addEventListener("click",async()=>{
    const years=document.getElementById("cycleYears")?.value||6,status=document.getElementById("cycleValidationStatus");
    run.disabled=true;if(status)status.textContent=`جاري التحقق الزمني لـ ${years} سنوات...`;
    try{
      const r=await fetch(`/api/cycle-validation?years=${years}`,{method:"POST"}),data=await r.json();
      if(!r.ok)throw new Error(data.detail||"Cycle validation failed");
      renderCycleValidation(data);if(status)status.textContent=`اكتمل · Holdout زمني بدون إعادة ضبط المعادلات على المستقبل.`;await refreshReadiness();
    }catch(e){if(status)status.textContent=`خطأ: ${e.message}`;}finally{run.disabled=false;}
  });

  const backtestBtn=document.getElementById("runBacktest");
  if(backtestBtn)backtestBtn.addEventListener("click",()=>setTimeout(refreshReadiness,5000));
  refreshReadiness();
  setInterval(refreshReadiness,30000);
})();
