const $ = id => document.getElementById(id);
const money = x => x==null ? '—' : '$'+Number(x).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
const num = (x,d=2) => x==null ? '—' : Number(x).toFixed(d);
const pct = (x,d=2) => x==null ? '—' : (Number(x)>=0?'+':'')+Number(x).toFixed(d)+'%';

function clsDirection(x){
  if(['BULLISH','LONG','UP','WIN','SUPPORTIVE','OK','TRIGGERED','OPTIMAL','LOW'].includes(x)) return 'good';
  if(['BEARISH','SHORT','DOWN','LOSS','HEADWIND','ERROR','HIGH','LATE'].includes(x)) return 'bad';
  if(['WAIT','NEUTRAL','DEGRADED','PARTIAL','NO_API_KEY','READY','MEDIUM','EARLY','ACCEPTABLE'].includes(x)) return 'warn';
  return 'neutral';
}
function setupGradeClass(g){ return ['A+','A'].includes(g)?'good':g==='B'?'warn':'neutral'; }
function ageText(sec){
  sec=Number(sec||0);
  if(sec<60) return Math.round(sec)+'s';
  if(sec<3600) return Math.round(sec/60)+'m';
  return (sec/3600).toFixed(1)+'h';
}
function shortId(x){
  if(!x) return '—';
  return x.length>24 ? x.slice(0,11)+'…'+x.slice(-7) : x;
}

document.querySelectorAll('.tab').forEach(btn=>{
  btn.addEventListener('click',()=>{
    document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(x=>x.classList.remove('active'));
    btn.classList.add('active');
    $(btn.dataset.tab).classList.add('active');
  });
});

function renderPnl(pnl){
  const labels={day:'اليوم',week:'الأسبوع',month:'الشهر',total:'الإجمالي'};
  $('pnlGrid').innerHTML=['day','week','month','total'].map(k=>{
    const x=pnl?.[k]||{}, n=Number(x.net_pnl||0);
    return `<article class="pnl-card">
      <div class="period">${labels[k]}</div>
      <div class="net ${n>0?'good':n<0?'bad':'neutral'}">${money(n)}</div>
      <div class="pnl-details">
        <span>Gross +: ${money(x.gross_profit||0)}</span>
        <span>Gross -: ${money(x.gross_loss||0)}</span>
        <span>Fees: ${money(x.fees||0)}</span>
        <span>R: ${num(x.total_r||0,2)}R</span>
        <span>W/L: ${x.wins||0}/${x.losses||0}</span>
        <span>WR: ${num(x.win_rate||0,1)}%</span>
        <span>Return: ${pct(x.return_pct||0,2)}</span>
      </div>
    </article>`;
  }).join('');
}

