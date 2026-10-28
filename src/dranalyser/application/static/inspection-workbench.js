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
  const native=new Map(),nativeRms=new Map(),cursorValues=new Map(),cursorRms=new Map();
  let page=0,active='A',follow='A',analysis=null,reference='',mode='waveform',hoverTimer,hoverController,viewController;
  const pins=()=>Object.entries(s.pins);
  const analogs=()=>s.order.filter(id=>byId.get(id).kind==='analog');
  const digitals=()=>s.order.filter(id=>byId.get(id).kind==='digital'&&s.visible(id));
  const shown=()=>[...analogs(),...digitals().slice(page*8,page*8+8)];
  const esc=escapeHtml;
  mount.innerHTML=`<div class="inspection-toolbar"><label>Analog display <select class="inspection-mode"><option value="waveform">Waveforms</option><option value="rms">Sample RMS · 1 cycle</option><option value="fundamental">Fundamental RMS · fitted</option></select></label><button data-action="in">Zoom +</button><button data-action="out">Zoom −</button><button data-action="left">← Pan</button><button data-action="right">Pan →</button><button data-action="reset">Full recording</button><span id="inspection-range"></span></div><details class="inspection-channels"><summary>Channels & colours · all ${analogs().length} analog channels always displayed · choose additional digital signals</summary><div class="inspection-channel-list"></div></details><div class="inspection-pins"></div><p class="inspection-clock"></p><p class="field-help inspection-axis-note">Zero is the recorded trigger when available. Hover for readings; click to move a cursor, or use ← / → to step samples. All plots share source sample positions; tick labels show their actual recorded times.</p><div class="inspection-display"><div class="inspection-layout"><div class="inspection-plots" tabindex="0" aria-label="Waveform cursors; left and right arrows step selected pin"><div class="inspection-time-nav"><div class="inspection-nav-caption"></div><svg class="inspection-overview" viewBox="0 0 900 52" preserveAspectRatio="none" role="slider" tabindex="0" aria-label="Full recording cursor navigator" aria-valuemin="0" aria-valuemax="${s.n-1}"></svg><label class="inspection-span-label">Pan zoomed recording <input class="inspection-span" type="range" min="0" max="${Math.max(0,s.n-1)}" value="0" aria-label="Recording viewport position"></label><div class="inspection-time-axis"></div></div><section class="inspection-pane analog"><h3>Analog channels <small>All channels · shared cursors</small></h3><p class="inspection-mode-note"></p><div class="analog-slots"></div><div class="inspection-time-axis"></div></section><section class="inspection-pane digital"><h3>Digital channels <small>Changed signals first</small></h3><p class="field-help">Filled bars show recorded state 1; blank breaks are unknown. State 1 is not automatically a trip or asserted state.</p><div class="digital-slots"></div><div class="inspection-time-axis"></div><div class="inspection-toolbar"><button data-action="prev">Previous digital signals</button><span class="inspection-page"></span><button data-action="next">Next digital signals</button></div></section></div></div><aside class="inspection-vector"><h3>Cursor readings & vectors</h3><p class="inspection-live-cursor"></p><label>Angle reference <select class="inspection-reference" aria-label="Vector angle reference"></select></label><div class="inspection-vector-charts"></div><h4>Values at cursor</h4><div class="inspection-live-values"></div></aside></div><p class="inspection-load" role="status"></p><p class="inspection-delta"></p><details class="inspection-cursor-details"><summary>All cursor values and delta times</summary><div class="table-wrap"><table class="inspection-values"><thead></thead><tbody></tbody></table></div></details>`;
  mount.querySelector('.inspection-mode').onchange=e=>{mode=e.target.value;drawSlots();};
  mount.querySelector('.inspection-span').oninput=e=>{const span=s.view[1]-s.view[0],lo=Math.max(0,Math.min(s.n-1-span,Number(e.target.value)));s.view=[lo,lo+span];drawSlots();loadView();};
  const overview=mount.querySelector('.inspection-overview');
  const overviewIndex=e=>{const r=overview.getBoundingClientRect();return Math.round(Math.max(0,Math.min(1,(e.clientX-r.left)/r.width))*(s.n-1));};
  overview.onpointerdown=e=>{overview.setPointerCapture?.(e.pointerId);movePin(active,overviewIndex(e));};
  overview.onpointermove=e=>{if(e.buttons===1)movePin(active,overviewIndex(e));};
  overview.onkeydown=e=>{e.stopPropagation?.();if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();movePin(active,e.key==='Home'?0:e.key==='End'?s.n-1:s.pins[active]+(e.key==='ArrowLeft'?-1:1));}};
  mount.querySelector('.inspection-reference').onchange=e=>{reference=e.target.value;values();};
  const phase=id=>s.phases[id]||DRInspection.phaseFor(byId.get(id),data.channels);
  const color=id=>s.colors[phase(id)];
  function controls() {
    mount.querySelector('.inspection-channel-list').innerHTML='<p class="field-help">Phase colour and overlay group are display choices.</p><div class="inspection-palette">'+Object.entries(s.colors).map(([name,c])=>`<label>${name==='unknown'?'Other':name}<input type="color" aria-label="Phase ${name} colour" data-phase-color="${name}" value="${c}"></label>`).join('')+'</div>'+s.order.map(id=>{const c=byId.get(id);return `<div class="inspection-channel-choice"><label><input type="checkbox" data-channel="${id}" ${c.kind==='analog'||s.visible(id)?'checked':''} ${c.kind==='analog'?'disabled':''}>${id} ${esc(c.label)} <small>${esc(c.units)}${c.kind==='digital'?` · ${c.activity?.transition_count??'Unknown'} changes`:''}</small></label><button data-move="${id}" data-direction="-1" aria-label="Move ${id} up">↑</button><button data-move="${id}" data-direction="1" aria-label="Move ${id} down">↓</button><select aria-label="${id} display phase" data-phase="${id}">${Object.keys(s.colors).map(p=>`<option value="${p}" ${p===phase(id)?'selected':''}>${p==='unknown'?'Other':p}</option>`).join('')}</select>${c.kind==='analog'?`<select aria-label="${id} overlay group" data-group="${id}"><option value="">Separate slot</option>${['1','2','3','4'].map(g=>`<option value="${g}" ${s.groups[id]===g?'selected':''}>Overlay ${g}</option>`).join('')}</select>`:''}</div>`;}).join('');
    mount.querySelectorAll('[data-phase-color]').forEach(el=>el.onchange=()=>{s.setColour(el.dataset.phaseColor,el.value);drawPaths();values();});
    mount.querySelectorAll('[data-phase]').forEach(el=>el.onchange=()=>{s.phases[el.dataset.phase]=el.value;drawPaths();values();});
    mount.querySelectorAll('[data-group]').forEach(el=>el.onchange=()=>{s.groups[el.dataset.group]=el.value;drawSlots();});
    mount.querySelectorAll('[data-channel]').forEach(el=>el.onchange=()=>{s.toggle(el.dataset.channel);page=0;drawSlots();loadView();});
    mount.querySelectorAll('[data-move]').forEach(el=>el.onclick=()=>{s.reorder(el.dataset.move,Number(el.dataset.direction));controls();drawSlots();loadView();});
    mount.querySelector('.inspection-pins').innerHTML=pins().map(([name,index])=>`<label><input type="radio" name="inspection-active" value="${name}" ${name===active?'checked':''}>Pin ${name} <input aria-label="Cursor ${name} sample index" data-pin="${name}" type="number" min="0" max="${s.n-1}" value="${index}"></label>${!['A','B'].includes(name)?`<button data-remove-pin="${name}" aria-label="Remove cursor ${name}">×</button>`:''}`).join('')+'<button data-action="add-pin">Add cursor at hover</button>';
    mount.querySelectorAll('[name=inspection-active]').forEach(el=>el.onchange=()=>active=el.value);
    mount.querySelectorAll('[data-pin]').forEach(el=>el.onchange=()=>movePin(el.dataset.pin,Number(el.value)));
    mount.querySelectorAll('[data-remove-pin]').forEach(el=>el.onclick=()=>{s.removePin(el.dataset.removePin);if(!s.pins[active]&&s.pins[active]!==0)active='A';if(follow===el.dataset.removePin)follow=active;controls();drawSlots();loadCursors();});
    mount.querySelector('[data-action=add-pin]').onclick=()=>{try{s.addPin();controls();drawSlots();loadCursors();}catch(error){mount.querySelector('.inspection-load').textContent=error.message;}};
  }
  function drawSlots() {
    for (const kind of ['analog','digital']) {
      const groups=DRInspection.groupChannels(shown().map(id=>byId.get(id)).filter(c=>c.kind===kind),s);
      mount.querySelector(`.${kind}-slots`).innerHTML=groups.map(group=>{const c=group[0],id=group.map(c=>c.id).join(',');return `<div class="inspection-slot"><strong>${group.map(c=>c.id+' · '+esc(c.label)).join(' / ')} <small>${esc(mode==='fundamental'&&kind==='analog'?(analysis?.channels.find(m=>m.id===c.id)?.units||'RMS units pending'):c.units)}</small></strong><div class="inspection-trace-readings"><svg data-trace="${id}" viewBox="0 0 900 100" preserveAspectRatio="none" role="img" aria-label="${esc(c.label)} waveform"></svg><div class="inspection-graph-readout" data-graph-reading="${id}"></div></div>${kind==='digital'?activityMarkup(c):''}</div>`;}).join('') || (kind==='digital'?'<p class="muted">No selected state-changing digital signals. Use Channels & colours above to add constant or other signals.</p>':'<p class="muted">This recording contains no recoverable analog channels.</p>');
    }
    const ds=digitals(),changed=data.channels.filter(c=>c.kind==='digital'&&c.activity?.transition_count>0).length;
    mount.querySelector('.inspection-page').textContent=`${ds.length?Math.min(page*8+1,ds.length):0}–${Math.min(page*8+8,ds.length)} of ${ds.length} selected digital signals · ${changed} changed`;
    mount.querySelector('[data-action=prev]').disabled=page===0;
    mount.querySelector('[data-action=next]').disabled=(page+1)*8>=ds.length;
    mount.querySelector('#inspection-range').textContent=`Samples ${Math.ceil(s.view[0])}–${Math.floor(s.view[1])} / ${s.n}`;
    mount.querySelector('.inspection-span').max=Math.max(0,s.n-1-(s.view[1]-s.view[0]));
    mount.querySelector('.inspection-span').value=s.view[0];
    mount.querySelector('.inspection-span').disabled=s.view[1]-s.view[0]>=s.n-1;
    mount.querySelector('.inspection-mode-note').textContent=mode==='rms'?'Trailing one-cycle sample RMS in recorded source units; includes DC and harmonics. Incomplete or missing supports stay blank.':mode==='fundamental'?'Fundamental RMS at supported four-cycle model centres. Gaps are withheld fits; values between model centres are display connections only.':'Recorded analog waveforms · labeled vertical scales · exact instantaneous and sample RMS cursor readings';
    mount.querySelector('.inspection-clock').textContent=`Recorded trigger: ${data.timeline?.trigger_local?.replace('T',' ')||'Unavailable'} · relay-local time, clock accuracy unverified`;
    mount.querySelectorAll('[data-trace]').forEach(svg=>{
      const indexFrom=e=>{const r=svg.getBoundingClientRect();return s.view[0]+Math.max(0,Math.min(1,((e.clientX-r.left)/r.width*900-74)/814))*(s.view[1]-s.view[0]);};
      svg.onpointerdown=e=>{svg.setPointerCapture?.(e.pointerId);movePin(active,indexFrom(e));};
      svg.onpointermove=e=>{if(e.buttons===1){movePin(active,indexFrom(e));return;}follow='hover';s.move('hover',indexFrom(e));cursorValues.delete('hover');cursorRms.delete('hover');drawPaths();values();clearTimeout(hoverTimer);hoverTimer=setTimeout(loadHover,70);};
      svg.onclick=e=>{movePin(active,indexFrom(e));mount.querySelector('.inspection-plots').focus();};
      svg.onwheel=e=>{e.preventDefault();s.zoom(e.deltaY>0?1.5:1/1.5,indexFrom(e));drawSlots();loadView();};
    });
    drawPaths();values();
  }
  function drawPaths() {
    for(const svg of mount.querySelectorAll('[data-trace]')) {
      const ids=svg.dataset.trace.split(','),channels=ids.map(id=>byId.get(id));
      const full=channels.map(c=>({c,points:c.kind==='analog'&&mode==='rms'?(nativeRms.get(c.id)||c.rms_trace||[]):c.kind==='analog'&&mode==='fundamental'?DRInspection.rmsSeries(analysis,c.id):(native.get(c.id)||c.trace)}));
      const series=full.map(({c,points})=>({c,points:points.filter(p=>p[0]>=s.view[0]&&p[0]<=s.view[1])}));
      const domain=DRInspection.amplitudeScale(full.flatMap(v=>v.points),channels[0].kind,mode);
      const x=i=>74+(i-s.view[0])/Math.max(1,s.view[1]-s.view[0])*814,y=domain.y;
      const axes=domain.ticks.map(v=>`<line x1="74" x2="888" y1="${y(v)}" y2="${y(v)}" stroke="#e6edf1"/><text class="inspection-y-tick" x="65" y="${y(v)+3}" text-anchor="end">${esc(DRInspection.amplitudeLabel(v))}</text>`).join('')+'<line x1="74" x2="74" y1="10" y2="92" stroke="#a9bcc8"/>';
      const gap=data.time_basis.minimum_interval_s?data.time_basis.minimum_interval_s*8:Infinity;
      svg.innerHTML=axes+series.map(({c,points})=>{
        const parts=DRInspection.segments(points,mode==='fundamental'&&c.kind==='analog'?Infinity:gap,data.break_indices||[]),path=parts.map(part=>part.map((p,i)=>`${i?(c.kind==='digital'?'H'+x(p[0])+'V':'L'):'M'+x(p[0])+','}${i?(c.kind==='digital'?y(p[2]):x(p[0])+','+y(p[2])):y(p[2])}`).join(' ')).join(' ');
        const bars=c.kind==='digital'?parts.flatMap(part=>part.slice(0,-1).flatMap((p,i)=>{const q=part[i+1];if(p[2]!==1||q[0]!==p[0]+1)return [];return `<rect x="${x(p[0])}" y="${y(1)}" width="${Math.max(0,x(q[0])-x(p[0]))}" height="${y(0)-y(1)}" fill="${color(c.id)}" opacity=".16"/>`;})).join(''):'';
        return bars+`<path d="${path}" fill="none" stroke="${color(c.id)}" stroke-width="1.5" vector-effect="non-scaling-stroke"/>`+parts.filter(p=>p.length===1).map(part=>`<circle cx="${x(part[0][0])}" cy="${y(part[0][2])}" r="2" fill="${color(c.id)}"/>`).join('');
      }).join('')+[...(Number.isFinite(data.timeline?.trigger_index)?[['0 ms',data.timeline.trigger_index]]:[]),...(data.join?.sources||[]).slice(1).filter(c=>Number.isFinite(c.trigger_index)).map(c=>[c.file+' trigger',c.trigger_index]),['hover',s.hover],...pins()].filter(([,i])=>i>=s.view[0]&&i<=s.view[1]).map(([name,i])=>`<line x1="${x(i)}" x2="${x(i)}" y1="0" y2="100" stroke="${name==='hover'?'#8b919a':name==='A'?'#bb3b51':'#6a4cbb'}" stroke-dasharray="${name==='hover'?'3 4':'0'}"/><text x="${x(i)+4}" y="12">${esc(name)}</text>`).join('');
      if(!series.some(({points})=>points.some(p=>p[2]!==null)))svg.innerHTML+='<text x="20" y="50">'+(mode==='rms'&&channels[0].kind==='analog'?'No complete sample RMS support in this span':mode==='fundamental'&&channels[0].kind==='analog'?(analysis?'No supported fundamental RMS fit in this span':'Preparing fundamental analysis…'):'No known samples in this span')+'</text>';
    }
    const ticks=DRInspection.axisTicks(data,s.view,native),axis='<svg viewBox="0 0 900 52" preserveAspectRatio="none" role="img" aria-label="Recorded time axis">'+ticks.map(p=>{const x=74+(p[0]-s.view[0])/Math.max(1,s.view[1]-s.view[0])*814;return `<text x="${x}" y="18" text-anchor="${x<150?'start':x>810?'end':'middle'}">${esc(p[1]===null?'Sample '+p[0]:DRInspection.milliseconds(p[1],data.timeline))}</text><text x="${x}" y="38" text-anchor="${x<150?'start':x>810?'end':'middle'}">${esc(p[1]===null?'':DRInspection.relayTime(p[1],data.timeline).split(' ')[1]||'')}</text>`;}).join('')+'</svg>';
    mount.querySelectorAll('.inspection-time-axis').forEach(el=>el.innerHTML=axis);
    const c=data.channels.find(c=>c.kind==='analog'),source=c?.trace||[],d=DRInspection.amplitudeScale(source,'analog','waveform'),ox=i=>i/Math.max(1,s.n-1)*900;
    overview.innerHTML=(c?DRInspection.segments(source).map(part=>`<path d="${part.map((p,i)=>`${i?'L':'M'}${ox(p[0])},${d.y(p[2])/2}`).join(' ')}" fill="none" stroke="#7e9baa"/>`).join(''):'')+`<rect x="${ox(s.view[0])}" width="${Math.max(1,ox(s.view[1])-ox(s.view[0]))}" y="1" height="49" fill="#176d82" fill-opacity=".10" stroke="#176d82"/>`+pins().map(([name,i])=>`<line x1="${ox(i)}" x2="${ox(i)}" y1="0" y2="52" stroke="${name==='A'?'#bb3b51':'#6a4cbb'}"/>`).join('');

  }
  function activityMarkup(c){
    const a=c.activity;if(!a)return '';
    const first=a.high_intervals?.[0],caption=first?`${a.high_intervals.length>1||a.omitted_intervals?'First high':'High'} ${DRInspection.milliseconds(first.start_s,data.timeline)} → ${DRInspection.milliseconds(first.last_s,data.timeline)} · ${first.observed_span_s===null?'duration unavailable':(first.observed_span_s*1000).toFixed(3)+' ms observed span'}${first.start_open?' · onset unknown':''}${first.end_open?' · ending unknown':''}`:(a.high_samples?'High samples recorded; interval detail budget reached.':'No recorded high-state span.');
    return `<p class="inspection-activity-caption">${esc(caption)}</p><details class="inspection-activity"><summary>${a.transition_count} changes · ${a.high_samples} high samples · recorded high-state spans</summary>${(a.high_intervals||[]).map(v=>`<p>${esc(DRInspection.milliseconds(v.start_s,data.timeline))} → ${esc(DRInspection.milliseconds(v.last_s,data.timeline))} · ${v.observed_span_s===null?'Duration unavailable':(v.observed_span_s*1000).toFixed(3)+' ms observed span'}${v.start_open?' · already high / onset unknown':''}${v.end_open?' · ending unknown':''}</p>`).join('')||'<p>No recorded high-state span.</p>'}${a.omitted_intervals?`<p>${a.omitted_intervals} further spans omitted from this summary.</p>`:''}<small>${esc(a.basis)}</small></details>`;
  }
  function values() {
    const names=[...pins().map(([name])=>name),'hover'];
    mount.querySelector('.inspection-values thead').innerHTML='<tr><th>Channel · source units</th>'+names.map(name=>`<th>${name} · sample ${name==='hover'?s.hover:s.pins[name]}</th>`).join('')+'</tr>';
    mount.querySelector('.inspection-values tbody').innerHTML=shown().map(id=>{const c=byId.get(id);return `<tr><th>${id} ${esc(c.label)}<small>${esc(c.units)}</small></th>${names.map(name=>{const point=cursorValues.get(name)?.get(id);return `<td>${esc(DRInspection.value(point))}<small>${point?point[1]===null?'Time not available':`${point[1].toPrecision(9)} local s`:'Awaiting native observation'}</small></td>`;}).join('')}</tr>`;}).join('');
    const index=follow==='hover'?s.hover:s.pins[follow],local=DRInspection.exactPoints(native,shown(),[index]);
    const points=cursorValues.get(follow)||(local?new Map(local.map(c=>[c.id,c.samples[0]])):null),rmsPoints=cursorRms.get(follow)||new Map(analogs().map(id=>[id,DRInspection.exactPoints(nativeRms,[id],[index])?.[0]?.samples[0]])),reading=DRReadings.view(analysis,index,reference);
    if(data.join&&!analysis)reading.reasons={voltage:['Joined view: inspect the original capture for fundamental voltage vectors.'],current:['Joined view: inspect the original capture for fundamental current vectors.']};
    const options='<option value="">Automatic supported source reference</option>'+(analysis?.channels||[]).map(c=>`<option value="${esc(c.id)}">${esc(c.id+' '+c.label)}</option>`).join('');
    const ref=mount.querySelector('.inspection-reference');if(ref.innerHTML!==options)ref.innerHTML=options;ref.value=reference;
    mount.querySelector('.inspection-live-values').innerHTML=shown().map(id=>DRReadings.readingMarkup(byId.get(id),points?.get(id),reading.channels.get(id),follow,rmsPoints.get(id),byId.get(id).rms_reason)).join('');
    for(const el of mount.querySelectorAll('[data-graph-reading]')){
      el.innerHTML=el.dataset.graphReading.split(',').map(id=>DRReadings.graphMarkup(byId.get(id),points?.get(id),rmsPoints.get(id),reading.channels.get(id),mode,DRInspection.milliseconds(points?.get(id)?.[1],data.timeline))).join('');
      const fraction=(index-s.view[0])/Math.max(1,s.view[1]-s.view[0]);
      el.hidden=index<s.view[0]||index>s.view[1];el.style.left=Math.max(12,Math.min(98,8.23+fraction*90.44+1))+'%';el.style.transform=fraction>.55?'translateX(-100%)':'';
    }
    overview.setAttribute?.('aria-valuenow',index);
    mount.querySelector('.inspection-nav-caption').textContent=`${follow==='hover'?'Hover':'Cursor '+follow} · ${DRInspection.milliseconds(points?.get(shown()[0])?.[1],data.timeline)} · ${DRInspection.relayTime(points?.get(shown()[0])?.[1],data.timeline)} · drag the overview to move through the entire recording`;
    mount.querySelector('.inspection-vector-charts').innerHTML=DRReadings.vectorMarkup(reading,Object.fromEntries(data.channels.map(c=>[c.id,color(c.id)])));
    const current=points?.get(shown()[0]);mount.querySelector('.inspection-live-cursor').textContent=`${follow==='hover'?'Hover':'Cursor '+follow} · sample ${index} · ${DRInspection.milliseconds(current?.[1],data.timeline)} · ${DRInspection.relayTime(current?.[1],data.timeline)}`;
    const first=shown()[0],a=cursorValues.get('A')?.get(first),b=cursorValues.get('B')?.get(first);
    mount.querySelector('.inspection-delta').textContent=a&&b?`B − A: ${DRInspection.delta(a,b).samples} samples · ${DRInspection.delta(a,b).seconds===null?'Time difference not available':(DRInspection.delta(a,b).seconds*1000).toPrecision(9)+' ms (source coordinates)'}`:'B − A: waiting for exact cursor observations.';
  }
  async function getSamples(id,lo,hi,controller) {
    const query=new URLSearchParams({revision:row.number,record:data.file,channel_id:id,start_index:lo,stop_index:hi});
    const response=await fetch(`/api/incidents/${row.incident_id}/inspection/samples?${query}`,{signal:controller.signal});
    const body=await response.json();if(!response.ok)throw new Error(body.detail||'Native observations unavailable.');
    if(body.file!==data.file||body.revision!==row.number||body.channel_id!==id||DRInspection.identity(body.source_sha256)!==DRInspection.identity(data.source_sha256))throw new Error('Source identity changed; reopen recording.');
    return body;
  }
  function loadHover(){return loadCursors();}
  async function loadCursors() {
    hoverController?.abort();if(recordController.signal.aborted)return;
    const controller=new AbortController();hoverController=controller;
    recordController.signal.addEventListener('abort',()=>controller.abort(),{once:true,signal:controller.signal});
    const names=[...pins(),['hover',s.hover]],ids=shown(),indices=[...new Set(names.map(([,i])=>i))],token=s.request('points');
    cursorValues.clear();cursorRms.clear();values();if(!ids.length)return;
    const current=()=>s.accept(token)&&!controller.signal.aborted&&host.isConnected&&
      names.every(([name,index])=>(name==='hover'?s.hover:s.pins[name])===index)&&ids.join(',')===shown().join(',');
    try {
      let channels=DRInspection.exactPoints(native,ids,indices);
      if(!channels){
        channels=[];for(let offset=0;offset<ids.length;offset+=8){
        const query=new URLSearchParams({revision:row.number,record:data.file,channel_ids:JSON.stringify(ids.slice(offset,offset+8)),indices:JSON.stringify(indices)});
        const response=await fetch(`/api/incidents/${row.incident_id}/inspection/points?${query}`,{signal:controller.signal});
        const body=await response.json();if(!response.ok)throw new Error(body.detail||'Cursor observations unavailable.');
        if(body.file!==data.file||body.revision!==row.number||DRInspection.identity(body.source_sha256)!==DRInspection.identity(data.source_sha256))throw new Error('Source identity changed; reopen recording.');
        channels.push(...body.channels);}
      }
      if(current()){for(const[name,index]of names){
        cursorValues.set(name,new Map(channels.map(c=>[c.id,c.samples[indices.indexOf(index)]])));
        cursorRms.set(name,new Map(channels.map(c=>[c.id,c.rms_samples?.[indices.indexOf(index)]||DRInspection.exactPoints(nativeRms,[c.id],[index])?.[0]?.samples[0]])));
      }values();}
    }catch(error){if(error.name!=='AbortError'&&current())mount.querySelector('.inspection-load').textContent=error.message;}
  }
  async function loadView() {
    if(recordController.signal.aborted)return;
    clearTimeout(hoverTimer);viewController?.abort();hoverController?.abort();s.invalidate();native.clear();nativeRms.clear();cursorValues.clear();cursorRms.clear();drawPaths();values();
    const controller=new AbortController();viewController=controller;
    recordController.signal.addEventListener('abort',()=>controller.abort(),{once:true,signal:controller.signal});
    const lo=Math.ceil(s.view[0]),hi=Math.floor(s.view[1])+1,token=s.request('view');
    const status=mount.querySelector('.inspection-load');status.textContent=hi-lo<=20000?'Loading exact native observations…':'Display envelopes; zoom to ≤20000 samples for native paths. Cursors always use exact observations.';
    if(hi-lo<=20000){try{const entries=await DRTransport.mapLimit(shown(),4,async id=>[id,await getSamples(id,lo,hi,controller)],controller.signal);
      if(s.accept(token)&&!controller.signal.aborted&&host.isConnected){for(const[id,body]of entries){native.set(id,body.samples);if(body.rms_samples?.length)nativeRms.set(id,body.rms_samples);}status.textContent='Native observations loaded. Unknown states and missing amplitudes stay blank.';drawPaths();}
    }catch(error){if(error.name!=='AbortError'&&s.accept(token)&&!controller.signal.aborted&&host.isConnected){status.textContent=error.message;native.clear();drawPaths();}}}
    if(s.accept(token)&&!controller.signal.aborted)loadCursors();
  }
  function movePin(name,index){follow=name;s.move(name,index);const moved=s.follow(s.pins[name]);controls();if(moved){drawSlots();loadView();}else{drawPaths();loadCursors();}}
  mount.querySelector('.inspection-plots').onkeydown=e=>{if(['INPUT','SELECT','BUTTON'].includes(e.target?.tagName)||e.target===overview)return;if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();movePin(active,s.pins[active]+(e.key==='ArrowLeft'?-1:1));}};
  mount.querySelectorAll('[data-action]').forEach(button=>{if(button.dataset.action==='add-pin')return;button.onclick=()=>{const action=button.dataset.action;if(action==='in')s.zoom(.5);if(action==='out')s.zoom(2);if(action==='left')s.pan(-.5);if(action==='right')s.pan(.5);if(action==='reset')s.reset();if(action==='prev')page--;if(action==='next')page++;drawSlots();loadView();};});
  recordController.signal.addEventListener('abort',()=>{clearTimeout(hoverTimer);hoverController?.abort();viewController?.abort();s.invalidate();},{once:true});
  controls();drawSlots();loadView();
  return {setAnalysis(result){analysis=result;drawSlots();},getPins(){return {...s.pins};},getPoint(name){const point=cursorValues.get(name)?.get(shown()[0]);return point?.[0]===s.pins[name]?point:null;},focusWindow(lo,hi){s.view=[Math.max(0,lo),Math.min(s.n-1,Math.max(lo+1,hi-1))];drawSlots();loadView();mount.scrollIntoView({block:"start",behavior:"smooth"});}};
}
