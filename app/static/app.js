const $ = (id) => document.getElementById(id);
const money = (x) => x == null ? "—" : "$" + Number(x).toLocaleString(undefined,{maximumFractionDigits:2});
const num = (x,d=2) => x == null ? "—" : Number(x).toLocaleString(undefined,{maximumFractionDigits:d});

let tf = "5m";
let lastState = null;
let priceLines = [];

const chart = LightweightCharts.createChart($("chart"), {
  layout: { background: { type: "solid", color: "#121722" }, textColor: "#9aa5b5" },
  grid: { vertLines: { color: "#1d2431" }, horzLines: { color: "#1d2431" } },
  rightPriceScale: { borderColor: "#2b3445" },
  timeScale: { borderColor: "#2b3445", timeVisible: true, secondsVisible: false },
  crosshair: { mode: 0 },
  localization: { locale: "en-US" },
});
const candles = chart.addSeries(LightweightCharts.CandlestickSeries, {
  upColor: "#22c55e", downColor: "#ef4444",
  wickUpColor: "#22c55e", wickDownColor: "#ef4444",
  borderVisible: false,
});

function resize(){ chart.applyOptions({ width: $("chart").clientWidth, height: $("chart").clientHeight }); }
window.addEventListener("resize", resize);
window.addEventListener("orientationchange", () => setTimeout(resize, 250));
resize();

async function loadCandles() {
  const r = await fetch(`/api/candles/${tf}?limit=500`);
  const data = await r.json();
  candles.setData(data.map(c => ({time:c.time,open:c.open,high:c.high,low:c.low,close:c.close})));
  chart.timeScale().fitContent();
  drawLevels();
}

function line(price, title, color, style=2) {
  if (price == null) return;
  const l = candles.createPriceLine({ price:Number(price), color, lineWidth:1, lineStyle:style, axisLabelVisible:true, title });
  priceLines.push(l);
}
function clearLines(){ priceLines.forEach(l => { try{candles.removePriceLine(l)}catch(e){} }); priceLines=[]; }

function drawLevels() {
  clearLines();
  if (!lastState) return;
  const t = lastState.active_trade;
  if (t) {
    line(t.entry,"ENTRY","#60a5fa",0);
    line(t.stop_loss,"SL","#ef4444",2);
    line(t.tp1,"TP1","#22c55e",2);
    line(t.tp2,"TP2","#16a34a",2);
    line(t.tp3,"TP3","#15803d",2);
    return;
  }
  const w = lastState.master?.winner;
  if (w && ["LONG","SHORT"].includes(w.direction)) {
    line(w.entry,"Candidate Entry","#60a5fa",2);
    line(w.stop_loss,"Candidate SL","#ef4444",2);
    line(w.tp1,"TP1","#22c55e",2);
    line(w.tp2,"TP2","#16a34a",2);
    line(w.tp3,"TP3","#15803d",2);
  }
}

function renderBrains(master) {
  const proposals = master?.proposals || [];
  $("brains").innerHTML = proposals.map(p => {
    const score = p.final_score || 0;
    const gate = p.risk_gate === "PASSED" ? "✅ PASSED" : "⛔ " + (p.risk_gate || "WAIT");
    const reasons = (p.risk_gate_reasons || []).slice(0,2).join(" · ");
    return `<div class="brain">
      <h3>${p.brain}</h3>
      <div class="dir ${p.direction}">${p.direction}</div>
      <small>Confidence: ${num(p.confidence)}%</small>
      <small>Safety: ${num(p.safety_score)} · Profit: ${num(p.profit_score)}</small>
      <small>EV: ${num(p.ev_pct,4)}% · R:R ${num(p.rr,2)}</small>
      <div class="scorebar"><i style="width:${Math.max(0,Math.min(100,score))}%"></i></div>
      <small>${gate} · ${p.shared_context || ""}</small>
      ${reasons ? `<small class="gate-reasons">${reasons}</small>` : ""}
    </div>`;
  }).join("") || `<div class="empty">بانتظار أول تحليل...</div>`;
}