function renderLane(lane,lab){
  const p=lane?.plan||{}, d=lane?.diagnostics||{}, opp=lane?.opportunity||{}, pa=lane?.price_action||{};
  const why=Object.entries(lane?.why||{}).map(([k,v])=>
    `<span class="${v?'good':'bad'}">${v?'✓':'×'} ${k.replaceAll('_',' ')}</span>`
  ).join('<br>');
  return `<article class="lane-card">
    <div class="lane-head">
      <div>
        <div class="label">${lane?.lane||'—'}</div>
        <div class="lane-action ${clsDirection(lane?.action)}">${lane?.action||'—'}</div>
      </div>
      <div style="text-align:left">
        <div class="grade ${setupGradeClass(lane?.setup_grade)}">${lane?.setup_grade||'—'} · ${num(lane?.setup_score,0)}</div>
        <div class="minor">Setup Score — ليس احتمال نجاح</div>
      </div>
    </div>

    <div class="opportunity-strip">
      <span><b>Opportunity</b> <code title="${opp.opportunity_id||''}">${shortId(opp.opportunity_id)}</code></span>
      <span class="${clsDirection(opp.state)}">${opp.state||'—'}</span>
      <span>${opp.age_sec==null?'—':ageText(opp.age_sec)}</span>
    </div>

    <div class="permission">
      <div class="perm"><div class="label">LONG Direction Score</div><b class="good">${num(lane?.long_direction_score,0)}</b></div>
      <div class="perm"><div class="label">SHORT Direction Score</div><b class="bad">${num(lane?.short_direction_score,0)}</b></div>
    </div>

    <div class="diagnostic-grid">
      <div class="diag"><span class="label">Entry Timing</span><b class="${clsDirection(d.entry_timing)}">${d.entry_timing||'—'}</b></div>
      <div class="diag"><span class="label">Chasing Risk</span><b class="${clsDirection(d.chasing_risk)}">${d.chasing_risk||'—'}</b></div>
      <div class="diag"><span class="label">Available R:R</span><b>${num(d.available_rr,2)}R</b></div>
      <div class="diag"><span class="label">R:R Gate</span><b class="${d.rr_gate_pass?'good':'bad'}">${d.rr_gate_pass?'PASS':'BLOCK'}</b></div>
      <div class="diag"><span class="label">Price Action</span><b class="${pa.state==='ALIGNED'?'good':pa.state==='OPPOSED'?'bad':'warn'}">${pa.state||'NEUTRAL'}</b></div>
      <div class="diag"><span class="label">PA Match Score</span><b class="${(pa.score||0)>.18?'good':(pa.score||0)<-.18?'bad':'warn'}">${num((pa.score||0)*100,0)}</b></div>
    </div>

    <div class="pa-evidence">
      <div><span class="label">PA aligned:</span> ${(pa.aligned_evidence||[]).slice(0,5).join(' · ')||'—'}</div>
      <div><span class="label">PA opposed:</span> ${(pa.opposed_evidence||[]).slice(0,5).join(' · ')||'—'}</div>
    </div>

    <div class="reason-list">${why||'—'}</div>
    <div class="plan-grid">
      <div class="plan-item"><span class="label">Entry</span><div class="ltr">${num(p.entry)}</div></div>
      <div class="plan-item"><span class="label">SL</span><div class="ltr">${num(p.sl)}</div></div>
      <div class="plan-item"><span class="label">TP1</span><div class="ltr">${num(p.tp1)}</div></div>
      <div class="plan-item"><span class="label">TP2</span><div class="ltr">${num(p.tp2)}</div></div>
    </div>
    <div class="execution-source">
      <span><b>Plan:</b> ${p.mode||'—'}</span>
      <span><b>SL:</b> ${p.stop_source||'—'}</span>
      <span><b>TP1:</b> ${p.tp1_source||'—'}</span>
      <span><b>TP2:</b> ${p.tp2_source||'—'}</span>
    </div>

    <div class="lane-lab-strip">
      <div class="lane-lab-item"><span class="label">Lab Trades</span><b>${lab?.closed_trades||0}</b></div>
      <div class="lane-lab-item"><span class="label">Lab Return</span><b class="${(lab?.return_pct||0)>0?'good':(lab?.return_pct||0)<0?'bad':'neutral'}">${pct(lab?.return_pct||0)}</b></div>
      <div class="lane-lab-item"><span class="label">Expectancy</span><b class="${(lab?.expectancy_r||0)>0?'good':(lab?.expectancy_r||0)<0?'bad':'neutral'}">${num(lab?.expectancy_r||0,2)}R</b></div>
      <div class="lane-lab-item"><span class="label">Quality / Evidence</span><b>${num(lab?.quality_score||50,1)} · ${lab?.evidence||'LOW'}</b></div>
    </div>
  </article>`;
}

function renderScoreRows(obj){
  return Object.entries(obj||{}).map(([k,v])=>{
    const n=Number(v||0);
    return `<div class="score-row">
      <div class="score-top"><span>${k}</span><b class="${n>.15?'good':n<-.15?'bad':'warn'}">${num(n*100,0)}</b></div>
      <div class="bar"><div class="fill" style="width:${Math.min(100,Math.abs(n)*100)}%"></div></div>
    </div>`;
  }).join('');
}

function renderContext(ctx){
  const l=ctx?.local||{}, b=ctx?.bitbo||{};
  $('contextBox').innerHTML=`<div class="ctx-grid">
    <div class="ctx-item"><div class="label">Regime</div><b class="${clsDirection(ctx?.regime)}">${ctx?.regime||'—'}</b><div class="minor">Context Score ${num((ctx?.score||0)*100,0)}</div></div>
    <div class="ctx-item"><div class="label">Mayer Multiple</div><b>${num(l.mayer_multiple,3)}</b></div>
    <div class="ctx-item"><div class="label">200W MA</div><b class="ltr">${money(l.ma200w)}</b><div class="minor">${pct(l.distance_200w_pct)}</div></div>
    <div class="ctx-item"><div class="label">Bitbo API</div><b class="${clsDirection(b.status)}">${b.status||'—'}</b></div>
  </div>`;
}

function renderTimeframes(analysis){
  const order=['1Y','6M','3M','1M','2W','12D','1W','3D','1D','12H','8H','6H','4H','2H','1H','30m','15m','5m','3m','1m'];
  const T=analysis?.timeframes||{};
  $('tfTable').innerHTML=order.filter(tf=>T[tf]).map(tf=>{
    const a=T[tf];
    return `<tr>
      <td>${tf}</td><td class="${clsDirection(a.trend)}">${a.trend}</td>
      <td class="${clsDirection(a.structure)}">${a.structure}</td>
      <td class="${clsDirection(a.wave_direction)}">${a.wave_direction}</td>
      <td>${a.wave_state}</td>
      <td class="${a.momentum_score>.15?'good':a.momentum_score<-.15?'bad':'warn'}">${num(a.momentum_score*100,0)}</td>
      <td class="${a.volume_score>.15?'good':a.volume_score<-.15?'bad':'warn'}">${num(a.volume_score*100,0)}</td>
      <td class="ltr">${num(a.atr_pct,2)}%</td><td>${a.bos}</td>
    </tr>`;
  }).join('');
  $('hierarchy').innerHTML=renderScoreRows(analysis?.hierarchy);
  $('families').innerHTML=renderScoreRows(analysis?.families);
}

