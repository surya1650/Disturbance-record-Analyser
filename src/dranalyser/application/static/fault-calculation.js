'use strict';
// Physical study choices are deliberately separate from report/display choices.
const DRFaultCalculation=(()=>{
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const records=row=>(row.bundle?.files||[]).filter(f=>f.kind==='comtrade'&&!f.duplicate_of);
  const identity=row=>JSON.stringify((row.files||[]).map(f=>[f.name,f.sha256]).sort(([a],[b])=>a.localeCompare(b)));
  function selected(row,end,lineId=row.metadata?.line_id){
    if(lineId&&lineId===row.metadata?.incident_line?.line_id)return row.metadata.incident_line.review?.ends?.[end]?.record||'';
    return Object.entries(row.metadata?.assignments||{}).find(([,v])=>v.end===end&&v.role==='primary')?.[0]||'';
  }
  const recordName=file=>file?.display_name||String(file?.name||'').replace(/\\/g,'/').split('/').pop().replace(/\.[^.]+$/,'').replace(/_/g,' ').trim();
  function endLabel(row,end,name=selected(row,end)){
    const file=records(row).find(f=>f.name===name),title=end==='S'?'Reference end (S)':'Other end (R)';
    const reviewed=row.metadata?.incident_line?.review?.ends?.[end];
    return title+(file?' · '+(reviewed?.record===name&&reviewed.name?reviewed.name:recordName(file)):'');
  }
  function lineSummary(row,localSelected,line){
    const review=localSelected?row.metadata.incident_line.review||{}:{};
    const known=(number,unit)=>typeof number==='number'&&Number.isFinite(number)?esc(number)+' '+unit:'Not supplied';
    const sections=Array.isArray(review.sections)&&review.sections.length;
    const basis=review.basis==='per-km'?'Ω/km':review.basis==='total'?'Ω whole line':'units not confirmed';
    const model=localSelected?'This incident’s saved line details':line?esc(line.name||line.id):'Line details are not set up yet';
    const facts=localSelected?`<p>Full length: <strong>${known(review.length_km,'km')}</strong> · Voltage: <strong>${known(review.kv,'kV')}</strong></p><p>${sections?'Impedance uses the saved section table.':`R1: ${known(review.r1,basis)} · X1: ${known(review.x1,basis)}`}</p>`:line?'<p class="field-help">Using the existing engineering line record. Its selection and physical ends are available below.</p>':'';
    return `<div data-fault-line-summary><h3>${model}</h3>${facts}<p>${['S','R'].map(end=>esc(endLabel(row,end))+(selected(row,end)?'':' · Not assigned')).join('<br>')}</p></div>`;
  }
  function panel(row,configuration){
    const lines=(configuration?.lines||[]).filter(l=>l.id),local=row.metadata?.incident_line,busy=['queued','running'].includes(row.state);
    if(local?.line_id&&!lines.some(line=>line.id===local.line_id))lines.unshift({id:local.line_id,name:'This incident’s saved line details',kv:local.review?.kv??'not supplied',parameter_status:'supplied facts; incomplete inputs remain gated'});
    const localSelected=Boolean(local?.line_id&&row.metadata?.line_id===local.line_id);
    const chosen=lines.find(line=>line.id===row.metadata?.line_id);
    const accepted=Boolean(row.result&&chosen&&(selected(row,'S')||selected(row,'R')));
    const setup='#setup/'+encodeURIComponent(row.incident_id||row.id||'');
    const options=end=>'<option value="">No record at this end</option>'+records(row).map(f=>`<option value="${esc(f.name)}"${selected(row,end)===f.name?' selected':''}>${esc(recordName(f))} · ${esc(f.name)}${f.blocked?' · review inputs required':''}</option>`).join('');
    const engineering=lines.length?`<form data-fault-form><details data-engineering-model-selection><summary>Engineering model selection</summary><p class="field-help">Use this only to select an existing engineering line record. For this incident’s length, impedance, ratios and end names, use Setup.</p><label>Saved line record<select name="line_id"><option value="">Choose an existing line record</option>${lines.map(l=>`<option value="${esc(l.id)}"${row.metadata?.line_id===l.id?' selected':''}>${esc(l.name||l.id)} · ${esc(l.kv??'not supplied')} kV</option>`).join('')}</select></label><div class="event-study-end-grid">${['S','R'].map(end=>`<label><span data-fault-end-label="${end}">${esc(endLabel(row,end))}</span><select name="${end}"${localSelected?' disabled':''}>${options(end)}</select></label>`).join('')}</div></details><p class="field-help" data-fault-local-note${localSelected?'':' hidden'}>The calculation uses this incident’s saved line and physical ends. Change them in Setup.</p><label class="event-study-confirm"><input type="checkbox" name="confirmed"${accepted?' checked':''}> I confirm the selected line and physical ends; two recordings, when selected, are the same event at opposite ends.</label><button type="submit" class="button primary"${busy?' disabled':''}>Calculate fault location</button><p data-fault-status role="status" aria-live="polite">${busy?'Wait for the current revision to finish.':chosen?'Fault type and the usable analysis window are detected automatically. Missing or unsuitable evidence keeps a named reason.':'Save the line details in Setup, or choose an existing engineering line record.'}</p></form>`:'<p data-fault-status role="status">Enter line length, impedance and physical ends in Setup before requesting a distance. Waveforms and the incident report are available now.</p>';
    return `<section data-fault-calculation><h3>Fault analysis and location</h3><p>The analyser detects the fault type and analysis window from usable recordings. You do not need to choose an assumed fault loop.</p><p class="field-help">Distance also needs the actual line length and impedance. These usually come from the line schedule, not the DR. A separate line-model file is not required. Single-ended methods use one eligible end; E5 uses compatible opposite ends without GPS.</p><p><a class="button" data-fault-setup href="${esc(setup)}">${local?'Edit':'Set up'} ratios and line details →</a></p>${lineSummary(row,localSelected,chosen)}${engineering}</section>`;
  }
  function payload(row,choices){
    if(!choices.line_id)throw new Error('Choose the actual declared line model.');
    if(!choices.S&&!choices.R)throw new Error('Choose at least one physical end.');
    if(choices.S&&choices.S===choices.R)throw new Error('One recording cannot represent both physical ends.');
    if(choices.line_id===row.metadata?.incident_line?.line_id&&['S','R'].some(end=>(choices[end]||'')!==selected(row,end,choices.line_id)))throw new Error('The physical ends differ from this incident’s saved line facts. Update and save the line inputs before calculating.');
    if(!choices.confirmed)throw new Error('Confirm the physical line and end identities for this calculation.');
    const inventory=records(row),assignments={};
    for(const [end,name] of [['S',choices.S],['R',choices.R]]){
      if(!name)continue;
      const file=inventory.find(f=>f.name===name);
      if(!file||!file.ok)throw new Error('The selected source is not a recoverable operational recording: '+name);
      if(typeof DRInputGuidance!=='undefined'&&DRInputGuidance.assess(file).ratio)throw new Error(name+': actual CT/VT ratings are missing. Save the actual ratings for this recording in Setup first.');
      const prior=row.metadata?.assignments?.[name]||{};
      // An end/line change invalidates end-specific window/settings reviews.
      const retained=prior.end===end&&row.metadata?.line_id===choices.line_id?prior:{};
      assignments[name]={...retained,end,role:'primary'};
      if(prior.channel_mapping)assignments[name].channel_mapping=prior.channel_mapping;
      if(prior.instrument_review)assignments[name].instrument_review=prior.instrument_review;
    }
    for(const file of inventory)if(!assignments[file.name]){
      assignments[file.name]={end:'',role:'excluded'};
      const review=row.metadata?.assignments?.[file.name]?.instrument_review;
      if(review)assignments[file.name].instrument_review=review;
    }
    return {revision:row.number,line_id:choices.line_id,assignments};
  }
  async function queue(row,choices,request,{signal,onProgress=()=>{},wait=ms=>new Promise(resolve=>setTimeout(resolve,ms))}={}){
    const body=payload(row,choices),base='/api/incidents/'+encodeURIComponent(row.incident_id||row.id);
    const active=()=>{if(signal?.aborted)throw new Error('Calculation cancelled because the recording or revision changed.');};
    const post=value=>({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(value),signal});
    active();
    if(['completed','attention','failed'].includes(row.state)){
      onProgress('Creating a new review revision; previous reports remain unchanged…');
      const revision=await request(base+'/reanalyse?revision='+row.number,{method:'POST',signal});
      active();let ready;
      for(let attempt=0;attempt<120;attempt++){
        ready=await request(base+'?revision='+revision.revision,{signal});active();
        if(ready.state==='needs_review')break;
        if(!['queued','running'].includes(ready.state))throw new Error('New review could not be prepared: '+(ready.error||ready.state));
        await wait(250);active();
      }
      if(ready?.state!=='needs_review')throw new Error('Review preparation is still running. Reopen this incident when it finishes.');
      if(identity(ready)!==identity(row))throw new Error('Source files changed. Review the current revision before calculating.');
      body.revision=ready.number;
    }else if(row.state!=='needs_review')throw new Error('Wait for the current revision to finish before calculating.');
    active();onProgress('Checking assignments and queuing the engineering calculation…');
    await request(base+'/review',post(body));active();
    return body.revision;
  }
  function bind(row,host,signal,{onQueued,config}={}){
    const root=host.querySelector('[data-fault-calculation]');if(!root)return;
    const form=root.querySelector('[data-fault-form]'),status=root.querySelector('[data-fault-status]');if(!form)return;
    form.addEventListener('change',event=>{if(['line_id','S','R'].includes(event.target.name)){
      if(event.target.name==='line_id'){
        const local=event.target.value===row.metadata?.incident_line?.line_id;
        for(const end of ['S','R']){const field=form.elements.namedItem(end);field.disabled=local;field.value=selected(row,end,event.target.value);const label=root.querySelector(`[data-fault-end-label="${end}"]`);if(label)label.textContent=endLabel(row,end,field.value);}
        root.querySelector('[data-fault-local-note]').hidden=!local;
      }
      if(['S','R'].includes(event.target.name)){const label=root.querySelector(`[data-fault-end-label="${event.target.name}"]`);if(label)label.textContent=endLabel(row,event.target.name,event.target.value);}
      const summary=root.querySelector('[data-fault-line-summary]');if(summary)summary.hidden=true;
      form.elements.namedItem('confirmed').checked=false;status.textContent='Physical inputs changed. Confirm the current line and end identities before calculating.';
    }},{signal});
    form.addEventListener('submit',async event=>{
      event.preventDefault();if(form.dataset.busy)return;
      const field=name=>form.elements.namedItem(name),choices={line_id:field('line_id').value,S:field('S').value,R:field('R').value,confirmed:field('confirmed').checked};
      const controls=[...form.querySelectorAll('input,select,button')],disabledBefore=controls.map(el=>el.disabled);
      try{
        payload(row,choices);form.dataset.busy='true';controls.forEach(el=>{el.disabled=true;});
        await queue(row,choices,api,{signal,onProgress:message=>{if(root.isConnected&&!signal?.aborted)status.textContent=message;}});
        if(root.isConnected&&!signal?.aborted){status.textContent='Calculation queued. The result will retain its method, input evidence and refusal reasons.';await onQueued?.();}
      }catch(error){if(root.isConnected&&!signal?.aborted)status.textContent=error.message;}
      finally{delete form.dataset.busy;if(root.isConnected&&!signal?.aborted)controls.forEach((el,index)=>{el.disabled=disabledBefore[index];});}
    },{signal});
  }
  return {panel,payload,queue,bind};
})();
