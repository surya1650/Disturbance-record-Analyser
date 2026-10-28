'use strict';
function inspectionPanel(row) {
  const records=row.bundle?.files.filter(f=>f.kind==='comtrade')||[];
  if(!records.length)return '';
  return `<section id="source-inspection"><section data-incident-pane="viewer inputs diagrams" class="panel detail-section"><h2>Recording</h2><label>Recording <select id="inspection-record">${records.map(f=>`<option value="${escapeHtml(f.name)}">${escapeHtml(DRIncident.recordLabel(row,f.name))}</option>`).join('')}</select></label></section><section data-incident-pane="combine" class="panel detail-section"><h2>Combine successive captures</h2>${records.length>1?`<div class="inspection-join-controls"><p>Select 2–8 captures from the same physical relay. Channels and recorded local times must be compatible. All samples, gaps and overlaps remain visible.</p><label>Recordings <select class="inspection-join-records" multiple size="${Math.min(records.length,5)}">${records.map(f=>`<option value="${escapeHtml(f.name)}">${escapeHtml(f.name)}</option>`).join('')}</select></label><label><input class="inspection-join-confirm" type="checkbox"> I confirm these are successive captures from the same physical relay.</label><button class="inspection-join-button" type="button">Open combined timeline</button><p class="inspection-join-status" role="status"></p></div>`:'<p>Attach another capture from the same relay to combine recordings.</p>'}<p class="field-help">This creates a joined inspection timeline and a derived COMTRADE export. Both captures remain evidence from one end; a second capture is not a receiving-end record.</p></section><div id="inspection-workspace" aria-live="polite"></div></section>`;
}
let inspectionController;
function mountInspection(row) {
  inspectionController?.abort();
  const select=document.getElementById('inspection-record');if(!select)return;
  async function load() {
    inspectionController?.abort();const controller=new AbortController();inspectionController=controller;
    const host=document.getElementById('inspection-workspace');host.innerHTML='<p data-incident-pane="viewer">Loading source observations…</p>';DRIncident.show();
    try {
      const query=new URLSearchParams({revision:row.number,record:select.value});
      const response=await fetch(`/api/incidents/${row.incident_id}/inspection?${query}`,{signal:controller.signal});const data=await response.json();
      if(!response.ok)throw new Error(data.detail||'Source inspection unavailable.');if(controller.signal.aborted||!host.isConnected)return;
      const entry=row.bundle?.files.find(f=>f.name===select.value),guidance=entry?DRInspection.operationalGuidance(entry):[];
      host.innerHTML=`<section data-incident-pane="inputs" class="panel detail-section"><h2>Selected recording: ${escapeHtml(data.file)}</h2><p>${escapeHtml(data.issues.join(' '))}</p><p>${data.sample_count} samples · ${escapeHtml(data.time_basis.basis||data.time_basis.reason)}</p>${guidance.length?`<div class="inspection-operational-notes"><strong>Operational fault location needs input review.</strong>${guidance.map(note=>`<p>${escapeHtml(note)}</p>`).join('')}${guidance.some(n=>n.startsWith('RATIO-PS:'))?'<button class="inspection-provide-ratios" type="button">Provide missing CT / VT ratings</button>':''}</div>`:''}</section><section data-incident-pane="viewer" class="panel detail-section"><p class="field-help">${escapeHtml({observed:'Waveforms decoded',partial:'Partial observations',sample_only:'Samples available; timing needs review',cfg_only:'Header available; data missing',unsupported:'Sample decoding unavailable'}[data.status]||data.status)}${guidance.length?` · <a href="${DRIncident.link(row,'inputs')}">Review required analysis inputs →</a>`:''}</p><div class="inspection-traces"></div></section>`;
      if(typeof renderInspectionWorkbench==='function'){
        const workbench=renderInspectionWorkbench(host,data,row,controller);
        if(data.join){
          const params=new URLSearchParams({revision:row.number,record:data.file}),note=document.createElement('section');note.className='panel detail-section inspection-joined-notice';note.dataset.incidentPane='combine';
          note.innerHTML='<h3>Joined capture provenance and export</h3><p>'+escapeHtml(data.join.clock_basis)+'</p><p>'+escapeHtml(data.join.sample_policy)+'</p><ul>'+data.join.sources.map(c=>'<li>'+escapeHtml(c.file)+' · '+c.samples+' samples'+(c.boundary_delta_s===null?'':c.boundary_delta_s<0?' · '+(-c.boundary_delta_s*1000).toFixed(3)+' ms overlap':' · '+(c.boundary_delta_s*1000).toFixed(3)+' ms between boundary samples')+'</li>').join('')+'</ul><a class="button primary" href="/api/incidents/'+row.incident_id+'/inspection/combined-export?'+params+'">Download joined COMTRADE + provenance ZIP</a><p class="field-help">Derived export. Floating inputs may require reported quantization. Export refuses missing samples or unrepresentable timing. Original captures retain their identity.</p>';host.append(note);
          const report=document.createElement('section');report.className='panel detail-section';report.dataset.incidentPane='viewer';report.innerHTML='<h2>Combined inspection report</h2><p>Sample RMS, digital observations and capture provenance. Fundamental models and operational studies use the original captures.</p>';
          const button=document.createElement('a');button.className='button primary inspection-joined-report';button.textContent='View combined report';button.target='_blank';button.rel='noopener';
          const reportUrl=()=>{const q=new URLSearchParams(params);q.set('cursor',workbench?.getPins().A??0);return '/api/incidents/'+row.incident_id+'/inspection/combined-report?'+q;};button.href=reportUrl();button.onclick=()=>{button.href=reportUrl();};report.append(button);host.append(report);
          const status=document.querySelector('.inspection-join-status');if(status)status.textContent='Combined timeline ready. View waveforms or download the derived ZIP here.';location.hash=DRIncident.link(row,'viewer');
        }else {
          const saved=await api(`/api/incidents/${row.incident_id}/diagram-inputs?`+query);
          if(controller.signal.aborted||!host.isConnected)return;
          row.diagramInputs=saved;if(saved.options&&!sourceAnalysisPreferences.has(`${row.incident_id}/${row.number}/${data.file}`))sourceAnalysisPreferences.set(`${row.incident_id}/${row.number}/${data.file}`,saved.options);
          mountSourceAnalysis(host,data,row,controller,workbench);
        }
        const provide=host.querySelector('.inspection-provide-ratios');if(provide)provide.onclick=()=>{location.hash=DRIncident.link(row,'inputs');const section=[...document.querySelectorAll('[data-instrument-file]')].find(s=>s.dataset.instrumentFile===data.file);if(section){section.open=true;section.scrollIntoView({block:'start',behavior:'smooth'});}};
      }else host.querySelector('.inspection-traces').textContent='No waveform renderer is available.';
      DRIncident.show();
    }catch(error){if(error.name!=='AbortError'&&!controller.signal.aborted&&host.isConnected){host.innerHTML='<p data-incident-pane="viewer inputs combine" class="panel detail-section"></p>';host.firstChild.textContent=error.message;DRIncident.show();}}
  }
  const combine=document.querySelector('.inspection-join-button');if(combine)combine.onclick=()=>{
    const status=document.querySelector('.inspection-join-status');if(!document.querySelector('.inspection-join-confirm').checked){status.textContent='Confirm the same physical relay before combining captures.';return;}
    const names=[...document.querySelector('.inspection-join-records').selectedOptions].map(o=>o.value);if(names.length<2||names.length>8){status.textContent='Select 2–8 recordings.';return;}
    const ends=new Set(names.map(name=>row.presentation.record_ends[name]).filter(Boolean));if(ends.size>1){status.textContent='These captures are labelled as opposite ends. Correct the labels or select captures from one relay only.';return;}
    const value='@join:'+JSON.stringify(names);if(![...select.options].some(o=>o.value===value))select.add(new Option('Combined · '+names.join(' + '),value));select.value=value;status.textContent='Checking compatible channels and times…';load();
  };
  select.onchange=load;load();
}