function renderShadow(shadow){
  $('shadowStats').innerHTML=(shadow?.strategies||[]).map(x=>`<tr>
    <td>${x.strategy}</td><td>${x.trades}</td><td>${x.wins}/${x.losses}</td>
    <td>${num(x.win_rate,1)}%</td><td>${x.profit_factor>=900?'∞':num(x.profit_factor,2)}</td>
    <td>${num(x.avg_r,2)}R</td><td>${Math.round((x.avg_delay_sec||0)/60)}m</td>
    <td>${pct(x.avg_confirmation_cost_pct,3)}</td>
    <td>${x.missed_winners||0}</td><td>${x.avoided_losers||0}</td>
  </tr>`).join('');
}

function renderLaneStats(stats){
  $('laneStats').innerHTML=['FAST_SCALP','SCALP','INTRADAY','SWING'].map(k=>{
    const x=stats?.[k]||{};
    return `<tr><td>${k}</td><td>${x.trades||0}</td><td>${x.open||0}</td>
      <td>${x.wins||0}/${x.losses||0}</td><td>${num(x.win_rate||0,1)}%</td>
      <td class="${(x.net_pnl||0)>0?'good':(x.net_pnl||0)<0?'bad':'neutral'}">${money(x.net_pnl||0)}</td>
      <td>${num(x.avg_r||0,2)}R</td><td>${x.profit_factor>=900?'∞':num(x.profit_factor||0,2)}</td></tr>`;
  }).join('');
}

function renderResearch(r){
  $('researchMemory').textContent=(r?.snapshots||0).toLocaleString('en-US');
  $('researchGrades').innerHTML=(r?.by_grade||[]).map(x=>`<tr>
    <td>${x.grade}</td><td>${x.n}</td><td>${pct(x.aligned_1h_avg_pct)}</td><td>${pct(x.aligned_4h_avg_pct)}</td>
  </tr>`).join('');
  $('researchRecent').innerHTML=(r?.recent||[]).map(x=>`<tr>
    <td><code>${shortId(x.opportunity_id)}</code></td>
    <td class="${clsDirection(x.bias)}">${x.bias}</td><td>${x.market_regime||'—'}</td>
    <td>${x.best_lane||'—'}</td><td class="${clsDirection(x.best_action)}">${x.best_action||'—'}</td>
    <td>${x.best_grade||'—'}</td><td>${num(x.best_score,0)}</td>
    <td class="${clsDirection(x.entry_timing)}">${x.entry_timing||'—'}</td>
    <td class="${clsDirection(x.chasing_risk)}">${x.chasing_risk||'—'}</td>
    <td>${num(x.available_rr,2)}R</td><td>${pct(x.r1h_pct)}</td><td>${pct(x.r4h_pct)}</td>
  </tr>`).join('');
}

function renderRecentTrades(rows){
  $('recentTrades').innerHTML=(rows||[]).map(x=>`<tr>
    <td><code>${shortId(x.opportunity_id)}</code></td><td>${x.lane}</td><td>${x.market_regime||'—'}</td>
    <td class="${x.price_action_state==='ALIGNED'?'good':x.price_action_state==='OPPOSED'?'bad':'warn'}">${x.price_action_state||'—'}</td>
    <td>${x.plan_mode||'—'}<div class="minor">${x.stop_source||'—'}</div></td>
    <td class="${clsDirection(x.side)}">${x.side}</td><td>${x.setup_grade||'—'}</td>
    <td class="${clsDirection(x.entry_timing)}">${x.entry_timing||'—'}</td>
    <td class="${clsDirection(x.chasing_risk)}">${x.chasing_risk||'—'}</td>
    <td class="ltr">${num(x.entry)}</td><td class="${clsDirection(x.status)}">${x.status}</td>
    <td class="${(x.net_pnl||0)>0?'good':(x.net_pnl||0)<0?'bad':'neutral'}">${money(x.net_pnl||0)}</td>
    <td>${num(x.realized_r||0,2)}R</td><td>${num(x.mfe_r||0,2)}R</td><td>${num(x.mae_r||0,2)}R</td>
    <td>${num(x.capture_efficiency_pct||0,1)}%</td>
  </tr>`).join('');
}

