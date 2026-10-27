'use strict';
const sourceAnalysisPreferences=new Map();
function mountSourceAnalysis(host,data,row,recordController,workbench) {
  const esc=DRSourceReport.esc,key=`${row.incident_id}/${row.number}/${data.file}`;
  const prefs=sourceAnalysisPreferences.get(key)||{voltage_kv:0,mappings:{}};
  sourceAnalysisPreferences.set(key,prefs);if(sourceAnalysisPreferences.size>12)sourceAnalysisPreferences.delete(sourceAnalysisPreferences.keys().next().value);
  const section=document.createElement('section');section.className='source-analysis';host.append(section);
  const otherRecords=(row.bundle?.files||[]).filter(f=>f.kind==='comtrade'&&f.name!==data.file);
  section.innerHTML=`<h2>Source analysis and report</h2><p>Usable observations can be analysed here before operational assignment. Review channel meanings, then apply your choices. CT defaults affect assumption-labelled analysis values; waveform readouts keep their displayed source units. Unavailable calculations keep a specific reason; the report remains available.</p><div class="inspection-toolbar"><label>Voltage level / missing CT default <select class="source-voltage"><option value="0">Not declared · retain unresolved ratios</option><option value="132">132 kV · missing CT 600/1</option><option value="220">220 kV · missing CT 800/1</option></select></label><button class="source-run">Apply meanings & analyse</button></div><details class="source-mappings"><summary>Channel meanings for source analysis (${data.channels.length})</summary><p class="field-help">These choices apply to independent source diagnostics and this report. Source IDs and raw observations stay unchanged. Automatic label suggestions are unverified; select Ignore to exclude a meaning.</p><div class="source-mapping-list">${data.channels.map(c=>{const targets=c.kind==='analog'?config.mapping_targets.analog:config.mapping_targets.digital;return `<label>${esc(c.id+' '+c.label)} <small>${esc(c.units)}</small><select data-meaning="${c.id}" aria-label="${c.id} analysis meaning"><option value="">Automatic label suggestion</option><option value="ignore">Ignore meaning; keep observations</option>${targets.map(t=>`<option value="${esc(t)}">${esc(t)}</option>`).join('')}</select></label>`;}).join('')}</div></details><p class="source-job-status" role="status"></p><div class="source-report-tools" hidden><button data-export="json">Download snapshot & evidence JSON</button><button data-export="html">Download printable snapshot</button><button data-export="print">Print snapshot</button></div><div class="source-summary"></div><details class="source-evidence" hidden><summary>Detailed channel/window evidence</summary><div class="source-channel-summary"></div><h3>Signal-model windows</h3><div class="source-window-pages inspection-toolbar"><button data-window-page="-1">Previous windows</button><span></span><button data-window-page="1">Next windows</button></div><div class="source-windows"></div><h3>Digital source observations</h3><div class="source-digital-pages inspection-toolbar"><button data-digital-page="-1">Previous digital channels</button><span></span><button data-digital-page="1">Next digital channels</button></div><div class="source-digital"></div></details>${otherRecords.length?`<section class="source-compare"><h3>Compare independent source recordings</h3><p class="field-help">Choose two signals for visual comparison on their own local axes. Selection does not establish common event, physical ends or clock alignment.</p><label>Second recording <select class="source-compare-record"><option value="">Choose…</option>${otherRecords.map(f=>`<option value="${esc(f.name)}">${esc(f.name)}</option>`).join('')}</select></label><div class="source-comparison"></div></section>`:''}`;
  section.querySelector('.source-voltage').value=String(prefs.voltage_kv);
  section.querySelectorAll('[data-meaning]').forEach(el=>el.value=prefs.mappings[el.dataset.meaning]||'');
  let generation=0,controller,timer,result=null,windowPage=0,digitalPage=0,comparisonGeneration=0,comparisonController;
  const q=selector=>section.querySelector(selector);
  function invalidate(message='Choices changed. Apply meanings & analyse to update the report.') {
    generation++;controller?.abort();clearTimeout(timer);result=null;
    q('.source-summary').innerHTML=DRSourceReport.schematic({terminals:{S:'Not available',R:'Not available'},sections:[],length_km:null,location:{status:'Not available',text:'Preparing source snapshot; supplied line facts will appear with provenance.'}});q('.source-evidence').hidden=true;q('.source-report-tools').hidden=true;q('.source-job-status').textContent=message;
  }
  function options() {return {voltage_kv:Number(q('.source-voltage').value),mappings:Object.fromEntries([...section.querySelectorAll('[data-meaning]')].filter(el=>el.value).map(el=>[el.dataset.meaning,el.value]).sort(([a],[b])=>a<b?-1:a>b?1:0))};}
  q('.source-voltage').onchange=()=>invalidate();section.querySelectorAll('[data-meaning]').forEach(el=>el.onchange=()=>invalidate());
  async function fetchResult(file,choices,signal) {
    const params=new URLSearchParams({revision:row.number,record:file,voltage_kv:choices.voltage_kv,mappings:JSON.stringify(choices.mappings)});
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
    section.querySelectorAll('[data-focus-window]').forEach(el=>el.onclick=()=>{const w=result.windows.find(w=>w.index===Number(el.dataset.focusWindow));workbench?.focusWindow(w.start_index,w.stop_index);});
  }
  async function run() {
    invalidate('Preparing source analysis…');const token=generation,choices=options();Object.assign(prefs,choices);
    controller=new AbortController();const signal=controller.signal;recordController.signal.addEventListener('abort',()=>controller.abort(),{once:true,signal});
    async function poll() {
      try {const body=await fetchResult(data.file,choices,signal);
        if(signal.aborted||token!==generation||!host.isConnected)return;
        if(body.file!==data.file||body.revision!==row.number||JSON.stringify(body.options)!==JSON.stringify(choices)||JSON.stringify(body.source_sha256)!==JSON.stringify(data.source_sha256))throw new Error('Source or choices changed; reopen this recording.');
        if(body.status==='pending'||body.status==='busy'){q('.source-job-status').textContent=body.detail;timer=setTimeout(poll,1000);return;}
        if(body.status!=='ready')throw new Error(body.detail||'Diagnostics could not finish; source inspection remains available.');
        result=body.result;windowPage=digitalPage=0;
        q('.source-job-status').textContent=`Analysis ready · ${result.fit_coverage.model_consistent} conditional fits / ${result.fit_coverage.total} evaluated channel-windows. Report and source evidence available.`;
        q('.source-summary').innerHTML=DRSourceReport.summary(result);q('.source-evidence').hidden=false;q('.source-report-tools').hidden=false;
        q('.source-channel-summary').innerHTML='<table><thead><tr><th>Source / assigned meaning</th><th>Units</th><th>Observed min / max</th><th>Finite / missing</th></tr></thead><tbody>'+result.channels.map(c=>`<tr><th>${esc(c.id+' '+c.label)}<small>${esc(c.meaning||'Meaning unassigned')}</small></th><td>${esc(c.units)}</td><td>${DRSourceReport.number(c.sample_min)} / ${DRSourceReport.number(c.sample_max)}</td><td>${c.finite_samples} / ${c.missing_samples}</td></tr>`).join('')+'</tbody></table>';
        renderEvidence();
      }catch(error){if(error.name!=='AbortError'&&token===generation){q('.source-job-status').textContent=error.message;result=null;q('.source-summary').innerHTML='';q('.source-evidence').hidden=true;q('.source-report-tools').hidden=true;}}
    }
    poll();
  }
  q('.source-run').onclick=run;
  section.querySelectorAll('[data-window-page]').forEach(el=>el.onclick=()=>{windowPage+=Number(el.dataset.windowPage);renderEvidence();});section.querySelectorAll('[data-digital-page]').forEach(el=>el.onclick=()=>{digitalPage+=Number(el.dataset.digitalPage);renderEvidence();});
  function exportReport(kind) {
    if(!result)return;
    const html='<!doctype html><html><head><meta charset="utf-8"><title>Source analysis snapshot</title><style>body{font:14px Arial;margin:30px;color:#243444}table{border-collapse:collapse;width:100%}td,th{padding:7px;border:1px solid #ddd;text-align:left}svg{width:100%;max-height:150px}section{break-inside:avoid;margin:16px 0}small{display:block}button{display:none}pre{white-space:pre-wrap}</style></head><body><h1>'+esc(row.name)+'</h1><p>'+esc(data.file)+' · revision '+row.number+'</p>'+DRSourceReport.summary(result)+'<p>Source byte hashes: '+esc(JSON.stringify(result.source_sha256))+'</p><p>Choices: '+esc(JSON.stringify(result.options))+'</p></body></html>';
    if(kind==='print'){const page=window.open('','_blank');if(page){page.opener=null;page.document.write(html);page.document.close();page.focus();page.print();}return;}
    const blob=new Blob([kind==='json'?JSON.stringify(result,null,2):html],{type:kind==='json'?'application/json':'text/html'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`source-analysis-r${row.number}.${kind==='json'?'json':'html'}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),3000);
  }
  section.querySelectorAll('[data-export]').forEach(el=>el.onclick=()=>exportReport(el.dataset.export));
  if(q('.source-compare-record'))q('.source-compare-record').onchange=()=>compare(q('.source-compare-record').value);
  async function compare(file) {
    comparisonGeneration++;comparisonController?.abort();const token=comparisonGeneration,container=q('.source-comparison');container.innerHTML='';if(!file)return;
    const ctl=new AbortController();comparisonController=ctl;recordController.signal.addEventListener('abort',()=>ctl.abort(),{once:true,signal:ctl.signal});container.textContent='Loading independent source envelopes…';
    try {const params=new URLSearchParams({revision:row.number,record:file});const response=await fetch(`/api/incidents/${row.incident_id}/inspection?${params}`,{signal:ctl.signal});const second=await response.json();if(!response.ok)throw new Error(second.detail||'Second source could not be opened.');if(token!==comparisonGeneration||ctl.signal.aborted)return;
      const analogs=meta=>meta.channels.filter(c=>c.kind==='analog');
      container.innerHTML=`<div class="source-comparison-signals">${[data,second].map((meta,i)=>`<section><h4>${esc(meta.file)}</h4><label>Source signal <select data-comparison-signal="${i}">${analogs(meta).map(c=>`<option value="${c.id}">${esc(c.id+' '+c.label+' · '+c.units)}</option>`).join('')}</select></label><div data-comparison-chart="${i}"></div></section>`).join('')}</div><p class="field-help">Each trace uses its own source sample-index axis and its own stated units. Envelopes are display summaries; use the main workbench for exact samples. No event alignment or terminal identity is inferred.</p><div class="source-comparison-summary"></div>`;
      const draw=()=>[data,second].forEach((meta,i)=>{const id=container.querySelector(`[data-comparison-signal="${i}"]`).value,c=meta.channels.find(c=>c.id===id);container.querySelector(`[data-comparison-chart="${i}"]`).innerHTML=c?comparisonPlot(c,meta):'<p>No recoverable analog signal.</p>';});
      container.querySelectorAll('[data-comparison-signal]').forEach(el=>el.onchange=draw);draw();
      const otherPrefs=sourceAnalysisPreferences.get(`${row.incident_id}/${row.number}/${file}`)||{voltage_kv:0,mappings:{}};
      const pollOther=async()=>{try{const body=await fetchResult(file,otherPrefs,ctl.signal);if(token!==comparisonGeneration||ctl.signal.aborted)return;if(['pending','busy'].includes(body.status)){container.querySelector('.source-comparison-summary').textContent=body.detail;setTimeout(pollOther,1000);return;}if(body.status!=='ready')throw new Error(body.detail||'Second source diagnostics unavailable.');container.querySelector('.source-comparison-summary').innerHTML=`<h4>Independent second-source observations</h4><p>${esc(body.result.trip.text)}</p><p>${esc(body.result.ar.text)}</p><p>${body.result.fit_coverage.model_consistent}/${body.result.fit_coverage.total} conditional channel-window fits. Choices: ${esc(JSON.stringify(body.result.options))}</p>`;}catch(error){if(error.name!=='AbortError'&&token===comparisonGeneration)container.querySelector('.source-comparison-summary').textContent=error.message;}};pollOther();
    }catch(error){if(error.name!=='AbortError'&&token===comparisonGeneration)container.textContent=error.message;}
  }
  function comparisonPlot(c,meta) {
    const points=c.trace,known=points.filter(p=>p[2]!==null);let lo=Infinity,hi=-Infinity;for(const p of known){lo=Math.min(lo,p[2]);hi=Math.max(hi,p[2]);}const scale=Math.max(Math.abs(lo),Math.abs(hi),1),x=i=>i/Math.max(1,meta.sample_count-1)*500,y=v=>95-(v/scale-lo/scale)/((hi/scale-lo/scale)||1)*85;
    const path=DRInspection.segments(points,meta.time_basis.minimum_interval_s?meta.time_basis.minimum_interval_s*8:Infinity).map(part=>part.map((p,i)=>`${i?'L':'M'}${x(p[0])},${y(p[2])}`).join(' ')).join(' ');
    const phase=DRInspection.phaseFor(c,meta.channels),color={A:'#c94145',B:'#b88a00',C:'#316ecc',N:'#606c78',unknown:'#176d82'}[phase];
    return `<svg viewBox="0 0 500 110" role="img" aria-label="${esc(c.label)} independent source envelope"><path d="${path}" stroke="${color}" fill="none"/></svg><p>${esc(c.units)} · observed envelope ${DRSourceReport.number(lo)}–${DRSourceReport.number(hi)} · indices 0–${meta.sample_count-1}</p>`;
  }
  recordController.signal.addEventListener('abort',()=>{generation++;comparisonGeneration++;controller?.abort();comparisonController?.abort();clearTimeout(timer);},{once:true});
  run();
}
