'use strict';
// Parsing reveals source facts first; edits use the existing immutable input-review APIs.
const DRRecordingSetup=(()=>{
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const records=row=>(row.bundle?.files||[]).filter(file=>file.kind==='comtrade'&&!file.duplicate_of);
  const positive=value=>typeof value==='number'&&Number.isFinite(value)&&value>0;
  const displayName=file=>file.display_name||String(file.name||'').replace(/\\/g,'/').split('/').pop().replace(/\.[^.]+$/,'').replace(/_/g,' ');
  function declaredRatios(file){
    const inventory=(file.channel_inventory||[]).filter(channel=>channel.kind==='analog');
    const groups=[['CT','A'],['VT / PT','V']].map(([label,kind])=>{
      const channels=inventory.filter(channel=>String(channel.unit??channel.declared_units??'').trim().toUpperCase().endsWith(kind));
      const declared=[...new Set(channels.filter(channel=>positive(channel.primary)&&positive(channel.secondary)&&channel.primary!==channel.secondary).map(channel=>`${channel.primary} / ${channel.secondary}`))];
      const sides=[...new Set(channels.map(channel=>String(channel.ps??channel.primary_secondary??'').trim().toUpperCase()).filter(Boolean))];
      return {label,kind,ratios:declared,primarySamples:channels.length>0&&sides.length===1&&sides[0]==='P',hasChannels:channels.length>0};
    });
    return groups;
  }
  function recordSummary(file){
    const rows=declaredRatios(file).filter(group=>group.hasChannels).map(group=>`<li><strong>${esc(group.label)}:</strong> ${group.ratios.length?esc(group.ratios.join(' · '))+' '+esc(group.kind)+' (CFG declarations)':'Actual transformer ratings are not declared.'}${group.primarySamples?' <span>Samples are already in primary units; no ratio is applied again.</span>':''}</li>`).join('');
    return `<div class="recording-setup-source"><h3>${esc(displayName(file))}</h3><p class="field-help">${esc(file.name)}</p>${rows?'<ul class="recording-setup-facts">'+rows+'</ul>':'<p>Instrument declarations are unavailable. Recoverable observations remain available in their recorded units.</p>'}</div>`;
  }
  const fieldKey=input=>[input.dataset.common||'',input.closest?.('[data-rating]')?.dataset.rating||'',input.dataset.ratingValue||'',input.hasAttribute?.('data-rating-override')?'override':'',input.hasAttribute?.('data-rating-reviewer')?'reviewer':'',input.hasAttribute?.('data-rating-evidence')?'evidence':'',input.hasAttribute?.('data-rating-confirm')?'confirmed':'',input.type||input.tagName].join('|');
  function capture(host,row,state,excludedRecord){
    state.drafts||={};
    for(const section of host.querySelectorAll('[data-instrument-file]')){
      const file=records(row).find(file=>file.name===section.dataset.instrumentFile);
      if(!file||file.name===excludedRecord)continue;
      state.drafts[file.name]={hash:file.content_hash,fields:[...section.querySelectorAll('input,textarea')].map(input=>({key:fieldKey(input),value:input.value,checked:input.checked}))};
    }
    if(excludedRecord)delete state.drafts[excludedRecord];
    const form=host.querySelector('[data-line-input-form]');
    if(form){
      const field=name=>form.elements.namedItem(name),review={ends:{}};
      for(const key of ['length_km','kv','r1','x1','r0','x0','basis','reviewer','evidence'])review[key]=field(key)?.value??'';
      for(const key of ['confirmed_line','uniform_line','confirmed_same_event','reference_reviewed'])review[key]=field(key)?.checked===true;
      review.reference_id=field('reference_id')?.value||'';
      for(const end of ['S','R']){
        const selected=field(end+'.record')?.value;
        if(selected)review.ends[end]=Object.fromEntries(['record','name','current_direction','vt_type','vt_location'].map(key=>[key,field(end+'.'+key)?.value||'']));
      }
      review.sections=JSON.parse(JSON.stringify(row.metadata?.incident_line?.review?.sections||[]));
      state.lineReview=review;
    }
  }
  function restore(host,row,state){
    for(const section of host.querySelectorAll('[data-instrument-file]')){
      const file=records(row).find(file=>file.name===section.dataset.instrumentFile),draft=state.drafts?.[file?.name];
      const inputs=[...section.querySelectorAll('input,textarea')];
      if(!draft||draft.hash!==file.content_hash||JSON.stringify(inputs.map(fieldKey))!==JSON.stringify(draft.fields.map(field=>field.key)))continue;
      inputs.forEach((input,index)=>{input.value=draft.fields[index].value;if(input.type==='checkbox')input.checked=draft.fields[index].checked;});
      for(const channel of section.querySelectorAll('[data-rating]')){
        const override=channel.querySelector('[data-rating-override]')?.checked;
        for(const input of channel.querySelectorAll('[data-rating-value]'))input.disabled=!override;
      }
    }
  }
  async function ready(request,id,{signal,wait=ms=>new Promise(resolve=>setTimeout(resolve,ms)),onPending=()=>{},attempts=120}={}){
    for(let attempt=0;attempt<attempts;attempt++){
      if(signal?.aborted)return null;
      const row=await request('/api/incidents/'+encodeURIComponent(id),{signal});
      if(signal?.aborted)return null;
      if(row.incident_id!==id)throw new Error('The parsed response belongs to another incident. Reopen setup.');
      if(!['queued','running'].includes(row.state))return row;
      onPending(row);await wait(500);
    }
    throw new Error('Parsing is still running. Reopen recording setup when it finishes; your upload is retained.');
  }
  async function mount(host,row,{config={},signal,request=(path,options)=>api(path,options),state={},isCurrent=()=>true,onRevision=()=>{},onRefresh=()=>{}}={}){
    const active=()=>host.isConnected&&!signal?.aborted&&isCurrent();
    const inventory=records(row),requirements={},errors={};
    host.innerHTML='<div class="panel recording-setup-loading" role="status">Reading instrument declarations from the parsed recordings…</div>';
    await Promise.all(inventory.map(async file=>{
      if(!/^[0-9a-f]{64}$/.test(file.content_hash||''))return;
      try{
        const result=await request(`/api/incidents/${encodeURIComponent(row.incident_id)}/instrument-review?record=${encodeURIComponent(file.name)}&revision=${row.number}`,{signal});
        if(result.record!==file.name||result.revision!==row.number||result.record_hash!==file.content_hash)throw new Error('Recording or revision changed. Reopen setup before saving instrument inputs.');
        requirements[file.name]=result;
      }catch(error){if(error.name==='AbortError')throw error;errors[file.name]=error.message;}
    }));
    if(!active())return null;
    const virtualRow=state.lineReview?{...row,metadata:{...row.metadata,incident_line:{...(row.metadata?.incident_line||{}),review:state.lineReview}}}:row;
    host.innerHTML=`<div class="recording-setup-heading"><div class="eyebrow">STEP 1 · PARSE & SETUP</div><h1>Check the recordings once</h1><p>Names and available instrument ratings come from the recordings. Enter a shared CT rating and a shared VT / PT rating for each recording only where values are missing. Other ends and auxiliary channels may differ.</p><p class="field-help">Original files and previous reports are retained. You can continue with unknown values to inspect raw observations; physical calculations keep their input checks.</p></div><section class="panel recording-setup-section"><h2>1. Recording names and instrument ratios</h2>${inventory.length?inventory.map(file=>`<article class="recording-setup-record" data-setup-record="${esc(file.name)}">${recordSummary(file)}${errors[file.name]?'<p class="hint">'+esc(errors[file.name])+'</p>':requirements[file.name]?instrumentReviewEditor(row,file.name,{[file.name]:requirements[file.name]}):'<p class="field-help">A matching parsed source identity is unavailable; inspect the source error before entering ratings.</p>'}${requirements[file.name]&&!reviewableInstrumentRatings(row,file,requirements[file.name]).length?'<p class="recording-setup-ready">No missing phase instrument ratings require entry for this recording.</p>':''}</article>`).join(''):'<p>No parsed COMTRADE recording is available. Open the source errors in Analyse.</p>'}</section><section class="panel recording-setup-section"><h2>2. Line details · for fault distance</h2><p>Enter the actual line length and approved impedance values here, or use an applicable saved line/reference. These are usually absent from a disturbance recording. A line-model file is not required.</p><div data-setup-line>${typeof DRIncidentLineInputs!=='undefined'?DRIncidentLineInputs.markup(virtualRow,config):'<p>Line input controls are unavailable. Reload the application.</p>'}</div></section><div class="recording-setup-actions"><button type="button" class="button" data-setup-refresh>Refresh parsed facts</button><a class="button primary" href="#incident/${encodeURIComponent(row.incident_id)}/${row.number}/waveforms">Continue to Analyse →</a></div>`;
    restore(host,row,state);
    bindInstrumentReview(row,host,{signal,isCurrent:active,onSuccess:async(updated,result)=>{
      if(!active())return;capture(host,row,state,result.record||result.reviewed_record);await onRevision(updated,result);
    }});
    const line=host.querySelector('[data-setup-line]');
    if(typeof DRIncidentLineInputs!=='undefined'){
      const details=line?.querySelector('[data-incident-line-inputs]>details');if(details)details.open=true;
      DRIncidentLineInputs.bind(virtualRow,line,signal,{config,request,onSaved:async result=>{
        if(!active())return;capture(host,row,state);delete state.lineReview;await onRevision(null,result);
      }});
    }
    host.querySelector('[data-setup-refresh]')?.addEventListener('click',()=>{if(active()){capture(host,row,state);onRefresh();}},{signal});
    return {capture:()=>capture(host,row,state),row};
  }
  return {declaredRatios,recordSummary,ready,mount};
})();
if(typeof module!=='undefined')module.exports=DRRecordingSetup;