function renderOpenTrades(rows,summary){
  const n=summary?.open_trades||0, up=Number(summary?.unrealized_pnl||0);
  $('openTradesSummary').textContent=`${n} · ${money(up)}`;
  $('openTradesSummary').className='big-stat '+(up>0?'good':up<0?'bad':'neutral');
  $('openTradesMeta').textContent=`Unrealized only · Current R ${num(summary?.current_r||0,2)}R — لا يدخل في Realized P&L`;
  $('openTrades').innerHTML=(rows||[]).map(x=>`<tr>
    <td><code>${shortId(x.opportunity_id)}</code></td><td>${x.lane}</td>
    <td class="${clsDirection(x.side)}">${x.side}</td>
    <td class="${x.trade_state==='TP1_HIT'?'good':'warn'}">${x.trade_state}</td>
    <td>${ageText(x.age_sec)}</td><td class="ltr">${num(x.entry)}</td><td class="ltr">${num(x.live_price)}</td>
    <td class="${x.unrealized_pnl>0?'good':x.unrealized_pnl<0?'bad':'neutral'}">${money(x.unrealized_pnl)}</td>
    <td>${num(x.current_r,2)}R</td><td>${num(x.mfe_r,2)}R</td><td>${num(x.mae_r,2)}R</td>
    <td>${pct(x.distance_to_sl_pct)}</td><td>${pct(x.distance_to_tp1_pct)}</td><td>${pct(x.distance_to_tp2_pct)}</td>
  </tr>`).join('');
}

function renderRiskGuard(g){
  const ok=g?.allow_new_trades;
  $('riskGuard').innerHTML=`<div class="guard-box">
    <div class="guard-item"><div class="label">New Trades</div><b class="${ok?'good':'bad'}">${ok?'ALLOWED':'PAUSED'}</b></div>
    <div class="guard-item"><div class="label">Open</div><b>${g?.open_trades||0}/${g?.max_open_trades||0}</b></div>
    <div class="guard-item"><div class="label">Daily Net</div><b class="${(g?.daily_net_pnl||0)>=0?'good':'bad'}">${money(g?.daily_net_pnl||0)}</b></div>
    <div class="guard-item"><div class="label">Loss Limit</div><b>${money(g?.daily_loss_limit_usd||0)}</b></div>
    <div class="guard-item"><div class="label">Consecutive Losses</div><b>${g?.consecutive_losses||0}/${g?.max_consecutive_losses||0}</b></div>
    <div class="guard-item"><div class="label">Reason</div><b class="warn">${(g?.reasons||[]).join(', ')||'—'}</b></div>
  </div>`;
}

function renderRegimePerformance(rows){
  $('regimePerformance').innerHTML=(rows||[]).map(x=>`<tr>
    <td>${x.lane}</td><td>${x.regime}</td><td>${x.trades}</td><td>${x.wins}/${x.losses}</td>
    <td>${num(x.win_rate,1)}%</td>
    <td class="${x.net_pnl>0?'good':x.net_pnl<0?'bad':'neutral'}">${money(x.net_pnl)}</td>
    <td>${num(x.avg_r,2)}R</td><td>${num(x.avg_mfe_r,2)}R</td><td>${num(x.avg_mae_r,2)}R</td>
    <td>${num(x.capture_efficiency,1)}%</td>
  </tr>`).join('');
}

function calibrationRows(rows){
  return (rows||[]).map(x=>`<tr>
    <td>${x.label}</td><td>${x.trades}</td><td>${x.wins}/${x.losses}</td>
    <td>${num(x.win_rate,1)}%</td><td>${num(x.avg_r,2)}R</td><td>${num(x.capture_efficiency,1)}%</td>
  </tr>`).join('');
}

function renderOpportunityEvents(rows){
  $('opportunityEvents').innerHTML=(rows||[]).map(x=>`<tr>
    <td><code title="${x.opportunity_id}">${shortId(x.opportunity_id)}</code></td>
    <td>${x.lane}</td><td class="${clsDirection(x.side)}">${x.side}</td>
    <td class="${clsDirection(x.state)}">${x.state}</td><td>${num(x.score,0)}</td>
    <td class="${clsDirection(x.action)}">${x.action||'—'}</td><td>${x.note||'—'}</td>
  </tr>`).join('');
}

function renderPerformanceKpis(a){
  const items=[
    ['Experiment',shortId(a?.experiment_id),'neutral'],
    ['Return',pct(a?.return_pct||0,2),(a?.return_pct||0)>0?'good':(a?.return_pct||0)<0?'bad':'neutral'],
    ['Net P&L',money(a?.net_pnl||0),(a?.net_pnl||0)>0?'good':(a?.net_pnl||0)<0?'bad':'neutral'],
    ['Max Drawdown',pct(-(a?.max_drawdown_pct||0),2),(a?.max_drawdown_pct||0)>0?'bad':'neutral'],
    ['Expectancy',num(a?.expectancy_r||0,2)+'R',(a?.expectancy_r||0)>0?'good':(a?.expectancy_r||0)<0?'bad':'neutral'],
    ['Profit Factor',a?.profit_factor>=900?'∞':num(a?.profit_factor||0,2),(a?.profit_factor||0)>1?'good':'warn'],
    ['Payoff',a?.payoff_ratio>=900?'∞':num(a?.payoff_ratio||0,2),(a?.payoff_ratio||0)>1?'good':'warn'],
    ['Recovery',a?.recovery_factor>=900?'∞':num(a?.recovery_factor||0,2),(a?.recovery_factor||0)>1?'good':'warn'],
    ['Best Trade',money(a?.best_trade_usd||0),(a?.best_trade_usd||0)>0?'good':'neutral'],
    ['Worst Trade',money(a?.worst_trade_usd||0),(a?.worst_trade_usd||0)<0?'bad':'neutral'],
    ['Max Win Streak',String(a?.max_win_streak||0),'good'],
    ['Max Loss Streak',String(a?.max_loss_streak||0),(a?.max_loss_streak||0)>0?'bad':'neutral'],
  ];
  $('performanceKpis').innerHTML=items.map(([k,v,c])=>`<div class="perf-kpi">
    <div class="label">${k}</div><div class="perf-value ${c}">${v}</div>
  </div>`).join('');
}

