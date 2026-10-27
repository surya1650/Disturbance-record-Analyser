'use strict';
const inspectionViews=new Map();
function renderInspectionWorkbench(host,data,row,recordController) {
  const mount=host.querySelector('.inspection-traces');
  if (!data.sample_count) {
    mount.innerHTML='<h3>Recovered header inventory</h3><p>No recoverable samples. The decode reason and original files remain available.</p>'+
      (data.inventory.length?'<table><thead><tr><th>ID</th><th>Kind</th><th>Source label</th><th>Declared units (unverified)</th></tr></thead><tbody>'+data.inventory.map(c=>`<tr><td>${escapeHtml(c.id)}</td><td>${escapeHtml(c.kind)}</td><td>${escapeHtml(c.label)}</td><td>${escapeHtml(c.declared_units||c.units||'Not available')}</td></tr>`).join('')+'</tbody></table>':'<p>No independently readable channel header.</p>');return;
  }
  const key=`${row.incident_id}/${row.number}/${data.file}`;
  const s=inspectionViews.get(key)||DRInspection.create(data);inspectionViews.set(key,s);s.invalidate();
  if(inspectionViews.size>12)inspectionViews.delete(inspectionViews.keys().next().value);
  const byId=new Map(data.channels.map(c=>[c.id,c]));
  const native=new Map(),cursorValues=new Map();
  let page=0,active='A',hoverTimer,hoverController,viewController;
  const pins=()=>Object.entries(s.pins);
  const visible=()=>s.order.filter(id=>s.visible(id));
  const shown=()=>visible().slice(page*8,page*8+8);
  const esc=escapeHtml;
  mount.innerHTML=`<div class="inspection-toolbar"><button data-action="in">Zoom +</button><button data-action="out">Zoom −</button><button data-action="left">← Pan</button><button data-action="right">Pan →</button><button data-action="reset">Reset view</button><span id="inspection-range"></span></div><p class="field-help">Horizontal axis: zero-based sample index. Cursor labels show actual local source seconds where available. No interpolation. Hover to inspect; click to move the selected pin; arrow keys step one sample. Gaps stay blank.</p><div class="inspection-pins"></div><div class="inspection-layout"><details class="inspection-channels" open><summary>Channel slots (${data.channels.length})</summary><div class="inspection-channel-list"></div></details><div class="inspection-plots" tabindex="0" aria-label="Waveform cursors; left and right arrows step selected pin"><div class="inspection-pane analog"><h3>Analog observations</h3><div class="analog-slots"></div></div><div class="inspection-pane digital"><h3>Digital observations</h3><div class="digital-slots"></div></div><div class="inspection-toolbar"><button data-action="prev">Previous channels</button><span class="inspection-page"></span><button data-action="next">Next channels</button></div></div></div><p class="inspection-load" role="status"></p><p class="inspection-delta"></p><div class="table-wrap"><table class="inspection-values"><thead></thead><tbody></tbody></table></div>`;
  function controls() {
    mount.querySelector('.inspection-channel-list').innerHTML=s.order.map(id=>{const c=byId.get(id);return `<div><label><input type="checkbox" data-channel="${id}" ${s.visible(id)?'checked':''}>${id} ${esc(c.label)} <small>${esc(c.units)}</small></label><button data-move="${id}" data-direction="-1" aria-label="Move ${id} up">↑</button><button data-move="${id}" data-direction="1" aria-label="Move ${id} down">↓</button></div>`;}).join('');
    mount.querySelectorAll('[data-channel]').forEach(el=>el.onchange=()=>{s.toggle(el.dataset.channel);page=0;drawSlots();loadView();});
    mount.querySelectorAll('[data-move]').forEach(el=>el.onclick=()=>{s.reorder(el.dataset.move,Number(el.dataset.direction));controls();drawSlots();loadView();});
    mount.querySelector('.inspection-pins').innerHTML=pins().map(([name,index])=>`<label><input type="radio" name="inspection-active" value="${name}" ${name===active?'checked':''}>Pin ${name} <input aria-label="Cursor ${name} sample index" data-pin="${name}" type="number" min="0" max="${s.n-1}" value="${index}"></label>${!['A','B'].includes(name)?`<button data-remove-pin="${name}" aria-label="Remove cursor ${name}">×</button>`:''}`).join('')+'<button data-action="add-pin">Add cursor at hover</button>';
    mount.querySelectorAll('[name=inspection-active]').forEach(el=>el.onchange=()=>active=el.value);
    mount.querySelectorAll('[data-pin]').forEach(el=>el.onchange=()=>movePin(el.dataset.pin,Number(el.value)));
    mount.querySelectorAll('[data-remove-pin]').forEach(el=>el.onclick=()=>{s.removePin(el.dataset.removePin);if(!s.pins[active]&&s.pins[active]!==0)active='A';controls();drawSlots();loadCursors();});
    mount.querySelector('[data-action=add-pin]').onclick=()=>{s.addPin();controls();drawSlots();loadCursors();};
  }
  function drawSlots() {
    for (const kind of ['analog','digital']) {
      const ids=shown().filter(id=>byId.get(id).kind===kind);
      mount.querySelector(`.${kind}-slots`).innerHTML=ids.map(id=>{const c=byId.get(id);return `<div class="inspection-slot"><strong>${id} · ${esc(c.label)} <small>${esc(c.units)}</small></strong><svg data-trace="${id}" viewBox="0 0 900 100" preserveAspectRatio="none" role="img" aria-label="${esc(c.label)} waveform"></svg></div>`;}).join('') || '<p class="muted">No channels of this kind on this page. Choose channels or change page.</p>';
    }
    mount.querySelector('.inspection-page').textContent=`${visible().length?Math.min(page*8+1,visible().length):0}–${Math.min(page*8+8,visible().length)} of ${visible().length} visible channels (${data.channels.length} total)`;
    mount.querySelector('[data-action=prev]').disabled=page===0;
    mount.querySelector('[data-action=next]').disabled=(page+1)*8>=visible().length;
    mount.querySelector('#inspection-range').textContent=`Samples ${Math.ceil(s.view[0])}–${Math.floor(s.view[1])}`;
    mount.querySelectorAll('[data-trace]').forEach(svg=>{
      const indexFrom=e=>{const r=svg.getBoundingClientRect();return s.view[0]+Math.max(0,Math.min(1,(e.clientX-r.left)/r.width))*(s.view[1]-s.view[0]);};
      svg.onpointermove=e=>{s.move('hover',indexFrom(e));cursorValues.delete('hover');drawPaths();values();clearTimeout(hoverTimer);hoverTimer=setTimeout(loadHover,70);};
      svg.onclick=e=>{movePin(active,indexFrom(e));mount.querySelector('.inspection-plots').focus();};
      svg.onwheel=e=>{e.preventDefault();s.zoom(e.deltaY>0?1.5:1/1.5,indexFrom(e));drawSlots();loadView();};
    });
    drawPaths();values();
  }
  function drawPaths() {
    for(const svg of mount.querySelectorAll('[data-trace]')) {
      const c=byId.get(svg.dataset.trace),points=(native.get(c.id)||c.trace).filter(p=>p[0]>=s.view[0]&&p[0]<=s.view[1]);
      const known=points.filter(p=>p[2]!==null).map(p=>p[2]);
      let lo=c.kind==='digital'?-.2:Math.min(...known),hi=c.kind==='digital'?1.2:Math.max(...known);
      if(lo===hi){lo-=1;hi+=1;}const scale=Math.max(Math.abs(lo),Math.abs(hi),1);
      const x=i=>(i-s.view[0])/Math.max(1,s.view[1]-s.view[0])*900,y=v=>92-(v/scale-lo/scale)/((hi/scale-lo/scale)||1)*84;
      const gap=data.time_basis.minimum_interval_s?data.time_basis.minimum_interval_s*8:Infinity;
      const path=DRInspection.segments(points,gap).map(part=>part.map((p,i)=>`${i?(c.kind==='digital'?'H'+x(p[0])+'V':'L'):'M'+x(p[0])+','}${i? (c.kind==='digital'?y(p[2]):x(p[0])+','+y(p[2])):y(p[2])}`).join(' ')).join(' ');
      svg.innerHTML=`<path d="${path}" fill="none" stroke="${c.kind==='digital'?'#986423':'#176d82'}" stroke-width="1.5" vector-effect="non-scaling-stroke"/>`+[['hover',s.hover],...pins()].filter(([,i])=>i>=s.view[0]&&i<=s.view[1]).map(([name,i])=>`<line x1="${x(i)}" x2="${x(i)}" y1="0" y2="100" stroke="${name==='hover'?'#8b919a':name==='A'?'#bb3b51':'#6a4cbb'}" stroke-dasharray="${name==='hover'?'3 4':'0'}"/><text x="${x(i)+4}" y="12">${name}</text>`).join('');
    }
  }
  function values() {
    const names=[...pins().map(([name])=>name),'hover'];
    mount.querySelector('.inspection-values thead').innerHTML='<tr><th>Channel · source units</th>'+names.map(name=>`<th>${name} · sample ${name==='hover'?s.hover:s.pins[name]}</th>`).join('')+'</tr>';
    mount.querySelector('.inspection-values tbody').innerHTML=shown().map(id=>{const c=byId.get(id);return `<tr><th>${id} ${esc(c.label)}<small>${esc(c.units)}</small></th>${names.map(name=>{const point=cursorValues.get(name)?.get(id);return `<td>${esc(DRInspection.value(point))}<small>${point?point[1]===null?'Time not available':`${point[1].toPrecision(9)} local s`:'Awaiting native observation'}</small></td>`;}).join('')}</tr>`;}).join('');
    const first=shown()[0],a=cursorValues.get('A')?.get(first),b=cursorValues.get('B')?.get(first);
    mount.querySelector('.inspection-delta').textContent=a&&b?`B − A: ${DRInspection.delta(a,b).samples} samples · ${DRInspection.delta(a,b).seconds===null?'Time difference not available':(DRInspection.delta(a,b).seconds*1000).toPrecision(9)+' ms (source coordinates)'}`:'B − A: waiting for exact cursor observations.';
  }
  async function getSamples(id,lo,hi,controller) {
    const query=new URLSearchParams({revision:row.number,record:data.file,channel_id:id,start_index:lo,stop_index:hi});
    const response=await fetch(`/api/incidents/${row.incident_id}/inspection/samples?${query}`,{signal:controller.signal});
    const body=await response.json();if(!response.ok)throw new Error(body.detail||'Native observations unavailable.');
    if(body.file!==data.file||body.revision!==row.number||body.channel_id!==id||JSON.stringify(body.source_sha256)!==JSON.stringify(data.source_sha256))throw new Error('Source identity changed; reopen recording.');
    return body.samples;
  }
  async function loadHover() {
    hoverController?.abort();const controller=new AbortController();hoverController=controller;
    recordController.signal.addEventListener('abort',()=>controller.abort(),{once:true,signal:controller.signal});
    const index=s.hover,token=s.request('hover');cursorValues.delete('hover');values();
    try {const entries=await Promise.all(shown().map(async id=>[id,(await getSamples(id,index,index+1,controller))[0]]));
      if(s.accept(token)&&s.hover===index&&!controller.signal.aborted&&host.isConnected){cursorValues.set('hover',new Map(entries));values();}
    }catch(error){if(error.name!=='AbortError'&&s.accept(token))mount.querySelector('.inspection-load').textContent=error.message;}
  }
  async function loadCursors() {
    cursorValues.clear();values();
    const token=s.request('pins');
    try {const entries=await Promise.all(pins().map(async([name,index])=>[name,new Map(await Promise.all(shown().map(async id=>[id,(await getSamples(id,index,index+1,recordController))[0]])))]));
      if(s.accept(token)&&!recordController.signal.aborted&&host.isConnected){for(const [name,entry]of entries)cursorValues.set(name,entry);values();}
    }catch(error){if(error.name!=='AbortError'&&s.accept(token))mount.querySelector('.inspection-load').textContent=error.message;}
    loadHover();
  }
  async function loadView() {
    viewController?.abort();hoverController?.abort();s.invalidate();native.clear();cursorValues.clear();drawPaths();values();
    const controller=new AbortController();viewController=controller;
    recordController.signal.addEventListener('abort',()=>controller.abort(),{once:true,signal:controller.signal});
    const lo=Math.ceil(s.view[0]),hi=Math.floor(s.view[1])+1,token=s.request('view');
    const status=mount.querySelector('.inspection-load');status.textContent=hi-lo<=20000?'Loading exact native observations…':'Display envelopes; zoom to ≤20000 samples for native paths. Cursors always use exact observations.';
    if(hi-lo<=20000){try{const entries=await Promise.all(shown().map(async id=>[id,await getSamples(id,lo,hi,controller)]));
      if(s.accept(token)&&!controller.signal.aborted&&host.isConnected){for(const[id,points]of entries)native.set(id,points);status.textContent='Native observations loaded. Unknown states and missing amplitudes stay blank.';drawPaths();}
    }catch(error){if(error.name!=='AbortError'&&s.accept(token)){status.textContent=error.message;native.clear();drawPaths();}}}
    if(s.accept(token)&&!controller.signal.aborted)loadCursors();
  }
  function movePin(name,index){s.move(name,index);controls();drawPaths();loadCursors();}
  mount.querySelector('.inspection-plots').onkeydown=e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();movePin(active,s.pins[active]+(e.key==='ArrowLeft'?-1:1));}};
  mount.querySelectorAll('[data-action]').forEach(button=>{if(button.dataset.action==='add-pin')return;button.onclick=()=>{const action=button.dataset.action;if(action==='in')s.zoom(.5);if(action==='out')s.zoom(2);if(action==='left')s.pan(-.5);if(action==='right')s.pan(.5);if(action==='reset')s.reset();if(action==='prev')page--;if(action==='next')page++;drawSlots();loadView();};});
  recordController.signal.addEventListener('abort',()=>{clearTimeout(hoverTimer);hoverController?.abort();viewController?.abort();s.invalidate();},{once:true});
  controls();drawSlots();loadView();
}
