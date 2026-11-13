'use strict';

// Presentation of staged source evidence. Choosing a catalogue never reviews its engineering facts.
const DRCatalogue = (() => {
  const MAX_BYTES = 16 * 1024 * 1024, PAGE_SIZE = 50;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const count = value => Number.isFinite(value) && value >= 0 ? value.toLocaleString() : '0';
  const text = value => typeof value === 'object' && value !== null ? JSON.stringify(value) : String(value ?? '');
  const kind = row => row.kind || 'TL';
  function validateFile(file) {
    if (!file || !/\.xlsx$/i.test(file.name)) return 'Choose an Excel .xlsx workbook.';
    if (!file.size) return 'The workbook is empty.';
    if (file.size > MAX_BYTES) return 'The workbook must be 16 MiB or smaller.';
    return '';
  }
  function filters(values, offset = 0) {
    return new URLSearchParams({q:values.q || '',circle:values.circle || '',station:values.station || '',kind:values.kind || '',errors_only:!!values.errors_only,offset,limit:PAGE_SIZE});
  }
  function options(values, selected, label) {
    return `<option value="">${esc(label)}</option>` + [...new Set(values || [])].map(v => `<option value="${esc(v)}"${v === selected ? ' selected' : ''}>${esc(v)}</option>`).join('');
  }
  const facts = rows => `<div class="table-wrap"><table><tbody>${rows.map(([k,v]) => `<tr><th>${esc(k)}</th><td>${esc(text(v ?? 'Unknown'))}</td></tr>`).join('')}</tbody></table></div>`;
  function issueList(issues) {
    return `<ul>${(issues || []).map(i => `<li>${esc(i.severity)} · ${esc(i.field || i.code)}: ${esc(i.detail || i.message)}</li>`).join('') || '<li>No parsing errors. Independent source and identity review remains required.</li>'}</ul>`;
  }
  function sourceLink(row) {
    const url = /^https?:\/\//i.test(row.url || '') ? `<a href="${esc(row.url)}" target="_blank" rel="noopener">Open exact source row ↗</a> · ` : '';
    return `<p>${url}${esc(row.sheet)} · row ${esc(row.row)}</p>`;
  }
  function sourceCells(row) {
    const cells = row.cells || {}, location = row.source_locator;
    return `<details class="catalogue-source-cells"><summary>Original sheet and cell references</summary>${location ? facts([['Workbook',location.file_name],['Original workbook SHA-256',location.sha256],['Sheet',location.sheet],['Original row',location.row]]) : ''}${facts(Object.entries(cells))}</details>`;
  }
  function sourceFields(row) {
    if (Array.isArray(row.source_values)) return row.source_values.map((value,index)=>[row.source_headers?.[index] || `Column ${index+1}`,value]);
    return Object.entries(row.source_values || row.raw || {});
  }
  function rowMarkup(row) {
    const raw = row.raw || {};
    const heading = `<h2>${esc(row.station || 'Unknown station')} / ${kind(row) === 'PTR' || row.inventory_only ? 'Transformer inventory' : esc(row.feeder || 'Unknown feeder')}</h2>${sourceLink(row)}`;
    const issues = `<h3>Input issues</h3>${issueList(row.issues)}`;
    if (kind(row) === 'PTR' || row.inventory_only) {
      return `${heading}<p><strong>PTR inventory only · Unreviewed source evidence</strong></p><p>Transformer values are retained as supplied. They do not define a transmission line or establish operational settings.</p>${facts([
        ['Circle',row.circle],['Capacity / winding capacity as supplied',row.transformer_capacity ?? raw.transformer_capacity ?? raw.capacity],
        ['Winding voltage as supplied',row.winding_voltage_raw ?? row.winding_voltage ?? raw.kv ?? raw.winding_voltage ?? raw.voltage],
        ['Vector group',row.vector_group ?? raw.vector_group],['CT available as supplied',row.ct_available_raw],['CT adopted as supplied',row.ct_adopted_raw ?? raw.ct_ratio],
        ['Percentage impedance as supplied',row.impedance_percent_raw ?? raw.percent_impedance ?? raw.impedance_percent ?? raw.z_percent],
        ['Reference',row.reference],['Row ID',row.id],['Source checksum',row.row_hash]])}${issues}${sourceCells(row)}<details><summary>All original transformer fields</summary>${facts(sourceFields(row))}</details>`;
    }
    const quantity = key => row[key] ? `${row[key].r} + j${row[key].x} Ω (source base unconfirmed)` : 'Unavailable';
    return `${heading}<p><strong>${esc(row.status)}</strong>. Reference date ${esc(row.reference_date || raw.date || 'unknown')} does not establish settings validity for an incident.</p>${facts([['Positive sequence',quantity('z1')],['Zero sequence',quantity('z0')],['CT ratio',raw.ct_ratio],['PT ratio',raw.vt_ratio],['Reference',row.reference],['Row ID',row.id],['Source checksum',row.row_hash]])}<h3>Source reach / time entries</h3><p>Impedance base, full characteristic, phase/earth boundaries and event-effective version remain unconfirmed. These values are not zone polygons.</p><div class="table-wrap"><table><thead><tr><th>Zone</th><th>Reach as supplied</th><th>Time as supplied</th></tr></thead><tbody>${(row.zones || []).map(z=>`<tr><td>${esc(z.name)}</td><td>${esc(z.reach_raw ?? 'Missing')}</td><td>${esc(z.time_raw ?? 'Missing')}</td></tr>`).join('')}</tbody></table></div>${issues}<h3>Reciprocal-end candidates</h3><p>Exact formatting-normalized station/feeder reversals only. Spelling variants and circuit suffixes are retained; no pairing is applied automatically.</p><ul>${(row.reciprocal_candidates || []).map(c=>`<li>${esc(c.station)} / ${esc(c.feeder)} · ${esc(c.status)}<br>Disagreements: ${esc((c.disagreements || []).join(', ') || 'none in compared source values')}</li>`).join('') || '<li>No exact reciprocal candidate. This does not establish absence of the remote terminal.</li>'}</ul>${sourceCells(row)}`;
  }
  function tableMarkup(items) {
    return `<table><thead><tr><th>Kind / station / feeder</th><th>Voltage / size</th><th>Bus ID / number</th><th>Source / reference</th><th>Review</th></tr></thead><tbody>${(items || []).map(r=>`<tr><td><span class="badge">${esc(kind(r))}</span><button class="button quiet" data-catalogue-row="${esc(r.id)}">${esc(r.station || 'Unknown station')}</button><small>${esc(r.circle)} · ${kind(r) === 'PTR' || r.inventory_only ? esc(r.transformer_capacity || 'Transformer inventory') : `${esc(r.feeder || 'Unknown feeder')} · ${esc(r.relay || 'Relay unspecified')}`}</small></td><td>${esc(r.kv ?? 'Unknown')} kV<small>${kind(r) === 'PTR' || r.inventory_only ? esc(text(r.transformer_capacity ?? 'Capacity unspecified')) : `${esc(r.length_km ?? 'Unknown')} km`}</small></td><td>${esc(r.bus_id || 'Unknown')}<small>${esc(r.bus_number || 'Unknown')}</small></td><td>${esc(r.sheet)} · row ${esc(r.row)}<small>${esc(r.reference)} · ${esc(r.reference_date || 'Date unspecified')}</small></td><td>${r.inventory_only || kind(r) === 'PTR' ? 'Inventory only' : r.electrical_values_parseable ? 'Source review required' : 'Value errors'}<small>${count(r.issue_count)} issue(s)</small></td></tr>`).join('') || '<tr><td colspan="5">No source rows match this search.</td></tr>'}</tbody></table>`;
  }
  function summaryMarkup(data) {
    if (!data.available) return '<div class="empty"><strong>No source catalogue selected</strong><p>Upload a workbook above to preview its source evidence, then choose “Use in catalogue”.</p></div>';
    const s = data.summary || {}, source = data.source || {};
    return `<div class="hint"><strong>${count(s.rows)} source rows · Unreviewed source evidence</strong><p>${count(s.transmission_rows ?? s.tl_rows ?? s.rows)} TL rows · ${count(s.transformer_rows ?? s.ptr_rows)} PTR rows</p><p>${esc(data.limits)}</p><small>${esc(source.file_name || source.filename || source.title || '')}${source.modified_time ? ` · Source modified ${esc(source.modified_time)}` : ''}${source.retrieved_at ? ` · Retrieved ${esc(source.retrieved_at)}` : ''}</small><small>Catalogue SHA-256 <code>${esc(data.catalogue_hash)}</code></small>${(data.facets?.kinds || ['TL']).includes('TL') ? '<p><button class="button quiet" id="catalogue-template">Download blank registry review</button></p>' : ''}</div>`;
  }
  function previewMarkup(preview) {
    const s = preview.summary || {}, source = preview.source || {}, issues = s.issues || {};
    const issuesRows = Object.entries(issues).map(([name,total])=>`<li>${esc(name)}: ${esc(text(total))}</li>`).join('');
    return `<h2>Workbook preview</h2><p><strong>${esc(source.file_name || source.filename || source.original_filename || source.title || 'Excel workbook')}</strong></p><p>${count(s.rows)} source rows · ${count(s.transmission_rows ?? s.tl_rows)} TL rows · ${count(s.transformer_rows ?? s.ptr_rows)} PTR rows</p><small>Original workbook SHA-256 <code>${esc(preview.import_id)}</code></small><p>${esc(preview.limits || 'Unreviewed source evidence. Independent engineering review is required.')}</p><details><summary>Import issues and source coverage</summary>${issuesRows ? `<ul>${issuesRows}</ul>` : '<p>No parsing issues reported.</p>'}${facts(Object.entries(s).filter(([k])=>!['issues'].includes(k)))}</details><div class="catalogue-preview-actions"><button type="button" class="button primary" id="catalogue-activate"${preview.active ? ' disabled' : ''}>${preview.active ? 'In use in catalogue' : 'Use in catalogue'}</button><a class="button quiet" href="/api/catalogue/imports/${encodeURIComponent(preview.import_id)}/original" download>Download original workbook</a></div><p>Using this version changes the source catalogue for browsing. Engineering review and the approved registry remain separate.</p>`;
  }
  function historyMarkup(items) {
    return (items || []).map(item=>`<li><button type="button" class="button quiet" data-catalogue-import="${esc(item.import_id)}">${esc(item.source?.file_name || item.source?.filename || item.source?.title || 'Excel workbook')}</button><small>${esc(item.created_at)}${item.active ? ' · In use' : ''} · ${count(item.summary?.rows)} rows</small><code>${esc(item.import_id)}</code></li>`).join('') || '<li>No workbook versions uploaded yet.</li>';
  }
  let mounted = null;
  async function mount(host, request, environment = {}) {
    mounted?.dispose();
    const lifetime = new AbortController();
    let listController, detailController, offset = 0, listGeneration = 0, detailGeneration = 0, previewGeneration = 0, timer;
    let activeHash = null, preview = null, uploadPending = false, activationPending = false;
    const active = () => !lifetime.signal.aborted && host.isConnected && (!environment.isCurrent || environment.isCurrent());
    const el = id => host.querySelector('#'+id);
    const dispose = () => { clearTimeout(timer); lifetime.abort(); listController?.abort(); detailController?.abort(); };
    mounted = {dispose};
    if (typeof window !== 'undefined') window.addEventListener('hashchange',dispose,{once:true,signal:lifetime.signal});
    const report = error => { if (active() && error.name !== 'AbortError') el('catalogue-message').textContent = error.message; };
    const safely = task => Promise.resolve().then(task).catch(report);
    host.innerHTML = `<section class="catalogue-upload"><div><h2>Import Excel source evidence</h2><p>Choose an .xlsx workbook to preview its TL and PTR rows. Maximum 16 MiB.</p></div><label class="button" for="catalogue-file">Choose workbook</label><input id="catalogue-file" type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"><span id="catalogue-upload-state" role="status"></span></section><p id="catalogue-message" role="status" aria-live="polite"></p><section id="catalogue-preview" class="catalogue-preview" hidden></section><details class="catalogue-history"><summary>Workbook version history</summary><ul id="catalogue-history-list"><li>Loading versions…</li></ul></details><div class="toolbar catalogue-filters"><label>Search<input id="catalogue-search" maxlength="200" placeholder="Station, feeder, bus ID or reference…"></label><label>Circle<select id="catalogue-circle"><option value="">All circles</option></select></label><label>Station<select id="catalogue-station"><option value="">All stations</option></select></label><label>Kind<select id="catalogue-kind"><option value="">All kinds</option><option>TL</option><option>PTR</option></select></label><label class="catalogue-errors-label"><input id="catalogue-errors" type="checkbox"> Rows with value errors</label></div><div id="catalogue-summary"></div><div id="catalogue-table" class="table-wrap"></div><div class="pagination"><button type="button" class="button quiet" id="catalogue-prev">← Previous</button><span id="catalogue-page"></span><button type="button" class="button quiet" id="catalogue-next">Next →</button></div><div id="catalogue-detail" class="detail-section" aria-live="polite"></div>`;
    function setBusy() {
      el('catalogue-file').disabled = uploadPending || activationPending;
      const button = el('catalogue-activate');
      if (button) { button.disabled = uploadPending || activationPending || !!preview?.active; button.textContent = activationPending ? 'Selecting version…' : preview?.active ? 'In use in catalogue' : 'Use in catalogue'; }
    }
    async function loadHistory() {
      const data = await request('/api/catalogue/imports',{signal:lifetime.signal});
      if (!active()) return;
      el('catalogue-history-list').innerHTML = historyMarkup(data.items);
      for (const button of el('catalogue-history-list').querySelectorAll('[data-catalogue-import]')) button.onclick = () => safely(async()=>{
        if (uploadPending || activationPending) return;
        const generation = ++previewGeneration;
        button.disabled = true;
        try {
          const value = await request('/api/catalogue/imports/'+encodeURIComponent(button.dataset.catalogueImport),{signal:lifetime.signal});
          if (active() && generation === previewGeneration) showPreview(value);
        } finally { if (active()) button.disabled = false; }
      });
    }
    function showPreview(value) {
      preview = value;
      el('catalogue-preview').hidden = false;
      el('catalogue-preview').innerHTML = previewMarkup(value);
      el('catalogue-activate').onclick = () => safely(activate);
      setBusy();
    }
    async function activate() {
      if (!preview || activationPending || uploadPending || preview.active) return;
      const selected = preview;
      ++previewGeneration;
      activationPending = true; setBusy(); el('catalogue-message').textContent = '';
      try {
        await request('/api/catalogue/imports/'+encodeURIComponent(selected.import_id)+'/activate', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_active_hash:selected.expected_active_hash ?? null}),signal:lifetime.signal});
        if (!active()) return;
        showPreview({...selected,active:true});
        offset = 0;
        el('catalogue-detail').innerHTML = '';
        await load();
        if (!active()) return;
        el('catalogue-message').textContent = 'Workbook selected for source browsing. Its engineering values remain unreviewed.';
        await loadHistory();
      } catch (error) {
        if (active() && error.name !== 'AbortError') {
          el('catalogue-message').textContent = error.message;
          await load();
          const refreshed = await request('/api/catalogue/imports/'+encodeURIComponent(selected.import_id),{signal:lifetime.signal});
          if (active()) showPreview(refreshed);
        }
      } finally { activationPending = false; if (active()) setBusy(); }
    }
    async function load() {
      const generation = ++listGeneration;
      listController?.abort(); detailController?.abort(); ++detailGeneration;
      listController = new AbortController();
      el('catalogue-prev').disabled = true; el('catalogue-next').disabled = true;
      const values = {q:el('catalogue-search').value,circle:el('catalogue-circle').value,station:el('catalogue-station').value,kind:el('catalogue-kind').value,errors_only:el('catalogue-errors').checked};
      const data = await request('/api/catalogue?'+filters(values,offset),{signal:listController.signal});
      if (!active() || generation !== listGeneration) return;
      if (activeHash !== (data.catalogue_hash || null)) el('catalogue-detail').innerHTML = '';
      activeHash = data.catalogue_hash || null;
      el('catalogue-summary').innerHTML = summaryMarkup(data);
      if (data.facets) {
        for (const [key,label] of [['circle','All circles'],['station','All stations'],['kind','All kinds']]) {
          el('catalogue-'+key).innerHTML = options(data.facets[key === 'kind' ? 'kinds' : key+'s'],values[key],label);
        }
      }
      el('catalogue-table').innerHTML = data.available ? tableMarkup(data.items) : '';
      el('catalogue-prev').disabled = offset === 0 || !data.available;
      el('catalogue-next').disabled = offset+PAGE_SIZE >= data.total || !data.available;
      el('catalogue-page').textContent = data.available ? `${count(data.total)} matches · Page ${Math.floor(offset/PAGE_SIZE)+1}` : '';
      if (el('catalogue-template')) el('catalogue-template').onclick = event => safely(async()=>{
        const button = event.currentTarget; button.disabled = true;
        try {
          const template = await request('/api/catalogue/review-template',{signal:lifetime.signal});
          if (!active()) return;
          const url = URL.createObjectURL(new Blob([JSON.stringify(template,null,2)],{type:'application/json'}));
          const a = document.createElement('a'); a.href=url; a.download='registry-review.json'; a.click(); URL.revokeObjectURL(url);
        } finally { if (active()) button.disabled=false; }
      });
      for (const button of el('catalogue-table').querySelectorAll('[data-catalogue-row]')) button.onclick = () => safely(()=>showRow(button));
    }
    async function showRow(button) {
      detailController?.abort(); detailController = new AbortController();
      const generation = ++detailGeneration, expectedHash = activeHash;
      button.disabled = true;
      el('catalogue-detail').textContent = 'Loading source row…';
      try {
        const row = await request('/api/catalogue/rows/'+encodeURIComponent(button.dataset.catalogueRow),{signal:detailController.signal});
        if (!active() || generation !== detailGeneration || activeHash !== expectedHash) return;
        if (row.catalogue_hash && row.catalogue_hash !== expectedHash) {
          el('catalogue-message').textContent = 'The active catalogue changed. Select a source row from the refreshed list.';
          await load(); return;
        }
        el('catalogue-detail').innerHTML = rowMarkup(row);
        el('catalogue-detail').scrollIntoView({block:'start'});
      } finally { if (active()) button.disabled = false; }
    }
    el('catalogue-file').onchange = () => safely(async()=>{
      if (uploadPending || activationPending) return;
      const file = el('catalogue-file').files[0], error = validateFile(file);
      if (error) { el('catalogue-message').textContent=error; return; }
      const generation = ++previewGeneration;
      uploadPending = true; preview = null; el('catalogue-preview').hidden = true; setBusy();
      el('catalogue-message').textContent = ''; el('catalogue-upload-state').textContent = 'Preparing workbook preview…';
      try {
        const body = new FormData(); body.append('file',file);
        const value = await request('/api/catalogue/imports',{method:'POST',body,signal:lifetime.signal});
        if (!active() || generation !== previewGeneration) return;
        showPreview(value);
        el('catalogue-upload-state').textContent = 'Preview ready. Review it below before using this version.';
        await loadHistory();
      } finally { uploadPending=false; if (active()) {setBusy(); el('catalogue-file').value=''; if (!preview) el('catalogue-upload-state').textContent='';} }
    });
    el('catalogue-search').oninput = () => { clearTimeout(timer); timer=setTimeout(()=>{offset=0;safely(load);},250); };
    for (const key of ['circle','station','kind','errors']) el('catalogue-'+key).onchange = () => { clearTimeout(timer); if (key === 'circle') el('catalogue-station').value = ''; offset=0; safely(load); };
    el('catalogue-prev').onclick = () => { offset=Math.max(0,offset-PAGE_SIZE); safely(load); };
    el('catalogue-next').onclick = () => { offset+=PAGE_SIZE; safely(load); };
    await Promise.all([load(),loadHistory().catch(report)]);
    return {dispose};
  }
  return {mount,validateFile,filters,options,rowMarkup,tableMarkup,summaryMarkup,previewMarkup,historyMarkup,MAX_BYTES};
})();

async function catalogueView() {
  const generation = routeGeneration;
  return DRCatalogue.mount(document.getElementById('catalogue-content'),api,{isCurrent:()=>generation===routeGeneration});
}
if (typeof module !== 'undefined') module.exports = DRCatalogue;