function drawEquityCurve(curve){
  const canvas=$('equityCanvas');
  if(!canvas) return;
  const ctx=canvas.getContext('2d');
  const cssW=Math.max(320,canvas.clientWidth||1200);
  const cssH=320;
  const dpr=window.devicePixelRatio||1;
  canvas.width=Math.round(cssW*dpr);
  canvas.height=Math.round(cssH*dpr);
  ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,cssW,cssH);

  const data=curve||[];
  if(data.length<2){
    ctx.font='13px Tahoma';
    ctx.fillStyle='#8ba2b8';
    ctx.textAlign='center';
    ctx.fillText('تظهر Equity Curve بعد إغلاق الصفقات.',cssW/2,cssH/2);
    return;
  }

  const pad={l:58,r:18,t:18,b:32};
  const w=cssW-pad.l-pad.r, h=cssH-pad.t-pad.b;
  const vals=data.map(x=>Number(x.equity));
  let min=Math.min(...vals), max=Math.max(...vals);
  if(max===min){max+=1;min-=1}
  const margin=(max-min)*.10;
  min-=margin;max+=margin;

  const x=i=>pad.l+(i/(data.length-1))*w;
  const y=v=>pad.t+(max-v)/(max-min)*h;

  ctx.strokeStyle='#1d3246';
  ctx.lineWidth=1;
  ctx.fillStyle='#8ba2b8';
  ctx.font='10px Tahoma';
  ctx.textAlign='right';
  for(let i=0;i<=4;i++){
    const yy=pad.t+(i/4)*h;
    const val=max-(i/4)*(max-min);
    ctx.beginPath();ctx.moveTo(pad.l,yy);ctx.lineTo(cssW-pad.r,yy);ctx.stroke();
    ctx.fillText('$'+val.toFixed(2),pad.l-6,yy+3);
  }

  ctx.strokeStyle='#67adff';
  ctx.lineWidth=2;
  ctx.beginPath();
  data.forEach((pt,i)=>{
    const xx=x(i), yy=y(Number(pt.equity));
    if(i===0)ctx.moveTo(xx,yy);else ctx.lineTo(xx,yy);
  });
  ctx.stroke();

  const last=data[data.length-1];
  ctx.fillStyle='#edf6ff';
  ctx.textAlign='left';
  ctx.font='11px Tahoma';
  ctx.fillText('Current '+money(last.equity),pad.l,pad.t+12);
}

function performanceRows(rows){
  return (rows||[]).map(x=>`<tr>
    <td>${x.label}</td><td>${x.trades}</td><td>${x.wins}/${x.losses}</td>
    <td>${num(x.win_rate,1)}%</td>
    <td class="${x.net_pnl>0?'good':x.net_pnl<0?'bad':'neutral'}">${money(x.net_pnl)}</td>
    <td>${num(x.avg_r,2)}R</td>
  </tr>`).join('');
}

function renderExperimentHistory(rows){
  $('experimentHistory').innerHTML=(rows||[]).map(x=>`<tr>
    <td><code title="${x.experiment_id}">${shortId(x.experiment_id)}</code></td>
    <td class="${x.status==='ACTIVE'?'good':'neutral'}">${x.status}</td>
    <td>${money(x.start_balance)}</td><td>${money(x.ending_balance)}</td>
    <td>${x.trades}</td><td>${x.wins}/${x.losses}</td><td>${num(x.win_rate,1)}%</td>
    <td class="${x.net_pnl>0?'good':x.net_pnl<0?'bad':'neutral'}">${money(x.net_pnl)}</td>
    <td class="${x.return_pct>0?'good':x.return_pct<0?'bad':'neutral'}">${pct(x.return_pct)}</td>
    <td class="${x.max_drawdown_pct>0?'bad':'neutral'}">${pct(-x.max_drawdown_pct)}</td>
    <td>${num(x.total_r,2)}R</td><td>${x.profit_factor>=900?'∞':num(x.profit_factor,2)}</td>
  </tr>`).join('');
}

