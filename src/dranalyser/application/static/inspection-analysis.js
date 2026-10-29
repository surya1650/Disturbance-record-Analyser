'use strict';
const sourceAnalysisPreferences=new Map();
function mountSourceAnalysis(host,data,row,recordController,workbench) {
  const esc=DRSourceReport.esc,key=`${row.incident_id}/${row.number}/${data.file}`;
  let prefs=sourceAnalysisPreferences.get(key)||{voltage_kv:0,mappings:{}};
  sourceAnalysisPreferences.set(key,prefs);if(sourceAnalysisPreferences.size>12)sourceAnalysisPreferences.delete(sourceAnalysisPreferences.keys().next().value);
  const section=document.createElement('section');section.className='source-analysis';host.append(section);
  const otherRecords=(row.bundle?.files||[]).filter(f=>f.kind==='comtrade'&&f.name!==data.file);
  section.innerHTML=`<h2>Source analysis and report</h2><p>Usable observations can be analysed here before operational assignment. Review channel meanings, then apply your choices. CT defaults affect assumption-labelled analysis values; waveform readouts keep their displayed source units. Unavailable calculations keep a specific reason; the report remains available.</p><div class="inspection-toolbar"><label>Voltage level / missing CT default <select class="source-voltage"><option value="0">Not declared · retain unresolved ratios</option><option value="132">132 kV · missing CT 600/1</option><option value="220">220 kV · missing CT 800/1</option></select></label><button class="source-run">Apply meanings & analyse</button></div><details class="source-mappings"><summary>Channel meanings for source analysis (${data.channels.length})</summary><p class="field-help">These choices apply to independent source diagnostics and this report. Source IDs and raw observations stay unchanged. Automatic label suggestions are unverified; select Ignore to exclude a meaning.</p><div class="source-mapping-list">${data.channels.map(c=>{const targets=c.kind==='analog'?config.mapping_targets.analog:config.mapping_targets.digital;return `<label>${esc(c.id+' '+c.label)} <small>${esc(c.units)}</small><select data-meaning="${c.id}" aria-label="${c.id} analysis meaning"><option value="">Automatic label suggestion</option><option value="ignore">Ignore meaning; keep observations</option>${targets.map(t=>`<option value="${esc(t)}">${esc(t)}</option>`).join('')}</select></label>`;}).join('')}</div></details><p class="source-job-status" role="status"></p><div class="source-report-tools" hidden><button data-export="json">Download snapshot & evidence JSON</button><button data-export="html">Download printable snapshot</button><button data-export="print">Print snapshot</button></div><div class="source-condition-tools inspection-toolbar"><button class="source-use-region">Compare A–B conditions</button><button class="source-clear-region">Clear interval</button></div><div class="source-condition-summary"></div><div class="source-line-summary"></div><details class="source-technical"><summary>Technical details, method availability and provenance</summary><div class="source-summary"></div></details><details class="source-evidence" hidden><summary>Detailed channel/window evidence</summary><div class="source-channel-summary"></div><h3>Signal-model windows</h3><div class="source-window-pages inspection-toolbar"><button data-window-page="-1">Previous windows</button><span></span><button data-window-page="1">Next windows</button></div><div class="source-windows"></div><h3>Digital source observations</h3><div class="source-digital-pages inspection-toolbar"><button data-digital-page="-1">Previous digital channels</button><span></span><button data-digital-page="1">Next digital channels</button></div><div class="source-digital"></div></details>${otherRecords.length?`<section class="source-compare"><h3>Compare independent source recordings</h3><p class="field-help">View every analog channel in matching quantity/phase rows, with voltages above currents. Missing or ambiguous counterparts remain visible. Selection does not establish common event, physical ends or clock alignment.</p><label>Second recording <select class="source-compare-record"><option value="">Choose…</option>${otherRecords.map(f=>`<option value="${esc(f.name)}">${esc(f.name)}</option>`).join('')}</select></label><div class="source-comparison"></div></section>`:''}`;
  section.querySelector('.source-voltage').value=String(prefs.voltage_kv);
  section.querySelectorAll('[data-meaning]').forEach(el=>el.value=prefs.mappings[el.dataset.meaning]||'');
  let region=null,generation=0,controller,timer,result=null,windowPage=0,digitalPage=0,comparisonGeneration=0,comparisonController,flow;
  const q=selector=>section.querySelector(selector);
  q('.source-run').textContent='Apply choices & analyse';
  const inputHost=document.createElement('div');inputHost.className='source-extra-inputs';inputHost.innerHTML=DRSourceInputs.markup(prefs);section.insertBefore(inputHost,q('.source-job-status'));
  q('.source-line-mode').value=prefs.line_id||(prefs.line_model?'__custom__':'');q('.source-fault-loop').value=prefs.fault_loop||'';q('.source-projection-window').value=prefs.projection_window??'';
  q('.source-custom-line').hidden=q('.source-line-mode').value!=='__custom__';
  for(const c of data.channels.filter(c=>c.kind==='digital')){
    const meaning=q(`[data-meaning="${c.id}"]`),state=document.createElement('select');state.dataset.assertion=c.id;state.setAttribute('aria-label',c.id+' asserted state');state.innerHTML='<option value="">Asserted state1 (assumed high)</option><option value="1">Asserted state1 · explicit choice</option><option value="0">Asserted state0 · explicit choice</option>';state.value=prefs.asserted_states?.[c.id]??'';meaning.parentElement.append(state);
  }
  const stable=DRSourceInputs.stable;
  let lineModels=[];
  fetch('/api/source-lines',{signal:recordController.signal}).then(async r=>DRSourceInputs.catalogue(await r.json(),r.ok)).then(items=>{
    if(recordController.signal.aborted||!host.isConnected)return;
    lineModels=items;const select=q('.source-line-mode'),chosen=select.value;
    select.innerHTML='<option value="">Frozen incident model if supplied</option>'+lineModels.filter(m=>m.id).map(m=>`<option value="${esc(m.id)}">${esc(m.name)} · ${esc(m.parameter_status)}</option>`).join('')+'<option value="__custom__">Enter declared line values</option>';
    if(chosen&&!['__custom__',...lineModels.map(m=>m.id)].includes(chosen)){select.add(new Option(chosen+' (not currently resolved)',chosen));}select.value=chosen;
    lineNotes();
  }).catch(error=>{if(error.name!=='AbortError')q('.source-line-notes').textContent='Line catalogue unavailable: '+error.message;});
  function lineNotes(){const chosen=q('.source-line-mode').value,line=lineModels.find(m=>m.id===chosen);q('.source-custom-line').hidden=chosen!=='__custom__';q('.source-line-notes').textContent=line?`${line.parameter_status}. ${line.provenance} Hash: ${line.sha256}`:chosen==='__custom__'?'Explicit user-declared values; blank fields remain Not available.':'No independent line is inferred. Frozen incident facts appear only when supplied.';}
  q('.source-line-mode').onchange=()=>{lineNotes();const line=lineModels.find(m=>m.id===q('.source-line-mode').value);if(q('.source-voltage').value==='0'&&[132,220].includes(line?.kv))q('.source-voltage').value=String(line.kv);invalidate();};
  q('.source-fault-loop').onchange=()=>invalidate();q('.source-projection-window').onchange=()=>run();section.querySelectorAll('[data-line-field],[data-assertion]').forEach(el=>el.onchange=()=>invalidate());
  q('.source-accept-meanings').onclick=()=>{
    if(!result){q('.source-job-status').textContent='Run source analysis first to inspect its suggestions.';return;}
    const suggestions=[...result.channels.map(c=>[c.id,c.meaning]),...result.digital_evidence.map(c=>[c.id,c.meanings.length===1?c.meanings[0]:''])];
    const counts=new Map();for(const[id,meaning]of suggestions)if(meaning&&meaning!=='ignore')counts.set((id[0]+'/'+meaning),(counts.get(id[0]+'/'+meaning)||0)+1);
    for(const[id,meaning]of suggestions)if(meaning&&meaning!=='ignore'&&counts.get(id[0]+'/'+meaning)===1){const select=q(`[data-meaning="${id}"]`);if(select)select.value=meaning;}
    invalidate('Unique label suggestions selected as unverified meaning choices. Apply choices to update the report.');
  };

  function invalidate(message='Choices changed. Apply meanings & analyse to update the report.') {
    generation++;controller?.abort();clearTimeout(timer);result=null;workbench?.setAnalysis(null);
    comparisonGeneration++;comparisonController?.abort();if(q('.source-compare-record')){q('.source-compare-record').value='';q('.source-comparison').innerHTML='';}
    q('.source-condition-summary').innerHTML='';q('.source-line-summary').innerHTML='';q('.source-summary').innerHTML=DRSourceReport.schematic({terminals:{S:'Not available',R:'Not available'},sections:[],length_km:null,location:{status:'Not available',text:'Preparing source snapshot; supplied line facts will appear with provenance.'}});q('.source-evidence').hidden=true;q('.source-report-tools').hidden=true;q('.source-job-status').textContent=message;flow?.update(null);
  }
  function options() {for(const el of section.querySelectorAll('input[data-line-field]'))if(el.validity?.badInput)throw new Error((el.getAttribute('aria-label')||'Line input')+' must be a valid number, or blank for unknown.');return DRSourceInputs.options({voltageKv:q('.source-voltage').value,
    mappings:Object.fromEntries([...section.querySelectorAll('[data-meaning]')].map(el=>[el.dataset.meaning,el.value])),
    assertedStates:Object.fromEntries([...section.querySelectorAll('[data-assertion]')].map(el=>[el.dataset.assertion,el.value])),
    lineMode:q('.source-line-mode').value,model:Object.fromEntries([...section.querySelectorAll('[data-line-field]')].map(el=>[el.dataset.lineField,el.value])),
    faultLoop:q('.source-fault-loop').value,projectionWindow:q('.source-projection-window').value});}
  q('.source-voltage').onchange=()=>invalidate();section.querySelectorAll('[data-meaning]').forEach(el=>el.onchange=()=>invalidate());
  async function fetchResult(file,choices,signal) {
    const params=new URLSearchParams({revision:row.number,record:file,voltage_kv:choices.voltage_kv,mappings:JSON.stringify(choices.mappings)});
    for(const field of ['line_id','fault_loop','projection_window'])if(choices[field]!==undefined)params.set(field,String(choices[field]));
    for(const field of ['line_model','asserted_states'])if(choices[field])params.set(field,JSON.stringify(choices[field]));
    const response=await fetch(`/api/incidents/${row.incident_id}/inspection/analysis?${params}`,{signal});
    const body=await response.json();if(!response.ok)throw new Error(body.detail||'Source analysis request could not be read.');return body;
  }
  function renderEvidence() {
    q('.source-windows').innerHTML=DRSourceReport.windows(result,windowPage);
    q('.source-window-pages span').textContent=`${result.windows.length?windowPage*4+1:0}–${Math.min((windowPage+1)*4,result.windows.length)} of ${result.windows.length} windows; ${result.remaining_windows} planned windows not evaluated.`;
    q('[data-window-page="-1"]').disabled=windowPage===0;q('[data-window-page="1"]').disabled=(windowPage+1)*4>=result.windows.length;
    q('.source-digital').innerHTML=DRSourceReport.digital(result,digitalPage);
    q('.source-digital-pages span').textContent=`${result.digital_evidence.length?digitalPage*8+1:0}–${Math.min((digitalPage+1)*8,result.digital_evidence.length)} of ${result.digital_evidence.length} digital channels`;
    q('[data-digital-page="-1"]').disabled=digitalPage===0;q('[data-digital-page="1"]').disabled=(digitalPage+1)*8>=result.digital_evidence.length;
    section.querySelectorAll('[data-focus-window]').forEach(el=>el.onclick=()=>{const w=result.windows.find(w=>w.index===Number(el.dataset.focusWindow));flow?.select('waveforms');workbench?.focusWindow(w.start_index,w.stop_index);});
  }
  async function run() {
    invalidate('Preparing source analysis…');const token=generation;let choices;try{choices=options();}catch(error){q('.source-job-status').textContent=error.message;return;}prefs=choices;sourceAnalysisPreferences.set(key,prefs);
    controller=new AbortController();const signal=controller.signal;recordController.signal.addEventListener('abort',()=>controller.abort(),{once:true,signal});
    async function poll() {
      try {const body=await fetchResult(data.file,choices,signal);
        if(signal.aborted||token!==generation||!host.isConnected)return;
        if(body.file!==data.file||body.revision!==row.number||stable(body.options)!==stable(choices)||stable(body.source_sha256)!==stable(data.source_sha256))throw new Error('Source or choices changed; reopen this recording.');
        if(body.status==='pending'||body.status==='busy'){q('.source-job-status').textContent=body.detail;timer=setTimeout(poll,1000);return;}
        if(body.status!=='ready')throw new Error(body.detail||'Diagnostics could not finish; source inspection remains available.');
        result=body.result;workbench?.setAnalysis(result);windowPage=digitalPage=0;
        const select=q('.source-projection-window'),chosen=choices.projection_window??'';select.innerHTML='<option value="">Choose a source window for projection</option>'+result.windows.map(w=>`<option value="${w.index}">Window ${w.index}: ${DRSourceReport.number(w.support_s[0])}–${DRSourceReport.number(w.support_s[1])} local s</option>`).join('');select.value=String(chosen);
        q('.source-job-status').textContent=result.windows.length?'Electrical observations ready. Move a cursor for RMS/angles; choose A–B to compare conditions.':'Instantaneous readings and recorded indications are available. '+result.methods.source_models.reason.replace(' Lower-density/short-support alternatives are not yet independently validated.','');
        renderConditions();q('.source-line-summary').innerHTML=DRSourceReport.schematic(result.snapshot.line,result.options?.fault_loop||result.options?.line_model||result.options?.line_id?result.snapshot.selected_projection:null);
        q('.source-summary').innerHTML=DRSourceReport.summary(result,false);q('.source-evidence').hidden=false;q('.source-report-tools').hidden=false;
        q('.source-channel-summary').innerHTML='<table><thead><tr><th>Source / assigned meaning</th><th>Units</th><th>Observed min / max</th><th>Finite / missing</th></tr></thead><tbody>'+result.channels.map(c=>`<tr><th>${esc(c.id+' '+c.label)}<small>${esc(c.meaning||'Meaning unassigned')}</small></th><td>${esc(c.units)}</td><td>${DRSourceReport.number(c.sample_min)} / ${DRSourceReport.number(c.sample_max)}</td><td>${c.finite_samples} / ${c.missing_samples}</td></tr>`).join('')+'</tbody></table>';
        renderEvidence();
      }catch(error){if(error.name!=='AbortError'&&token===generation){q('.source-job-status').textContent=error.message;result=null;workbench?.setAnalysis(null);q('.source-condition-summary').innerHTML='';q('.source-line-summary').innerHTML='';q('.source-summary').innerHTML='';q('.source-evidence').hidden=true;q('.source-report-tools').hidden=true;flow?.update(null);}}
    }
    poll();
  }
  function renderConditions(){if(!result)return;result.operator_conditions=DRConditions.build(result,region);result.simple_report=DRSimpleReport.build(result,row.result);q('.source-condition-summary').innerHTML=DRSimpleReport.markup(result.simple_report);flow?.update(result);}
  q('.source-use-region').onclick=()=>{if(!result){q('.source-job-status').textContent='Wait for electrical observations before selecting the comparison interval.';return;}const pins=workbench?.getPins();try{const next={start:pins?.A,end:pins?.B,start_s:workbench?.getPoint?.('A')?.[1]??null,end_s:workbench?.getPoint?.('B')?.[1]??null};DRConditions.build(result,next);region=next;renderConditions();q('.source-job-status').textContent='Selected A–B conditions updated. Regions are operator-selected; reapply after moving cursors.';}catch(error){q('.source-job-status').textContent=error.message;}};
  q('.source-clear-region').onclick=()=>{region=null;renderConditions();};
  q('.source-run').onclick=run;
  section.querySelectorAll('[data-window-page]').forEach(el=>el.onclick=()=>{windowPage+=Number(el.dataset.windowPage);renderEvidence();});section.querySelectorAll('[data-digital-page]').forEach(el=>el.onclick=()=>{digitalPage+=Number(el.dataset.digitalPage);renderEvidence();});
  function exportReport(kind) {
    if(!result)return;
    const html='<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Source analysis snapshot</title><style>body{font:14px Arial;margin:30px;color:#243444}table{border-collapse:collapse;width:100%}td,th{padding:7px;border:1px solid #ddd;text-align:left}svg{width:100%;max-height:150px}section{break-inside:avoid;margin:16px 0}small{display:block}button{display:none}pre{white-space:pre-wrap}</style></head><body><h1>'+esc(row.name)+'</h1><p>'+esc(data.file)+' · revision '+row.number+'</p>'+DRSourceReport.summary(result)+'<p>Source byte hashes: '+esc(JSON.stringify(result.source_sha256))+'</p><p>Choices: '+esc(JSON.stringify(result.options))+'</p></body></html>';
    if(kind==='print'){const page=window.open('','_blank');if(page){page.opener=null;page.document.write(html);page.document.close();page.focus();page.print();}return;}
    const blob=new Blob([kind==='json'?JSON.stringify(result,null,2):html],{type:kind==='json'?'application/json':'text/html'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`source-analysis-r${row.number}.${kind==='json'?'json':'html'}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),3000);
  }
  section.querySelectorAll('[data-export]').forEach(el=>el.onclick=()=>exportReport(el.dataset.export));
  if(q('.source-compare-record'))q('.source-compare-record').onchange=()=>compare(q('.source-compare-record').value);
  async function compare(file) {
    comparisonGeneration++;comparisonController?.abort();const token=comparisonGeneration,container=q('.source-comparison');container.innerHTML='';if(!file)return;
    const ctl=new AbortController();comparisonController=ctl;recordController.signal.addEventListener('abort',()=>ctl.abort(),{once:true,signal:ctl.signal});container.textContent='Loading independent source envelopes…';
    try {const params=new URLSearchParams({revision:row.number,record:file});const response=await fetch(`/api/incidents/${row.incident_id}/inspection?${params}`,{signal:ctl.signal});const second=await response.json();if(!response.ok)throw new Error(second.detail||'Second source could not be opened.');if(token!==comparisonGeneration||ctl.signal.aborted)return;
      if(second.file!==file||second.revision!==row.number)throw new Error('Second source identity changed; reopen the comparison.');
      const otherPrefs=sourceAnalysisPreferences.get(`${row.incident_id}/${row.number}/${file}`)||{voltage_kv:0,mappings:{}};
      container.innerHTML='<div class="source-comparison-channels"></div><div class="source-comparison-summary"></div>';
      DRChannelComparisonView.mount(container.querySelector('.source-comparison-channels'),data,second,prefs.mappings,otherPrefs.mappings);
      const pollOther=async()=>{try{const body=await fetchResult(file,otherPrefs,ctl.signal);if(token!==comparisonGeneration||ctl.signal.aborted)return;if(['pending','busy'].includes(body.status)){container.querySelector('.source-comparison-summary').textContent=body.detail;setTimeout(pollOther,1000);return;}if(body.status!=='ready')throw new Error(body.detail||'Second source diagnostics unavailable.');container.querySelector('.source-comparison-summary').innerHTML=`<h4>Independent second-source observations</h4><p>${esc(body.result.trip.text)}</p><p>${esc(body.result.ar.text)}</p><p>${body.result.fit_coverage.model_consistent}/${body.result.fit_coverage.total} conditional channel-window fits. Choices: ${esc(JSON.stringify(body.result.options))}</p>`;}catch(error){if(error.name!=='AbortError'&&token===comparisonGeneration)container.querySelector('.source-comparison-summary').textContent=error.message;}};pollOther();
    }catch(error){if(error.name!=='AbortError'&&token===comparisonGeneration)container.textContent=error.message;}
  }
  recordController.signal.addEventListener('abort',()=>{generation++;comparisonGeneration++;controller?.abort();comparisonController?.abort();clearTimeout(timer);},{once:true});
  flow=DROperatorWorkspace.mount(section,{traces:host.querySelector('.inspection-traces'),row,data,signal:recordController.signal,workbench});
  run();
}
