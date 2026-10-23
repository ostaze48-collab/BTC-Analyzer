// V1.4 Market Structure + Liquidity visual layer.
// All signals are computed by the backend from confirmed candles; the browser
// only renders the structured snapshot.
let msLines = [];
let msTrendSeries = [];
let msShowStructure = true;
let msShowZones = true;
let msShowLiquidity = true;
let msShowChannel = true;
let msLastSignature = "";

const MS_EVENT_AR = {BOS_UP:"BOS صاعد ↑",BOS_DOWN:"BOS هابط ↓",CHOCH_UP:"CHoCH صاعد ↑",CHOCH_DOWN:"CHoCH هابط ↓"};
const MS_STATE_AR = {BULLISH:"صاعد",BEARISH:"هابط",RANGE:"نطاق",NEUTRAL:"محايد"};
const CHANNEL_AR = {
  ASCENDING_CHANNEL:"قناة صاعدة",DESCENDING_CHANNEL:"قناة هابطة",
  BULLISH_EXPANSION:"اتساع صاعد",BEARISH_EXPANSION:"اتساع هابط",
  CONVERGING:"تضييق / مثلث",DIVERGING:"اتساع",MIXED:"مختلط"
};

const msChartEl=document.getElementById("chart");
const msZoneLayer=document.createElement("div");msZoneLayer.className="structure-zone-layer";msChartEl.appendChild(msZoneLayer);

function msRemoveLines(){for(const item of msLines){try{candles.removePriceLine(item)}catch(e){}}msLines=[];for(const s of msTrendSeries){try{chart.removeSeries(s)}catch(e){}}msTrendSeries=[];}
function msPriceLine(price,title,color,style=2){const value=Number(price);if(!Number.isFinite(value))return;try{msLines.push(candles.createPriceLine({price:value,color,lineWidth:1,lineStyle:style,axisLabelVisible:true,title}));}catch(e){console.warn("Market structure line failed",e);}}
function msTrendLine(lineDef,color,title){if(!lineDef)return;const p1=Number(lineDef.start_price),p2=Number(lineDef.end_price),t1=Number(lineDef.start_time),t2=Number(lineDef.end_time);if(![p1,p2,t1,t2].every(Number.isFinite)||t2<=t1)return;try{const s=chart.addSeries(LightweightCharts.LineSeries,{color,lineWidth:2,priceLineVisible:false,lastValueVisible:false,crosshairMarkerVisible:false,title});s.setData([{time:t1,value:p1},{time:t2,value:p2}]);msTrendSeries.push(s);}catch(e){console.warn("Trendline draw failed",e);}}
function msBand(lower,upper,kind,label){const lo=Number(lower),hi=Number(upper);if(!Number.isFinite(lo)||!Number.isFinite(hi)||hi<=lo)return;let yTop=null,yBottom=null;try{yTop=candles.priceToCoordinate(hi);yBottom=candles.priceToCoordinate(lo);}catch(e){return;}if(yTop==null||yBottom==null)return;const top=Math.min(yTop,yBottom),height=Math.max(2,Math.abs(yBottom-yTop));const band=document.createElement("div");band.className=`structure-zone ${kind.toLowerCase()}`;band.style.top=`${top}px`;band.style.height=`${height}px`;const tag=document.createElement("span");tag.textContent=label;band.appendChild(tag);msZoneLayer.appendChild(band);}
function msZoneText(zone){return zone?`${num(zone.lower)} – ${num(zone.upper)}`:"—";}

function msRenderPanel(snapshot){
  const panel=document.getElementById("structurePanel");if(!panel)return;if(!snapshot){panel.innerHTML=`<div class="muted">بانتظار بيانات Market Structure...</div>`;return;}
  const event=snapshot.structure_event,fvg=(snapshot.fvg_zones||[])[0],ob=snapshot.order_block,liq=snapshot.liquidity||{},sweep=liq.sweep,eh=(liq.equal_highs||[])[0],el=(liq.equal_lows||[])[0],channel=snapshot.trend_channel;
  const eventClass=event?.direction==="BULLISH"?"good":event?.direction==="BEARISH"?"bad":"neutral";
  const sweepClass=sweep?.direction==="BULLISH"?"good":sweep?.direction==="BEARISH"?"bad":"neutral";
  panel.innerHTML=`
    <div class="structure-kpi"><small>هيكل ${TF_LABEL[tf]||tf}</small><b>${MS_STATE_AR[snapshot.structure]||snapshot.structure||"—"}</b></div>
    <div class="structure-kpi"><small>Swing High</small><b>${num(snapshot.swing_high)}</b></div>
    <div class="structure-kpi"><small>Swing Low</small><b>${num(snapshot.swing_low)}</b></div>
    <div class="structure-kpi"><small>آخر كسر</small><b class="${eventClass}">${event?MS_EVENT_AR[event.kind]||event.kind:"لا يوجد حديثًا"}</b></div>
    <div class="structure-kpi"><small>Equal High</small><b>${eh?`${num(eh.level)} · ${eh.touches} لمس`:"—"}</b></div>
    <div class="structure-kpi"><small>Equal Low</small><b>${el?`${num(el.level)} · ${el.touches} لمس`:"—"}</b></div>
    <div class="structure-kpi"><small>Liquidity Sweep</small><b class="${sweepClass}">${sweep?(sweep.direction==="BULLISH"?"سحب سيولة سفلي ↑":"سحب سيولة علوي ↓"):"—"}</b></div>
    <div class="structure-kpi"><small>Trend / Channel</small><b>${channel?(CHANNEL_AR[channel.kind]||channel.kind):"—"}</b></div>
    <div class="structure-kpi"><small>أقرب FVG</small><b>${fvg?`${fvg.kind==="BULLISH"?"صاعد":"هابط"} ${msZoneText(fvg)}`:"—"}</b></div>
    <div class="structure-kpi"><small>Order Block*</small><b>${ob?`${ob.kind==="BULLISH"?"صاعد":"هابط"} ${msZoneText(ob)}`:"—"}</b></div>
    <div class="structure-disclaimer">* Order Block كشف آلي تجريبي. Equal High/Low وLiquidity Sweep مناطق احتمالية وليست ضمانًا لانعكاس السعر.</div>`;
}

