(() => {
  const style=document.createElement('style');
  style.textContent=`
    .sig-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:10px}.sig-box{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:10px}.sig-box small{display:block;color:var(--muted);font-size:11px}.sig-box b{display:block;margin-top:4px;font-size:14px}.sig-note{margin-top:10px;padding:10px;border-radius:9px;background:rgba(20,184,166,.07);border:1px solid rgba(20,184,166,.24);font-size:12px}
    @media(max-width:900px){.sig-grid{grid-template-columns:1fr 1fr}.sig-grid .sig-box:last-child{grid-column:1/-1}}
  `;
  document.head.appendChild(style);
  const archive=document.getElementById('historicalArchiveSection');
  const host=archive||document.getElementById('historicalAnalogSection')||document.getElementById('learningSection');
  if(host){
    const section=document.createElement('section');section.id='signatureCacheSection';section.className='card section-context';
    section.innerHTML=`<div class="section-title-row"><div><div class="card-title">Historical Signature Cache</div><small class="muted">بصمات سوق مضغوطة لتسريع مقارنة مئات الحالات السابقة</small></div><button id="refreshSignatures" class="primary" type="button">تحديث</button></div><div id="signatureStats" class="sig-grid"><div class="muted">بانتظار cache...</div></div><div id="signatureNote" class="sig-note">يُبنى في الخلفية ولا يغيّر MASTER.</div>`;
    host.parentNode.insertBefore(section,host.nextSibling);
  }
  const n=(x,d=2)=>x==null?'—':Number(x).toLocaleString(undefined,{maximumFractionDigits:d});
  function render(a){
    const stats=document.getElementById('signatureStats'),note=document.getElementById('signatureNote');if(!stats)return;
    const c=a?.signature_cache||{};
    stats.innerHTML=`<div class="sig-box"><small>Cache status</small><b>${c.status||'EMPTY'}</b></div><div class="sig-box"><small>Signatures</small><b>${Number(c.candidates||0).toLocaleString()}</b></div><div class="sig-box"><small>Scanned now</small><b>${Number(a?.signature_candidates_scanned||0).toLocaleString()}</b></div><div class="sig-box"><small>Build time</small><b>${n(c.build_seconds,3)}s</b></div><div class="sig-box"><small>Cache used</small><b>${a?.signature_cache_used?'YES':'FALLBACK'}</b></div>`;
    if(note)note.innerHTML=`⚡ Target cache ≈ <b>${Number(c.target_candidates||720).toLocaleString()}</b> states · stride ${c.stride??'—'} · anchor bars ${Number(c.anchor_bars||a?.history_bars_scanned||0).toLocaleString()} · Historical evidence remains <b>SHADOW_ONLY</b>.`;
  }
  async function refresh(){const b=document.getElementById('refreshSignatures');if(b)b.disabled=true;try{const r=await fetch('/api/historical-analogs'),a=await r.json();render(a);}catch(e){console.warn('Signature cache failed',e);}finally{if(b)b.disabled=false;}}
  const b=document.getElementById('refreshSignatures');if(b)b.addEventListener('click',refresh);
  refresh();setInterval(refresh,15000);
  fetch('/api/version').then(r=>r.json()).then(v=>{document.title=`${v.name} ${v.label}`;const el=document.querySelector('h1 span');if(el)el.textContent=v.label;}).catch(()=>{});
})();
