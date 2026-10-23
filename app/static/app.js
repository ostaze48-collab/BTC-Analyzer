const $ = (id) => document.getElementById(id);
const money = (x) => x == null ? "—" : "$" + Number(x).toLocaleString(undefined,{maximumFractionDigits:2});
const num = (x,d=2) => x == null ? "—" : Number(x).toLocaleString(undefined,{maximumFractionDigits:d});

const ACTION_AR = {LONG:"شراء LONG",SHORT:"بيع SHORT",WAIT:"انتظار",NO_TRADE:"لا صفقة",BOOTING:"تحميل"};
const TREND_AR = {BULLISH:"صاعد",BEARISH:"هابط",MIXED:"مختلط",NEUTRAL:"محايد"};
const STRUCTURE_AR = {BULLISH:"صاعد",BEARISH:"هابط",RANGE:"نطاق",NEUTRAL:"محايد"};
const CONSENSUS_AR = {FULL_CONSENSUS:"اتفاق كامل",PARTIAL_CONSENSUS:"اتفاق جزئي",CONFLICT:"تعارض",SOLO:"منفرد",NEUTRAL:"محايد"};
const REASON_AR = {
  "No directional setup":"لا يوجد اتجاه واضح",
  "Confidence below minimum":"الثقة أقل من الحد المطلوب",
  "R:R below minimum":"العائد مقابل المخاطرة أقل من المطلوب",
  "Expected value is not positive":"القيمة المتوقعة ليست موجبة",
  "Stop distance exceeds maximum":"مسافة وقف الخسارة كبيرة",
  "Safety score below minimum":"درجة الأمان أقل من الحد المطلوب",
  "Strong macro conflict":"تعارض قوي مع اتجاه الفريمات الكبيرة",
};
const TF_LABEL = {
  "1m":"1 دقيقة","3m":"3 دقائق","5m":"5 دقائق","15m":"15 دقيقة","30m":"30 دقيقة",
  "1h":"1 ساعة","2h":"2 ساعة","4h":"4 ساعات","6h":"6 ساعات","8h":"8 ساعات","12h":"12 ساعة",
  "1d":"يومي","3d":"3 أيام","1w":"أسبوعي"
};
const TF_ORDER = ["1m","3m","5m","15m","30m","1h","2h","4h","6h","8h","12h","1d","3d","1w"];
const LAYER_AR = {MICRO:"Micro · تنفيذ",INTRADAY:"Intraday · يومي",SWING:"Swing · متوسط",MACRO:"Macro · كبير"};

let tf = "5m";
let lastState = null;
let lastDecisionSignature = "";
let priceLines = [];
let renderTimer = null;
let pendingState = null;
let rawCandles = [];
let overlayTimer = null;
const overlays = {ema:true,vwap:false,sr:true,trade:true};

function chartWidth(){ return Math.max(300, $("chart")?.clientWidth || document.documentElement.clientWidth - 16); }
const chart = LightweightCharts.createChart($("chart"), {
  width: chartWidth(),
  layout: { background: { type: "solid", color: "#121722" }, textColor: "#9aa5b5" },
  grid: { vertLines: { color: "#1d2431" }, horzLines: { color: "#1d2431" } },
  rightPriceScale: { borderColor: "#2b3445" },
  timeScale: { borderColor: "#2b3445", timeVisible: true, secondsVisible: false, rightOffset: 4 },
  crosshair: { mode: 0 }, localization: { locale: "en-US" },
});
const candles = chart.addSeries(LightweightCharts.CandlestickSeries, {
  upColor: "#22c55e", downColor: "#ef4444", wickUpColor: "#22c55e", wickDownColor: "#ef4444", borderVisible: false,
});
const ema20Series = chart.addSeries(LightweightCharts.LineSeries, {color:"#f59e0b",lineWidth:1,priceLineVisible:false,lastValueVisible:false});
const ema50Series = chart.addSeries(LightweightCharts.LineSeries, {color:"#60a5fa",lineWidth:1,priceLineVisible:false,lastValueVisible:false});
const ema200Series = chart.addSeries(LightweightCharts.LineSeries, {color:"#a78bfa",lineWidth:1,priceLineVisible:false,lastValueVisible:false});
const vwapSeries = chart.addSeries(LightweightCharts.LineSeries, {color:"#e879f9",lineWidth:1,priceLineVisible:false,lastValueVisible:false,visible:false});

