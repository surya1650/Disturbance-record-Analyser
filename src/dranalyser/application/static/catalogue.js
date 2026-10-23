'use strict';

async function catalogueView() {
  const host = document.getElementById('catalogue-content');
  host.innerHTML = '<p class="empty">Loading source catalogue…</p>';
  let offset = 0, generation = 0;
  const esc = escapeHtml;
  host.innerHTML = `<div class="toolbar"><input id="catalogue-search" aria-label="Search source catalogue" placeholder="Station, feeder, bus ID or reference…"><label><input id="catalogue-errors" type="checkbox"> Rows needing value review</label></div><div id="catalogue-summary"></div><div id="catalogue-table" class="table-wrap"></div><div class="pagination"><button class="button quiet" id="catalogue-prev">← Previous</button><span id="catalogue-page"></span><button class="button quiet" id="catalogue-next">Next →</button></div><div id="catalogue-detail" class="detail-section" aria-live="polite"></div>`;
  const el = id => host.querySelector('#'+id);
  async function load() {
    const request = ++generation;
    const params = new URLSearchParams({q:el('catalogue-search').value,errors_only:el('catalogue-errors').checked,offset,limit:50});
    const data = await api('/api/catalogue?'+params);
    if (request !== generation || !host.isConnected) return;
    if (!data.available) {
      host.innerHTML = '<div class="empty"><strong>No source catalogue imported</strong><p>Import the spreadsheet snapshot into this workspace to browse its line and relay evidence.</p></div>';
      return;
    }
    el('catalogue-summary').innerHTML = `<div class="hint"><strong>${data.summary.rows.toLocaleString()} source rows · ${data.summary.transmission_tabs} line tabs</strong><p>${data.summary.parseable_electrical_rows.toLocaleString()} rows have parseable electrical values. ${data.summary.missing_bus_id.toLocaleString()} lack a bus ID.</p><p>${esc(data.limits)}</p><small>Source modified ${esc(data.source.modified_time)} · Retrieved ${esc(data.source.retrieved_at)}</small><p><button class="button quiet" id="catalogue-template">Download blank registry review</button></p></div>`;
    el('catalogue-table').innerHTML = `<table><thead><tr><th>Station / feeder</th><th>Voltage / length</th><th>Bus ID / number</th><th>Source / reference</th><th>Review</th></tr></thead><tbody>${data.items.map(r=>`<tr><td><button class="button quiet" data-catalogue-row="${esc(r.id)}">${esc(r.station || 'Unknown station')}</button><small>${esc(r.feeder || 'Unknown feeder')} · ${esc(r.relay || 'Relay unspecified')}</small></td><td>${esc(r.kv ?? 'Unknown')} kV<small>${esc(r.length_km ?? 'Unknown')} km</small></td><td>${esc(r.bus_id || 'Unknown')}<small>${esc(r.bus_number || 'Unknown')}</small></td><td>${esc(r.sheet)} · row ${r.row}<small>${esc(r.reference)} · ${esc(r.reference_date || 'Date unspecified')}</small></td><td>${r.electrical_values_parseable?'Source review required':'Value errors'}<small>${r.issue_count} issue(s)</small></td></tr>`).join('') || '<tr><td colspan="5">No source rows match this search.</td></tr>'}</tbody></table>`;
    el('catalogue-prev').disabled = offset === 0;
    el('catalogue-next').disabled = offset+50 >= data.total;
    el('catalogue-page').textContent = `${data.total} matches · Page ${Math.floor(offset/50)+1}`;
    el('catalogue-template').onclick = async () => {
      try {
        const template = await api('/api/catalogue/review-template');
        const url = URL.createObjectURL(new Blob([JSON.stringify(template,null,2)],{type:'application/json'}));
        const a = document.createElement('a'); a.href=url;a.download='registry-review.json';a.click();URL.revokeObjectURL(url);
      } catch(error) { notice(error.message); }
    };
    for (const button of el('catalogue-table').querySelectorAll('[data-catalogue-row]')) button.onclick = () => showRow(button.dataset.catalogueRow).catch(e=>notice(e.message));
  }
  async function showRow(id) {
    const selected = id;
    el('catalogue-detail').dataset.selected = selected;
    const r = await api('/api/catalogue/rows/'+encodeURIComponent(id));
    if (el('catalogue-detail').dataset.selected !== selected) return;
    const quantity = key => r[key] ? `${r[key].r} + j${r[key].x} Ω (source base unconfirmed)` : 'Unavailable';
    el('catalogue-detail').innerHTML = `<h2>${esc(r.station)} / ${esc(r.feeder)}</h2><p><a href="${esc(r.url)}" target="_blank" rel="noopener">Open exact source row ↗</a> · ${esc(r.sheet)} row ${r.row}</p><p><strong>${esc(r.status)}</strong>. Reference date ${esc(r.reference_date || r.raw.date || 'unknown')} does not establish settings validity for an incident.</p><div class="table-wrap"><table><tbody>${[['Positive sequence',quantity('z1')],['Zero sequence',quantity('z0')],['CT ratio',r.raw.ct_ratio],['PT ratio',r.raw.vt_ratio],['Reference',r.reference],['Row ID',r.id],['Source checksum',r.row_hash]].map(([k,v])=>`<tr><th>${esc(k)}</th><td>${esc(v ?? 'Unknown')}</td></tr>`).join('')}</tbody></table></div><h3>Source reach / time entries</h3><p>Impedance base, full characteristic, phase/earth boundaries and event-effective version remain unconfirmed. These values are not zone polygons.</p><div class="table-wrap"><table><thead><tr><th>Zone</th><th>Reach as supplied</th><th>Time as supplied</th></tr></thead><tbody>${r.zones.map(z=>`<tr><td>${esc(z.name)}</td><td>${esc(z.reach_raw ?? 'Missing')}</td><td>${esc(z.time_raw ?? 'Missing')}</td></tr>`).join('')}</tbody></table></div><h3>Input issues</h3><ul>${r.issues.map(i=>`<li>${esc(i.severity)} · ${esc(i.field)}: ${esc(i.detail)}</li>`).join('') || '<li>No parsing errors. Independent source and identity review remains required.</li>'}</ul><h3>Reciprocal-end candidates</h3><p>Exact formatting-normalized station/feeder reversals only. Spelling variants and circuit suffixes are retained; no pairing is applied automatically.</p><ul>${r.reciprocal_candidates.map(c=>`<li>${esc(c.station)} / ${esc(c.feeder)} · ${esc(c.status)}<br>Disagreements: ${esc(c.disagreements.join(', ') || 'none in compared source values')}</li>`).join('') || '<li>No exact reciprocal candidate. This does not establish absence of the remote terminal.</li>'}</ul>`;
    el('catalogue-detail').scrollIntoView({block:'start'});
  }
  let timer;
  el('catalogue-search').oninput = () => {clearTimeout(timer);timer=setTimeout(()=>{offset=0;load().catch(e=>notice(e.message));},250);};
  el('catalogue-errors').onchange = () => {offset=0;load().catch(e=>notice(e.message));};
  el('catalogue-prev').onclick = () => {offset=Math.max(0,offset-50);load().catch(e=>notice(e.message));};
  el('catalogue-next').onclick = () => {offset+=50;load().catch(e=>notice(e.message));};
  await load();
}
