// V1.3 Market Structure visual layer.
// This file deliberately consumes the structured backend snapshot instead of
// re-inventing the signal in the browser.
let msLines = [];
let msShowStructure = true;
let msShowZones = true;
let msLastSignature = "";

const MS_EVENT_AR = {
  BOS_UP: "BOS صاعد ↑",
  BOS_DOWN: "BOS هابط ↓",
  CHOCH_UP: "CHoCH صاعد ↑",
  CHOCH_DOWN: "CHoCH هابط ↓",
};
const MS_STATE_AR = {BULLISH:"صاعد",BEARISH:"هابط",RANGE:"نطاق",NEUTRAL:"محايد"};

const msChartEl = document.getElementById("chart");
const msZoneLayer = document.createElement("div");
msZoneLayer.className = "structure-zone-layer";
msChartEl.appendChild(msZoneLayer);

function msRemoveLines(){
  for(const item of msLines){
    try{ candles.removePriceLine(item); }catch(e){}
  }
  msLines=[];
}

function msPriceLine(price,title,color,style=2){
  const value=Number(price);
  if(!Number.isFinite(value)) return;
  try{
    msLines.push(candles.createPriceLine({
      price:value,color,lineWidth:1,lineStyle:style,axisLabelVisible:true,title
    }));
  }catch(e){ console.warn("Market structure line failed",e); }
}

function msBand(lower,upper,kind,label){
  const lo=Number(lower), hi=Number(upper);
  if(!Number.isFinite(lo)||!Number.isFinite(hi)||hi<=lo) return;
  let yTop=null,yBottom=null;
  try{
    yTop=candles.priceToCoordinate(hi);
    yBottom=candles.priceToCoordinate(lo);
  }catch(e){ return; }
  if(yTop==null||yBottom==null) return;
  const top=Math.min(yTop,yBottom), height=Math.max(2,Math.abs(yBottom-yTop));
  const band=document.createElement("div");
  band.className=`structure-zone ${kind.toLowerCase()}`;
  band.style.top=`${top}px`;
  band.style.height=`${height}px`;
  const tag=document.createElement("span");
  tag.textContent=label;
  band.appendChild(tag);
  msZoneLayer.appendChild(band);
}

function msZoneText(zone){
  if(!zone) return "—";
  return `${num(zone.lower)} – ${num(zone.upper)}`;
}

function msRenderPanel(snapshot){
  const panel=document.getElementById("structurePanel");
  if(!panel) return;
  if(!snapshot){
    panel.innerHTML=`<div class="muted">بانتظار بيانات Market Structure...</div>`;
    return;
  }
  const event=snapshot.structure_event;
  const fvg=(snapshot.fvg_zones||[])[0];
  const ob=snapshot.order_block;
  const eventClass=event?.direction==="BULLISH"?"good":event?.direction==="BEARISH"?"bad":"neutral";
  panel.innerHTML=`
    <div class="structure-kpi"><small>هيكل ${TF_LABEL[tf]||tf}</small><b>${MS_STATE_AR[snapshot.structure]||snapshot.structure||"—"}</b></div>
    <div class="structure-kpi"><small>Swing High</small><b>${num(snapshot.swing_high)}</b></div>
    <div class="structure-kpi"><small>Swing Low</small><b>${num(snapshot.swing_low)}</b></div>
    <div class="structure-kpi"><small>آخر كسر</small><b class="${eventClass}">${event?MS_EVENT_AR[event.kind]||event.kind:"لا يوجد حديثًا"}</b></div>
    <div class="structure-kpi"><small>أقرب FVG</small><b>${fvg?`${fvg.kind==="BULLISH"?"صاعد":"هابط"} ${msZoneText(fvg)}`:"—"}</b></div>
    <div class="structure-kpi"><small>Order Block*</small><b>${ob?`${ob.kind==="BULLISH"?"صاعد":"هابط"} ${msZoneText(ob)}`:"—"}</b></div>
    <div class="structure-disclaimer">* Order Block هنا كشف آلي تجريبي: آخر شمعة معاكسة قبل BOS/CHoCH، وليس تأكيدًا مؤسسيًا.</div>`;
}

function msDraw(force=false){
  const snapshot=lastState?.snapshots?.[tf];
  const sig=JSON.stringify({
    tf,
    structure:snapshot?.structure,
    high:snapshot?.swing_high,
    low:snapshot?.swing_low,
    event:snapshot?.structure_event,
    fvg:(snapshot?.fvg_zones||[]).slice(0,2),
    ob:snapshot?.order_block,
    structureOn:msShowStructure,
    zonesOn:msShowZones,
  });
  if(!force && sig===msLastSignature) return;
  msLastSignature=sig;
  msRemoveLines();
  msZoneLayer.innerHTML="";
  msRenderPanel(snapshot);
  if(!snapshot) return;

  if(msShowStructure){
    msPriceLine(snapshot.swing_high,"SWING H","#38bdf8",3);
    msPriceLine(snapshot.swing_low,"SWING L","#38bdf8",3);
    const event=snapshot.structure_event;
    if(event){
      const bullish=event.direction==="BULLISH";
      const title=event.kind.startsWith("CHOCH")?(bullish?"CHoCH ↑":"CHoCH ↓"):(bullish?"BOS ↑":"BOS ↓");
      msPriceLine(event.level,title,bullish?"#22c55e":"#ef4444",1);
    }
  }

  if(msShowZones){
    const zones=(snapshot.fvg_zones||[]).slice(0,2);
    zones.forEach((z,i)=>{
      const bullish=z.kind==="BULLISH";
      msPriceLine(z.upper,`FVG${i+1} U`,bullish?"#34d399":"#fb7185",3);
      msPriceLine(z.lower,`FVG${i+1} L`,bullish?"#34d399":"#fb7185",3);
      msBand(z.lower,z.upper,bullish?"fvg-bull":"fvg-bear",`FVG ${bullish?"↑":"↓"}`);
    });
    const ob=snapshot.order_block;
    if(ob){
      const bullish=ob.kind==="BULLISH";
      msPriceLine(ob.upper,"OB U",bullish?"#14b8a6":"#f97316",2);
      msPriceLine(ob.lower,"OB L",bullish?"#14b8a6":"#f97316",2);
      msBand(ob.lower,ob.upper,bullish?"ob-bull":"ob-bear",`OB* ${bullish?"↑":"↓"}`);
    }
  }
}

function msToggle(button,stateSetter){
  if(!button) return;
  button.addEventListener("click",()=>{
    const next=!button.classList.contains("active");
    button.classList.toggle("active",next);
    stateSetter(next);
    msLastSignature="";
    msDraw(true);
  });
}

msToggle(document.getElementById("structureToggle"),v=>{msShowStructure=v;});
msToggle(document.getElementById("zonesToggle"),v=>{msShowZones=v;});

document.querySelectorAll("#tfButtons button").forEach(btn=>btn.addEventListener("click",()=>{
  msLastSignature="";
  setTimeout(()=>msDraw(true),500);
}));
window.addEventListener("resize",()=>setTimeout(()=>msDraw(true),150));
window.addEventListener("orientationchange",()=>setTimeout(()=>msDraw(true),450));

// Redraw zones after auto-scaling or a fresh backend snapshot. The signature
// prevents expensive work when nothing changed.
setInterval(()=>msDraw(false),900);
setTimeout(()=>msDraw(true),700);
