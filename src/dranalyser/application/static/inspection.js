'use strict';
function inspectionPanel(row) {
  const records = row.bundle?.files.filter(f => f.kind === 'comtrade') || [];
  if (!records.length) return '';
  const preferred=DRInputGuidance.preferredRecording(row,records);
  return `<section id="source-inspection" class="panel detail-section"><h2>Source waveform inspection</h2><p>Open recorded observations before assignment. Source scaling and timing do not establish physical, clock or fault-location authority.</p><label>Recording <select id="inspection-record">${records.map(f=>`<option value="${escapeHtml(f.name)}" ${f.name===preferred?'selected':''}>${escapeHtml(f.name)}</option>`).join('')}</select></label><div id="inspection-workspace" aria-live="polite"></div></section>`;
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
      host.innerHTML=`<p><strong>${escapeHtml({observed:'Waveforms decoded',partial:'Partial observations',sample_only:'Samples available; timing needs review',cfg_only:'Header available; data missing',unsupported:'Sample decoding unavailable'}[data.status]||data.status)}</strong> · Operational state: ${escapeHtml(labels[data.operational_eligibility.state]||data.operational_eligibility.state)}</p><p>${escapeHtml(data.issues.join(' '))}</p><details><summary>Input and timing details</summary><p>${data.sample_count} source samples · ${escapeHtml(data.time_basis.basis || data.time_basis.reason)}</p></details><div class="inspection-traces"></div>`;
      if (typeof renderInspectionWorkbench === 'function') {
        const workbench=renderInspectionWorkbench(host,data,row,controller);
        mountSourceAnalysis(host,data,row,controller,workbench);
      }
      else host.querySelector('.inspection-traces').textContent=data.channels.map(c=>`${c.id} ${c.label} (${c.units})`).join(' · ') || 'No recoverable samples. File inventory and decode reason are retained above.';
    } catch(error) {
      if (error.name!=='AbortError' && host.isConnected) host.textContent=error.message;
    }
  }
  select.onchange=load; load();
}
