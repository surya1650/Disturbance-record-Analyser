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
  let active='A',follow='A',analysis=null,reference='',mode='waveform',hoverTimer,hoverController,viewController;
  const pins=()=>Object.entries(s.pins);
  const analogs=()=>s.order.filter(id=>byId.get(id).kind==='analog');
  const digitals=()=>s.order.filter(id=>byId.get(id).kind==='digital'&&s.visible(id));
  const shown=()=>[...analogs(),...digitals()];
  const esc=escapeHtml;
  mount.innerHTML=`<div class="inspection-toolbar"><label>Analog display <select class="inspection-mode"><option value="waveform">Waveforms</option><option value="fundamental">Fundamental RMS · fitted</option></select></label><button data-action="in">Zoom +</button><button data-action="out">Zoom −</button><button data-action="left">← Pan</button><button data-action="right">Pan →</button><button data-action="reset">Full recording</button><span id="inspection-range"></span></div><details class="inspection-channels"><summary>Channels & colours · all ${analogs().length} analog channels always displayed · choose additional digital signals</summary><div class="inspection-channel-list"></div></details><div class="inspection-pins"></div><p class="inspection-clock"></p><p class="field-help">All plots share source sample positions. Tick labels show exact recorded coordinates, relative to the recorded trigger when available; the trigger is not inferred fault inception. Click a plot to move the selected cursor; arrow keys step samples.</p><div class="inspection-display"><div class="inspection-analog-workspace"><div class="inspection-time-nav"><label>Pan zoomed recording <input class="inspection-span" type="range" min="0" max="${Math.max(0,s.n-1)}" value="0" aria-label="Recording viewport position"></label><div class="inspection-time-axis"></div></div><div class="inspection-plots" tabindex="0" aria-label="Waveform cursors; left and right arrows step selected pin"><section class="inspection-pane analog"><h3>Analog channels <small>All ${analogs().length} analog channels · shared cursors</small></h3><p class="inspection-mode-note"></p><div class="analog-slots"></div></section></div><div class="inspection-time-axis"></div></div><aside class="inspection-vector"><h3>Cursor readings & vectors</h3><p class="inspection-live-cursor"></p><label>Angle reference <select class="inspection-reference" aria-label="Vector angle reference"></select></label><div class="inspection-vector-charts"></div></aside><section class="inspection-pane digital"><h3>Digital channels <small>Changed signals first · no pagination</small></h3><p class="field-help">State-1 bars are recorded observations, not verified trip/assertion polarity. State spans below are sampled support, not physical operating times.</p><div class="digital-slots"></div><div class="inspection-time-axis"></div><p class="inspection-digital-count"></p></section></div><p class="inspection-load" role="status"></p><p class="inspection-delta"></p><details class="inspection-cursor-details"><summary>All cursor values and delta times</summary><div class="table-wrap"><table class="inspection-values"><thead></thead><tbody></tbody></table></div></details>`;
  mount.querySelector('.inspection-mode').onchange=e=>{mode=e.target.value;drawSlots();};
  mount.querySelector('.inspection-span').oninput=e=>{const span=s.view[1]-s.view[0],lo=Math.max(0,Math.min(s.n-1-span,Number(e.target.value)));s.view=[lo,lo+span];drawSlots();loadView();};
  mount.querySelector('.inspection-reference').onchange=e=>{reference=e.target.value;values();};
  const phase=id=>s.phases[id]||DRInspection.phaseFor(byId.get(id),data.channels);
  const color=id=>s.colors[phase(id)];
  function controls() {
    mount.querySelector('.inspection-channel-list').innerHTML='<p class="field-help">Phase colour and overlay group are display choices.</p><div class="inspection-palette">'+Object.entries(s.colors).map(([name,c])=>`<label>${name==='unknown'?'Other':name}<input type="color" aria-label="Phase ${name} colour" data-phase-color="${name}" value="${c}"></label>`).join('')+'</div>'+s.order.map(id=>{const c=byId.get(id);return `<div class="inspection-channel-choice"><label><input type="checkbox" data-channel="${id}" ${c.kind==='analog'||s.visible(id)?'checked':''} ${c.kind==='analog'?'disabled':''}>${id} ${esc(c.label)} <small>${esc(c.units)}${c.kind==='digital'?' · '+(c.activity?.transition_count??'Unknown')+' changes':''}</small></label><button data-move="${id}" data-direction="-1" aria-label="Move ${id} up">↑</button><button data-move="${id}" data-direction="1" aria-label="Move ${id} down">↓</button><select aria-label="${id} display phase" data-phase="${id}">${Object.keys(s.colors).map(p=>`<option value="${p}" ${p===phase(id)?'selected':''}>${p==='unknown'?'Other':p}</option>`).join('')}</select>${c.kind==='analog'?`<select aria-label="${id} overlay group" data-group="${id}"><option value="">Separate slot</option>${['1','2','3','4'].map(g=>`<option value="${g}" ${s.groups[id]===g?'selected':''}>Overlay ${g}</option>`).join('')}</select>`:''}</div>`;}).join('');
    mount.querySelectorAll('[data-phase-color]').forEach(el=>el.onchange=()=>{s.setColour(el.dataset.phaseColor,el.value);drawPaths();values();});
    mount.querySelectorAll('[data-phase]').forEach(el=>el.onchange=()=>{s.phases[el.dataset.phase]=el.value;drawPaths();values();});
    mount.querySelectorAll('[data-group]').forEach(el=>el.onchange=()=>{s.groups[el.dataset.group]=el.value;drawSlots();});
    mount.querySelectorAll('[data-channel]').forEach(el=>el.onchange=()=>{s.toggle(el.dataset.channel);drawSlots();loadView();});
    mount.querySelectorAll('[data-move]').forEach(el=>el.onclick=()=>{s.reorder(el.dataset.move,Number(el.dataset.direction));controls();drawSlots();loadView();});
    mount.querySelector('.inspection-pins').innerHTML=pins().map(([name,index])=>`<label><input type="radio" name="inspection-active" value="${name}" ${name===active?'checked':''}>Pin ${name} <input aria-label="Cursor ${name} sample index" data-pin="${name}" type="number" min="0" max="${s.n-1}" value="${index}"></label>${!['A','B'].includes(name)?`<button data-remove-pin="${name}" aria-label="Remove cursor ${name}">×</button>`:''}`).join('')+'<button data-action="add-pin">Add cursor at hover</button>';
    mount.querySelectorAll('[name=inspection-active]').forEach(el=>el.onchange=()=>active=el.value);
    mount.querySelectorAll('[data-pin]').forEach(el=>el.onchange=()=>movePin(el.dataset.pin,Number(el.value)));
    mount.querySelectorAll('[data-remove-pin]').forEach(el=>el.onclick=()=>{s.removePin(el.dataset.removePin);if(!s.pins[active]&&s.pins[active]!==0)active='A';if(follow===el.dataset.removePin)follow=active;controls();drawSlots();loadCursors();});
    mount.querySelector('[data-action=add-pin]').onclick=()=>{try{s.addPin();controls();drawSlots();loadCursors();}catch(error){mount.querySelector('.inspection-load').textContent=error.message;}};
  }
  function digitalActivity(c){
    const a=c.activity;if(!a)return '<p class="inspection-digital-activity">Exact activity metadata unavailable; original states remain inspectable.</p>';
    const duration=Number.isFinite(a.active_duration_s)?(a.active_duration_s*1000).toPrecision(6)+' ms of sampled state-1 support':'state-1 duration unavailable';
    const spans=(a.high_intervals||[]).map(run=>`<li>${run.start_index}–${run.last_index}: ${esc(DRInspection.milliseconds(run.start_s,data.timeline))} to ${esc(DRInspection.milliseconds(run.last_s,data.timeline))}${run.start_open||run.end_open?' · boundary open/unknown':''}</li>`).join('');
    return `<div class="inspection-digital-activity">${a.transition_count??'Unknown'} recorded changes · ${esc(duration)} · ${a.unknown_samples??'Unknown'} unknown samples${spans?'<details><summary>Recorded state-1 spans'+(a.omitted_intervals?' · '+a.omitted_intervals+' additional spans omitted':'')+'</summary><ul>'+spans+'</ul></details>':''}</div>`;
  }
  function drawSlots() {
    for (const kind of ['analog','digital']) {
      const groups=DRInspection.groupChannels(shown().map(id=>byId.get(id)).filter(c=>c.kind===kind),s);
      mount.querySelector(`.${kind}-slots`).innerHTML=groups.map(group=>{const c=group[0],id=group.map(c=>c.id).join(',');return `<div class="inspection-slot"><strong>${group.map(c=>c.id+' · '+esc(c.label)).join(' / ')} <small>${esc(c.units)}</small></strong>${c.kind==='digital'?digitalActivity(c):''}<div class="inspection-trace-readings"><div class="inspection-graph"><div class="inspection-y-labels" data-y-labels="${id}"></div><svg data-trace="${id}" viewBox="0 0 900 140" preserveAspectRatio="none" role="img" aria-label="${esc(c.label)} waveform"></svg></div><div class="inspection-inline-values" data-reading="${id}"></div></div></div>`;}).join('') || '<p class="muted">No digital changes are selected. Add other digital signals using Channels & colours above.</p>';
    }
    mount.querySelector('.inspection-digital-count').textContent=`${digitals().length} of ${data.channels.filter(c=>c.kind==='digital').length} digital channels displayed. All ${analogs().length} analog channels remain visible.`;
    mount.querySelector('.inspection-mode-note').textContent=mode==='fundamental'?'Fundamental fitted RMS at supported model centres. Missing fits remain gaps; this is a trend, not instantaneous amplitude.':'Recorded waveform observations with independent labelled channel scales.';
    mount.querySelector('#inspection-range').textContent=`Samples ${Math.ceil(s.view[0])}–${Math.floor(s.view[1])}`;
    const slider=mount.querySelector('.inspection-span');slider.value=String(Math.round(s.view[0]));slider.max=String(Math.max(0,s.n-1-(s.view[1]-s.view[0])));
    mount.querySelectorAll('[data-trace]').forEach(svg=>{
      const indexFrom=e=>{const r=svg.getBoundingClientRect();return s.view[0]+Math.max(0,Math.min(1,(e.clientX-r.left)/r.width))*(s.view[1]-s.view[0]);};
      svg.onpointermove=e=>{follow='hover';s.move('hover',indexFrom(e));cursorValues.delete('hover');drawCursors();values();clearTimeout(hoverTimer);hoverTimer=setTimeout(loadHover,70);};
      svg.onclick=e=>{movePin(active,indexFrom(e));mount.querySelector('.inspection-plots').focus();};
      svg.onwheel=e=>{e.preventDefault();s.zoom(e.deltaY>0?1.5:1/1.5,indexFrom(e));drawSlots();loadView();};
    });
    drawPaths();values();
  }
  function drawPaths() {
    for(const svg of mount.querySelectorAll('[data-trace]')) {
      const ids=svg.dataset.trace.split(','),channels=ids.map(id=>byId.get(id));
      const series=channels.map(c=>({c,points:(c.kind==='analog'&&mode==='fundamental'?DRInspection.rmsSeries(analysis,c.id):(native.get(c.id)||c.trace)).filter(p=>p[0]>=s.view[0]&&p[0]<=s.view[1])}));
      const amplitude=DRInspection.amplitudeScale(series.flatMap(series=>series.points),channels[0].kind,mode==='waveform'?'waveform':'fundamental');
      const x=i=>(i-s.view[0])/Math.max(1,s.view[1]-s.view[0])*900,y=amplitude.y;
      const labelNode=svg.parentElement?.querySelector('[data-y-labels]');if(labelNode)labelNode.innerHTML=amplitude.ticks.map(v=>`<span style="top:${y(v)/140*100}%">${esc(DRInspection.amplitudeLabel(v))}</span>`).join('');
      const gap=data.time_basis.minimum_interval_s?data.time_basis.minimum_interval_s*8:Infinity;
      svg.innerHTML=amplitude.ticks.map(v=>`<line x1="0" x2="900" y1="${y(v)}" y2="${y(v)}" stroke="#e1e9ee"/>`).join('')+series.map(({c,points})=>{
        const parts=mode==='fundamental'&&c.kind==='analog'&&data.omitted_break_indices>0?points.filter(p=>p[2]!==null).map(p=>[p]):DRInspection.segments(points,gap,data.break_indices||[]),path=parts.map(part=>part.map((p,i)=>`${i?(c.kind==='digital'?'H'+x(p[0])+'V':'L'):'M'+x(p[0])+','}${i?(c.kind==='digital'?y(p[2]):x(p[0])+','+y(p[2])):y(p[2])}`).join(' ')).join(' ');
        const bands=c.kind==='digital'?(c.activity?.high_intervals||[]).filter(r=>r.last_index>=s.view[0]&&r.start_index<=s.view[1]).map(r=>`<rect x="${x(Math.max(r.start_index,s.view[0]))}" y="22" width="${Math.max(1,x(Math.min(r.last_index,s.view[1]))-x(Math.max(r.start_index,s.view[0])))}" height="60" fill="${color(c.id)}" opacity=".18"/>`).join(''):'';
        return bands+`<path d="${path}" fill="none" stroke="${color(c.id)}" stroke-width="1.5" vector-effect="non-scaling-stroke"/>`+parts.filter(p=>p.length===1).map(part=>`<circle cx="${x(part[0][0])}" cy="${y(part[0][2])}" r="2" fill="${color(c.id)}"/>`).join('');
      }).join('')+(Number.isFinite(data.timeline?.trigger_index)&&data.timeline.trigger_index>=s.view[0]&&data.timeline.trigger_index<=s.view[1]?`<line x1="${x(data.timeline.trigger_index)}" x2="${x(data.timeline.trigger_index)}" y1="0" y2="140" stroke="#8865aa"/><text x="${x(data.timeline.trigger_index)+4}" y="24">0 ms</text>`:'')+'<g data-cursor-layer></g>';
    }
    drawCursors();
    const ticks=DRInspection.axisTicks(data,s.view,native);
    const axis=ticks.map(p=>`<span style="left:${(p[0]-s.view[0])/Math.max(1,s.view[1]-s.view[0])*100}%">${esc(p[1]===null?'#'+p[0]:DRInspection.milliseconds(p[1],data.timeline))}</span>`).join('');
    for(const el of mount.querySelectorAll('.inspection-time-axis'))el.innerHTML=axis;
  }
  function drawCursors() {
    const x=i=>(i-s.view[0])/Math.max(1,s.view[1]-s.view[0])*900;
    const marks=[['hover',s.hover],...pins()].filter(([,i])=>i>=s.view[0]&&i<=s.view[1]).map(([name,i])=>`<line x1="${x(i)}" x2="${x(i)}" y1="0" y2="140" stroke="${name==='hover'?'#8b919a':name==='A'?'#bb3b51':'#6a4cbb'}" stroke-dasharray="${name==='hover'?'3 4':'0'}"/><text x="${x(i)+4}" y="12">${name}</text>`).join('');
    for(const svg of mount.querySelectorAll('[data-trace]')){const layer=svg.querySelector('[data-cursor-layer]');if(layer)layer.innerHTML=marks;}
  }
  function values() {
    const names=[...pins().map(([name])=>name),'hover'];
    mount.querySelector('.inspection-values thead').innerHTML='<tr><th>Channel · source units</th>'+names.map(name=>`<th>${name} · sample ${name==='hover'?s.hover:s.pins[name]}</th>`).join('')+'</tr>';
    mount.querySelector('.inspection-values tbody').innerHTML=shown().map(id=>{const c=byId.get(id);return `<tr><th>${id} ${esc(c.label)}<small>${esc(c.units)}</small></th>${names.map(name=>{const point=cursorValues.get(name)?.get(id);return `<td>${esc(DRInspection.value(point))}<small>${point?point[1]===null?'Time not available':`${point[1].toPrecision(9)} local s`:'Awaiting native observation'}</small></td>`;}).join('')}</tr>`;}).join('');
    const index=follow==='hover'?s.hover:s.pins[follow],points=cursorValues.get(follow),reading=DRReadings.view(analysis,index,reference);
    const options='<option value="">Automatic supported source reference</option>'+(analysis?.channels||[]).map(c=>`<option value="${esc(c.id)}">${esc(c.id+' '+c.label)}</option>`).join('');
    const ref=mount.querySelector('.inspection-reference');if(ref.innerHTML!==options)ref.innerHTML=options;ref.value=reference;
    for(const el of mount.querySelectorAll('[data-reading]'))el.innerHTML=el.dataset.reading.split(',').map(id=>DRReadings.readingMarkup(byId.get(id),points?.get(id),reading.channels.get(id),follow)).join('');
    mount.querySelector('.inspection-vector-charts').innerHTML=DRReadings.vectorMarkup(reading,Object.fromEntries(data.channels.map(c=>[c.id,color(c.id)])));
    const current=points?.get(shown()[0]);mount.querySelector('.inspection-clock').textContent=current?DRInspection.milliseconds(current[1],data.timeline)+' · '+DRInspection.relayTime(current[1],data.timeline):'Move a cursor to read exact source time.';mount.querySelector('.inspection-live-cursor').textContent=`${follow==='hover'?'Hover':'Cursor '+follow} · sample ${index} · ${current?.[1]===null||!current?'Time unavailable':current[1].toPrecision(7)+' local s'}`;
    const first=shown()[0],a=cursorValues.get('A')?.get(first),b=cursorValues.get('B')?.get(first);
    mount.querySelector('.inspection-delta').textContent=a&&b?`B − A: ${DRInspection.delta(a,b).samples} samples · ${DRInspection.delta(a,b).seconds===null?'Time difference not available':(DRInspection.delta(a,b).seconds*1000).toPrecision(9)+' ms (source coordinates)'}`:'B − A: waiting for exact cursor observations.';
  }
  async function getSamples(id,lo,hi,controller) {
    const query=new URLSearchParams({revision:row.number,record:data.file,channel_id:id,start_index:lo,stop_index:hi});
    const response=await fetch(`/api/incidents/${row.incident_id}/inspection/samples?${query}`,{signal:controller.signal});
    const body=await response.json();if(!response.ok)throw new Error(body.detail||'Native observations unavailable.');
    if(body.file!==data.file||body.revision!==row.number||body.channel_id!==id||DRInspection.identity(body.source_sha256)!==DRInspection.identity(data.source_sha256)||body.samples?.length!==hi-lo||body.samples.some((p,i)=>p[0]!==lo+i))throw new Error('Source identity changed; reopen recording.');
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
        const batches=await DRInspection.boundedMap(DRInspection.chunks(ids),async batch=>{
          if(controller.signal.aborted){const error=new Error('Cursor request aborted.');error.name='AbortError';throw error;}
          const query=new URLSearchParams({revision:row.number,record:data.file,channel_ids:JSON.stringify(batch),indices:JSON.stringify(indices)});
          const response=await fetch(`/api/incidents/${row.incident_id}/inspection/points?${query}`,{signal:controller.signal});
          const body=await response.json();if(!response.ok)throw new Error(body.detail||'Cursor observations unavailable.');
          if(body.file!==data.file||body.revision!==row.number||DRInspection.identity(body.source_sha256)!==DRInspection.identity(data.source_sha256)||body.channels?.length!==batch.length||body.channels.some((c,i)=>c.id!==batch[i]||c.samples?.length!==indices.length||c.samples.some((p,j)=>p[0]!==indices[j])))throw new Error('Cursor response identity changed; reopen recording.');
          return body.channels;
        });
        channels=batches.flat();
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
    const canLoad=hi-lo<=20000&&(hi-lo)*shown().length<=200000&&!(data.omitted_break_indices>0);
    const status=mount.querySelector('.inspection-load');status.textContent=canLoad?'Loading exact native observations…':'Display envelopes; zoom for native paths (up to 20000 samples and 200000 visible cells). All channel cursors remain exact.';
    if(canLoad){try{const entries=await DRInspection.boundedMap(shown(),async id=>{if(controller.signal.aborted){const error=new Error('View request aborted.');error.name='AbortError';throw error;}return [id,await getSamples(id,lo,hi,controller)];});
      if(s.accept(token)&&!controller.signal.aborted&&host.isConnected){for(const[id,points]of entries)native.set(id,points);status.textContent='Native observations loaded. Unknown states and missing amplitudes stay blank.';drawPaths();}
    }catch(error){if(error.name!=='AbortError'&&s.accept(token)&&!controller.signal.aborted&&host.isConnected){status.textContent=error.message;native.clear();drawPaths();}}}
    if(s.accept(token)&&!controller.signal.aborted)loadCursors();
  }
  function movePin(name,index){follow=name;s.move(name,index);const moved=s.follow(s.pins[name]);controls();if(moved){drawSlots();loadView();}else{drawCursors();loadCursors();}}
  mount.querySelector('.inspection-plots').onkeydown=e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();movePin(active,s.pins[active]+(e.key==='ArrowLeft'?-1:1));}};
  mount.querySelectorAll('[data-action]').forEach(button=>{if(button.dataset.action==='add-pin')return;button.onclick=()=>{const action=button.dataset.action;if(action==='in')s.zoom(.5);if(action==='out')s.zoom(2);if(action==='left')s.pan(-.5);if(action==='right')s.pan(.5);if(action==='reset')s.reset();drawSlots();loadView();};});
  recordController.signal.addEventListener('abort',()=>{clearTimeout(hoverTimer);hoverController?.abort();viewController?.abort();s.invalidate();},{once:true});
  controls();drawSlots();loadView();
  return {setAnalysis(result){analysis=result;drawPaths();values();},getPins(){return {...s.pins};},getPoint(name){const point=cursorValues.get(name)?.get(shown()[0]);return point?.[0]===s.pins[name]?point:null;},focusWindow(lo,hi){s.view=[Math.max(0,lo),Math.min(s.n-1,Math.max(lo+1,hi-1))];drawSlots();loadView();mount.scrollIntoView({block:"start",behavior:"smooth"});}};
}
