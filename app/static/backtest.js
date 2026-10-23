function renderBacktest(result) {
  const m = result.metrics || {};
  const brains = result.by_brain || {};
  const rows = ["SCALP","INTRADAY","SWING"].map(name => {
    const b = brains[name] || {};
    return `<tr>
      <td data-label="العقل">${name}</td>
      <td data-label="Trades">${b.trades||0}</td>
      <td data-label="Win Rate">${num(b.win_rate)}%</td>
      <td data-label="Net P/L" class="${Number(b.net_pnl)>=0?"good":"bad"}">${money(b.net_pnl||0)}</td>
      <td data-label="Avg R">${num(b.avg_r,3)}</td>
      <td data-label="MFE">${num(b.avg_mfe_pct,3)}%</td>
      <td data-label="MAE">${num(b.avg_mae_pct,3)}%</td>
    </tr>`;
  }).join("");
  $("backtestResults").innerHTML = `<div class="backtest-summary">
    <div class="trade-box"><small>Ending Capital</small><b>${money(m.ending_capital)}</b></div>
    <div class="trade-box"><small>Net P/L</small><b class="${Number(m.net_pnl)>=0?"good":"bad"}">${money(m.net_pnl)}</b></div>
    <div class="trade-box"><small>Return</small><b>${num(m.return_pct)}%</b></div>
    <div class="trade-box"><small>Trades</small><b>${m.trades||0}</b></div>
    <div class="trade-box"><small>Win Rate</small><b>${num(m.win_rate)}%</b></div>
    <div class="trade-box"><small>Profit Factor</small><b>${num(m.profit_factor,3)}</b></div>
    <div class="trade-box"><small>Avg R</small><b>${num(m.avg_r,3)}</b></div>
    <div class="trade-box"><small>Max DD</small><b>${num(m.max_drawdown_pct,3)}%</b></div>
  </div>
  <div class="table-wrap backtest-table"><table><thead><tr><th>العقل</th><th>Trades</th><th>Win Rate</th><th>Net P/L</th><th>Avg R</th><th>MFE</th><th>MAE</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

$("runBacktest").addEventListener("click", async () => {
  const btn = $("runBacktest");
  const days = $("backtestDays").value;
  btn.disabled = true;
  $("backtestStatus").textContent = `جاري تشغيل Replay لمدة ${days} يوم...`;
  $("backtestResults").innerHTML = "";
  try {
    const response = await fetch(`/api/backtest?days=${days}`, {method:"POST"});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Backtest failed");
    renderBacktest(data);
    $("backtestStatus").textContent = `اكتمل اختبار ${data.days} يوم · عند تعارض SL وTP في نفس شمعة الدقيقة يتم احتساب SL أولاً.`;
  } catch (error) {
    $("backtestStatus").textContent = `خطأ: ${error.message}`;
  } finally {
    btn.disabled = false;
  }
});
