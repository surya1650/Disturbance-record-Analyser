'use strict';
function inspectionPanel(row) {
  const records = row.bundle?.files.filter(f => f.kind === 'comtrade') || [];
  if (!records.length) return '';
  return `<section id="source-inspection" class="panel detail-section"><h2>Source waveform inspection</h2><p>Open recorded observations before assignment. Source scaling and timing do not establish physical, clock or fault-location authority.</p><label>Recording <select id="inspection-record">${records.map(f=>`<option value="${escapeHtml(f.name)}">${escapeHtml(f.name)}</option>`).join('')}</select></label>${records.length>1?`<details class="inspection-join-controls"><summary>Combine successive captures from one relay</summary><p>Select 2–8 captures. Compatible channels and recorded local times are required. Gaps and overlaps remain visible; this does not turn captures into opposite line ends.</p><label>Recordings <select class="inspection-join-records" multiple size="${Math.min(records.length,5)}">${records.map((f,i)=>`<option value="${escapeHtml(f.name)}" ${i<2?'selected':''}>${escapeHtml(f.name)}</option>`).join('')}</select></label><label><input class="inspection-join-confirm" type="checkbox"> I confirm these are successive captures from the same physical relay.</label><button class="inspection-join-button" type="button">Open combined timeline</button><p class="inspection-join-status" role="status"></p></details>`:''}<div id="inspection-workspace" aria-live="polite"></div></section>`;
}
let inspectionController;
function mountInspection(row) {
  inspectionController?.abort();
  const select = document.getElementById('inspection-record');
  if (!select) return;
  async function load() {
    inspectionController?.abort();
    const controller = new AbortController(); inspectionController=controller;
    const host = document.getElementById('inspection-workspace');
    host.textContent='Loading source observations…';
    try {
      const query=new URLSearchParams({revision:row.number,record:select.value});
      const response=await fetch(`/api/incidents/${row.incident_id}/inspection?${query}`,{signal:controller.signal});
      const data=await response.json();
      if (!response.ok) throw new Error(data.detail || 'Source inspection unavailable.');
      if (controller.signal.aborted || !host.isConnected) return;
      const entry=row.bundle?.files.find(f=>f.name===select.value),guidance=entry?DRInspection.operationalGuidance(entry):[];
      host.innerHTML=`${guidance.length?`<div class="inspection-operational-notes"><strong>Operational fault location is withheld; source inspection remains available.</strong>${guidance.map(note=>`<p>${escapeHtml(note)}</p>`).join('')}<button class="inspection-open-analysis" type="button">Open independent source analysis</button>${guidance.some(n=>n.startsWith('RATIO-PS:'))?'<button class="inspection-provide-ratios" type="button">Provide missing CT / VT ratings</button>':''}</div>`:''}<p><strong>${escapeHtml({observed:'Waveforms decoded',partial:'Partial observations',sample_only:'Samples available; timing needs review',cfg_only:'Header available; data missing',unsupported:'Sample decoding unavailable'}[data.status]||data.status)}</strong> · Operational state: ${escapeHtml(labels[data.operational_eligibility.state]||data.operational_eligibility.state)}</p><p>${escapeHtml(data.issues.join(' '))}</p><details><summary>Input and timing details</summary><p>${data.sample_count} source samples · ${escapeHtml(data.time_basis.basis || data.time_basis.reason)}</p></details><div class="inspection-traces"></div>`;
      if (typeof renderInspectionWorkbench === 'function') {
        const workbench=renderInspectionWorkbench(host,data,row,controller);
        if(data.join){
          const note=document.createElement('section');note.className='inspection-joined-notice';
          const params=new URLSearchParams({revision:row.number,record:data.file});
          note.innerHTML='<h3>Combined same-relay recording</h3><p>'+escapeHtml(data.join.clock_basis)+'</p><p>'+escapeHtml(data.join.sample_policy)+'</p><ul>'+data.join.sources.map(c=>'<li>'+escapeHtml(c.file)+' · '+c.samples+' samples'+(c.boundary_delta_s===null?'':c.boundary_delta_s<0?' · '+(-c.boundary_delta_s*1000).toFixed(3)+' ms overlap':' · '+(c.boundary_delta_s*1000).toFixed(3)+' ms between boundary samples')+'</li>').join('')+'</ul><p>RMS windows stop at source boundaries. Fundamental vectors and operational studies use the individual original captures.</p><a class="button primary" href="/api/incidents/'+row.incident_id+'/inspection/combined-export?'+params+'">Download joined COMTRADE + provenance ZIP</a><p class="field-help">Derived export, not relay-original evidence. The ZIP retains every capture trigger and original sample identity in provenance.json. Floating inputs may require reported quantization; export refuses missing samples or unrepresentable timing.</p>';
          const report=document.createElement('a');report.className='button inspection-joined-report';report.textContent='View combined inspection report';report.target='_blank';report.rel='noopener';
          const reportUrl=()=>{const q=new URLSearchParams(params);q.set('cursor',workbench?.getPins().A??0);return '/api/incidents/'+row.incident_id+'/inspection/combined-report?'+q;};
          report.href=reportUrl();report.onclick=()=>{report.href=reportUrl();};note.append(report);
          host.insertBefore(note,host.querySelector('.inspection-traces'));
        }else mountSourceAnalysis(host,data,row,controller,workbench);
        const go=host.querySelector('.inspection-open-analysis');if(go)go.onclick=()=>host.querySelector('.source-analysis')?.scrollIntoView({block:'start',behavior:'smooth'});
        const provide=host.querySelector('.inspection-provide-ratios');if(provide)provide.onclick=()=>{const section=[...document.querySelectorAll('[data-instrument-file]')].find(s=>s.dataset.instrumentFile===data.file);if(section){for(let p=section;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;section.scrollIntoView({block:'start',behavior:'smooth'});}};
      }
      else host.querySelector('.inspection-traces').textContent=data.channels.map(c=>`${c.id} ${c.label} (${c.units})`).join(' · ') || 'No recoverable samples. File inventory and decode reason are retained above.';
    } catch(error) {
      if (error.name!=='AbortError' && host.isConnected) host.textContent=error.message;
    }
  }
  const combine=document.querySelector('.inspection-join-button');
  if(combine)combine.onclick=()=>{
    const status=document.querySelector('.inspection-join-status');
    if(!document.querySelector('.inspection-join-confirm').checked){status.textContent='Confirm the same physical relay before combining captures.';return;}
    const names=[...document.querySelector('.inspection-join-records').selectedOptions].map(o=>o.value);
    if(names.length<2||names.length>8){status.textContent='Select 2–8 recordings.';return;}
    const value='@join:'+JSON.stringify(names);
    if(![...select.options].some(o=>o.value===value))select.add(new Option('Combined · '+names.join(' + '),value));
    select.value=value;status.textContent='Checking channel compatibility and declared times…';load();
  };
  select.onchange=load; load();
}
