'use strict';
const DROperatorWorkspace=(()=>{
  const preferences=new Map();
  const tabs=[['waveforms','Analyse','Inspect the waveforms, move cursors for exact values, and review RMS values and vectors.'],['compare','Compare','Choose another recording to compare the recorded quantities side by side. This step is optional.'],['report','Report','Generate a short incident report with the findings, supporting observations and any missing information.']];
  function mount(section,{traces,row,data,signal,workbench}){
    const root=document.createElement('div');root.className='operator-workspace';
    const key=row.incident_id+'/'+row.number,prefix='operator-'+String(row.incident_id).replace(/[^a-zA-Z0-9]/g,'')+'-'+row.number;
    root.innerHTML=DRInputGuidance.workflowMarkup(row,data)+`<div class="operator-tabs" role="tablist" aria-label="Incident tasks">${tabs.map(([id,title])=>`<button type="button" role="tab" id="${prefix}-${id}-tab" aria-controls="${prefix}-${id}" data-workspace-tab="${id}">${title}</button>`).join('')}</div>`+tabs.map(([id,title,help])=>`<section role="tabpanel" tabindex="0" id="${prefix}-${id}" aria-labelledby="${prefix}-${id}-tab" data-workspace-pane="${id}" hidden><div class="operator-task-heading"><h2>${title}</h2><p>${help}</p></div><div data-workspace-content="${id}"></div></section>`).join('');
    section.append(root);
    const content=id=>root.querySelector(`[data-workspace-content="${id}"]`);
    const record=(row.bundle?.files||[]).find(f=>f.name===data.file)||{};
    const noticePanel=document.createElement('div');noticePanel.innerHTML=DRInputGuidance.markup(record);content('waveforms').append(noticePanel);
    if(traces)content('waveforms').append(traces);
    const inputs=document.createElement('details');inputs.className='operator-inputs';inputs.innerHTML='<summary>Review analysis inputs if needed</summary><p class="field-help">Waveforms and an observation report do not need a line model. Change a meaning or supply an actual instrument rating only when the affected finding needs it.</p>';
    const reviewInputs=document.createElement('div');reviewInputs.innerHTML=instrumentReviewEditor(row,data.file);inputs.append(reviewInputs);
    bindInstrumentReview(row,reviewInputs,{signal,onSuccess:async(updated,result)=>{
      history.replaceState(null,'','#incident/'+row.incident_id);await detail(row.incident_id);
      const select=document.getElementById('inspection-record');if(select&&[...select.options].some(o=>o.value===result.reviewed_record)){select.value=result.reviewed_record;select.dispatchEvent(new Event('change'));}
      notice('Instrument ratings saved for this recording in input revision '+updated.number+'. Original files are preserved.');
    }});
    const technical=document.createElement('details');technical.className='operator-source-details';technical.innerHTML='<summary>Supporting measurements and technical exports</summary><p class="field-help">Detailed source fits and method evidence are available here when a finding needs closer review.</p>';
    const original=[...section.children].filter(el=>el!==root);
    for(const el of original){
      if(el.matches('.source-job-status')){root.insertBefore(el,root.querySelector('[role=tabpanel]'));continue;}
      if(el.matches('.source-compare')){content('compare').append(el);continue;}
      if(el.matches('.source-line-summary,.source-technical,.source-evidence,.source-report-tools,.source-condition-tools,.source-condition-summary')){technical.append(el);continue;}
      if(el.matches('h2,p')){el.remove();continue;}
      inputs.append(el);
    }
    const run=inputs.querySelector('.source-run');
    if(run){run.classList.add('operator-primary-action');run.textContent='Update analysis';run.setAttribute('type','button');content('waveforms').append(run);}
    content('waveforms').append(inputs,technical);
    const guide=document.createElement('section');guide.className='operator-feature-guide';
    const help=document.createElement('details');help.innerHTML='<summary>Help for the current analysis</summary>';help.append(guide);inputs.append(help);
    if(typeof DRFaultCalculation!=='undefined'){
      const calculation=document.createElement('section');calculation.innerHTML=DRFaultCalculation.panel(row,config);inputs.append(calculation);
      DRFaultCalculation.bind(row,calculation,signal,{onQueued:async()=>detail(row.incident_id)});
    }
    if(typeof DREventStudy!=='undefined'){
      const refinement=document.createElement('details');refinement.className='operator-region-help';refinement.innerHTML='<summary>Advanced: source timings and opposite-end study</summary><p>Saved, source-matched time ranges are reused by Generate report. This optional engineering study has its own opposite-end and same-event checks. Use the Report tab for the four-page summary.</p>';
      const eventHost=document.createElement('div');eventHost.innerHTML=DREventStudy.panel(row);refinement.append(eventHost);inputs.append(refinement);
      const eventStudy=DREventStudy.bind(row,eventHost,signal,{sourceChoices(file){
        const chosen=sourceAnalysisPreferences.get(row.incident_id+'/'+row.number+'/'+file);
        return chosen&&(Object.keys(chosen.mappings||{}).length||Object.keys(chosen.asserted_states||{}).length)?{mappings:chosen.mappings||{},asserted_states:chosen.asserted_states||{}}:undefined;
      }});
      eventHost.addEventListener('event-study-request-region',event=>{
        const {record:file,kind}=event.detail||{},pins=workbench?.getPins();
        if(file!==data.file||!pins){notice('Select '+String(file||'the requested recording')+' in Analyse, place cursors A and B, then apply the interval.');return;}
        const lo=Math.min(pins.A,pins.B),hi=Math.max(pins.A,pins.B)+1;
        if(eventStudy.applyRegion(file,[lo,hi],kind))notice('Applied samples '+lo+'–'+(hi-1)+' inclusive. Generate the report to update it.');
      },{signal});
    }
    if(!content('compare').children.length)content('compare').innerHTML='<div class="operator-empty"><h3>One recording is available</h3><p>You can analyse it and generate a report now. Add another capture to compare recorded quantities.</p><a href="#upload/'+encodeURIComponent(row.incident_id)+'">Attach another recording →</a></div>';
    const reportHost=document.createElement('div');content('report').append(reportHost);
    const report=typeof DRIncidentReport!=='undefined'?DRIncidentReport.mount(reportHost,row,{signal}):null;
    if(!report)reportHost.textContent='The report view is unavailable. Reload the application to load it.';
    const end=document.createElement('div');end.className='operator-next-actions';end.innerHTML='<button type="button" data-go-feature="compare">Compare recordings →</button><button type="button" data-go-feature="report">Generate report →</button>';content('waveforms').append(end);
    function select(id,focus=false){
      const openInputs=id==='inputs',openTechnical=id==='evidence';
      if(openInputs||openTechnical||id==='analyse')id='waveforms';
      if(!tabs.some(t=>t[0]===id))id='waveforms';
      preferences.set(key,id);if(preferences.size>12)preferences.delete(preferences.keys().next().value);
      for(const button of root.querySelectorAll('[role=tab]')){const active=button.dataset.workspaceTab===id;button.setAttribute('aria-selected',String(active));button.tabIndex=active?0:-1;}
      for(const pane of root.querySelectorAll('[role=tabpanel]'))pane.hidden=pane.dataset.workspacePane!==id;
      for(const step of root.querySelectorAll('.operator-workflow [data-go-feature]')){if(step.dataset.goFeature===id)step.setAttribute('aria-current','step');else step.removeAttribute('aria-current');}
      if(openInputs)inputs.open=true;if(openTechnical)technical.open=true;
      if(typeof setPortalTask==='function')setPortalTask(id,row);
      if(id==='report')report?.activate();
      if(focus)root.querySelector(`[data-workspace-tab="${id}"]`).focus();
    }
    root.addEventListener('click',event=>{
      const tab=event.target.closest('[data-workspace-tab]');if(tab){select(tab.dataset.workspaceTab);return;}
      const go=event.target.closest('[data-go-feature]');if(!go)return;
      if(go.dataset.goFeature==='study'){
        const more=document.querySelector('.incident-more');if(more){more.open=true;const study=more.querySelector('details');if(study)study.open=true;more.scrollIntoView({block:'start'});}return;
      }
      select(go.dataset.goFeature,true);
      if(go.dataset.goFeature==='inputs')inputs.scrollIntoView({block:'start'});
      if(go.closest('[data-guide-feature]')?.dataset.guideFeature==='projection'){const line=section.querySelector('.source-line-inputs');if(line){line.open=true;line.scrollIntoView({block:'start'});line.querySelector('select')?.focus({preventScroll:true});}}
    },{signal});
    root.querySelector('[role=tablist]').addEventListener('keydown',event=>{
      const button=event.target.closest('[role=tab]');if(!button||!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
      event.preventDefault();const current=tabs.findIndex(t=>t[0]===button.dataset.workspaceTab),index=event.key==='Home'?0:event.key==='End'?tabs.length-1:(current+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;select(tabs[index][0],true);
    },{signal});
    function update(result){
      const chosenLoop=section.querySelector('.source-fault-loop')?.value;
      guide.innerHTML=DRFeatureGuide.markup({hasSamples:data.sample_count>0,hasSecondRecord:(row.bundle?.files||[]).filter(f=>f.kind==='comtrade').length>1,hasAnalogSamples:data.channels.some(c=>c.kind==='analog'),hasSourceTimes:Array.isArray(data.time_range_s)&&data.time_range_s.length===2&&data.time_range_s.every(Number.isFinite)&&data.time_range_s[1]>data.time_range_s[0],hasNominalFrequency:Number.isFinite(data.nominal_frequency_hz)&&data.nominal_frequency_hz>=40&&data.nominal_frequency_hz<=70,analysisReady:Boolean(result),hasSupportedFits:(result?.fit_coverage?.model_consistent||0)>0,hasRegions:Boolean(result?.operator_conditions?.selection),hasLine:Boolean(result?.snapshot?.line?.length_km>0),hasLoop:Boolean(chosenLoop),faultLoop:chosenLoop,hasWindow:Number.isInteger(result?.options?.projection_window),hasOperationalResult:Boolean(row.result)});
    }
    const scalingHelp=document.createElement('p');scalingHelp.className='field-help';scalingHelp.textContent='Leave the voltage-level choice unspecified to retain unresolved ratios. The optional 132/220 kV choices apply labelled missing-CT assumptions only to otherwise-known secondary-current channels; actual supplied ratios remain unchanged.';
    section.querySelector('.source-voltage')?.closest('.inspection-toolbar')?.after(scalingHelp);
    const inspectionHost=document.getElementById('inspection-workspace'),requested=inspectionHost?.dataset.requestedTask;
    select(requested||preferences.get(key)||'waveforms');if(requested){delete inspectionHost.dataset.requestedRecord;delete inspectionHost.dataset.requestedTask;}update(null);
    return {select,update};
  }
  return {mount,tasks:()=>tabs.map(([id,title])=>({id,title}))};
})();
if(typeof module!=='undefined')module.exports=DROperatorWorkspace;
