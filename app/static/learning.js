// V1.6 learning journal UI. This visualizes paper-trading evidence only.
const REGIME_AR={
  TREND_UP:"اتجاه صاعد",TREND_DOWN:"اتجاه هابط",
  PULLBACK_UPTREND:"تصحيح داخل اتجاه صاعد",PULLBACK_DOWNTREND:"تصحيح داخل اتجاه هابط",
  BREAKOUT_UP:"اختراق صاعد",BREAKOUT_DOWN:"اختراق هابط",
  RANGE:"نطاق عرضي",TRANSITION:"مرحلة انتقال",BOOTING:"تحميل",UNKNOWN:"غير معروف"
};
const VOL_AR={HIGH:"مرتفع",NORMAL:"طبيعي",LOW:"منخفض"};
let learningSig="";

function regimeClass(direction){return direction==="BULLISH"?"good":direction==="BEARISH"?"bad":"neutral";}
function renderLearning(state){
  const current=document.getElementById("currentRegime");
  const stats=document.getElementById("learningStats");
  const matrix=document.getElementById("learningMatrix");
  const excursion=document.getElementById("excursionBox");
  if(!current||!stats||!matrix)return;
  const regime=state?.market_regime||{};
  const learning=state?.learning||{};
  const active=state?.active_trade;
  const layers=regime.layers||{};

  current.innerHTML=`
    <div class="regime-primary"><small>حالة السوق الحالية</small><b class="${regimeClass(regime.direction)}">${REGIME_AR[regime.regime]||regime.regime||"—"}</b></div>
    <div class="regime-chip"><span>الاتجاه</span><b class="${regimeClass(regime.direction)}">${trendLabel(regime.direction)}</b></div>
    <div class="regime-chip"><span>التقلب</span><b>${VOL_AR[regime.volatility]||regime.volatility||"—"}</b></div>
    <div class="regime-chip"><span>Micro</span><b>${trendLabel(layers.micro)}</b></div>
    <div class="regime-chip"><span>Intraday</span><b>${trendLabel(layers.intraday)}</b></div>
    <div class="regime-chip"><span>Swing</span><b>${trendLabel(layers.swing)}</b></div>
    <div class="regime-chip"><span>Macro</span><b>${trendLabel(layers.macro)}</b></div>`;

  stats.innerHTML=`<div><small>صفقات مغلقة</small><b>${learning.closed_trades||0}</b></div><div><small>Feature Snapshots</small><b>${learning.feature_snapshots||0}</b></div><div><small>حالات أداء مسجلة</small><b>${(learning.brain_regime||[]).length}</b></div>`;

  const rows=learning.brain_regime||[];
  matrix.innerHTML=rows.length?rows.map(r=>`<div class="learn-card">
    <div class="learn-head"><b>${r.brain}</b><span>${REGIME_AR[r.regime]||r.regime}</span></div>
    <div class="learn-grid"><span>Trades <b>${r.trades}</b></span><span>Win <b>${num(r.win_rate)}%</b></span><span>P/L <b class="${Number(r.net_pnl)>=0?"good":"bad"}">${money(r.net_pnl)}</b></span><span>PF <b>${num(r.profit_factor,2)}</b></span><span>MFE <b>${num(r.avg_mfe_pct,2)}%</b></span><span>MAE <b>${num(r.avg_mae_pct,2)}%</b></span></div>
  </div>`).join(""):`<div class="learning-empty">لا توجد بيانات كافية بعد. يبدأ الجدول بالامتلاء تلقائيًا بعد إغلاق صفقات Paper Trading.</div>`;

  if(excursion){
    excursion.innerHTML=active?`<div class="excursion"><span>MFE الحالي <b class="good">${num(active.mfe_pct,3)}%</b></span><span>MAE الحالي <b class="bad">${num(active.mae_pct,3)}%</b></span><span>Regime <b>${REGIME_AR[active.market_regime]||active.market_regime||REGIME_AR[regime.regime]||"—"}</b></span></div>`:`<div class="muted">لا توجد صفقة نشطة لقياس MFE / MAE الآن.</div>`;
  }
}

function learningTick(){
  if(typeof lastState==="undefined"||!lastState)return;
  const s=JSON.stringify({regime:lastState.market_regime,learning:lastState.learning,active:lastState.active_trade?{id:lastState.active_trade.id,mfe:lastState.active_trade.mfe_pct,mae:lastState.active_trade.mae_pct,regime:lastState.active_trade.market_regime}:null});
  if(s===learningSig)return;learningSig=s;renderLearning(lastState);
}
setInterval(learningTick,900);setTimeout(learningTick,900);