function resize(){ const el=$("chart"); if(el) chart.applyOptions({width:chartWidth(),height:Math.max(320,el.clientHeight||430)}); }
window.addEventListener("resize",()=>requestAnimationFrame(resize));
window.addEventListener("orientationchange",()=>setTimeout(()=>{resize();chart.timeScale().fitContent();},250));
resize();

function emaData(data,period){ if(!data.length)return[];const alpha=2/(period+1);let value=data[0].close;return data.map((c,i)=>{value=i===0?c.close:alpha*c.close+(1-alpha)*value;return{time:c.time,value};}); }
function vwapData(data,period=20){const out=[],q=[];let pv=0,vol=0;for(const c of data){const v=Number(c.volume||0),typical=(c.high+c.low+c.close)/3;q.push({pv:typical*v,v});pv+=typical*v;vol+=v;if(q.length>period){const old=q.shift();pv-=old.pv;vol-=old.v;}out.push({time:c.time,value:vol>0?pv/vol:c.close});}return out;}
function updateOverlaySeries(){
  ema20Series.applyOptions({visible:overlays.ema});ema50Series.applyOptions({visible:overlays.ema});ema200Series.applyOptions({visible:overlays.ema});vwapSeries.applyOptions({visible:overlays.vwap});
  if(overlays.ema){ema20Series.setData(emaData(rawCandles,20));ema50Series.setData(emaData(rawCandles,50));ema200Series.setData(emaData(rawCandles,200));}
  if(overlays.vwap)vwapSeries.setData(vwapData(rawCandles,20));drawLevels();
}
function scheduleOverlayRefresh(){if(overlayTimer)return;overlayTimer=setTimeout(()=>{overlayTimer=null;updateOverlaySeries();},1200);}

async function loadCandles(){
  try{const r=await fetch(`/api/candles/${tf}?limit=500`);const data=await r.json();rawCandles=Array.isArray(data)?data:[];candles.setData(rawCandles.map(c=>({time:c.time,open:c.open,high:c.high,low:c.low,close:c.close})));updateOverlaySeries();chart.timeScale().fitContent();}
  catch(e){console.warn("Candles load failed",e);}
}
function line(price,title,color,style=2){if(price==null||!Number.isFinite(Number(price)))return;priceLines.push(candles.createPriceLine({price:Number(price),color,lineWidth:1,lineStyle:style,axisLabelVisible:true,title}));}
function clearLines(){priceLines.forEach(l=>{try{candles.removePriceLine(l)}catch(e){}});priceLines=[];}
function drawLevels(){
  clearLines();if(!lastState)return;const t=lastState.active_trade,w=lastState.master?.winner;
  if(overlays.trade){if(t){line(t.entry,"ENTRY","#60a5fa",0);line(t.stop_loss,"SL","#ef4444",2);line(t.tp1,"TP1","#22c55e",2);line(t.tp2,"TP2","#16a34a",2);line(t.tp3,"TP3","#15803d",2);}else if(w&&["LONG","SHORT"].includes(w.direction)){line(w.entry,"ENTRY?","#60a5fa",2);line(w.stop_loss,"SL?","#ef4444",2);line(w.tp1,"TP1?","#22c55e",2);line(w.tp2,"TP2?","#16a34a",2);line(w.tp3,"TP3?","#15803d",2);}}
  if(overlays.sr){const s=lastState.snapshots?.[tf];if(s){line(s.support,"SUPPORT","#10b981",3);line(s.resistance,"RESIST","#f97316",3);}}
}

function riskReason(reason){return REASON_AR[reason]||reason;}
function dirLabel(v){return ACTION_AR[v]||v||"—";}
function trendLabel(v){return TREND_AR[v]||v||"—";}
function structureLabel(v){return STRUCTURE_AR[v]||v||"—";}
function consensusLabel(v){return CONSENSUS_AR[v]||v||"—";}

