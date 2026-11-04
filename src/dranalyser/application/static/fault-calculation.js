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
  function panel(row,configuration){
    const lines=(configuration?.lines||[]).filter(l=>l.id),local=row.metadata?.incident_line,busy=['queued','running'].includes(row.state);
    if(local?.line_id&&!lines.some(line=>line.id===local.line_id))lines.unshift({id:local.line_id,name:'This incident’s saved line inputs',kv:local.review?.kv??'not supplied',parameter_status:'reviewed incident facts; missing inputs remain gated'});
    const localSelected=Boolean(local?.line_id&&row.metadata?.line_id===local.line_id);
    const accepted=Boolean(row.result&&row.metadata?.line_id&&lines.some(l=>l.id===row.metadata.line_id)&&(selected(row,'S')||selected(row,'R')));
    const options=end=>'<option value="">No record at this end</option>'+records(row).map(f=>`<option value="${esc(f.name)}"${selected(row,end)===f.name?' selected':''}>${esc(recordName(f))} · ${esc(f.name)}${f.blocked?' · review inputs required':''}</option>`).join('');
    const inputs=typeof DRIncidentLineInputs!=='undefined'?DRIncidentLineInputs.markup(row,configuration):'';
    return `<section data-fault-calculation><details${accepted||local?' open':''}><summary>Optional: calculate physical fault location</summary><p class="field-help">Inspect waveforms, compare recordings and build an observation report first. These do not require a line model or physical-end assignment.</p><h3>Calculate fault location</h3><p>Use the existing engineering engine with reviewed physical inputs. One end is enough for eligible single-ended methods; E5 uses compatible opposite ends without GPS.</p><p class="field-help">Fault detection and analysis-window selection are automatic. The engine checks the recorded disturbance for sufficient usable samples; no manual window is required. If support is too short or unsuitable, the result explains why.</p>${inputs}<form data-fault-form><label>Actual line model<select name="line_id"><option value="">Choose a saved incident line or declared line model</option>${lines.map(l=>`<option value="${esc(l.id)}"${row.metadata?.line_id===l.id?' selected':''}>${esc(l.name)} · ${esc(l.kv)} kV · ${esc(l.parameter_status)}</option>`).join('')}</select></label><div class="event-study-end-grid">${['S','R'].map(end=>`<label><span data-fault-end-label="${end}">${esc(endLabel(row,end))}</span><select name="${end}"${localSelected?' disabled':''}>${options(end)}</select></label>`).join('')}</div><p class="field-help" data-fault-local-note${localSelected?'':' hidden'}>These physical ends and their names come from this incident’s saved line facts. Update and save the line inputs above to change them.</p><label class="event-study-confirm"><input type="checkbox" name="confirmed"${accepted?' checked':''}> I confirm the line and physical ends; when both are selected, they record the same event at opposite ends.</label><p class="field-help">Other recordings are excluded from this calculation and remain available for inspection. Same-relay successive captures are not opposite ends. Channel/scaling corrections must be reviewed in Inputs & help; display choices do not authorize physical calculations.</p><button type="submit" class="button primary"${busy?' disabled':''}>Calculate fault location</button><p data-fault-status role="status" aria-live="polite">${busy?'Wait for the current revision to finish.':!lines.length?'Enter and save this incident’s line facts above, then choose that model here.':'Only method-specific missing evidence will prevent an estimate. Protection settings, relay distance and towers are optional for location.'}</p></form></details></section>`;
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
      if(typeof DRInputGuidance!=='undefined'&&DRInputGuidance.assess(file).ratio)throw new Error(name+': actual CT/VT ratings are missing. Save the actual ratings for this recording in Review analysis inputs first.');
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
    if(typeof DRIncidentLineInputs!=='undefined')DRIncidentLineInputs.bind(row,root,signal,{config,onSaved:async result=>{if(root.isConnected&&!signal?.aborted)await onQueued?.(result);}});
    const form=root.querySelector('[data-fault-form]'),status=root.querySelector('[data-fault-status]');
    form.addEventListener('change',event=>{if(['line_id','S','R'].includes(event.target.name)){
      if(event.target.name==='line_id'){
        const local=event.target.value===row.metadata?.incident_line?.line_id;
        for(const end of ['S','R']){const field=form.elements.namedItem(end);field.disabled=local;field.value=selected(row,end,event.target.value);const label=root.querySelector(`[data-fault-end-label="${end}"]`);if(label)label.textContent=endLabel(row,end,field.value);}
        root.querySelector('[data-fault-local-note]').hidden=!local;
      }
      if(['S','R'].includes(event.target.name)){const label=root.querySelector(`[data-fault-end-label="${event.target.name}"]`);if(label)label.textContent=endLabel(row,event.target.name,event.target.value);}
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
