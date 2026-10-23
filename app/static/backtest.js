const BT_REGIME_AR={TREND_UP:"اتجاه صاعد",TREND_DOWN:"اتجاه هابط",PULLBACK_UPTREND:"تصحيح داخل صعود",PULLBACK_DOWNTREND:"تصحيح داخل هبوط",BREAKOUT_UP:"اختراق صاعد",BREAKOUT_DOWN:"اختراق هابط",RANGE:"نطاق عرضي",TRANSITION:"مرحلة انتقال",UNKNOWN:"غير معروف"};

function btMetricRow(label,b){return `<div class="bt-regime-card"><div class="bt-regime-head"><b>${label}</b><span>${b.trades||0} صفقة</span></div><div class="bt-regime-grid"><span>Win <b>${num(b.win_rate)}%</b></span><span>P/L <b class="${Number(b.net_pnl)>=0?"good":"bad"}">${money(b.net_pnl||0)}</b></span><span>PF <b>${num(b.profit_factor,2)}</b></span><span>Avg R <b>${num(b.avg_r,2)}</b></span><span>MFE <b>${num(b.avg_mfe_pct,2)}%</b></span><span>MAE <b>${num(b.avg_mae_pct,2)}%</b></span></div></div>`;}

function renderBacktest(result) {
  const m=result.metrics||{},brains=result.by_brain||{};
  const rows=["SCALP","INTRADAY","SWING"].map(name=>{const b=brains[name]||{};return `<tr><td data-label="العقل">${name}</td><td data-label="Trades">${b.trades||0}</td><td data-label="Win Rate">${num(b.win_rate)}%</td><td data-label="Net P/L" class="${Number(b.net_pnl)>=0?"good":"bad"}">${money(b.net_pnl||0)}</td><td data-label="Avg R">${num(b.avg_r,3)}</td><td data-label="MFE">${num(b.avg_mfe_pct,3)}%</td><td data-label="MAE">${num(b.avg_mae_pct,3)}%</td><td data-label="Rejected">${b.rejected_candidates||0}</td></tr>`;}).join("");

  const regimes=result.by_regime||{};
  const regimeCards=Object.entries(regimes).map(([name,b])=>btMetricRow(BT_REGIME_AR[name]||name,b)).join("")||`<div class="bt-empty">لا توجد صفقات كافية لتقسيم الأداء حسب حالة السوق.</div>`;
  const matrix=(result.by_brain_regime||[]).map(r=>`<div class="bt-matrix-card"><div><b>${r.brain}</b><span>${BT_REGIME_AR[r.regime]||r.regime}</span></div><div><span>${r.trades} Trades</span><span>Win ${num(r.win_rate)}%</span><span class="${Number(r.net_pnl)>=0?"good":"bad"}">${money(r.net_pnl)}</span><span>PF ${num(r.profit_factor,2)}</span></div></div>`).join("")||`<div class="bt-empty">ستظهر مقارنة Brain × Regime بعد وجود صفقات في أكثر من حالة سوق.</div>`;
  const dc=result.decision_counts||{},reject=result.rejected_candidates||{};

  $("backtestResults").innerHTML=`
    <div class="backtest-summary">
      <div class="trade-box"><small>Ending Capital</small><b>${money(m.ending_capital)}</b></div>
      <div class="trade-box"><small>Net P/L</small><b class="${Number(m.net_pnl)>=0?"good":"bad"}">${money(m.net_pnl)}</b></div>
      <div class="trade-box"><small>Return</small><b>${num(m.return_pct)}%</b></div>
      <div class="trade-box"><small>Trades</small><b>${m.trades||0}</b></div>
      <div class="trade-box"><small>Win Rate</small><b>${num(m.win_rate)}%</b></div>
      <div class="trade-box"><small>Profit Factor</small><b>${num(m.profit_factor,3)}</b></div>
      <div class="trade-box"><small>Avg R</small><b>${num(m.avg_r,3)}</b></div>
      <div class="trade-box"><small>Max DD</small><b>${num(m.max_drawdown_pct,3)}%</b></div>
    </div>
    <div class="bt-section-title">أداء العقول</div>
    <div class="table-wrap backtest-table"><table><thead><tr><th>العقل</th><th>Trades</th><th>Win Rate</th><th>Net P/L</th><th>Avg R</th><th>MFE</th><th>MAE</th><th>Rejected</th></tr></thead><tbody>${rows}</tbody></table></div>
    <div class="bt-section-title">الأداء حسب حالة السوق</div><div class="bt-regime-list">${regimeCards}</div>
    <div class="bt-section-title">Brain × Regime</div><div class="bt-matrix">${matrix}</div>
    <div class="bt-section-title">قرارات المحرك أثناء Replay</div>
    <div class="bt-decisions"><span>LONG <b>${dc.LONG||0}</b></span><span>SHORT <b>${dc.SHORT||0}</b></span><span>WAIT <b>${dc.WAIT||0}</b></span><span>NO TRADE <b>${dc.NO_TRADE||0}</b></span></div>
    <div class="bt-reject-note">مرشحات رفضتها Risk Gate: SCALP <b>${reject.SCALP||0}</b> · INTRADAY <b>${reject.INTRADAY||0}</b> · SWING <b>${reject.SWING||0}</b>. هذه أعداد رفض فقط وليست إثباتًا أن الصفقات المرفوضة كانت ستربح أو تخسر.</div>`;
}

$("runBacktest").addEventListener("click",async()=>{
  const btn=$("runBacktest"),days=$("backtestDays").value;btn.disabled=true;$("backtestStatus").textContent=`جاري تشغيل Replay لمدة ${days} يوم على جميع الفريمات...`;$("backtestResults").innerHTML="";
  try{const response=await fetch(`/api/backtest?days=${days}`,{method:"POST"}),data=await response.json();if(!response.ok)throw new Error(data.detail||"Backtest failed");renderBacktest(data);$("backtestStatus").textContent=`اكتمل اختبار ${data.days} يوم · جميع الفريمات مؤكدة · وعند تعارض SL وTP في نفس شمعة الدقيقة يتم احتساب SL أولاً.`;}catch(error){$("backtestStatus").textContent=`خطأ: ${error.message}`;}finally{btn.disabled=false;}
});