function renderMaster(master){
  const action=master?.action||"WAIT";$("masterAction").className="decision "+action.toLowerCase();$("masterAction").textContent=dirLabel(action);const w=master?.winner;
  if(!w){$("masterMessage").textContent="لا توجد أفضلية واضحة الآن.";$("winner").innerHTML="";$("masterExplain").innerHTML=`<div class="explain-note">القرار الحالي: مراقبة السوق وعدم إجبار النظام على الدخول.</div>`;return;}
  const passed=w.risk_gate==="PASSED";$("masterMessage").textContent=passed?`${w.brain} هي أفضل فرصة معدلة بالمخاطرة الآن.`:"توجد فرصة محتملة لكنها لم تجتز بوابة الأمان.";$("winner").innerHTML=`الأفضل الآن: <b>${w.brain}</b> · Final <b>${num(w.final_score)}</b>`;
  const reasons=(w.risk_gate_reasons||[]).map(r=>`<li>${riskReason(r)}</li>`).join("");
  const macroClass=w.macro_direction==="BULLISH"?"good":w.macro_direction==="BEARISH"?"bad":"neutral";
  const positives=[`الاتجاه: ${trendLabel(w.trend)}`,`الهيكل: ${structureLabel(w.structure)}`,`التوافق: ${consensusLabel(w.shared_context)}`,`R:R ${num(w.rr,2)}`,`EV ${num(w.ev_pct,3)}%`,`Macro: ${trendLabel(w.macro_direction)} ${w.macro_conflict?"⚠️ تعارض":w.macro_aligned?"✓ متوافق":""}`];
  $("masterExplain").innerHTML=`<div class="score-chips"><span>أمان <b>${num(w.safety_score)}</b></span><span>ربح <b>${num(w.profit_score)}</b></span><span>ثقة <b>${num(w.confidence)}%</b></span><span class="${macroClass}">Macro <b>${trendLabel(w.macro_direction)}</b></span></div><div class="explain-grid">${positives.map(x=>`<span>${x}</span>`).join("")}</div>${passed?`<div class="explain-ok">✅ اجتازت بوابة الأمان</div>`:`<div class="explain-reject">⛔ أسباب الرفض<ul>${reasons||"<li>لم تحقق الحدود المطلوبة</li>"}</ul></div>`}`;
}

function renderBrains(master){
  const proposals=master?.proposals||[],container=$("brains"),scroll=container?.scrollLeft||0;
  container.innerHTML=proposals.map(p=>{const score=p.final_score||0,gate=p.risk_gate==="PASSED"?"✅ اجتازت الأمان":"⛔ مرفوضة",reasons=(p.risk_gate_reasons||[]).slice(0,2).map(riskReason).join(" · ");return `<div class="brain"><h3>${p.brain}</h3><div class="dir ${p.direction}">${dirLabel(p.direction)}</div><small>الثقة: ${num(p.confidence)}%</small><small>الأمان: ${num(p.safety_score)} · الربح: ${num(p.profit_score)}</small><small>EV: ${num(p.ev_pct,4)}% · R:R ${num(p.rr,2)}</small><small>${trendLabel(p.trend)} · ${structureLabel(p.structure)}</small><small>Macro: <b class="${p.macro_direction==="BULLISH"?"good":p.macro_direction==="BEARISH"?"bad":"neutral"}">${trendLabel(p.macro_direction)}</b>${p.macro_conflict?" · ⚠️ تعارض":""}</small><div class="scorebar"><i style="width:${Math.max(0,Math.min(100,score))}%"></i></div><small>${gate} · ${consensusLabel(p.shared_context)}</small>${reasons?`<small class="gate-reasons">${reasons}</small>`:""}</div>`;}).join("")||`<div class="empty">بانتظار أول تحليل...</div>`;if(container)container.scrollLeft=scroll;
}

