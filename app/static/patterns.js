// V1.5 Pattern visual layer. Backend computes patterns from confirmed candles;
// the browser renders them and never invents a signal from the live unfinished bar.
let patternLines=[];
let patternsVisible=true;
let lastPatternSignature="";

const PATTERN_AR={
  DOJI:"دوجي",HAMMER:"مطرقة",SHOOTING_STAR:"شهاب هابط",
  BULLISH_ENGULFING:"ابتلاع صاعد",BEARISH_ENGULFING:"ابتلاع هابط",
  INSIDE_BAR:"Inside Bar",MORNING_STAR:"نجمة الصباح",EVENING_STAR:"نجمة المساء",
  DOUBLE_TOP:"قمة مزدوجة",DOUBLE_BOTTOM:"قاع مزدوج",
  SYMMETRICAL_TRIANGLE:"مثلث متماثل",ASCENDING_TRIANGLE:"مثلث صاعد",DESCENDING_TRIANGLE:"مثلث هابط"
};

function patternName(p){return PATTERN_AR[p?.name]||p?.name||"—";}
function patternClass(direction){return direction==="BULLISH"?"good":direction==="BEARISH"?"bad":"neutral";}
function patternDir(direction){return direction==="BULLISH"?"صاعد":direction==="BEARISH"?"هابط":"محايد";}
function removePatternLines(){for(const l of patternLines){try{candles.removePriceLine(l)}catch(e){}}patternLines=[];}
function pLine(price,title,color,style=3){const value=Number(price);if(!Number.isFinite(value))return;try{patternLines.push(candles.createPriceLine({price:value,color,lineWidth:1,lineStyle:style,axisLabelVisible:true,title}));}catch(e){}}

function topPattern(snapshot){
  const classical=(snapshot?.chart_patterns||[])[0];
  const candle=(snapshot?.candlestick_patterns||[])[0];
  if(classical&&Number(classical.strength||0)>=Number(candle?.strength||0))return classical;
  return candle||classical||null;
}

function renderPatternMatrix(snapshots={}){
  const matrix=document.getElementById("patternMatrix");if(!matrix)return;
  matrix.innerHTML=TF_ORDER.map(k=>{const s=snapshots[k],p=topPattern(s);return `<div class="pattern-mini"><b>${TF_LABEL[k]||k}</b>${p?`<span class="${patternClass(p.direction)}">${patternName(p)}</span><small>${patternDir(p.direction)} · ${Math.round(Number(p.strength||0)*100)}%</small>`:`<span class="muted">لا نموذج قوي</span><small>Bias ${num(s?.pattern_bias||0,2)}</small>`}</div>`;}).join("");
}

function renderSelectedPatterns(snapshot){
  const panel=document.getElementById("patternPanel");if(!panel)return;
  if(!snapshot){panel.innerHTML=`<div class="muted">بانتظار بيانات النماذج...</div>`;return;}
  const candlesP=snapshot.candlestick_patterns||[],charts=snapshot.chart_patterns||[];
  const candleHtml=candlesP.slice(0,4).map(p=>`<div class="pattern-row"><span>${patternName(p)}</span><b class="${patternClass(p.direction)}">${patternDir(p.direction)}</b><small>${Math.round(Number(p.strength||0)*100)}%</small></div>`).join("")||`<div class="muted pattern-empty">لا نموذج شموع حديث</div>`;
  const chartHtml=charts.slice(0,3).map(p=>`<div class="pattern-row"><span>${patternName(p)}</span><b class="${patternClass(p.direction)}">${patternDir(p.direction)}</b><small>${p.confirmed?"مؤكد":"قيد التكوين"}</small></div>`).join("")||`<div class="muted pattern-empty">لا نموذج فني مؤكد</div>`;
  panel.innerHTML=`<div class="pattern-column"><h4>نماذج الشموع · ${TF_LABEL[tf]||tf}</h4>${candleHtml}</div><div class="pattern-column"><h4>النماذج الفنية</h4>${chartHtml}</div><div class="pattern-bias"><span>Pattern Bias</span><b class="${Number(snapshot.pattern_bias||0)>0.05?"good":Number(snapshot.pattern_bias||0)<-0.05?"bad":"neutral"}">${num(snapshot.pattern_bias,3)}</b></div>`;
}

function drawPatternLevels(force=false){
  const snapshot=lastState?.snapshots?.[tf];
  const sig=JSON.stringify({tf,visible:patternsVisible,patterns:snapshot?.chart_patterns,bias:snapshot?.pattern_bias});
  if(!force&&sig===lastPatternSignature)return;lastPatternSignature=sig;removePatternLines();renderSelectedPatterns(snapshot);renderPatternMatrix(lastState?.snapshots||{});
  if(!patternsVisible||!snapshot)return;
  for(const p of (snapshot.chart_patterns||[]).slice(0,3)){
    const bullish=p.direction==="BULLISH",color=bullish?"#22c55e":p.direction==="BEARISH"?"#ef4444":"#f59e0b";
    if(p.level!=null)pLine(p.level,patternName(p),color,3);
    if(p.neckline!=null)pLine(p.neckline,"NECKLINE",color,p.confirmed?0:3);
    if(p.upper_level!=null)pLine(p.upper_level,"PATTERN U","#f59e0b",3);
    if(p.lower_level!=null)pLine(p.lower_level,"PATTERN L","#60a5fa",3);
  }
}

const patternToggle=document.getElementById("patternToggle");
if(patternToggle)patternToggle.addEventListener("click",()=>{patternsVisible=!patternsVisible;patternToggle.classList.toggle("active",patternsVisible);lastPatternSignature="";drawPatternLevels(true);});
document.querySelectorAll("#tfButtons button").forEach(btn=>btn.addEventListener("click",()=>{lastPatternSignature="";setTimeout(()=>drawPatternLevels(true),520);}));
window.addEventListener("resize",()=>setTimeout(()=>drawPatternLevels(true),180));
setInterval(()=>drawPatternLevels(false),1000);
setTimeout(()=>drawPatternLevels(true),850);
