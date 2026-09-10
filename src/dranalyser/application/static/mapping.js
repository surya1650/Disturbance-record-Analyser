'use strict';

function mappingEditor(row) {
  const targets=config.mapping_targets;
  if(!targets) return '<p class="field-help">Channel mapping review requires the updated backend.</p>';
  const records=(row.bundle?.files || []).filter(f=>f.kind==='comtrade' && f.ok && !f.duplicate_of);
  return `<section class="mapping-editor detail-section"><h3>Review channel identities</h3><p>Corrections apply only to this exact recording and this analysis revision. Original samples, labels, ratios and polarity are retained. All conformance checks run again.</p>${records.map(f=>{
    const previous=row.metadata.assignments?.[f.name]?.channel_mapping || {};
    const stale=previous.record_hash && previous.record_hash!==f.content_hash;
    const selected=stale ? {} : previous;
    const options=(kind,value)=>`<option value="">Automatic mapping</option><option value="ignore" ${value==='ignore'?'selected':''}>Leave unmapped / ignore meaning</option>${targets[kind].map(t=>`<option value="${escapeHtml(t)}" ${value===t?'selected':''}>${escapeHtml(t)}</option>`).join('')}`;
    return `<details class="mapping-record" data-map-file="${escapeHtml(f.name)}"><summary>${escapeHtml(f.name)} · ${(f.channel_inventory || []).length} original channel positions</summary><p class="field-help">Recording SHA-256 ${escapeHtml(f.content_hash)}</p>${stale ? '<p class="hint">Saved corrections refer to another recording hash. They have been cleared here; review these original channels before declaring replacements.</p>' : ''}<div class="table-wrap"><table class="evidence-table"><thead><tr><th>Position / original label</th><th>Declared quantity / scaling</th><th>Automatic interpretation</th><th>Reviewed interpretation</th></tr></thead><tbody>${(f.channel_inventory || []).map(c=>`<tr><td>${escapeHtml(c.id)} · ${escapeHtml(c.label || '(blank label)')}</td><td>${c.kind==='analog' ? `${escapeHtml(c.unit)} · phase ${escapeHtml(c.declared_phase || '?')} · ${escapeHtml(c.ps)}<small>Primary/secondary ${escapeHtml(c.primary)} / ${escapeHtml(c.secondary)}</small>` : 'Digital 0/1; no inversion applied'}</td><td>${escapeHtml(c.automatic || 'unmapped')}</td><td><select aria-label="${escapeHtml(c.id+' reviewed interpretation')}" data-map-id="${escapeHtml(c.id)}" data-map-kind="${c.kind}">${options(c.kind,selected[c.kind]?.[c.id])}</select></td></tr>`).join('')}</tbody></table></div><label>Reason / supporting evidence for corrections<input class="mapping-reason" maxlength="1000" value="${escapeHtml(selected.reason || '')}" placeholder="Describe the reviewed source or channel-label correction"></label><button type="button" class="button quiet mapping-reset">Restore automatic mapping</button><p class="field-help">A=analog position, D=digital position in CFG order. Phase A/B/C corresponds to R/Y/B. Collisions require explicit remapping or ignoring the competing channel. Unit or ratio correction is not supported here.</p></details>`;
  }).join('')}</section>`;
}

function collectMappings(row) {
  const result={};
  document.querySelectorAll('[data-map-file]').forEach(section=>{
    const file=row.bundle.files.find(f=>f.name===section.dataset.mapFile);
    const value={record_hash:file.content_hash,reason:section.querySelector('.mapping-reason').value.trim(),analog:{},digital:{}};
    section.querySelectorAll('[data-map-id]').forEach(select=>{
      if(select.value) value[select.dataset.mapKind][select.dataset.mapId]=select.value;
    });
    if(Object.keys(value.analog).length || Object.keys(value.digital).length) {
      if(!value.reason) throw new Error('Describe the reviewed mapping for '+file.name+'.');
      result[file.name]=value;
    }
  });
  return result;
}

function bindMappingEditor() {
  document.querySelectorAll('.mapping-reset').forEach(button=>button.onclick=()=>{
    const section=button.closest('[data-map-file]');
    section.querySelectorAll('[data-map-id]').forEach(s=>s.value='');
    section.querySelector('.mapping-reason').value='';
  });
}

function mappingEvidence(record) {
  const m=record.channel_mapping;
  if(!m || !m.record_hash) return '';
  const esc=escapeHtml;
  const rows=(record.channel_inventory || []).filter(c=>c.reviewed).map(c=>`<li>${esc(c.id)} · ${esc(c.label)} → ${esc(m[c.kind]?.[c.id] || c.selected)}</li>`).join('');
  return `<div class="hint"><strong>Reviewed channel mapping applied</strong><p>${esc(m.reason)}</p><p class="field-help">Original recording SHA-256 ${esc(m.record_hash)}. Values, ratios and polarity are unchanged.</p><ul>${rows}</ul>${record.mapping_original_flags?.length ? `<details><summary>Checks before reviewed mapping</summary><ul>${record.mapping_original_flags.map(f=>`<li>${esc(f)}</li>`).join('')}</ul></details>` : ''}</div>`;
}