function renderTimeframeLayers(layers={}){
  const el=$("timeframeLayers");if(!el)return;const order=["MICRO","INTRADAY","SWING","MACRO"];
  el.innerHTML=order.map(name=>{const x=layers[name]||{},dir=x.direction||"NEUTRAL",cls=dir==="BULLISH"?"good":dir==="BEARISH"?"bad":"neutral";return `<div class="layer-card"><small>${LAYER_AR[name]}</small><b class="${cls}">${trendLabel(dir)}</b><span>Bias ${num(x.bias,3)}</span></div>`;}).join("");
}

function renderMarketContext(snapshots={}){
  $("marketContext").innerHTML=TF_ORDER.map(k=>{const s=snapshots[k];if(!s)return `<div class="context-item"><b>${TF_LABEL[k]}</b><span>بانتظار البيانات</span></div>`;const cls=s.trend==="BULLISH"?"good":s.trend==="BEARISH"?"bad":"neutral",sweep=s.liquidity?.sweep;return `<div class="context-item"><div class="context-head"><b>${TF_LABEL[k]}</b><span class="${cls}">${trendLabel(s.trend)}</span></div><div class="context-line"><span>الهيكل</span><b>${structureLabel(s.structure)}</b></div><div class="context-line"><span>RSI</span><b>${num(s.rsi14,1)}</b></div><div class="context-line"><span>التقلب</span><b>${num(s.volatility_pct,2)}%</b></div><div class="context-line"><span>Volume</span><b>${num(s.volume_ratio,2)}×</b></div><div class="context-line"><span>Liquidity</span><b>${sweep?(sweep.direction==="BULLISH"?"Sweep ↑":"Sweep ↓"):"—"}</b></div></div>`;}).join("");
}

function renderTrade(t){if(!t){$("activeTrade").innerHTML=`<div class="empty">لا توجد صفقة مفتوحة.</div>`;$("tradeLock").className="lock open";$("tradeLock").textContent="🔓 لا توجد صفقة مفتوحة";return;}$("tradeLock").className="lock closed";$("tradeLock").textContent="🔒 تم قفل الصفقات الجديدة";const live=Number(t.total_live_pnl||0),entry=Number(t.entry||0),current=Number(lastState?.price||entry),movePct=entry?((current-entry)/entry*100*(t.direction==="LONG"?1:-1)):0;$("activeTrade").innerHTML=`<div class="trade-grid"><div class="trade-box"><small>العقل</small><b>${t.brain}</b></div><div class="trade-box"><small>الاتجاه</small><b class="${t.direction==="LONG"?"good":"bad"}">${dirLabel(t.direction)}</b></div><div class="trade-box"><small>Entry</small><b>${num(t.entry)}</b></div><div class="trade-box"><small>Live P/L</small><b class="${live>=0?"good":"bad"}">${money(live)}</b></div><div class="trade-box"><small>حركة الصفقة</small><b class="${movePct>=0?"good":"bad"}">${num(movePct,2)}%</b></div><div class="trade-box"><small>SL</small><b>${num(t.stop_loss)}</b></div><div class="trade-box"><small>TP1</small><b>${num(t.tp1)}</b></div><div class="trade-box"><small>TP2 / TP3</small><b>${num(t.tp2)} / ${num(t.tp3)}</b></div></div>`;}

async function refreshTrades(){try{const r=await fetch("/api/trades?limit=20"),rows=await r.json();$("tradesBody").innerHTML=rows.map(t=>`<tr><td data-label="#">${t.id}</td><td data-label="العقل">${t.brain}</td><td data-label="الاتجاه" class="${t.direction==="LONG"?"good":"bad"}">${dirLabel(t.direction)}</td><td data-label="الدخول">${num(t.entry)}</td><td data-label="الخروج">${num(t.exit_price)}</td><td data-label="P/L" class="${Number(t.realized_pnl)>=0?"good":"bad"}">${money(t.realized_pnl)}</td><td data-label="السبب">${t.exit_reason||t.status}</td></tr>`).join("")||`<tr><td data-label="الحالة">لا توجد صفقات مسجلة بعد</td></tr>`;}catch(e){console.warn("Trades refresh failed",e);}}

