'use strict';
const inspectionViews=new Map();
function renderInspectionWorkbench(host,data,row,recordController) {
  const mount=host.querySelector('.inspection-traces');
  if (!data.sample_count) {
    mount.innerHTML='<h3>Recovered header inventory</h3><p>No recoverable samples. The decode reason and original files remain available.</p>'+
      (data.inventory.length?'<table><thead><tr><th>ID</th><th>Kind</th><th>Source label</th><th>Declared units (unverified)</th></tr></thead><tbody>'+data.inventory.map(c=>`<tr><td>${escapeHtml(c.id)}</td><td>${escapeHtml(c.kind)}</td><td>${escapeHtml(c.label)}</td><td>${escapeHtml(c.declared_units||c.units||'Not available')}</td></tr>`).join('')+'</tbody></table>':'<p>No independently readable channel header.</p>');return;
  }
  const key=`${row.incident_id}/${row.number}/${data.file}`;
  const saved=inspectionViews.get(key);
  const s=saved?.sourceIdentity===DRInspection.identity(data.source_sha256)?saved:DRInspection.create(data);inspectionViews.set(key,s);s.invalidate();
  if(inspectionViews.size>12)inspectionViews.delete(inspectionViews.keys().next().value);
  const byId=new Map(data.channels.map(c=>[c.id,c]));
  const native=new Map(),cursorValues=new Map();
  let page=0,active='A',follow='A',analysis=null,reference='',hoverTimer,hoverController,viewController;
  const pins=()=>Object.entries(s.pins);
  const visible=()=>s.order.filter(id=>s.visible(id));
  const shown=()=>visible().slice(page*8,page*8+8);
  const esc=escapeHtml;
  mount.innerHTML=`<div class="inspection-toolbar"><button data-action="in">Zoom +</button><button data-action="out">Zoom −</button><button data-action="left">← Pan</button><button data-action="right">Pan →</button><button data-action="reset">Reset view</button><span id="inspection-range"></span></div><p class="field-help">Horizontal axis: zero-based sample index. Cursor labels show actual local source seconds where available. No interpolation. Hover to inspect; click to move the selected pin; arrow keys step one sample. Gaps stay blank.</p><div class="inspection-pins"></div><div class="inspection-display"><div class="inspection-layout"><details class="inspection-channels" open><summary>Channel slots (${data.channels.length})</summary><div class="inspection-channel-list"></div></details><div class="inspection-plots" tabindex="0" aria-label="Waveform cursors; left and right arrows step selected pin"><div class="inspection-pane analog"><h3>Analog observations</h3><div class="analog-slots"></div></div><div class="inspection-pane digital"><h3>Digital observations</h3><div class="digital-slots"></div></div><div class="inspection-toolbar"><button data-action="prev">Previous channels</button><span class="inspection-page"></span><button data-action="next">Next channels</button></div></div></div><aside class="inspection-vector"><h3>Live vector diagram</h3><p class="inspection-live-cursor"></p><label>Angle reference <select class="inspection-reference" aria-label="Vector angle reference"></select></label><div class="inspection-vector-charts"></div></aside></div><p class="inspection-load" role="status"></p><p class="inspection-delta"></p><details class="inspection-cursor-details"><summary>All cursor values and delta times</summary><div class="table-wrap"><table class="inspection-values"><thead></thead><tbody></tbody></table></div></details>`;
  mount.querySelector('.inspection-reference').onchange=e=>{reference=e.target.value;values();};
  const phase=id=>s.phases[id]||DRInspection.phaseFor(byId.get(id),data.channels);
  const color=id=>s.colors[phase(id)];
  function controls() {
    mount.querySelector('.inspection-channel-list').innerHTML='<p class="field-help">Phase colour and overlay group are display choices.</p><div class="inspection-palette">'+Object.entries(s.colors).map(([name,c])=>`<label>${name==='unknown'?'Other':name}<input type="color" aria-label="Phase ${name} colour" data-phase-color="${name}" value="${c}"></label>`).join('')+'</div>'+s.order.map(id=>{const c=byId.get(id);return `<div class="inspection-channel-choice"><label><input type="checkbox" data-channel="${id}" ${s.visible(id)?'checked':''}>${id} ${esc(c.label)} <small>${esc(c.units)}</small></label><button data-move="${id}" data-direction="-1" aria-label="Move ${id} up">↑</button><button data-move="${id}" data-direction="1" aria-label="Move ${id} down">↓</button><select aria-label="${id} display phase" data-phase="${id}">${Object.keys(s.colors).map(p=>`<option value="${p}" ${p===phase(id)?'selected':''}>${p==='unknown'?'Other':p}</option>`).join('')}</select>${c.kind==='analog'?`<select aria-label="${id} overlay group" data-group="${id}"><option value="">Separate slot</option>${['1','2','3','4'].map(g=>`<option value="${g}" ${s.groups[id]===g?'selected':''}>Overlay ${g}</option>`).join('')}</select>`:''}</div>`;}).join('');
    mount.querySelectorAll('[data-phase-color]').forEach(el=>el.onchange=()=>{s.setColour(el.dataset.phaseColor,el.value);drawPaths();values();});
    mount.querySelectorAll('[data-phase]').forEach(el=>el.onchange=()=>{s.phases[el.dataset.phase]=el.value;drawPaths();values();});
    mount.querySelectorAll('[data-group]').forEach(el=>el.onchange=()=>{s.groups[el.dataset.group]=el.value;drawSlots();});
    mount.querySelectorAll('[data-channel]').forEach(el=>el.onchange=()=>{s.toggle(el.dataset.channel);page=0;drawSlots();loadView();});
    mount.querySelectorAll('[data-move]').forEach(el=>el.onclick=()=>{s.reorder(el.dataset.move,Number(el.dataset.direction));controls();drawSlots();loadView();});
    mount.querySelector('.inspection-pins').innerHTML=pins().map(([name,index])=>`<label><input type="radio" name="inspection-active" value="${name}" ${name===active?'checked':''}>Pin ${name} <input aria-label="Cursor ${name} sample index" data-pin="${name}" type="number" min="0" max="${s.n-1}" value="${index}"></label>${!['A','B'].includes(name)?`<button data-remove-pin="${name}" aria-label="Remove cursor ${name}">×</button>`:''}`).join('')+'<button data-action="add-pin">Add cursor at hover</button>';
    mount.querySelectorAll('[name=inspection-active]').forEach(el=>el.onchange=()=>active=el.value);
    mount.querySelectorAll('[data-pin]').forEach(el=>el.onchange=()=>movePin(el.dataset.pin,Number(el.value)));
    mount.querySelectorAll('[data-remove-pin]').forEach(el=>el.onclick=()=>{s.removePin(el.dataset.removePin);if(!s.pins[active]&&s.pins[active]!==0)active='A';controls();drawSlots();loadCursors();});
    mount.querySelector('[data-action=add-pin]').onclick=()=>{try{s.addPin();controls();drawSlots();loadCursors();}catch(error){mount.querySelector('.inspection-load').textContent=error.message;}};
  }
  function drawSlots() {
    for (const kind of ['analog','digital']) {
      const groups=DRInspection.groupChannels(shown().map(id=>byId.get(id)).filter(c=>c.kind===kind),s);
      mount.querySelector(`.${kind}-slots`).innerHTML=groups.map(group=>{const c=group[0],id=group.map(c=>c.id).join(',');return `<div class="inspection-slot"><strong>${group.map(c=>c.id+' · '+esc(c.label)).join(' / ')} <small>${esc(c.units)}</small></strong><div class="inspection-trace-readings"><svg data-trace="${id}" viewBox="0 0 900 100" preserveAspectRatio="none" role="img" aria-label="${esc(c.label)} waveform"></svg><div class="inspection-inline-values" data-reading="${id}"></div></div></div>`;}).join('') || '<p class="muted">No channels of this kind on this page. Choose channels or change page.</p>';
    }
    mount.querySelector('.inspection-page').textContent=`${visible().length?Math.min(page*8+1,visible().length):0}–${Math.min(page*8+8,visible().length)} of ${visible().length} visible channels (${data.channels.length} total)`;
    mount.querySelector('[data-action=prev]').disabled=page===0;
    mount.querySelector('[data-action=next]').disabled=(page+1)*8>=visible().length;
    mount.querySelector('#inspection-range').textContent=`Samples ${Math.ceil(s.view[0])}–${Math.floor(s.view[1])}`;
    mount.querySelectorAll('[data-trace]').forEach(svg=>{
      const indexFrom=e=>{const r=svg.getBoundingClientRect();return s.view[0]+Math.max(0,Math.min(1,(e.clientX-r.left)/r.width))*(s.view[1]-s.view[0]);};
      svg.onpointermove=e=>{follow='hover';s.move('hover',indexFrom(e));cursorValues.delete('hover');drawPaths();values();clearTimeout(hoverTimer);hoverTimer=setTimeout(loadHover,70);};
      svg.onclick=e=>{movePin(active,indexFrom(e));mount.querySelector('.inspection-plots').focus();};
      svg.onwheel=e=>{e.preventDefault();s.zoom(e.deltaY>0?1.5:1/1.5,indexFrom(e));drawSlots();loadView();};
    });
    drawPaths();values();
  }
  function drawPaths() {
    for(const svg of mount.querySelectorAll('[data-trace]')) {
      const ids=svg.dataset.trace.split(','),channels=ids.map(id=>byId.get(id));
      const series=channels.map(c=>({c,points:(native.get(c.id)||c.trace).filter(p=>p[0]>=s.view[0]&&p[0]<=s.view[1])}));
      let lo=Infinity,hi=-Infinity;for(const {points} of series)for(const p of points)if(p[2]!==null){lo=Math.min(lo,p[2]);hi=Math.max(hi,p[2]);}
      if(channels[0].kind==='digital'){lo=-.2;hi=1.2;}if(!Number.isFinite(lo)){lo=-1;hi=1;}if(lo===hi){lo-=1;hi+=1;}
      const scale=Math.max(Math.abs(lo),Math.abs(hi),1),x=i=>(i-s.view[0])/Math.max(1,s.view[1]-s.view[0])*900,y=v=>92-(v/scale-lo/scale)/((hi/scale-lo/scale)||1)*84;
      const gap=data.time_basis.minimum_interval_s?data.time_basis.minimum_interval_s*8:Infinity;
      svg.innerHTML=series.map(({c,points})=>{
        const parts=DRInspection.segments(points,gap),path=parts.map(part=>part.map((p,i)=>`${i?(c.kind==='digital'?'H'+x(p[0])+'V':'L'):'M'+x(p[0])+','}${i?(c.kind==='digital'?y(p[2]):x(p[0])+','+y(p[2])):y(p[2])}`).join(' ')).join(' ');
        return `<path d="${path}" fill="none" stroke="${color(c.id)}" stroke-width="1.5" vector-effect="non-scaling-stroke"/>`+parts.filter(p=>p.length===1).map(part=>`<circle cx="${x(part[0][0])}" cy="${y(part[0][2])}" r="2" fill="${color(c.id)}"/>`).join('');
      }).join('')+[['hover',s.hover],...pins()].filter(([,i])=>i>=s.view[0]&&i<=s.view[1]).map(([name,i])=>`<line x1="${x(i)}" x2="${x(i)}" y1="0" y2="100" stroke="${name==='hover'?'#8b919a':name==='A'?'#bb3b51':'#6a4cbb'}" stroke-dasharray="${name==='hover'?'3 4':'0'}"/><text x="${x(i)+4}" y="12">${name}</text>`).join('');
    }
  }
  function values() {
    const names=[...pins().map(([name])=>name),'hover'];
    mount.querySelector('.inspection-values thead').innerHTML='<tr><th>Channel · source units</th>'+names.map(name=>`<th>${name} · sample ${name==='hover'?s.hover:s.pins[name]}</th>`).join('')+'</tr>';
    mount.querySelector('.inspection-values tbody').innerHTML=shown().map(id=>{const c=byId.get(id);return `<tr><th>${id} ${esc(c.label)}<small>${esc(c.units)}</small></th>${names.map(name=>{const point=cursorValues.get(name)?.get(id);return `<td>${esc(DRInspection.value(point))}<small>${point?point[1]===null?'Time not available':`${point[1].toPrecision(9)} local s`:'Awaiting native observation'}</small></td>`;}).join('')}</tr>`;}).join('');
    const index=follow==='hover'?s.hover:s.pins[follow],points=cursorValues.get(follow),reading=DRReadings.view(analysis,index,reference);
    const options=(analysis?.channels||[]).map(c=>`<option value="${esc(c.id)}">${esc(c.id+' '+c.label)}</option>`).join('');
    const ref=mount.querySelector('.inspection-reference');if(ref.innerHTML!==options)ref.innerHTML=options;ref.value=reading.reference;
    for(const el of mount.querySelectorAll('[data-reading]'))el.innerHTML=el.dataset.reading.split(',').map(id=>DRReadings.readingMarkup(byId.get(id),points?.get(id),reading.channels.get(id),follow)).join('');
    mount.querySelector('.inspection-vector-charts').innerHTML=DRReadings.vectorMarkup(reading,Object.fromEntries(data.channels.map(c=>[c.id,color(c.id)])));
    const current=points?.get(shown()[0]);mount.querySelector('.inspection-live-cursor').textContent=`${follow==='hover'?'Hover':'Cursor '+follow} · sample ${index} · ${current?.[1]===null||!current?'Time unavailable':current[1].toPrecision(7)+' local s'}`;
    const first=shown()[0],a=cursorValues.get('A')?.get(first),b=cursorValues.get('B')?.get(first);
    mount.querySelector('.inspection-delta').textContent=a&&b?`B − A: ${DRInspection.delta(a,b).samples} samples · ${DRInspection.delta(a,b).seconds===null?'Time difference not available':(DRInspection.delta(a,b).seconds*1000).toPrecision(9)+' ms (source coordinates)'}`:'B − A: waiting for exact cursor observations.';
  }
  async function getSamples(id,lo,hi,controller) {
    const query=new URLSearchParams({revision:row.number,record:data.file,channel_id:id,start_index:lo,stop_index:hi});
    const response=await fetch(`/api/incidents/${row.incident_id}/inspection/samples?${query}`,{signal:controller.signal});
    const body=await response.json();if(!response.ok)throw new Error(body.detail||'Native observations unavailable.');
    if(body.file!==data.file||body.revision!==row.number||body.channel_id!==id||DRInspection.identity(body.source_sha256)!==DRInspection.identity(data.source_sha256))throw new Error('Source identity changed; reopen recording.');
    return body.samples;
  }
  function loadHover(){return loadCursors();}
  async function loadCursors() {
    hoverController?.abort();if(recordController.signal.aborted)return;
    const controller=new AbortController();hoverController=controller;
    recordController.signal.addEventListener('abort',()=>controller.abort(),{once:true,signal:controller.signal});
    const names=[...pins(),['hover',s.hover]],ids=shown(),indices=[...new Set(names.map(([,i])=>i))],token=s.request('points');
    cursorValues.clear();values();if(!ids.length)return;
    const current=()=>s.accept(token)&&!controller.signal.aborted&&host.isConnected&&
      names.every(([name,index])=>(name==='hover'?s.hover:s.pins[name])===index)&&ids.join(',')===shown().join(',');
    try {
      let channels=DRInspection.exactPoints(native,ids,indices);
      if(!channels){
        const query=new URLSearchParams({revision:row.number,record:data.file,channel_ids:JSON.stringify(ids),indices:JSON.stringify(indices)});
        const response=await fetch(`/api/incidents/${row.incident_id}/inspection/points?${query}`,{signal:controller.signal});
        const body=await response.json();if(!response.ok)throw new Error(body.detail||'Cursor observations unavailable.');
        if(body.file!==data.file||body.revision!==row.number||DRInspection.identity(body.source_sha256)!==DRInspection.identity(data.source_sha256))throw new Error('Source identity changed; reopen recording.');
        channels=body.channels;
      }
      if(current()){for(const[name,index]of names)cursorValues.set(name,new Map(channels.map(c=>[c.id,c.samples[indices.indexOf(index)]])));values();}
    }catch(error){if(error.name!=='AbortError'&&current())mount.querySelector('.inspection-load').textContent=error.message;}
  }
  async function loadView() {
    if(recordController.signal.aborted)return;
    clearTimeout(hoverTimer);viewController?.abort();hoverController?.abort();s.invalidate();native.clear();cursorValues.clear();drawPaths();values();
    const controller=new AbortController();viewController=controller;
    recordController.signal.addEventListener('abort',()=>controller.abort(),{once:true,signal:controller.signal});
    const lo=Math.ceil(s.view[0]),hi=Math.floor(s.view[1])+1,token=s.request('view');
    const status=mount.querySelector('.inspection-load');status.textContent=hi-lo<=20000?'Loading exact native observations…':'Display envelopes; zoom to ≤20000 samples for native paths. Cursors always use exact observations.';
    if(hi-lo<=20000){try{const entries=await Promise.all(shown().map(async id=>[id,await getSamples(id,lo,hi,controller)]));
      if(s.accept(token)&&!controller.signal.aborted&&host.isConnected){for(const[id,points]of entries)native.set(id,points);status.textContent='Native observations loaded. Unknown states and missing amplitudes stay blank.';drawPaths();}
    }catch(error){if(error.name!=='AbortError'&&s.accept(token)&&!controller.signal.aborted&&host.isConnected){status.textContent=error.message;native.clear();drawPaths();}}}
    if(s.accept(token)&&!controller.signal.aborted)loadCursors();
  }
  function movePin(name,index){follow=name;s.move(name,index);const moved=s.follow(s.pins[name]);controls();if(moved){drawSlots();loadView();}else{drawPaths();loadCursors();}}
  mount.querySelector('.inspection-plots').onkeydown=e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();movePin(active,s.pins[active]+(e.key==='ArrowLeft'?-1:1));}};
  mount.querySelectorAll('[data-action]').forEach(button=>{if(button.dataset.action==='add-pin')return;button.onclick=()=>{const action=button.dataset.action;if(action==='in')s.zoom(.5);if(action==='out')s.zoom(2);if(action==='left')s.pan(-.5);if(action==='right')s.pan(.5);if(action==='reset')s.reset();if(action==='prev')page--;if(action==='next')page++;drawSlots();loadView();};});
  recordController.signal.addEventListener('abort',()=>{clearTimeout(hoverTimer);hoverController?.abort();viewController?.abort();s.invalidate();},{once:true});
  controls();drawSlots();loadView();
  return {setAnalysis(result){analysis=result;values();},getPins(){return {...s.pins};},focusWindow(lo,hi){s.view=[Math.max(0,lo),Math.min(s.n-1,Math.max(lo+1,hi-1))];drawSlots();loadView();mount.scrollIntoView({block:"start",behavior:"smooth"});}};
}