function renderLaneComparison(lab){
  const lanes=lab?.lanes||{};
  const ranking=lab?.ranking||['FAST_SCALP','SCALP','INTRADAY','SWING'];

  $('laneComparison').innerHTML=ranking.map((lane,i)=>{
    const x=lanes[lane]||{};
    return `<tr class="${i===0?'rank-1':''}">
      <td>#${i+1}</td><td>${lane}</td><td>${x.closed_trades||0}</td><td>${x.open_trades||0}</td>
      <td>${x.wins||0}/${x.losses||0}</td><td>${num(x.win_rate||0,1)}%</td>
      <td class="${(x.net_pnl||0)>0?'good':(x.net_pnl||0)<0?'bad':'neutral'}">${money(x.net_pnl||0)}</td>
      <td class="${(x.return_pct||0)>0?'good':(x.return_pct||0)<0?'bad':'neutral'}">${pct(x.return_pct||0)}</td>
      <td class="${(x.expectancy_r||0)>0?'good':(x.expectancy_r||0)<0?'bad':'neutral'}">${num(x.expectancy_r||0,2)}R</td>
      <td>${x.profit_factor>=900?'∞':num(x.profit_factor||0,2)}</td>
      <td class="${(x.max_drawdown_pct||0)>0?'bad':'neutral'}">${pct(-(x.max_drawdown_pct||0))}</td>
      <td>${num(x.quality_score||50,1)}</td>
      <td class="evidence-${x.evidence||'LOW'}">${x.evidence||'LOW'}</td>
      <td>${num(x.reliability_pct||0,0)}%</td>
    </tr>`;
  }).join('');

  if(lab?.best_observed_lane){
    const x=lanes[lab.best_observed_lane]||{};
    $('laneLeader').innerHTML=
      `أفضل مسار مرصود حاليًا: <b class="good">${lab.best_observed_lane}</b> · `+
      `Quality ${num(x.quality_score,1)} · Expectancy ${num(x.expectancy_r,2)}R · `+
      `PF ${x.profit_factor>=900?'∞':num(x.profit_factor,2)} · `+
      `${x.closed_trades} صفقة مغلقة · Evidence ${x.evidence}.`;
  }else{
    $('laneLeader').innerHTML=
      `لا يوجد Leader موثوق بعد. نحتاج على الأقل ${lab?.minimum_for_provisional_leader||10} `+
      `صفقات مغلقة لمسار واحد لإظهار Leader أولي، و${lab?.target_for_high_evidence||30} لثقة بحثية أعلى.`;
  }
}

function renderLaneRegimeComparison(rows){
  $('laneRegimeComparison').innerHTML=(rows||[]).map(x=>`<tr>
    <td>${x.regime||'UNKNOWN'}</td><td>${x.lane}</td><td>${x.trades||0}</td>
    <td>${x.wins||0}/${x.losses||0}</td><td>${num(x.win_rate||0,1)}%</td>
    <td class="${(x.net_pnl||0)>0?'good':(x.net_pnl||0)<0?'bad':'neutral'}">${money(x.net_pnl||0)}</td>
    <td>${num(x.avg_r||0,2)}R</td><td>${num(x.avg_mfe_r||0,2)}R</td>
    <td>${num(x.avg_mae_r||0,2)}R</td><td>${num(x.capture_efficiency||0,1)}%</td>
  </tr>`).join('');
}

function paPrice(v){
  return v==null ? '—' : Number(v).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
}

function renderPriceAction(pa){
  const P=pa?.timeframes||{};
  const order=['1W','3D','1D','12H','8H','6H','4H','2H','1H','30m','15m','5m','3m','1m'];

  $('paSummary').textContent=(pa?.summary_state||'NEUTRAL')+' · '+num((pa?.summary_score||0)*100,0);
  $('paSummary').className='big-stat '+(
    pa?.summary_state==='BULLISH'?'good':pa?.summary_state==='BEARISH'?'bad':'warn'
  );

  $('paTfTable').innerHTML=order.filter(tf=>P[tf]).map(tf=>{
    const x=P[tf]||{};
    const z=x.zones||{}, s=z.nearest_support, r=z.nearest_resistance;
    const tl=x.trendlines||{};
    const candle=x.candles?.primary;
    const pattern=x.chart_patterns?.primary;

    let trend='—';
    if(tl.support_line?.valid_direction && tl.support_line?.r2>=.55){
      trend='UP TL '+num(tl.support_line.slope_pct_per_bar,3)+'%/bar';
    }
    if(tl.resistance_line?.valid_direction && tl.resistance_line?.r2>=.55){
      trend=(trend==='—'?'':trend+' · ')+'DOWN TL '+num(tl.resistance_line.slope_pct_per_bar,3)+'%/bar';
    }
    if(tl.channel && tl.channel!=='NONE'){
      trend=(trend==='—'?'':trend+' · ')+tl.channel;
    }
    if(tl.breakout && tl.breakout!=='NONE'){
      trend=(trend==='—'?'':trend+' · ')+tl.breakout+(tl.retest?' + RETEST':'');
    }

    return `<tr>
      <td>${tf}</td>
      <td class="${x.state==='BULLISH'?'good':x.state==='BEARISH'?'bad':'warn'}">${x.state||'—'}</td>
      <td>${num((x.directional_score||0)*100,0)}</td>
      <td class="ltr">${s?paPrice(s.center):'—'}${s?` (${pct(-s.distance_pct)})`:''}</td>
      <td>${s?num(s.strength,0)+' · '+s.freshness+(s.role_flip?' · FLIP':''):'—'}</td>
      <td class="ltr">${r?paPrice(r.center):'—'}${r?` (${pct(r.distance_pct)})`:''}</td>
      <td>${r?num(r.strength,0)+' · '+r.freshness+(r.role_flip?' · FLIP':''):'—'}</td>
      <td>${trend}</td>
      <td class="${candle?.direction==='BULLISH'?'good':candle?.direction==='BEARISH'?'bad':'neutral'}">${candle?.name||'—'}</td>
      <td class="${pattern?.direction==='BULLISH'?'good':pattern?.direction==='BEARISH'?'bad':'neutral'}">
        ${pattern?.name||'—'}
        ${pattern?`<div class="minor">${pattern.validation?.status||'CANDIDATE'}${pattern.validation?.target!=null?' · Target '+paPrice(pattern.validation.target):''}</div>`:''}
      </td>
      <td class="good">${(x.bullish_evidence||[]).slice(0,4).join(', ')||'—'}</td>
      <td class="bad">${(x.bearish_evidence||[]).slice(0,4).join(', ')||'—'}</td>
    </tr>`;
  }).join('');
}