function decisionSignature(s){const t=s.active_trade||{},w=s.master?.winner||{};return[s.last_analysis_at,t.id,t.stop_loss,t.tp1_hit,t.tp2_hit,s.master?.action,w.brain,w.final_score,tf].join("|");}
function renderState(s){lastState=s;$("conn").textContent=s.connected?"LIVE":"OFFLINE";$("conn").style.color=s.connected?"#22c55e":"#ef4444";$("price").textContent=s.price?money(s.price):"—";const sig=decisionSignature(s);if(sig!==lastDecisionSignature){lastDecisionSignature=sig;renderMaster(s.master||{});renderBrains(s.master||{});renderTimeframeLayers(s.timeframe_layers||s.master?.timeframe_layers||{});renderMarketContext(s.snapshots||{});drawLevels();}renderTrade(s.active_trade);const st=s.stats||{};$("startCapital").textContent=money(st.starting_capital);$("capital").textContent=money(st.capital);$("netPnl").textContent=money(st.net_pnl);$("netPnl").className=Number(st.net_pnl)>=0?"good":"bad";$("winRate").textContent=num(st.win_rate)+"%";$("trades").textContent=st.trades||0;$("pf").textContent=num(st.profit_factor);$("dd").textContent=num(st.max_drawdown_pct)+"%";}
function scheduleStateRender(s){pendingState=s;if(renderTimer)return;renderTimer=setTimeout(()=>{renderTimer=null;if(pendingState)renderState(pendingState);pendingState=null;},250);}
function upsertRawCandle(c){if(!rawCandles.length||rawCandles[rawCandles.length-1].time<c.time){rawCandles.push(c);if(rawCandles.length>500)rawCandles.shift();}else if(rawCandles[rawCandles.length-1].time===c.time)rawCandles[rawCandles.length-1]={...rawCandles[rawCandles.length-1],...c};}

document.querySelectorAll("#tfButtons button").forEach(btn=>btn.addEventListener("click",async()=>{document.querySelectorAll("#tfButtons button").forEach(x=>x.classList.remove("active"));btn.classList.add("active");tf=btn.dataset.tf;lastDecisionSignature="";await loadCandles();if(lastState){renderMarketContext(lastState.snapshots||{});drawLevels();}}));
document.querySelectorAll(".overlay-toggle[data-overlay]").forEach(btn=>btn.addEventListener("click",()=>{const key=btn.dataset.overlay;overlays[key]=!overlays[key];btn.classList.toggle("active",overlays[key]);updateOverlaySeries();}));
$("resetBtn").addEventListener("click",async()=>{if(!confirm("تصفير سجل المحاكاة ورأس المال إلى $1000؟"))return;const r=await fetch("/api/reset",{method:"POST"});if(!r.ok){const e=await r.json();alert(e.detail||"تعذر التصفير");return;}renderState(await r.json());await refreshTrades();});
document.querySelectorAll('.mobile-nav a').forEach(a=>a.addEventListener('click',()=>{if(a.getAttribute('href')==='#chartSection')setTimeout(()=>{resize();chart.timeScale().fitContent();},350);}));

function connectWs(){const proto=location.protocol==="https:"?"wss":"ws",ws=new WebSocket(`${proto}://${location.host}/ws`);let pingTimer=null;ws.onopen=()=>{ws.send("hello");pingTimer=setInterval(()=>{if(ws.readyState===WebSocket.OPEN)ws.send("ping");},20000);};ws.onmessage=(ev)=>{const msg=JSON.parse(ev.data);if(msg.type==="state")scheduleStateRender(msg.state);else if(msg.type==="candle"&&msg.interval===tf){const c=msg.candle;candles.update({time:c.time,open:c.open,high:c.high,low:c.low,close:c.close});upsertRawCandle(c);scheduleOverlayRefresh();}};ws.onclose=()=>{if(pingTimer)clearInterval(pingTimer);setTimeout(connectWs,2000);};ws.onerror=()=>ws.close();}

loadCandles();fetch("/api/state").then(r=>r.json()).then(renderState).catch(()=>{});refreshTrades();setInterval(refreshTrades,5000);connectWs();
