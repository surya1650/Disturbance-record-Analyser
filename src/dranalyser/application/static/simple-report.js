'use strict';
// Presentation of supplied evidence only; no new fault or distance calculation.
const DRSimpleReport=(()=>{
  const text=v=>typeof v==='string'?v:'';
  const array=v=>Array.isArray(v)?v:[];
  const finite=v=>typeof v==='number'&&Number.isFinite(v)?v:null;
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=v=>finite(v)===null?'Not available':v===0?'0':v.toPrecision(5);
  const names=['Pre-fault','Fault','Post-fault'];
  function conditions(result){
    const report=result.operator_conditions||{},s=report.selection;
    const valid=s&&Number.isInteger(s.start)&&Number.isInteger(s.end)&&s.start>=0&&s.end>s.start&&
      (finite(result.sample_count)===null||s.end<=result.sample_count);
    const selection=valid?{start:s.start,end:s.end,start_s:finite(s.start_s),end_s:finite(s.end_s),source:text(s.source)||'Operator selection',basis:text(s.basis)}:null;
    if(selection&&!(selection.start_s!==null&&selection.end_s!==null&&selection.end_s>selection.start_s))selection.start_s=selection.end_s=null;
    const channels=new Map();
    for(const c of [...array(result.channels),...array(report.overview)])if(c&&typeof c.id==='string')channels.set(c.id,{...(channels.get(c.id)||{}),...c});
    const rows=[...channels.values()].map(c=>{
      const cells=names.map(name=>{
        const region=array(report.regions).find(r=>r?.name===name),channel=array(region?.channels).find(ch=>ch?.id===c.id);
        let reason=selection?'No complete supported model window is available in this region.':'Select and apply the fault interval before comparing regions.';
        if(!selection)return {value:null,windows:0,reason};
        if(channel&&channel.units!==c.units)return {value:null,windows:0,reason:'Channel units do not match the selected region evidence.'};
        const value=finite(channel?.rms),count=channel?.windows;
        if(value!==null&&value>=0&&Number.isInteger(count)&&count>0)return {value,windows:count,reason:''};
        reason=text(channel?.reason)||reason;return {value:null,windows:0,reason};
      });
      return {id:c.id,label:text(c.label)||c.id,meaning:text(c.meaning),units:text(c.units)||'Units unavailable',pre:cells[0],fault:cells[1],post:cells[2]};
    });
    return {selection,rows,note:'Values are median fundamental fitted RMS from complete supported windows inside each operator-selected region. Empty cells do not mean zero.'};
  }
  function distances(result,operational){
    const line=result.snapshot?.line||{},p=result.snapshot?.selected_projection||result.selected_projection||{};
    const method=text(p.method),validProjection=['Conditional model projection','Outside supplied line'].includes(p.status),km=method&&validProjection?finite(p.distance_km):null;
    const projection={kind:'projection',status:text(p.status)||'Not available',distance_km:km,length_km:finite(line.length_km),
      reference:'S · '+(text(line.terminals?.S)||'reference terminal not named'),method:method||'Not supplied',
      reason:finite(p.distance_km)!==null&&!method?'Calculation method was not supplied; no distance is presented.':finite(p.distance_km)!==null&&!validProjection?'Calculation status does not support a projection; no distance is presented.':text(p.reason)||text(p.basis)||text(result.methods?.location?.reason)||'Supply line facts, a phase loop and a supported source window.',
      assumptions:array(p.assumptions).filter(v=>typeof v==='string'),authorizes_location:false,window_index:Number.isInteger(p.window_index)?p.window_index:null};
    const stored=text(operational?.location_text),match=stored.match(/^(-?\d+(?:\.\d+)?) km from (.+) by (.+) \(([^)]+)\)$/);
    const storedKm=match?finite(Number(match[1])):null;
    const used=Object.entries(operational?.used||{}).filter(([,file])=>typeof file==='string').map(([end,file])=>({end,file}));
    const incident=operational?{kind:'incident',status:storedKm===null?'Not available':'Stored incident calculation',distance_km:storedKm,
      length_km:null,reference:match?match[2]:'Not supplied',method:match?match[3]:'Not supplied',text:stored||'No incident distance calculation supplied.',
      reason:storedKm===null?(stored||'No eligible incident calculation is available.'):'Conditional on the incident inputs and data-quality findings; see the incident report.',
      source_records:used,selected_source_used:used.some(r=>r.file===result.file),authorizes_location:false}:null;
    return {primary:incident?.distance_km!==null&&incident?incident:projection,incident,projection};
  }
  function digital(result){
    const evidence=array(result.digital_evidence).filter(c=>c&&typeof c==='object');
    const relevant=evidence.filter(c=>finite(c.active_samples)>0||c.first_active_index!==null&&Number.isInteger(c.first_active_index)||c.interpretation_available===false||finite(c.unknown_samples)>0);
    const rows=relevant.slice(0,12).map(c=>{
      const meanings=array(c.meanings).filter(m=>typeof m==='string'),interpretable=c.interpretation_available===true&&meanings.length>0&&(c.asserted_state===0||c.asserted_state===1);
      return {id:text(c.id),label:text(c.label),meanings,interpretable,active_samples:finite(c.active_samples),unknown_samples:finite(c.unknown_samples),
        asserted_state:c.asserted_state===0||c.asserted_state===1?c.asserted_state:null,assertion_source:text(c.assertion_source)||'Polarity source not supplied',
        first_active_index:Number.isInteger(c.first_active_index)&&c.first_active_index>=0?c.first_active_index:null,
        first_active_source_s:Number.isInteger(c.first_active_index)&&c.first_active_index>=0?finite(c.first_active_source_s):null,
        interpretation:!meanings.length?'Meaning not assigned; raw states are observations only.':!interpretable?'Review asserted-state polarity before interpreting this indication.':'Recorded '+meanings.join(', ')+' indication under the stated polarity; physical operation is not verified.'};
    });
    return {rows,shown:rows.length,total:evidence.length,relevant:relevant.length,omitted:Math.max(0,relevant.length-rows.length),
      unresolved:evidence.filter(c=>c.interpretation_available!==true||!array(c.meanings).length||![0,1].includes(c.asserted_state)).length,
      trip:text(result.trip?.text)||'No trip interpretation is available. Review trip channel meaning, polarity and capture coverage.',
      ar:text(result.ar?.text)||'No autoreclose interpretation is available. Review AR indications and scheme settings.',
      note:'Indications are recorded relay signals. A trip signal does not prove breaker opening; opening time needs suitable pole/contact evidence and a valid timing reference. Local source times are not relay operating times.'};
  }
  function build(result={},operationalResult=null){
    result=result&&typeof result==='object'?result:{};
    const c=conditions(result),d=distances(result,operationalResult),signals=digital(result),next=[];
    if(!c.selection)next.push('In Waveforms, place A at fault start and B at post-fault start, then apply Compare A–B conditions.');
    if(c.selection&&c.rows.some(r=>[r.pre,r.fault,r.post].some(cell=>cell.value===null)))next.push('Review unavailable region values. A short or transient interval may not contain a complete supported four-cycle fit; do not assume a missing value is zero.');
    if(d.primary.distance_km===null)next.push('For a distance calculation, supply the actual line model, channel meanings/scaling, a supported loop/window and the method-specific inputs.');
    if(signals.unresolved)next.push('Review digital channel meanings and asserted-state polarity before drawing operation conclusions.');
    return {title:'Simple analysis report',source:{file:text(result.file)||'Recording not supplied',incident_id:text(result.incident_id),revision:Number.isInteger(result.revision)?result.revision:null},
      conditions:c,distance:d.primary,incident_distance:d.incident,projection:d.projection,
      analog:{interpretations:c.selection?array(result.operator_conditions?.interpretations).filter(v=>typeof v==='string'):[],
        note:'Changes describe the selected regions and stated source units. They do not by themselves verify the fault type, CT/VT ratios or wiring.'},
      digital:signals,next_steps:next,assumptions:array(result.assumptions).map(a=>({channel_id:text(a?.channel_id),ratio_text:text(a?.ratio_text),source:text(a?.source),basis:text(a?.basis)})),
      scaling_notes:array(result.scaling_notes).filter(v=>typeof v==='string')};
  }
  const list=items=>'<ul>'+items.map(v=>'<li>'+esc(v)+'</li>').join('')+'</ul>';
  function distanceMarkup(distance){
    const isIncident=distance.kind==='incident',value=distance.distance_km;
    return `<section class="simple-distance"><h3>${isIncident?'Incident distance calculation':'Approximate line-model projection'}</h3><p><strong>${value===null?'Not available':num(value)+' km from '+esc(distance.reference)}</strong> · ${esc(distance.status)}</p><p>Method: ${esc(distance.method)}${distance.length_km!==null?' · Full supplied line length: '+num(distance.length_km)+' km':''}${Number.isInteger(distance.window_index)?' · Source window '+distance.window_index:''}</p>${distance.text?'<p>'+esc(distance.text)+'</p>':''}<p>${esc(distance.reason)}</p>${isIncident?'<p>Selected incident records: '+(distance.source_records.length?distance.source_records.map(r=>esc(r.end+' · '+r.file)).join('; '):'Not supplied')+'. '+(distance.selected_source_used?'This recording is listed in that calculation.':'This recording is not listed as driving that incident calculation.')+'</p>':'<p>This projection depends on the supplied line and selected source support; it is not a verified physical fault location.</p>'}${distance.assumptions?.length?'<details><summary>Projection assumptions</summary>'+list(distance.assumptions)+'</details>':''}</section>`;
  }
  function markup(model){
    const c=model.conditions,s=c.selection;
    const selection=s?`Applied fault interval: source indices [${s.start}, ${s.end})${s.start_s!==null?' · '+num(s.start_s)+'–'+num(s.end_s)+' local s':''}. A starts fault; B starts post-fault. ${esc(s.source)}.`:'Fault interval not selected. Select A and B in Waveforms, then apply Compare A–B conditions. Values appear only where complete supported windows exist.';
    const cell=entry=>`<td>${num(entry.value)}${entry.value===null?'<details class="simple-unavailable"><summary>Why unavailable?</summary><small>'+esc(entry.reason)+'</small></details>':'<small>'+entry.windows+' supported window'+(entry.windows===1?'':'s')+'</small>'}</td>`;
    const table=c.rows.length?`<div class="table-wrap" role="region" tabindex="0" aria-label="Report table; scroll horizontally to see all columns"><table><thead><tr><th>Analog channel / units</th><th>Pre-fault RMS</th><th>Fault RMS</th><th>Post-fault RMS</th></tr></thead><tbody>${c.rows.map(r=>`<tr><th>${esc(r.id+' · '+r.label)}<small>${esc(r.meaning||'Meaning not assigned')} · ${esc(r.units)}</small></th>${cell(r.pre)}${cell(r.fault)}${cell(r.post)}</tr>`).join('')}</tbody></table></div>`:'<p>No recoverable analog channel evidence is available.</p>';
    const signals=model.digital;
    return `<article class="simple-report"><header><h2>${esc(model.title)}</h2><p>Selected recording: ${esc(model.source.file)}${model.source.revision!==null?' · Revision '+model.source.revision:''}. This source summary belongs to the incident; it does not establish common events or clocks.</p></header><section><h3>Pre-fault, fault and post-fault conditions</h3><p>${selection}</p>${table}<p class="field-help">${esc(c.note)}</p></section>${distanceMarkup(model.distance)}${model.incident_distance&&model.distance.kind==='incident'&&model.projection.distance_km!==null?distanceMarkup(model.projection):''}<section><h3>What the analog channels show</h3>${model.analog.interpretations.length?list(model.analog.interpretations):'<p>No supported pre-fault/fault comparison is available yet. Review the interval, channel meanings and individual unavailable-value reasons.</p>'}<p class="field-help">${esc(model.analog.note)}</p></section><section><h3>What the digital channels show</h3><p>${esc(signals.trip)}</p><p>${esc(signals.ar)}</p>${signals.rows.length?'<div class="table-wrap" role="region" tabindex="0" aria-label="Report table; scroll horizontally to see all columns"><table><thead><tr><th>Indication / meaning</th><th>Recorded evidence</th><th>Simple interpretation</th></tr></thead><tbody>'+signals.rows.map(r=>`<tr><th>${esc(r.id+' · '+r.label)}<small>${esc(r.meanings.join(', ')||'Meaning unassigned')}</small></th><td>${num(r.active_samples)} samples at state ${r.asserted_state??'unknown'}; ${num(r.unknown_samples)} unknown.<small>${esc(r.assertion_source)}</small><small>First observed active: ${r.first_active_index===null?'Not available':'sample '+r.first_active_index}${r.first_active_source_s===null?' · time unavailable':' · '+num(r.first_active_source_s)+' local s'}</small></td><td>${esc(r.interpretation)}</td></tr>`).join('')+'</tbody></table></div>':'<p>No active or unresolved digital indication is listed. This does not prove that no trip or reclose occurred.</p>'}<p>Showing ${signals.shown} of ${signals.relevant} active or unresolved channels (${signals.total} digital channels in this source).${signals.omitted?' Additional indications remain in technical evidence.':''}</p><p class="field-help">${esc(signals.note)}</p></section>${model.next_steps.length?'<section><h3>What to do next</h3>'+list(model.next_steps)+'</section>':''}${model.assumptions.length||model.scaling_notes.length?'<details><summary>Measurement assumptions and scaling</summary>'+list([...model.assumptions.map(a=>[a.channel_id,a.ratio_text,a.source,a.basis].filter(Boolean).join(' · ')),...model.scaling_notes])+'</details>':''}</article>`;
  }
  return {build,markup};
})();
if(typeof module!=='undefined')module.exports=DRSimpleReport;
