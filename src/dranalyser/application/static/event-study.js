'use strict';
// This view presents one backend report. It does not infer fault boundaries,
// synchronize clocks, convert scaling or calculate a new fault distance.
const DREventStudy=(()=>{
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const arr=v=>Array.isArray(v)?v:[];
  const finite=v=>typeof v==='number'&&Number.isFinite(v);
  const num=v=>finite(v)?v===0?'0':Number(v.toPrecision(5)).toString():'Not available';
  const roles={S:'Sending end (S)',R:'Receiving end (R)'};
  const regions=['pre','fault','post'];
  const regionName=kind=>({pre:'Pre-fault',fault:'Fault',post:'Post-fault'}[kind]);
  const colors=['#d62d39','#a67400','#2463cf','#526678'];
  const channelColor=(channel,index)=>{const phase=/([ABC])$/.exec(channel.meaning||'');return colors[phase?'ABC'.indexOf(phase[1]):index%colors.length];};
  const live=new WeakMap();
  const interpretation=value=>String(value||'Comparison unavailable').replace(' between the selected regions; this alone does not establish fault type or breaker operation.','.');
  const list=items=>'<ul>'+arr(items).map(v=>'<li>'+esc(v)+'</li>').join('')+'</ul>';
  function timingFields(role){
    return `<label>Analysis timings<select name="${role}.timing_mode"><option value="auto">Automatic · from recording</option><option value="manual">Manual adjustment</option></select></label><div class="event-study-timing" data-timing-summary="${role}" role="status">Choose a recording to select timings automatically.</div><button type="button" data-auto-timing="${role}">Auto select timings</button>`;
  }
  function endFields(role){
    return `<fieldset class="event-study-end" data-event-end="${role}"><legend>${roles[role]}</legend><label>Recording${role==='R'?' · optional':''}<select name="${role}.record"><option value="">Choose recording</option></select></label><label>Substation name<input name="${role}.substation" maxlength="160" placeholder="Enter substation name"></label><p class="event-study-help" data-end-meta="${role}"></p>${timingFields(role)}<details data-manual-timing="${role}" hidden><summary>Adjust pre-fault, fault and post-fault intervals</summary><p>Choose stable pre-fault samples and the fault interval separately. Use source sample indices; the start is included and the end is excluded. Empty intervals leave comparison values unavailable.</p><div class="event-study-ranges">${regions.map(kind=>`<fieldset><legend>${regionName(kind)} samples</legend><label>Start<input name="${role}.${kind}.0" type="number" min="0" step="1" placeholder="Not selected"></label><label>End, excluded<input name="${role}.${kind}.1" type="number" min="1" step="1" placeholder="Not selected"></label><button type="button" data-request-region="${role}:${kind}">Use waveform A–B</button></fieldset>`).join('')}</div></details><details><summary>Relay-reported distance · optional</summary><p>Enter the relay reading and its reference end. This remains separate from the application calculation.</p><label>Distance, km<input name="${role}.relay.km" type="number" min="0" step="any" placeholder="Not supplied"></label><label>Measured from<select name="${role}.relay.reference"><option value="">Choose reference end</option><option value="S">Sending end (S)</option><option value="R">Receiving end (R)</option></select></label><label>Source of this reading<input name="${role}.relay.evidence" maxlength="500" placeholder="Relay event report or setting reference"></label></details></fieldset>`;
  }
  function panel(row={}){
    return `<section class="event-study" data-event-study data-incident="${esc(row.incident_id??row.id??'')}"><header><h2>Simple event analysis</h2><p>Compare both ends of one fault: voltages, currents, selected pre-fault and fault values, digital indications and available distance evidence.</p></header><form data-event-study-form><div class="event-study-end-grid">${endFields('S')}${endFields('R')}</div><label class="event-study-confirm"><input type="checkbox" name="same_event_confirmed"> I confirm these recordings are from opposite physical ends of the same event.</label><p class="event-study-help">Keep successive DR1/DR2 captures from the same relay separate and inspect or compare them at one end. Joining/export is not available. They are not opposite line ends.</p><div class="event-study-actions"><button type="submit" disabled>Build event report</button><span data-event-study-status role="status" aria-live="polite">Loading recording choices…</span></div><details class="event-study-explain"><summary>Which inputs do I need?</summary><p>For waveform inspection, choose a recording. Timings are selected automatically from supported changes in each recording; manual adjustment is optional. Review universal CT/VT ratios and channel meanings in Inputs before interpreting primary values. Applied channel-meaning and digital-polarity choices carry into this report for display; they do not assign physical ends or authorize an operational calculation.</p><p>For a fault-distance calculation, use Calculate fault location above with the actual line model, physical end assignments and method-specific evidence. Advanced operational review remains in More tools. This report presents its eligible existing result with its method and reference. Digital operation times require reviewed signal meanings, polarity and suitable contact evidence.</p></details></form><div data-event-study-output></div></section>`;
  }
  function collect(values){
    const get=name=>String(typeof values==='function'?values(name)??'':values[name]??'').trim();
    const checked=typeof values==='function'?values('same_event_confirmed')===true:values.same_event_confirmed===true;
    const ends={};
    for(const role of ['S','R']){
      const record=get(role+'.record');
      if(!record){if(role==='S')throw new Error('Choose the sending-end recording.');continue;}
      const substation=get(role+'.substation');
      if(!substation)throw new Error('Enter the '+roles[role].toLowerCase()+' substation name.');
      const timing_mode=get(role+'.timing_mode')||'manual';
      if(!['auto','manual'].includes(timing_mode))throw new Error('Choose automatic or manual timings.');
      const end={record,substation,timing_mode};
      for(const kind of regions){
        if(timing_mode==='auto'){end[kind]=null;continue;}
        const lo=get(`${role}.${kind}.0`),hi=get(`${role}.${kind}.1`);
        if(!lo&&!hi){end[kind]=null;continue;}
        const a=Number(lo),b=Number(hi);
        if(!lo||!hi||!Number.isSafeInteger(a)||!Number.isSafeInteger(b)||a<0||b<=a)throw new Error(`${roles[role]}: ${regionName(kind).toLowerCase()} samples need an integer start ≥ 0 and an excluded end greater than the start.`);
        end[kind]=[a,b];
      }
      if(end.pre&&end.fault&&end.pre[1]>end.fault[0])throw new Error(roles[role]+': pre-fault samples must finish before the fault interval begins.');
      const before=end.fault||end.pre;
      if(before&&end.post&&before[1]>end.post[0])throw new Error(roles[role]+': post-fault samples must begin after the preceding interval ends.');
      const km=get(role+'.relay.km'),reference=get(role+'.relay.reference'),evidence=get(role+'.relay.evidence');
      end.relay_distance=null;
      if(km||reference||evidence){
        if(km===''||!finite(Number(km))||Number(km)<0||!['S','R'].includes(reference)||!evidence)throw new Error(`${roles[role]}: a relay distance needs nonnegative kilometres, its reference end and the source of the reading.`);
        end.relay_distance={km:Number(km),reference,evidence};
      }
      ends[role]=end;
    }
    if(ends.R&&ends.R.record===ends.S.record)throw new Error('Choose distinct opposite-end recordings. A recording cannot represent both ends.');
    if(ends.R&&!checked)throw new Error('Confirm that the selected recordings are opposite physical ends of the same event.');
    return {same_event_confirmed:!!ends.R&&checked,ends};
  }
  function coordinates(model){
    const ends=Object.values(model.ends||{}).filter(Boolean),relative=ends.length>0&&ends.every(end=>finite(end.origin_s));
    const shift=end=>relative?end.origin_s:0;
    let lo=Infinity,hi=-Infinity;
    for(const end of ends)for(const kind of ['voltage','current'])for(const channel of arr(end.groups?.[kind]))for(const point of arr(channel.trace))if(Array.isArray(point)&&finite(point[1])){const x=(point[1]-shift(end))*1000;lo=Math.min(lo,x);hi=Math.max(hi,x);}
    if(!finite(lo)||!finite(hi)){lo=0;hi=1;}else if(lo===hi)hi=lo+1;
    return {lo,hi,relative,shift,label:relative?'ms from each selected fault start · display alignment only':'source-local ms · clocks are not synchronized'};
  }
  function tracePaths(points,x,y){
    const paths=[];let path='',previousIndex=null;
    for(const point of arr(points)){
      if(!Array.isArray(point)||!finite(point[1])||!finite(point[2])){if(path)paths.push(path);path='';previousIndex=null;continue;}
      // Nulls and backwards samples remain breaks. Source gaps are supplied as nulls.
      if(previousIndex!==null&&point[0]<=previousIndex){if(path)paths.push(path);path='';}
      path+=(path?'L':'M')+x(point[1]).toFixed(2)+','+y(point[2]).toFixed(2);previousIndex=point[0];
    }
    if(path)paths.push(path);return paths;
  }
  function plot(end,kind,space,mode='trace',role='S'){
    const channels=arr(end?.groups?.[kind]),title=(kind==='voltage'?'Voltages':'Currents')+' · '+roles[role];
    const units=[...new Set(channels.map(c=>c.units||'Unknown units'))];
    if(!end||!channels.length)return `<section class="event-study-plot event-study-empty"><h4>${esc(title)}</h4><p>${end?'No mapped '+kind+' phase channels are available. Review channel meanings in Inputs.':'Choose an opposite-end recording to compare this quantity.'}</p></section>`;
    if(units.length!==1)return `<section class="event-study-plot event-study-empty"><h4>${esc(title)}</h4><p>Phase units differ. Review scaling and channel meanings before overlaying these values.</p></section>`;
    const W=760,H=240,L=82,R=18,T=16,B=40,w=W-L-R,h=H-T-B,shift=space.shift(end);
    const values=channels.flatMap(c=>arr(c[mode]).filter(p=>Array.isArray(p)&&finite(p[2])).map(p=>p[2]));
    let min=values.length?Math.min(...values):0,max=values.length?Math.max(...values):1;
    if(mode==='rms_trace'&&values.every(value=>value>=0)){min=0;max=max>0?max*1.08:1;}
    else if(min===max){const margin=Math.max(1,Math.abs(min)*0.1);min-=margin;max+=margin;}else{const margin=(max-min)*0.08;min-=margin;max+=margin;}
    const x=t=>L+((t-shift)*1000-space.lo)/(space.hi-space.lo)*w,y=v=>T+(max-v)/(max-min)*h;
    const ticks=[0,.25,.5,.75,1],grid=ticks.map(f=>{const yy=T+h*f,value=max-(max-min)*f;return `<line x1="${L}" y1="${yy}" x2="${W-R}" y2="${yy}" class="event-study-gridline"/><text x="${L-8}" y="${yy+4}" text-anchor="end">${esc(num(value))}</text>`;}).join('');
    const xticks=ticks.map(f=>{const xx=L+w*f;return `<text x="${xx}" y="${H-17}" text-anchor="middle">${esc(num(space.lo+(space.hi-space.lo)*f))}</text>`;}).join('');
    const paths=channels.map((c,i)=>tracePaths(c[mode],x,y).map(d=>`<path d="${d}" fill="none" stroke="${channelColor(c,i)}" stroke-width="1.35"/>`).join('')).join('');
    const zero=space.lo<=0&&space.hi>=0?`<line x1="${L-space.lo/(space.hi-space.lo)*w}" x2="${L-space.lo/(space.hi-space.lo)*w}" y1="${T}" y2="${H-B}" class="event-study-zero"/>`:'';
    return `<section class="event-study-plot"><h4>${esc(title)}</h4><p class="event-study-help" title="${esc(end.substation+' · '+end.record+' · '+units[0])}">${esc(end.substation)} · ${esc(end.record)} · ${esc(units[0])}</p><div class="event-study-legend">${channels.map((c,i)=>`<span><i style="background:${channelColor(c,i)}"></i>${esc(c.meaning||c.label||c.id)}</span>`).join('')}</div><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(title+'; '+units[0]+'; '+space.label)}" data-event-plot="${role}:${kind}" data-plot-left="${L}" data-plot-width="${w}">${grid}${zero}${paths}${xticks}<line class="event-study-cursor" x1="${L}" x2="${L}" y1="${T}" y2="${H-B}" visibility="hidden"/></svg>${values.length?'':'<p>No '+(mode==='rms_trace'?'one-cycle RMS':'recorded waveform')+' observations are available in this capture. Gaps are not filled.</p>'}</section>`;
  }
  function phaseTable(end,role){
    const rows=arr(end?.phase_values);
    return `<section class="event-study-values"><h4>${roles[role]}${end?' · '+esc(end.substation):''}</h4>${end?'<p class="event-study-help">Selected sample intervals: '+regions.map(kind=>regionName(kind)+' '+(arr(end[kind]).length===2?'['+end[kind].map(esc).join(', ')+')':'not selected')).join(' · ')+'.</p>':''}${rows.length?'<div class="event-study-table-wrap" tabindex="0" role="region" aria-label="'+roles[role]+' pre-fault and fault RMS values"><table><thead><tr><th>Phase / units</th><th>Pre-fault RMS</th><th>Fault RMS</th><th>Post-fault RMS</th><th>Fault change</th></tr></thead><tbody>'+rows.map(c=>`<tr><th>${esc(c.meaning||c.label||c.id)}<small>${esc(c.units||'Unknown units')}</small></th><td>${num(c.pre_rms)}</td><td>${num(c.fault_rms)}</td><td>${num(c.post_rms)}</td><td class="event-study-change" data-direction="${finite(c.change_percent)?c.change_percent>0?'rise':c.change_percent<0?'fall':'steady':'unknown'}">${finite(c.change_percent)?(c.change_percent>0?'↑ ':c.change_percent<0?'↓ ':'↔ ')+num(c.change_percent)+'%':'Not available'}<small>${esc(interpretation(c.interpretation))}</small>${c.reason?'<small>'+esc(c.reason)+'</small>':''}</td></tr>`).join('')+'</tbody></table></div>':'<p>No selected-end phase comparison is available.</p>'}${end?.timing_mode==='auto'?'<details><summary>Automatic timing evidence</summary>'+timingMarkup(end.timing_evidence)+'</details>':''}${list(end?.insights)}</section>`;
  }
  function digital(end,role){
    const d=end?.digital||{},events=arr(d.events);
    return `<section><h4>${roles[role]}${end?' · '+esc(end.substation):''}</h4>${list(d.insights)}${events.length?'<div class="event-study-table-wrap" tabindex="0" role="region" aria-label="'+roles[role]+' observed digital transitions"><table><thead><tr><th>Recorded signal</th><th>Observed change</th><th>Local time</th><th>From selected fault start</th></tr></thead><tbody>'+events.map(e=>`<tr><th>${esc(e.label||e.id)}<small>${esc(e.meaning||'Meaning not assigned')}</small></th><td>${esc(e.interpretation_available===true?e.kind||'Change':'Observed transition; meaning or polarity unreviewed')}<small>Sample ${esc(e.index)}${arr(e.sample_bracket).length===2?' · bracket ['+esc(e.sample_bracket.join(', '))+']':''}</small></td><td>${finite(e.source_s)?num(e.source_s*1000)+' ms':'Not available'}${arr(e.source_bracket_s).length===2?'<small>Bracket '+e.source_bracket_s.map(t=>finite(t)?num(t*1000):'unknown').join(' to ')+' ms</small>':''}</td><td>${finite(e.relative_fault_s)?num(e.relative_fault_s*1000)+' ms':'Not available'}</td></tr>`).join('')+'</tbody></table></div>':'<p>No interpreted transition is listed in the selected capture. This does not establish that no operation occurred.</p>'}${d.omitted_events?'<p>'+esc(d.omitted_events)+' more observed transitions remain in technical evidence.</p>':''}</section>`;
  }
  function distance(model){
    const d=model.distance||{},km=finite(d.km_from_S)&&d.method?d.km_from_S:null;
    return `<section class="event-study-distance"><h3>Fault-distance evidence</h3><p><strong>${km===null?'Calculated distance unavailable':num(km)+' km from '+esc(roles[d.reference]||d.reference||'Sending end')}</strong></p><p>${esc(d.text||d.status||'No eligible calculation is stored.')}</p><p>Method: ${esc(d.method||'Not available')}</p><p>${esc(d.reason||'')}</p>${d.next_action?'<details><summary>Inputs needed for distance</summary><p>'+esc(typeof d.next_action==='string'?d.next_action:d.next_action.label)+'</p>'+list(d.next_action.requirements)+'<button type="button" data-go-feature="study">Open operational study</button></details>':''}${d.source_records&&Object.keys(d.source_records).length?'<p>Calculation records: '+Object.entries(d.source_records).map(([role,file])=>esc((roles[role]||role)+' · '+file)).join('; ')+'.</p>':''}${arr(model.relay_distances).length?'<h4>Relay-reported distance</h4><ul>'+model.relay_distances.map(r=>`<li>${roles[r.end]||esc(r.end)} reading: <strong>${num(r.km)} km</strong> from ${roles[r.reference]||esc(r.reference)}. Source: ${esc(r.evidence)}${finite(r.delta_to_calculated_km)?' · Difference from calculation: '+num(r.delta_to_calculated_km)+' km':''}${r.reason?' · '+esc(r.reason):''}</li>`).join('')+'</ul>':'<p>Relay-reported distance has not been supplied.</p>'}<p class="event-study-help">The method, reference end, selected records and input quality govern a calculated result. A relay reading is separate evidence; neither establishes the actual physical fault position by itself.</p></section>`;
  }
  function explanation(model){
    const summary=model.explanation;
    if(!summary)return '';
    const evidence=entry=>`${entry.record?' · '+entry.record:''}${entry.events?.length?' · samples '+entry.events.map(event=>arr(event.sample_bracket).join('–')).join(', '):entry.regions?.fault?' · fault samples ['+entry.regions.fault.join(', ')+')':''}`;
    return `<section class="event-study-explanation"><h3>${esc(summary.title||'What the recordings show')}</h3><h4>Observed</h4>${arr(summary.observations).length?'<ul>'+summary.observations.map(entry=>'<li>'+esc(entry.text)+'<small>'+esc(evidence(entry))+'</small></li>').join('')+'</ul>':'<p>No supported pre-fault/fault change summary is available. Inspect the recoverable source waveforms.</p>'}${arr(summary.interpretation).length?'<h4>Interpretation</h4>'+list(summary.interpretation.map(entry=>entry.text)):''}<p>${esc(summary.protection_verdict||'')}</p><details><summary>What remains uncertain</summary>${list(summary.uncertainty)}</details></section>`;
  }
  function lineView(model){
    const line=model.line||{},length=line.length_km,d=model.distance||{};
    if(!finite(length)||length<=0)return '<p class="event-study-help">A declared line length is needed for the line sketch. No topology or towers are assumed.</p>';
    const km=finite(d.km_from_S)&&d.method&&d.km_from_S>=0&&d.km_from_S<=length?d.km_from_S:null;
    const marker=km===null?'':`<circle cx="${80+640*km/length}" cy="58" r="7" fill="#ad4c21"/><text x="${80+640*km/length}" y="90" text-anchor="middle">${esc(num(km))} km · ${esc(d.method)}</text>`;
    const sections=arr(line.sections).filter(s=>finite(s.to_km)&&s.to_km>0&&s.to_km<length).map(s=>`<line x1="${80+640*s.to_km/length}" x2="${80+640*s.to_km/length}" y1="50" y2="66" stroke="#52677c"/>`).join('');
    return `<section class="event-study-line"><h3>Declared line · ${esc(line.name||line.id||'Line')}</h3><svg viewBox="0 0 800 115" role="img" aria-label="${esc('Declared full line '+num(length)+' km; '+(km===null?'no eligible fault location':num(km)+' km from S by '+d.method))}"><line x1="80" x2="720" y1="58" y2="58" stroke="#52677c" stroke-width="3"/><text x="80" y="24">S · ${esc(line.terminals?.S||'Not supplied')}</text><text x="720" y="24" text-anchor="end">R · ${esc(line.terminals?.R||'Not supplied')}</text><text x="80" y="108">0 km</text><text x="720" y="108" text-anchor="end">${esc(num(length))} km</text>${sections}${marker}</svg><p class="event-study-help">Full declared length; the marker is the stored method-labelled operational location, not cursor projection. Line parameters: ${esc(line.parameter_status||'unverified')}. No tower chainage, breaker position or unrecorded topology is invented.</p></section>`;
  }
  function navigationView(model){
    if(!model.navigation?.available)return '';
    return `<details class="event-study-navigation"><summary>R–X and source-local event view</summary><p>${esc(model.navigation.note)} The report inspection cursor can follow the same selected source only; it never synchronizes ends.</p><button type="button" data-event-open-navigation>Open existing R–X view</button><div data-event-navigation-host></div></details>`;
  }
  function markup(model,mode='trace'){
    const space=coordinates(model),ends=model.ends||{};
    return `<article class="event-study-report"><p class="event-study-stale" data-event-stale hidden>Inputs have changed. Build the event report to apply them; the report below still shows the previous choices.</p><header><h2>Event report</h2><p>Incident ${esc(model.incident_id)} · Revision ${esc(model.revision)}</p></header>${explanation(model)}<section><div class="event-study-heading"><h3>Both-end waveform overview</h3><label>Display<select data-event-mode><option value="trace"${mode==='trace'?' selected':''}>Recorded waveform</option><option value="rms_trace"${mode==='rms_trace'?' selected':''}>One-cycle RMS</option></select></label></div><p class="event-study-help">${esc(space.label)}. Each plot has its own labelled vertical scale. These overviews do not establish clock alignment or exact cursor values.</p><div class="event-study-quantity-row">${plot(ends.S,'voltage',space,mode,'S')}${plot(ends.R,'voltage',space,mode,'R')}</div><div class="event-study-quantity-row">${plot(ends.S,'current',space,mode,'S')}${plot(ends.R,'current',space,mode,'R')}</div><label class="event-study-inspector">Inspect the full displayed span<input type="range" min="0" max="10000" step="1" value="0" data-event-inspector><output data-event-cursor-label>Move over a plot or use this slider. Click a plot to hold the inspection line.</output></label><p class="event-study-help">Use the Waveforms page for exact instantaneous values, one-cycle RMS, vectors and source sample cursors.</p></section><section><h3>Pre-fault, fault and optional post-fault comparison</h3><p>RMS values use the selected source intervals and stated units. Empty values retain their reason; zero is a real value. Primary quantities require reviewed CT/VT scaling. Region changes alone do not establish fault type or breaker operation.</p>${list([...new Set(Object.values(ends).map(end=>end?.rms_basis).filter(Boolean))])}<div class="event-study-end-grid">${phaseTable(ends.S,'S')}${phaseTable(ends.R,'R')}</div></section>${distance(model)}${lineView(model)}${navigationView(model)}<section><h3>Digital indications and timing</h3><p>Times below are observed source transitions. A trip indication alone does not prove circuit-breaker opening; AR command alone does not prove successful reclosure. Reviewed meanings, polarity and suitable contacts are needed for those conclusions.</p><div class="event-study-end-grid">${digital(ends.S,'S')}${digital(ends.R,'R')}</div></section>${arr(model.notes).length?'<section><h3>Evidence and limits</h3>'+list(model.notes)+'</section>':''}<div class="event-study-actions"><button type="button" data-event-download="html">Download report</button><button type="button" data-event-download="json">Download report data</button></div></article>`;
  }
  function withChoices(inputs,saved={},sourceChoices){
    const result=JSON.parse(JSON.stringify(inputs));
    for(const end of Object.values(result.ends)){
      const prior=Object.values(saved.ends||{}).find(item=>item.record===end.record)||{};
      const choice=typeof sourceChoices==='function'?sourceChoices(end.record):undefined;
      for(const key of ['mappings','asserted_states']){
        const value=choice&&Object.prototype.hasOwnProperty.call(choice,key)?choice[key]:prior[key];
        if(value!==undefined)end[key]=JSON.parse(JSON.stringify(value));
      }
    }
    return result;
  }
  function timingMarkup(value){
    if(!value)return '<p>Choose a recording to select timings automatically.</p>';
    const offset=finite(value.timeline?.trigger_offset_s)?value.timeline.trigger_offset_s:0;
    const point=t=>num((t-offset)*1000)+' ms';
    const rows=regions.map(kind=>{const bounds=value[kind],span=value.intervals?.[kind];return '<li><strong>'+regionName(kind)+':</strong> '+(span?point(span.start_s)+' to '+point(span.last_s):Array.isArray(bounds)?'samples ['+esc(bounds.join(', '))+')':'Unavailable')+'</li>';});
    return '<p><strong>'+esc(value.status==='manual'?'Manual selection':'Automatic timings · '+value.status)+'</strong></p><p>'+ (finite(value.timeline?.trigger_offset_s)?'Times relative to the recorded trigger (0 ms).':'Times in source-local milliseconds.')+'</p><ul>'+rows.join('')+'</ul><p>'+esc(value.reason||value.method||'')+'</p>'+list(value.notes||[]);
  }
  function bind(row,host,signal,options={}){
    const root=host?.matches?.('[data-event-study]')?host:host?.querySelector?.('[data-event-study]');
    if(!root)return {destroy(){},applyRegion(){return false;}};
    live.get(root)?.abort();const controller=new AbortController(),local=controller.signal;live.set(root,controller);
    if(signal?.aborted)controller.abort();else signal?.addEventListener('abort',()=>controller.abort(),{once:true});
    const form=root.querySelector('form'),status=root.querySelector('[data-event-study-status]'),output=root.querySelector('[data-event-study-output]');
    const submit=form.querySelector('[type=submit]'),base='/api/incidents/'+encodeURIComponent(row.incident_id??row.id)+'/event-study',revision=row.number??row.revision??row.current_revision??1;
    let version=0,records=[],model=null,busy=false,mode='trace',held=false,savedInputs={},navigationHandle=null,navigationRequest=0;
    const automatic=new Map(),pending=new Map();
    const current=()=>!local.aborted&&root.isConnected;
    const field=name=>form.elements.namedItem(name);
    const setStatus=(message,error=false)=>{if(current()){status.textContent=message;status.classList.toggle('event-study-error',error);}};
    function stale(){const warning=output.querySelector('[data-event-stale]');if(warning)warning.hidden=false;setStatus('Inputs changed. Build the event report to apply them.');}
    const freeze=value=>{form.querySelectorAll('input,select,button').forEach(control=>{control.disabled=value;});if(!value)for(const role of ['S','R'])syncTiming(role);};
    const request=async(path,options={})=>{
      if(typeof api!=='function')throw new Error('Application API is unavailable. Reload this page.');
      return api(path,{...options,signal:options.signal||local});
    };
    const json=(method,body)=>({method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    function syncTiming(role){
      const auto=field(role+'.timing_mode').value==='auto',details=form.querySelector('[data-manual-timing="'+role+'"]');
      details.hidden=auto;
      for(const kind of regions)for(const i of [0,1])field(`${role}.${kind}.${i}`).disabled=auto||busy;
    }
    function choicesFor(role){
      const record=field(role+'.record').value;
      return withChoices({ends:{[role]:{record}}},savedInputs,options.sourceChoices).ends[role];
    }
    function selectTimings(role){
      automatic.get(role)?.abort();const record=field(role+'.record').value;
      if(!record||field(role+'.timing_mode').value!=='auto')return Promise.resolve();
      const child=new AbortController();automatic.set(role,child);local.addEventListener('abort',()=>child.abort(),{once:true,signal:child.signal});
      const choices=choicesFor(role),signature=JSON.stringify(choices),target=form.querySelector('[data-timing-summary="'+role+'"]');
      target.textContent='Selecting pre-fault, fault and post-fault timings…';
      const valid=()=>current()&&!child.signal.aborted&&field(role+'.record').value===record&&field(role+'.timing_mode').value==='auto'&&JSON.stringify(choicesFor(role))===signature;
      const task=request(base+'/regions',{...json('POST',{revision,record,mappings:choices.mappings||{},asserted_states:choices.asserted_states||{}}),signal:child.signal}).then(value=>{
        if(!valid())return;
        const inventory=records.find(item=>item.file===record),hash=v=>JSON.stringify(Object.entries(v||{}).sort(([a],[b])=>a.localeCompare(b)));
        if(value.file!==record||value.revision!==revision||(inventory?.source_sha256&&hash(value.source_sha256)!==hash(inventory.source_sha256)))throw new Error('Automatic timings source identity changed; reopen the recording.');
        for(const kind of regions)for(const i of [0,1])field(`${role}.${kind}.${i}`).value=value[kind]?.[i]??'';
        target.innerHTML=timingMarkup(value);if(inventory)inventory.sample_count=value.sample_count;describe(role);
      }).catch(error=>{if(valid())target.textContent=error.message||'Automatic timings are unavailable. You may adjust them manually.';}).finally(()=>{if(pending.get(role)===task)pending.delete(role);});
      pending.set(role,task);return task;
    }
    function describe(role){
      const selected=records.find(r=>r.file===field(role+'.record').value),node=form.querySelector('[data-end-meta="'+role+'"]');
      node.textContent=selected?[selected.station,selected.device,Number.isInteger(selected.sample_count)?selected.sample_count+' samples':'Sample count available when decoded'].filter(Boolean).join(' · '):'Choose the recording for this physical end.';
      for(const kind of regions)for(const i of [0,1]){const input=field(`${role}.${kind}.${i}`);if(Number.isInteger(selected?.sample_count)&&selected.sample_count>0)input.max=String(selected.sample_count);else input.removeAttribute('max');}
    }
    function populate(inputs={}){
      for(const role of ['S','R']){
        const end=inputs.ends?.[role]||{};
        field(role+'.record').value=end.record||'';field(role+'.substation').value=end.substation||'';
        field(role+'.timing_mode').value=end.record?(end.timing_mode||(regions.some(kind=>Array.isArray(end[kind]))?'manual':'auto')):'auto';
        for(const kind of regions)for(const i of [0,1])field(`${role}.${kind}.${i}`).value=end[kind]?.[i]??'';
        for(const key of ['km','reference','evidence'])field(role+'.relay.'+key).value=end.relay_distance?.[key]??'';
        describe(role);
        syncTiming(role);form.querySelector('[data-timing-summary="'+role+'"]') .innerHTML=timingMarkup(end.timing_evidence||{...end,status:end.record?'manual':'unavailable'});
      }
      field('same_event_confirmed').checked=inputs.same_event_confirmed===true;
    }
    function applyAutomaticReport(report){
      for(const [role,end] of Object.entries(report.ends||{}))if(end.timing_mode==='auto'&&field(role+'.record').value===end.record){
        for(const kind of regions)for(const i of [0,1])field(`${role}.${kind}.${i}`).value=end[kind]?.[i]??'';
        form.querySelector('[data-timing-summary="'+role+'"]') .innerHTML=timingMarkup(end.timing_evidence);
      }
    }
    function cursor(fraction){
      if(!model)return;fraction=Math.max(0,Math.min(1,fraction));const space=coordinates(model),time=space.lo+(space.hi-space.lo)*fraction;
      output.querySelectorAll('[data-event-plot]').forEach(svg=>{const line=svg.querySelector('.event-study-cursor'),x=Number(svg.dataset.plotLeft)+Number(svg.dataset.plotWidth)*fraction;line.setAttribute('x1',x);line.setAttribute('x2',x);line.setAttribute('visibility','visible');});
      output.querySelector('[data-event-inspector]').value=String(Math.round(fraction*10000));
      output.querySelector('[data-event-cursor-label]').textContent=num(time)+' '+space.label+(held?' · held; click a plot to release':'');
      navigationHandle?.followCursor(Object.fromEntries(Object.values(model.ends||{}).map(end=>[end.record,time/1000+space.shift(end)])));
    }
    function render(){if(current()&&model){
      for(const end of Object.values(model.ends||{})){const record=records.find(item=>item.file===end.record);if(record&&Number.isInteger(end.sample_count)&&end.sample_count>0)record.sample_count=end.sample_count;}
      for(const role of ['S','R'])describe(role);
      output.innerHTML=markup(model,mode);held=false;navigationHandle=null;navigationRequest++;
    }}
    form.addEventListener('input',stale,{signal:local});
    form.addEventListener('change',event=>{stale();for(const role of ['S','R']){
      if(event.target===field(role+'.record')){field('same_event_confirmed').checked=false;field(role+'.timing_mode').value='auto';for(const kind of regions)for(const i of [0,1])field(`${role}.${kind}.${i}`).value='';describe(role);syncTiming(role);selectTimings(role);}
      if(event.target===field(role+'.timing_mode')){automatic.get(role)?.abort();syncTiming(role);if(event.target.value==='auto')selectTimings(role);else form.querySelector('[data-timing-summary="'+role+'"]') .textContent='Manual adjustment: retained intervals can be edited below.';}
    }},{signal:local});
    form.addEventListener('click',event=>{
      const auto=event.target.closest('[data-auto-timing]');if(auto){const role=auto.dataset.autoTiming;field(role+'.timing_mode').value='auto';syncTiming(role);stale();selectTimings(role);return;}
      const button=event.target.closest('[data-request-region]');if(!button)return;
      const [role,kind]=button.dataset.requestRegion.split(':'),record=field(role+'.record').value;
      if(!record){setStatus('Choose the '+roles[role].toLowerCase()+' recording first.',true);return;}
      setStatus('In Waveforms, choose A and B for '+record+', then apply them to this '+regionName(kind).toLowerCase()+' interval. You can also type its sample indices.');
      root.dispatchEvent(new CustomEvent('event-study-request-region',{bubbles:true,detail:{record,role,kind}}));
    },{signal:local});
    form.addEventListener('submit',async event=>{
      event.preventDefault();if(busy)return;
      try{
        if(!form.reportValidity())return;
        busy=true;freeze(true);await Promise.all([...pending.values()]);if(!current())return;
        const inputs=withChoices(collect(name=>name==='same_event_confirmed'?field(name).checked:field(name).value),savedInputs,options.sourceChoices);
        setStatus('Saving reviewed inputs and building the event report…');
        const saved=await request(base,json('PUT',{revision,expected_version:version,inputs}));if(!current())return;version=saved.version;savedInputs=saved.inputs||inputs;
        populate(savedInputs);
        const report=await request(base+'/report',json('POST',{revision,inputs:savedInputs}));if(!current())return;
        model=report;applyAutomaticReport(report);render();setStatus('Event report ready. Review its missing values and evidence limits.');
      }catch(error){setStatus(error.message||'The event report could not be built.',true);}finally{busy=false;if(current())freeze(false);}
    },{signal:local});
    output.addEventListener('change',event=>{if(event.target.matches('[data-event-mode]')){mode=event.target.value;render();}},{signal:local});
    output.addEventListener('input',event=>{if(event.target.matches('[data-event-inspector]')){held=true;cursor(Number(event.target.value)/10000);}},{signal:local});
    function fraction(event,svg){const point=svg.createSVGPoint();point.x=event.clientX;point.y=event.clientY;const matrix=svg.getScreenCTM();if(!matrix)return null;return (point.matrixTransform(matrix.inverse()).x-Number(svg.dataset.plotLeft))/Number(svg.dataset.plotWidth);}
    output.addEventListener('pointermove',event=>{const svg=event.target.closest('[data-event-plot]');if(svg&&!held){const f=fraction(event,svg);if(f!==null)cursor(f);}},{signal:local});
    output.addEventListener('click',async event=>{
      const svg=event.target.closest('[data-event-plot]');if(svg){held=!held;const f=fraction(event,svg);if(f!==null)cursor(f);return;}
      const open=event.target.closest('[data-event-open-navigation]');
      if(open&&model){
        const shown=model,sequence=++navigationRequest,target=output.querySelector('[data-event-navigation-host]');open.disabled=true;
        try{
          const data=await request('/api/incidents/'+encodeURIComponent(row.incident_id??row.id)+'/navigator?revision='+encodeURIComponent(revision));
          if(!current()||model!==shown||sequence!==navigationRequest||!target.isConnected)return;
          if(typeof mountNavigation!=='function')throw new Error('The R–X viewer is unavailable. Reload the application.');
          navigationHandle=mountNavigation(target,data,row,{records:arr(shown.navigation?.records),record:shown.ends?.S?.record||shown.ends?.R?.record,signal:local});open.hidden=true;
        }catch(error){if(current()&&model===shown&&sequence===navigationRequest){target.textContent=error.message||'Stored R–X data could not be loaded.';open.disabled=false;}}
        return;
      }
      const button=event.target.closest('[data-event-download]');if(!button||!model)return;
      const html=button.dataset.eventDownload==='html',body=html?'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Event analysis report</title><style>body{font:15px system-ui;max-width:1500px;margin:24px auto;padding:16px;color:#152d43}table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:8px;border-bottom:1px solid #ddd}small{display:block}svg{width:100%}.event-study-quantity-row,.event-study-end-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}.event-study-gridline{stroke:#ddd}.event-study-zero{stroke:#888;stroke-dasharray:4 4}.event-study-cursor,.event-study-actions,.event-study-inspector,.event-study-heading label,.event-study-report button{display:none}.event-study-legend{display:flex;gap:12px}.event-study-legend span{display:flex;gap:6px;align-items:center}.event-study-legend i{display:inline-block;width:14px;height:3px}.event-study-plot{border:1px solid #ddd;border-radius:8px;padding:12px;min-width:0}.event-study-plot>.event-study-help{min-height:2.7em;line-height:1.35;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}@media(max-width:700px){.event-study-quantity-row,.event-study-end-grid{display:block}}</style><body>'+markup(model,mode)+'</body></html>':JSON.stringify(model,null,2);
      const url=URL.createObjectURL(new Blob([body],{type:html?'text/html':'application/json'})),link=document.createElement('a');link.href=url;link.download='event-report-'+String(model.incident_id).replace(/[^a-z0-9_-]/gi,'_')+'.'+(html?'html':'json');link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    },{signal:local});
    request(base+'?revision='+encodeURIComponent(revision)).then(data=>{
      if(!current())return;version=data.version;records=arr(data.records);
      for(const role of ['S','R'])field(role+'.record').innerHTML='<option value="">Choose recording</option>'+records.map(record=>'<option value="'+esc(record.file)+'">'+esc(record.file)+'</option>').join('');
      savedInputs=data.inputs||{};populate(data.inputs);submit.disabled=false;setStatus(data.note||'Choose records and intervals, then build the event report.');
      if(version>0&&data.inputs?.ends?.S?.record){
        busy=true;freeze(true);setStatus('Loading the saved event report…');
        const initial=JSON.parse(JSON.stringify(data.inputs));let migrated=false;
        for(const [role,end] of Object.entries(initial.ends))if(!end.timing_mode&&field(role+'.timing_mode').value==='auto'){end.timing_mode='auto';migrated=true;}
        return request(base+'/report',json('POST',{revision,inputs:initial})).then(report=>{if(current()){model=report;applyAutomaticReport(report);render();setStatus(migrated?'Automatic timings filled previously empty intervals. Build the report to save them.':'Saved event report loaded. Input changes apply when you build it again.');}}).finally(()=>{busy=false;if(current())freeze(false);});
      }
    }).catch(error=>setStatus(error.message||'Recording choices could not be loaded.',true));
    return {destroy(){controller.abort();},applyRegion(record,bounds,kind='fault'){
      if(!current()||busy||!regions.includes(kind)||!Array.isArray(bounds)||bounds.length!==2||!bounds.every(Number.isSafeInteger)||bounds[0]<0||bounds[1]<=bounds[0])return false;
      const role=['S','R'].find(r=>field(r+'.record').value===record);if(!role)return false;
      automatic.get(role)?.abort();field(role+'.timing_mode').value='manual';syncTiming(role);
      form.querySelector('[data-timing-summary="'+role+'"]') .textContent='Manual interval selected from waveform cursors. Build the report to apply it.';
      bounds.forEach((value,i)=>{field(`${role}.${kind}.${i}`).value=value;});stale();setStatus(roles[role]+' '+(regionName(kind).toLowerCase())+' interval selected. Build the report to apply this change.');return true;
    }};
  }
  return {panel,collect,withChoices,timingMarkup,coordinates,tracePaths,plot,explanation,lineView,markup,bind};
})();
function eventStudyPanel(row){return DREventStudy.panel(row);}
function bindEventStudy(row,host,signal,options){return DREventStudy.bind(row,host,signal,options);}
if(typeof module!=='undefined')module.exports=DREventStudy;