function msDraw(force=false){
  const snapshot=lastState?.snapshots?.[tf];
  const sig=JSON.stringify({tf,structure:snapshot?.structure,high:snapshot?.swing_high,low:snapshot?.swing_low,event:snapshot?.structure_event,fvg:(snapshot?.fvg_zones||[]).slice(0,2),ob:snapshot?.order_block,liq:snapshot?.liquidity,channel:snapshot?.trend_channel,structureOn:msShowStructure,zonesOn:msShowZones,liquidityOn:msShowLiquidity,channelOn:msShowChannel});
  if(!force&&sig===msLastSignature)return;msLastSignature=sig;msRemoveLines();msZoneLayer.innerHTML="";msRenderPanel(snapshot);if(!snapshot)return;

  if(msShowStructure){
    msPriceLine(snapshot.swing_high,"SWING H","#38bdf8",3);msPriceLine(snapshot.swing_low,"SWING L","#38bdf8",3);
    const event=snapshot.structure_event;if(event){const bullish=event.direction==="BULLISH",title=event.kind.startsWith("CHOCH")?(bullish?"CHoCH ↑":"CHoCH ↓"):(bullish?"BOS ↑":"BOS ↓");msPriceLine(event.level,title,bullish?"#22c55e":"#ef4444",1);}
  }

  if(msShowZones){
    (snapshot.fvg_zones||[]).slice(0,2).forEach((z,i)=>{const bullish=z.kind==="BULLISH";msPriceLine(z.upper,`FVG${i+1} U`,bullish?"#34d399":"#fb7185",3);msPriceLine(z.lower,`FVG${i+1} L`,bullish?"#34d399":"#fb7185",3);msBand(z.lower,z.upper,bullish?"fvg-bull":"fvg-bear",`FVG ${bullish?"↑":"↓"}`);});
    const ob=snapshot.order_block;if(ob){const bullish=ob.kind==="BULLISH";msPriceLine(ob.upper,"OB U",bullish?"#14b8a6":"#f97316",2);msPriceLine(ob.lower,"OB L",bullish?"#14b8a6":"#f97316",2);msBand(ob.lower,ob.upper,bullish?"ob-bull":"ob-bear",`OB* ${bullish?"↑":"↓"}`);}
  }

  if(msShowLiquidity){
    const liq=snapshot.liquidity||{};
    (liq.equal_highs||[]).slice(0,2).forEach((z,i)=>{msPriceLine(z.level,`EQH${i+1}`,"#facc15",3);msBand(z.lower,z.upper,"liq-high",`EQH ×${z.touches}`);});
    (liq.equal_lows||[]).slice(0,2).forEach((z,i)=>{msPriceLine(z.level,`EQL${i+1}`,"#22d3ee",3);msBand(z.lower,z.upper,"liq-low",`EQL ×${z.touches}`);});
    const sweep=liq.sweep;if(sweep)msPriceLine(sweep.level,sweep.direction==="BULLISH"?"SWEEP ↑":"SWEEP ↓",sweep.direction==="BULLISH"?"#22c55e":"#ef4444",0);
  }

  if(msShowChannel&&snapshot.trend_channel){
    msTrendLine(snapshot.trend_channel.upper,"#f59e0b","Upper trend");
    msTrendLine(snapshot.trend_channel.lower,"#60a5fa","Lower trend");
  }
}

function msToggle(button,stateSetter){if(!button)return;button.addEventListener("click",()=>{const next=!button.classList.contains("active");button.classList.toggle("active",next);stateSetter(next);msLastSignature="";msDraw(true);});}
msToggle(document.getElementById("structureToggle"),v=>{msShowStructure=v;});
msToggle(document.getElementById("zonesToggle"),v=>{msShowZones=v;});
msToggle(document.getElementById("liquidityToggle"),v=>{msShowLiquidity=v;});
msToggle(document.getElementById("channelToggle"),v=>{msShowChannel=v;});
document.querySelectorAll("#tfButtons button").forEach(btn=>btn.addEventListener("click",()=>{msLastSignature="";setTimeout(()=>msDraw(true),500);}));
window.addEventListener("resize",()=>setTimeout(()=>msDraw(true),150));window.addEventListener("orientationchange",()=>setTimeout(()=>msDraw(true),450));
setInterval(()=>msDraw(false),900);setTimeout(()=>msDraw(true),700);