function renderTrade(t) {
  if (!t) {
    $("activeTrade").innerHTML = `<div class="empty">لا توجد صفقة مفتوحة.</div>`;
    $("tradeLock").className = "lock open";
    $("tradeLock").textContent = "🔓 لا توجد صفقة مفتوحة";
    return;
  }
  $("tradeLock").className = "lock closed";
  $("tradeLock").textContent = "🔒 NEW TRADES LOCKED";
  $("activeTrade").innerHTML = `<div class="trade-grid">
    <div class="trade-box"><small>العقل</small><b>${t.brain}</b></div>
    <div class="trade-box"><small>الاتجاه</small><b class="${t.direction==="LONG"?"good":"bad"}">${t.direction}</b></div>
    <div class="trade-box"><small>Entry</small><b>${num(t.entry)}</b></div>
    <div class="trade-box"><small>Live P/L</small><b class="${(t.total_live_pnl||0)>=0?"good":"bad"}">${money(t.total_live_pnl)}</b></div>
    <div class="trade-box"><small>SL</small><b>${num(t.stop_loss)}</b></div>
    <div class="trade-box"><small>TP1</small><b>${num(t.tp1)}</b></div>
    <div class="trade-box"><small>TP2</small><b>${num(t.tp2)}</b></div>
    <div class="trade-box"><small>TP3</small><b>${num(t.tp3)}</b></div>
  </div>`;
}

async function refreshTrades(){
  const r = await fetch("/api/trades?limit=20");
  const rows = await r.json();
  $("tradesBody").innerHTML = rows.map(t => `<tr>
    <td data-label="#">${t.id}</td>
    <td data-label="العقل">${t.brain}</td>
    <td data-label="الاتجاه" class="${t.direction==="LONG"?"good":"bad"}">${t.direction}</td>
    <td data-label="الدخول">${num(t.entry)}</td>
    <td data-label="الخروج">${num(t.exit_price)}</td>
    <td data-label="P/L" class="${Number(t.realized_pnl)>=0?"good":"bad"}">${money(t.realized_pnl)}</td>
    <td data-label="السبب">${t.exit_reason || t.status}</td>
  </tr>`).join("") || `<tr><td data-label="الحالة">لا توجد صفقات مسجلة بعد</td></tr>`;
}

function renderState(s) {
  lastState = s;
  $("conn").textContent = s.connected ? "LIVE" : "OFFLINE";
  $("conn").style.color = s.connected ? "#22c55e" : "#ef4444";
  $("price").textContent = s.price ? money(s.price) : "—";

  const m = s.master || {};
  const a = (m.action || "WAIT").toLowerCase();
  $("masterAction").className = "decision " + a;
  $("masterAction").textContent = m.action || "WAIT";
  $("masterMessage").textContent = m.message || "";
  $("winner").innerHTML = m.winner ? `الأفضل الآن: <b>${m.winner.brain}</b> · Final Score <b>${num(m.winner.final_score)}</b>` : "";

  renderBrains(m);
  renderTrade(s.active_trade);

  const st = s.stats || {};
  $("startCapital").textContent = money(st.starting_capital);
  $("capital").textContent = money(st.capital);
  $("netPnl").textContent = money(st.net_pnl);
  $("netPnl").className = Number(st.net_pnl)>=0 ? "good" : "bad";
  $("winRate").textContent = num(st.win_rate) + "%";
  $("trades").textContent = st.trades || 0;
  $("pf").textContent = num(st.profit_factor);
  $("dd").textContent = num(st.max_drawdown_pct) + "%";
  drawLevels();
}

document.querySelectorAll("#tfButtons button").forEach(btn => {
  btn.addEventListener("click", async () => {
    document.querySelectorAll("#tfButtons button").forEach(x => x.classList.remove("active"));
    btn.classList.add("active");
    tf = btn.dataset.tf;
    await loadCandles();
  });
});

$("resetBtn").addEventListener("click", async () => {
  if (!confirm("تصفير سجل المحاكاة ورأس المال إلى $1000؟")) return;
  const r = await fetch("/api/reset", {method:"POST"});
  if (!r.ok) {
    const e = await r.json();
    alert(e.detail || "تعذر التصفير");
    return;
  }
  renderState(await r.json());
  await refreshTrades();
});

function connectWs() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen = () => ws.send("hello");
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === "state") {
      renderState(msg.state);
      refreshTrades();
      try { ws.send("ping"); } catch(e) {}
    } else if (msg.type === "candle" && msg.interval === tf) {
      const c = msg.candle;
      candles.update({time:c.time,open:c.open,high:c.high,low:c.low,close:c.close});
    }
  };
  ws.onclose = () => setTimeout(connectWs, 2000);
}
loadCandles();
fetch("/api/state").then(r=>r.json()).then(renderState).catch(()=>{});
refreshTrades();
connectWs();