function renderPaPerformance(rows){
  $('paPerformance').innerHTML=(rows||[]).map(x=>`<tr>
    <td class="${x.label==='ALIGNED'?'good':x.label==='OPPOSED'?'bad':'warn'}">${x.label}</td>
    <td>${x.trades}</td><td>${x.wins}/${x.losses}</td><td>${num(x.win_rate,1)}%</td>
    <td class="${x.net_pnl>0?'good':x.net_pnl<0?'bad':'neutral'}">${money(x.net_pnl)}</td>
    <td>${num(x.avg_r,2)}R</td><td>${num(x.avg_mfe_r,2)}R</td><td>${num(x.avg_mae_r,2)}R</td>
    <td>${num(x.capture_efficiency,1)}%</td>
  </tr>`).join('');
}

function renderLanePaPerformance(rows){
  $('lanePaPerformance').innerHTML=(rows||[]).map(x=>`<tr>
    <td>${x.lane}</td>
    <td class="${x.label==='ALIGNED'?'good':x.label==='OPPOSED'?'bad':'warn'}">${x.label}</td>
    <td>${x.trades}</td><td>${x.wins}/${x.losses}</td><td>${num(x.win_rate,1)}%</td>
    <td class="${x.net_pnl>0?'good':x.net_pnl<0?'bad':'neutral'}">${money(x.net_pnl)}</td>
    <td>${num(x.avg_r,2)}R</td>
  </tr>`).join('');
}

function renderExecutionPlanPerformance(rows){
  $('executionPlanPerformance').innerHTML=(rows||[]).map(x=>`<tr>
    <td class="${x.label==='STRUCTURE_AWARE'?'good':'warn'}">${x.label}</td>
    <td>${x.trades}</td><td>${x.wins}/${x.losses}</td><td>${num(x.win_rate,1)}%</td>
    <td class="${x.net_pnl>0?'good':x.net_pnl<0?'bad':'neutral'}">${money(x.net_pnl)}</td>
    <td>${num(x.avg_r,2)}R</td><td>${num(x.avg_mfe_r,2)}R</td><td>${num(x.avg_mae_r,2)}R</td>
    <td>${num(x.capture_efficiency,1)}%</td>
  </tr>`).join('');
}

function renderLaneExecutionPlanPerformance(rows){
  $('laneExecutionPlanPerformance').innerHTML=(rows||[]).map(x=>`<tr>
    <td>${x.lane}</td>
    <td class="${x.label==='STRUCTURE_AWARE'?'good':'warn'}">${x.label}</td>
    <td>${x.trades}</td><td>${x.wins}/${x.losses}</td><td>${num(x.win_rate,1)}%</td>
    <td class="${x.net_pnl>0?'good':x.net_pnl<0?'bad':'neutral'}">${money(x.net_pnl)}</td>
    <td>${num(x.avg_r,2)}R</td>
  </tr>`).join('');
}

