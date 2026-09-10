'use strict';
const $ = id => document.getElementById(id);
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const labels = {queued:'Queued',running:'Processing',needs_review:'Needs review',completed:'Completed',attention:'Needs attention',failed:'Failed'};
const badge = state => `<span class="badge ${escapeHtml(state)}">${escapeHtml(labels[state] || state)}</span>`;
const date = stamp => new Date(stamp * 1000).toLocaleString(undefined, {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
const size = bytes => bytes > 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${(bytes / 1024).toFixed(1)} KB`;
let config, selected = [], page = 0, lastItems = [], current = null, polling = false, busyUpload = false;

function notice(message = '') { $('notice').textContent = message; $('notice').hidden = !message; }
async function api(path, options = {}) {
  options.headers = {...options.headers, 'X-DR-Token': config?.token || ''};
  const response = await fetch(path, options);
  const body = await response.json();
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail || body));
  return body;
}
const jsonPost = body => ({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});

async function overview() {
  const result = await api(`/api/incidents?limit=20&offset=${page * 20}&q=${encodeURIComponent($('search').value)}&state=${$('state-filter').value}`);
  lastItems = result.items;
  const counts = result.summary;
  const total = Object.values(counts).reduce((a,b) => a+b, 0);
  $('metrics').innerHTML = [
    ['Total incidents', total, 'Across all intake sources'],
    ['Needs review', (counts.needs_review || 0) + (counts.attention || 0), 'Assignments or evidence to check'],
    ['In progress', (counts.queued || 0) + (counts.running || 0), 'Queued and processing'],
    ['Completed', counts.completed || 0, 'Analysis reports available']
  ].map(([title,value,hint], i) => `<div class="metric ${i===3?'accent':''}"><div class="metric-label">${title}<span>${['▤','◷','↻','✓'][i]}</span></div><div class="metric-number">${value}</div><small>${hint}</small></div>`).join('');
  $('incident-list').innerHTML = result.items.length ? `<table><thead><tr><th>Incident</th><th>Source</th><th>Status</th><th>Updated</th><th></th></tr></thead><tbody>${result.items.map(row => `<tr><td><a href="#incident/${row.id}"><strong>${escapeHtml(row.name)}</strong></a><small>${escapeHtml(row.line_id || 'Line pending')} · Revision ${row.number}</small></td><td>${escapeHtml(row.source)}</td><td>${badge(row.state)}</td><td>${date(row.updated)}</td><td><a href="#incident/${row.id}" aria-label="Open ${escapeHtml(row.name)}">View →</a></td></tr>`).join('')}</tbody></table>` : `<div class="empty"><strong>${total?'No matching incidents':'Your workspace is ready'}</strong>${total?'Try another name or status filter.':'Upload your first set of relay records, or connect a collector to get started.'}</div>`;
  $('prev').disabled = page === 0;
  $('next').disabled = result.items.length < 20;
  $('page-label').textContent = `Page ${page+1}`;
}

function chooseFiles(files) {
  const existing = new Set(selected.map(f => f.webkitRelativePath || f.name));
  for (const file of files) {
    const name = file.webkitRelativePath || file.name;
    if (existing.has(name)) { notice(`A file named ${name} is already selected. Use folders to distinguish terminals.`); continue; }
    existing.add(name); selected.push(file);
  }
  if (!$('incident-name').value && selected.length) $('incident-name').value = selected[0].name.replace(/\.[^.]+$/, '');
  renderFiles();
}
function renderFiles() {
  $('selected-files').innerHTML = selected.map((f,i) => `<div class="file-row"><span>${escapeHtml(f.webkitRelativePath || f.name)} <small class="muted">${size(f.size)}</small></span><button type="button" data-remove="${i}" aria-label="Remove ${escapeHtml(f.name)}">✕</button></div>`).join('');
}
async function uploadView(target = '') {
  const result = await api('/api/incidents?limit=200');
  $('target-incident').innerHTML = '<option value="">Create a new incident</option>' + result.items.map(row => `<option value="${row.id}" data-revision="${row.number}">${escapeHtml(row.name)} · r${row.number}</option>`).join('');
  if (target && !result.items.some(row => row.id === target)) {
    const row = await api(`/api/incidents/${target}`);
    $('target-incident').add(new Option(`${row.name} · r${row.number}`, target));
    $('target-incident').lastChild.dataset.revision = row.number;
  }
  $('target-incident').value = target;
}
function submitUpload(event) {
  event.preventDefault(); notice();
  if (busyUpload) return;
  if (!selected.length) return notice('Choose files for this incident first.');
  if (selected.reduce((n,f) => n+f.size, 0) > 400*1024*1024) return notice('The selected files exceed 400 MB.');
  const data = new FormData();
  selected.forEach(f => data.append('files', f, f.webkitRelativePath || f.name));
  data.append('name', $('incident-name').value);
  if ($('target-incident').value) {
    data.append('incident_id', $('target-incident').value);
    data.append('expected_revision', $('target-incident').selectedOptions[0].dataset.revision);
  }
  busyUpload = true; $('submit-upload').disabled = true; $('upload-progress').hidden = false;
  const xhr = new XMLHttpRequest(); xhr.open('POST','/api/intake'); xhr.setRequestHeader('X-DR-Token', config.token);
  xhr.upload.onprogress = event => {
    if (event.lengthComputable) $('upload-progress').querySelector('progress').value = event.loaded/event.total*100;
  };
  const finish = () => { busyUpload=false; $('submit-upload').disabled=false; $('upload-progress').hidden=true; };
  xhr.onerror = () => { finish(); notice('Upload could not reach the local application. Check that it is running.'); };
  xhr.onload = () => {
    finish();
    let result;
    try { result=JSON.parse(xhr.responseText); } catch { return notice('The application returned an unexpected upload response.'); }
    if (xhr.status >= 400) return notice(typeof result.detail === 'string' ? result.detail : JSON.stringify(result.detail));
    selected=[];renderFiles();$('file-picker').value='';$('folder-picker').value='';
    location.hash=`incident/${result.incident_id}`;
  };
  xhr.send(data);
}

function assignmentForm(row) {
  const records = row.bundle?.files.filter(f => f.kind === 'comtrade') || [];
  const options = '<option value="">Analyse without line constants</option>' + config.lines.filter(l=>l.id).map(l=>`<option value="${escapeHtml(l.id)}">${escapeHtml(l.name)} · ${l.kv} kV · ${l.parameter_status}</option>`).join('');
  return `<form id="review-form" class="panel"><div class="panel-heading"><div><h2>Confirm the incident assignment</h2><p>Choose one primary record at each available end. Other records can corroborate it.</p></div></div><div class="detail-section"><label for="review-line">Line definition</label><select id="review-line">${options}</select><p class="field-help">Without line constants, you can still inspect protection behaviour. Provisional definitions do not establish operational distance accuracy.</p></div><div class="table-wrap"><table class="assign-table"><thead><tr><th>Record & evidence</th><th>Data quality</th><th>Use in analysis</th></tr></thead><tbody>${records.map((f,i) => {
    const usable = f.ok && !f.duplicate_of && (!f.blocked || (config.mapping_targets && f.channel_inventory?.length));
    const state = f.duplicate_of?'Duplicate':f.blocked?'Blocked':!f.ok?'Unreadable':'Usable';
    return `<tr><td><strong>${escapeHtml(f.name)}</strong><small>${escapeHtml(f.station)} · ${f.fs_hz} Hz</small><p class="field-help">${escapeHtml(f.suggested_reason || '')}${f.suggested_end?` · Suggested end ${f.suggested_end}`:''}</p></td><td>${state}<div class="flags">${escapeHtml(f.error || f.duplicate_of || f.flags.join('\n'))}</div></td><td><select data-record="${escapeHtml(f.name)}" data-index="${i}" ${usable?'':'disabled'}><option value="">${usable?'Choose…':'Excluded'}</option><option value="excluded">Exclude from this analysis</option><option value="S:primary">End S · Primary</option><option value="S:corroborating">End S · Corroborating</option><option value="R:primary">End R · Primary</option><option value="R:corroborating">End R · Corroborating</option></select></td></tr>`;
  }).join('')}</tbody></table></div>${mappingEditor(row)}${rxReviewEditor(row)}${stageReviewEditor(row)}<div class="detail-section"><button class="button primary" type="submit">Confirm & analyse →</button></div></form>`;
}
async function detail(id, revision = '') {
  const row = await api(`/api/incidents/${id}${revision?`?revision=${revision}`:''}`); current=row;
  await loadStageReviewSource(row);
  const result = row.result;
  let body = `<div class="detail-top"><a href="#overview">← All incidents</a><span class="muted">/ Revision ${row.number}</span>${badge(row.state)}</div><div class="page-title"><div><div class="eyebrow">INCIDENT ${id.slice(0,8).toUpperCase()}</div><h1>${escapeHtml(row.name)}</h1><p>${escapeHtml(row.source)} intake · ${date(row.created)} · ${row.files.length} files</p></div><div class="detail-actions"><a class="button" href="#upload/${id}">＋ Attach late records</a>${result?.report_path?`<a class="button primary" href="/api/incidents/${id}/report?revision=${row.number}&download=true">Download report</a>`:''}</div></div>`;
  if (row.error) body += `<div class="hint">${escapeHtml(row.error)}</div>`;
  if (['queued','running'].includes(row.state)) body += '<div class="panel busy"><span class="spinner"></span><h2>Processing this incident</h2><p>You can leave this page. The job and its results stay in the workspace.</p></div>';
  if (row.state==='needs_review') body += assignmentForm(row);
  if (row.state==='failed') body += '<div class="panel detail-section"><h2>Processing could not finish</h2><p>The files are retained. Review the error above, then retry the job.</p><button id="retry-job" class="button">Retry processing</button></div>';
  if (result) {
    body += navigationPanel(result);
    body += relayEvidencePanel(result);
    body += stageLocationsPanel(result.stage_locations);
    body += standardsAuditsPanel(result);
    const operationReview = result.operation_comparisons?.some(p => p.status === 'review differences');
    if (operationReview) body += '<div class="hint"><h2>Review relay differences</h2><p>Records contain different fault or operation observations. The selected-record rule assessment below does not resolve these differences.</p></div>';
    body += `<div class="panel result-banner"><span class="icon-box">${result.verdict === 'Correct operation' && !operationReview ? '✓' : '!'}</span><div><div class="eyebrow">SELECTED-RECORD RULE ASSESSMENT</div><h2>${escapeHtml(result.verdict)}</h2><p>${escapeHtml(result.location_text)}</p><p class="field-help">Line parameters: ${escapeHtml(result.parameter_status)}. Review all data-quality caveats in the report.</p></div></div>`;
    if (result.excluded?.length) body += `<details class="panel detail-section"><summary>Records not driving the estimate (${result.excluded.length})</summary><ul>${result.excluded.map(v=>`<li class="field-help">${escapeHtml(v)}</li>`).join('')}</ul></details>`;
    if (result.report_path) body += `<div class="panel"><div class="panel-heading"><h2>Incident report</h2><a href="/api/incidents/${id}/report?revision=${row.number}" target="_blank" rel="noopener">Open full report ↗</a></div><iframe class="report-frame" title="Incident analysis report" sandbox="allow-same-origin" src="/api/incidents/${id}/report?revision=${row.number}"></iframe></div>`;
  }
  body += `<details class="panel detail-section"><summary>Original file inventory (${row.files.length})</summary><table class="inventory"><tbody>${row.files.map(f=>`<tr><td>${escapeHtml(f.name)}</td><td>${size(f.size)}</td><td><code>${f.sha256.slice(0,16)}…</code></td></tr>`).join('')}</tbody></table></details>`;
  body += `<div class="bottom-grid"><div class="panel detail-section"><h2>Report revisions</h2><ul class="activity">${row.revisions.map(r=>`<li><a href="#incident/${id}/${r.number}">Revision ${r.number}</a> ${badge(r.state)}<small>${date(r.created)}</small></li>`).join('')}</ul></div><div class="panel detail-section"><h2>Activity</h2><ul class="activity">${row.activity.map(a=>`<li>${escapeHtml(a.message)}<small>${date(a.at)} · Revision ${a.revision}</small></li>`).join('')}</ul></div></div>`;
  $('detail-content').innerHTML=body;
  if (result) bindNavigation(row);
  if (['completed','attention','failed'].includes(row.state)) {
    const button=document.createElement('button');
    button.className='button';button.textContent='Review & rerun';
    document.querySelector('.detail-actions').append(button);
    button.onclick=async()=>{
      try{await api(`/api/incidents/${id}/reanalyse?revision=${row.number}`,{method:'POST'});location.hash=`incident/${id}`;await detail(id);}
      catch(error){notice(error.message);}
    };
  }
  if ($('review-form')) {
    bindMappingEditor();
    $('review-line').value=row.metadata.line_id || '';
    const selectedEnds=new Set();
    document.querySelectorAll('[data-record]').forEach(select => {
      if (select.disabled) return;
      const f=row.bundle.files.find(f=>f.name===select.dataset.record), declared=row.metadata.assignments?.[f.name];
      const label = document.createElement('label');
      label.className = 'field-help'; label.textContent = 'Protection system (separate from analysis role)';
      const system = document.createElement('select'); system.dataset.system = f.name;
      for (const name of ['unknown', 'Main-1', 'Main-2', 'other']) system.add(new Option(name, name));
      system.value = declared?.protection_system || f.protection_system || 'unknown';
      label.append(system); select.parentElement.append(label);
      const profileLabel = document.createElement('label');
      profileLabel.className = 'field-help'; profileLabel.textContent = 'Recording reference profile';
      const profile = document.createElement('select'); profile.dataset.profile = f.name;
      for (const [value, title] of Object.entries({'unconfirmed':'Unconfirmed', 'wg3-132-distance':'WG-3: 132 kV Main-1 distance', 'wg3-132-backup':'WG-3: 132 kV Main-2 backup', 'wg3-220plus-distance':'WG-3: 220 kV+ Main-1/Main-2 distance'})) profile.add(new Option(title, value));
      profile.value = declared?.recording_profile || f.recording_profile || 'unconfirmed';
      profileLabel.append(profile); select.parentElement.append(profileLabel);
      if (declared) select.value=declared.role==='excluded'?'excluded':`${declared.end}:${declared.role}`;
      else if (f.suggested_end && (!row.metadata.line_id || f.suggested_line_id===row.metadata.line_id)) {
        select.value=`${f.suggested_end}:${selectedEnds.has(f.suggested_end)?'corroborating':'primary'}`;
        selectedEnds.add(f.suggested_end);
      }
    });
    $('review-form').onsubmit = async event => {
      event.preventDefault(); notice(); const assignments={};
      let mappings, rxReviews;
      try { mappings=collectMappings(row); rxReviews=collectRxReviews(row,mappings); } catch(error) { return notice(error.message); }
      for (const select of document.querySelectorAll('[data-record]')) {
        if (select.disabled) continue;
        if (!select.value) return notice('Choose how to use each usable record, or explicitly exclude it.');
        const [end,role]=select.value==='excluded'?['','excluded']:select.value.split(':');
        const system = [...document.querySelectorAll('[data-system]')].find(s => s.dataset.system === select.dataset.record);
        const profile = [...document.querySelectorAll('[data-profile]')].find(s => s.dataset.profile === select.dataset.record);
        assignments[select.dataset.record]={end,role,protection_system:system?.value || 'unknown',recording_profile:profile?.value || 'unconfirmed'};
        if(mappings[select.dataset.record]) assignments[select.dataset.record].channel_mapping=mappings[select.dataset.record];
        if(rxReviews[select.dataset.record]) assignments[select.dataset.record].rx_review=rxReviews[select.dataset.record];
      }
      try { const stages=collectStageReviews(row,mappings,assignments); for(const [name,review] of Object.entries(stages)) assignments[name].stage_review=review; } catch(error) { return notice(error.message); }
      try { await api(`/api/incidents/${id}/review`,jsonPost({revision:row.number,line_id:$('review-line').value,assignments})); await detail(id); }
      catch(error){notice(error.message);}
    };
  }
  if ($('retry-job')) $('retry-job').onclick=async()=>{
    try{await api(`/api/incidents/${id}/retry?revision=${row.number}`,{method:'POST'});await detail(id,row.number);}
    catch(error){notice(error.message);}
  };
}

async function integrations() {
  const result=await api('/api/integrations');
  $('inbox-path').textContent=result.inbox;
  $('token-path').textContent=`${config.data_directory}/api-token.txt`;
  $('receipts').innerHTML=result.receipts.length?`<table><thead><tr><th>Source item</th><th>Receipt</th><th>Details</th><th>Updated</th></tr></thead><tbody>${result.receipts.map(r=>`<tr><td>${escapeHtml(r.path)}</td><td>${escapeHtml(r.state)}</td><td>${escapeHtml(r.message)}</td><td>${date(r.updated)}</td></tr>`).join('')}</tbody></table>`:'<div class="empty"><strong>No collector deliveries yet</strong>Place a completed event and its ready marker in the inbox to start.</div>';
}
async function route() {
  if (!config) return;
  notice(); current=null;
  const [view,id,revision]=(location.hash.slice(1)||'overview').split('/');
  const name=view==='incident'?'detail':['overview','upload','integrations'].includes(view)?view:'overview';
  document.querySelectorAll('.view').forEach(v=>v.hidden=v.id!==name);
  document.querySelectorAll('[data-nav]').forEach(v=>v.classList.toggle('active',v.dataset.nav===(name==='detail'?'overview':name)));
  $('breadcrumb').textContent=`Workspace / ${name==='detail'?'Incident':name[0].toUpperCase()+name.slice(1)}`;
  try {
    if(name==='overview') await overview();
    if(name==='upload') await uploadView(id);
    if(name==='integrations') await integrations();
    if(name==='detail') await detail(id,revision);
  }catch(error){notice(error.message);}
}
$('upload-form').onsubmit=submitUpload;
$('file-picker').onchange=event=>chooseFiles(event.target.files);
$('folder-picker').onchange=event=>chooseFiles(event.target.files);
$('choose-folder').onclick=()=>$('folder-picker').click();
$('dropzone').onclick=()=>$('file-picker').click();
$('dropzone').onkeydown=event=>{if(['Enter',' '].includes(event.key)){event.preventDefault();$('file-picker').click();}};
$('dropzone').ondragover=event=>{event.preventDefault();$('dropzone').classList.add('drag');};
$('dropzone').ondragleave=()=>$('dropzone').classList.remove('drag');
$('dropzone').ondrop=event=>{event.preventDefault();$('dropzone').classList.remove('drag');chooseFiles(event.dataTransfer.files);};
$('selected-files').onclick=event=>{if(event.target.dataset.remove!==undefined){selected.splice(Number(event.target.dataset.remove),1);renderFiles();}};
let searchTimer;
$('search').oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>{page=0;overview().catch(e=>notice(e.message));},250);};
$('state-filter').onchange=()=>{page=0;overview().catch(e=>notice(e.message));};
$('prev').onclick=()=>{page=Math.max(0,page-1);overview().catch(e=>notice(e.message));};
$('next').onclick=()=>{page++;overview().catch(e=>notice(e.message));};
$('scan-inbox').onclick=async()=>{try{await api('/api/integrations/scan',{method:'POST'});await integrations();}catch(e){notice(e.message);}};
window.addEventListener('hashchange',route);
setInterval(async()=>{
  if(polling||!config||document.hidden) return;
  polling=true;
  try{
    const [view,id,revision]=(location.hash.slice(1)||'overview').split('/');
    if(view==='overview') await overview();
    else if(view==='incident' && current && ['queued','running'].includes(current.state)) await detail(id,revision);
    else if(view==='integrations') await integrations();
  }catch(e){notice(e.message);}finally{polling=false;}
},2500);
(async()=>{try{config=await api('/api/config');await route();}catch(e){notice(`Cannot reach the local application: ${e.message}`);}})();
