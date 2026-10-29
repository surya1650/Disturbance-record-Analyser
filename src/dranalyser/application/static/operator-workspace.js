'use strict';
const DROperatorWorkspace=(()=>{
  const preferences=new Map();
  const tabs=[['waveforms','Waveforms','Inspect analog and digital observations. Move a cursor for exact values; no line model is required.'],['report','Simple report','Read selected pre-fault, fault and post-fault values, distance availability and recorded indications.'],['inputs','Inputs & help','Choose only the inputs needed for the feature you want. Apply changed choices to update the report.'],['compare','Compare recordings','Compare the same quantities side by side. Visual comparison does not confirm common events or clocks.'],['evidence','Technical evidence','Inspect method availability, supported windows and source-quality evidence when you need detail.']];
  function mount(section,{traces,row,data,signal,workbench}){
    const root=document.createElement('div');root.className='operator-workspace';
    const key=row.incident_id+'/'+row.number,prefix='operator-'+String(row.incident_id).replace(/[^a-zA-Z0-9]/g,'')+'-'+row.number;
    root.innerHTML=`<div class="operator-tabs" role="tablist" aria-label="Recording tasks">${tabs.map(([id,title])=>`<button type="button" role="tab" id="${prefix}-${id}-tab" aria-controls="${prefix}-${id}" data-workspace-tab="${id}">${title}</button>`).join('')}</div>`+tabs.map(([id,title,help])=>`<section role="tabpanel" tabindex="0" id="${prefix}-${id}" aria-labelledby="${prefix}-${id}-tab" data-workspace-pane="${id}" hidden><div class="operator-task-heading"><h2>${title}</h2><p>${help}</p></div><div data-workspace-content="${id}"></div></section>`).join('');
    section.append(root);
    const content=id=>root.querySelector(`[data-workspace-content="${id}"]`);
    const record=(row.bundle?.files||[]).find(f=>f.name===data.file)||{};
    const noticePanel=document.createElement('div');noticePanel.innerHTML=DRInputGuidance.markup(record);content('waveforms').append(noticePanel);
    if(traces)content('waveforms').append(traces);
    const reviewInputs=document.createElement('div');reviewInputs.innerHTML=instrumentReviewEditor(row,data.file);content('inputs').append(reviewInputs);
    bindInstrumentReview(row,reviewInputs,{signal,onSuccess:async(updated,result)=>{
      history.replaceState(null,'','#incident/'+row.incident_id);await detail(row.incident_id);
      const select=document.getElementById('inspection-record');if(select&&[...select.options].some(o=>o.value===result.reviewed_record)){select.value=result.reviewed_record;select.dispatchEvent(new Event('change'));}
      notice('Reviewed CFG copy created in revision '+updated.number+'. Original files are preserved; inspect the rechecked copy before operational assignment.');
    }});
    const guide=document.createElement('section');guide.className='operator-feature-guide';content('inputs').append(guide);
    const original=[...section.children].filter(el=>el!==root);
    for(const el of original){
      if(el.matches('.source-job-status')){root.insertBefore(el,root.querySelector('[role=tabpanel]'));continue;}
      const destination=el.matches('.source-report-tools,.source-condition-tools,.source-condition-summary')?'report':el.matches('.source-line-summary,.source-technical,.source-evidence')?'evidence':el.matches('.source-compare')?'compare':'inputs';
      content(destination).append(el);
    }
    if(typeof DREventStudy!=='undefined'){
      const sourceDetails=document.createElement('details');sourceDetails.className='operator-source-details';
      sourceDetails.innerHTML='<summary>Selected-record fit measurements and exports</summary>';
      for(const el of [...content('report').children])sourceDetails.append(el);
      content('evidence').append(sourceDetails);
      const eventHost=document.createElement('div');eventHost.innerHTML=DREventStudy.panel(row);content('report').append(eventHost);
      const eventStudy=DREventStudy.bind(row,eventHost,signal,{sourceChoices(record){
        const chosen=sourceAnalysisPreferences.get(row.incident_id+'/'+row.number+'/'+record);
        return chosen&&(Object.keys(chosen.mappings||{}).length||Object.keys(chosen.asserted_states||{}).length)?{mappings:chosen.mappings||{},asserted_states:chosen.asserted_states||{}}:undefined;
      }});
      eventHost.addEventListener('event-study-request-region',event=>{
        const {record,kind}=event.detail||{},pins=workbench?.getPins();
        if(record!==data.file||!pins){notice('Select '+String(record||'the requested recording')+' in Waveforms, place cursors A and B, then return here to apply that interval.');return;}
        const lo=Math.min(pins.A,pins.B),hi=Math.max(pins.A,pins.B)+1;
        if(eventStudy.applyRegion(record,[lo,hi],kind))notice('Applied samples '+lo+'–'+(hi-1)+' inclusive to the '+kind+' interval. Build the event report to update it.');
      },{signal});
    }
    if(!content('compare').children.length)content('compare').innerHTML='<p class="operator-empty">Attach another recording to this incident to compare channels. Keep matching CFG/DAT files together in distinct folders.</p>';
    const end=document.createElement('div');end.className='operator-next-actions';end.innerHTML='<button type="button" data-go-feature="inputs">Review inputs & explanations →</button><button type="button" data-go-feature="report">Read simple report →</button>';content('waveforms').append(end);
    const reportHelp=document.createElement('details');reportHelp.className='operator-region-help';reportHelp.innerHTML='<summary>How to select pre-fault, fault and post-fault regions</summary><p>On Waveforms place A and B around the interval you want, then use the matching interval button in the event report. Both selected samples are included. At least one complete nominal cycle must fit inside each region. Moving cursors does not change an already built report.</p>';content('report').insertBefore(reportHelp,content('report').firstChild);
    const back=document.createElement('button');back.type='button';back.dataset.goFeature='waveforms';back.textContent='← Set A and B on waveforms';reportHelp.after(back);
    function select(id,focus=false){
      if(!tabs.some(t=>t[0]===id))id='waveforms';
      preferences.set(key,id);if(preferences.size>12)preferences.delete(preferences.keys().next().value);
      for(const button of root.querySelectorAll('[role=tab]')){const active=button.dataset.workspaceTab===id;button.setAttribute('aria-selected',String(active));button.tabIndex=active?0:-1;}
      for(const pane of root.querySelectorAll('[role=tabpanel]'))pane.hidden=pane.dataset.workspacePane!==id;
      if(focus)root.querySelector(`[data-workspace-tab="${id}"]`).focus();
    }
    root.addEventListener('click',e=>{
      const tab=e.target.closest('[data-workspace-tab]');if(tab){select(tab.dataset.workspaceTab);return;}
      const go=e.target.closest('[data-go-feature]');if(!go)return;
      if(go.dataset.goFeature==='study'){
        const more=document.querySelector('.incident-more');if(more){more.open=true;const study=more.querySelector('details');if(study)study.open=true;more.scrollIntoView({block:'start',behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});}return;
      }
      select(go.dataset.goFeature,true);
      if(go.closest('[data-guide-feature]')?.dataset.guideFeature==='projection'){const line=section.querySelector('.source-line-inputs');if(line){line.open=true;line.scrollIntoView({block:'start',behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});line.querySelector('select')?.focus({preventScroll:true});}}
    });
    root.querySelector('[role=tablist]').addEventListener('keydown',e=>{
      const button=e.target.closest('[role=tab]');if(!button||!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;
      e.preventDefault();const current=tabs.findIndex(t=>t[0]===button.dataset.workspaceTab),index=e.key==='Home'?0:e.key==='End'?tabs.length-1:(current+(e.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;select(tabs[index][0],true);
    });
    function update(result){
      const chosenLoop=section.querySelector('.source-fault-loop')?.value;
      guide.innerHTML=DRFeatureGuide.markup({hasSamples:data.sample_count>0,hasSecondRecord:(row.bundle?.files||[]).filter(f=>f.kind==='comtrade').length>1,analysisReady:Boolean(result),hasSupportedFits:(result?.fit_coverage?.model_consistent||0)>0,hasRegions:Boolean(result?.operator_conditions?.selection),hasLine:Boolean(result?.snapshot?.line?.length_km>0),hasLoop:Boolean(chosenLoop),faultLoop:chosenLoop,hasWindow:Number.isInteger(result?.options?.projection_window),hasOperationalResult:Boolean(row.result)});
      const run=section.querySelector('.source-run');if(run){run.classList.add('operator-primary-action');run.textContent='Apply inputs & update report';}
      const report=section.querySelector('.source-condition-summary');if(!result&&report&&!report.innerHTML)report.innerHTML='<div class="operator-empty"><h3>Report waiting for analysis</h3><p>Read the analysis status above. Exact waveform inspection remains available. Open Inputs & help to review changed or missing inputs; unavailable calculations keep their explanation.</p></div>';
    }
    const inputHeading=content('inputs').querySelector('h2');if(inputHeading)inputHeading.textContent='Analysis input choices';
    const apply=section.querySelector('.source-use-region');if(apply)apply.setAttribute('aria-label','Apply A–B as the fault interval');
    const scalingHelp=document.createElement('p');scalingHelp.className='field-help';scalingHelp.textContent='Voltage-level choice is optional. Leave it unspecified for raw inspection. The 132 kV and 220 kV options apply assumption-labelled missing CT defaults of 600/1 and 800/1 only to otherwise-known secondary-current channels. Valid supplied ratios remain; this does not verify CT/VT wiring.';
    section.querySelector('.source-voltage')?.closest('.inspection-toolbar')?.after(scalingHelp);
    const inspectionHost=document.getElementById('inspection-workspace'),requested=inspectionHost?.dataset.requestedRecord===data.file?inspectionHost.dataset.requestedTask:null;
    select(requested||preferences.get(key)||'waveforms');if(requested){delete inspectionHost.dataset.requestedRecord;delete inspectionHost.dataset.requestedTask;}update(null);
    return {select,update};
  }
  return {mount};
})();