function renderHealth(h,status){
  const items=[
    ['Engine',h?.engine_version||'—'],['Status',status||'—'],
    ['Cycle',h?.cycle_seconds==null?'—':num(h.cycle_seconds,2)+'s'],
    ['Last success',h?.last_success_age_sec==null?'—':num(h.last_success_age_sec,0)+'s ago'],
    ['Spot',h?.spot_provider||'—'],['Futures',h?.futures_status||'—'],
    ['Bitbo',h?.bitbo_status||'—'],['Persistent DB',h?.persistent_storage?'ON':'OFF'],
    ['Closed candles',h?.closed_candle_analysis?'ON':'OFF'],['Live price separate',h?.live_price_separate?'ON':'OFF'],
    ['FAST SCALP',h?.fast_scalp_enabled?'ON':'OFF'],['Fixed Capital',money(h?.fixed_paper_capital||1000)],
  ];
  $('healthGrid').innerHTML=items.map(([k,v])=>`<div class="health-item"><div class="label">${k}</div><b>${v}</b></div>`).join('');
  $('freshness').innerHTML=Object.entries(h?.data_freshness_sec||{}).map(([tf,v])=>`<div class="fresh"><div class="label">${tf}</div><b>${Math.round(v)}s</b></div>`).join('');
  $('lastError').textContent=h?.last_error||'—';
}

async function refresh(){
  try{
    const s=await (await fetch('/api/state',{cache:'no-store'})).json();
    const status=s.status||'—';
    $('statusBadge').textContent=status;
    $('statusBadge').className='badge '+(status==='OK'?'good':status==='DEGRADED'?'warn':'bad');
    $('dataBadge').textContent='Data '+((s.health?.spot_provider)?'✓':'—');
    if(status==='ERROR' && !s.analysis) return;

    const degraded=$('degradedBanner');
    if(status==='DEGRADED'){
      degraded.classList.remove('hidden');
      degraded.textContent='DEGRADED — يتم عرض آخر تحليل ناجح. الخطأ الحالي: '+(s.health?.last_error||'غير معروف');
    }else degraded.classList.add('hidden');

    $('price').textContent=money(s.price);
    $('bias').textContent=s.analysis?.bias||'—';
    $('bias').className='hero-value '+clsDirection(s.analysis?.bias);
    $('biasScore').textContent='Bias Score '+num((s.analysis?.bias_score||0)*100,0);

    const best=s.decision?.best_setup||{}, bestOpp=best.opportunity||{};
    $('bestSetup').textContent=(best.lane||'—')+' · '+(best.action||'—');
    $('bestSetup').className='hero-value '+clsDirection(best.action);
    $('bestSetupMeta').textContent=`${best.setup_grade||'—'} · Setup Score ${num(best.setup_score,0)} · ${shortId(bestOpp.opportunity_id)}`;

    $('balance').textContent=money(s.pnl?.balance);
    $('pnlTimezone').textContent='Fixed Start $1,000 · '+shortId(s.pnl?.experiment_id)+' · '+(s.pnl?.timezone||'—');

    $('marketRegime').textContent=s.market_regime?.regime||'—';
    $('marketRegime').className='hero-value '+(s.market_regime?.regime==='TREND'?'good':s.market_regime?.regime==='HIGH_VOL'?'bad':'warn');
    $('marketRegimeMeta').textContent=`Regime Strength ${num(s.market_regime?.confidence,0)}/100 · Research only`;

    renderPnl(s.pnl);
    renderOpenTrades(s.open_positions,s.unrealized);
    renderRiskGuard(s.risk_guard);
    $('lanes').innerHTML=['FAST_SCALP','SCALP','INTRADAY','SWING'].map(k=>renderLane(s.decision?.lanes?.[k],s.lane_comparison?.lanes?.[k])).join('');
    renderContext(s.bitcoin_context);
    renderRecentTrades(s.recent_trades);
    renderTimeframes(s.analysis);
    renderPriceAction(s.analysis?.price_action);
    renderPaPerformance(s.price_action_performance);
    renderLanePaPerformance(s.lane_price_action_comparison);
    renderExecutionPlanPerformance(s.execution_plan_performance);
    renderLaneExecutionPlanPerformance(s.lane_execution_plan_comparison);
    renderShadow(s.shadow_compare);
    renderLaneStats(s.lane_stats);
    renderResearch(s.research);
    renderRegimePerformance(s.regime_performance);
    $('entryTimingCalibration').innerHTML=calibrationRows(s.calibration_stats?.entry_timing);
    $('chasingCalibration').innerHTML=calibrationRows(s.calibration_stats?.chasing_risk);
    renderOpportunityEvents(s.opportunity_events);
    renderPerformanceKpis(s.performance_analytics);
    drawEquityCurve(s.performance_analytics?.equity_curve);
    $('hourPerformance').innerHTML=performanceRows(s.time_performance?.hour);
    $('weekdayPerformance').innerHTML=performanceRows(s.time_performance?.weekday);
    $('timePerfTz').textContent='Entry time · '+(s.time_performance?.timezone||'—');
    renderExperimentHistory(s.experiments);
    renderLaneComparison(s.lane_comparison);
    renderLaneRegimeComparison(s.lane_regime_comparison);
    renderHealth(s.health,status);
  }catch(e){
    $('statusBadge').textContent='UI ERROR';
    $('statusBadge').className='badge bad';
  }
}
refresh();
setInterval(refresh,15000);
